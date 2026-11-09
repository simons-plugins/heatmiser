# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Plugin Overview

**Heatmiser Neo** - Indigo plugin for Heatmiser Neo thermostats and smart plugs

- **Version**: see `PluginVersion` in `Info.plist` (2026.x, API 3.0 / Python 3)
- **Bundle ID**: `com.racarter.indigoplugin.heatmiser-neo` (kept from the original so it upgrades existing installs in place)
- **Origin**: Simon Clark's fork of Alan Carter's plugin, imported at 2025.1.1 (March 2026). See git history for changes since.
- **Original documentation**: https://carter53.wordpress.com/indigo/heatmiser/

Integrates Heatmiser Neo heating system with Indigo home automation via the Neohub central controller.

## Versioning & Release

### Version bump is required for every PR

The `PluginVersion` in `HeatmiserNeo.IndigoPlugin/Contents/Info.plist` must be bumped in every PR. CI runs a version-check that fails if the version already exists as a git tag. **Do not merge with failing checks.**

Version format: `YYYY.R.patch` (e.g. `2026.0.2`). Bump the patch for fixes/docs, minor for features.

On merge to main, the `create-release` workflow automatically creates a GitHub release with a `.zip` bundle of the plugin.

### PR checklist

1. Bump `PluginVersion` in `Info.plist`
2. Push and create PR
3. Wait for version-check CI to pass
4. Merge only after all checks are green

## Architecture

### Communication Protocol

The plugin supports two connection modes to the **Neohub** device:

**WSS — Secure WebSocket (default, recommended):**
- **Port**: 4243 (TLS, self-signed cert)
- **Protocol**: Two-layer JSON envelope over WebSocket. Outer message has `message_type` + `message` fields; inner payload contains API token and `COMMANDS` array with `COMMAND`/`COMMANDID` pairs.
- **Authentication**: API token (generated in Heatmiser Neo App → Settings → Api Access → Tokens)
- **Connection**: Fresh WebSocket opened per command (closed in `finally`). Thread-safe via `_wss_lock`. An earlier persistent-connection design was abandoned after Indigo 2025.2 / Python 3.13 / `websockets` 15.x began raising `ProtocolError("incorrect masking")` on long-lived sockets — the per-call model trades one TLS handshake per poll for immunity to that class of state-desync bug.
- **Timeout**: 8 seconds for connection, 10 seconds for response

**Legacy TCP (port 4242):**
- **Port**: 4242 (unencrypted, no auth)
- **Protocol**: JSON over TCP with null terminator (`\0`). Opens a new socket per command.
- **Timeout**: 8 seconds for socket operations

- **IP Address**: Configurable via plugin preferences (default: 192.168.0.1)

All commands are sent as JSON objects: `{"COMMAND":value}`. The WSS path wraps them in the token-authenticated envelope; the TCP path sends them directly with a null terminator.

### Concurrent Thread Architecture

The plugin runs a continuous monitoring thread (`runConcurrentThread` in `plugin.py`) that:

1. **Every 30 seconds**: Polls Neohub for device status updates via `INFO` command
2. **Once daily at specific times**:
   - 03:00 - Synchronizes Neohub time/date with Indigo (if enabled)
   - 00:00 - Fetches DCB (Device Control Block) data
   - 05:00 - Fetches Engineering data
3. **On first run**: Configures NTP settings based on time sync preference

**Thread Sleep Pattern**: 1 second poll + 29 second wait = 30 second cycle

### Device Auto-Discovery

On startup, on the first successful poll if startup discovery failed, and whenever the hub reports a changed device list (`TIMESTAMP_DEVICE_LISTS` in `GET_LIVE_DATA` changes; Gen 2 only) or a hub zone not seen at the last discovery (both generations; Gen 1 `INFO` has no stamp), `createDevices()` queries the Neohub for all connected devices:

1. Sends `GET_LIVE_DATA` (Gen 2) or `INFO` (Gen 1) and indexes the result by `ZONE_NAME` (Gen 1: `device`)
2. Each Indigo device is bound to its hub zone by the `zoneName` plugin prop — **never by list position**. Removing a stat from the hub shifts every later entry up one slot, and position matching silently fed each device its neighbour's readings (issue #33).
3. Devices without `zoneName` (created before 2026.1.1) are migrated by Indigo name (allowing a trailing ` Heatmiser`). A device renamed in Indigo before upgrading cannot be matched safely: it is left alone (error state `NO HUB ZONE`) with a warning telling the user to rename it to exactly the hub zone name (or `<zone> Heatmiser`), restart, then rename it as they like. If its stat is no longer on the hub, the user adds `SUPERSEDED` to its name or deletes it.
4. Every hub zone with no claiming device gets a new Indigo device of the right type (named `<zone> Heatmiser` if Indigo already has a device with the zone's name). Creation is **held** while any legacy device is unmatched, so the user's rename-and-restart fix stays possible; the hold lifts once every unmatched legacy device is bound or retired (`SUPERSEDED`/deleted). A device whose zone has left the hub, or a legacy device with no matching zone, is warned about, put in an error state, and not updated. A hub-side zone rename orphans its device (`ZONE NOT ON HUB`) and creates a new device for the new name unless creation is held; to repoint it, use **Edit Device → Hub zone** (a menu of the hub's zones, defaulting to the stored `zoneName`); validation refuses a zone another live device already claims (rename that device with `SUPERSEDED` first), and a change logs the rebind and sets `_discoveryDone = False` so the next poll (≤30 s) runs `createDevices()`. When two devices claim one zone the first wins and the loser gets `DUPLICATE ZONE`. A device type change is deferred while creation is held (the old device is kept and still updated). A new zone whose device type is unknown (type 0 or `GET_ENGINEERS` failed) is not created until a later discovery sees its type.
5. Rediscovery is triggered only by stamp changes and by **new** zones. A zone that vanishes never triggers it: that device goes `ZONE NOT ON HUB` per poll and recovers by itself, so an offline stat dropping out of the list cannot churn discovery. Unusable list entries (no zone name, duplicate zone name — the first wins) are logged once per discovery.
6. If the hub fails to answer three polls in a row, every live device gets error state `HUB UNREACHABLE` (one warning, re-asserted each failed poll). The first good response clears it on bound devices and the per-device loop re-asserts `NO HUB ZONE` / `ZONE NOT ON HUB` / `DUPLICATE ZONE` / `OFFLINE` where they still apply.
7. Hub-level states (`HubFirmwareVersion`, DST, NTP, units, program format) exist only on `heatmiserNeostat`, so they always go to a neostat: the device bound to the position-0 zone if it is one, else the bound neostat with the lowest numeric `address`. No neostat means they are not written.
8. `address` mirrors the hub list position (refreshed via `pluginProps["address"]` for bound devices on each discovery) and is used only for display and for the pre-discovery hub-host fallback
9. Commands (`SET_TEMP`, `HOLD`, `TIMER_ON`, …) and `GET_ENGINEERS` lookups use `zoneName`. Once bound (`zoneName` set), devices can be renamed freely; unbound devices refuse commands with an Event Log error.

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
- Hold time remaining and hold temperature
- Window open, low battery, keypad locked
- Floor temperature (when probe present, 127 = no probe)
- Hub firmware version, DST/NTP status (stored on first device)
- Engineering data: Rate of Change, Frost Temp, Switching Differential

**NeoTimeclock** tracks:
- On/Off state, temperature, short mode
- Away/Holiday modes
- Hold time remaining (for timer boost)

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

**PluginConfig.xml** defines these settings:

1. **neohubIP**: IP address of Neohub (default: 192.168.0.1)
2. **connectionMode**: `wss` (default) or `tcp` — selects WSS port 4243 or legacy TCP port 4242
3. **neohubToken**: API token for WSS authentication (only visible when connectionMode is `wss`)
4. **neohubGen2**: Gen 2 API toggle (only visible when connectionMode is `tcp`; forced `True` for WSS)
5. **timeSync**: If true, sync Neohub time with Indigo daily; if false, use NTP
6. **logComms**: If true, log all communications to Indigo Event Log (token is redacted in WSS logs)

## Available Actions

Defined in [Actions.xml](HeatmiserNeo.IndigoPlugin/Contents/Server Plugin/Actions.xml):

1. **Heating Override** (`setOverride`): Temporarily override schedule
   - Duration: 30 minutes to 20 hours
   - Temperature: 10-25°C
2. **Building Protection** (`setCool`): Enable frost protection mode
3. **Auto Mode** (`setAuto`): Return to programmed schedule
4. **Timer Boost** (`timerBoost`): Boost timeclock device on for set duration
5. **Cancel Timer Boost** (`timerBoostOff`): Cancel active timer boost
6. **Set Holiday** (`setHoliday`): Set all devices to holiday mode until end date
7. **Cancel Holiday** (`cancelHoliday`): Cancel holiday mode
8. **Away Mode On** (`awayOn`): Set device to away mode (reduced temperature)
9. **Away Mode Off** (`awayOff`): Cancel away mode, restore schedule
10. **Lock Keypad** (`lockKeypad`): Lock thermostat keypad with 4-digit PIN
11. **Unlock Keypad** (`unlockKeypad`): Remove keypad lock
12. **Cancel Hold** (`cancelHold`): Cancel active temperature hold
13. **Set Frost Temp** (`setFrostTemp`): Set frost protection temperature per device
14. **Identify Device** (`identifyDevice`): Flash LED to locate a device
15. **Change Neohub IP** (`changeIp`): Update IP address without plugin restart

## Key Implementation Details

### Error Handling Strategy

The plugin uses error counters to avoid log spam:
- `connectErrorCount` / `sendErrorCount`: Track consecutive failures per transport
- **WSS path**: Logs the first 3 errors, then every 10th failure. Counters reset on success.
- **TCP path**: Logs only on the 3rd consecutive failure. `sendErrorCount` resets after logging.
- Both counters reset to 0 on any successful command.

### Multi-Packet Response Handling (TCP only)

On the legacy TCP path, some commands (INFO/GET_LIVE_DATA, ENGINEERS_DATA/GET_ENGINEERS) return large JSON responses that may arrive in multiple TCP packets. The plugin handles this by checking for complete JSON markers:
- `INFO`/`GET_LIVE_DATA` command: Waits for `}]}` at end of response
- `ENGINEERS_DATA`/`GET_ENGINEERS`: Waits for `}}` at end of response

The WSS path does not need this — WebSocket messages are framed at the protocol level.

### JSON Parsing Resilience

The plugin strips extraneous non-printable characters before JSON parsing (in `_get_neo_data_tcp`):
```python
datak = re.sub(b'[^\s!-~]', b'', dataj)  # Filter characters outside printable ASCII range
```

### Device Superseding

Devices with "SUPERSEDED" in their name are ignored during discovery and updates (see `_liveDevices`, `updateEng`, `_hubHostDevice`). This allows graceful device replacement without deleting old device records.

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
