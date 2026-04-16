from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_HEADERS,
    CONF_PREFIX,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_REQUEST_TIMEOUT = 90


def _parse_headers(raw: str) -> dict[str, str]:
    """Accept JSON object or one \"Key: Value\" header per line."""
    raw = raw.strip()
    if not raw:
        return {}
    if raw.startswith("{"):
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Headers JSON must be an object")
        return {str(k): str(v) for k, v in parsed.items()}
    result: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Invalid header line (expected 'Key: Value'): {line!r}")
        key, _, value = line.partition(":")
        result[key.strip()] = value.strip()
    return result


async def _validate_connection(
    hass: HomeAssistant, url: str, headers: dict[str, str]
) -> str | None:
    """Return an error key on failure, None on success."""
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(_REQUEST_TIMEOUT):
            resp = await session.get(url, headers=headers)
    except asyncio.TimeoutError:
        return "timeout"
    except aiohttp.ClientError:
        return "cannot_connect"
    except Exception:
        return "unknown"

    if resp.status != 200:
        return "cannot_connect"

    try:
        payload = await resp.json(content_type=None)
    except Exception:
        return "invalid_payload"

    if not isinstance(payload, dict) or not isinstance(payload.get("devices"), dict):
        return "invalid_payload"

    return None


def _build_schema(defaults: dict[str, Any], include_name: bool = False) -> vol.Schema:
    fields: dict[vol.Marker, Any] = {}
    if include_name:
        fields[vol.Optional("name", default=defaults.get("name", DEFAULT_NAME))] = str
    fields[vol.Required(CONF_URL, default=defaults.get(CONF_URL, ""))] = str
    fields[
        vol.Optional(
            CONF_SCAN_INTERVAL,
            default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
    ] = vol.All(int, vol.Range(min=5))
    fields[vol.Optional(CONF_PREFIX, default=defaults.get(CONF_PREFIX, ""))] = str
    fields[vol.Optional(CONF_HEADERS, default=defaults.get(CONF_HEADERS, ""))] = str
    return vol.Schema(fields)


class JsonSensorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            headers_raw = user_input.get(CONF_HEADERS, "")
            try:
                headers = _parse_headers(headers_raw)
            except (ValueError, json.JSONDecodeError):
                errors[CONF_HEADERS] = "invalid_headers"
            else:
                error = await _validate_connection(
                    self.hass, user_input[CONF_URL], headers
                )
                if error:
                    errors["base"] = error
                else:
                    return self.async_create_entry(
                        title=user_input.get("name") or DEFAULT_NAME,
                        data={
                            CONF_URL: user_input[CONF_URL],
                            CONF_SCAN_INTERVAL: user_input.get(
                                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                            ),
                            CONF_PREFIX: user_input.get(CONF_PREFIX, ""),
                            CONF_HEADERS: headers,
                        },
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input or {}, include_name=True),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return JsonSensorOptionsFlow(config_entry)


class JsonSensorOptionsFlow(OptionsFlow):
    """Allow reconfiguring URL, poll interval, prefix, and headers."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        current = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            headers_raw = user_input.get(CONF_HEADERS, "")
            try:
                headers = _parse_headers(headers_raw)
            except (ValueError, json.JSONDecodeError):
                errors[CONF_HEADERS] = "invalid_headers"
            else:
                error = await _validate_connection(
                    self.hass, user_input[CONF_URL], headers
                )
                if error:
                    errors["base"] = error
                else:
                    return self.async_create_entry(
                        data={
                            CONF_URL: user_input[CONF_URL],
                            CONF_SCAN_INTERVAL: user_input.get(
                                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                            ),
                            CONF_PREFIX: user_input.get(CONF_PREFIX, ""),
                            CONF_HEADERS: headers,
                        }
                    )

        # Pre-fill headers for display
        existing_headers = current.get(CONF_HEADERS) or {}
        defaults = {
            CONF_URL: current.get(CONF_URL, ""),
            CONF_SCAN_INTERVAL: current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            CONF_PREFIX: current.get(CONF_PREFIX, ""),
            CONF_HEADERS: json.dumps(existing_headers) if existing_headers else "",
        }

        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(defaults),
            errors=errors,
        )
