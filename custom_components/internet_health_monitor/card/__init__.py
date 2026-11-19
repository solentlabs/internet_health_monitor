"""Bundled Internet Health card: the one entry point the integration calls.

The card is additive: nothing here may stop monitoring from loading
(docs/DASHBOARD_CARD.md § Card).
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from ..const import VERSION
from .commands import ws_card_config

_LOGGER = logging.getLogger(__name__)

CARD_URL_BASE = "/internet_health_monitor/card"
CARD_MODULE = "internet-health-card.js"
_FRONTEND_DIR = Path(__file__).parent / "frontend"


async def async_register_card(hass: HomeAssistant) -> None:
    """Register the card's command, then serve and load its module when a frontend exists."""
    try:
        websocket_api.async_register_command(hass, ws_card_config)
        if "frontend" not in hass.config.components or "http" not in hass.config.components:
            _LOGGER.debug("Internet Health card not served: frontend or http is not loaded")
            return
        # The version query busts the browser cache on upgrade; HA keeps the
        # URL in memory only, so this runs on every start.
        await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL_BASE, str(_FRONTEND_DIR), False)])
        add_extra_js_url(hass, f"{CARD_URL_BASE}/{CARD_MODULE}?v={VERSION}")
    except Exception:  # noqa: BLE001  # the card is additive; a failure here must not stop monitoring
        _LOGGER.warning("Internet Health card could not be registered; monitoring is unaffected", exc_info=True)
