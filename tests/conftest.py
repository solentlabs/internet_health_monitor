"""Pytest configuration for HA Network Diagnostics tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def mock_gateway_ip() -> str:
    """Return a mock gateway IP."""
    return "192.168.1.1"


@pytest.fixture
def mock_isp_hop_ip() -> str:
    """Return a mock ISP hop IP."""
    return "10.0.0.1"


@pytest.fixture
def mock_dns_server() -> str:
    """Return a mock DNS server."""
    return "1.1.1.1"
