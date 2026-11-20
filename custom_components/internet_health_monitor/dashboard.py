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
        probatio.Optional("include_hops", default=True): cv.boolean,
        probatio.Optional("include_latency", default=True): cv.boolean,
        probatio.Optional("include_jitter", default=True): cv.boolean,
        probatio.Optional("include_packet_loss", default=True): cv.boolean,
        probatio.Optional("include_speed_test", default=True): cv.boolean,
        probatio.Optional("graph_hours", default=GRAPH_HOURS_DEFAULT): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1, max=GRAPH_HOURS_MAX)
        ),
    }
)

# (platform, entity key, short label). Labels and titles are English (docs/DASHBOARD_CARD.md § Layout);
# a name the user gave the entity replaces the label.
Row = tuple[str, str, str]

HOP_NAMES = {1: "Gateway", 2: "ISP", 3: "Backbone"}
_HOPS = range(1, NUM_HOPS + 1)

_STATUS: list[Row] = [
    ("binary_sensor", "gateway_reachable", "Gateway"),
    ("binary_sensor", "internet_reachable", "Internet"),
    ("sensor", "dns_latency", "DNS latency"),
    ("button", "refresh_diagnostics", "Refresh"),
]


def _hop_rows(hop: int) -> list[Row]:
    """One hop's current readings."""
    return [
        ("sensor", f"hop_{hop}_latency", "Latency"),
        ("sensor", f"hop_{hop}_jitter", "Jitter"),
        ("sensor", f"hop_{hop}_packet_loss", "Packet loss"),
    ]


def _hop_lines(metric: str) -> list[Row]:
    """One metric across the hops, for a graph."""
    return [("sensor", f"hop_{hop}_{metric}", HOP_NAMES[hop]) for hop in _HOPS]


# Option -> (graph title, lines).
_GRAPHS: list[tuple[str, str, list[Row]]] = [
    ("include_latency", "Hop latency", _hop_lines("latency")),
    ("include_latency", "DNS latency", [("sensor", "dns_latency", "DNS")]),
    ("include_jitter", "Jitter", _hop_lines("jitter")),
    ("include_packet_loss", "Packet loss", _hop_lines("packet_loss")),
]

_SPEED_TEST: list[Row] = [
    ("sensor", "speed_test_download", "Download"),
    ("sensor", "speed_test_upload", "Upload"),
    ("sensor", "speed_test_idle_latency", "Idle latency"),
    ("sensor", "speed_test_download_latency", "Download latency"),
    ("sensor", "speed_test_upload_latency", "Upload latency"),
    ("sensor", "speed_test_bufferbloat_grade", "Bufferbloat grade"),
    ("sensor", "speed_test_download_latency_increase", "Download latency increase"),
    ("sensor", "speed_test_upload_latency_increase", "Upload latency increase"),
    ("sensor", "speed_test_data_used", "Data used"),
    ("button", "run_speed_test", "Run speed test"),
]
_THROUGHPUT: list[Row] = [
    ("sensor", "speed_test_download", "Download"),
    ("sensor", "speed_test_upload", "Upload"),
]


def _rows(registry: er.EntityRegistry, entry_id: str, targets: list[Row]) -> list[dict[str, str]]:
    """Registered, enabled entities as named rows, in order."""
    found = []
    for platform, key, label in targets:
        entity_id = registry.async_get_entity_id(platform, DOMAIN, f"{entry_id}_{key}")
        entity = registry.async_get(entity_id) if entity_id else None
        if entity and not entity.disabled:
            found.append({"entity": entity.entity_id, "name": entity.name or label})
    return found


def _entities(title: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    """An entities card."""
    return {"type": "entities", "title": title, "entities": rows}


def _graph(title: str, lines: list[dict[str, str]], hours: int) -> dict[str, Any]:
    """A history graph."""
    return {"type": "history-graph", "title": title, "hours_to_show": hours, "entities": lines}


def _parts(registry: er.EntityRegistry, entry_id: str, options: dict[str, Any]) -> list[dict[str, Any]]:
    """Every part the options switch on that has entities, in card order."""

    def rows(targets: list[Row]) -> list[dict[str, str]]:
        """This entry's rows for *targets*."""
        return _rows(registry, entry_id, targets)

    hours = options["graph_hours"]
    parts: list[dict[str, Any]] = []
    if options["include_status"] and (status := rows(_STATUS)):
        parts.append(_entities("Network Status", status))
    if options["include_hops"]:
        parts += [_entities(f"Hop {h} · {HOP_NAMES[h]}", r) for h in _HOPS if (r := rows(_hop_rows(h)))]
    parts += [_graph(title, lines, hours) for opt, title, t in _GRAPHS if options[opt] and (lines := rows(t))]
    if options["include_speed_test"] and (speed := rows(_SPEED_TEST)):
        parts += [_entities("Speed test", speed), _graph("Throughput", rows(_THROUGHPUT), hours)]
    return parts


def build_card_config(hass: HomeAssistant, options: dict[str, Any]) -> dict[str, Any]:
    """Return the card for validated *options*; raise ServiceValidationError if there is none."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="not_set_up")
    cards = _parts(er.async_get(hass), entries[0].entry_id, options)
    if not cards:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="nothing_to_show")
    return {"type": "vertical-stack", "cards": cards}
