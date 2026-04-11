from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_HEADERS, CONF_SCAN_INTERVAL, CONF_URL, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

_REQUEST_TIMEOUT = 10


def _effective_config(entry: ConfigEntry) -> dict:
    """Merge entry.data and entry.options, with options taking precedence."""
    return {**entry.data, **entry.options}


class JsonSensorCoordinator(DataUpdateCoordinator[dict]):
    """Fetches and validates the JSON sensor payload on a fixed interval."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        config = _effective_config(entry)
        self.url: str = config[CONF_URL]
        self.headers: dict[str, str] = config.get(CONF_HEADERS) or {}
        scan_interval = int(config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> dict:
        session = async_get_clientsession(self.hass)
        try:
            async with asyncio.timeout(_REQUEST_TIMEOUT):
                response = await session.get(self.url, headers=self.headers)
        except asyncio.TimeoutError as err:
            raise UpdateFailed("Timeout fetching data from endpoint") from err
        except Exception as err:
            raise UpdateFailed(f"Error communicating with endpoint: {err}") from err

        if response.status != 200:
            raise UpdateFailed(f"Endpoint returned HTTP {response.status}")

        try:
            payload = await response.json(content_type=None)
        except Exception as err:
            raise UpdateFailed(f"Failed to parse JSON response: {err}") from err

        if not isinstance(payload, dict):
            raise UpdateFailed("Payload is not a JSON object")
        if "devices" not in payload:
            raise UpdateFailed("Payload missing required 'devices' key")
        devices = payload["devices"]
        if not isinstance(devices, dict):
            raise UpdateFailed("'devices' must be a JSON object")

        return devices
