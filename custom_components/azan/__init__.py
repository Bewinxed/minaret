"""The Minaret integration - Prayer times & azan playback for Home Assistant."""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.network import get_url
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AZAN_URL,
    CONF_EXTERNAL_URL,
    CONF_FAJR_URL,
    CONF_MEDIA_PLAYER,
    CONF_NOTIFY_SERVICE,
    CONF_OFFSET_MINUTES,
    CONF_OUTPUT_DEVICE,
    CONF_PLAYBACK_MODE,
    CONF_SUHOOR_URL,
    DEFAULT_OFFSET_MINUTES,
    DOMAIN,
)
from .coordinator import AzanCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

# Service schemas
SERVICE_PLAY_SCHEMA = vol.Schema(
    {
        vol.Required("prayer", default="Test"): vol.In(
            ["Suhoor", "Fajr", "Dhuhr", "Asr", "Maghrib", "Isha", "Test"]
        ),
    }
)


def _resolve_output_device(config: dict) -> tuple[str, str]:
    """Resolve the output device from config, handling legacy formats.

    Returns (device_type, device_id) where:
    - device_type is "media_player" or "notify"
    - device_id is the entity_id or notify service name
    """
    # New format: "media_player:media_player.living_room" or "notify:mobile_app_saga"
    output_device = config.get(CONF_OUTPUT_DEVICE, "")
    if output_device:
        if ":" in output_device:
            parts = output_device.split(":", 1)
            return parts[0], parts[1]
        # Raw value without prefix - guess from format
        if output_device.startswith("media_player."):
            return "media_player", output_device
        return "notify", output_device

    # Legacy format migration
    playback_mode = config.get(CONF_PLAYBACK_MODE, "")
    if playback_mode == "media_player":
        entity_id = config.get(CONF_MEDIA_PLAYER, "")
        return "media_player", entity_id
    elif playback_mode == "android_vlc":
        service = config.get(CONF_NOTIFY_SERVICE, "")
        return "notify", service

    # Fallback: check for legacy keys directly
    if config.get(CONF_MEDIA_PLAYER):
        return "media_player", config[CONF_MEDIA_PLAYER]
    if config.get(CONF_NOTIFY_SERVICE):
        return "notify", config[CONF_NOTIFY_SERVICE]

    return "", ""


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Azan Prayer Times from a config entry."""
    config = {**entry.data, **entry.options}

    coordinator = AzanCoordinator(hass, config)
    coordinator.config_entry = entry

    # Store integration data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "is_playing": False,
        "currently_playing": None,
        "is_downloading": False,
        "audio_file": None,
        "fajr_audio_file": None,
        "suhoor_audio_file": None,
        "unsub_timer": None,
        "playback_reset_unsub": None,
    }

    store = hass.data[DOMAIN][entry.entry_id]

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    # Forward platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Download audio in background (yt-dlp is blocking)
    async def _download_audio_background():
        azan_url = config.get(CONF_AZAN_URL)
        fajr_url = config.get(CONF_FAJR_URL)

        store["is_downloading"] = True
        if coordinator.data:
            coordinator.async_set_updated_data(coordinator.data)

        audio_dir = Path(hass.config.path("www", "azan"))

        if azan_url:
            try:
                path = await hass.async_add_executor_job(
                    _download_audio, hass, azan_url, "azan"
                )
                store["audio_file"] = path
                _LOGGER.info("Azan audio ready: %s", path)
            except Exception:
                _LOGGER.exception("Failed to download azan audio")
                # Fall back to cached file if it exists on disk
                cached = audio_dir / "azan.mp3"
                if cached.exists():
                    store["audio_file"] = str(cached)
                    _LOGGER.info("Using cached azan audio: %s", cached)

        if fajr_url:
            try:
                path = await hass.async_add_executor_job(
                    _download_audio, hass, fajr_url, "fajr_azan"
                )
                store["fajr_audio_file"] = path
                _LOGGER.info("Fajr audio ready: %s", path)
            except Exception:
                _LOGGER.exception("Failed to download fajr audio")
                # Fall back to cached file if it exists on disk
                cached = audio_dir / "fajr_azan.mp3"
                if cached.exists():
                    store["fajr_audio_file"] = str(cached)
                    _LOGGER.info("Using cached fajr audio: %s", cached)

        suhoor_url = config.get(CONF_SUHOOR_URL)
        if suhoor_url:
            try:
                path = await hass.async_add_executor_job(
                    _download_audio, hass, suhoor_url, "suhoor"
                )
                store["suhoor_audio_file"] = path
                _LOGGER.info("Suhoor audio ready: %s", path)
            except Exception:
                _LOGGER.exception("Failed to download suhoor audio")
                cached = audio_dir / "suhoor.mp3"
                if cached.exists():
                    store["suhoor_audio_file"] = str(cached)
                    _LOGGER.info("Using cached suhoor audio: %s", cached)

        store["is_downloading"] = False
        if coordinator.data:
            coordinator.async_set_updated_data(coordinator.data)

    entry.async_create_background_task(
        hass, _download_audio_background(), "azan_audio_download"
    )

    # Schedule azan playback
    _schedule_next_prayer(hass, entry)

    # Register services
    _register_services(hass, entry)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update - reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Azan Prayer Times config entry."""
    store = hass.data[DOMAIN].get(entry.entry_id, {})

    # Cancel scheduled timer
    unsub = store.get("unsub_timer")
    if unsub:
        unsub()

    # Cancel playback reset timer
    reset_unsub = store.get("playback_reset_unsub")
    if reset_unsub:
        reset_unsub()

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # Remove services if no more entries
        if not hass.data[DOMAIN]:
            for service_name in ("play_azan", "stop_playback", "refresh_times"):
                hass.services.async_remove(DOMAIN, service_name)

    return unloaded


# --- Audio Download ---


def _download_audio(hass: HomeAssistant, url: str, name: str) -> str:
    """Download audio using yt-dlp (runs in executor thread)."""
    audio_dir = Path(hass.config.path("www", "azan"))
    audio_dir.mkdir(parents=True, exist_ok=True)

    out_path = audio_dir / f"{name}.mp3"
    marker_path = audio_dir / f".{name}.url"

    # Check cache -- if same URL and file exists, skip download entirely
    if out_path.exists() and marker_path.exists():
        existing_url = marker_path.read_text().strip()
        if existing_url == url:
            _LOGGER.debug("Audio already cached: %s", name)
            return str(out_path)

    _LOGGER.info("Downloading audio: %s -> %s", url, name)

    # Download to a temp name so we don't clobber a working cached file
    tmp_name = f".{name}_tmp"

    import yt_dlp

    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",
            }
        ],
        "outtmpl": str(audio_dir / f"{tmp_name}.%(ext)s"),
        "noplaylist": True,
        "overwrites": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # Find the downloaded temp file and move it to the final path
    tmp_mp3 = audio_dir / f"{tmp_name}.mp3"
    if tmp_mp3.exists():
        shutil.move(str(tmp_mp3), str(out_path))
    else:
        # yt-dlp may output with a different extension before post-processing
        for f in audio_dir.iterdir():
            if f.stem == tmp_name and not f.name.startswith(".."):
                shutil.move(str(f), str(out_path))
                break

    # Clean up any leftover temp files
    for f in audio_dir.iterdir():
        if f.stem.startswith(f".{name}_tmp"):
            f.unlink(missing_ok=True)

    if not out_path.exists():
        raise FileNotFoundError(f"Audio file not found after download: {out_path}")

    marker_path.write_text(url)
    _LOGGER.info("Audio downloaded: %s", name)
    return str(out_path)


# --- Playback ---


async def _play_azan(hass: HomeAssistant, entry: ConfigEntry, prayer_name: str) -> None:
    """Play the azan audio on the configured device."""
    store = hass.data[DOMAIN].get(entry.entry_id)
    if not store:
        return

    config = {**entry.data, **entry.options}
    device_type, device_id = _resolve_output_device(config)

    if not device_type or not device_id:
        _LOGGER.warning("No output device configured")
        return

    # Pick the right audio file
    audio_file = store.get("audio_file")
    if prayer_name == "Fajr" and store.get("fajr_audio_file"):
        audio_file = store["fajr_audio_file"]
    elif prayer_name == "Suhoor" and store.get("suhoor_audio_file"):
        audio_file = store["suhoor_audio_file"]

    if not audio_file or not os.path.exists(audio_file):
        _LOGGER.warning("No audio file available for %s", prayer_name)
        return

    filename = os.path.basename(audio_file)

    # Build the media URL
    if device_type == "media_player":
        # For media_player, prefer internal URL
        try:
            base_url = get_url(hass, allow_internal=True, prefer_external=False)
        except Exception:
            try:
                base_url = get_url(hass, allow_external=True, prefer_external=True)
            except Exception:
                base_url = get_url(hass)
    else:
        # For Android notify, use configured external URL
        base_url = config.get(CONF_EXTERNAL_URL, "").rstrip("/")
        if not base_url:
            try:
                base_url = get_url(hass, allow_external=True, prefer_external=True)
            except Exception:
                base_url = get_url(hass)

    media_url = f"{base_url}/local/azan/{filename}"

    coordinator: AzanCoordinator = store["coordinator"]

    # Mark as playing
    store["is_playing"] = True
    store["currently_playing"] = prayer_name

    # Mark prayer as played (unless test)
    if prayer_name != "Test" and coordinator.data:
        coordinator.data.played_today.add(prayer_name)

    # Trigger sensor updates for status change
    if coordinator.data:
        coordinator.async_set_updated_data(coordinator.data)

    _LOGGER.info("Playing azan for %s via %s (%s): %s", prayer_name, device_type, device_id, media_url)

    try:
        if device_type == "media_player":
            # --- Smart Speaker / Media Player ---
            await hass.services.async_call(
                "media_player",
                "play_media",
                {
                    "entity_id": device_id,
                    "media_content_id": media_url,
                    "media_content_type": "music",
                },
            )
        else:
            # --- Android via notify service ---
            # Wake screen first
            await hass.services.async_call(
                "notify",
                device_id,
                {
                    "message": "command_screen_on",
                    "data": {"ttl": 0, "priority": "high"},
                },
            )

            # Launch VLC with the audio URL
            await hass.services.async_call(
                "notify",
                device_id,
                {
                    "message": "command_activity",
                    "data": {
                        "intent_action": "android.intent.action.VIEW",
                        "intent_uri": media_url,
                        "intent_type": "audio/mpeg",
                        "intent_package_name": "org.videolan.vlc",
                        "ttl": 0,
                        "priority": "high",
                    },
                },
            )
    except Exception:
        _LOGGER.exception("Failed to play azan via %s (%s)", device_type, device_id)
        store["is_playing"] = False
        store["currently_playing"] = None
        if coordinator.data:
            coordinator.async_set_updated_data(coordinator.data)
        return

    # Reset playing state after 5 minutes
    @callback
    def _reset_playing(_now):
        if store.get("currently_playing") == prayer_name:
            store["is_playing"] = False
            store["currently_playing"] = None
            # Trigger sensor update
            coordinator = store.get("coordinator")
            if coordinator and coordinator.data:
                coordinator.async_set_updated_data(coordinator.data)

    reset_unsub = store.get("playback_reset_unsub")
    if reset_unsub:
        reset_unsub()

    store["playback_reset_unsub"] = async_track_point_in_time(
        hass, _reset_playing, dt_util.now() + timedelta(minutes=5)
    )

    # Schedule next prayer after this one
    _schedule_next_prayer(hass, entry)


async def _stop_playback(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Stop the currently playing azan."""
    store = hass.data[DOMAIN].get(entry.entry_id)
    if not store:
        return

    store["is_playing"] = False
    store["currently_playing"] = None

    config = {**entry.data, **entry.options}
    device_type, device_id = _resolve_output_device(config)

    if not device_type or not device_id:
        return

    try:
        if device_type == "media_player":
            await hass.services.async_call(
                "media_player",
                "media_stop",
                {"entity_id": device_id},
            )
        else:
            await hass.services.async_call(
                "notify",
                device_id,
                {
                    "message": "command_media",
                    "data": {
                        "media_command": "stop",
                        "media_package_name": "org.videolan.vlc",
                        "ttl": 0,
                        "priority": "high",
                    },
                },
            )
        _LOGGER.info("Stopped azan playback via %s (%s)", device_type, device_id)
    except Exception:
        _LOGGER.exception("Failed to stop playback via %s (%s)", device_type, device_id)

    # Trigger sensor update
    coordinator = store.get("coordinator")
    if coordinator and coordinator.data:
        coordinator.async_set_updated_data(coordinator.data)


# --- Scheduling ---


@callback
def _schedule_next_prayer(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Schedule a callback for the next upcoming prayer."""
    store = hass.data[DOMAIN].get(entry.entry_id)
    if not store:
        return

    # Cancel existing timer
    unsub = store.get("unsub_timer")
    if unsub:
        unsub()
        store["unsub_timer"] = None

    coordinator: AzanCoordinator = store["coordinator"]
    if not coordinator.data:
        return

    config = {**entry.data, **entry.options}
    offset_minutes = config.get(CONF_OFFSET_MINUTES, DEFAULT_OFFSET_MINUTES)
    now = dt_util.now()

    # Find next enabled, unplayed prayer
    next_prayer = None
    for prayer in coordinator.data.prayers:
        if not prayer["enabled"]:
            continue
        if prayer["name"] in coordinator.data.played_today:
            continue
        # Make prayer time timezone-aware for comparison
        prayer_time = prayer["time"]
        if prayer_time.tzinfo is None:
            prayer_time = prayer_time.replace(tzinfo=now.tzinfo)
        target_time = prayer_time - timedelta(minutes=offset_minutes)
        if target_time > now:
            next_prayer = prayer
            break

    if next_prayer is None:
        # No more prayers today, schedule a refresh at midnight
        tomorrow = (now + timedelta(days=1)).replace(
            hour=0, minute=1, second=0, microsecond=0
        )
        _LOGGER.debug("No more prayers today, scheduling midnight refresh")

        @callback
        def _midnight_refresh(_now):
            """Refresh prayer times at midnight."""
            hass.async_create_task(coordinator.async_refresh())
            _schedule_next_prayer(hass, entry)

        store["unsub_timer"] = async_track_point_in_time(
            hass, _midnight_refresh, tomorrow
        )
        return

    prayer_time = next_prayer["time"]
    if prayer_time.tzinfo is None:
        prayer_time = prayer_time.replace(tzinfo=now.tzinfo)
    target_time = prayer_time - timedelta(minutes=offset_minutes)
    _LOGGER.info(
        "Scheduled %s azan at %s (offset: -%dm)",
        next_prayer["name"],
        target_time.strftime("%H:%M:%S"),
        offset_minutes,
    )

    @callback
    def _prayer_callback(_now):
        """Trigger azan playback for the scheduled prayer."""
        prayer_name = next_prayer["name"]
        _LOGGER.info("Scheduler triggered: %s", prayer_name)
        hass.async_create_task(_play_azan(hass, entry, prayer_name))

    store["unsub_timer"] = async_track_point_in_time(
        hass, _prayer_callback, target_time
    )


# --- Services ---


def _register_services(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register integration services."""

    async def handle_play_azan(call: ServiceCall) -> None:
        prayer = call.data.get("prayer", "Test")
        await _play_azan(hass, entry, prayer)

    async def handle_stop_playback(call: ServiceCall) -> None:
        await _stop_playback(hass, entry)

    async def handle_refresh_times(call: ServiceCall) -> None:
        store = hass.data[DOMAIN].get(entry.entry_id)
        if store:
            coordinator: AzanCoordinator = store["coordinator"]
            await coordinator.async_refresh()
            _schedule_next_prayer(hass, entry)

    if not hass.services.has_service(DOMAIN, "play_azan"):
        hass.services.async_register(
            DOMAIN, "play_azan", handle_play_azan, schema=SERVICE_PLAY_SCHEMA
        )
    if not hass.services.has_service(DOMAIN, "stop_playback"):
        hass.services.async_register(DOMAIN, "stop_playback", handle_stop_playback)
    if not hass.services.has_service(DOMAIN, "refresh_times"):
        hass.services.async_register(DOMAIN, "refresh_times", handle_refresh_times)
