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

from solentlabs.internet_health_monitor_core.bufferbloat import MAY_AFFECT_REAL_TIME, SCALE, WORST
from solentlabs.internet_health_monitor_core.network_diagnostics import NUM_HOPS

from .const import DOMAIN

GRAPH_HOURS_DEFAULT = 24
HOP_LAYOUTS = ("cards", "table")
GRAPH_HOURS_MAX = 168

# Saved in users' dashboards: renaming a key breaks them (docs/DASHBOARD_CARD.md § Options).
CARD_OPTIONS_SCHEMA = probatio.Schema(
    {
        probatio.Optional("include_status", default=True): cv.boolean,
        probatio.Optional("include_hops", default=True): cv.boolean,
        # cards: one card per point; table: one combined card, readings inline (docs/DASHBOARD_CARD.md)
        probatio.Optional("hop_layout", default="cards"): probatio.In(HOP_LAYOUTS),
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

# Where hops 1 and 2 usually are; hop 3 has no such place, so it is named by number only.
HOP_PLACES = {1: "Gateway", 2: "ISP"}
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


def _reference_rows() -> list[Row]:
    """The internet reference's current readings (ADR-015)."""
    return [
        ("sensor", "internet_latency", "Latency"),
        ("sensor", "internet_jitter", "Jitter"),
        ("sensor", "internet_packet_loss", "Packet loss"),
    ]


def _hop_lines(metric: str) -> list[Row]:
    """One metric along the path, for a graph: each hop, then the internet reference."""
    hops = [("sensor", f"hop_{hop}_{metric}", HOP_PLACES.get(hop, f"Hop {hop}")) for hop in _HOPS]
    return [*hops, ("sensor", f"internet_{metric}", "Internet")]


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
]
_RUN: list[Row] = [("button", "run_speed_test", "Run speed test")]
# Lovelace config is plain text (no translation hook for a custom card): English, as the titles.
RUN_CONFIRMATION = (
    "Run a speed test now? It uses your whole connection for about 20 seconds, "
    "and its data counts toward your speed test data budget."
)
# The grade and the increases appear only as gauges: the list above does not repeat them.
_GRADE: list[Row] = [("sensor", "speed_test_bufferbloat_grade", "Bufferbloat")]
_BUFFERBLOAT: list[Row] = [
    ("sensor", "speed_test_download_latency_increase", "Download bufferbloat"),
    ("sensor", "speed_test_upload_latency_increase", "Upload bufferbloat"),
]
# Gauge range in ms: B's upper bound (60, where Waveform's grades start to "affect real-time
# applications") at 60% of the arc, so a healthy line reads as healthy. A larger value pins the
# needle at the end; HA picks a segment's label from the real value, so the C, D and F bands stay
# and the grade gauge still shows the right letter, and the direction gauges their exact ms.
GAUGE_MAX_MS = 100
# States with no reading yet: before the first speed test, or when the entity is unavailable.
NOT_MEASURED = ("unknown", "unavailable")
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


def _segments(*, labels: bool) -> list[dict[str, Any]]:
    """Waveform's bands (Core bufferbloat.py, R3), each from its grade's lower bound.

    Waveform publishes no colors, only that grades past B may affect real-time use,
    so the theme's success color up to B and its error color after. HA shows a
    segment's label instead of the value, so only the grade gauge, which reads the
    larger increase as Waveform grades, carries the grades as labels.
    """
    lower = [0.0, *(bound for bound, _ in SCALE)]
    grades = [*(g for _, g in SCALE), WORST]
    segments: list[dict[str, Any]] = []
    for start, grade in zip(lower, grades, strict=True):
        color = "var(--error-color)" if grade in MAY_AFFECT_REAL_TIME else "var(--success-color)"
        segments.append({"from": int(start), "color": color, **({"label": grade} if labels else {})})
    return segments


def _when_measured(entity_id: str, card: dict[str, Any]) -> dict[str, Any]:
    """Show *card* only once its entity has a value: a gauge shows an error for unknown."""
    condition = {"condition": "state", "entity": entity_id, "state_not": list(NOT_MEASURED)}
    return {"type": "conditional", "conditions": [condition], "card": card}


def _gauge(row: dict[str, str], *, labels: bool = False) -> dict[str, Any]:
    """A bufferbloat gauge over Waveform's bands, shown once measured."""
    gauge = {
        "type": "gauge",
        **row,
        "min": 0,
        "max": GAUGE_MAX_MS,
        "needle": True,
        "segments": _segments(labels=labels),
    }
    return _when_measured(row["entity"], gauge)


def _grade_gauge(row: dict[str, str]) -> dict[str, Any]:
    """The grade: the larger increase, labeled with its grade, full width, shown once graded."""
    gauge = _gauge(row, labels=True)
    gauge["card"] |= {"attribute": "latency_increase_ms", "unit": "ms"}
    return gauge


def _direction_gauges(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Each direction's increase in ms, side by side."""
    return {"type": "horizontal-stack", "cards": [_gauge(row) for row in rows]}


def _speed_test_card(rows: list[dict[str, str]]) -> dict[str, Any]:
    """The latest test's readings, and when it ran from the first reading's tested_at attribute."""
    last_test = {
        "type": "attribute",
        "entity": rows[0]["entity"],
        "attribute": "tested_at",
        "name": "Last test",
        "time_format": "datetime",
    }
    return _entities("Speed test", [*rows, last_test])


def _hop_card(hop: int, rows: list[dict[str, str]]) -> dict[str, Any]:
    """One hop's readings, and its address from the first reading's hop_ip attribute."""
    address = {"type": "attribute", "entity": rows[0]["entity"], "attribute": "hop_ip", "name": "Address"}
    title = f"Hop {hop} · {HOP_PLACES[hop]}" if hop in HOP_PLACES else f"Hop {hop}"
    return _entities(title, [*rows, address])


def _reference_card(rows: list[dict[str, str]]) -> dict[str, Any]:
    """The internet reference's readings, and the address it pings from the first reading's attribute."""
    address = {"type": "attribute", "entity": rows[0]["entity"], "attribute": "reference_ip", "name": "Address"}
    return _entities("Internet reference", [*rows, address])


# The combined card: each point (key prefix, row name, address attribute), its latency
# sensor's icon (icons.json; a test keeps them equal), and the readings across.
_POINTS: list[tuple[str, str, str]] = [
    *((f"hop_{hop}", HOP_PLACES.get(hop, f"Hop {hop}"), "hop_ip") for hop in _HOPS),
    ("internet", "Internet", "reference_ip"),
]
PATH_ICONS = {
    "hop_1_latency": "mdi:router-wireless",
    "hop_2_latency": "mdi:wan",
    "hop_3_latency": "mdi:server-network",
    "internet_latency": "mdi:earth",
}
_READINGS = ("latency", "jitter", "packet_loss")


def _value(entity_id: str) -> str:
    """A reading with its unit at the sensor's display precision; a dash while unknown or unavailable."""
    return f"{{{{ states('{entity_id}', rounded=True, with_unit=True) if has_value('{entity_id}') else '–' }}}}"


def _path_table(registry: er.EntityRegistry, entry_id: str) -> dict[str, Any] | None:
    """One markdown card: a row per point with its icon, its readings with units, and its address.

    A point is shown when its latency sensor is; HA's template engine fills the values at each
    sensor's display precision, so the card needs no code of its own.
    """
    lines = ["| | Latency | Jitter | Loss | Address |", "|:--|--:|--:|--:|:--|"]
    for prefix, name, attribute in _POINTS:
        ids: dict[str, str | None] = {}
        for reading in _READINGS:
            found = _rows(registry, entry_id, [("sensor", f"{prefix}_{reading}", name)])
            ids[reading] = found[0]["entity"] if found else None
        latency = ids["latency"]
        if not latency:
            continue
        values = [_value(entity) if (entity := ids[r]) else "–" for r in _READINGS]
        icon = f'<ha-icon icon="{PATH_ICONS[f"{prefix}_latency"]}"></ha-icon>'
        address = f"{{{{ state_attr('{latency}', '{attribute}') or '–' }}}}"
        lines.append(f"| {icon} {name} | " + " | ".join(values) + f" | {address} |")
    if len(lines) == 2:
        return None
    return {"type": "markdown", "title": "Network path", "content": "\n".join(lines)}


def _run_button(row: dict[str, str]) -> dict[str, Any]:
    """Run speed test as its own button card, asking first (Cable Modem Monitor's Restart pattern).

    A button row in an entities card presses without the row's confirmation when its own Press
    is clicked, so only a button card asks every time.
    """
    entity = row["entity"]
    press = {"action": "perform-action", "perform_action": "button.press", "target": {"entity_id": entity}}
    return {
        "type": "button",
        **row,
        "show_state": False,
        "tap_action": {**press, "confirmation": {"text": RUN_CONFIRMATION}},
    }


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
    if options["include_hops"] and options["hop_layout"] == "table":
        if table := _path_table(registry, entry_id):
            parts.append(table)
    elif options["include_hops"]:
        parts += [_hop_card(h, r) for h in _HOPS if (r := rows(_hop_rows(h)))]
        if reference := rows(_reference_rows()):
            parts.append(_reference_card(reference))
    parts += [_graph(title, lines, hours) for opt, title, t in _GRAPHS if options[opt] and (lines := rows(t))]
    if options["include_speed_test"] and (speed := rows(_SPEED_TEST)):
        parts.append(_speed_test_card(speed))
        parts += [_run_button(row) for row in rows(_RUN)]
        parts += [_grade_gauge(row) for row in rows(_GRADE)]
        if directions := rows(_BUFFERBLOAT):
            parts.append(_direction_gauges(directions))
        parts.append(_graph("Throughput", rows(_THROUGHPUT), hours))
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
