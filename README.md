<div align="center">

<img src="icon.png" alt="Minaret" width="200">

# Minaret

**Automated prayer times & azan playback for Home Assistant**

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

Minaret fetches daily prayer times, schedules azan audio playback to your Android phone via the HA Companion App, and provides a beautiful Lovelace dashboard card with live countdown, Hijri date, and playback controls.

## Features

- **Automatic prayer scheduling** - Schedules azan playback at exact prayer times (with configurable offset)
- **Two prayer time sources** - Qatar MOI portal or AlAdhan API (supports 15+ calculation methods worldwide)
- **YouTube audio support** - Provide a YouTube URL and Minaret downloads & caches the audio as MP3 via yt-dlp
- **Separate Fajr audio** - Optionally use a different azan recording for the Fajr prayer
- **Android playback via VLC** - Wakes the screen and plays audio through VLC with `command_screen_on` + `command_activity`
- **Stop control** - Stop playback remotely via `command_media` targeting VLC
- **Per-prayer toggles** - Enable/disable individual prayers (Fajr, Sunrise, Dhuhr, Asr, Maghrib, Isha)
- **Live countdown** - Client-side 1-second countdown timer to the next prayer
- **Hijri date** - Displays the current Islamic calendar date
- **Day/night theming** - Card auto-switches between light and dark theme based on sun position
- **Custom Lovelace card** - Pillars-inspired dashboard with no external dependencies

## Prerequisites

- **Home Assistant** 2024.1.0 or newer
- **HACS** (for easy installation) or manual install
- **HA Companion App** on your Android phone
- **VLC for Android** installed on your phone (used for audio playback)
- **ffmpeg** installed in your HA environment (for yt-dlp audio conversion)

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the **three dots** menu (top right) > **Custom repositories**
3. Add `https://github.com/bewinxed/minaret` with category **Integration**
4. Search for "Minaret" and install
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/azan` folder to your Home Assistant `config/custom_components/` directory
2. Copy `lovelace/azan-prayer-card.js` to your `config/www/azan/` directory
3. Restart Home Assistant

## Configuration

### 1. Add the Integration

Go to **Settings > Devices & Services > Add Integration** and search for **Minaret**.

The setup wizard will guide you through:

| Step | What you configure |
|------|--------------------|
| **Audio** | YouTube URL (or direct MP3 link) for the azan audio. Optional separate URL for Fajr. |
| **Prayer Source** | Qatar MOI (scrapes portal.moi.gov.qa) or AlAdhan API (global, 15+ methods). |
| **Location** | City, country, and calculation method (only if using AlAdhan). |
| **Schedule** | External URL (how your phone reaches HA), notify service name, offset minutes, and per-prayer toggles. |

### 2. Add the Lovelace Card

Add the card as a Lovelace resource:

1. Go to **Settings > Dashboards > Resources** (or edit `.storage/lovelace_resources`)
2. Add `/local/azan/azan-prayer-card.js` as a **JavaScript Module**

Then add the card to any dashboard view:

```yaml
type: custom:azan-prayer-card
```

No configuration needed - the card auto-discovers all Minaret entities.

### 3. Set Up Your Phone

1. Install **VLC for Android** from the Play Store
2. Set VLC as the default app for audio files
3. Ensure the **HA Companion App** is installed and connected
4. Grant the Companion App "Display over other apps" permission (triggered automatically on first play)

## Entities

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.minaret_fajr` | Sensor | Fajr prayer time (HH:MM) |
| `sensor.minaret_sunrise` | Sensor | Sunrise time |
| `sensor.minaret_dhuhr` | Sensor | Dhuhr prayer time |
| `sensor.minaret_asr` | Sensor | Asr prayer time |
| `sensor.minaret_maghrib` | Sensor | Maghrib prayer time |
| `sensor.minaret_isha` | Sensor | Isha prayer time |
| `sensor.minaret_next_prayer` | Sensor | Name of the next upcoming prayer |
| `sensor.minaret_countdown` | Sensor | Minutes until next prayer (updates every 60s) |
| `sensor.minaret_hijri_date` | Sensor | Current Hijri date (e.g., "28 Rajab 1447 AH") |
| `sensor.minaret_status` | Sensor | Current status: idle / playing / downloading |
| `button.minaret_test_play` | Button | Test azan playback |
| `button.minaret_refresh_times` | Button | Force-refresh prayer times |

## Services

| Service | Description |
|---------|-------------|
| `azan.play_azan` | Play azan for a specific prayer (Fajr/Dhuhr/Asr/Maghrib/Isha/Test) |
| `azan.stop_playback` | Stop currently playing azan |
| `azan.refresh_times` | Refresh prayer times from source |

## How It Works

1. On startup, Minaret fetches today's prayer times from your configured source
2. It downloads the azan audio from YouTube (or uses cached MP3) via yt-dlp
3. For each enabled prayer, it schedules an exact-time callback using `async_track_point_in_time`
4. When a prayer time arrives, it sends `command_screen_on` followed by `command_activity` to launch VLC with the audio URL
5. Prayer times refresh every 6 hours and at midnight
6. The Lovelace card reads entity states and provides a live client-side countdown

## Troubleshooting

**Audio doesn't play:**
- Ensure VLC is installed and set as default audio player
- Check that the external URL is reachable from your phone
- Verify the notify service name matches your phone (check **Settings > Companion App > Notifications**)

**Prayer times are wrong:**
- For Qatar MOI: times are specific to Qatar
- For AlAdhan: verify your city, country, and calculation method. Use method 10 (Qatar) for Qatar, method 2 (ISNA) for North America, method 3 (MWL) for Europe, etc.

**Card shows "Custom element doesn't exist":**
- Ensure the JS file is in `www/azan/azan-prayer-card.js`
- Ensure it's registered as a Lovelace resource
- Hard refresh the browser (Ctrl+Shift+R)

## License

MIT - See [LICENSE](LICENSE) for details.
