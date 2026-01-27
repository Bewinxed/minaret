/**
 * Minaret - Custom Lovelace Card
 * A Pillars-inspired prayer times dashboard for Home Assistant.
 */

const PRAYER_ORDER = ["Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha"];

const PRAYER_EMOJI = {
  Fajr: "\u{1F305}",
  Sunrise: "\u{2600}\u{FE0F}",
  Dhuhr: "\u{1F54C}",
  Asr: "\u{26C5}",
  Maghrib: "\u{1F307}",
  Isha: "\u{1F319}",
};

class AzanPrayerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._countdownInterval = null;
  }

  set hass(hass) {
    this._hass = hass;

    if (!this.shadowRoot.querySelector(".azan-card")) {
      this._render();
    } else {
      this._update();
    }

    if (!this._countdownInterval) {
      this._countdownInterval = setInterval(() => this._updateCountdown(), 1000);
    }
  }

  setConfig(config) {
    this._config = config;
    this._entityPrefix =
      config.entity_prefix || "sensor.azan_prayer_service";
  }

  getCardSize() {
    return 8;
  }

  static getConfigElement() {
    return document.createElement("div");
  }

  static getStubConfig() {
    return {};
  }

  disconnectedCallback() {
    if (this._countdownInterval) {
      clearInterval(this._countdownInterval);
      this._countdownInterval = null;
    }
  }

  // --- Helpers ---

  _entity(suffix) {
    return this._hass
      ? this._hass.states[`${this._entityPrefix}_${suffix}`]
      : null;
  }

  _isNight() {
    const sun = this._hass?.states["sun.sun"];
    return sun ? sun.state === "below_horizon" : true;
  }

  _getNextPrayerDatetime() {
    const next = this._entity("next_prayer");
    if (!next || !next.attributes.datetime) return null;
    return new Date(next.attributes.datetime);
  }

  _formatCountdown(diffMs) {
    if (diffMs <= 0) return { h: 0, m: 0, s: 0, text: "Now" };
    const totalSec = Math.floor(diffMs / 1000);
    const h = Math.floor(totalSec / 3600);
    const m = Math.floor((totalSec % 3600) / 60);
    const s = totalSec % 60;
    const parts = [];
    if (h > 0) parts.push(`${h}h`);
    parts.push(`${m}m`);
    parts.push(`${String(s).padStart(2, "0")}s`);
    return { h, m, s, text: parts.join(" ") };
  }

  _getPrayerStatus(prayerName) {
    const entity = this._entity(prayerName.toLowerCase());
    if (!entity || ["unknown", "unavailable"].includes(entity.state)) return "unknown";
    const attrs = entity.attributes;
    const prayerTime = attrs.datetime ? new Date(attrs.datetime) : null;
    const now = new Date();
    const nextPrayer = this._entity("next_prayer");
    const nextName = nextPrayer && !["unknown", "unavailable"].includes(nextPrayer.state) ? nextPrayer.state : null;

    if (attrs.played) return "played";
    if (prayerName === nextName) return "next";
    if (prayerTime && prayerTime < now) return "passed";
    return "upcoming";
  }

  _getStatusInfo() {
    const status = this._entity("status");
    if (!status) return { state: "idle", playing: null };
    return {
      state: status.state,
      playing: status.attributes.currently_playing || null,
    };
  }

  _el(tag, className, textContent) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (textContent !== undefined) el.textContent = textContent;
    return el;
  }

  // --- Rendering ---

  _render() {
    const root = this.shadowRoot;

    // Clear
    while (root.firstChild) root.removeChild(root.firstChild);

    // Style
    const style = document.createElement("style");
    style.textContent = this._getStyles();
    root.appendChild(style);

    // Card container
    const card = this._el("div", `azan-card ${this._isNight() ? "night" : "day"}`);

    // Hero section
    const hero = this._el("div", "hero");
    hero.appendChild(this._el("div", "hijri-date"));
    hero.appendChild(this._el("div", "gregorian-date"));
    hero.appendChild(this._el("div", "next-prayer-label"));
    hero.appendChild(this._el("div", "next-prayer-time"));
    hero.appendChild(this._el("div", "countdown-badge"));
    card.appendChild(hero);

    // Prayer list
    card.appendChild(this._el("div", "prayer-list"));

    // Actions
    const actions = this._el("div", "actions");
    const playBtn = this._el("button", "action-btn play-btn", "\u{25B6} Test Play");
    const stopBtn = this._el("button", "action-btn stop-btn", "\u{23F9} Stop");
    const refreshBtn = this._el("button", "action-btn refresh-btn", "\u{21BB}");

    playBtn.addEventListener("click", () => {
      this._hass.callService("azan", "play_azan", { prayer: "Test" });
    });
    stopBtn.addEventListener("click", () => {
      this._hass.callService("azan", "stop_playback", {});
    });
    refreshBtn.addEventListener("click", () => {
      this._hass.callService("azan", "refresh_times", {});
    });

    actions.appendChild(playBtn);
    actions.appendChild(stopBtn);
    actions.appendChild(refreshBtn);
    card.appendChild(actions);

    // Status bar
    card.appendChild(this._el("div", "status-bar"));

    root.appendChild(card);
    this._update();
  }

  _update() {
    if (!this._hass) return;

    const night = this._isNight();
    const card = this.shadowRoot.querySelector(".azan-card");
    if (card) {
      card.className = `azan-card ${night ? "night" : "day"}`;
    }

    this._updateHero();
    this._updatePrayerList();
    this._updateStatusBar();
  }

  _updateHero() {
    const hero = this.shadowRoot.querySelector(".hero");
    if (!hero) return;

    const hijriEl = hero.querySelector(".hijri-date");
    const gregEl = hero.querySelector(".gregorian-date");
    const nextLabel = hero.querySelector(".next-prayer-label");
    const nextTime = hero.querySelector(".next-prayer-time");

    // Hijri date
    const hijri = this._entity("hijri_date");
    if (hijriEl) {
      const hijriState = hijri && !["unknown", "unavailable"].includes(hijri.state) ? hijri.state : "";
      hijriEl.textContent = hijriState;
    }

    // Gregorian
    if (gregEl) {
      const now = new Date();
      gregEl.textContent = now.toLocaleDateString("en-US", {
        weekday: "long",
        day: "numeric",
        month: "long",
      });
    }

    // Next prayer
    const next = this._entity("next_prayer");
    const hasNext = next && next.state && !["unknown", "unavailable"].includes(next.state);
    if (nextLabel) {
      if (hasNext) {
        const emoji = PRAYER_EMOJI[next.state] || "\u{1F54C}";
        nextLabel.textContent = `${emoji} ${next.state}`;
      } else {
        nextLabel.textContent = "\u{1F319} All prayers complete";
      }
    }
    if (nextTime) {
      nextTime.textContent = hasNext && next.attributes.time ? next.attributes.time : "";
    }

    // Countdown
    this._updateCountdown();
  }

  _updateCountdown() {
    const badge = this.shadowRoot?.querySelector(".countdown-badge");
    if (!badge) return;
    const target = this._getNextPrayerDatetime();
    if (!target) {
      badge.textContent = "See you at Fajr";
      return;
    }
    const diff = target.getTime() - Date.now();
    const cd = this._formatCountdown(diff);
    badge.textContent = cd.text;
  }

  _updatePrayerList() {
    const list = this.shadowRoot.querySelector(".prayer-list");
    if (!list) return;

    const statusInfo = this._getStatusInfo();

    // Clear existing rows
    while (list.firstChild) list.removeChild(list.firstChild);

    for (const name of PRAYER_ORDER) {
      const entity = this._entity(name.toLowerCase());
      const time = entity ? entity.state : "--:--";
      const status = this._getPrayerStatus(name);
      const emoji = PRAYER_EMOJI[name] || "";
      const enabled = entity ? entity.attributes.enabled !== false : true;

      let statusText = "";
      let statusClass = status;

      if (!enabled) {
        statusText = "Disabled";
        statusClass = "disabled";
      } else if (status === "played") {
        statusText = "\u{2714} Played";
      } else if (status === "next") {
        statusText =
          statusInfo.state === "playing" && statusInfo.playing === name
            ? "\u{1F50A} Playing"
            : "\u{25B6} Next";
      } else if (status === "passed") {
        statusText = "\u{00B7} Passed";
      } else {
        statusText = time;
      }

      const row = this._el("div", `prayer-row ${statusClass}`);
      row.appendChild(this._el("span", "prayer-emoji", emoji));
      row.appendChild(this._el("span", "prayer-name", name));
      row.appendChild(this._el("span", "prayer-time", time));
      row.appendChild(this._el("span", "prayer-status", statusText));
      list.appendChild(row);
    }
  }

  _updateStatusBar() {
    const el = this.shadowRoot.querySelector(".status-bar");
    if (!el) return;
    const info = this._getStatusInfo();

    // Clear
    while (el.firstChild) el.removeChild(el.firstChild);

    if (info.state === "playing") {
      const container = this._el("div", "status-playing");
      const dot = this._el("span", "pulse-dot");
      container.appendChild(dot);
      container.appendChild(document.createTextNode(` Now Playing: ${info.playing || "Azan"}`));
      el.appendChild(container);
    } else if (info.state === "downloading") {
      el.appendChild(this._el("div", "status-downloading", "Downloading audio..."));
    } else {
      el.appendChild(this._el("div", "status-idle", "Ready"));
    }
  }

  // --- Styles ---

  _getStyles() {
    return `
      @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');

      :host {
        display: block;
        --gold: #c8a951;
        --green: #2e7d32;
        --green-light: #4caf50;
      }

      .azan-card {
        font-family: 'Poppins', sans-serif;
        border-radius: 20px;
        overflow: hidden;
        max-width: 480px;
        margin: 0 auto;
        transition: background 0.5s ease, color 0.5s ease;
      }

      /* Night theme */
      .azan-card.night {
        background: linear-gradient(180deg, #0a1628 0%, #1a2940 40%, #0d1f35 100%);
        color: #e8e0d0;
        --row-bg: rgba(255,255,255,0.04);
        --row-border: rgba(255,255,255,0.06);
        --muted: #8899aa;
        --btn-bg: rgba(255,255,255,0.08);
        --btn-hover: rgba(255,255,255,0.15);
        --badge-bg: rgba(200,169,81,0.15);
        --badge-border: rgba(200,169,81,0.3);
        --next-bg: rgba(200,169,81,0.1);
        --next-border-left: var(--gold);
        --status-bg: rgba(255,255,255,0.03);
      }

      /* Day theme */
      .azan-card.day {
        background: linear-gradient(180deg, #f5f0e8 0%, #eee8db 40%, #e8e0d0 100%);
        color: #1a1a2e;
        --row-bg: rgba(0,0,0,0.02);
        --row-border: rgba(0,0,0,0.06);
        --muted: #6b7280;
        --btn-bg: rgba(0,0,0,0.06);
        --btn-hover: rgba(0,0,0,0.12);
        --badge-bg: rgba(46,125,50,0.1);
        --badge-border: rgba(46,125,50,0.3);
        --next-bg: rgba(46,125,50,0.08);
        --next-border-left: var(--green);
        --status-bg: rgba(0,0,0,0.03);
      }

      /* Hero section */
      .hero {
        text-align: center;
        padding: 32px 24px 28px;
      }

      .hijri-date {
        font-size: 13px;
        font-weight: 500;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        opacity: 0.7;
        margin-bottom: 2px;
      }

      .gregorian-date {
        font-size: 12px;
        opacity: 0.5;
        margin-bottom: 20px;
      }

      .next-prayer-label {
        font-size: 28px;
        font-weight: 600;
        margin-bottom: 4px;
      }

      .next-prayer-time {
        font-size: 18px;
        font-weight: 300;
        opacity: 0.7;
        margin-bottom: 16px;
      }

      .countdown-badge {
        display: inline-block;
        font-size: 22px;
        font-weight: 600;
        padding: 10px 28px;
        border-radius: 24px;
        background: var(--badge-bg);
        border: 1px solid var(--badge-border);
        font-variant-numeric: tabular-nums;
        letter-spacing: 0.5px;
      }

      .night .countdown-badge {
        color: var(--gold);
      }
      .day .countdown-badge {
        color: var(--green);
      }

      /* Prayer list */
      .prayer-list {
        padding: 0 16px 8px;
      }

      .prayer-row {
        display: flex;
        align-items: center;
        padding: 14px 16px;
        margin-bottom: 4px;
        border-radius: 14px;
        background: var(--row-bg);
        transition: all 0.2s ease;
      }

      .prayer-row.next {
        background: var(--next-bg);
        border-left: 3px solid var(--next-border-left);
      }

      .prayer-row.played {
        opacity: 0.5;
      }

      .prayer-row.passed {
        opacity: 0.45;
      }

      .prayer-row.disabled {
        opacity: 0.3;
      }

      .prayer-emoji {
        font-size: 20px;
        width: 32px;
        text-align: center;
        flex-shrink: 0;
      }

      .prayer-name {
        font-weight: 500;
        font-size: 15px;
        flex: 1;
        margin-left: 8px;
      }

      .prayer-time {
        font-size: 14px;
        font-weight: 400;
        opacity: 0.7;
        margin-right: 16px;
        font-variant-numeric: tabular-nums;
      }

      .prayer-status {
        font-size: 12px;
        font-weight: 500;
        min-width: 70px;
        text-align: right;
        color: var(--muted);
      }

      .prayer-row.next .prayer-status {
        color: var(--next-border-left);
        font-weight: 600;
      }

      .prayer-row.played .prayer-status {
        color: var(--green-light);
      }

      /* Actions */
      .actions {
        display: flex;
        gap: 10px;
        padding: 12px 20px 8px;
        justify-content: center;
      }

      .action-btn {
        font-family: 'Poppins', sans-serif;
        font-size: 13px;
        font-weight: 500;
        border: none;
        padding: 10px 20px;
        border-radius: 12px;
        cursor: pointer;
        background: var(--btn-bg);
        color: inherit;
        transition: background 0.2s ease, transform 0.1s ease;
      }

      .action-btn:hover {
        background: var(--btn-hover);
      }

      .action-btn:active {
        transform: scale(0.96);
      }

      .play-btn {
        flex: 1;
        max-width: 160px;
      }

      .stop-btn {
        flex: 1;
        max-width: 120px;
      }

      .refresh-btn {
        width: 44px;
        height: 44px;
        padding: 0;
        font-size: 18px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 12px;
        flex-shrink: 0;
      }

      /* Status bar */
      .status-bar {
        text-align: center;
        padding: 12px 20px 20px;
        font-size: 12px;
        color: var(--muted);
      }

      .status-playing {
        color: var(--gold);
        font-weight: 500;
        animation: pulse-text 2s ease-in-out infinite;
      }

      .status-downloading {
        opacity: 0.6;
      }

      .status-idle {
        opacity: 0.4;
      }

      .pulse-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--gold);
        margin-right: 6px;
        vertical-align: middle;
        animation: pulse-dot 1.5s ease-in-out infinite;
      }

      @keyframes pulse-dot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.4; transform: scale(0.8); }
      }

      @keyframes pulse-text {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
      }
    `;
  }
}

customElements.define("azan-prayer-card", AzanPrayerCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "azan-prayer-card",
  name: "Minaret Prayer Card",
  description: "Prayer times dashboard with live countdown, Hijri date, and azan playback controls.",
});
