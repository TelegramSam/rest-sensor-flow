"""Integration tests using the real-world fixture at tests/fixtures/full.json.

Covers cases not exercised by test_sensor.py:
  - Numeric string device keys ("1", "2", "3")
  - Device name from payload ("1" → "NICA", "totals" → "Consulting Totals")
  - Zero float state (not treated as unavailable)
  - Negative float state
  - String status values ("ahead", "at_risk", "on_track")
  - Integer state (elapsed_days)
  - state_class present vs. absent on the same sensor type
  - Custom compound unit ("h/day")
  - Sensor display name passthrough ("Hours Logged", "Status", …)
"""
import json
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.json_sensor.const import DOMAIN

from .conftest import TEST_URL

# ---------------------------------------------------------------------------
# Fixture data
# ---------------------------------------------------------------------------

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "full.json"
FIXTURE_PAYLOAD = json.loads(_FIXTURE_PATH.read_text())


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _setup(hass: HomeAssistant, config_entry, mock_aioclient):
    mock_aioclient.get(TEST_URL, payload=FIXTURE_PAYLOAD)
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# Entity / device creation
# ---------------------------------------------------------------------------


async def test_entities_created_for_all_devices(hass, config_entry, mock_aioclient):
    """All four devices produce at least one entity each."""
    await _setup(hass, config_entry, mock_aioclient)

    for device_key, sensor_key in [
        ("1", "hours_logged"),
        ("2", "hours_logged"),
        ("3", "hours_logged"),
        ("totals", "month_hours"),
    ]:
        assert hass.states.get(f"sensor.{device_key}_{sensor_key}") is not None


async def test_device_names_resolved_from_payload(hass, config_entry, mock_aioclient):
    """Numeric-keyed devices use the payload 'name', not the key."""
    await _setup(hass, config_entry, mock_aioclient)

    dev_reg = dr.async_get(hass)
    entry_id = config_entry.entry_id

    assert dev_reg.async_get_device({(DOMAIN, f"{entry_id}__1")}).name == "NICA"
    assert dev_reg.async_get_device({(DOMAIN, f"{entry_id}__2")}).name == "TravelStorys"
    assert dev_reg.async_get_device({(DOMAIN, f"{entry_id}__3")}).name == "T-Tech"
    assert dev_reg.async_get_device({(DOMAIN, f"{entry_id}__totals")}).name == "Consulting Totals"


# ---------------------------------------------------------------------------
# State values
# ---------------------------------------------------------------------------


async def test_zero_float_state_is_not_unavailable(hass, config_entry, mock_aioclient):
    """state: 0.0 must not be treated as falsy/unavailable."""
    await _setup(hass, config_entry, mock_aioclient)

    state = hass.states.get("sensor.3_hours_logged")
    assert state is not None
    assert state.state == "0.0"


async def test_negative_float_state(hass, config_entry, mock_aioclient):
    """Negative numeric states are surfaced correctly."""
    await _setup(hass, config_entry, mock_aioclient)

    # device 3, delta_vs_max: -14.29
    state = hass.states.get("sensor.3_delta_vs_max")
    assert state.state == "-14.29"


async def test_string_status_states(hass, config_entry, mock_aioclient):
    """String sensor states are passed through verbatim."""
    await _setup(hass, config_entry, mock_aioclient)

    assert hass.states.get("sensor.1_status").state == "ahead"
    assert hass.states.get("sensor.3_status").state == "at_risk"
    assert hass.states.get("sensor.totals_status").state == "on_track"


async def test_integer_state(hass, config_entry, mock_aioclient):
    """Integer state values are rendered without a decimal point."""
    await _setup(hass, config_entry, mock_aioclient)

    # elapsed_days: 5  (int, not float)
    assert hass.states.get("sensor.totals_elapsed_days").state == "5"


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


async def test_state_class_present(hass, config_entry, mock_aioclient):
    """Sensors with state_class expose it as an attribute."""
    await _setup(hass, config_entry, mock_aioclient)

    state = hass.states.get("sensor.1_hours_logged")
    assert state.attributes.get("state_class") == "measurement"


async def test_state_class_absent(hass, config_entry, mock_aioclient):
    """Sensors without state_class produce no state_class attribute."""
    await _setup(hass, config_entry, mock_aioclient)

    # min_hours has no state_class in the fixture
    state = hass.states.get("sensor.1_min_hours")
    assert state.attributes.get("state_class") is None


async def test_compound_unit(hass, config_entry, mock_aioclient):
    """Units with slashes (h/day) are passed through unchanged."""
    await _setup(hass, config_entry, mock_aioclient)

    state = hass.states.get("sensor.1_daily_rate_to_minimum")
    assert state.attributes.get("unit_of_measurement") == "h/day"


async def test_sensor_display_names(hass, config_entry, mock_aioclient):
    """Payload 'name' fields become the entity's display name."""
    await _setup(hass, config_entry, mock_aioclient)

    ent_reg = er.async_get(hass)

    assert ent_reg.async_get("sensor.1_hours_logged").original_name == "Hours Logged"
    assert ent_reg.async_get("sensor.1_status").original_name == "Status"
    assert ent_reg.async_get("sensor.totals_elapsed_days").original_name == "Elapsed Working Days"
