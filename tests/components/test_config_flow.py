"""Tests for the setup and options forms, run through HA's flow manager."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.internet_health_monitor.config_flow import (
    DEFAULTS,
    SPEED_TEST_DEFAULTS,
    build_schema,
    build_speed_test_schema,
)
from custom_components.internet_health_monitor.const import (
    CONF_DNS_SERVER,
    CONF_ENABLE_DNS_MONITORING,
    CONF_ENABLE_GATEWAY_MONITORING,
    CONF_HOP_OWNERSHIP,
    CONF_LONG_TERM_STATISTICS,
    CONF_PING_COUNT,
    CONF_SPEED_TEST_AUTOMATIC,
    CONF_SPEED_TEST_BACKEND,
    CONF_SPEED_TEST_BUDGET,
    CONF_SPEED_TEST_DAILY_LIMIT,
    CONF_SPEED_TEST_DATA_LIMIT,
    CONF_USAGE_TOTALS,
    DOMAIN,
    NAME,
)

from .conftest import SetupEntry

USER_INPUT: dict[str, Any] = {
    CONF_ENABLE_GATEWAY_MONITORING: True,
    CONF_ENABLE_DNS_MONITORING: False,
    CONF_DNS_SERVER: "cloudflare",
    CONF_PING_COUNT: 5,
    CONF_HOP_OWNERSHIP: True,
    CONF_USAGE_TOTALS: True,
    CONF_LONG_TERM_STATISTICS: True,
    CONF_SPEED_TEST_BACKEND: "cloudflare",
}
SPEED_INPUT: dict[str, Any] = {
    CONF_SPEED_TEST_AUTOMATIC: False,
    CONF_SPEED_TEST_DATA_LIMIT: 300,
    CONF_SPEED_TEST_DAILY_LIMIT: 2,
    CONF_SPEED_TEST_BUDGET: 50,
}
SAVED = {**USER_INPUT, **SPEED_INPUT}

# stored options -> form defaults for (dns server, ping count, hop ownership)
# fmt: off
DEFAULT_CASES = [
    ("never set", {},                                                    ("auto", 3, False)),
    ("stored",    {CONF_DNS_SERVER: "quad9", CONF_PING_COUNT: 2, CONF_HOP_OWNERSHIP: True},
                                                                         ("quad9", 2, True)),
    ("stored address", {CONF_DNS_SERVER: "9.9.9.9"},                     ("quad9", 3, False)),
]
# fmt: on


def _defaults(schema: Any) -> dict[str, Any]:
    """Form field -> default."""
    return {marker.schema: marker.default() for marker in schema.schema}


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """The form creates one entry, keyed to the domain, with the input as options."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result.get("type") is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert (result.get("type"), result.get("step_id")) == (FlowResultType.FORM, "speed_test")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], SPEED_INPUT)
    await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == NAME
    assert result.get("options") == SAVED
    created = result.get("result")
    assert created is not None
    assert created.unique_id == DOMAIN


async def test_second_entry_aborts(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """One host, one entry: a second setup is refused."""
    await setup_entry()
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_options_flow_saves(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """The options form saves the new settings on the entry."""
    entry = await setup_entry()
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result.get("type") is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(result["flow_id"], USER_INPUT)
    result = await hass.config_entries.options.async_configure(result["flow_id"], SPEED_INPUT)
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert dict(entry.options) == SAVED


@pytest.mark.parametrize(("description", "stored", "expected"), DEFAULT_CASES, ids=[c[0] for c in DEFAULT_CASES])
def test_form_defaults(description: str, stored: dict[str, Any], expected: tuple[str, int, bool]) -> None:
    """The form shows stored values, else DEFAULTS; hop ownership is off unless chosen."""
    defaults = _defaults(build_schema(stored))
    assert (defaults[CONF_DNS_SERVER], defaults[CONF_PING_COUNT], defaults[CONF_HOP_OWNERSHIP]) == expected


@pytest.mark.parametrize(
    ("schema", "defaults"),
    [(build_schema({}), DEFAULTS), (build_speed_test_schema({}), SPEED_TEST_DEFAULTS)],
    ids=["monitoring", "speed test"],
)
def test_form_fields_match_defaults(schema: Any, defaults: dict[str, Any]) -> None:
    """Every field on each screen has a default, and no field carries a stray argument (msg)."""
    assert {m.schema for m in schema.schema} == set(defaults)
    assert [m.schema for m in schema.schema if m.msg] == []


@pytest.mark.parametrize(("value", "valid"), [(1, True), (10, True), (0, False), (11, False)])
def test_ping_count_range(value: int, valid: bool) -> None:
    """Ping count accepts 1 to 10 and is stored as an int."""
    schema = build_schema({})
    data = {**DEFAULTS, CONF_PING_COUNT: float(value)}
    if valid:
        assert schema(data)[CONF_PING_COUNT] == value
        assert isinstance(schema(data)[CONF_PING_COUNT], int)
    else:
        with pytest.raises(Exception):  # noqa: B017 - voluptuous raises its own Invalid subclasses
            schema(data)


async def test_reconfigure_updates_and_reloads(
    hass: HomeAssistant, setup_entry: SetupEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Reconfigure shows the current settings, saves the new ones and reloads."""
    entry = await setup_entry(**{CONF_PING_COUNT: 2})
    result = await entry.start_reconfigure_flow(hass)
    assert result.get("type") is FlowResultType.FORM
    assert _defaults(result.get("data_schema"))[CONF_PING_COUNT] == 2

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], SPEED_INPUT)
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reconfigure_successful"
    assert dict(entry.options) == SAVED
    assert entry.runtime_data.diagnostics.config.ping_count == 5
    # HA 2026.12 stops reloading an entry that also has an update listener; IHM must not rely on one.
    assert "update listener" not in caplog.text


# ┌──────────────────────────┬────────┬──────────────────────────┐
# │ field                    │ value  │ valid                    │
# ├──────────────────────────┼────────┼──────────────────────────┤
# │ data limit               │ 100    │ yes (minimum)            │
# │ data limit               │ 10000  │ yes (maximum)            │
# │ data limit               │ 99     │ no                       │
# │ tests per day            │ 40     │ yes (M-Lab interactive)  │
# │ tests per day            │ 41     │ no                       │
# │ tests per day            │ 0      │ no                       │
# │ data budget              │ 0      │ yes (none)               │
# │ data budget              │ 10000  │ yes (maximum)            │
# │ data budget              │ -1     │ no                       │
# └──────────────────────────┴────────┴──────────────────────────┘
# fmt: off
LIMIT_CASES: list[tuple[str, int, bool]] = [
    (CONF_SPEED_TEST_DATA_LIMIT,  100,   True),
    (CONF_SPEED_TEST_DATA_LIMIT,  10000, True),
    (CONF_SPEED_TEST_DATA_LIMIT,  99,    False),
    (CONF_SPEED_TEST_DAILY_LIMIT, 40,    True),
    (CONF_SPEED_TEST_DAILY_LIMIT, 41,    False),
    (CONF_SPEED_TEST_DAILY_LIMIT, 0,     False),
    (CONF_SPEED_TEST_BUDGET,      0,     True),
    (CONF_SPEED_TEST_BUDGET,      10000, True),
    (CONF_SPEED_TEST_BUDGET,      -1,    False),
]
# fmt: on


@pytest.mark.parametrize(("field", "value", "valid"), LIMIT_CASES)
def test_speed_test_limit_ranges(field: str, value: int, valid: bool) -> None:
    """Speed test limits accept their ranges from Core's timing.py and are stored as ints."""
    schema = build_speed_test_schema({})
    data = {**SPEED_TEST_DEFAULTS, field: float(value)}
    if valid:
        assert schema(data)[field] == value
    else:
        with pytest.raises(Exception):  # noqa: B017 - probatio raises its own Invalid subclasses
            schema(data)


def test_speed_tests_default_off() -> None:
    """A new entry runs no speed tests."""
    assert DEFAULTS[CONF_SPEED_TEST_BACKEND] == "none"


async def test_no_service_skips_speed_test_screen(hass: HomeAssistant) -> None:
    """With no speed test service the setup is one screen."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], DEFAULTS)
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("options") == DEFAULTS


async def test_speed_test_screen_defaults_and_advice(hass: HomeAssistant) -> None:
    """The second screen turns the nightly test on at 500 MB and says what that costs in 30 days."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert _defaults(result.get("data_schema")) == {
        CONF_SPEED_TEST_AUTOMATIC: True,
        CONF_SPEED_TEST_DATA_LIMIT: 500,
        CONF_SPEED_TEST_DAILY_LIMIT: 4,
        CONF_SPEED_TEST_BUDGET: 0,
    }
    assert result.get("description_placeholders") == {"limit_mb": "500", "monthly_gb": "15"}


async def test_options_with_no_service_is_one_screen(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Options with the speed test service off save from the first screen, keeping the stored speed settings."""
    entry = await setup_entry(**SAVED)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_SPEED_TEST_BACKEND: "none"}
    )
    await hass.async_block_till_done()
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert dict(entry.options) == {**SAVED, CONF_SPEED_TEST_BACKEND: "none"}
