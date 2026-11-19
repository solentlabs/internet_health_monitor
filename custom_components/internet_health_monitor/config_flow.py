"""Config and options flow for Internet Health Monitor."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
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

from .const import (
    CONF_DNS_SERVER,
    CONF_ENABLE_DNS_MONITORING,
    CONF_ENABLE_GATEWAY_MONITORING,
    CONF_HOP_OWNERSHIP,
    CONF_PING_COUNT,
    DEFAULT_DNS_SERVER,
    DEFAULT_PING_COUNT,
    DNS_SERVERS,
    DOMAIN,
    NAME,
    PING_COUNT_MAX,
    PING_COUNT_MIN,
)

# Field -> default when the user has never set it. One list for setup and
# options, so the two forms cannot drift.
DEFAULTS: dict[str, Any] = {
    CONF_ENABLE_GATEWAY_MONITORING: True,
    CONF_ENABLE_DNS_MONITORING: True,
    CONF_DNS_SERVER: DEFAULT_DNS_SERVER,
    CONF_PING_COUNT: DEFAULT_PING_COUNT,
    CONF_HOP_OWNERSHIP: False,
}


def build_schema(current: Mapping[str, Any]) -> vol.Schema:
    """Return the form, pre-filled from current values or DEFAULTS."""

    def default(key: str) -> Any:
        return current.get(key, DEFAULTS[key])

    return vol.Schema(
        {
            vol.Required(CONF_ENABLE_GATEWAY_MONITORING, default=default(CONF_ENABLE_GATEWAY_MONITORING)): (
                BooleanSelector()
            ),
            vol.Required(CONF_ENABLE_DNS_MONITORING, default=default(CONF_ENABLE_DNS_MONITORING)): BooleanSelector(),
            vol.Required(CONF_DNS_SERVER, default=default(CONF_DNS_SERVER)): SelectSelector(
                SelectSelectorConfig(
                    options=list(DNS_SERVERS),
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_DNS_SERVER,
                )
            ),
            vol.Required(CONF_PING_COUNT, default=default(CONF_PING_COUNT)): vol.All(
                NumberSelector(
                    NumberSelectorConfig(min=PING_COUNT_MIN, max=PING_COUNT_MAX, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Coerce(int),
            ),
            vol.Required(CONF_HOP_OWNERSHIP, default=default(CONF_HOP_OWNERSHIP)): BooleanSelector(),
        }
    )


class InternetHealthConfigFlow(ConfigFlow, domain=DOMAIN):
    """One entry per Home Assistant: it monitors this host's own path."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the settings, then create the entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title=NAME, data={}, options=user_input)
        return self.async_show_form(step_id="user", data_schema=build_schema({}))

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change the settings from the entry's Reconfigure menu, then reload."""
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            return self.async_update_reload_and_abort(entry, options=user_input)
        return self.async_show_form(step_id="reconfigure", data_schema=build_schema(entry.options))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> InternetHealthOptionsFlow:
        """Create the options flow."""
        return InternetHealthOptionsFlow()


class InternetHealthOptionsFlow(OptionsFlow):
    """Change settings; HA supplies self.config_entry (2024.11+)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the current settings, then save them."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(step_id="init", data_schema=build_schema(self.config_entry.options))
