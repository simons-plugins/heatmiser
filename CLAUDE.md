# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Plugin Overview

**Heatmiser Neo** - Indigo plugin for Heatmiser Neo thermostats and smart plugs

- **Version**: 2023.1.0 (API 3.0 / Python 3)
- **Bundle ID**: `com.racarter.indigoplugin.heatmiser-neo`
- **Author**: Alan Carter
- **Documentation**: https://carter53.wordpress.com/indigo/heatmiser/

Integrates Heatmiser Neo heating system with Indigo home automation via the Neohub central controller.

## Architecture

### Communication Protocol

The plugin communicates directly with a **Neohub** device using TCP sockets:
- **Port**: 4242
- **Protocol**: JSON over TCP with null terminator (`\0`)
- **Timeout**: 8 seconds for socket operations
- **IP Address**: Configurable via plugin preferences (default: 192.168.0.1)

All commands are sent as JSON objects wrapped in curly braces: `{"COMMAND":value}`

### Concurrent Thread Architecture

The plugin runs a continuous monitoring thread ([plugin.py:84-108](HeatmiserNeo.IndigoPlugin/Contents/Server Plugin/plugin.py#L84-L108)) that:

1. **Every 30 seconds**: Polls Neohub for device status updates via `INFO` command
2. **Once daily at specific times**:
   - 03:00 - Synchronizes Neohub time/date with Indigo (if enabled)
   - 00:00 - Fetches DCB (Device Control Block) data
   - 05:00 - Fetches Engineering data
3. **On first run**: Configures NTP settings based on time sync preference

**Thread Sleep Pattern**: 1 second poll + 29 second wait = 30 second cycle

### Device Auto-Discovery

On startup, the plugin queries the Neohub for all connected devices ([plugin.py:144-186](HeatmiserNeo.IndigoPlugin/Contents/Server Plugin/plugin.py#L144-L186)):

1. Sends `{"INFO":0}` command to discover devices
2. Creates Indigo device for each physical device (if not already created)
3. Uses the device's array index in the Neohub as the Indigo device address
4. Automatically determines device type and creates appropriate Indigo device

**Device Naming Restriction**: Device names from Heatmiser must be valid Python identifiers (no spaces, special characters except underscore). The plugin validates this with `isidentifier()` and logs an error if invalid.

### Supported Device Types

| Device Type | Description | Indigo Device Type |
|-------------|-------------|-------------------|
| 1 | NeoStat thermostat | `heatmiserNeostat` |
| 6 | NeoPlug smart plug | `heatmiserNeoplug` |
| 7 | NeoAir thermostat | `heatmiserNeostat` |
| 12 | NeoStat-e thermostat | `heatmiserNeostat` |
| 13 | NeoAir (newer model) | `heatmiserNeostat` |
| 14 | Wireless air sensor | `heatmiserNeoSensor` |
| 0 | Offline device | (sets error state) |

### State Management

**NeoStat Thermostats** track:
- Current temperature, setpoint, heat state
- Pre-heat mode, frost protection (mapped to "Cool" mode)
- Away/Holiday modes
- Hub firmware version, DST/NTP status (stored on first device)
- Engineering data: Rate of Change, Frost Temp, Switching Differential

**NeoPlug** tracks:
- On/Off state based on timer status

**Wireless Air Sensors** track:
- Current temperature reading
- Sensor valid/online status
- Low battery warning

### Mode Mapping

Heatmiser modes are mapped to Indigo HVAC modes:

| Heatmiser Mode | Indigo Mode | Description |
|----------------|-------------|-------------|
| Normal schedule | ProgramHeat | Following programmed schedule |
| Frost protection (STANDBY) | Cool | Building protection mode |
| Temperature hold (TEMP_HOLD) | Heat | Manual override/boost |

## Plugin Configuration

**PluginConfig.xml** defines three settings:

1. **neohubIP**: IP address of Neohub (default: 192.168.0.1)
2. **timeSync**: If true, sync Neohub time with Indigo daily; if false, use NTP
3. **logComms**: If true, log all socket communications to Indigo Event Log

## Available Actions

Defined in [Actions.xml](HeatmiserNeo.IndigoPlugin/Contents/Server Plugin/Actions.xml):

1. **Heating Override** (`setOverride`): Temporarily override schedule
   - Duration: 30 minutes to 20 hours
   - Temperature: 10-25°C
2. **Building Protection** (`setCool`): Enable frost protection mode
3. **Auto Mode** (`setAuto`): Return to programmed schedule
4. **Change Neohub IP** (`changeIp`): Update IP address without plugin restart

## Key Implementation Details

### Error Handling Strategy

The plugin uses error counters to avoid log spam ([plugin.py:44-45](HeatmiserNeo.IndigoPlugin/Contents/Server Plugin/plugin.py#L44-L45)):
- `connectErrorCount`: Only logs socket connection errors after 3 failures
- `sendErrorCount`: Only logs socket send errors after 3 failures
- Counters reset on successful communication

### Multi-Packet Response Handling

Some commands (INFO, ENGINEERS_DATA) return large JSON responses that may arrive in multiple TCP packets. The plugin handles this by checking for complete JSON markers:
- `INFO` command: Waits for `}]}` at end of response
- `ENGINEERS_DATA`: Waits for `}}` at end of response

### JSON Parsing Resilience

The plugin strips extraneous non-printable characters before JSON parsing ([plugin.py:298](HeatmiserNeo.IndigoPlugin/Contents/Server Plugin/plugin.py#L298)):
```python
datak = re.sub(b'[^\s!-~]', b'', dataj)  # Filter characters outside printable ASCII range
```

### Device Superseding

Devices with "SUPERSEDED" in their name are ignored during discovery and updates ([plugin.py:158, 397](HeatmiserNeo.IndigoPlugin/Contents/Server Plugin/plugin.py#L158)). This allows graceful device replacement without deleting old device records.

## Testing the Plugin

### Installation

```bash
# Copy plugin to Indigo plugins directory
cp -r "HeatmiserNeo.IndigoPlugin" "/Library/Application Support/Perceptive Automation/Indigo 2023.2/Plugins/"

# Or to disabled plugins folder for development
cp -r "HeatmiserNeo.IndigoPlugin" "/Library/Application Support/Perceptive Automation/Indigo 2023.2/Plugins (Disabled)/"
```

Then enable via: **Indigo → Plugins → Manage Plugins**

### Configuration

1. Enter your Neohub IP address in plugin preferences
2. Enable "Copy Neo comms to Indigo Event Log" for debugging
3. Optionally enable time sync if you want Indigo to manage Neohub time

### Debugging Commands

All Neohub commands are sent via `getNeoData()` method. Common commands:
- `{"INFO":0}` - Get all device status
- `{"READ_DCB":100}` - Get Device Control Block
- `{"ENGINEERS_DATA":0}` - Get engineering data
- `{"SET_TEMP":[20, "DeviceName"]}` - Set temperature
- `{"FROST_ON":["DeviceName"]}` - Enable frost protection
- `{"TIMER_ON":["DeviceName"]}` - Turn on NeoPlug

## Important Constraints

### Device Names
Heatmiser device names **must** be valid Python identifiers:
- ✅ `Living_Room`, `Bedroom1`, `Hall`
- ❌ `Living Room` (space), `Bed/Room` (slash), `Hall-way` (hyphen)

If invalid names are detected, the plugin logs an error and you must rename the device on the Neohub.

### Cooling Not Supported
Heatmiser Neo devices don't support cooling. The "Cool" mode in Indigo is mapped to frost protection. Indigo commands for cool setpoints are ignored.

### Status Update Frequency
Device status is updated every 30 seconds. Manual status request actions are not supported - the plugin logs "Status automatically updated every 30 seconds" for these requests.

## Development History

See [Versions.txt](HeatmiserNeo.IndigoPlugin/Versions.txt) for complete changelog. Key milestones:
- **2023.1.0** (Dec 2023): Added NeoAir support, superseded device handling
- **2022.1.0** (Aug 2022): Added Holiday Mode
- **2022.0.0** (Apr 2022): Updated for Indigo 2022.1+ and Python 3
- **0.5.0** (Jun 2019): Added 30-minute override option
- **0.3.0** (Oct 2017): Made time sync optional with NTP support

## Related Documentation

For general Indigo plugin development, see the parent [CLAUDE.md](../CLAUDE.md) which covers:
- Plugin lifecycle and structure
- Debugging techniques
- SDK examples and references
- Common development tasks

## Neohub API Reference

The plugin uses undocumented Heatmiser Neohub socket API. Key commands discovered through reverse engineering:

| Command | Purpose |
|---------|---------|
| `INFO` | Get all device status |
| `READ_DCB` | Get hub configuration (firmware, DST, NTP) |
| `ENGINEERS_DATA` | Get advanced device parameters |
| `SET_TEMP` | Set target temperature |
| `SET_TIME` / `SET_DATE` | Sync time/date |
| `FROST_ON` / `FROST_OFF` | Control building protection |
| `HOLD` | Temporary temperature override |
| `TIMER_ON` / `TIMER_OFF` | Control NeoPlug |
| `NTP_ON` / `NTP_OFF` | Enable/disable NTP |
| `DST_ON` / `DST_OFF` | Enable/disable DST |
