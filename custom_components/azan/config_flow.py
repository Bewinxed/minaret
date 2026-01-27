"""Config flow for Minaret integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from .const import (
    CALC_METHODS,
    CONF_AZAN_URL,
    CONF_CITY,
    CONF_COUNTRY,
    CONF_EXTERNAL_URL,
    CONF_FAJR_URL,
    CONF_METHOD,
    CONF_NOTIFY_SERVICE,
    CONF_OFFSET_MINUTES,
    CONF_PRAYER_ASR,
    CONF_PRAYER_DHUHR,
    CONF_PRAYER_FAJR,
    CONF_PRAYER_ISHA,
    CONF_PRAYER_MAGHRIB,
    CONF_PRAYER_SOURCE,
    CONF_PRAYER_SUNRISE,
    DEFAULT_METHOD,
    DEFAULT_OFFSET_MINUTES,
    DEFAULT_SOURCE,
    DOMAIN,
    SOURCE_ALADHAN,
    SOURCE_QATAR_MOI,
)


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
            return await self.async_step_prayer_source()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AZAN_URL): str,
                    vol.Optional(CONF_FAJR_URL, default=""): str,
                }
            ),
            description_placeholders={
                "azan_url_desc": "YouTube or direct URL for the azan audio",
                "fajr_url_desc": "Optional separate audio for Fajr prayer",
            },
        )

    async def async_step_prayer_source(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Step 2: Prayer times source."""
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
        """Step 2b: Location settings for AlAdhan."""
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
        """Step 3: Schedule and notification settings."""
        if user_input is not None:
            self._data.update(user_input)
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Minaret",
                data=self._data,
            )

        return self.async_show_form(
            step_id="schedule",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EXTERNAL_URL): str,
                    vol.Required(CONF_NOTIFY_SERVICE): str,
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
            return await self.async_step_prayer_source()

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

    async def async_step_prayer_source(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Options step 2: Prayer source."""
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
        """Options step 2b: Location for AlAdhan."""
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
        """Options step 3: Schedule settings."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="", data=self._data)

        current = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="schedule",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_EXTERNAL_URL,
                        default=current.get(CONF_EXTERNAL_URL, ""),
                    ): str,
                    vol.Required(
                        CONF_NOTIFY_SERVICE,
                        default=current.get(CONF_NOTIFY_SERVICE, ""),
                    ): str,
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
