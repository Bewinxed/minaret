"""Constants for the Minaret integration."""

DOMAIN = "azan"

# Config keys
CONF_AZAN_URL = "azan_url"
CONF_FAJR_URL = "fajr_azan_url"
CONF_PRAYER_SOURCE = "prayer_source"
CONF_OUTPUT_DEVICE = "output_device"
CONF_EXTERNAL_URL = "external_url"
CONF_CITY = "city"
CONF_COUNTRY = "country"
CONF_METHOD = "method"
CONF_OFFSET_MINUTES = "offset_minutes"

# Suhoor config keys
CONF_SUHOOR_ENABLED = "suhoor_enabled"
CONF_SUHOOR_OFFSET = "suhoor_offset_minutes"
CONF_SUHOOR_URL = "suhoor_url"
CONF_SUHOOR_RAMADAN_ONLY = "suhoor_ramadan_only"

# Legacy config keys (for migration)
CONF_PLAYBACK_MODE = "playback_mode"
CONF_MEDIA_PLAYER = "media_player"
CONF_NOTIFY_SERVICE = "notify_service"

# Prayer toggle config keys
CONF_PRAYER_FAJR = "prayer_fajr"
CONF_PRAYER_SUNRISE = "prayer_sunrise"
CONF_PRAYER_DHUHR = "prayer_dhuhr"
CONF_PRAYER_ASR = "prayer_asr"
CONF_PRAYER_MAGHRIB = "prayer_maghrib"
CONF_PRAYER_ISHA = "prayer_isha"

PRAYER_TOGGLES = [
    CONF_PRAYER_FAJR,
    CONF_PRAYER_SUNRISE,
    CONF_PRAYER_DHUHR,
    CONF_PRAYER_ASR,
    CONF_PRAYER_MAGHRIB,
    CONF_PRAYER_ISHA,
]

# Prayer sources
SOURCE_QATAR_MOI = "qatar_moi"
SOURCE_ALADHAN = "aladhan"

# Ordered list of prayers
PRAYER_ORDER = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"]

PRAYER_ICONS = {
    "Fajr": "mdi:weather-sunset-up",
    "Sunrise": "mdi:weather-sunny",
    "Dhuhr": "mdi:mosque",
    "Asr": "mdi:weather-partly-cloudy",
    "Maghrib": "mdi:weather-sunset-down",
    "Isha": "mdi:weather-night",
    "Suhoor": "mdi:silverware-fork-knife",
}

# Qatar MOI name normalization
NAME_MAP = {
    "fajer": "Fajr",
    "fajr": "Fajr",
    "sunrise": "Sunrise",
    "dhuhr": "Dhuhr",
    "zuhr": "Dhuhr",
    "asr": "Asr",
    "maghrib": "Maghrib",
    "isha": "Isha",
}

# AlAdhan calculation methods
CALC_METHODS = {
    0: "Shia Ithna-Ashari",
    1: "University of Islamic Sciences, Karachi",
    2: "Islamic Society of North America",
    3: "Muslim World League",
    4: "Umm Al-Qura University, Makkah",
    5: "Egyptian General Authority of Survey",
    7: "Institute of Geophysics, University of Tehran",
    8: "Gulf Region",
    9: "Kuwait",
    10: "Qatar",
    11: "Majlis Ugama Islam Singapura",
    12: "Union Organization Islamic de France",
    13: "Diyanet Isleri Baskanligi, Turkey",
    14: "Spiritual Administration of Muslims of Russia",
    15: "Moonsighting Committee Worldwide",
}

# Defaults
DEFAULT_OFFSET_MINUTES = 0
DEFAULT_METHOD = 10  # Qatar
DEFAULT_SOURCE = SOURCE_QATAR_MOI
DEFAULT_SUHOOR_OFFSET = 60
