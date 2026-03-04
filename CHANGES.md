# Heatmiser Neo Plugin - Changes Summary

**Original Author**: Alan Carter
**Fork Maintainer**: Simon
**Version**: 1.0.9 (from 2023.1.0)
**Date**: January 2026

## Overview

This fork adds full support for Heatmiser wireless air sensors (device type 14) and fixes several bugs related to device management and error handling.

## New Features

### 1. Wireless Air Sensor Support (Device Type 14)

The plugin now properly supports Heatmiser wireless air sensors as a distinct device type with appropriate states and UI display.

**Key capabilities:**
- Temperature monitoring with proper UI display
- Online/offline status detection
- Low battery warnings
- Sensor validity tracking

### 2. Automatic Device Type Migration

When the plugin detects air sensors that were previously created as thermostat devices, it automatically:
- Renames the old device with "SUPERSEDED" suffix
- Creates a new device with the correct `heatmiserNeoSensor` type
- Preserves the device address and name

### 3. Improved Device Matching

Enhanced device lookup logic to correctly match devices by both address AND device type, preventing conflicts when multiple device types share the same address.

## Bug Fixes

### 1. Fixed Temperature Display for Sensors

**Problem**: Air sensor devices were updating temperature states internally but not displaying values in the Indigo UI.

**Solution**: Added `<UiDisplayStateId>temperatureInput1</UiDisplayStateId>` to the sensor device definition.

### 2. Fixed Offline Device Error Spam

**Problem**: Offline thermostat devices (e.g., towel rails) logged "Neo temperature error" every 30 seconds.

**Solution**: Added offline detection before temperature processing. Offline devices now show OFFLINE error state without additional error logging.

### 3. Fixed Device Lookup Bug

**Problem**: Code was doing an unnecessary second lookup using `indigo.devices[dev.name]` after already finding the device by iteration.

**Solution**: Changed all instances to use the device object directly (`device = dev`).

### 4. Consistent Offline Handling

**Problem**: Thermostats and sensors handled offline status differently.

**Solution**: Standardized offline detection with early return for both device types, while still updating battery status for sensors.

### 5. Offline Sensor Display

**Problem**: Offline sensors showed "0" temperature which was confusing.

**Solution**: Offline sensors now display "offline" text and use the SensorOff icon for clear visual indication. Custom devices don't support `setErrorStateOnServer` the same way as built-in device types, so we set the display value explicitly.

## Files Modified

### 1. `Contents/Server Plugin/plugin.py`

#### Lines 159, 182 (createDevices method)
**Changed:**
```python
# OLD
device = indigo.devices[dev.name]

# NEW
device = dev
```
**Reason**: Fixed unnecessary device lookup bug.

#### Lines 153-177 (createDevices method)
**Added:** New code block to handle device type 14 (wireless air sensors) during device discovery and creation.

```python
if neoInfo["devices"][stat]["DEVICE_TYPE"] == 14:
    # This is a wireless air sensor
    device = None
    for dev in indigo.devices.iter("self"):
        if "SUPERSEDED" not in dev.name:
            if int(dev.address) == stat:
                device = dev
                # Check if existing device has correct type
                if device.deviceTypeId != "heatmiserNeoSensor":
                    indigo.server.log("Upgrading sensor device %s to new device type" % device.name)
                    # Rename old device
                    device.name = device.name + " SUPERSEDED"
                    device.replaceOnServer()
                    device = None
    if device == None:
        statName = neoInfo["devices"][stat]["device"]
        indigo.server.log("Creating Heatmiser sensor device for %s" % neoInfo["devices"][stat]["device"])
        device = indigo.device.create(protocol=indigo.kProtocol.Plugin,
        address=stat,
        name=neoInfo["devices"][stat]["device"],
        pluginId="com.racarter.indigoplugin.heatmiser-neo",
        deviceTypeId="heatmiserNeoSensor",
        props={})
    self.updateStatState(neoInfo, stat, device)
    continue
```

#### Lines 211-231 (updateReadings method)
**Changed:** Enhanced device matching logic to distinguish between sensors and thermostats at the same address.

```python
def updateReadings(self):
    update = self.getNeoData("\"INFO\":0")
    if update != "":
        max_devices = len(update["devices"])
        for stat in range(0, max_devices):
            device = None
            neoDeviceType = update["devices"][stat]["DEVICE_TYPE"]
            for dev in indigo.devices.iter("self"):
                if "SUPERSEDED" not in dev.name:
                    if int(dev.address) == stat:
                        # Match device type: sensor (14) should be heatmiserNeoSensor
                        if neoDeviceType == 14 and dev.deviceTypeId == "heatmiserNeoSensor":
                            device = dev
                            break
                        elif neoDeviceType != 14 and dev.deviceTypeId != "heatmiserNeoSensor":
                            device = dev
                            break
            if device != None:
                self.updateStatState(update, stat, device)
```

#### Lines 234-298 (updateStatState method)
**Changed:** Added offline detection for thermostats and improved air sensor handling.

**Thermostats (lines 236-241):**
```python
if (deviceType == 1) or (deviceType == 7) or (deviceType == 12) or (deviceType == 13):
    # Check if device is offline first
    if neoRep["devices"][index]["OFFLINE"]:
        indigoDevice.setErrorStateOnServer('OFFLINE')
        return
    # ... rest of processing
```

**Air Sensors (lines 275-296):**
```python
elif deviceType == 14:
    # This device is a wireless air sensor
    # Update battery status regardless of online/offline state
    indigoDevice.updateStateOnServer(key="lowBattery", value=neoRep["devices"][index]["LOW_BATTERY"])

    if neoRep["devices"][index]["OFFLINE"]:
        indigoDevice.updateStateOnServer(key="sensorValid", value=False)
        indigoDevice.updateStateOnServer(key="temperatureInput1", value=0, uiValue="offline")
        indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
        return

    # Device is online, process temperature
    curTemp = neoRep["devices"][index]["CURRENT_TEMPERATURE"]
    curTempf = float(curTemp)
    curTempr = round(curTempf, 1)

    if curTempr > 0:
        indigoDevice.updateStateOnServer(key="temperatureInput1", value=curTempr, uiValue=str(curTempr)+" °C", clearErrorState=True)
        indigoDevice.updateStateOnServer(key="sensorValid", value=True)
    else:
        indigoDevice.setErrorStateOnServer('INVALID TEMPERATURE')
        indigoDevice.updateStateOnServer(key="sensorValid", value=False)
```

**Note**: For custom devices, `setErrorStateOnServer` doesn't display consistently, so offline sensors show "offline" text and use the SensorOff icon instead.

### 2. `Contents/Server Plugin/Devices.xml`

#### Lines 100-119
**Added:** New device definition for wireless air sensors.

```xml
<Device type="custom" id="heatmiserNeoSensor" allowUserCreation="false">
    <Name>Heatmiser Neo Sensor</Name>
    <UiDisplayStateId>temperatureInput1</UiDisplayStateId>
    <States>
        <State id="temperatureInput1">
            <ValueType>Number</ValueType>
            <TriggerLabel>Temperature</TriggerLabel>
            <ControlPageLabel>Temperature</ControlPageLabel>
        </State>
        <State id="sensorValid">
            <ValueType>Boolean</ValueType>
            <TriggerLabel>Sensor Valid</TriggerLabel>
            <ControlPageLabel>Sensor Status</ControlPageLabel>
        </State>
        <State id="lowBattery">
            <ValueType>Boolean</ValueType>
            <TriggerLabel>Low Battery</TriggerLabel>
            <ControlPageLabel>Battery Status</ControlPageLabel>
        </State>
    </States>
</Device>
```

**Key element**: `<UiDisplayStateId>temperatureInput1</UiDisplayStateId>` ensures temperature displays in Indigo UI.

### 3. `Contents/Info.plist`

#### Line 16
**Changed:**
```xml
<!-- OLD -->
<string>2023.1.0</string>

<!-- NEW -->
<string>1.0.9</string>
```

Version number updated to reflect changes.

## Device States

### heatmiserNeoSensor States

| State | Type | Description |
|-------|------|-------------|
| `temperatureInput1` | Number | Current temperature reading in °C (UI display state) |
| `sensorValid` | Boolean | True if sensor is online and reporting valid data |
| `lowBattery` | Boolean | True if sensor battery is low |

## Testing Recommendations

1. **New Installation**: Plugin should auto-discover air sensors and create appropriate devices
2. **Upgrade Path**: Existing installations with air sensors as thermostats should auto-migrate to new device type with "SUPERSEDED" suffix on old devices
3. **Offline Devices**:
   - Verify offline thermostats show "OFFLINE" error state without error spam
   - Verify offline sensors display "offline" text with greyed SensorOff icon
4. **Temperature Display**: Verify air sensors show temperature values in Indigo device list
5. **Battery Status**: Verify low battery warnings display for air sensors (updated even when offline)

## Backwards Compatibility

- ✅ Existing thermostat and plug devices unaffected
- ✅ Existing air sensors (if any) will be migrated automatically on next plugin restart
- ✅ No configuration changes required
- ⚠️ Users may have "SUPERSEDED" devices to manually delete after migration

## Known Issues

None at this time.

## Future Enhancements

Potential improvements for future versions:
1. Auto-delete SUPERSEDED devices after successful migration
2. Add temperature trending/graphing support
3. Configurable offline detection timeout
4. Support for additional Heatmiser sensor types

## Migration Guide for Users

### For Existing Installations

1. Install updated plugin (version 1.0.9)
2. Plugin will restart automatically
3. Check Indigo device list for new sensor devices
4. Wait 30 seconds for first temperature update
5. Verify new devices are showing temperatures
6. Delete any "SUPERSEDED" devices from Indigo
7. Offline sensors will display "offline" with greyed sensor icon

### For New Installations

1. Install plugin
2. Configure Neohub IP address in plugin preferences
3. Plugin will auto-discover all devices including air sensors
4. All devices should appear in Indigo with correct types

## Contact

For questions about these changes, contact the fork maintainer.

For the original plugin, see: https://carter53.wordpress.com/indigo/heatmiser/

## Version History

- **1.0.9** (Final) - Improved offline sensor display with "offline" text and SensorOff icon
- **1.0.8** - Attempted to use consistent error state handling (reverted)
- **1.0.7** - Attempted custom offline display (improved in 1.0.9)
- **1.0.6** - Added offline detection for thermostats
- **1.0.5** - Fixed offline thermostat error spam
- **1.0.4** - Added UiDisplayStateId for sensors
- **1.0.3** - Enhanced device matching by type
- **1.0.2** - Fixed device lookup bug
- **1.0.1** - Initial air sensor support
- **2023.1.0** - Original version by Alan Carter

## License

Same as original Heatmiser Neo plugin (Copyright Alan Carter 2016-2018).
