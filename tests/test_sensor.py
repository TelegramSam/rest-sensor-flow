"""Tests for the sensor platform — entity creation, states, and dynamic discovery."""
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.json_sensor.const import DOMAIN

from .conftest import FULL_PAYLOAD, SINGLE_DEVICE_PAYLOAD, TEST_URL

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _setup(hass: HomeAssistant, config_entry, mock_aioclient, payload=None):
    """Add the config entry to hass, mock one fetch, and complete setup."""
    mock_aioclient.get(TEST_URL, payload=payload or FULL_PAYLOAD)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def _refresh(hass: HomeAssistant, config_entry, mock_aioclient, payload):
    """Trigger a coordinator refresh with a new mocked payload."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    mock_aioclient.get(TEST_URL, payload=payload)
    await coordinator.async_refresh()
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# Entity creation
# ---------------------------------------------------------------------------


async def test_creates_all_entities_from_payload(hass, config_entry, mock_aioclient):
    await _setup(hass, config_entry, mock_aioclient)

    # FULL_PAYLOAD has 3 sensors in device_one and 2 in device_two
    assert hass.states.get("sensor.device_one_numeric_sensor") is not None
    assert hass.states.get("sensor.device_one_string_sensor") is not None
    assert hass.states.get("sensor.device_one_cumulative_sensor") is not None
    assert hass.states.get("sensor.device_two_boolean_sensor") is not None
    assert hass.states.get("sensor.device_two_dated_sensor") is not None


async def test_entity_unique_ids_match_spec(hass, config_entry, mock_aioclient):
    await _setup(hass, config_entry, mock_aioclient)

    ent_reg = er.async_get(hass)
    entry_id = config_entry.entry_id

    entity = ent_reg.async_get("sensor.device_one_numeric_sensor")
    assert entity is not None
    assert entity.unique_id == f"{entry_id}__device_one__numeric_sensor"

    entity = ent_reg.async_get("sensor.device_two_boolean_sensor")
    assert entity is not None
    assert entity.unique_id == f"{entry_id}__device_two__boolean_sensor"


async def test_device_created_in_device_registry(hass, config_entry, mock_aioclient):
    await _setup(hass, config_entry, mock_aioclient)

    dev_reg = dr.async_get(hass)
    entry_id = config_entry.entry_id

    device = dev_reg.async_get_device({(DOMAIN, f"{entry_id}__device_one")})
    assert device is not None
    assert device.name == "Device One"

    device = dev_reg.async_get_device({(DOMAIN, f"{entry_id}__device_two")})
    assert device is not None
    assert device.name == "Device Two"


# ---------------------------------------------------------------------------
# Entity name resolution
# ---------------------------------------------------------------------------


async def test_sensor_name_from_payload_name_field(hass, config_entry, mock_aioclient):
    """When the payload provides a 'name', use it."""
    await _setup(hass, config_entry, mock_aioclient)

    ent_reg = er.async_get(hass)
    entity = ent_reg.async_get("sensor.device_one_numeric_sensor")
    # FULL_PAYLOAD sets name: "Temperature" on this sensor
    assert entity.original_name == "Temperature"


async def test_sensor_name_defaults_to_title_cased_key(
    hass, config_entry, mock_aioclient
):
    """When the payload omits 'name', fall back to title-cased sensor key."""
    await _setup(hass, config_entry, mock_aioclient)

    ent_reg = er.async_get(hass)
    # FULL_PAYLOAD's string_sensor has no 'name' field
    entity = ent_reg.async_get("sensor.device_one_string_sensor")
    assert entity.original_name == "String Sensor"


async def test_device_name_defaults_to_title_cased_key(
    hass, config_entry, mock_aioclient
):
    """Device name falls back to title-cased key when omitted from payload."""
    payload = {
        "devices": {
            "my_device": {
                # no 'name' key
                "sensors": {"temp": {"state": 20.0}},
            }
        }
    }
    await _setup(hass, config_entry, mock_aioclient, payload=payload)

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(
        {(DOMAIN, f"{config_entry.entry_id}__my_device")}
    )
    assert device.name == "My Device"


# ---------------------------------------------------------------------------
# State values
# ---------------------------------------------------------------------------


async def test_numeric_state(hass, config_entry, mock_aioclient):
    await _setup(hass, config_entry, mock_aioclient)

    state = hass.states.get("sensor.device_one_numeric_sensor")
    assert state.state == "42.5"


async def test_string_state(hass, config_entry, mock_aioclient):
    await _setup(hass, config_entry, mock_aioclient)

    state = hass.states.get("sensor.device_one_string_sensor")
    assert state.state == "active"


@pytest.mark.parametrize(
    "boolean_value, expected_state",
    [
        (True, "true"),
        (False, "false"),
    ],
)
async def test_boolean_state_serialized_to_string(
    hass, config_entry, mock_aioclient, boolean_value, expected_state
):
    payload = {
        "devices": {
            "device_one": {
                "sensors": {"flag": {"state": boolean_value}},
            }
        }
    }
    await _setup(hass, config_entry, mock_aioclient, payload=payload)

    state = hass.states.get("sensor.device_one_flag")
    assert state.state == expected_state


async def test_date_string_state(hass, config_entry, mock_aioclient):
    await _setup(hass, config_entry, mock_aioclient)

    state = hass.states.get("sensor.device_two_dated_sensor")
    assert state.state == "2026-01-01"


# ---------------------------------------------------------------------------
# Sensor metadata pass-through
# ---------------------------------------------------------------------------


async def test_unit_of_measurement(hass, config_entry, mock_aioclient):
    await _setup(hass, config_entry, mock_aioclient)

    state = hass.states.get("sensor.device_one_numeric_sensor")
    assert state.attributes.get("unit_of_measurement") == "°C"


async def test_device_class(hass, config_entry, mock_aioclient):
    await _setup(hass, config_entry, mock_aioclient)

    state = hass.states.get("sensor.device_one_numeric_sensor")
    assert state.attributes.get("device_class") == "temperature"


async def test_state_class(hass, config_entry, mock_aioclient):
    await _setup(hass, config_entry, mock_aioclient)

    state = hass.states.get("sensor.device_one_numeric_sensor")
    assert state.attributes.get("state_class") == "measurement"


async def test_icon(hass, config_entry, mock_aioclient):
    await _setup(hass, config_entry, mock_aioclient)

    state = hass.states.get("sensor.device_one_numeric_sensor")
    assert state.attributes.get("icon") == "mdi:thermometer"


async def test_sensor_without_optional_metadata(hass, config_entry, mock_aioclient):
    """Sensors that omit unit/device_class/state_class/icon produce no attributes."""
    await _setup(hass, config_entry, mock_aioclient)

    state = hass.states.get("sensor.device_one_string_sensor")
    assert state.attributes.get("unit_of_measurement") is None
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("state_class") is None
    assert state.attributes.get("icon") is None


# ---------------------------------------------------------------------------
# Unavailability
# ---------------------------------------------------------------------------


async def test_entity_unavailable_when_coordinator_fails(
    hass, config_entry, mock_aioclient
):
    await _setup(hass, config_entry, mock_aioclient)

    # Force a failing poll
    mock_aioclient.get(TEST_URL, status=503)
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.device_one_numeric_sensor")
    assert state.state == "unavailable"


async def test_entity_unavailable_when_device_key_absent(
    hass, config_entry, mock_aioclient
):
    await _setup(hass, config_entry, mock_aioclient)

    # Second poll drops device_two entirely
    payload_without_device_two = {
        "devices": {"device_one": FULL_PAYLOAD["devices"]["device_one"]}
    }
    await _refresh(hass, config_entry, mock_aioclient, payload_without_device_two)

    state = hass.states.get("sensor.device_two_boolean_sensor")
    assert state.state == "unavailable"


async def test_entity_unavailable_when_sensor_key_absent(
    hass, config_entry, mock_aioclient
):
    await _setup(hass, config_entry, mock_aioclient)

    # Second poll removes boolean_sensor from device_two
    payload = {
        "devices": {
            "device_one": FULL_PAYLOAD["devices"]["device_one"],
            "device_two": {
                "name": "Device Two",
                "sensors": {
                    # boolean_sensor is gone; dated_sensor remains
                    "dated_sensor": {"state": "2026-06-01", "device_class": "date"},
                },
            },
        }
    }
    await _refresh(hass, config_entry, mock_aioclient, payload)

    assert hass.states.get("sensor.device_two_boolean_sensor").state == "unavailable"
    assert hass.states.get("sensor.device_two_dated_sensor").state == "2026-06-01"


async def test_entity_unavailable_when_state_is_null(
    hass, config_entry, mock_aioclient
):
    payload = {
        "devices": {
            "device_one": {
                "sensors": {"null_sensor": {"state": None}},
            }
        }
    }
    await _setup(hass, config_entry, mock_aioclient, payload=payload)

    state = hass.states.get("sensor.device_one_null_sensor")
    assert state.state == "unavailable"


async def test_entities_recover_after_coordinator_error(
    hass, config_entry, mock_aioclient
):
    await _setup(hass, config_entry, mock_aioclient)

    # Fail
    mock_aioclient.get(TEST_URL, status=500)
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.device_one_numeric_sensor").state == "unavailable"

    # Recover
    await _refresh(hass, config_entry, mock_aioclient, FULL_PAYLOAD)
    assert hass.states.get("sensor.device_one_numeric_sensor").state == "42.5"


# ---------------------------------------------------------------------------
# Dynamic entity discovery
# ---------------------------------------------------------------------------


async def test_new_device_key_creates_entity_on_next_poll(
    hass, config_entry, mock_aioclient
):
    """A device key absent on first poll but present on second is auto-created."""
    await _setup(hass, config_entry, mock_aioclient, payload=SINGLE_DEVICE_PAYLOAD)

    assert hass.states.get("sensor.device_two_boolean_sensor") is None

    await _refresh(hass, config_entry, mock_aioclient, FULL_PAYLOAD)

    assert hass.states.get("sensor.device_two_boolean_sensor") is not None
    assert hass.states.get("sensor.device_two_boolean_sensor").state == "true"


async def test_new_sensor_key_creates_entity_on_next_poll(
    hass, config_entry, mock_aioclient
):
    """A sensor key that appears mid-run is auto-created without restart."""
    initial = {
        "devices": {
            "device_one": {
                "name": "Device One",
                "sensors": {
                    "numeric_sensor": {"state": 10.0, "unit": "°C"},
                },
            }
        }
    }
    await _setup(hass, config_entry, mock_aioclient, payload=initial)

    assert hass.states.get("sensor.device_one_new_sensor") is None

    updated = {
        "devices": {
            "device_one": {
                "name": "Device One",
                "sensors": {
                    "numeric_sensor": {"state": 10.0, "unit": "°C"},
                    "new_sensor": {"state": "hello"},
                },
            }
        }
    }
    await _refresh(hass, config_entry, mock_aioclient, updated)

    state = hass.states.get("sensor.device_one_new_sensor")
    assert state is not None
    assert state.state == "hello"


# ---------------------------------------------------------------------------
# Prefix handling
# ---------------------------------------------------------------------------


async def test_prefix_applied_to_entity_id(
    hass, config_entry_with_prefix, mock_aioclient
):
    await _setup(hass, config_entry_with_prefix, mock_aioclient)

    # prefix "My Prefix" → "my_prefix"
    assert hass.states.get("sensor.my_prefix_device_one_numeric_sensor") is not None


async def test_prefix_applied_to_device_name(
    hass, config_entry_with_prefix, mock_aioclient
):
    await _setup(hass, config_entry_with_prefix, mock_aioclient)

    dev_reg = dr.async_get(hass)
    entry_id = config_entry_with_prefix.entry_id
    device = dev_reg.async_get_device(
        {(DOMAIN, f"{entry_id}__my_prefix__device_one")}
    )
    assert device is not None
    assert device.name == "My Prefix Device One"


async def test_prefix_included_in_unique_id(
    hass, config_entry_with_prefix, mock_aioclient
):
    await _setup(hass, config_entry_with_prefix, mock_aioclient)

    ent_reg = er.async_get(hass)
    entry_id = config_entry_with_prefix.entry_id

    entity = ent_reg.async_get("sensor.my_prefix_device_one_numeric_sensor")
    assert entity is not None
    assert entity.unique_id == f"{entry_id}__my_prefix__device_one__numeric_sensor"


async def test_no_prefix_entity_id_has_no_prefix(hass, config_entry, mock_aioclient):
    await _setup(hass, config_entry, mock_aioclient)

    # Entity ID must not contain any leading underscore or extra segment
    assert hass.states.get("sensor.device_one_numeric_sensor") is not None
    assert hass.states.get("sensor.__device_one_numeric_sensor") is None


async def test_two_instances_no_collision(hass, mock_aioclient):
    """Two config entries with different prefixes must not produce colliding unique IDs."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry
    from custom_components.json_sensor.const import CONF_HEADERS, CONF_PREFIX, CONF_SCAN_INTERVAL, CONF_URL

    entry_a = MockConfigEntry(
        domain=DOMAIN,
        title="Instance A",
        data={
            CONF_URL: TEST_URL,
            CONF_SCAN_INTERVAL: 60,
            CONF_PREFIX: "alpha",
            CONF_HEADERS: {},
        },
        options={},
    )
    entry_b = MockConfigEntry(
        domain=DOMAIN,
        title="Instance B",
        data={
            CONF_URL: TEST_URL,
            CONF_SCAN_INTERVAL: 60,
            CONF_PREFIX: "beta",
            CONF_HEADERS: {},
        },
        options={},
    )

    mock_aioclient.get(TEST_URL, payload=SINGLE_DEVICE_PAYLOAD)
    entry_a.add_to_hass(hass)
    await hass.config_entries.async_setup(entry_a.entry_id)
    await hass.async_block_till_done()

    mock_aioclient.get(TEST_URL, payload=SINGLE_DEVICE_PAYLOAD)
    entry_b.add_to_hass(hass)
    await hass.config_entries.async_setup(entry_b.entry_id)
    await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    uid_a = f"{entry_a.entry_id}__alpha__device_one__numeric_sensor"
    uid_b = f"{entry_b.entry_id}__beta__device_one__numeric_sensor"

    assert ent_reg.async_get_entity_id("sensor", DOMAIN, uid_a) is not None
    assert ent_reg.async_get_entity_id("sensor", DOMAIN, uid_b) is not None
    assert uid_a != uid_b


# ---------------------------------------------------------------------------
# Unload
# ---------------------------------------------------------------------------


async def test_unload_removes_coordinator(hass, config_entry, mock_aioclient):
    await _setup(hass, config_entry, mock_aioclient)

    assert config_entry.entry_id in hass.data[DOMAIN]

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.entry_id not in hass.data.get(DOMAIN, {})
