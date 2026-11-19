"""Websocket command that hands the Internet Health card its layout (docs/DASHBOARD_CARD.md § Card)."""

from __future__ import annotations

from typing import Any

import probatio
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.decorators import websocket_command
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError

from ..dashboard import CARD_OPTIONS_SCHEMA, build_card_config

CARD_CONFIG_COMMAND = "internet_health_monitor/card_config"
ERR_CARD_UNAVAILABLE = "card_unavailable"


@websocket_command(
    {
        probatio.Required("type"): CARD_CONFIG_COMMAND,
        probatio.Optional("options", default=dict): CARD_OPTIONS_SCHEMA,
    }
)
@callback
def ws_card_config(hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]) -> None:
    """Send the card, or the reason there is none."""
    try:
        card = build_card_config(hass, msg["options"])
    except ServiceValidationError as err:
        connection.send_error(msg["id"], ERR_CARD_UNAVAILABLE, str(err))
        return
    connection.send_result(msg["id"], {"card": card})
