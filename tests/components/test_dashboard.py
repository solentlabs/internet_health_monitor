"""Dashboard card: layout builder, action, websocket command, registration (docs/DASHBOARD_CARD.md)."""

from __future__ import annotations

import builtins
import re
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import probatio
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.yaml import parse_yaml
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.internet_health_monitor.card import CARD_MODULE, CARD_URL_BASE, async_register_card
from custom_components.internet_health_monitor.card.commands import CARD_CONFIG_COMMAND, ERR_CARD_UNAVAILABLE
from custom_components.internet_health_monitor.const import DOMAIN, VERSION
from custom_components.internet_health_monitor.dashboard import CARD_OPTIONS_SCHEMA, build_card_config
from custom_components.internet_health_monitor.services import SERVICE_GENERATE_DASHBOARD_CARD

from .conftest import SetupEntry, entity_id

FRONTEND = Path(__file__).parents[2] / "custom_components" / DOMAIN / "card" / "frontend"

GATEWAY_REACHABLE = "binary_sensor.internet_health_gateway_reachable"
INTERNET_REACHABLE = "binary_sensor.internet_health_internet_reachable"
DNS_LATENCY = "sensor.internet_health_dns_latency"
REFRESH = "button.internet_health_refresh_diagnostics"
SUFFIX = {1: "_gateway", 2: "_isp", 3: ""}


def _hop(hop: int, metric: str) -> str:
    """A hop sensor's default entity id."""
    return f"sensor.internet_health_hop_{hop}_{metric}{SUFFIX[hop]}"


def _graph(title: str, metric: str) -> dict[str, Any]:
    """A default path graph: one line per hop, named for the hop, then the internet reference."""
    lines = [{"entity": _hop(h, metric), "name": n} for h, n in ((1, "Gateway"), (2, "ISP"), (3, "Hop 3"))]
    lines.append({"entity": f"sensor.internet_health_internet_{metric}", "name": "Internet"})
    return {"type": "history-graph", "title": title, "hours_to_show": 24, "entities": lines}


def _reference_card() -> dict[str, Any]:
    """The internet reference's card: its readings and the address it pings (ADR-015)."""
    rows = [("latency", "Latency"), ("jitter", "Jitter"), ("packet_loss", "Packet loss")]
    latency = "sensor.internet_health_internet_latency"
    address = {"type": "attribute", "entity": latency, "attribute": "reference_ip", "name": "Address"}
    return {
        "type": "entities",
        "title": "Internet reference",
        "entities": [
            *({"entity": f"sensor.internet_health_internet_{m}", "name": label} for m, label in rows),
            address,
        ],
    }


def _hop_card(hop: int, name: str | None) -> dict[str, Any]:
    """A default per-hop card: current latency, jitter and loss, and the hop's address (latency's attribute)."""
    rows = [("latency", "Latency"), ("jitter", "Jitter"), ("packet_loss", "Packet loss")]
    address = {"type": "attribute", "entity": _hop(hop, "latency"), "attribute": "hop_ip", "name": "Address"}
    return {
        "type": "entities",
        "title": f"Hop {hop} · {name}" if name else f"Hop {hop}",
        "entities": [*({"entity": _hop(hop, metric), "name": label} for metric, label in rows), address],
    }


DEFAULT_CARD: dict[str, Any] = {
    "type": "vertical-stack",
    "cards": [
        {
            "type": "entities",
            "title": "Network Status",
            "entities": [
                {"entity": GATEWAY_REACHABLE, "name": "Gateway"},
                {"entity": INTERNET_REACHABLE, "name": "Internet"},
                {"entity": DNS_LATENCY, "name": "DNS latency"},
                {"entity": REFRESH, "name": "Refresh"},
            ],
        },
        _hop_card(1, "Gateway"),
        _hop_card(2, "ISP"),
        _hop_card(3, None),
        _reference_card(),
        _graph("Hop latency", "latency"),
        {
            "type": "history-graph",
            "title": "DNS latency",
            "hours_to_show": 24,
            "entities": [{"entity": DNS_LATENCY, "name": "DNS"}],
        },
        _graph("Jitter", "jitter"),
        _graph("Packet loss", "packet_loss"),
    ],
}

HOPS = ["Hop 1 · Gateway", "Hop 2 · ISP", "Hop 3", "Internet reference"]
STATUS = "Network Status"
GRAPHS = ["Hop latency", "DNS latency", "Jitter", "Packet loss"]
NO_JITTER = ["Hop latency", "DNS latency", "Packet loss"]
NO_GRAPHS = {"include_latency": False, "include_jitter": False, "include_packet_loss": False}
NO_REFERENCE = {"internet_reference": "off"}

# ┌──────────────────────────┬──────────────────────┬──────────────────────────────────────────────┬──────────────┐
# │ entry options            │ card options         │ expected part titles                         │ description  │
# ├──────────────────────────┼──────────────────────┼──────────────────────────────────────────────┼──────────────┤
# │ defaults                 │ {}                   │ status, 3 hops, reference card, 4 graphs     │ everything   │
# │ defaults                 │ include_hops off     │ status, 4 graphs                             │ hops off     │
# │ defaults                 │ include_jitter off   │ status, 3 hops, latency, dns, loss           │ one graph    │
# │ defaults                 │ graphs off           │ status, 3 hops                               │ graphs off   │
# │ internet reference off   │ {}                   │ status, 3 hops, 4 graphs                     │ no reference │
# └──────────────────────────┴──────────────────────┴──────────────────────────────────────────────┴──────────────┘
# fmt: off
LAYOUT_CASES: list[tuple[dict[str, Any], dict[str, Any], list[str], str]] = [
    ({},         {},                        [STATUS, *HOPS, *GRAPHS],         "everything"),
    ({},         {"include_hops": False},   [STATUS, *GRAPHS],                "hops_off"),
    ({},         {"include_jitter": False}, [STATUS, *HOPS, *NO_JITTER],      "one_graph_off"),
    ({},         NO_GRAPHS,                 [STATUS, *HOPS],                  "graphs_off"),
    (NO_REFERENCE, {},                      [STATUS, *HOPS[:3], *GRAPHS],     "no_reference"),
]
# fmt: on


def _titles(card: dict[str, Any]) -> list[str]:
    """Each part's title."""
    return [part["title"] for part in card["cards"]]


async def test_default_layout(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """A new install's card: status, one card per hop, then hop latency, DNS, jitter and loss graphs."""
    await setup_entry()
    assert build_card_config(hass, CARD_OPTIONS_SCHEMA({})) == DEFAULT_CARD


@pytest.mark.parametrize("entry_options,card_options,expected,desc", LAYOUT_CASES, ids=[c[3] for c in LAYOUT_CASES])
async def test_layout_follows_options(
    hass: HomeAssistant,
    setup_entry: SetupEntry,
    entry_options: dict[str, Any],
    card_options: dict[str, Any],
    expected: list[str],
    desc: str,
) -> None:
    """Parts follow the card's options and the entities the entry created."""
    await setup_entry(**entry_options)
    assert _titles(build_card_config(hass, CARD_OPTIONS_SCHEMA(card_options))) == expected, desc


async def test_layout_uses_registry_ids_names_and_skips_disabled(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """A renamed entity keeps its place under its new id and its own name; a disabled one is left out."""
    entry = await setup_entry()
    registry = er.async_get(hass)
    hop_1 = entity_id(hass, "sensor", entry, "hop_1_latency")
    hop_3 = entity_id(hass, "sensor", entry, "hop_3_latency")
    assert hop_1 and hop_3
    registry.async_update_entity(hop_1, new_entity_id="sensor.my_router", name="My router")
    registry.async_update_entity(hop_3, disabled_by=er.RegistryEntryDisabler.USER)
    graph = build_card_config(hass, CARD_OPTIONS_SCHEMA({}))["cards"][5]
    assert graph["entities"] == [
        {"entity": "sensor.my_router", "name": "My router"},
        {"entity": _hop(2, "latency"), "name": "ISP"},
        {"entity": "sensor.internet_health_internet_latency", "name": "Internet"},
    ]


async def test_graph_hours_applies_to_every_graph(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """graph_hours sets hours_to_show on each history graph."""
    await setup_entry()
    card = build_card_config(hass, CARD_OPTIONS_SCHEMA({"graph_hours": 48}))
    assert {part["hours_to_show"] for part in card["cards"] if part["type"] == "history-graph"} == {48}


# ┌────────────────────────────┬───────────────────────┬──────────────────────────┐
# │ setup                      │ card options          │ error key                │
# ├────────────────────────────┼───────────────────────┼──────────────────────────┤
# │ no entry                   │ {}                    │ not_set_up               │
# │ entry                      │ everything off        │ nothing_to_show          │
# └────────────────────────────┴───────────────────────┴──────────────────────────┘
ALL_OFF = {"include_status": False, "include_hops": False, **NO_GRAPHS}
# fmt: off
ERROR_CASES: list[tuple[bool, dict[str, Any], str]] = [
    (False, {},      "not_set_up"),
    (True,  ALL_OFF, "nothing_to_show"),
]
# fmt: on


@pytest.mark.parametrize("with_entry,card_options,key", ERROR_CASES, ids=[c[2] for c in ERROR_CASES])
async def test_layout_errors(
    hass: HomeAssistant, setup_entry: SetupEntry, with_entry: bool, card_options: dict[str, Any], key: str
) -> None:
    """No entry, or nothing to show, raises a translated validation error."""
    if with_entry:
        await setup_entry()
    with pytest.raises(ServiceValidationError) as err:
        build_card_config(hass, CARD_OPTIONS_SCHEMA(card_options))
    assert err.value.translation_key == key


# ┌──────────────────────────┬────────────────────────────────────┐
# │ options                  │ description                        │
# ├──────────────────────────┼────────────────────────────────────┤
# │ graph_hours 0            │ below range                        │
# │ graph_hours 169          │ above range                        │
# │ unknown key              │ typo is not silently ignored       │
# └──────────────────────────┴────────────────────────────────────┘
# fmt: off
INVALID_OPTIONS: list[tuple[dict[str, Any], str]] = [
    ({"graph_hours": 0},      "hours_below_range"),
    ({"graph_hours": 169},    "hours_above_range"),
    ({"include_graphs": True}, "unknown_key"),
]
# fmt: on


@pytest.mark.parametrize("options,desc", INVALID_OPTIONS, ids=[c[1] for c in INVALID_OPTIONS])
def test_schema_rejects_invalid_options(options: dict[str, Any], desc: str) -> None:
    """Out-of-range or unknown options fail validation."""
    with pytest.raises(probatio.Invalid):
        CARD_OPTIONS_SCHEMA(options)


async def test_action_returns_the_layout_as_yaml(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """The action's YAML parses back to the builder's dict."""
    await setup_entry()
    response = await hass.services.async_call(
        DOMAIN, SERVICE_GENERATE_DASHBOARD_CARD, {"include_jitter": False}, blocking=True, return_response=True
    )
    assert response is not None
    assert isinstance(response["yaml"], str)
    assert parse_yaml(response["yaml"]) == build_card_config(hass, CARD_OPTIONS_SCHEMA({"include_jitter": False}))


async def test_action_without_entry_raises(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """The action is registered at startup and fails clearly when nothing is set up."""
    entry = await setup_entry()
    await hass.config_entries.async_remove(entry.entry_id)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, SERVICE_GENERATE_DASHBOARD_CARD, {}, blocking=True, return_response=True)


async def test_websocket_command(
    hass: HomeAssistant, setup_entry: SetupEntry, hass_ws_client: WebSocketGenerator
) -> None:
    """The card's command returns the layout, a reason when there is none, and rejects bad options."""
    client = await hass_ws_client(hass)
    await setup_entry()

    await client.send_json_auto_id({"type": CARD_CONFIG_COMMAND})
    reply = await client.receive_json()
    assert reply["success"]
    assert reply["result"] == {"card": DEFAULT_CARD}

    await client.send_json_auto_id({"type": CARD_CONFIG_COMMAND, "options": ALL_OFF})
    reply = await client.receive_json()
    assert not reply["success"]
    assert reply["error"]["code"] == ERR_CARD_UNAVAILABLE
    assert reply["error"]["message"]

    await client.send_json_auto_id({"type": CARD_CONFIG_COMMAND, "options": {"graph_hours": 999}})
    reply = await client.receive_json()
    assert not reply["success"]
    assert reply["error"]["code"] == "invalid_format"


# ┌──────────────────────┬───────────────────────┬──────────────────────────────────────┐
# │ components loaded    │ serves the card       │ description                          │
# ├──────────────────────┼───────────────────────┼──────────────────────────────────────┤
# │ frontend + http      │ yes                   │ normal install                       │
# │ http only            │ no                    │ no frontend to load it into          │
# │ frontend only        │ no                    │ no http to serve it from             │
# │ neither              │ no                    │ headless install                     │
# └──────────────────────┴───────────────────────┴──────────────────────────────────────┘
# fmt: off
COMPONENT_CASES: list[tuple[set[str], bool, str]] = [
    ({"frontend", "http"}, True,  "normal_install"),
    ({"http"},             False, "no_frontend"),
    ({"frontend"},         False, "no_http"),
    (set(),                False, "headless"),
]
# fmt: on


def _hass_with(components: set[str]) -> MagicMock:
    """A hass double with *components* loaded and an awaitable static-path hook."""
    hass = MagicMock()
    hass.config.components = components
    hass.http.async_register_static_paths = AsyncMock()
    return hass


@pytest.mark.parametrize("components,serves,desc", COMPONENT_CASES, ids=[c[2] for c in COMPONENT_CASES])
async def test_register_card(components: set[str], serves: bool, desc: str) -> None:
    """The command is always registered; the module is served and loaded only with frontend and http."""
    hass = _hass_with(components)
    with (
        patch("homeassistant.components.websocket_api.async_register_command") as command,
        patch("homeassistant.components.frontend.add_extra_js_url") as add_url,
    ):
        await async_register_card(hass)
    command.assert_called_once()
    if not serves:
        hass.http.async_register_static_paths.assert_not_called()
        add_url.assert_not_called()
        return
    (config,) = hass.http.async_register_static_paths.call_args.args[0]
    assert config.url_path == CARD_URL_BASE
    assert Path(config.path) == FRONTEND
    assert (FRONTEND / CARD_MODULE).is_file()
    add_url.assert_called_once_with(hass, f"{CARD_URL_BASE}/{CARD_MODULE}?v={VERSION}")


async def test_register_card_failure_is_contained(caplog: pytest.LogCaptureFixture) -> None:
    """A registration error is logged, never raised: monitoring must still load."""
    hass = _hass_with({"frontend", "http"})
    hass.http.async_register_static_paths.side_effect = RuntimeError("boom")
    with patch("homeassistant.components.websocket_api.async_register_command"):
        await async_register_card(hass)
    assert "monitoring is unaffected" in caplog.text


FORM_FIELD = re.compile(r'\{ name: "(\w+)", default: ([\w.]+),')


def test_card_form_matches_schema() -> None:
    """The card's form lists every option with the schema's default."""
    source = (FRONTEND / CARD_MODULE).read_text(encoding="utf-8")
    form = {name: parse_yaml(default) for name, default in FORM_FIELD.findall(source)}
    assert form == CARD_OPTIONS_SCHEMA({})


# Bufferbloat gauge bands: Waveform's scale (R3), from each grade's lower bound. Success color up
# to B, error color past it: Waveform's "Anything worse than a B may affect video calls, gaming,
# and other real-time applications"; it publishes no colors. Only the grade gauge, which reads the
# larger increase as Waveform grades, carries the grade labels (HA shows a label instead of the value).
# fmt: off
BANDS: list[tuple[int, str, str]] = [
    (0,   "var(--success-color)", "A+"),
    (5,   "var(--success-color)", "A"),
    (30,  "var(--success-color)", "B"),
    (60,  "var(--error-color)",   "C"),
    (200, "var(--error-color)",   "D"),
    (400, "var(--error-color)",   "F"),
]
# fmt: on
# 0 to 100 ms: green up to B is 60% of the arc. D and F start past the end; their bands stay so a
# larger value is still labeled with its grade (HA labels by the real value, not the needle's).
GAUGE = {"type": "gauge", "min": 0, "max": 100, "needle": True}
SENSOR = "sensor.internet_health_speed_test_"


# A gauge shows an error for a state that is not a number, so each is shown only once measured:
# not before the first speed test (unknown), nor while its entity is unavailable.
NOT_MEASURED = ["unknown", "unavailable"]


def _gauge(key: str, name: str, *, labels: bool = False, **extra: str) -> dict[str, Any]:
    """One bufferbloat gauge as the card builds it, inside the card that hides it until measured."""
    segments = [{"from": f, "color": c, **({"label": g} if labels else {})} for f, c, g in BANDS]
    entity = f"{SENSOR}{key}"
    gauge = {**GAUGE, "entity": entity, "name": name, "segments": segments, **extra}
    condition = {"condition": "state", "entity": entity, "state_not": NOT_MEASURED}
    return {"type": "conditional", "conditions": [condition], "card": gauge}


GRADE_GAUGE = _gauge("bufferbloat_grade", "Bufferbloat", labels=True, attribute="latency_increase_ms", unit="ms")
DOWNLOAD_GAUGE = _gauge("download_latency_increase", "Download bufferbloat")
UPLOAD_GAUGE = _gauge("upload_latency_increase", "Upload bufferbloat")


RUN = "button.internet_health_run_speed_test"
RUN_CONFIRMATION = (
    "Run a speed test now? It uses your whole connection for about 20 seconds, "
    "and its data counts toward your speed test data budget."
)
RUN_BUTTON = {
    "type": "button",
    "entity": RUN,
    "name": "Run speed test",
    "show_state": False,
    "tap_action": {
        "action": "perform-action",
        "perform_action": "button.press",
        "target": {"entity_id": RUN},
        "confirmation": {"text": RUN_CONFIRMATION},
    },
}


async def test_speed_test_part_appears_with_a_backend(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """With a speed test service, the card adds readings, the grade gauge full width, the direction gauges side by
    side, and a throughput graph; off hides them."""
    await setup_entry(speed_test_backend="cloudflare")
    card = build_card_config(hass, CARD_OPTIONS_SCHEMA({}))
    speed, run, grade, directions, throughput = card["cards"][-5:]
    assert (speed["title"], speed["entities"][0], speed["entities"][-1]) == (
        "Speed test",
        {"entity": f"{SENSOR}download", "name": "Download"},
        {"entity": f"{SENSOR}data_used", "name": "Data used"},
    )
    # Its own button card, as Cable Modem Monitor's Restart: an entities row's button skips the
    # confirmation when its own Press is clicked.
    assert run == RUN_BUTTON
    # The gauges show the grade and the increases, so the list does not repeat them.
    listed = {row["entity"] for row in speed["entities"]}
    gauged = {f"{SENSOR}{key}" for key in ("bufferbloat_grade", "download_latency_increase", "upload_latency_increase")}
    assert not listed & gauged
    assert grade == GRADE_GAUGE
    assert directions == {"type": "horizontal-stack", "cards": [DOWNLOAD_GAUGE, UPLOAD_GAUGE]}
    assert throughput["entities"] == [
        {"entity": f"{SENSOR}download", "name": "Download"},
        {"entity": f"{SENSOR}upload", "name": "Upload"},
    ]
    hidden = build_card_config(hass, CARD_OPTIONS_SCHEMA({"include_speed_test": False}))
    assert len(hidden["cards"]) == len(card["cards"]) - 5


async def test_disabled_sensor_has_no_gauge(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """A gauge whose entity the user disabled is left out, as rows are."""
    entry = await setup_entry(speed_test_backend="cloudflare")
    registry = er.async_get(hass)
    for key in ("speed_test_bufferbloat_grade", "speed_test_upload_latency_increase"):
        disabled = entity_id(hass, "sensor", entry, key)
        assert disabled
        registry.async_update_entity(disabled, disabled_by=er.RegistryEntryDisabler.USER)
    card = build_card_config(hass, CARD_OPTIONS_SCHEMA({}))
    assert card["cards"][-2] == {"type": "horizontal-stack", "cards": [DOWNLOAD_GAUGE]}


async def test_card_import_failure_does_not_stop_monitoring(
    hass: HomeAssistant, setup_entry: SetupEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """If a release moves an HA piece the card imports, the card is skipped and IHM still loads."""
    real_import = builtins.__import__

    def moved(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "homeassistant.components.frontend":
            raise ImportError("moved in a future release")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", moved):
        await async_register_card(hass)
    assert "monitoring is unaffected" in caplog.text
    entry = await setup_entry()
    assert entry.state is ConfigEntryState.LOADED
