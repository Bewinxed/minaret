"""DataUpdateCoordinator for Minaret."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CITY,
    CONF_COUNTRY,
    CONF_METHOD,
    CONF_PRAYER_SOURCE,
    CONF_SUHOOR_ENABLED,
    CONF_SUHOOR_OFFSET,
    CONF_SUHOOR_RAMADAN_ONLY,
    DEFAULT_SUHOOR_OFFSET,
    DOMAIN,
    NAME_MAP,
    PRAYER_ORDER,
    SOURCE_QATAR_MOI,
)

_LOGGER = logging.getLogger(__name__)


class PrayerData:
    """Container for prayer time data."""

    def __init__(
        self,
        prayers: list[dict],
        date: str,
        hijri_month: int | None = None,
        hijri_day: int | None = None,
        hijri_month_name: str | None = None,
    ) -> None:
        """Initialize prayer data."""
        self.prayers = prayers
        self.date = date
        self.played_today: set[str] = set()
        self.hijri_month = hijri_month
        self.hijri_day = hijri_day
        self.hijri_month_name = hijri_month_name
        self.is_ramadan = (hijri_month == 9) if hijri_month else False


class AzanCoordinator(DataUpdateCoordinator[PrayerData]):
    """Coordinator to fetch and manage prayer times."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=6),
        )
        self.config = config
        self._last_date: str | None = None

    def get_config_value(self, key: str, default=None):
        """Get a config value, checking options first then data."""
        if hasattr(self, "config_entry") and self.config_entry is not None:
            options = self.config_entry.options
            data = self.config_entry.data
            return options.get(key, data.get(key, default))
        return self.config.get(key, default)

    async def _async_update_data(self) -> PrayerData:
        """Fetch prayer times from the configured source."""
        source = self.config.get(CONF_PRAYER_SOURCE, SOURCE_QATAR_MOI)

        hijri_month = None
        hijri_day = None
        hijri_month_name = None

        try:
            if source == SOURCE_QATAR_MOI:
                raw = await self._fetch_qatar_moi()
                # Use hijri-converter for Hijri date
                try:
                    from hijri_converter import Gregorian

                    hijri = Gregorian.today().to_hijri()
                    hijri_month = hijri.month
                    hijri_day = hijri.day
                    hijri_month_name = hijri.month_name()
                except Exception:
                    _LOGGER.debug("Could not determine Hijri date")
            else:
                raw, hijri_info = await self._fetch_aladhan()
                hijri_month = hijri_info.get("month")
                hijri_day = hijri_info.get("day")
                hijri_month_name = hijri_info.get("month_name")
        except Exception as err:
            raise UpdateFailed(f"Failed to fetch prayer times: {err}") from err

        today = datetime.now().strftime("%Y-%m-%d")
        is_ramadan = (hijri_month == 9) if hijri_month else False
        prayers = self._normalize_times(raw, is_ramadan)

        # Preserve played_today across refreshes on the same day
        data = PrayerData(
            prayers=prayers,
            date=today,
            hijri_month=hijri_month,
            hijri_day=hijri_day,
            hijri_month_name=hijri_month_name,
        )
        if self.data and self.data.date == today:
            data.played_today = self.data.played_today

        self._last_date = today
        _LOGGER.info("Prayer times refreshed for %s", today)
        for p in prayers:
            _LOGGER.debug(
                "  %s: %s (enabled=%s)", p["name"], p["time_str"], p["enabled"]
            )

        return data

    async def _fetch_qatar_moi(self) -> dict[str, str]:
        """Fetch prayer times from Qatar MOI portal."""
        url = "https://portal.moi.gov.qa/MoiPortalRestServices/rest/prayertimings/today/en"

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers={"User-Agent": "Mozilla/5.0"}
            ) as resp:
                resp.raise_for_status()
                html = await resp.text()

        # Parse table headers and cells
        headers = [
            re.sub(r"<[^>]+>", "", m).strip()
            for m in re.findall(r"<th[^>]*>(.*?)</th>", html, re.DOTALL)
            if re.sub(r"<[^>]+>", "", m).strip()
        ]
        cells = [
            m.strip()
            for m in re.findall(r"<td[^>]*>(.*?)</td>", html, re.DOTALL)
        ]

        times: dict[str, str] = {}
        for i, header in enumerate(headers):
            if i < len(cells):
                key = NAME_MAP.get(header.lower(), header)
                times[key] = cells[i]

        if not times:
            raise UpdateFailed("Qatar MOI returned no prayer times")

        return times

    async def _fetch_aladhan(self) -> tuple[dict[str, str], dict]:
        """Fetch prayer times and Hijri date from AlAdhan API."""
        city = self.config.get(CONF_CITY, "Doha")
        country = self.config.get(CONF_COUNTRY, "Qatar")
        method = self.config.get(CONF_METHOD, 10)

        url = (
            f"https://api.aladhan.com/v1/timingsByCity"
            f"?city={city}&country={country}&method={method}"
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, headers={"User-Agent": "Mozilla/5.0"}
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()

        timings = data["data"]["timings"]

        # Extract Hijri date from API response
        hijri_info: dict = {}
        try:
            hijri_data = data["data"]["date"]["hijri"]
            hijri_info["month"] = int(hijri_data["month"]["number"])
            hijri_info["day"] = int(hijri_data["day"])
            hijri_info["month_name"] = hijri_data["month"]["en"]
        except (KeyError, ValueError, TypeError):
            _LOGGER.debug("Could not parse Hijri date from AlAdhan response")

        times = {
            "Fajr": timings["Fajr"],
            "Sunrise": timings["Sunrise"],
            "Dhuhr": timings["Dhuhr"],
            "Asr": timings["Asr"],
            "Maghrib": timings["Maghrib"],
            "Isha": timings["Isha"],
        }
        return times, hijri_info

    def _normalize_times(self, raw: dict[str, str], is_ramadan: bool = False) -> list[dict]:
        """Convert raw time strings to structured prayer info dicts."""
        now = datetime.now()
        config = self.config

        # Build enabled map from prayer toggle config keys
        enabled_map = {
            "Fajr": config.get("prayer_fajr", True),
            "Sunrise": config.get("prayer_sunrise", False),
            "Dhuhr": config.get("prayer_dhuhr", True),
            "Asr": config.get("prayer_asr", True),
            "Maghrib": config.get("prayer_maghrib", True),
            "Isha": config.get("prayer_isha", True),
        }

        # Sort entries by prayer order
        entries = sorted(
            raw.items(),
            key=lambda x: (
                PRAYER_ORDER.index(x[0]) if x[0] in PRAYER_ORDER else 99
            ),
        )

        prayers = []
        fajr_time = None
        for name, time_str in entries:
            if name not in PRAYER_ORDER:
                continue

            # Parse HH:MM (handles both "HH:MM" and "HH:MM (timezone)" formats)
            time_clean = time_str.strip().split(" ")[0].split("(")[0].strip()
            parts = time_clean.split(":")
            if len(parts) < 2:
                continue

            hour = int(parts[0])
            minute = int(parts[1])

            # Qatar MOI uses 12h format: afternoon prayers need +12
            if name in ("Asr", "Maghrib", "Isha") and hour < 10:
                hour += 12

            prayer_time = now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )

            if name == "Fajr":
                fajr_time = prayer_time

            prayers.append(
                {
                    "name": name,
                    "time": prayer_time,
                    "time_str": f"{hour:02d}:{minute:02d}",
                    "enabled": enabled_map.get(name, False),
                }
            )

        # Inject Suhoor before Fajr if enabled
        suhoor_enabled = config.get(CONF_SUHOOR_ENABLED, False)
        if suhoor_enabled and fajr_time:
            ramadan_only = config.get(CONF_SUHOOR_RAMADAN_ONLY, True)
            if not ramadan_only or is_ramadan:
                offset = config.get(CONF_SUHOOR_OFFSET, DEFAULT_SUHOOR_OFFSET)
                suhoor_time = fajr_time - timedelta(minutes=offset)
                suhoor_entry = {
                    "name": "Suhoor",
                    "time": suhoor_time,
                    "time_str": f"{suhoor_time.hour:02d}:{suhoor_time.minute:02d}",
                    "enabled": True,
                }
                # Insert before Fajr
                fajr_idx = next(
                    (i for i, p in enumerate(prayers) if p["name"] == "Fajr"), 0
                )
                prayers.insert(fajr_idx, suhoor_entry)
                _LOGGER.debug(
                    "Suhoor alarm at %s (%d min before Fajr)",
                    suhoor_entry["time_str"],
                    offset,
                )

        return prayers
