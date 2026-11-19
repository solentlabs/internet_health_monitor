"""Config and options flow for Internet Health Monitor."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, override

import probatio
from homeassistant.config_entries import SOURCE_RECONFIGURE, ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
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

from .const import (
    CONF_DNS_SERVER,
    CONF_ENABLE_DNS_MONITORING,
    CONF_ENABLE_GATEWAY_MONITORING,
    CONF_HOP_OWNERSHIP,
    CONF_MLAB_CONSENT,
    CONF_PING_COUNT,
    CONF_SPEED_TEST_BACKEND,
    CONF_SPEED_TEST_DAILY_LIMIT,
    CONF_SPEED_TEST_DATA_LIMIT,
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
    CONF_SPEED_TEST_BACKEND: SPEED_TEST_OFF,
    CONF_SPEED_TEST_DATA_LIMIT: timing.SPEED_TEST_DATA_LIMIT_MB_DEFAULT,
    CONF_SPEED_TEST_DAILY_LIMIT: timing.SPEED_TEST_DAILY_DEFAULT,
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
                )
            ),
            probatio.Required(CONF_PING_COUNT, default=default(CONF_PING_COUNT)): probatio.All(
                NumberSelector(
                    NumberSelectorConfig(min=PING_COUNT_MIN, max=PING_COUNT_MAX, step=1, mode=NumberSelectorMode.BOX)
                ),
                probatio.Coerce(int),
            ),
            probatio.Required(CONF_HOP_OWNERSHIP, default=default(CONF_HOP_OWNERSHIP)): BooleanSelector(),
            probatio.Required(CONF_SPEED_TEST_BACKEND, default=default(CONF_SPEED_TEST_BACKEND)): SelectSelector(
                SelectSelectorConfig(
                    options=SPEED_TEST_CHOICES,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_SPEED_TEST_BACKEND,
                )
            ),
            probatio.Required(CONF_SPEED_TEST_DATA_LIMIT, default=default(CONF_SPEED_TEST_DATA_LIMIT)): _box(
                timing.SPEED_TEST_DATA_LIMIT_MB_MIN, timing.SPEED_TEST_DATA_LIMIT_MB_MAX, 100, "MB"
            ),
            probatio.Required(CONF_SPEED_TEST_DAILY_LIMIT, default=default(CONF_SPEED_TEST_DAILY_LIMIT)): _box(
                timing.SPEED_TEST_DAILY_MIN, timing.SPEED_TEST_DAILY_MAX, 1
            ),
        }
    )


def with_consent(user_input: dict[str, Any], current: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    """The options to save, keeping consent already given, and whether M-Lab consent must still be asked."""
    options = dict(user_input)
    if current.get(CONF_MLAB_CONSENT):
        options[CONF_MLAB_CONSENT] = True
    return options, options[CONF_SPEED_TEST_BACKEND] == "mlab" and not options.get(CONF_MLAB_CONSENT)


class InternetHealthConfigFlow(ConfigFlow, domain=DOMAIN):
    """One entry per Home Assistant: it monitors this host's own path."""

    VERSION = 1

    def __init__(self) -> None:
        """Nothing is pending until the form is submitted."""
        self._pending: dict[str, Any] = {}

    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the settings, then create the entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return await self._async_submit(user_input, {})
        return self.async_show_form(step_id="user", data_schema=build_schema({}))

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change the settings from the entry's Reconfigure menu, then reload."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return await self._async_submit(user_input, entry.options)
        return self.async_show_form(step_id="reconfigure", data_schema=build_schema(entry.options))

    async def async_step_mlab_consent(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask before M-Lab is used: it publishes results with the user's IP address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_MLAB_CONSENT]:
                return self._async_finish({**self._pending, CONF_MLAB_CONSENT: True})
            errors["base"] = "mlab_consent_required"
        return self.async_show_form(step_id="mlab_consent", data_schema=CONSENT_SCHEMA, errors=errors)

    async def _async_submit(self, user_input: dict[str, Any], current: Mapping[str, Any]) -> ConfigFlowResult:
        """Save, or ask for M-Lab consent first."""
        options, ask = with_consent(user_input, current)
        if ask:
            self._pending = options
            return await self.async_step_mlab_consent()
        return self._async_finish(options)

    def _async_finish(self, options: dict[str, Any]) -> ConfigFlowResult:
        """Create the entry, or update it when reconfiguring."""
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(self._get_reconfigure_entry(), options=options)
        return self.async_create_entry(title=NAME, data={}, options=options)

    @override
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> InternetHealthOptionsFlow:
        """Create the options flow."""
        return InternetHealthOptionsFlow()


class InternetHealthOptionsFlow(OptionsFlow):
    """Change settings; HA supplies self.config_entry (2024.11+)."""

    def __init__(self) -> None:
        """Nothing is pending until the form is submitted."""
        self._pending: dict[str, Any] = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the current settings, then save them (asking M-Lab consent first if needed)."""
        if user_input is not None:
            options, ask = with_consent(user_input, self.config_entry.options)
            if ask:
                self._pending = options
                return await self.async_step_mlab_consent()
            return self.async_create_entry(data=options)
        return self.async_show_form(step_id="init", data_schema=build_schema(self.config_entry.options))

    async def async_step_mlab_consent(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask before M-Lab is used: it publishes results with the user's IP address."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input[CONF_MLAB_CONSENT]:
                return self.async_create_entry(data={**self._pending, CONF_MLAB_CONSENT: True})
            errors["base"] = "mlab_consent_required"
        return self.async_show_form(step_id="mlab_consent", data_schema=CONSENT_SCHEMA, errors=errors)
