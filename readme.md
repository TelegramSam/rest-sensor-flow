# JSON Sensor Integration for Home Assistant

A custom Home Assistant integration that automatically creates sensor entities from a structured JSON endpoint. Configure a URL, and the integration creates and maintains one device per logical group and one sensor entity per value — no YAML templating, no manual entity definitions.

---

## Overview

Home Assistant's built-in REST sensor requires you to manually define every entity you want to track. For data sources that return structured collections of values — multiple groups, each with multiple metrics — this becomes tedious and brittle. This integration inverts that: the data producer describes the entities in the JSON payload itself, and the integration creates them automatically.

The schema is intentionally opinionated. Producers are responsible for mapping their data to Home Assistant's entity model. In exchange, the integration requires minimal configuration: a URL and an optional prefix.

---

## Installation

Install via HACS by adding this repository as a custom repository, or install manually by copying the `custom_components/json_sensor` directory into your Home Assistant `custom_components` folder.

After installation, add the integration via **Settings → Devices & Services → Add Integration** and search for **JSON Sensor**.

---

## Configuration

| Field | Required | Description |
|---|---|---|
| `url` | Yes | The endpoint that returns the JSON payload |
| `scan_interval` | No | Poll interval in seconds. Default: `60` |
| `headers` | No | Optional HTTP headers, e.g. for authorization |
| `name` | No | Display name for this integration instance. Default: `JSON Sensor` |
| `prefix` | No | Optional prefix applied to device names and entity IDs upon creation. Default: none |

Multiple instances of the integration may be configured, each pointing to a different URL.

### Prefix

When a `prefix` is configured, it is prepended to the display name and entity ID slug of every device and sensor created by that integration instance. If left blank, no prefix is applied.

The prefix is applied at creation time as follows:

- **Device name** — the prefix is prepended to the device display name with a space separator: `{prefix} {device_name}`
- **Entity ID** — the prefix is prepended to the entity ID slug with an underscore separator: `sensor.{prefix}_{device_key}_{sensor_key}`
- **Unique ID** — the prefix is included in the unique ID to ensure stability and avoid collisions between multiple integration instances: `{entry_id}__{prefix}__{device_key}__{sensor_key}`. If no prefix is set, the prefix segment is omitted: `{entry_id}__{device_key}__{sensor_key}`

The prefix is normalized to lowercase with spaces replaced by underscores before being applied to IDs. The original prefix string is used as-is for display name prepending.

The prefix is useful when running multiple integration instances that may return overlapping device or sensor keys, or when namespacing entities from a particular source is desirable for dashboard or automation organization.

---

## JSON Schema

The integration expects a JSON payload at the configured URL conforming to the following structure.

### Top-Level Structure

```json
{
  "devices": {
    "<device_key>": { },
    "<device_key>": { }
  }
}
```

The top-level object must contain a `devices` key. Each key within `devices` defines one device in Home Assistant. Device keys must be stable strings — they form part of each entity's unique ID and must not change between updates.

### Device Object

```json
{
  "<device_key>": {
    "name": "Human Readable Name",
    "sensors": {
      "<sensor_key>": { },
      "<sensor_key>": { }
    }
  }
}
```

| Field | Required | Description |
|---|---|---|
| `name` | No | Display name for the device. Defaults to the device key with underscores replaced by spaces, title-cased |
| `sensors` | Yes | Object containing one or more sensor definitions |

### Sensor Object

```json
{
  "<sensor_key>": {
    "state": <value>,
    "name": "Human Readable Name",
    "unit": "<unit_of_measurement>",
    "device_class": "<device_class>",
    "state_class": "<state_class>",
    "icon": "mdi:<icon_name>"
  }
}
```

| Field | Required | Description |
|---|---|---|
| `state` | Yes | The sensor value. Must be a string, number, or boolean |
| `name` | No | Display name for the sensor. Defaults to the sensor key with underscores replaced by spaces, title-cased |
| `unit` | No | Unit of measurement string. See [Supported Units](#supported-units) |
| `device_class` | No | Home Assistant sensor device class. See [Device Classes](#device-classes) |
| `state_class` | No | Home Assistant state class. See [State Classes](#state-classes). Omit for string or enum sensors |
| `icon` | No | Material Design Icons string in `mdi:<name>` format. Overrides the device class default icon if provided |

#### State Values

The `state` field must be a scalar value:

- **Number** — integer or float
- **String** — any text value, including ISO 8601 dates and timestamps
- **Boolean** — `true` or `false`

Nested objects and arrays are not valid state values. If `state` is `null` or the key is absent, the entity state will be set to `unavailable`.

#### Device Classes

The `device_class` field maps to Home Assistant's [sensor device class](https://developers.home-assistant.io/docs/core/entity/sensor/#available-device-classes). Setting a device class controls display formatting, unit validation, and the default icon. Common values include:

| Value | Description |
|---|---|
| `battery` | Battery level |
| `current` | Electrical current |
| `date` | Date value (ISO 8601 date string) |
| `duration` | Time duration |
| `energy` | Energy |
| `frequency` | Frequency |
| `humidity` | Relative humidity |
| `monetary` | Monetary value |
| `power` | Power |
| `pressure` | Pressure |
| `temperature` | Temperature |
| `timestamp` | Date and time (ISO 8601 datetime string) |
| `voltage` | Voltage |

This list is not exhaustive. Any valid Home Assistant sensor device class string is accepted. Unrecognized values are ignored rather than causing an error.

#### State Classes

The `state_class` field tells Home Assistant how to handle the sensor's history and long-term statistics:

| Value | Description |
|---|---|
| `measurement` | The value represents a current measurement. Suitable for most numeric sensors |
| `total` | The value is a cumulative total that may decrease (e.g. on reset) |
| `total_increasing` | The value is a cumulative total that only increases |

Omit `state_class` entirely for sensors with string or enum states.

#### Supported Units

The `unit` field accepts any string. For proper Home Assistant behavior, use standard unit strings. Common examples:

| Unit String | Meaning |
|---|---|
| `%` | Percentage |
| `°C` | Degrees Celsius |
| `°F` | Degrees Fahrenheit |
| `h` | Hours |
| `min` | Minutes |
| `s` | Seconds |
| `kWh` | Kilowatt-hours |
| `W` | Watts |
| `V` | Volts |
| `A` | Amperes |
| `hPa` | Hectopascals |
| `USD` | US Dollars |
| `EUR` | Euros |

The full list of recognized unit strings is defined by Home Assistant's unit registry.

---

## Entity Identity and Stability

Each sensor entity is assigned a `unique_id` derived from the integration instance, the optional prefix, the device key, and the sensor key.

Without a prefix:
```
{entry_id}__{device_key}__{sensor_key}
```

With a prefix:
```
{entry_id}__{prefix}__{device_key}__{sensor_key}
```

This ID is stable as long as the prefix, device key, and sensor key do not change between payloads. Stable IDs allow Home Assistant to preserve entity customizations, history, and dashboard assignments across restarts and payload updates.

**The prefix, device keys, and sensor keys should all be treated as permanent identifiers.** Changing any of them is equivalent to deleting the old entity and creating a new one. Use the `name` field in the payload and the `name` configuration field for display names that may change.

---

## Behavior

### Polling

The integration polls the configured URL at the interval defined by `scan_interval`. All devices and sensors for a given integration instance are updated from a single HTTP request per poll cycle.

### New Entities

If a new device key or sensor key appears in the payload that was not present when the integration was first loaded, the new device and/or sensor entities will be created automatically on the next poll cycle. A Home Assistant restart is not required.

### Missing Entities

If a device or sensor key that previously existed is absent from the payload, the corresponding entity's state is set to `unavailable`. The entity is not deleted. This preserves history and dashboard assignments.

### Payload Errors

If the endpoint returns a non-200 status, a malformed JSON body, or a body that does not contain a valid `devices` object, all entities managed by that integration instance are set to `unavailable` until a valid payload is received.

### Unit and Device Class Changes

The `unit` and `device_class` for a sensor are set when the entity is first created. If these values change in a subsequent payload, the change is applied and HA is notified. Note that changing `unit` or `device_class` may affect historical data display in HA's energy and statistics dashboards.

---

## Authentication

For endpoints that require authentication, configure the `headers` field with appropriate values. For example, to use a bearer token:

```
Authorization: Bearer <token>
```

Headers are stored in Home Assistant's config entry and are not exposed in logs.

---

## Limitations

- **Read-only.** This integration creates sensor entities only. Writable entity types (switches, numbers, selects, etc.) are not supported.
- **Scalar states only.** Nested objects and arrays cannot be expressed as entity states. State values must be strings, numbers, or booleans.
- **No attributes.** Sensor entities created by this integration do not expose additional state attributes beyond the standard HA entity metadata. The entire value surface is expressed as discrete sensor states.
- **Flat sensor namespace per device.** All sensors within a device share the same key namespace. Nested groupings within a device are not supported.
- **Poll only.** Push-based updates are not supported. The integration polls on a fixed interval.

---

## Producer Responsibilities

This integration places deliberate responsibility on the data producer:

1. **Schema conformance.** The producer must return a payload that matches the schema defined in this document.
2. **HA vocabulary.** The producer is responsible for knowing and using correct Home Assistant `device_class` and `unit` strings. The integration does not attempt to infer or translate these.
3. **Key stability.** Device and sensor keys must remain stable across payload updates. Keys are permanent identifiers, not display names.
4. **Scalar values.** The producer must reduce all values to scalars before including them in the payload. Aggregation, formatting, and type conversion are the producer's responsibility.

This design intentionally avoids any mapping or inference logic in the integration itself. The integration is mechanical: it reads the schema and creates entities. All semantic decisions live in the producer.

---

## Example Payload Structure

The following illustrates the schema using generic placeholders:

```json
{
  "devices": {
    "device_one": {
      "name": "Device One",
      "sensors": {
        "numeric_sensor": {
          "state": 42.5,
          "unit": "<unit>",
          "device_class": "<device_class>",
          "state_class": "measurement"
        },
        "string_sensor": {
          "state": "active"
        },
        "cumulative_sensor": {
          "state": 1024.0,
          "unit": "<unit>",
          "device_class": "<device_class>",
          "state_class": "total_increasing"
        }
      }
    },
    "device_two": {
      "name": "Device Two",
      "sensors": {
        "boolean_sensor": {
          "state": true
        },
        "dated_sensor": {
          "state": "2026-01-01",
          "device_class": "date"
        }
      }
    }
  }
}
```

---

## Project Structure

```
custom_components/
  json_sensor/
    __init__.py
    manifest.json
    config_flow.py
    coordinator.py
    sensor.py
    const.py
    strings.json
    translations/
      en.json
```

---

## Contributing

Contributions are welcome. Please open an issue before submitting a pull request for significant changes. Bug reports should include the payload structure (anonymized as needed) and the relevant Home Assistant logs.

---

## License

MIT