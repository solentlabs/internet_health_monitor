"""Tests for the setup and options forms, run through HA's flow manager."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import probatio
import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.internet_health_monitor.config_flow import (
    CUSTOM_FIELDS,
    DEFAULTS,
    SPEED_TEST_DEFAULTS,
    build_schema,
    build_speed_test_schema,
)
from custom_components.internet_health_monitor.const import (
    CONF_DNS_SERVER,
    CONF_DNS_SERVER_CUSTOM,
    CONF_HOP_OWNERSHIP,
    CONF_INTERNET_REFERENCE,
    CONF_INTERNET_REFERENCE_CUSTOM,
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


FORM_MONITORING = build_schema({})


def _defaults(schema: Any) -> dict[str, Any]:
    """Form field -> default; the optional address boxes have none."""
    return {marker.schema: _default_of(marker) for marker in schema.schema if isinstance(marker, probatio.Required)}


def _default_of(marker: Any) -> Any:
    """A form field's default value."""
    default = marker.default
    return default() if callable(default) else None


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


# DNS server: the list says what is timed. "Custom address" uses the box below it: any IPv4
# or IPv6 address (a Pi-hole, AdGuard Home, the router), never a name, which would need DNS
# to find DNS. Any other choice ignores the box, so the list never says one thing while IHM
# does another.
# fmt: off
DNS_CASES: list[tuple[str, str | None, str | None]] = [
    # (choice,       typed address,      stored, or None for an error on the box)
    ("quad9",        None,               "quad9"),
    ("quad9",        "192.168.1.5",      "quad9"),          # an old address left in the box is ignored
    ("custom",       "192.168.1.5",      "192.168.1.5"),    # a Pi-hole on the LAN
    ("custom",       "2606:4700::1111",  "2606:4700::1111"),
    ("custom",       " 192.168.1.5 ",    "192.168.1.5"),    # pasted with spaces
    ("custom",       "pihole.local",     None),             # a name
    ("custom",       "999.1.1.1",        None),             # not an address
    ("custom",       "",                 None),             # Custom with nothing typed
    ("custom",       None,               None),
]
# fmt: on


@pytest.mark.parametrize(("choice", "typed", "stored"), DNS_CASES)
async def test_dns_server_choice_or_address(
    hass: HomeAssistant, choice: str, typed: str | None, stored: str | None
) -> None:
    """Custom address takes the box's address; any other choice ignores the box."""
    user_input = {**USER_INPUT, CONF_DNS_SERVER: choice, CONF_SPEED_TEST_BACKEND: "none"}
    if typed is not None:
        user_input[CONF_DNS_SERVER_CUSTOM] = typed
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
    if stored is not None:
        assert result.get("type") is FlowResultType.CREATE_ENTRY
        options = result.get("options", {})
        assert options[CONF_DNS_SERVER] == stored
        assert CONF_DNS_SERVER_CUSTOM not in options  # the box is part of the form, not the settings
    else:
        assert (result.get("step_id"), result.get("errors")) == (
            "user",
            {CONF_DNS_SERVER_CUSTOM: "invalid_dns_server"},
        )


# Internet reference: the list says what is pinged. "Custom address" uses the box: a public
# IPv4 address, so it is past the ISP and on the measured path (ADR-014, ADR-015). Any other
# choice ignores the box, so Off is always off (ADR-015's privacy switch).
# fmt: off
REFERENCE_CASES: list[tuple[str, str | None, str | None]] = [
    # (choice,       typed address,      stored, or None for an error on the box)
    ("cloudflare",   None,               "cloudflare"),
    ("off",          "8.8.4.4",          "off"),            # Off wins over an old address in the box
    ("google",       "8.8.4.4",          "google"),
    ("custom",       "8.8.4.4",          "8.8.4.4"),        # a public IPv4 address
    ("custom",       " 8.8.4.4 ",        "8.8.4.4"),        # pasted with spaces
    ("custom",       "192.168.1.5",      None),             # at home, not past the ISP
    ("custom",       "100.64.0.1",       None),             # ISP shared space
    ("custom",       "2606:4700::1111",  None),             # IPv6 (ADR-014)
    ("custom",       "one.one.one.one",  None),             # a name
    ("custom",       "",                 None),             # Custom with nothing typed
]
# fmt: on


@pytest.mark.parametrize(("choice", "typed", "stored"), REFERENCE_CASES)
async def test_internet_reference_choice_or_address(
    hass: HomeAssistant, choice: str, typed: str | None, stored: str | None
) -> None:
    """Custom address takes the box's public IPv4 address; any other choice, Off included, ignores the box."""
    user_input = {**USER_INPUT, CONF_INTERNET_REFERENCE: choice, CONF_SPEED_TEST_BACKEND: "none"}
    if typed is not None:
        user_input[CONF_INTERNET_REFERENCE_CUSTOM] = typed
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)
    if stored is not None:
        assert result.get("type") is FlowResultType.CREATE_ENTRY
        options = result.get("options", {})
        assert options[CONF_INTERNET_REFERENCE] == stored
        assert CONF_INTERNET_REFERENCE_CUSTOM not in options
    else:
        assert (result.get("step_id"), result.get("errors")) == (
            "user",
            {CONF_INTERNET_REFERENCE_CUSTOM: "invalid_internet_reference"},
        )


# Stored address -> what the form shows: a listed provider's address as its name in the
# list; any other address as Custom address, with the address in the box.
# fmt: off
PREFILL_CASES: list[tuple[str, str, str, str | None]] = [
    # (field,                   stored,          list shows,    box shows)
    (CONF_DNS_SERVER,           "quad9",         "quad9",       None),
    (CONF_DNS_SERVER,           "9.9.9.9",       "quad9",       None),
    (CONF_DNS_SERVER,           "192.168.1.5",   "custom",      "192.168.1.5"),
    (CONF_INTERNET_REFERENCE,   "8.8.8.8",       "google",      None),
    (CONF_INTERNET_REFERENCE,   "8.8.4.4",       "custom",      "8.8.4.4"),
]
# fmt: on


@pytest.mark.parametrize(("field", "stored", "listed", "boxed"), PREFILL_CASES)
def test_form_shows_a_stored_address(field: str, stored: str, listed: str, boxed: str | None) -> None:
    """The list shows names; an address the list does not name shows as Custom address, in its box."""
    markers = {m.schema: m for m in build_schema({field: stored}).schema}
    assert markers[field].default() == listed
    box = markers[CUSTOM_FIELDS[field]]
    assert (box.description or {}).get("suggested_value") == boxed


def test_internet_reference_defaults_to_cloudflare() -> None:
    """A new install pings Cloudflare as its internet reference (ADR-015)."""
    assert _defaults(build_schema({}))[CONF_INTERNET_REFERENCE] == "cloudflare"


async def test_dns_server_checked_on_every_screen(hass: HomeAssistant, setup_entry: SetupEntry) -> None:
    """Configure and Reconfigure check a typed DNS server as setup does."""
    entry = await setup_entry()
    bad = {
        **USER_INPUT,
        CONF_DNS_SERVER: "custom",
        CONF_DNS_SERVER_CUSTOM: "pihole.local",
        CONF_SPEED_TEST_BACKEND: "none",
    }
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], bad)
    assert result.get("errors") == {CONF_DNS_SERVER_CUSTOM: "invalid_dns_server"}
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], bad)
    assert result.get("errors") == {CONF_DNS_SERVER_CUSTOM: "invalid_dns_server"}


@pytest.mark.parametrize(("description", "stored", "expected"), DEFAULT_CASES, ids=[c[0] for c in DEFAULT_CASES])
def test_form_defaults(description: str, stored: dict[str, Any], expected: tuple[str, int, bool]) -> None:
    """The form shows stored values, else DEFAULTS; hop ownership is off unless chosen."""
    defaults = _defaults(build_schema(stored))
    assert (defaults[CONF_DNS_SERVER], defaults[CONF_PING_COUNT], defaults[CONF_HOP_OWNERSHIP]) == expected


@pytest.mark.parametrize(
    ("schema", "defaults"),
    [(FORM_MONITORING, DEFAULTS), (build_speed_test_schema({}), SPEED_TEST_DEFAULTS)],
    ids=["monitoring", "speed test"],
)
def test_form_fields_match_defaults(schema: Any, defaults: dict[str, Any]) -> None:
    """Every setting on each screen has a default, the only other fields are the address boxes, and none carries
    a stray argument (msg)."""
    required = {m.schema for m in schema.schema if isinstance(m, probatio.Required)}
    assert required == set(defaults)
    boxes = set(CUSTOM_FIELDS.values()) if schema is FORM_MONITORING else set()
    assert {m.schema for m in schema.schema} - required == boxes
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
