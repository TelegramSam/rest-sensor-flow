"""Shared fixtures and test data for json_sensor tests."""
import asyncio

import aiohttp
import pytest
from aioresponses import aioresponses as AioResponses
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.json_sensor.const import (
    CONF_HEADERS,
    CONF_PREFIX,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DOMAIN,
)

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

TEST_URL = "http://test.local/sensors"

# Full example payload — covers numeric, string, boolean, and dated sensors
# across two devices, with all optional sensor fields present on at least one.
FULL_PAYLOAD = {
    "devices": {
        "device_one": {
            "name": "Device One",
            "sensors": {
                "numeric_sensor": {
                    "state": 42.5,
                    "name": "Temperature",
                    "unit": "°C",
                    "device_class": "temperature",
                    "state_class": "measurement",
                    "icon": "mdi:thermometer",
                },
                "string_sensor": {
                    "state": "active",
                },
                "cumulative_sensor": {
                    "state": 1024.0,
                    "unit": "kWh",
                    "device_class": "energy",
                    "state_class": "total_increasing",
                },
            },
        },
        "device_two": {
            "name": "Device Two",
            "sensors": {
                "boolean_sensor": {
                    "state": True,
                },
                "dated_sensor": {
                    "state": "2026-01-01",
                    "device_class": "date",
                },
            },
        },
    }
}

# Minimal single-device payload used by tests that don't need both devices.
SINGLE_DEVICE_PAYLOAD = {
    "devices": {
        "device_one": {
            "name": "Device One",
            "sensors": {
                "numeric_sensor": {
                    "state": 42.5,
                    "unit": "°C",
                    "device_class": "temperature",
                    "state_class": "measurement",
                },
            },
        }
    }
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="session")
def _pre_warm_aiohttp_thread():
    """Spawn aiohttp's internal background thread before any test captures its
    thread baseline.  Without this, the first test to use aiohttp fails HA's
    verify_cleanup check because the thread appears to be new."""

    async def _touch():
        conn = aiohttp.TCPConnector()
        await conn.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_touch())
    finally:
        loop.close()


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of custom integrations under custom_components/."""
    yield


@pytest.fixture
def mock_aioclient():
    """Yield an aioresponses context that intercepts all aiohttp requests."""
    with AioResponses() as m:
        yield m


@pytest.fixture
def config_entry():
    """Return a MockConfigEntry with default test configuration."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test JSON Sensor",
        data={
            CONF_URL: TEST_URL,
            CONF_SCAN_INTERVAL: 60,
            CONF_PREFIX: "",
            CONF_HEADERS: {},
        },
        options={},
    )


@pytest.fixture
def config_entry_with_prefix():
    """Return a MockConfigEntry that uses a prefix."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="My Sensor",
        data={
            CONF_URL: TEST_URL,
            CONF_SCAN_INTERVAL: 60,
            CONF_PREFIX: "My Prefix",
            CONF_HEADERS: {},
        },
        options={},
    )
