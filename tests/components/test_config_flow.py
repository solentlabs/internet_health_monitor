"""Tests for the setup and options forms, run through HA's flow manager."""

from __future__ import annotations

from dataclasses import asdict
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
    CONF_HOP_OWNERSHIP,
    CONF_INTERNET_REFERENCE,
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
from solentlabs.internet_health_monitor_core.speed_test import SpeedTestResult

from .conftest import SetupEntry


@pytest.fixture
def speed_test_result(hass_storage: dict[str, Any]) -> None:
    """A stored last result: a 1000/40 Mbit/s line."""
    last = SpeedTestResult("cloudflare", "s", 1000.0, 40.0, 10.0, 20.0, 30.0, 1300.0, 0.0)
    key = "internet_health_monitor.speed_test"
    hass_storage[key] = {"version": 1, "minor_version": 1, "key": key, "data": {"runs": [], "last": asdict(last)}}


USER_INPUT: dict[str, Any] = {
    CONF_DNS_SERVER: "cloudflare",
    CONF_PING_COUNT: 5,
    CONF_HOP_OWNERSHIP: True,
    CONF_INTERNET_REFERENCE: "quad9",
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


# DNS server typed into the list -> accepted. A server from the list, or any IPv4 or IPv6
# address (a Pi-hole, AdGuard Home, the router); never a name, which would need DNS to find DNS.
# fmt: off
DNS_CASES: list[tuple[str, bool]] = [
    ("quad9",            True),   # from the list
    ("192.168.1.5",      True),   # a Pi-hole on the LAN
    ("2606:4700::1111",  True),   # IPv6
    (" 192.168.1.5 ",    True),   # pasted with spaces
    ("pihole.local",     False),  # a name
    ("999.1.1.1",        False),  # not an address
    ("",                 False),
]
# fmt: on


@pytest.mark.parametrize(("value", "valid"), DNS_CASES)
async def test_dns_server_typed_address(hass: HomeAssistant, value: str, valid: bool) -> None:
    """Any IP address can be typed as the DNS server; anything else is an error on that field."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_DNS_SERVER: value, CONF_SPEED_TEST_BACKEND: "none"}
    )
    if valid:
        assert result.get("type") is FlowResultType.CREATE_ENTRY
        assert result.get("options", {})[CONF_DNS_SERVER] == value.strip()
    else:
        assert (result.get("step_id"), result.get("errors")) == ("user", {CONF_DNS_SERVER: "invalid_dns_server"})


# Internet reference typed into the list -> accepted: a provider from the list, Off, or a
# public IPv4 address, so it is past the ISP and on the measured path (ADR-014, ADR-015).
# fmt: off
REFERENCE_CASES: list[tuple[str, bool]] = [
    ("cloudflare",       True),   # from the list
    ("off",              True),
    ("8.8.4.4",          True),   # a public IPv4 address
    (" 8.8.4.4 ",        True),   # pasted with spaces
    ("192.168.1.5",      False),  # at home, not past the ISP
    ("100.64.0.1",       False),  # ISP shared space
    ("2606:4700::1111",  False),  # IPv6 (ADR-014)
    ("one.one.one.one",  False),  # a name
    ("",                 False),
]
# fmt: on


@pytest.mark.parametrize(("value", "valid"), REFERENCE_CASES)
async def test_internet_reference_typed_address(hass: HomeAssistant, value: str, valid: bool) -> None:
    """The internet reference is a listed provider, Off, or a typed public IPv4 address."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**USER_INPUT, CONF_INTERNET_REFERENCE: value, CONF_SPEED_TEST_BACKEND: "none"}
    )
    if valid:
        assert result.get("type") is FlowResultType.CREATE_ENTRY
        assert result.get("options", {})[CONF_INTERNET_REFERENCE] == value.strip()
    else:
        assert (result.get("step_id"), result.get("errors")) == (
            "user",
            {CONF_INTERNET_REFERENCE: "invalid_internet_reference"},
        )


def test_internet_reference_defaults_to_cloudflare() -> None:
    """A new install pings Cloudflare as its internet reference (ADR-015)."""
    assert _defaults(build_schema({}))[CONF_INTERNET_REFERENCE] == "cloudflare"


async def test_dns_server_checked_on_every_screen(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Configure and Reconfigure check a typed DNS server as setup does."""
    entry = await setup_entry()
    bad = {**USER_INPUT, CONF_DNS_SERVER: "pihole.local", CONF_SPEED_TEST_BACKEND: "none"}
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], bad)
    assert result.get("errors") == {CONF_DNS_SERVER: "invalid_dns_server"}
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], bad)
    assert result.get("errors") == {CONF_DNS_SERVER: "invalid_dns_server"}


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
# │ data limit               │ 0      │ yes (automatic)          │
# │ data limit               │ 100    │ yes                      │
# │ data limit               │ 10000  │ yes (maximum)            │
# │ data limit               │ -1     │ no                       │
# │ data limit               │ 10001  │ no                       │
# │ tests per day            │ 40     │ yes (M-Lab interactive)  │
# │ tests per day            │ 41     │ no                       │
# │ tests per day            │ 0      │ no                       │
# │ data budget              │ 0      │ yes (none)               │
# │ data budget              │ 10000  │ yes (maximum)            │
# │ data budget              │ -1     │ no                       │
# └──────────────────────────┴────────┴──────────────────────────┘
# fmt: off
LIMIT_CASES: list[tuple[str, int, bool]] = [
    (CONF_SPEED_TEST_DATA_LIMIT,  0,     True),
    (CONF_SPEED_TEST_DATA_LIMIT,  100,   True),
    (CONF_SPEED_TEST_DATA_LIMIT,  10000, True),
    (CONF_SPEED_TEST_DATA_LIMIT,  -1,    False),
    (CONF_SPEED_TEST_DATA_LIMIT,  10001, False),
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


async def test_speed_test_screen_defaults_and_working(hass: HomeAssistant) -> None:
    """The second screen turns automatic tests on with the automatic limit, and shows its working.

    No test has run: the first calibrates at 500 MB, and with no budget tests are weekly,
    so at most 5 in any 30 days.
    """
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert _defaults(result.get("data_schema")) == {
        CONF_SPEED_TEST_AUTOMATIC: True,
        CONF_SPEED_TEST_DATA_LIMIT: 0,
        CONF_SPEED_TEST_DAILY_LIMIT: 4,
        CONF_SPEED_TEST_BUDGET: 0,
    }
    assert result.get("description_placeholders") == {
        "last_test": "-",
        "limit_mb": "500",
        "every_days": "7",
        "monthly_gb": "2.5",
    }


async def test_working_follows_the_last_test_and_budget(
    hass: HomeAssistant, setup_entry: SetupEntry, speed_test_result: None
) -> None:
    """Options show the working from the last result: 1000/40 Mbit/s sizes 1640 MB; 10 GB holds 6, every 6 days."""
    entry = await setup_entry(**{**SAVED, CONF_SPEED_TEST_DATA_LIMIT: 0, CONF_SPEED_TEST_BUDGET: 10})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], USER_INPUT)
    assert result.get("description_placeholders") == {
        "last_test": "1000/40 Mbit/s",
        "limit_mb": "1640",
        "every_days": "6",
        "monthly_gb": "9.8",
    }


# (data limit, budget GB) -> the error on the data limit field
# fmt: off
FORM_ERROR_CASES: list[tuple[int, int, str]] = [
    (50,   0, "data_limit_too_small"),    # neither automatic (0) nor 100 or more
    (2000, 1, "data_limit_over_budget"),  # one test could use more than the whole budget
]
# fmt: on


@pytest.mark.parametrize(("limit", "budget", "error"), FORM_ERROR_CASES)
async def test_speed_test_screen_errors(hass: HomeAssistant, limit: int, budget: int, error: str) -> None:
    """A data limit the tests could never use is refused on the form, with the reason."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    form = {**SPEED_INPUT, CONF_SPEED_TEST_DATA_LIMIT: limit, CONF_SPEED_TEST_BUDGET: budget}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], form)
    assert (result.get("step_id"), result.get("errors")) == ("speed_test", {CONF_SPEED_TEST_DATA_LIMIT: error})


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
