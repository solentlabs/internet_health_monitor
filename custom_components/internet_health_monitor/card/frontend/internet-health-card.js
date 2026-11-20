/**
 * Internet Health card: renders the layout the integration builds.
 *
 * One dependency-free ES module, no build step. The element is defined
 * before anything awaits, because HA waits only two seconds for an
 * undefined `custom:` element. See docs/DASHBOARD_CARD.md.
 */

const CARD_TAG = "internet-health-card";
const COMMAND = "internet_health_monitor/card_config";
const UNAVAILABLE = "card_unavailable";
// After a failed load, retry no sooner than this: hass updates arrive many times a second.
const RETRY_MS = 30000;
const GRAPH_HOURS_MAX = 168;

const LABELS = {
  include_status: "Network status",
  include_hops: "Each hop",
  include_latency: "Latency graphs",
  include_jitter: "Jitter graph",
  include_packet_loss: "Packet loss graph",
  include_speed_test: "Speed test",
  graph_hours: "Graph hours",
};

class InternetHealthCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  static getConfigForm() {
    return {
      // One field per line: tests read name and default from these lines.
      schema: [
        { name: "include_status", default: true, selector: { boolean: {} } },
        { name: "include_hops", default: true, selector: { boolean: {} } },
        { name: "include_latency", default: true, selector: { boolean: {} } },
        { name: "include_jitter", default: true, selector: { boolean: {} } },
        { name: "include_packet_loss", default: true, selector: { boolean: {} } },
        { name: "include_speed_test", default: true, selector: { boolean: {} } },
        { name: "graph_hours", default: 24, selector: { number: { min: 1, max: GRAPH_HOURS_MAX, mode: "box" } } },
      ],
      computeLabel: (field) => LABELS[field.name],
    };
  }

  constructor() {
    super();
    this._root = this.attachShadow({ mode: "open" });
    this._config = null;
    this._hass = null;
    this._child = null;
    this._loading = false;
    this._reload = false;
    this._retryAt = 0;
  }

  setConfig(config) {
    if (config === null || typeof config !== "object") {
      throw new Error("Card configuration must be an object");
    }
    const hours = config.graph_hours;
    if (hours !== undefined && !(Number.isInteger(hours) && hours >= 1 && hours <= GRAPH_HOURS_MAX)) {
      throw new Error(`graph_hours must be a whole number from 1 to ${GRAPH_HOURS_MAX}`);
    }
    this._config = config;
    this._child = null;
    this._retryAt = 0;
    this._load();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._child) {
      this._child.hass = hass;
    } else if (!this._loading && Date.now() >= this._retryAt) {
      this._load();
    }
  }

  getCardSize() {
    return 8;
  }

  async _load() {
    if (!this._config || !this._hass) {
      return;
    }
    if (this._loading) {
      this._reload = true;
      return;
    }
    this._loading = true;
    try {
      const { type, ...options } = this._config;
      const result = await this._hass.callWS({ type: COMMAND, options });
      const helpers = await window.loadCardHelpers();
      const child = helpers.createCardElement(result.card);
      child.hass = this._hass;
      this._child = child;
      this._root.replaceChildren(child);
    } catch (err) {
      this._child = null;
      this._retryAt = Date.now() + RETRY_MS;
      this._showMessage(err && err.code === UNAVAILABLE ? err.message : "Could not load the Internet Health card");
    } finally {
      this._loading = false;
      if (this._reload) {
        this._reload = false;
        this._load();
      }
    }
  }

  _showMessage(text) {
    const card = document.createElement("ha-card");
    const body = document.createElement("div");
    body.style.padding = "16px";
    body.textContent = text;
    card.appendChild(body);
    this._root.replaceChildren(card);
  }
}

// HA's frontend can replace `window.customElements` with a scoped-registry
// polyfill after this module has run, hiding an element defined earlier.
// Define now, then re-check until the registry in use holds the element.
const REGISTER_EVERY_MS = 100;
const REGISTER_FOR_MS = 15000;

function register() {
  if (!window.customElements.get(CARD_TAG)) {
    window.customElements.define(CARD_TAG, InternetHealthCard);
  }
}

register();
const registerUntil = Date.now() + REGISTER_FOR_MS;
const registerTimer = setInterval(() => {
  try {
    register();
  } catch (err) {
    console.warn("internet-health-card: could not register", err);
  }
  if (Date.now() >= registerUntil) {
    clearInterval(registerTimer);
  }
}, REGISTER_EVERY_MS);

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: "Internet Health",
    description: "Reachability, latency, jitter and packet loss along your path to the internet.",
    documentationURL: "https://github.com/solentlabs/internet_health_monitor/blob/main/docs/DASHBOARD_CARD.md",
  });
}
