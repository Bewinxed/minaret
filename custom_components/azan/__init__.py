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
    CONF_SOUND_ASR,
    CONF_SOUND_DHUHR,
    CONF_SOUND_FAJR,
    CONF_SOUND_ISHA,
    CONF_SOUND_MAGHRIB,
    CONF_SOUND_SUNRISE,
    CONF_MEDIA_PLAYER,
    CONF_NOTIFY_SERVICE,
    CONF_OFFSET_MINUTES,
    CONF_PLAYBACK_MODE,
    DEFAULT_OFFSET_MINUTES,
    DOMAIN,
    PLAYBACK_ANDROID_VLC,
    PLAYBACK_MEDIA_PLAYER,
    SOUND_OPTION_CUSTOM,
    SOUND_OPTION_FULL,
    SOUND_OPTION_SHORT,
)
from .coordinator import AzanCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

# Service schemas
SERVICE_PLAY_SCHEMA = vol.Schema(
    {
        vol.Required("prayer", default="Test"): vol.In(
            ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha", "Test"]
        ),
    }
)


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
        "full_audio_file": None,
        "short_audio_file": None,
        "fajr_audio_file": None,
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

        if azan_url:
            try:
                path = await hass.async_add_executor_job(
                    _download_audio, hass, azan_url, "azan"
                )
                store["audio_file"] = path
                _LOGGER.info("Azan audio ready: %s", path)
            except Exception:
                _LOGGER.exception("Failed to download azan audio")

        if fajr_url:
            try:
                path = await hass.async_add_executor_job(
                    _download_audio, hass, fajr_url, "fajr_azan"
                )
                store["fajr_audio_file"] = path
                _LOGGER.info("Fajr audio ready: %s", path)
            except Exception:
                _LOGGER.exception("Failed to download fajr audio")

        # Look for user-provided default files in common locations and copy
        # them into www/azan as internal full/short names. This allows users
        # to drop their MP3s into `/config/media` or `/config/www` and name
        # them as provided below.
        try:
            audio_dir = Path(hass.config.path("www", "azan"))
            # Candidate filenames the user might place
            full_names = [
                "Azhan by Mishray Alafasi.mp3",
                "Azhan by Mishray Alafasi - Full.mp3",
            ]
            short_names = [
                "Short Azhan by Mishray Alafasi.mp3",
                "Azhan (short) by Mishray Alafasi.mp3",
            ]

            integration_media = Path(__file__).parent / "media"

            def _find_and_copy(candidates, dest_name):
                for name in candidates:
                    cand_paths = [
                        # Prefer bundled integration media first
                        integration_media / name,
                        # Then check common config locations
                        Path(hass.config.path(name)),
                        Path(hass.config.path("media", name)),
                        Path(hass.config.path("www", name)),
                        Path(hass.config.path("www", "azan", name)),
                        Path(name),
                    ]
                    for p in cand_paths:
                        if p and p.exists() and p.is_file():
                            dst = audio_dir / dest_name
                            try:
                                shutil.copyfile(str(p), str(dst))
                                return str(dst)
                            except Exception:
                                _LOGGER.exception("Failed to copy default audio %s", p)
                                return None
                return None

            full_path = _find_and_copy(full_names, "azan_full.mp3")
            short_path = _find_and_copy(short_names, "azan_short.mp3")

            if full_path:
                store["full_audio_file"] = full_path
                _LOGGER.info("Found default full azan: %s", full_path)
            if short_path:
                store["short_audio_file"] = short_path
                _LOGGER.info("Found default short azan: %s", short_path)
        except Exception:
            _LOGGER.exception("Failed to copy default azan files")

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
    """Download or use local audio file (runs in executor thread).

    If `url` refers to an existing local file (absolute or relative to
    the Home Assistant config/media/www folders), copy it into
    `www/azan` as `<name>.mp3`. Otherwise fallback to downloading with
    yt-dlp as before.
    """
    audio_dir = Path(hass.config.path("www", "azan"))
    audio_dir.mkdir(parents=True, exist_ok=True)

    out_path = audio_dir / f"{name}.mp3"
    marker_path = audio_dir / f".{name}.url"

    # Check cache
    if out_path.exists() and marker_path.exists():
        existing_url = marker_path.read_text().strip()
        if existing_url == url:
            _LOGGER.debug("Audio already cached: %s", name)
            return str(out_path)
    _LOGGER.info("Preparing audio: %s -> %s", url, name)

    # Try to resolve `url` as a local file path in several likely places
    candidates: list[Path] = []
    try:
        candidates.append(Path(url))
    except Exception:
        pass
    # Relative to config dir
    candidates.append(Path(hass.config.path(url)))
    # Common HA media folders
    candidates.append(Path(hass.config.path("media", url)))
    candidates.append(Path(hass.config.path("www", url)))
    candidates.append(Path(hass.config.path("www", "azan", url)))

    local_source: Path | None = None
    for c in candidates:
        if c.exists() and c.is_file():
            local_source = c
            break

    if local_source:
        _LOGGER.info("Using local audio file: %s", local_source)
        try:
            shutil.copyfile(str(local_source), str(out_path))
        except Exception:
            _LOGGER.exception("Failed to copy local audio file: %s", local_source)
            raise
        marker_path.write_text(str(local_source))
        _LOGGER.info("Audio copied: %s", name)
        return str(out_path)

    # Fallback: download using yt-dlp
    _LOGGER.info("Downloading audio with yt-dlp: %s -> %s", url, name)
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
        "outtmpl": str(audio_dir / f"{name}.%(ext)s"),
        "noplaylist": True,
        "overwrites": True,
        "quiet": True,
        "no_warnings": True,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 13) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Mobile Safari/537.36"
            )        
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android"]
            }
        },
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # yt-dlp may output with different extension before post-processing
    # The final file should be .mp3 after FFmpegExtractAudio
    if not out_path.exists():
        # Check for file without extension change
        for f in audio_dir.iterdir():
            if f.stem == name and f.suffix != ".url" and not f.name.startswith("."):
                if f.suffix != ".mp3":
                    shutil.move(str(f), str(out_path))
                break

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

    coordinator: AzanCoordinator = store["coordinator"]

    # Guard: check if already played (prevents double-triggers from race conditions)
    # We add the prayer to `played_today` only after playback successfully starts
    # so that missing audio doesn't permanently mark a prayer as played.
    if prayer_name != "Test" and coordinator.data:
        if prayer_name in coordinator.data.played_today:
            _LOGGER.debug("Prayer %s already played, skipping duplicate", prayer_name)
            return

    config = {**entry.data, **entry.options}
    playback_mode = config.get(CONF_PLAYBACK_MODE, PLAYBACK_MEDIA_PLAYER)

    # Pick the right audio file
    # Determine per-prayer sound selection
    selection_key_map = {
        "Fajr": CONF_SOUND_FAJR,
        "Sunrise": CONF_SOUND_SUNRISE,
        "Dhuhr": CONF_SOUND_DHUHR,
        "Asr": CONF_SOUND_ASR,
        "Maghrib": CONF_SOUND_MAGHRIB,
        "Isha": CONF_SOUND_ISHA,
    }

    # When invoked as a Test, prefer the short azan
    if prayer_name == "Test":
        selection = SOUND_OPTION_SHORT
    else:
        sel_key = selection_key_map.get(prayer_name)
        selection = config.get(sel_key, SOUND_OPTION_FULL) if sel_key else SOUND_OPTION_FULL

    audio_file = None
    if selection == SOUND_OPTION_CUSTOM:
        if prayer_name == "Fajr":
            audio_file = store.get("fajr_audio_file")
        else:
            audio_file = store.get("audio_file")
    elif selection == SOUND_OPTION_FULL:
        audio_file = store.get("full_audio_file")
    elif selection == SOUND_OPTION_SHORT:
        audio_file = store.get("short_audio_file")

    # Fallbacks if chosen file not available
    if not audio_file or not os.path.exists(audio_file):
        if prayer_name == "Fajr" and store.get("fajr_audio_file"):
            audio_file = store.get("fajr_audio_file")
        else:
            audio_file = store.get("audio_file")

    if not audio_file or not os.path.exists(audio_file):
        _LOGGER.warning("No audio file available for %s", prayer_name)
        # Ensure we still schedule the next prayer even if playback failed
        _schedule_next_prayer(hass, entry)
        return

    filename = os.path.basename(audio_file)

    # Build media URL
    if playback_mode == PLAYBACK_MEDIA_PLAYER:
        # For media_player, use internal URL is fine
        try:
            base_url = get_url(hass, allow_internal=True, prefer_external=False)
        except Exception:
            base_url = get_url(hass)
    else:
        # For Android, use configured external URL
        base_url = config.get(CONF_EXTERNAL_URL, "").rstrip("/")
        if not base_url:
            try:
                base_url = get_url(hass, allow_external=True, prefer_external=True)
            except Exception:
                base_url = get_url(hass)

    media_url = f"{base_url}/local/azan/{filename}"

    # Mark as playing
    store["is_playing"] = True
    store["currently_playing"] = prayer_name

    # Trigger sensor updates for status change
    if coordinator.data:
        coordinator.async_set_updated_data(coordinator.data)

    _LOGGER.info("Playing azan for %s: %s (mode: %s)", prayer_name, media_url, playback_mode)

    try:
        if playback_mode == PLAYBACK_MEDIA_PLAYER:
            # Use media_player.play_media service on one or more entities
            media_player_config = config.get(CONF_MEDIA_PLAYER)
            if not media_player_config:
                _LOGGER.warning("No media player configured")
                return

            # `media_player_config` may be a single entity_id or a list
            targets = media_player_config if isinstance(media_player_config, (list, tuple)) else [media_player_config]

            for target in targets:
                await hass.services.async_call(
                    "media_player",
                    "play_media",
                    {
                        "entity_id": target,
                        "media_content_id": media_url,
                        "media_content_type": "music",
                    },
                )
        else:
            # Android VLC mode
            notify_service = config.get(CONF_NOTIFY_SERVICE)
            if not notify_service:
                _LOGGER.warning("No notify service configured")
                return

            # Wake screen first
            await hass.services.async_call(
                "notify",
                notify_service,
                {
                    "message": "command_screen_on",
                    "data": {"ttl": 0, "priority": "high"},
                },
            )

            # Launch VLC with the audio URL
            await hass.services.async_call(
                "notify",
                notify_service,
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
        _LOGGER.exception("Failed to play azan")
        store["is_playing"] = False
        store["currently_playing"] = None
        # Mark that prayer was not successfully played and reschedule next
        if coordinator.data:
            coordinator.async_set_updated_data(coordinator.data)
        _schedule_next_prayer(hass, entry)
        return

    # Mark prayer as played (avoid marking Test)
    if prayer_name != "Test" and coordinator.data:
        coordinator.data.played_today.add(prayer_name)
        coordinator.async_set_updated_data(coordinator.data)

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
    playback_mode = config.get(CONF_PLAYBACK_MODE, PLAYBACK_ANDROID_VLC)

    try:
        if playback_mode == PLAYBACK_MEDIA_PLAYER:
            # Use media_player.media_stop service for one or more entities
            media_player_config = config.get(CONF_MEDIA_PLAYER)
            if media_player_config:
                targets = media_player_config if isinstance(media_player_config, (list, tuple)) else [media_player_config]
                for target in targets:
                    await hass.services.async_call(
                        "media_player",
                        "media_stop",
                        {"entity_id": target},
                    )
                    _LOGGER.info("Stopped azan playback on %s", target)
        else:
            # Android VLC mode
            notify_service = config.get(CONF_NOTIFY_SERVICE)
            if notify_service:
                await hass.services.async_call(
                    "notify",
                    notify_service,
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
                _LOGGER.info("Stopped azan playback via VLC")
    except Exception:
        _LOGGER.exception("Failed to stop playback")

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
    now = dt_util.now()

    # Find next enabled, unplayed prayer
    next_prayer = None
    _LOGGER.debug("Played today set: %s", getattr(coordinator.data, "played_today", set()))
    for prayer in coordinator.data.prayers:
        if not prayer["enabled"]:
            continue
        if prayer["name"] in coordinator.data.played_today:
            _LOGGER.debug("Skipping %s because it's in played_today", prayer["name"])
            continue
        _LOGGER.debug("Considering prayer %s at %s", prayer["name"], prayer["time"])
        # Make prayer time timezone-aware for comparison
        prayer_time = prayer["time"]
        if prayer_time.tzinfo is None:
            prayer_time = prayer_time.replace(tzinfo=now.tzinfo)
        # Offset only applies to Sunrise; other prayers use zero offset
        if prayer["name"] == "Sunrise":
            this_offset = config.get(CONF_OFFSET_MINUTES, DEFAULT_OFFSET_MINUTES)
        else:
            this_offset = 0
        target_time = prayer_time - timedelta(minutes=this_offset)
        if target_time > now:
            next_prayer = prayer
            break

    if next_prayer is None:
        # No more prayers today, schedule a refresh at midnight
        _LOGGER.debug("No next prayer found; played_today=%s", coordinator.data.played_today)
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
    # Determine offset for the selected prayer (Sunrise only)
    if next_prayer["name"] == "Sunrise":
        offset_minutes = config.get(CONF_OFFSET_MINUTES, DEFAULT_OFFSET_MINUTES)
    else:
        offset_minutes = 0

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
        # Guard: check if already played (prevents double-triggers)
        if coordinator.data and prayer_name in coordinator.data.played_today:
            _LOGGER.debug("Prayer %s already played, skipping", prayer_name)
            _schedule_next_prayer(hass, entry)
            return
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
