"""Tests for JsonSensorCoordinator — fetch, validation, and error handling."""
import pytest
from aiohttp import ClientConnectionError, ClientError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.json_sensor.const import (
    CONF_HEADERS,
    CONF_PREFIX,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DOMAIN,
)
from custom_components.json_sensor.coordinator import JsonSensorCoordinator

from .conftest import FULL_PAYLOAD, TEST_URL

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_coordinator(hass, url=TEST_URL, headers=None, scan_interval=60):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: url,
            CONF_HEADERS: headers or {},
            CONF_SCAN_INTERVAL: scan_interval,
            CONF_PREFIX: "",
        },
        options={},
    )
    return JsonSensorCoordinator(hass, entry)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_successful_fetch_returns_devices(hass, mock_aioclient):
    mock_aioclient.get(TEST_URL, payload=FULL_PAYLOAD)

    coordinator = _make_coordinator(hass)
    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert isinstance(coordinator.data, dict)
    assert "device_one" in coordinator.data
    assert "device_two" in coordinator.data


async def test_returns_only_the_devices_dict(hass, mock_aioclient):
    """Coordinator strips the outer wrapper; callers receive the devices object."""
    mock_aioclient.get(TEST_URL, payload=FULL_PAYLOAD)

    coordinator = _make_coordinator(hass)
    await coordinator.async_refresh()

    # data is the *devices* dict, not the full payload
    assert "devices" not in coordinator.data


async def test_custom_headers_forwarded(hass, mock_aioclient):
    mock_aioclient.get(
        TEST_URL,
        payload=FULL_PAYLOAD,
        headers={"Authorization": "Bearer secret"},
    )

    coordinator = _make_coordinator(hass, headers={"Authorization": "Bearer secret"})
    await coordinator.async_refresh()

    assert coordinator.last_update_success


async def test_scan_interval_applied(hass, mock_aioclient):
    mock_aioclient.get(TEST_URL, payload=FULL_PAYLOAD)

    coordinator = _make_coordinator(hass, scan_interval=120)
    await coordinator.async_refresh()

    assert coordinator.update_interval.total_seconds() == 120


# ---------------------------------------------------------------------------
# HTTP / network errors
# ---------------------------------------------------------------------------


async def test_non_200_response_marks_update_failed(hass, mock_aioclient):
    mock_aioclient.get(TEST_URL, status=503)

    coordinator = _make_coordinator(hass)
    await coordinator.async_refresh()

    assert not coordinator.last_update_success


async def test_connection_error_marks_update_failed(hass, mock_aioclient):
    mock_aioclient.get(TEST_URL, exception=ClientConnectionError())

    coordinator = _make_coordinator(hass)
    await coordinator.async_refresh()

    assert not coordinator.last_update_success


async def test_timeout_marks_update_failed(hass, mock_aioclient):
    import asyncio

    mock_aioclient.get(TEST_URL, exception=asyncio.TimeoutError())

    coordinator = _make_coordinator(hass)
    await coordinator.async_refresh()

    assert not coordinator.last_update_success


# ---------------------------------------------------------------------------
# Payload validation errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_payload",
    [
        # Not a JSON object at the top level
        [],
        "a string",
        42,
        # Missing 'devices' key
        {"sensors": {}},
        {},
        # 'devices' is not an object
        {"devices": []},
        {"devices": "bad"},
        {"devices": None},
    ],
)
async def test_invalid_payload_marks_update_failed(hass, mock_aioclient, bad_payload):
    mock_aioclient.get(TEST_URL, payload=bad_payload)

    coordinator = _make_coordinator(hass)
    await coordinator.async_refresh()

    assert not coordinator.last_update_success


async def test_malformed_json_marks_update_failed(hass, mock_aioclient):
    mock_aioclient.get(TEST_URL, body="not json at all {{{{", content_type="application/json")

    coordinator = _make_coordinator(hass)
    await coordinator.async_refresh()

    assert not coordinator.last_update_success


# ---------------------------------------------------------------------------
# Recovery — coordinator becomes healthy again after a failure
# ---------------------------------------------------------------------------


async def test_recovers_after_error(hass, mock_aioclient):
    mock_aioclient.get(TEST_URL, status=500)
    mock_aioclient.get(TEST_URL, payload=FULL_PAYLOAD)

    coordinator = _make_coordinator(hass)

    await coordinator.async_refresh()
    assert not coordinator.last_update_success

    await coordinator.async_refresh()
    assert coordinator.last_update_success
    assert "device_one" in coordinator.data
