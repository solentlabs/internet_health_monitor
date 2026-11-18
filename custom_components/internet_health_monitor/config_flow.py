"""Config flow for Internet Health Monitor integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback

from .const import (
    CONF_DNS_SERVER,
    CONF_ENABLE_DNS_MONITORING,
    CONF_ENABLE_GATEWAY_MONITORING,
    CONF_PING_COUNT,
    CONF_SCAN_INTERVAL,
    DEFAULT_DNS_SERVER,
    DEFAULT_PING_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DNS_SERVERS,
    DOMAIN,
    NAME,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Internet Health Monitor."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        # Check if already configured
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title=NAME,
                data={},
                options=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLE_GATEWAY_MONITORING,
                        default=True,
                    ): bool,
                    vol.Required(
                        CONF_ENABLE_DNS_MONITORING,
                        default=True,
                    ): bool,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=DEFAULT_SCAN_INTERVAL,
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                    vol.Required(
                        CONF_DNS_SERVER,
                        default=DEFAULT_DNS_SERVER,
                    ): vol.In(DNS_SERVERS),
                    vol.Required(
                        CONF_PING_COUNT,
                        default=DEFAULT_PING_COUNT,
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Create the options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow; HA supplies self.config_entry (2024.11+)."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENABLE_GATEWAY_MONITORING,
                        default=options.get(CONF_ENABLE_GATEWAY_MONITORING, True),
                    ): bool,
                    vol.Required(
                        CONF_ENABLE_DNS_MONITORING,
                        default=options.get(CONF_ENABLE_DNS_MONITORING, True),
                    ): bool,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                    vol.Required(
                        CONF_DNS_SERVER,
                        default=options.get(CONF_DNS_SERVER, DEFAULT_DNS_SERVER),
                    ): vol.In(DNS_SERVERS),
                    vol.Required(
                        CONF_PING_COUNT,
                        default=options.get(CONF_PING_COUNT, DEFAULT_PING_COUNT),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                }
            ),
        )
