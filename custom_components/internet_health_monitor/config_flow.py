"""Config and options flow for Internet Health Monitor."""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from typing import Any, override

import probatio
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from solentlabs.internet_health_monitor_core import timing
from solentlabs.internet_health_monitor_core.data_plan import automatic_limit, every_days, most_tests
from solentlabs.internet_health_monitor_core.network_diagnostics import is_traceable
from solentlabs.internet_health_monitor_core.speed_test import DataLimit, SpeedTestResult

from .const import (
    CONF_DNS_SERVER,
    CONF_DNS_SERVER_CUSTOM,
    CONF_HOP_OWNERSHIP,
    CONF_INTERNET_REFERENCE,
    CONF_INTERNET_REFERENCE_CUSTOM,
    CONF_LONG_TERM_STATISTICS,
    CONF_MLAB_CONSENT,
    CONF_PING_COUNT,
    CONF_SPEED_TEST_AUTOMATIC,
    CONF_SPEED_TEST_BACKEND,
    CONF_SPEED_TEST_BUDGET,
    CONF_SPEED_TEST_DAILY_LIMIT,
    CONF_SPEED_TEST_DATA_LIMIT,
    CONF_USAGE_TOTALS,
    DEFAULT_DNS_SERVER,
    DEFAULT_INTERNET_REFERENCE,
    DEFAULT_PING_COUNT,
    DNS_SERVERS,
    DOMAIN,
    INTERNET_REFERENCES,
    NAME,
    PING_COUNT_MAX,
    PING_COUNT_MIN,
    SPEED_TEST_CHOICES,
    SPEED_TEST_OFF,
)

# Field -> default when the user has never set it. One list for setup and
# options, so the two forms cannot drift.
DEFAULTS: dict[str, Any] = {
    CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    CONF_PING_COUNT: DEFAULT_PING_COUNT,
    CONF_INTERNET_REFERENCE: DEFAULT_INTERNET_REFERENCE,
    CONF_HOP_OWNERSHIP: False,
    CONF_USAGE_TOTALS: False,
    CONF_LONG_TERM_STATISTICS: False,
    CONF_SPEED_TEST_BACKEND: SPEED_TEST_OFF,
}
# The second screen, shown only when a speed test service is chosen.
SPEED_TEST_DEFAULTS: dict[str, Any] = {
    CONF_SPEED_TEST_AUTOMATIC: True,
    CONF_SPEED_TEST_DATA_LIMIT: timing.SPEED_TEST_DATA_LIMIT_MB_AUTO,
    CONF_SPEED_TEST_DAILY_LIMIT: timing.SPEED_TEST_DAILY_DEFAULT,
    CONF_SPEED_TEST_BUDGET: timing.SPEED_TEST_BUDGET_GB_DEFAULT,
}

# M-Lab publishes every result with the user's IP address; its terms require informed consent (R9).
CONSENT_SCHEMA = probatio.Schema({probatio.Required(CONF_MLAB_CONSENT, default=False): BooleanSelector()})


def _box(minimum: int, maximum: int, step: int, unit: str | None = None) -> probatio.All[int]:
    """A whole-number box from *minimum* to *maximum*."""
    config = NumberSelectorConfig(min=minimum, max=maximum, step=step, mode=NumberSelectorMode.BOX)
    if unit:
        config["unit_of_measurement"] = unit
    return probatio.All(NumberSelector(config), probatio.Coerce(int))


# Each list says what is measured. Its "Custom address" choice takes the address in the box
# below it, which is stored in the list's place; any other choice ignores the box, so the list
# never says one thing while IHM does another, and Off is always off (ADR-015). A plain list
# shows its options' names; one that also took typing showed the stored word ("auto").
CUSTOM_CHOICE = "custom"
CUSTOM_FIELDS = {CONF_DNS_SERVER: CONF_DNS_SERVER_CUSTOM, CONF_INTERNET_REFERENCE: CONF_INTERNET_REFERENCE_CUSTOM}
_CHOICES: dict[str, Mapping[str, str | None]] = {
    CONF_DNS_SERVER: DNS_SERVERS,
    CONF_INTERNET_REFERENCE: INTERNET_REFERENCES,
}


def _split(field: str, current: Mapping[str, Any]) -> tuple[str, str | None]:
    """(list choice, box address) for a stored or typed value: a listed address shows as its name."""
    choices = _CHOICES[field]
    typed = current.get(CUSTOM_FIELDS[field])
    value = current.get(field, DEFAULTS[field])
    if value == CUSTOM_CHOICE or value in choices:
        return value, typed or None
    named = next((name for name, address in choices.items() if address == value), None)
    if named is not None:
        return named, typed or None
    return CUSTOM_CHOICE, typed or value


def build_schema(current: Mapping[str, Any]) -> probatio.Schema:
    """Return the form, pre-filled from current values or DEFAULTS."""

    def default(key: str) -> Any:
        return current.get(key, DEFAULTS[key])

    def choice_and_box(field: str) -> dict[Any, Any]:
        choice, address = _split(field, current)
        box = CUSTOM_FIELDS[field]
        marker = probatio.Optional(box, description={"suggested_value": address}) if address else probatio.Optional(box)
        return {
            probatio.Required(field, default=choice): SelectSelector(
                SelectSelectorConfig(
                    options=[*_CHOICES[field], CUSTOM_CHOICE], mode=SelectSelectorMode.DROPDOWN, translation_key=field
                )
            ),
            marker: TextSelector(),
        }

    return probatio.Schema(
        {
            **choice_and_box(CONF_DNS_SERVER),
            probatio.Required(CONF_PING_COUNT, default=default(CONF_PING_COUNT)): probatio.All(
                NumberSelector(
                    NumberSelectorConfig(min=PING_COUNT_MIN, max=PING_COUNT_MAX, step=1, mode=NumberSelectorMode.BOX)
                ),
                probatio.Coerce(int),
            ),
            **choice_and_box(CONF_INTERNET_REFERENCE),
            probatio.Required(CONF_HOP_OWNERSHIP, default=default(CONF_HOP_OWNERSHIP)): BooleanSelector(),
            probatio.Required(CONF_USAGE_TOTALS, default=default(CONF_USAGE_TOTALS)): BooleanSelector(),
            probatio.Required(CONF_LONG_TERM_STATISTICS, default=default(CONF_LONG_TERM_STATISTICS)): BooleanSelector(),
            probatio.Required(CONF_SPEED_TEST_BACKEND, default=default(CONF_SPEED_TEST_BACKEND)): SelectSelector(
                SelectSelectorConfig(
                    options=SPEED_TEST_CHOICES,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_SPEED_TEST_BACKEND,
                )
            ),
        }
    )


def build_speed_test_schema(current: Mapping[str, Any]) -> probatio.Schema:
    """Return the speed test screen, pre-filled from current values or SPEED_TEST_DEFAULTS."""

    def default(key: str) -> Any:
        return current.get(key, SPEED_TEST_DEFAULTS[key])

    return probatio.Schema(
        {
            probatio.Required(CONF_SPEED_TEST_AUTOMATIC, default=default(CONF_SPEED_TEST_AUTOMATIC)): BooleanSelector(),
            # 0 (automatic) or MIN to MAX; speed_test_errors refuses the gap between.
            probatio.Required(CONF_SPEED_TEST_DATA_LIMIT, default=default(CONF_SPEED_TEST_DATA_LIMIT)): _box(
                timing.SPEED_TEST_DATA_LIMIT_MB_AUTO, timing.SPEED_TEST_DATA_LIMIT_MB_MAX, 100, "MB"
            ),
            probatio.Required(CONF_SPEED_TEST_DAILY_LIMIT, default=default(CONF_SPEED_TEST_DAILY_LIMIT)): _box(
                timing.SPEED_TEST_DAILY_MIN, timing.SPEED_TEST_DAILY_MAX, 1
            ),
            probatio.Required(CONF_SPEED_TEST_BUDGET, default=default(CONF_SPEED_TEST_BUDGET)): _box(
                0, timing.SPEED_TEST_BUDGET_GB_MAX, 1, "GB"
            ),
        }
    )


def _number(value: float) -> str:
    """To 0.1, without a trailing .0."""
    return f"{round(value, 1):g}"


def speed_test_placeholders(current: Mapping[str, Any], last: SpeedTestResult | None) -> dict[str, str]:
    """The speed test screen's working (Core data_plan.py): from the last result, the limit per test,
    the days between automatic tests and the most they can use in 30 days."""
    limit_mb = current.get(CONF_SPEED_TEST_DATA_LIMIT, SPEED_TEST_DEFAULTS[CONF_SPEED_TEST_DATA_LIMIT])
    budget_gb = current.get(CONF_SPEED_TEST_BUDGET, SPEED_TEST_DEFAULTS[CONF_SPEED_TEST_BUDGET])
    if limit_mb == timing.SPEED_TEST_DATA_LIMIT_MB_AUTO:
        limit = automatic_limit(last, budget_gb)
    else:
        limit = DataLimit.even(limit_mb)
    days = every_days(limit, budget_gb)
    return {
        "last_test": f"{_number(last.download_mbps)}/{_number(last.upload_mbps)} Mbit/s" if last else "-",
        "limit_mb": str(limit.total_mb),
        "every_days": str(days) if days else "-",
        "monthly_gb": _number(most_tests(days) * limit.total_mb / 1000) if days else "-",
    }


def speed_test_errors(options: Mapping[str, Any]) -> dict[str, str]:
    """A data limit tests could never use: between automatic and the minimum, or larger than the budget."""
    limit_mb, budget_gb = options[CONF_SPEED_TEST_DATA_LIMIT], options[CONF_SPEED_TEST_BUDGET]
    if timing.SPEED_TEST_DATA_LIMIT_MB_AUTO < limit_mb < timing.SPEED_TEST_DATA_LIMIT_MB_MIN:
        return {CONF_SPEED_TEST_DATA_LIMIT: "data_limit_too_small"}
    if budget_gb and limit_mb > budget_gb * 1000:
        return {CONF_SPEED_TEST_DATA_LIMIT: "data_limit_over_budget"}
    return {}


def last_result(entry: ConfigEntry | None) -> SpeedTestResult | None:
    """The loaded entry's last speed test result, if it has one."""
    runtime = getattr(entry, "runtime_data", None) if entry else None
    speed_test = getattr(runtime, "speed_test", None)
    return speed_test.data if speed_test else None


def monitoring_errors(user_input: dict[str, Any]) -> dict[str, str]:
    """Check the monitoring screen; Custom address stores the box's address, any other choice ignores the box.

    A custom DNS server must be an IP address; a custom internet reference a public IPv4
    address, so it is past the ISP and on the measured path (ADR-014, ADR-015). On an
    error the box keeps what was typed, so the form shows it again.
    """
    checks = {
        CONF_DNS_SERVER: (_is_ip, "invalid_dns_server"),
        CONF_INTERNET_REFERENCE: (is_traceable, "invalid_internet_reference"),
    }
    errors: dict[str, str] = {}
    for field, (valid, error) in checks.items():
        box = CUSTOM_FIELDS[field]
        if user_input.get(field) != CUSTOM_CHOICE:
            user_input.pop(box, None)
            continue
        typed = str(user_input.get(box) or "").strip()
        if not valid(typed):
            errors[box] = error
            continue
        user_input.pop(box, None)
        user_input[field] = typed
    return errors


def _is_ip(value: str) -> bool:
    """Whether *value* is an IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def needs_consent(options: Mapping[str, Any]) -> bool:
    """M-Lab is chosen and consent was never given."""
    return options[CONF_SPEED_TEST_BACKEND] == "mlab" and not options.get(CONF_MLAB_CONSENT)


class InternetHealthConfigFlow(ConfigFlow, domain=DOMAIN):
    """One entry per Home Assistant: it monitors this host's own path."""

    VERSION = 1

    def __init__(self) -> None:
        """Nothing is pending until the first screen is submitted."""
        self._options: dict[str, Any] = {}

    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the monitoring settings; a chosen speed test service leads to its own screen."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None and not (errors := monitoring_errors(user_input)):
            self._options = dict(user_input)
            return await self._async_next()
        return self.async_show_form(step_id="user", data_schema=build_schema(user_input or {}), errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change the settings from the entry's Reconfigure menu, then reload."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None and not (errors := monitoring_errors(user_input)):
            self._options = {**entry.options, **user_input}
            return await self._async_next()
        return self.async_show_form(
            step_id="reconfigure", data_schema=build_schema({**entry.options, **(user_input or {})}), errors=errors
        )

    async def async_step_speed_test(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """When tests run and how much data they may use."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._options.update(user_input)
            if not (errors := speed_test_errors(self._options)):
                if needs_consent(self._options):
                    return await self.async_step_mlab_consent()
                return self._async_finish()
        entry = self._get_reconfigure_entry() if self.source == SOURCE_RECONFIGURE else None
        return self.async_show_form(
            step_id="speed_test",
            data_schema=build_speed_test_schema(self._options),
            description_placeholders=speed_test_placeholders(self._options, last_result(entry)),
            errors=errors,
        )

    async def async_step_mlab_consent(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask before M-Lab is used: it publishes results with the user's IP address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_MLAB_CONSENT]:
                self._options[CONF_MLAB_CONSENT] = True
                return self._async_finish()
            errors["base"] = "mlab_consent_required"
        return self.async_show_form(step_id="mlab_consent", data_schema=CONSENT_SCHEMA, errors=errors)

    async def _async_next(self) -> ConfigFlowResult:
        """The speed test screen if a service is chosen, else save."""
        if self._options[CONF_SPEED_TEST_BACKEND] != SPEED_TEST_OFF:
            return await self.async_step_speed_test()
        return self._async_finish()

    def _async_finish(self) -> ConfigFlowResult:
        """Create the entry, or update it when reconfiguring."""
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(self._get_reconfigure_entry(), options=self._options)
        return self.async_create_entry(title=NAME, data={}, options=self._options)

    @override
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> InternetHealthOptionsFlow:
        """Create the options flow."""
        return InternetHealthOptionsFlow()


class InternetHealthOptionsFlow(OptionsFlowWithReload):
    """Change settings; HA supplies self.config_entry and reloads the entry on save."""

    def __init__(self) -> None:
        """Nothing is pending until the first screen is submitted."""
        self._options: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the current settings; a chosen speed test service leads to its own screen."""
        errors: dict[str, str] = {}
        if user_input is not None and not (errors := monitoring_errors(user_input)):
            self._options = {**self.config_entry.options, **user_input}
            if self._options[CONF_SPEED_TEST_BACKEND] != SPEED_TEST_OFF:
                return await self.async_step_speed_test()
            return self.async_create_entry(data=self._options)
        return self.async_show_form(
            step_id="init", data_schema=build_schema({**self.config_entry.options, **(user_input or {})}), errors=errors
        )

    async def async_step_speed_test(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """When tests run and how much data they may use."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._options.update(user_input)
            if not (errors := speed_test_errors(self._options)):
                if needs_consent(self._options):
                    return await self.async_step_mlab_consent()
                return self.async_create_entry(data=self._options)
        return self.async_show_form(
            step_id="speed_test",
            data_schema=build_speed_test_schema(self._options),
            description_placeholders=speed_test_placeholders(self._options, last_result(self.config_entry)),
            errors=errors,
        )

    async def async_step_mlab_consent(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask before M-Lab is used: it publishes results with the user's IP address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_MLAB_CONSENT]:
                return self.async_create_entry(data={**self._options, CONF_MLAB_CONSENT: True})
            errors["base"] = "mlab_consent_required"
        return self.async_show_form(step_id="mlab_consent", data_schema=CONSENT_SCHEMA, errors=errors)
