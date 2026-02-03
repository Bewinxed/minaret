"""Config flow for Minaret integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback

from homeassistant.helpers import selector

from .const import (
    CALC_METHODS,
    CONF_AZAN_URL,
    CONF_CITY,
    CONF_COUNTRY,
    CONF_EXTERNAL_URL,
    CONF_FAJR_URL,
    CONF_MEDIA_PLAYER,
    CONF_METHOD,
    CONF_NOTIFY_SERVICE,
    CONF_OFFSET_MINUTES,
    CONF_PLAYBACK_MODE,
    CONF_SOUND_ASR,
    CONF_SOUND_DHUHR,
    CONF_SOUND_FAJR,
    CONF_SOUND_ISHA,
    CONF_SOUND_MAGHRIB,
    CONF_SOUND_SUNRISE,
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
    PLAYBACK_ANDROID_VLC,
    PLAYBACK_MEDIA_PLAYER,
    SOURCE_ALADHAN,
    SOURCE_QATAR_MOI,
    SOUND_OPTION_CUSTOM,
    SOUND_OPTION_FULL,
    SOUND_OPTION_SHORT,
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
            return await self.async_step_playback_mode()
        # Allow selecting one of two built-in defaults or provide custom URLs/paths.
        # Also allow per-prayer selection of which sound to use (full/short/custom).
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SOUND_FAJR, default=SOUND_OPTION_FULL): vol.In(
                        {SOUND_OPTION_FULL: "Full", SOUND_OPTION_SHORT: "Short", SOUND_OPTION_CUSTOM: "Custom (use Fajr URL)"}
                    ),
                    vol.Required(CONF_SOUND_SUNRISE, default=SOUND_OPTION_FULL): vol.In(
                        {SOUND_OPTION_FULL: "Full", SOUND_OPTION_SHORT: "Short", SOUND_OPTION_CUSTOM: "Custom (use Azan URL)"}
                    ),
                    vol.Required(CONF_SOUND_DHUHR, default=SOUND_OPTION_FULL): vol.In(
                        {SOUND_OPTION_FULL: "Full", SOUND_OPTION_SHORT: "Short", SOUND_OPTION_CUSTOM: "Custom (use Azan URL)"}
                    ),
                    vol.Required(CONF_SOUND_ASR, default=SOUND_OPTION_FULL): vol.In(
                        {SOUND_OPTION_FULL: "Full", SOUND_OPTION_SHORT: "Short", SOUND_OPTION_CUSTOM: "Custom (use Azan URL)"}
                    ),
                    vol.Required(CONF_SOUND_MAGHRIB, default=SOUND_OPTION_FULL): vol.In(
                        {SOUND_OPTION_FULL: "Full", SOUND_OPTION_SHORT: "Short", SOUND_OPTION_CUSTOM: "Custom (use Azan URL)"}
                    ),
                    vol.Required(CONF_SOUND_ISHA, default=SOUND_OPTION_FULL): vol.In(
                        {SOUND_OPTION_FULL: "Full", SOUND_OPTION_SHORT: "Short", SOUND_OPTION_CUSTOM: "Custom (use Azan URL)"}
                    ),
                    vol.Optional(CONF_AZAN_URL, default=""): str,
                    vol.Optional(CONF_FAJR_URL, default=""): str,
                }
            ),
            description_placeholders={
                "azan_url_desc": (
                    "Choose the default built-in azan or provide a custom URL/local MP3 path (e.g. media/adhan.mp3)."
                ),
                "fajr_url_desc": (
                    "Optional separate audio for Fajr (URL or local path, e.g. media/fajr_adhan.mp3)."
                ),
            },
        )

    async def async_step_playback_mode(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Step 2: Playback mode selection."""
        if user_input is not None:
            self._data.update(user_input)
            if user_input[CONF_PLAYBACK_MODE] == PLAYBACK_MEDIA_PLAYER:
                return await self.async_step_media_player()
            return await self.async_step_android_vlc()

        return self.async_show_form(
            step_id="playback_mode",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PLAYBACK_MODE, default=PLAYBACK_MEDIA_PLAYER
                    ): vol.In(
                        {
                            PLAYBACK_ANDROID_VLC: "Android Phone (via VLC)",
                            PLAYBACK_MEDIA_PLAYER: "Smart Speaker / Media Player",
                        }
                    ),
                }
            ),
        )

    async def async_step_media_player(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Step 3a: Media player selection for smart speakers."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_prayer_source()

        return self.async_show_form(
            step_id="media_player",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MEDIA_PLAYER): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="media_player")
                    ),
                }
            ),
        )

    async def async_step_android_vlc(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Step 3b: Android VLC settings (notify service + external URL)."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_prayer_source()

        return self.async_show_form(
            step_id="android_vlc",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EXTERNAL_URL): str,
                    vol.Required(CONF_NOTIFY_SERVICE): str,
                }
            ),
        )

    async def async_step_prayer_source(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Step 4: Prayer times source."""
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
        """Step 5: Location settings for AlAdhan."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_schedule()

        method_options = {k: v for k, v in CALC_METHODS.items()}

        return self.async_show_form(
            step_id="location",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CITY, default="Los Angeles"): str,
                    vol.Required(CONF_COUNTRY, default="United States"): str,
                    vol.Required(CONF_METHOD, default=DEFAULT_METHOD): vol.In(
                        method_options
                    ),
                }
            ),
        )

    async def async_step_schedule(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Step 6: Schedule settings (offset and prayer toggles)."""
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
                    vol.Required(
                        CONF_OFFSET_MINUTES, default=DEFAULT_OFFSET_MINUTES
                    ): vol.All(int, vol.Range(min=0, max=45)),
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
            return await self.async_step_playback_mode()

        current = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SOUND_FAJR, default=current.get(CONF_SOUND_FAJR, SOUND_OPTION_FULL)
                    ): vol.In(
                        {SOUND_OPTION_FULL: "Full", SOUND_OPTION_SHORT: "Short", SOUND_OPTION_CUSTOM: "Custom (Use Fajr URL)"}
                    ),
                    vol.Required(
                        CONF_SOUND_SUNRISE, default=current.get(CONF_SOUND_SUNRISE, SOUND_OPTION_FULL)
                    ): vol.In(
                        {SOUND_OPTION_FULL: "Full", SOUND_OPTION_SHORT: "Short", SOUND_OPTION_CUSTOM: "Custom (use Azan URL)"}
                    ),
                    vol.Required(
                        CONF_SOUND_DHUHR, default=current.get(CONF_SOUND_DHUHR, SOUND_OPTION_FULL)
                    ): vol.In(
                        {SOUND_OPTION_FULL: "Full", SOUND_OPTION_SHORT: "Short", SOUND_OPTION_CUSTOM: "Custom (use Azan URL)"}
                    ),
                    vol.Required(
                        CONF_SOUND_ASR, default=current.get(CONF_SOUND_ASR, SOUND_OPTION_FULL)
                    ): vol.In(
                        {SOUND_OPTION_FULL: "Full", SOUND_OPTION_SHORT: "Short", SOUND_OPTION_CUSTOM: "Custom (use Azan URL)"}
                    ),
                    vol.Required(
                        CONF_SOUND_MAGHRIB, default=current.get(CONF_SOUND_MAGHRIB, SOUND_OPTION_FULL)
                    ): vol.In(
                        {SOUND_OPTION_FULL: "Full", SOUND_OPTION_SHORT: "Short", SOUND_OPTION_CUSTOM: "Custom (use Azan URL)"}
                    ),
                    vol.Required(
                        CONF_SOUND_ISHA, default=current.get(CONF_SOUND_ISHA, SOUND_OPTION_FULL)
                    ): vol.In(
                        {SOUND_OPTION_FULL: "Full", SOUND_OPTION_SHORT: "Short", SOUND_OPTION_CUSTOM: "Custom (use Azan URL)"}
                    ),
                    vol.Optional(
                        CONF_AZAN_URL,
                        default=current.get(CONF_AZAN_URL, ""),
                    ): str,
                    vol.Optional(
                        CONF_FAJR_URL,
                        default=current.get(CONF_FAJR_URL, ""),
                    ): str,
                }
            ),
            description_placeholders={
                "azan_url_desc": (
                    "Choose the default built-in azan or provide a custom URL/local MP3 path (e.g. media/adhan.mp3)."
                ),
                "fajr_url_desc": (
                    "Optional separate audio for Fajr (URL or local path, e.g. media/fajr_adhan.mp3)."
                ),
            },
        )

    async def async_step_playback_mode(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Options step: Playback mode selection."""
        if user_input is not None:
            self._data.update(user_input)
            if user_input[CONF_PLAYBACK_MODE] == PLAYBACK_MEDIA_PLAYER:
                return await self.async_step_media_player()
            return await self.async_step_android_vlc()

        current = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="playback_mode",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PLAYBACK_MODE,
                        default=current.get(CONF_PLAYBACK_MODE, PLAYBACK_MEDIA_PLAYER),
                    ): vol.In(
                        {
                            PLAYBACK_ANDROID_VLC: "Android Phone (via VLC)",
                            PLAYBACK_MEDIA_PLAYER: "Smart Speaker / Media Player",
                        }
                    ),
                }
            ),
        )

    async def async_step_media_player(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Options step: Media player selection for smart speakers."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_prayer_source()

        current = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="media_player",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_MEDIA_PLAYER,
                        default=current.get(CONF_MEDIA_PLAYER, ""),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="media_player")
                    ),
                }
            ),
        )

    async def async_step_android_vlc(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Options step: Android VLC settings."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_prayer_source()

        current = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="android_vlc",
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
                }
            ),
        )

    async def async_step_prayer_source(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        """Options step: Prayer source."""
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
        """Options step: Location for AlAdhan."""
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
                        CONF_CITY, default=current.get(CONF_CITY, "Los Angeles")
                    ): str,
                    vol.Required(
                        CONF_COUNTRY, default=current.get(CONF_COUNTRY, "United States")
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
        """Options step: Schedule settings."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(title="", data=self._data)

        current = {**self._config_entry.data, **self._config_entry.options}

        return self.async_show_form(
            step_id="schedule",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_PRAYER_FAJR,
                        default=current.get(CONF_PRAYER_FAJR, True),
                    ): bool,
                    vol.Required(
                        CONF_PRAYER_SUNRISE,
                        default=current.get(CONF_PRAYER_SUNRISE, False),
                    ): bool,
                    vol.Required(
                        CONF_OFFSET_MINUTES,
                        default=current.get(
                            CONF_OFFSET_MINUTES, DEFAULT_OFFSET_MINUTES
                        ),
                    ): vol.All(int, vol.Range(min=0, max=45)),
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
