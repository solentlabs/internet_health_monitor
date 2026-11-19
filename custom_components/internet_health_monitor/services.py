"""Actions: generate_dashboard_card (docs/DASHBOARD_CARD.md § Action)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse, callback
from homeassistant.util.yaml import dump

from .const import DOMAIN
from .dashboard import CARD_OPTIONS_SCHEMA, build_card_config

SERVICE_GENERATE_DASHBOARD_CARD = "generate_dashboard_card"


@callback
def _generate_dashboard_card(call: ServiceCall) -> ServiceResponse:
    """Return the card's YAML for the given options."""
    return {"yaml": dump(build_card_config(call.hass, dict(call.data)))}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions (once, from async_setup)."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_DASHBOARD_CARD,
        _generate_dashboard_card,
        schema=CARD_OPTIONS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
