"""Config flow for Minaret integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback

from .const import (
    CALC_METHODS,
    CONF_AZAN_URL,
    CONF_CITY,
    CONF_COUNTRY,
    CONF_EXTERNAL_URL,
    CONF_FAJR_URL,
    CONF_METHOD,
    CONF_OFFSET_MINUTES,
    CONF_OUTPUT_DEVICE,
    CONF_PRAYER_ASR,
    CONF_PRAYER_DHUHR,
    CONF_PRAYER_FAJR,
    CONF_PRAYER_ISHA,
    CONF_PRAYER_MAGHRIB,
    CONF_PRAYER_SOURCE,
    CONF_PRAYER_SUNRISE,
    CONF_SUHOOR_ENABLED,
    CONF_SUHOOR_OFFSET,
    CONF_SUHOOR_RAMADAN_ONLY,
    CONF_SUHOOR_URL,
    DEFAULT_METHOD,
    DEFAULT_OFFSET_MINUTES,
    DEFAULT_SUHOOR_OFFSET,
    DEFAULT_SOURCE,
    DOMAIN,
    SOURCE_ALADHAN,
    SOURCE_QATAR_MOI,
)


def _get_output_devices(hass: HomeAssistant) -> dict[str, str]:
    """Discover all available output devices dynamically.

    Returns a dict of {device_id: friendly_label} with:
    - All media_player entities (speakers, TVs, etc.)
    - All mobile_app notify services (Android/iOS phones)
    """
    devices: dict[str, str] = {}

    # Discover media_player entities
    for state in hass.states.async_all("media_player"):
        entity_id = state.entity_id
        name = state.attributes.get("friendly_name", entity_id)
        devices[f"media_player:{entity_id}"] = f"🔊 {name}"

    # Discover mobile_app notify services
    for service_name in hass.services.async_services().get("notify", {}):
        if service_name.startswith("mobile_app_"):
            device_name = service_name.replace("mobile_app_", "").replace("_", " ").title()
            devices[f"notify:{service_name}"] = f"📱 {device_name}"

    return devices


class AzanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Azan Prayer Times."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict = {}

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Step 1: Audio settings."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_output_device()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AZAN_URL): str,
                    vol.Optional(CONF_FAJR_URL, default=""): str,
                }
            ),
        )

    async def async_step_output_device(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Step 2: Select output device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device = user_input.get(CONF_OUTPUT_DEVICE)
            if not device:
                errors["base"] = "no_device"
            else:
                self._data.update(user_input)
                # If android device, ask for external URL
                if device.startswith("notify:"):
                    return await self.async_step_android_settings()
                return await self.async_step_prayer_source()

        devices = _get_output_devices(self.hass)

        if not devices:
            # No devices found, show a text field as fallback
            return self.async_show_form(
                step_id="output_device",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_OUTPUT_DEVICE): str,
                    }
                ),
                description_placeholders={
                    "device_help": "No devices found. Enter a media_player entity ID or notify service name manually."
                },
                errors=errors,
            )

        return self.async_show_form(
            step_id="output_device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_OUTPUT_DEVICE): vol.In(devices),
                }
            ),
            errors=errors,
        )

    async def async_step_android_settings(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Step 2b: External URL for Android devices."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_prayer_source()

        return self.async_show_form(
            step_id="android_settings",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EXTERNAL_URL): str,
                }
            ),
        )

    async def async_step_prayer_source(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Step 3: Prayer times source."""
        if user_input is not None:
            self._data.update(user_input)
            if user_input[CONF_PRAYER_SOURCE] == SOURCE_ALADHAN:
                return await self.async_step_location()
            return await self.async_step_schedule()

        return self.async_show_form(
            step_id="prayer_source",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PRAYER_SOURCE, default=DEFAULT_SOURCE
                    ): vol.In(
                        {
                            SOURCE_QATAR_MOI: "Qatar MOI (portal.moi.gov.qa)",
                            SOURCE_ALADHAN: "AlAdhan API (aladhan.com)",
                        }
                    ),
                }
            ),
        )

    async def async_step_location(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Step 3b: Location settings for AlAdhan."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_schedule()

        method_options = {k: v for k, v in CALC_METHODS.items()}

        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CITY, default="Doha"): str,
                    vol.Required(CONF_COUNTRY, default="Qatar"): str,
                    vol.Required(CONF_METHOD, default=DEFAULT_METHOD): vol.In(
                        method_options
                    ),
                }
            ),
        )

    async def async_step_schedule(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Step 4: Schedule and prayer toggles."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_suhoor()

        return self.async_show_form(
            step_id="schedule",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_OFFSET_MINUTES, default=DEFAULT_OFFSET_MINUTES
                    ): vol.All(int, vol.Range(min=0, max=30)),
                    vol.Required(CONF_PRAYER_FAJR, default=True): bool,
                    vol.Required(CONF_PRAYER_SUNRISE, default=False): bool,
                    vol.Required(CONF_PRAYER_DHUHR, default=True): bool,
                    vol.Required(CONF_PRAYER_ASR, default=True): bool,
                    vol.Required(CONF_PRAYER_MAGHRIB, default=True): bool,
                    vol.Required(CONF_PRAYER_ISHA, default=True): bool,
                }
            ),
        )

    async def async_step_suhoor(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Step 5: Suhoor alarm settings."""
        if user_input is not None:
            self._data.update(user_input)
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Minaret",
                data=self._data,
            )

        return self.async_show_form(
            step_id="suhoor",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SUHOOR_ENABLED, default=False): bool,
                    vol.Required(
                        CONF_SUHOOR_OFFSET, default=DEFAULT_SUHOOR_OFFSET
                    ): vol.All(int, vol.Range(min=15, max=120)),
                    vol.Required(CONF_SUHOOR_RAMADAN_ONLY, default=True): bool,
                    vol.Optional(CONF_SUHOOR_URL, default=""): str,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return AzanOptionsFlow(config_entry)


class AzanOptionsFlow(OptionsFlow):
    """Handle options flow for Azan Prayer Times."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._data: dict = {}

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """First step of options: audio settings."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_output_device()

        current = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_AZAN_URL,
                        default=current.get(CONF_AZAN_URL, ""),
                    ): str,
                    vol.Optional(
                        CONF_FAJR_URL,
                        default=current.get(CONF_FAJR_URL, ""),
                    ): str,
                }
            ),
        )

    async def async_step_output_device(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Options step 2: Select output device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device = user_input.get(CONF_OUTPUT_DEVICE)
            if not device:
                errors["base"] = "no_device"
            else:
                self._data.update(user_input)
                if device.startswith("notify:"):
                    return await self.async_step_android_settings()
                return await self.async_step_prayer_source()

        current = {**self._config_entry.data, **self._config_entry.options}
        devices = _get_output_devices(self.hass)

        current_device = current.get(CONF_OUTPUT_DEVICE, "")

        if not devices:
            return self.async_show_form(
                step_id="output_device",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            CONF_OUTPUT_DEVICE,
                            default=current_device,
                        ): str,
                    }
                ),
                errors=errors,
            )

        # If current device is in the list, use it as default
        default = current_device if current_device in devices else None

        schema_dict: dict = {}
        if default:
            schema_dict[vol.Required(CONF_OUTPUT_DEVICE, default=default)] = vol.In(
                devices
            )
        else:
            schema_dict[vol.Required(CONF_OUTPUT_DEVICE)] = vol.In(devices)

        return self.async_show_form(
            step_id="output_device",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
        )

    async def async_step_android_settings(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Options step 2b: External URL for Android devices."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_prayer_source()

        current = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="android_settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EXTERNAL_URL,
                        default=current.get(CONF_EXTERNAL_URL, ""),
                    ): str,
                }
            ),
        )

    async def async_step_prayer_source(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Options step 3: Prayer source."""
        if user_input is not None:
            self._data.update(user_input)
            if user_input[CONF_PRAYER_SOURCE] == SOURCE_ALADHAN:
                return await self.async_step_location()
            return await self.async_step_schedule()

        current = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="prayer_source",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PRAYER_SOURCE,
                        default=current.get(CONF_PRAYER_SOURCE, DEFAULT_SOURCE),
                    ): vol.In(
                        {
                            SOURCE_QATAR_MOI: "Qatar MOI (portal.moi.gov.qa)",
                            SOURCE_ALADHAN: "AlAdhan API (aladhan.com)",
                        }
                    ),
                }
            ),
        )

    async def async_step_location(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Options step 3b: Location for AlAdhan."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_schedule()

        current = {**self._config_entry.data, **self._config_entry.options}
        method_options = {k: v for k, v in CALC_METHODS.items()}

        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CITY, default=current.get(CONF_CITY, "Doha")
                    ): str,
                    vol.Required(
                        CONF_COUNTRY, default=current.get(CONF_COUNTRY, "Qatar")
                    ): str,
                    vol.Required(
                        CONF_METHOD,
                        default=current.get(CONF_METHOD, DEFAULT_METHOD),
                    ): vol.In(method_options),
                }
            ),
        )

    async def async_step_schedule(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Options step 4: Schedule settings."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_suhoor()

        current = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="schedule",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_OFFSET_MINUTES,
                        default=current.get(
                            CONF_OFFSET_MINUTES, DEFAULT_OFFSET_MINUTES
                        ),
                    ): vol.All(int, vol.Range(min=0, max=30)),
                    vol.Required(
                        CONF_PRAYER_FAJR,
                        default=current.get(CONF_PRAYER_FAJR, True),
                    ): bool,
                    vol.Required(
                        CONF_PRAYER_SUNRISE,
                        default=current.get(CONF_PRAYER_SUNRISE, False),
                    ): bool,
                    vol.Required(
                        CONF_PRAYER_DHUHR,
                        default=current.get(CONF_PRAYER_DHUHR, True),
                    ): bool,
                    vol.Required(
                        CONF_PRAYER_ASR,
                        default=current.get(CONF_PRAYER_ASR, True),
                    ): bool,
                    vol.Required(
                        CONF_PRAYER_MAGHRIB,
                        default=current.get(CONF_PRAYER_MAGHRIB, True),
                    ): bool,
                    vol.Required(
                        CONF_PRAYER_ISHA,
                        default=current.get(CONF_PRAYER_ISHA, True),
                    ): bool,
                }
            ),
        )

    async def async_step_suhoor(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Options step 5: Suhoor alarm settings."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="", data=self._data)

        current = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="suhoor",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SUHOOR_ENABLED,
                        default=current.get(CONF_SUHOOR_ENABLED, False),
                    ): bool,
                    vol.Required(
                        CONF_SUHOOR_OFFSET,
                        default=current.get(CONF_SUHOOR_OFFSET, DEFAULT_SUHOOR_OFFSET),
                    ): vol.All(int, vol.Range(min=15, max=120)),
                    vol.Required(
                        CONF_SUHOOR_RAMADAN_ONLY,
                        default=current.get(CONF_SUHOOR_RAMADAN_ONLY, True),
                    ): bool,
                    vol.Optional(
                        CONF_SUHOOR_URL,
                        default=current.get(CONF_SUHOOR_URL, ""),
                    ): str,
                }
            ),
        )
