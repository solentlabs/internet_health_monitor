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
)

from solentlabs.internet_health_monitor_core import timing
from solentlabs.internet_health_monitor_core.data_plan import automatic_limit, every_days, most_tests
from solentlabs.internet_health_monitor_core.speed_test import DataLimit, SpeedTestResult

from .const import (
    CONF_DNS_SERVER,
    CONF_ENABLE_DNS_MONITORING,
    CONF_ENABLE_GATEWAY_MONITORING,
    CONF_HOP_OWNERSHIP,
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
    DEFAULT_PING_COUNT,
    DNS_SERVERS,
    DOMAIN,
    NAME,
    PING_COUNT_MAX,
    PING_COUNT_MIN,
    SPEED_TEST_CHOICES,
    SPEED_TEST_OFF,
)

# Field -> default when the user has never set it. One list for setup and
# options, so the two forms cannot drift.
DEFAULTS: dict[str, Any] = {
    CONF_ENABLE_GATEWAY_MONITORING: True,
    CONF_ENABLE_DNS_MONITORING: True,
    CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    CONF_PING_COUNT: DEFAULT_PING_COUNT,
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


def build_schema(current: Mapping[str, Any]) -> probatio.Schema:
    """Return the form, pre-filled from current values or DEFAULTS."""

    def default(key: str) -> Any:
        value = current.get(key, DEFAULTS[key])
        if key == CONF_DNS_SERVER:
            # Older entries stored the address; show it as its named choice.
            value = next((name for name, address in DNS_SERVERS.items() if address == value), value)
        return value

    return probatio.Schema(
        {
            probatio.Required(CONF_ENABLE_GATEWAY_MONITORING, default=default(CONF_ENABLE_GATEWAY_MONITORING)): (
                BooleanSelector()
            ),
            probatio.Required(
                CONF_ENABLE_DNS_MONITORING, default=default(CONF_ENABLE_DNS_MONITORING)
            ): BooleanSelector(),
            probatio.Required(CONF_DNS_SERVER, default=default(CONF_DNS_SERVER)): SelectSelector(
                SelectSelectorConfig(
                    options=list(DNS_SERVERS),
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_DNS_SERVER,
                    custom_value=True,
                )
            ),
            probatio.Required(CONF_PING_COUNT, default=default(CONF_PING_COUNT)): probatio.All(
                NumberSelector(
                    NumberSelectorConfig(min=PING_COUNT_MIN, max=PING_COUNT_MAX, step=1, mode=NumberSelectorMode.BOX)
                ),
                probatio.Coerce(int),
            ),
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
    """Check the monitoring screen; a typed DNS server must be an IP address, and is saved trimmed."""
    server = user_input[CONF_DNS_SERVER] = str(user_input[CONF_DNS_SERVER]).strip()
    if server in DNS_SERVERS:
        return {}
    try:
        ipaddress.ip_address(server)
    except ValueError:
        return {CONF_DNS_SERVER: "invalid_dns_server"}
    return {}


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
