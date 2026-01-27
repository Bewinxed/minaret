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
    DOMAIN,
    NAME_MAP,
    PRAYER_ORDER,
    SOURCE_QATAR_MOI,
)

_LOGGER = logging.getLogger(__name__)


class PrayerData:
    """Container for prayer time data."""

    def __init__(self, prayers: list[dict], date: str) -> None:
        """Initialize prayer data."""
        self.prayers = prayers
        self.date = date
        self.played_today: set[str] = set()


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

        try:
            if source == SOURCE_QATAR_MOI:
                raw = await self._fetch_qatar_moi()
            else:
                raw = await self._fetch_aladhan()
        except Exception as err:
            raise UpdateFailed(f"Failed to fetch prayer times: {err}") from err

        today = datetime.now().strftime("%Y-%m-%d")
        prayers = self._normalize_times(raw)

        # Preserve played_today across refreshes on the same day
        data = PrayerData(prayers=prayers, date=today)
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

    async def _fetch_aladhan(self) -> dict[str, str]:
        """Fetch prayer times from AlAdhan API."""
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
        return {
            "Fajr": timings["Fajr"],
            "Sunrise": timings["Sunrise"],
            "Dhuhr": timings["Dhuhr"],
            "Asr": timings["Asr"],
            "Maghrib": timings["Maghrib"],
            "Isha": timings["Isha"],
        }

    def _normalize_times(self, raw: dict[str, str]) -> list[dict]:
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

            prayers.append(
                {
                    "name": name,
                    "time": prayer_time,
                    "time_str": f"{hour:02d}:{minute:02d}",
                    "enabled": enabled_map.get(name, False),
                }
            )

        return prayers
