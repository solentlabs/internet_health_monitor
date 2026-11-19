"""Diagnostics support for Internet Health Monitor."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VERSION


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    diagnostics_instance = data["diagnostics"]

    result = coordinator.data

    # Build hop data
    hops_data = []
    if result and result.hops:
        for hop in result.hops:
            hop_data = {
                "hop_number": hop.hop_number,
                "ip": hop.ip,
                "hostname": hop.hostname,
                "latency_ms": hop.latency_ms,
                "jitter_ms": hop.jitter_ms,
                "reachable": hop.reachable,
                "typical_location": hop.typical_location,
            }
            hops_data.append(hop_data)

    # Build host environment data
    host_env_data = None
    if result and result.host_environment:
        host_env_data = {
            "connection_type": result.host_environment.connection_type,
            "interface_name": result.host_environment.interface_name,
            "container_type": result.host_environment.container_type,
            "ha_install_type": result.host_environment.ha_install_type,
        }

    return {
        "version": VERSION,
        "config_entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval": str(coordinator.update_interval),
        },
        "network_data": {
            "gateway_ip": result.gateway_ip if result else None,
            "gateway_reachable": result.gateway_reachable if result else None,
            "gateway_latency_ms": result.gateway_latency_ms if result else None,
            "gateway_jitter_ms": result.gateway_jitter_ms if result else None,
            "packet_loss_percent": result.packet_loss_percent if result else None,
            "trace_target": result.trace_target if result else None,
            "hops": hops_data,
            "dns_server": result.dns_server if result else None,
            "dns_success": result.dns_success if result else None,
            "dns_latency_ms": result.dns_latency_ms if result else None,
        },
        "host_environment": host_env_data,
        "detection_state": {
            "gateway_detection_failed": diagnostics_instance._gateway_detection_failed,
            "hop_detection_failed": diagnostics_instance._hop_detection_failed,
            "hostnames_collected": diagnostics_instance._hostnames_collected,
            "gateway_latency_history_size": len(diagnostics_instance._gateway_latency_history),
        },
    }
