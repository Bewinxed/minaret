"""Constants for the Minaret integration."""

DOMAIN = "azan"

# Config keys
CONF_AZAN_URL = "azan_url"
CONF_FAJR_URL = "fajr_azan_url"
CONF_PRAYER_SOURCE = "prayer_source"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_CITY = "city"
CONF_COUNTRY = "country"
CONF_METHOD = "method"
CONF_OFFSET_MINUTES = "offset_minutes"
CONF_EXTERNAL_URL = "external_url"
CONF_PLAYBACK_MODE = "playback_mode"
CONF_MEDIA_PLAYER = "media_player"

# Default sound selection keys
# Per-prayer sound selection keys
CONF_SOUND_FAJR = "sound_fajr"
CONF_SOUND_SUNRISE = "sound_sunrise"
CONF_SOUND_DHUHR = "sound_dhuhr"
CONF_SOUND_ASR = "sound_asr"
CONF_SOUND_MAGHRIB = "sound_maghrib"
CONF_SOUND_ISHA = "sound_isha"

# Sound options
SOUND_OPTION_FULL = "full"
SOUND_OPTION_SHORT = "short"
SOUND_OPTION_CUSTOM = "custom"

# Playback modes
PLAYBACK_ANDROID_VLC = "android_vlc"
PLAYBACK_MEDIA_PLAYER = "media_player"

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
DEFAULT_METHOD = 2  # Islamic Society of North America
DEFAULT_SOURCE = SOURCE_ALADHAN
