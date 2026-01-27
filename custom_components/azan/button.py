"""Button platform for Minaret."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Azan buttons from a config entry."""
    async_add_entities(
        [
            AzanTestPlayButton(entry),
            AzanRefreshButton(entry),
        ]
    )


class AzanBaseButton(ButtonEntity):
    """Base class for Azan buttons."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the button."""
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


class AzanTestPlayButton(AzanBaseButton):
    """Button to test azan playback."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the test play button."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_test_play"
        self._attr_icon = "mdi:play-circle"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Test Play"

    async def async_press(self) -> None:
        """Handle button press."""
        await self.hass.services.async_call(
            DOMAIN,
            "play_azan",
            {"prayer": "Test"},
        )


class AzanRefreshButton(AzanBaseButton):
    """Button to refresh prayer times."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the refresh button."""
        super().__init__(entry)
        self._attr_unique_id = f"{entry.entry_id}_refresh_times"
        self._attr_icon = "mdi:refresh"

    @property
    def name(self) -> str:
        """Return the name."""
        return "Refresh Times"

    async def async_press(self) -> None:
        """Handle button press."""
        await self.hass.services.async_call(
            DOMAIN,
            "refresh_times",
            {},
        )
