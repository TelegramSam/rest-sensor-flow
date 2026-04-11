"""Tests for the config flow and options flow."""
import json
from unittest.mock import patch

import pytest
from aiohttp import ClientConnectionError
from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from custom_components.json_sensor.const import (
    CONF_HEADERS,
    CONF_PREFIX,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

from .conftest import FULL_PAYLOAD, TEST_URL

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_USER_INPUT = {
    CONF_URL: TEST_URL,
    "name": "My JSON Sensor",
    CONF_SCAN_INTERVAL: 30,
    CONF_PREFIX: "",
    CONF_HEADERS: "",
}


async def _init_flow(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


# ---------------------------------------------------------------------------
# Initial setup — happy path
# ---------------------------------------------------------------------------


async def test_user_step_shows_form(hass: HomeAssistant):
    result = await _init_flow(hass)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}


async def test_user_step_creates_entry(hass: HomeAssistant):
    with (
        patch("custom_components.json_sensor.config_flow._validate_connection", return_value=None),
        patch("custom_components.json_sensor.async_setup_entry", return_value=True),
    ):
        result = await _init_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], VALID_USER_INPUT
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "My JSON Sensor"
    assert result["data"][CONF_URL] == TEST_URL
    assert result["data"][CONF_SCAN_INTERVAL] == 30
    assert result["data"][CONF_PREFIX] == ""
    assert result["data"][CONF_HEADERS] == {}


async def test_user_step_default_name_when_blank(hass: HomeAssistant):
    with (
        patch("custom_components.json_sensor.config_flow._validate_connection", return_value=None),
        patch("custom_components.json_sensor.async_setup_entry", return_value=True),
    ):
        result = await _init_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**VALID_USER_INPUT, "name": ""}
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["title"] == "JSON Sensor"


# ---------------------------------------------------------------------------
# Initial setup — headers parsing
# ---------------------------------------------------------------------------


async def test_user_step_accepts_json_headers(hass: HomeAssistant):
    with (
        patch("custom_components.json_sensor.config_flow._validate_connection", return_value=None),
        patch("custom_components.json_sensor.async_setup_entry", return_value=True),
    ):
        result = await _init_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**VALID_USER_INPUT, CONF_HEADERS: '{"Authorization": "Bearer token123"}'},
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["data"][CONF_HEADERS] == {"Authorization": "Bearer token123"}


async def test_user_step_accepts_key_value_headers(hass: HomeAssistant):
    with (
        patch("custom_components.json_sensor.config_flow._validate_connection", return_value=None),
        patch("custom_components.json_sensor.async_setup_entry", return_value=True),
    ):
        result = await _init_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**VALID_USER_INPUT, CONF_HEADERS: "Authorization: Bearer token123\nX-Custom: value"},
        )
        await hass.async_block_till_done()

    assert result["type"] == "create_entry"
    assert result["data"][CONF_HEADERS] == {
        "Authorization": "Bearer token123",
        "X-Custom": "value",
    }


async def test_user_step_rejects_malformed_headers(hass: HomeAssistant, mock_aioclient):
    result = await _init_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**VALID_USER_INPUT, CONF_HEADERS: "this-is-not-valid"},
    )

    assert result["type"] == "form"
    assert result["errors"][CONF_HEADERS] == "invalid_headers"


# ---------------------------------------------------------------------------
# Initial setup — connection errors
# ---------------------------------------------------------------------------


async def test_user_step_cannot_connect(hass: HomeAssistant, mock_aioclient):
    mock_aioclient.get(TEST_URL, exception=ClientConnectionError())

    result = await _init_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_USER_INPUT
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_step_non_200_status(hass: HomeAssistant, mock_aioclient):
    mock_aioclient.get(TEST_URL, status=503)

    result = await _init_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_USER_INPUT
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_step_invalid_payload_missing_devices(
    hass: HomeAssistant, mock_aioclient
):
    mock_aioclient.get(TEST_URL, payload={"not_devices": {}})

    result = await _init_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_USER_INPUT
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_payload"


async def test_user_step_invalid_payload_devices_not_object(
    hass: HomeAssistant, mock_aioclient
):
    mock_aioclient.get(TEST_URL, payload={"devices": "bad"})

    result = await _init_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], VALID_USER_INPUT
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_payload"


# ---------------------------------------------------------------------------
# Options flow
# ---------------------------------------------------------------------------


async def test_options_flow_shows_current_values(
    hass: HomeAssistant, config_entry, mock_aioclient
):
    mock_aioclient.get(TEST_URL, payload=FULL_PAYLOAD)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    schema_keys = [str(k) for k in result["data_schema"].schema]
    assert CONF_URL in schema_keys
    assert CONF_SCAN_INTERVAL in schema_keys


async def test_options_flow_saves_new_values(
    hass: HomeAssistant, config_entry, mock_aioclient
):
    # Setup
    mock_aioclient.get(TEST_URL, payload=FULL_PAYLOAD)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    new_url = "http://new.local/sensors"
    mock_aioclient.get(new_url, payload=FULL_PAYLOAD)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_URL: new_url,
            CONF_SCAN_INTERVAL: 120,
            CONF_PREFIX: "lab",
            CONF_HEADERS: "",
        },
    )

    assert result["type"] == "create_entry"
    assert config_entry.options[CONF_URL] == new_url
    assert config_entry.options[CONF_SCAN_INTERVAL] == 120
    assert config_entry.options[CONF_PREFIX] == "lab"


async def test_options_flow_connection_error_shows_form(
    hass: HomeAssistant, config_entry, mock_aioclient
):
    mock_aioclient.get(TEST_URL, payload=FULL_PAYLOAD)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    bad_url = "http://bad.local/sensors"
    mock_aioclient.get(bad_url, exception=ClientConnectionError())

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_URL: bad_url,
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_PREFIX: "",
            CONF_HEADERS: "",
        },
    )

    assert result["type"] == "form"
    assert result["errors"]["base"] == "cannot_connect"
