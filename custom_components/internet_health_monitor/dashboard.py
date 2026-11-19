"""Dashboard card layout: one builder for the action and the bundled card (docs/DASHBOARD_CARD.md)."""

from __future__ import annotations

from typing import Any

import probatio
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
)

from solentlabs.internet_health_monitor_core.network_diagnostics import NUM_HOPS

from .const import DOMAIN

GRAPH_HOURS_DEFAULT = 24
GRAPH_HOURS_MAX = 168

# Saved in users' dashboards: renaming a key breaks them (docs/DASHBOARD_CARD.md § Options).
CARD_OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Optional("include_status", default=True): cv.boolean,
        probatio.Optional("include_latency", default=True): cv.boolean,
        probatio.Optional("include_jitter", default=True): cv.boolean,
        probatio.Optional("include_packet_loss", default=True): cv.boolean,
        probatio.Optional("include_speed_test", default=True): cv.boolean,
        probatio.Optional("graph_hours", default=GRAPH_HOURS_DEFAULT): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1, max=GRAPH_HOURS_MAX)
        ),
    }
)

_HOPS = range(1, NUM_HOPS + 1)
_LATENCY = [*(f"hop_{n}_latency" for n in _HOPS), "dns_latency"]
_STATUS: list[tuple[str, str]] = [
    ("binary_sensor", "gateway_reachable"),
    ("binary_sensor", "internet_reachable"),
    *(("sensor", key) for key in _LATENCY),
    ("button", "refresh_diagnostics"),
]
_SPEED_TEST: list[tuple[str, str]] = [
    *(
        ("sensor", f"speed_test_{field}")
        for field in ("download", "upload", "idle_latency", "download_latency", "upload_latency", "data_used")
    ),
    ("button", "run_speed_test"),
]
# Option -> (graph title, sensor keys). Titles are English (docs/DASHBOARD_CARD.md § Layout).
_GRAPHS: list[tuple[str, str, list[str]]] = [
    ("include_latency", "Latency", _LATENCY),
    ("include_jitter", "Jitter", [f"hop_{n}_jitter" for n in _HOPS]),
    ("include_packet_loss", "Packet loss", [f"hop_{n}_packet_loss" for n in _HOPS]),
]


def build_card_config(hass: HomeAssistant, options: dict[str, Any]) -> dict[str, Any]:
    """Return the card for validated *options*; raise ServiceValidationError if there is none."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_set_up")
    entry_id = entries[0].entry_id
    registry = er.async_get(hass)

    def ids(targets: list[tuple[str, str]]) -> list[str]:
        """Registered, enabled entity ids for (platform, key) pairs, in order."""
        found = []
        for platform, key in targets:
            entity_id = registry.async_get_entity_id(platform, DOMAIN, f"{entry_id}_{key}")
            entity = registry.async_get(entity_id) if entity_id else None
            if entity and not entity.disabled:
                found.append(entity.entity_id)
        return found

    cards: list[dict[str, Any]] = []
    if options["include_status"] and (status := ids(_STATUS)):
        cards.append({"type": "entities", "entities": status})
    for option, title, keys in _GRAPHS:
        if options[option] and (graphed := ids([("sensor", key) for key in keys])):
            cards.append(
                {"type": "history-graph", "title": title, "hours_to_show": options["graph_hours"], "entities": graphed}
            )
    if options["include_speed_test"] and (speed := ids(_SPEED_TEST)):
        cards.append({"type": "entities", "title": "Speed test", "entities": speed})
        throughput = ids([("sensor", "speed_test_download"), ("sensor", "speed_test_upload")])
        cards.append(
            {
                "type": "history-graph",
                "title": "Throughput",
                "hours_to_show": options["graph_hours"],
                "entities": throughput,
            }
        )
    if not cards:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="nothing_to_show")
    return {"type": "vertical-stack", "cards": cards}
