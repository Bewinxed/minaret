"""Sensor platform for Minaret."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, PRAYER_ICONS, PRAYER_ORDER
from .coordinator import AzanCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azan sensors from a config entry."""
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator: AzanCoordinator = store["coordinator"]

    entities: list[SensorEntity] = []

    # Individual prayer time sensors
    for prayer_name in PRAYER_ORDER:
        entities.append(PrayerTimeSensor(coordinator, entry, prayer_name))

    # Next prayer sensor
    entities.append(NextPrayerSensor(coordinator, entry))

    # Countdown sensor (updates every minute)
    entities.append(AzanCountdownSensor(coordinator, entry))

    # Hijri date sensor
    entities.append(HijriDateSensor(coordinator, entry))

    # Status sensor
    entities.append(AzanStatusSensor(coordinator, entry))

    async_add_entities(entities)


class AzanBaseSensor(CoordinatorEntity[AzanCoordinator], SensorEntity):
    """Base class for Azan sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AzanCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name="Minaret",
            manufacturer="Minaret",
            model="Prayer Times",
            entry_type=DeviceEntryType.SERVICE,
        )


class PrayerTimeSensor(AzanBaseSensor):
    """Sensor for individual prayer times."""

    def __init__(
        self,
        coordinator: AzanCoordinator,
        entry: ConfigEntry,
        prayer_name: str,
    ) -> None:
        """Initialize the prayer time sensor."""
        super().__init__(coordinator, entry)
        self._prayer_name = prayer_name
        self._attr_unique_id = f"{entry.entry_id}_{prayer_name.lower()}"
        self._attr_translation_key = prayer_name.lower()
        self._attr_icon = PRAYER_ICONS.get(prayer_name, "mdi:mosque")

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._prayer_name

    @property
    def native_value(self) -> str | None:
        """Return the prayer time as HH:MM string."""
        prayer = self._get_prayer()
        if prayer:
            return prayer["time_str"]
        return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        prayer = self._get_prayer()
        if not prayer:
            return {}

        played = False
        if self.coordinator.data:
            played = self._prayer_name in self.coordinator.data.played_today

        return {
            "enabled": prayer["enabled"],
            "played": played,
            "datetime": prayer["time"].isoformat(),
            "prayer_name": self._prayer_name,
        }

    def _get_prayer(self) -> dict | None:
        """Get the prayer data for this sensor."""
        if not self.coordinator.data:
            return None
        for prayer in self.coordinator.data.prayers:
            if prayer["name"] == self._prayer_name:
                return prayer
        return None


class NextPrayerSensor(AzanBaseSensor):
    """Sensor showing the next upcoming prayer."""

    def __init__(
        self,
        coordinator: AzanCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the next prayer sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_next_prayer"
        self._attr_icon = "mdi:mosque"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Next Prayer"

    @property
    def native_value(self) -> str | None:
        """Return the name of the next prayer."""
        prayer = self._get_next_prayer()
        if prayer:
            return prayer["name"]
        return None

    @property
    def icon(self) -> str:
        """Return dynamic icon based on next prayer."""
        prayer = self._get_next_prayer()
        if prayer:
            return PRAYER_ICONS.get(prayer["name"], "mdi:mosque")
        return "mdi:mosque"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        prayer = self._get_next_prayer()
        if not prayer:
            return {}

        now = datetime.now()
        diff = prayer["time"] - now
        minutes_until = max(0, int(diff.total_seconds() / 60))

        return {
            "time": prayer["time_str"],
            "countdown_minutes": minutes_until,
            "datetime": prayer["time"].isoformat(),
        }

    def _get_next_prayer(self) -> dict | None:
        """Find the next upcoming enabled prayer."""
        if not self.coordinator.data:
            return None

        now = datetime.now()
        for prayer in self.coordinator.data.prayers:
            if prayer["enabled"] and prayer["time"] > now:
                return prayer
        return None


class AzanCountdownSensor(AzanBaseSensor):
    """Sensor showing countdown to next prayer, updating every minute."""

    def __init__(
        self,
        coordinator: AzanCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the countdown sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_countdown"
        self._attr_icon = "mdi:timer-sand"
        self._attr_native_unit_of_measurement = "min"
        self._unsub_timer = None

    @property
    def name(self) -> str:
        """Return the name."""
        return "Countdown"

    async def async_added_to_hass(self) -> None:
        """Start the per-minute timer when added."""
        await super().async_added_to_hass()
        self._unsub_timer = async_track_time_interval(
            self.hass, self._update_countdown, timedelta(minutes=1)
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel the timer when removed."""
        if self._unsub_timer:
            self._unsub_timer()

    @callback
    def _update_countdown(self, _now) -> None:
        """Force a state write every minute."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        """Return minutes until next prayer."""
        prayer = self._get_next_prayer()
        if not prayer:
            return None
        diff = prayer["time"] - datetime.now()
        return max(0, int(diff.total_seconds() / 60))

    @property
    def extra_state_attributes(self) -> dict:
        """Return countdown breakdown."""
        prayer = self._get_next_prayer()
        if not prayer:
            return {"prayer_name": None, "time": None, "hours": 0, "minutes": 0, "seconds": 0}

        diff = prayer["time"] - datetime.now()
        total_seconds = max(0, int(diff.total_seconds()))
        return {
            "prayer_name": prayer["name"],
            "time": prayer["time_str"],
            "hours": total_seconds // 3600,
            "minutes": (total_seconds % 3600) // 60,
            "seconds": total_seconds % 60,
            "datetime": prayer["time"].isoformat(),
        }

    def _get_next_prayer(self) -> dict | None:
        """Find the next upcoming prayer (enabled or not, for countdown)."""
        if not self.coordinator.data:
            return None
        now = datetime.now()
        for prayer in self.coordinator.data.prayers:
            if prayer["time"] > now:
                return prayer
        return None


class HijriDateSensor(AzanBaseSensor):
    """Sensor showing the current Hijri date."""

    def __init__(
        self,
        coordinator: AzanCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the Hijri date sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_hijri_date"
        self._attr_icon = "mdi:calendar-star"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Hijri Date"

    @property
    def native_value(self) -> str | None:
        """Return the Hijri date string."""
        try:
            from hijri_converter import Gregorian

            hijri = Gregorian.today().to_hijri()
            return f"{hijri.day} {hijri.month_name()} {hijri.year} AH"
        except Exception:
            return None

    @property
    def extra_state_attributes(self) -> dict:
        """Return Hijri date components."""
        try:
            from hijri_converter import Gregorian

            hijri = Gregorian.today().to_hijri()
            return {
                "day": hijri.day,
                "month": hijri.month,
                "month_name": hijri.month_name(),
                "year": hijri.year,
            }
        except Exception:
            return {}


class AzanStatusSensor(AzanBaseSensor):
    """Sensor showing the current azan service status."""

    def __init__(
        self,
        coordinator: AzanCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the status sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_icon = "mdi:bell-ring"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Status"

    @property
    def native_value(self) -> str:
        """Return current status."""
        store = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})

        if store.get("is_downloading"):
            return "downloading"
        if store.get("is_playing"):
            return "playing"
        return "idle"

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        store = self.hass.data.get(DOMAIN, {}).get(self._entry.entry_id, {})
        attrs = {}

        currently_playing = store.get("currently_playing")
        if currently_playing:
            attrs["currently_playing"] = currently_playing

        audio_ready = store.get("audio_file") is not None
        attrs["audio_ready"] = audio_ready

        return attrs
