"""Tests for Internet Health Monitor diagnostics platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import Mock

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.internet_health_monitor.const import DOMAIN, VERSION
from custom_components.internet_health_monitor.core.network_diagnostics import (
    HopInfo,
    HostEnvironment,
    NetworkDiagnostics,
    NetworkDiagnosticsResult,
)
from custom_components.internet_health_monitor.diagnostics import (
    async_get_config_entry_diagnostics,
)


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = Mock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.title = "Internet Health Monitor"
    entry.options = {
        "enable_gateway_monitoring": True,
        "enable_dns_monitoring": True,
        "scan_interval": 60,
        "dns_server": "auto",
        "ping_count": 3,
    }
    return entry


@pytest.fixture
def mock_diagnostics_result():
    """Create a mock diagnostics result."""
    return NetworkDiagnosticsResult(
        timestamp=1234567890.0,
        gateway_ip="192.168.1.1",
        gateway_reachable=True,
        gateway_latency_ms=5.5,
        gateway_jitter_ms=1.2,
        packet_loss_percent=0.0,
        packets_sent=3,
        packets_received=3,
        hops=[
            HopInfo(
                hop_number=1,
                ip="192.168.1.1",
                latency_ms=1.0,
                jitter_ms=0.2,
                packet_loss_percent=0.0,
                packets_sent=3,
                packets_received=3,
                reachable=True,
            ),
            HopInfo(
                hop_number=2,
                ip="10.0.0.1",
                latency_ms=15.0,
                jitter_ms=2.0,
                packet_loss_percent=0.0,
                packets_sent=3,
                packets_received=3,
                reachable=True,
            ),
            HopInfo(
                hop_number=3,
                ip="8.8.8.1",
                latency_ms=20.0,
                jitter_ms=1.5,
                packet_loss_percent=0.0,
                packets_sent=3,
                packets_received=3,
                reachable=True,
            ),
        ],
        dns_server="1.1.1.1",
        dns_success=True,
        dns_latency_ms=25.0,
        host_environment=HostEnvironment(connection_type="ethernet", interface_name="eth0"),
        trace_target="8.8.8.8",
    )


@pytest.fixture
def mock_coordinator(mock_diagnostics_result):
    """Create a mock coordinator."""
    coordinator = Mock(spec=DataUpdateCoordinator)
    coordinator.last_update_success = True
    coordinator.update_interval = timedelta(seconds=60)
    coordinator.data = mock_diagnostics_result
    return coordinator


@pytest.fixture
def mock_diagnostics_instance():
    """Create a mock NetworkDiagnostics instance."""
    from collections import deque

    diag = Mock(spec=NetworkDiagnostics)
    diag._gateway_detection_failed = False
    diag._hop_detection_failed = False
    diag._metadata_collected = True
    diag._gateway_latency_history = deque([5.0, 5.5, 6.0])
    return diag


@pytest.mark.asyncio
async def test_diagnostics_basic_structure(mock_config_entry, mock_coordinator, mock_diagnostics_instance):
    """Test basic diagnostics structure."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "diagnostics": mock_diagnostics_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Verify top-level structure
    assert "version" in diagnostics
    assert "config_entry" in diagnostics
    assert "coordinator" in diagnostics
    assert "network_data" in diagnostics
    assert "host_environment" in diagnostics
    assert "detection_state" in diagnostics


@pytest.mark.asyncio
async def test_diagnostics_version(mock_config_entry, mock_coordinator, mock_diagnostics_instance):
    """Test diagnostics includes version."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "diagnostics": mock_diagnostics_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    assert diagnostics["version"] == VERSION


@pytest.mark.asyncio
async def test_diagnostics_config_entry(mock_config_entry, mock_coordinator, mock_diagnostics_instance):
    """Test diagnostics config entry section."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "diagnostics": mock_diagnostics_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    config_entry = diagnostics["config_entry"]
    assert config_entry["entry_id"] == "test_entry"
    assert config_entry["title"] == "Internet Health Monitor"
    assert "options" in config_entry


@pytest.mark.asyncio
async def test_diagnostics_config_entry_options(mock_config_entry, mock_coordinator, mock_diagnostics_instance):
    """Test diagnostics includes config entry options."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "diagnostics": mock_diagnostics_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    options = diagnostics["config_entry"]["options"]
    assert options["enable_gateway_monitoring"] is True
    assert options["enable_dns_monitoring"] is True
    assert options["scan_interval"] == 60
    assert options["dns_server"] == "auto"
    assert options["ping_count"] == 3


@pytest.mark.asyncio
async def test_diagnostics_coordinator_info(mock_config_entry, mock_coordinator, mock_diagnostics_instance):
    """Test diagnostics coordinator section."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "diagnostics": mock_diagnostics_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    coordinator = diagnostics["coordinator"]
    assert coordinator["last_update_success"] is True
    assert "update_interval" in coordinator


@pytest.mark.asyncio
async def test_diagnostics_network_data(mock_config_entry, mock_coordinator, mock_diagnostics_instance):
    """Test diagnostics network data section."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "diagnostics": mock_diagnostics_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    network_data = diagnostics["network_data"]
    assert network_data["gateway_ip"] == "192.168.1.1"
    assert network_data["gateway_reachable"] is True
    assert network_data["gateway_latency_ms"] == 5.5
    assert network_data["gateway_jitter_ms"] == 1.2
    assert network_data["packet_loss_percent"] == 0.0
    assert network_data["trace_target"] == "8.8.8.8"
    assert network_data["dns_server"] == "1.1.1.1"
    assert network_data["dns_success"] is True
    assert network_data["dns_latency_ms"] == 25.0
    assert len(network_data["hops"]) == 3


@pytest.mark.asyncio
async def test_diagnostics_hops_data(mock_config_entry, mock_coordinator, mock_diagnostics_instance):
    """Test diagnostics hops data."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "diagnostics": mock_diagnostics_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    hops = diagnostics["network_data"]["hops"]
    assert len(hops) == 3

    # Check hop 1
    assert hops[0]["hop_number"] == 1
    assert hops[0]["ip"] == "192.168.1.1"
    assert hops[0]["latency_ms"] == 1.0
    assert hops[0]["typical_location"] == "gateway"

    # Check hop 2
    assert hops[1]["hop_number"] == 2
    assert hops[1]["ip"] == "10.0.0.1"
    assert hops[1]["typical_location"] == "isp"

    # Check hop 3
    assert hops[2]["hop_number"] == 3
    assert hops[2]["typical_location"] == "backbone"


@pytest.mark.asyncio
async def test_diagnostics_host_environment(mock_config_entry, mock_coordinator, mock_diagnostics_instance):
    """Test diagnostics host environment section."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "diagnostics": mock_diagnostics_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    host_env = diagnostics["host_environment"]
    assert host_env["connection_type"] == "ethernet"
    assert host_env["interface_name"] == "eth0"


@pytest.mark.asyncio
async def test_diagnostics_detection_state(mock_config_entry, mock_coordinator, mock_diagnostics_instance):
    """Test diagnostics detection state section."""
    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "diagnostics": mock_diagnostics_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    detection_state = diagnostics["detection_state"]
    assert detection_state["gateway_detection_failed"] is False
    assert detection_state["hop_detection_failed"] is False
    assert detection_state["metadata_collected"] is True
    assert detection_state["gateway_latency_history_size"] == 3


@pytest.mark.asyncio
async def test_diagnostics_no_coordinator_data(mock_config_entry, mock_diagnostics_instance):
    """Test diagnostics when coordinator has no data."""
    coordinator = Mock(spec=DataUpdateCoordinator)
    coordinator.last_update_success = False
    coordinator.update_interval = timedelta(seconds=60)
    coordinator.data = None

    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": coordinator,
                "diagnostics": mock_diagnostics_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    # Should still return structure with None values
    network_data = diagnostics["network_data"]
    assert network_data["gateway_ip"] is None
    assert network_data["gateway_reachable"] is None
    assert network_data["gateway_latency_ms"] is None
    assert network_data["hops"] == []


@pytest.mark.asyncio
async def test_diagnostics_gateway_detection_failed(mock_config_entry, mock_coordinator):
    """Test diagnostics when gateway detection failed."""
    from collections import deque

    diag_instance = Mock(spec=NetworkDiagnostics)
    diag_instance._gateway_detection_failed = True
    diag_instance._hop_detection_failed = False
    diag_instance._metadata_collected = False
    diag_instance._gateway_latency_history = deque()

    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "diagnostics": diag_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    detection_state = diagnostics["detection_state"]
    assert detection_state["gateway_detection_failed"] is True


@pytest.mark.asyncio
async def test_diagnostics_hop_detection_failed(mock_config_entry, mock_coordinator):
    """Test diagnostics when hop detection failed."""
    from collections import deque

    diag_instance = Mock(spec=NetworkDiagnostics)
    diag_instance._gateway_detection_failed = False
    diag_instance._hop_detection_failed = True
    diag_instance._metadata_collected = False
    diag_instance._gateway_latency_history = deque()

    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "diagnostics": diag_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    detection_state = diagnostics["detection_state"]
    assert detection_state["hop_detection_failed"] is True


@pytest.mark.asyncio
async def test_diagnostics_empty_latency_history(mock_config_entry, mock_coordinator):
    """Test diagnostics with empty latency history."""
    from collections import deque

    diag_instance = Mock(spec=NetworkDiagnostics)
    diag_instance._gateway_detection_failed = False
    diag_instance._hop_detection_failed = False
    diag_instance._metadata_collected = True
    diag_instance._gateway_latency_history = deque()

    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "diagnostics": diag_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    detection_state = diagnostics["detection_state"]
    assert detection_state["gateway_latency_history_size"] == 0


@pytest.mark.asyncio
async def test_diagnostics_large_latency_history(mock_config_entry, mock_coordinator):
    """Test diagnostics with large latency history."""
    from collections import deque

    diag_instance = Mock(spec=NetworkDiagnostics)
    diag_instance._gateway_detection_failed = False
    diag_instance._hop_detection_failed = False
    diag_instance._metadata_collected = True
    diag_instance._gateway_latency_history = deque(range(100))

    hass = Mock(spec=HomeAssistant)
    hass.data = {
        DOMAIN: {
            mock_config_entry.entry_id: {
                "coordinator": mock_coordinator,
                "diagnostics": diag_instance,
            }
        }
    }

    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    detection_state = diagnostics["detection_state"]
    assert detection_state["gateway_latency_history_size"] == 100
