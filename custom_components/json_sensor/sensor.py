from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_PREFIX, DOMAIN
from .coordinator import JsonSensorCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: JsonSensorCoordinator = hass.data[DOMAIN][entry.entry_id]
    prefix: str = (entry.options or entry.data).get(CONF_PREFIX, "") or ""

    known: set[tuple[str, str]] = set()

    @callback
    def _discover_new_entities() -> None:
        if coordinator.data is None:
            return
        new_entities: list[JsonSensorEntity] = []
        for device_key, device_data in coordinator.data.items():
            if not isinstance(device_data, dict):
                continue
            sensors = device_data.get("sensors", {})
            if not isinstance(sensors, dict):
                continue
            for sensor_key in sensors:
                pair = (device_key, sensor_key)
                if pair not in known:
                    known.add(pair)
                    new_entities.append(
                        JsonSensorEntity(
                            coordinator, entry, device_key, sensor_key, prefix
                        )
                    )
        if new_entities:
            async_add_entities(new_entities)

    # Populate from the initial fetch, then listen for new keys on future polls.
    _discover_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(_discover_new_entities))


def _normalize_id(value: str) -> str:
    return value.lower().replace(" ", "_")


def _title(key: str) -> str:
    return key.replace("_", " ").title()


class JsonSensorEntity(CoordinatorEntity[JsonSensorCoordinator], SensorEntity):
    """A sensor entity whose state, unit, device class, and icon come from the payload."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: JsonSensorCoordinator,
        entry: ConfigEntry,
        device_key: str,
        sensor_key: str,
        prefix: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_key = device_key
        self._sensor_key = sensor_key
        self._prefix = prefix

        prefix_norm = _normalize_id(prefix) if prefix else ""

        # --- Unique ID (stable across restarts) ---
        if prefix_norm:
            self._attr_unique_id = (
                f"{entry.entry_id}__{prefix_norm}__{device_key}__{sensor_key}"
            )
        else:
            self._attr_unique_id = f"{entry.entry_id}__{device_key}__{sensor_key}"

        # --- Entity ID (matches README spec) ---
        if prefix_norm:
            self.entity_id = f"sensor.{prefix_norm}_{device_key}_{sensor_key}"
        else:
            self.entity_id = f"sensor.{device_key}_{sensor_key}"

        # --- Device info ---
        device_data = (coordinator.data or {}).get(device_key, {})
        raw_device_name = device_data.get("name") or _title(device_key)

        if prefix:
            device_display_name = f"{prefix} {raw_device_name}"
            device_id = f"{entry.entry_id}__{prefix_norm}__{device_key}"
        else:
            device_display_name = raw_device_name
            device_id = f"{entry.entry_id}__{device_key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_display_name,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _sensor_data(self) -> dict | None:
        """Return the sensor's data dict from the coordinator, or None."""
        if self.coordinator.data is None:
            return None
        device = self.coordinator.data.get(self._device_key)
        if not isinstance(device, dict):
            return None
        sensors = device.get("sensors", {})
        if not isinstance(sensors, dict):
            return None
        sensor = sensors.get(self._sensor_key)
        return sensor if isinstance(sensor, dict) else None

    # ------------------------------------------------------------------
    # SensorEntity properties — all read live from coordinator data
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        data = self._sensor_data
        if data:
            raw = data.get("name")
            if raw:
                return str(raw)
        return _title(self._sensor_key)

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        data = self._sensor_data
        return data is not None and data.get("state") is not None

    @property
    def native_value(self) -> Any:
        data = self._sensor_data
        if data is None:
            return None
        state = data.get("state")
        if state is None:
            return None
        # Booleans must be serialised; HA native_value does not accept Python bool.
        if isinstance(state, bool):
            return "true" if state else "false"
        # HA requires datetime objects for date/timestamp device classes.
        # The producer supplies ISO 8601 strings; we parse them here.
        device_class = data.get("device_class")
        if isinstance(state, str):
            if device_class == "date":
                try:
                    return datetime.date.fromisoformat(state)
                except ValueError:
                    return None
            if device_class == "timestamp":
                try:
                    return datetime.datetime.fromisoformat(state)
                except ValueError:
                    return None
        return state

    @property
    def native_unit_of_measurement(self) -> str | None:
        data = self._sensor_data
        return data.get("unit") if data else None

    @property
    def device_class(self) -> str | None:
        data = self._sensor_data
        return data.get("device_class") if data else None

    @property
    def state_class(self) -> str | None:
        data = self._sensor_data
        return data.get("state_class") if data else None

    @property
    def icon(self) -> str | None:
        data = self._sensor_data
        return data.get("icon") if data else None
