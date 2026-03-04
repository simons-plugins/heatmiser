# neoHub API Rev 3.02

**Released 21/01/2025**

This document is a complete API guide to using the Heatmiser neoHub system and associated devices.

---

## Table of Contents

- [Revision History](#revision-history)
- [Copyright](#copyright)
- [Notes to Reader](#notes-to-reader)
- [Websocket Port 4243 Connections](#websocket-port-4243-connections)
  - [IP Address](#ip-address)
  - [Authentication](#authentication)
  - [Connection](#connection)
- [Legacy Port 4242 Connections](#legacy-port-4242-connections)
  - [Putty](#putty)
- [Websocket Command Structure](#websocket-command-structure)
  - [Syntax Description](#syntax-description)
- [JSON Commands Syntax](#json-commands-syntax)
  - [Syntax Description](#json-syntax-description)
- [V2 Commands Overview](#v2-commands-overview)
  - [Changes to the System](#changes-to-the-system)
  - [Switching Levels](#switching-levels)
  - [Profiles](#v2-profiles)
  - [Device Types](#device-types)
- [neoHub Commands](#neohub-commands)
  - [System Reboot](#system-reboot)
  - [Set Channel](#set-channel)
  - [System Wide (Global) Settings](#system-wide-global-settings)
  - [Global Functions](#global-functions)
  - [Away Function](#away-function)
  - [Holiday Function](#holiday-function)
- [Caches and Data Stores](#caches-and-data-stores)
  - [Live Data](#live-data)
  - [System Files](#system-files)
  - [Device Lists](#device-lists)
  - [Engineers Data](#engineers-data)
  - [Profile Timestamps](#profile-timestamps)
- [Comfort Levels](#comfort-levels)
  - [GLOBAL_DEV_LIST](#global_dev_list)
- [Time and Date Settings](#time-and-date-settings)
  - [Time Zone Adjustment](#time-zone-adjustment)
  - [Daylight Savings](#daylight-savings)
  - [Manual DST](#manual-dst)
- [Adding Thermostats, Devices and Accessories](#adding-thermostats-devices-and-accessories)
  - [Zone Title](#zone-title)
  - [Removing a Device](#removing-a-device)
- [Devices](#devices)
  - [Window and Door Switches](#window-and-door-switches)
  - [Wireless Sensors](#wireless-sensors)
- [Profiles](#profiles)
  - [JSON Structures Within Profiles](#json-structures-within-profiles)
  - [Saving Profiles](#saving-profiles)
  - [Retrieving Profiles](#retrieving-profiles)
  - [Changing Profile Names](#changing-profile-names)
  - [Editing Profiles](#editing-profiles)
  - [Activating Profiles](#activating-profiles)
  - [Deleting Profiles](#deleting-profiles)
  - [Profile 0](#profile-0)
  - [Saving Profiles Directly to the Device](#saving-profiles-directly-to-the-device)
  - [Clear Current Profile](#clear-current-profile)
- [Boost Function](#boost-function)
- [Engineers Settings](#engineers-settings)
  - [Failsafe](#failsafe)
- [Hold Function](#hold-function)
  - [Cancelling Holds](#cancelling-holds)
- [Identify](#identify)
- [INFO Command](#info-command)
- [Lock Command](#lock-command)
- [Standby Function](#standby-function)
- [Summer](#summer)
- [Statistics](#statistics)
- [Home Kit](#home-kit)
- [Timeclock Commands](#timeclock-commands)
  - [TIMER_HOLD_ON](#timer_hold_on)
  - [TIMER_HOLD_OFF](#timer_hold_off)
- [NeoPlug Commands](#neoplug-commands)
- [Timeclock Switching Times](#timeclock-switching-times)
  - [READ_TIMECLOCK](#read_timeclock)
  - [SET_TIMECLOCK](#set_timeclock)
- [User Limit](#user-limit)
- [Optimisation](#optimisation)
  - [ROC](#roc)
- [Groups](#groups)
- [Recipes](#recipes)
- [Set Temperature](#set-temperature)
- [NeoStat HC Commands](#neostat-hc-commands)
  - [Cooling](#cooling)
  - [Setting Up the System](#setting-up-the-system)
  - [HC-Specific Commands](#hc-specific-commands)
- [Appendix A - Profile Examples](#appendix-a---profile-examples)
  - [Profile 0 Examples](#profile-0-examples)
  - [Named Profile Examples](#named-profile-examples)
  - [Editing Profiles Example](#editing-profiles-example)
  - [Default Profile 0 Examples (0.5 Degree)](#default-profile-0-examples-05-degree)
- [Appendix B - Deprecated Commands](#appendix-b---deprecated-commands)
- [Appendix C - Alphabetical Command List](#appendix-c---alphabetical-command-list)
- [Appendix D - Examples of Cached Files](#appendix-d---examples-of-cached-files)
  - [Get System](#get-system-example)
  - [Get Live Data](#get-live-data-example)
  - [Get Engineers](#get-engineers-example)
  - [Get Profiles](#get-profiles-example)
  - [Cooling Profiles](#cooling-profiles)
- [Appendix E - Device Type List](#appendix-e---device-type-list)
- [Appendix F - Daylight Saving](#appendix-f---daylight-saving)
- [Addendum - Additional Settings](#addendum---additional-settings)

---

## Revision History

| Revision | Changes |
|----------|---------|
| Rev 0 | Original version taken from V1 system |
| Rev 1.000 | V2 commands added |
| Rev 1.001 | Web sockets added |
| Rev 2.000 | Cooling commands, new data caches |
| REV 2.501 | Reformatted to include more examples, descriptions and references |
| REV 2.502 | Added Home kit flag and HUB_TYPE variable |
| REV 2.503 | Added Addendum |
| REV 2.504 | Minor correction to grouped commands, added hub type variable to addendum |
| REV 2.505 | Updated hold command to include cooling |
| REV 2.507 | Clarified Progformat settings |
| REV 2.508 | Time Zone List added in Appendix F |
| REV 2.509 | Correction to wireless sensor example |
| REV 2.510 | Added missing JSON command |
| REV 2.511 | Updated Store_Profile command |
| REV 2.512 | Correction to Hold command |
| REV 2.700 | 0.5 degree switching / recipes added |
| REV 2.701 | Fixed errors in recipe commands |
| REV 2.8 | Fixed errors in hold command |
| REV 2.9 | Added examples of 0.5 switching in Set Temp |
| REV 2.91 | Added warning "Do Not Use Store_Profile or Store_Profile2 with neoStat HC" |
| REV 3.0 | Adding new websocket comms method and token generation |
| REV 3.2 | New default settings in Appendix A |

---

## Copyright

This document contains proprietary information that is protected by copyright. This document must not be reproduced, transcribed, stored, translated or transmitted, in part or in whole, without the prior written approval of Heatmiser.

---

## Notes to Reader

Apps normally connect through the webserver but it is possible to check commands directly by talking to the neoHub.

Historically this was done by direct connection to the neoHub established using TCP/IP on port 4242. This port, although still currently available has been superseded by a new websocket communications port 4243.

For all neoHubs running firmware 2153, the Legacy API Port on 4242 is closed but can be enabled in the Heatmiser neoApp via the Settings/API Access Menu.

Data from each device is stored as an array called a DCB. The JSON commands access these arrays and report the data back. Any error relating to a DCB access should be taken as a failure to read the data from the target device.

Each device can be set up as a thermostat or a time clock. The `{"GET_LIVE_DATA":0}` command will return `timeclock = true` for time clocks.

The neoAir wireless device can also be set up as a combined device that has both a timeclock and thermostat. These are reported as 2 separate devices. The word "Timer" is automatically appended to the zone title for the neoAir Timeclock.

Several existing commands have been deprecated -- these are listed in [Appendix B](#appendix-b---deprecated-commands). For backward compatibility they will still function but should not be used in new designs.

---

## Websocket Port 4243 Connections

### IP Address

Finding neoHub's on the users local network has now become easier. UDP Broadcasting `hubseek` on port 19790 will prompt hubs to respond with their IP if they are available. This is all done over UDP broadcast and so 3rd party systems would both need to be able to broadcast and listen for UDP on port 19790.

**Request example:**

```bash
echo -n "hubseek" | nc -b -u 255.255.255.255 19790
```

**Response example:**

```json
{"ip":"192.168.0.19", "device_id":" D8:80:39:AD:0D:F0"}
```

### Authentication

Users now manage access to their neoHub via generating API tokens for use by 3rd party systems. The user can create these within the Heatmiser Neo App and then should share the token with the 3rd party system for use by it in communicating with the hub.

A token can be generated from within the app via **Settings > Api Access > Tokens**.

### Connection

Connection to the neoHub is now made via a WSS connection -- this is a secure web socket connection over port 4243. As the security certificate is generated locally it is assigned to an IP and therefore any WSS connection should ignore verification of the cert. Once connected the connection is constant and there should be no need/reason to reconnect.

Sending commands to the neoHub now requires that the token provided and detailed in authentication above is included in a JSON string sent to the hub.

An example connection URI would be `wss://192.168.0.18:4243` and command structure including auth token can be found in the syntax description below.

---

## Legacy Port 4242 Connections

### Putty

When using putty any command which you send must be followed by the key sequence `CTRL+SHIFT+@` pressed simultaneously, e.g.:

`{"GET_SYSTEM":0}` followed by `CTRL+SHIFT+@` will return the current system settings when you press enter.

`{"GET_ZONES":0}` followed by `CTRL+SHIFT+@` will return the list of zone names. Then press enter.

> **Note:** Send the data as "RAW".

---

## Websocket Command Structure

### Syntax Description

Websocket commands take a format as follows:

```json
{
  "message_type": "hm_get_command_queue",
  "message": "{\"token\":\"{{token}}\",\"COMMANDS\":[{\"COMMAND\":\"{{command}}\",\"COMMANDID\":1}]}"
}
```

- `{{command}}` -- Takes the format `{"FIRMWARE":0}`. All commands as shown within this document ([Appendix C](#appendix-c---alphabetical-command-list)) can be included.
- `{{token}}` -- Token provided by user.

Worth noting above is the escaped format of anything within the message section -- this should be maintained in all commands.

**Sample response:**

```json
{
  "command_id": 1,
  "device_id": "D8:80:39:AD:0D:F0",
  "message_type": "hm_set_command_response",
  "response": "{\"firmware version\":\"2153\"}"
}
```

For further examples please see the Postman collection at:
https://heatmiser.postman.co/workspace/95e2f560-f892-42fb-a1f6-e88f929028df

---

## JSON Commands Syntax

### JSON Syntax Description

- `<device(s)>` is either a device, an array of devices and/or group names or a group name so `"device1"` or `["device1","device2","ourgroup"]` or `"ourgroup"`
- `<group>` is always a group name like `"ourgroup"`
- Anything inside `<>` ending with `name` is the name as a string `"name"`
- `<temp>` can be an integer or a floating-point value

The basic command structure:

**When there are no arguments:**

```json
{"cmd":0}
```

These will not check the values at all, so `{"cmd":[1,2,3,4,{"fsdfdsf":3}]}` would work as well.

**When there is one argument:**

```json
{"cmd":"<arg>"}
```

**When there are more:**

```json
{"cmd":["<args>"]}
```

Where `devices` is always one argument. For one device or group it can be just the device zone name or device number or group name. If it's more they'll need to be an array (to stay the one devices argument).

**Examples:**

```json
{"cmd":[1,"kitchen"]}
```
For one device in a multiple argument command.

```json
{"cmd":[1,["kitchen", "bathroom"]]}
```
For multiple argument, multiple devices.

Such commands will only check if there are enough arguments (and the correct contents). If the one argument is the devices it would be:

```json
{"cmd":"kitchen"}
```
or
```json
{"cmd":["kitchen","bathroom"]}
```

Single device arrays are also allowed: `{"cmd":["kitchen"]}`

---

## V2 Commands Overview

### Changes to the System

The operation of the V2 system is based on the idea that downloading or uploading data that has not changed since the last up/download is inefficient.

To this end the data has been broken down into sections. Each section includes a time stamp to indicate if the data has changed.

Constantly changing data is stored in the live data array which also contains the timestamps for all the other sections.

To display current information, the app needs only to download this single file. To check the validity of previously stored files it then needs to scan the timestamps and if the timestamps match those previously downloaded, nothing further needs to be done. If the timestamps have changed, then the associated file needs to be downloaded again and stored within the app.

The app thereby retains local (to the device) copies of the various settings and profiles held in the neoHub itself. Synchronisation relies on the correct use and interpretation of the timestamps.

### Switching Levels

Thermostats can now have 4 or 6 comfort levels -- this is a global setting chosen by the user.

### V2 Profiles

The new system makes greater use of profiles.

Profiles are numbered and named so that only the profile number needs to be sent between the Application and the neoHub. The user uses the named local copy to select the profile and the app sends the profile number. The neoHub then uses its own copy of the profile to send the comfort level or timeclock settings to the device or devices.

The neoStat reports the profile it is currently using as part of the live data field.

**Profile 0:** This profile is not really a profile. Its purpose is to allow the system to report back changes on the thermostat itself and allow the user to use the app to change a single room.

If we assume that the kitchen is currently running a profile called "night shift" and the user manually changes the settings, then the kitchen neoStat is no longer running the night shift profile -- it's using its own comfort levels. This change resets the profile byte in the live data to 0.

Profile 0 is therefore a copy of the comfort levels for a device that's not running a profile. It needs to be uploaded when indicated. Named Profiles 1 through 255 are available to the user.

### Device Types

Device types tell you what the physical form of each device is, which indicates how to handle the information in the live data array and other caches. For example, the neoStat is device type 1 but could be a thermostat or a timeclock which is reflected in the live data array.

neoAir's are device type 7 and can be thermostats, timeclocks or a combination of both. Repeaters are device type 10. For a complete list of device types see [Appendix E](#appendix-e---device-type-list).

---

## neoHub Commands

### System Reboot

To force a soft reboot of the neoHub:

```json
{"RESET":0}
```

> **Note:** This command only works with firmware version 2027 and above.

### Set Channel

This command can be used to change the ZigBee channel used by the neoHub:

```json
{"SET_CHANNEL":11}
```

Allowed channels are: 11, 14, 15, 19, 20, 24 and 25.

Please note that if neoAir's or neoStats are connected to the neoHub, care must be taken to ensure all devices are online when the command is sent, otherwise the neoStat will not know the channel has been changed and may need to be re-paired to the network.

If you attempt to set a channel and the neoHub detects a lot of interference, it will refuse to change. Therefore, you need to verify the channel change has taken place. You will find the channel number in the system cache.

**Read DCB:100** -- Returns system wide variables. This command has been deprecated, use `{"GET_SYSTEM":0}`.

### System Wide (Global) Settings

Some feature settings within the neoStat's are global. For example, the choice of degrees Celsius or Fahrenheit -- changing any of these settings will instruct the neoHub to change every device to the same settings.

**Temperature format:**

```json
{"SET_TEMP_FORMAT":"C"}
```
or
```json
{"SET_TEMP_FORMAT":"F"}
```

Sets the system to run in Celsius (C) or Fahrenheit (F).

> **Note:** Changing from C to F or vice versa will invalidate historical data so this will be automatically deleted.

**Program format:**

```json
{"SET_FORMAT":"7DAY"}
```

> **Note:** Changing the format on 1 device will change it on all connected devices.

Available formats:

| Format | Description | System Cache Value |
|--------|-------------|-------------------|
| `"NONPROGRAMMABLE"` | Fixed temperature | FORMAT 0 |
| `"24HOURSFIXED"` | Every day the same | FORMAT 1 |
| `"5DAY/2DAY"` | Weekdays/weekends | FORMAT 2 |
| `"7DAY"` | Every day different | FORMAT 4 |

Time clocks cannot be nonprogrammable. If the system is moved to nonprogrammable any timeclock will remain on the previous settings. This setting can be read from `"ALT_TIMER_FORMAT"` variable in the system cache.

> **Note:** Changing the program format will invalidate any stored profiles so these will be automatically deleted.

### Global Functions

These functions affect every device on the system.

### Away Function

Used for when the property is unoccupied for an unknown length of time.

The away function turns everything off putting timeclocks and thermostats into standby. Thermostats put in standby will maintain the frost protection temperature set by the user, ignoring any schedule. Timeclocks will remain off ignoring any schedule.

```json
{"AWAY_ON":0}
{"AWAY_OFF":0}
```

These commands can also be targeted to specific devices:

```json
{"AWAY_ON":["lounge","bed1"]}
{"AWAY_OFF":["lounge","bed1"]}
```

However, using `{"AWAY_OFF":0}` will cancel these, so it's better to use the `FROST_ON`/`FROST_OFF` commands for individual rooms.

### Holiday Function

Used for when the property is unoccupied until a specified date and time.

The holiday function turns everything off putting timeclocks and thermostats into standby. Thermostats put in standby will maintain the frost protection temperature set by the user ignoring any schedule. Timeclocks will remain off ignoring any schedule.

```json
{"HOLIDAY":["START TIME AND DATE","END TIME AND DATE"]}
{"HOLIDAY":["HHMMSSDDMMYYYY","HHMMSSDDMMYYYY"]}
```

**Example:**

```json
{"HOLIDAY":["14450001062016","14450002062016"]}
```

In this example the start time is 2:45pm 0 seconds 01/06/2016 and the end time is 2:45pm 0 seconds 02/06/2016.

**Get holiday dates:**

```json
{"GET_HOLIDAY":0}
```

Returns:

```json
{"end": "Sun Feb 11 19:02:00 2018\n", "ids": ["Office"], "start": "Fri Feb 9 14:33:29 2018\n"}
```

**Cancel holiday:**

```json
{"CANCEL_HOLIDAY":0}
```

Cancels the holiday, all devices revert to following their schedules.

---

## Caches and Data Stores

There are 7 blocks of data that rarely change. These are stored in the neoHub and where they are needed in the controlling device (usually an App). These blocks are:

1. System
2. Device lists
3. Engineers data
4. Profile_0
5. Profile_comfort levels
6. Profile_timers
7. Profile_timers_0

The process is that the controller sends a command. If that command affects any of the stored data, the cache is updated along with its timestamp. The timestamp is then copied to the live data field. The controller scans the timestamps and uploads the cache if the timestamp is newer than the one it already holds. In this way data is only uploaded when it changes.

### Live Data

The live data array contains the latest status information about the thermostats and the timestamps for all the caches. Under normal circumstances it is updated once every 90 seconds, more often when an app is connected to our server.

**Example:**

```json
{"GET_LIVE_DATA":0}
```

Returns:

```json
{
  "CLOSE_DELAY": 0,
  "COOL_INPUT": false,
  "GLOBAL_SYSTEM_TYPE": "HeatOnly",
  "HOLIDAY_END": 0,
  "HUB_AWAY": false,
  "HUB_HOLIDAY": false,
  "HUB_TIME": 1518613752,
  "OPEN_DELAY": 0,
  "TIMESTAMP_DEVICE_LISTS": 1518607836,
  "TIMESTAMP_ENGINEERS": 1518607837,
  "TIMESTAMP_PROFILE_0": 1518607836,
  "TIMESTAMP_PROFILE_COMFORT_LEVELS": 1518604883,
  "TIMESTAMP_PROFILE_TIMERS": 1518600089,
  "TIMESTAMP_PROFILE_TIMERS_0": 1518607918,
  "TIMESTAMP_SYSTEM": 1518607836,
  "devices": [
    {
      "ACTIVE_LEVEL": 2,
      "ACTIVE_PROFILE": 25,
      "ACTUAL_TEMP": "25.7",
      "AVAILABLE_MODES": ["heat"],
      "AWAY": false,
      "COOL_MODE": false,
      "COOL_ON": false,
      "COOL_TEMP": 0,
      "CURRENT_FLOOR_TEMPERATURE": 127,
      "DATE": "Wednesday",
      "DEVICE_ID": 1,
      "FAN_CONTROL": "Automatic",
      "FAN_SPEED": "Custom",
      "FLOOR_LIMIT": false,
      "HC_MODE": "VENT",
      "HEAT_MODE": true,
      "HEAT_ON": false,
      "HOLD_OFF": true,
      "HOLD_ON": false,
      "HOLD_TEMP": 5,
      "HOLD_TIME": "0:00",
      "HOLIDAY": false,
      "LOCK": false,
      "LOW_BATTERY": false,
      "MANUAL_OFF": true,
      "MODELOCK": false,
      "MODULATION_LEVEL": 0,
      "OFFLINE": false,
      "PIN_NUMBER": "1111",
      "PREHEAT_ACTIVE": false,
      "RECENT_TEMPS": ["25.6", "25.7", "..."],
      "SET_TEMP": "17.0",
      "STANDBY": false,
      "SWITCH_DELAY_LEFT": "0:00",
      "TEMPORARY_SET_FLAG": false,
      "THERMOSTAT": true,
      "TIME": "13:08",
      "TIMER_ON": false,
      "WINDOW_OPEN": false,
      "WRITE_COUNT": 110,
      "ZONE_NAME": "Bathroom"
    }
  ]
}
```

The devices section is then duplicated for everything attached to the system.

Not all variables in this list are used by every device. For example, the Lock variable is not used by a neoPlug so will always return False. However, the write count is incremented when a command is received and actioned. It is therefore used by all devices.

> **Note:** For sleepy end devices the write count bit 6 and 7 will be updated by the neoHub to indicate that the command has been received but the hub is waiting for the device to wake up before it can be actioned. During the waiting period the hub will simulate the expected response from the device. Bits 6 and 7 will be cleared when all outstanding commands have been completed.

### System Files

`TIMESTAMP_SYSTEM` tracks system-wide settings.

```json
{"GET_SYSTEM":0}
```

Returns:

```json
{
  "ALT_TIMER_FORMAT": 2,
  "CORF": "C",
  "DEVICE_ID": "neoHub",
  "DST_AUTO": true,
  "DST_ON": false,
  "FORMAT": 2,
  "HEATING_LEVELS": 4,
  "HEATORCOOL": "HeatOnly",
  "HUB_VERSION": 2081,
  "NTP_ON": "Running",
  "PARTITION": "4",
  "TIMESTAMP": 1518607836,
  "TIME_ZONE": 0,
  "UTC": 1518611554
}
```

### Device Lists

`TIMESTAMP_DEVICE_LISTS` keeps track of anything added or removed from the system. It therefore reflects changes made to any of the following: `GET_DEVICES`, `GET_DEVICE_LIST`, `GET_ZONES`, `DEVICES_SN`.

**Examples:**

```json
{"GET_ZONES":0}
```

Returns the zone name and ID number of all neoStat's:

```json
{"Bathroom": 1, "Room name": 2, "Office": 3, "plug": 4}
```

Additional equipment that can be added to a neoHub are listed as devices. A full list of these devices is stored in the Devices list:

```json
{"GET_DEVICES":0}
```

Returns a list of all devices except neoStat's:

```json
{"result": ["plug"]}
```

Once on the system a device can be linked to a neoStat Zone name:

```json
{"GET_DEVICE_LIST":"room name"}
```

Returns:

```json
{"room name": []}
```

In this case nothing is linked to "room name".

```json
{"DEVICES_SN":0}
```

Returns the serial numbers for all attached devices.

### Engineers Data

`TIMESTAMP_ENGINEERS` contains setup information about all the neoStats.

**Example:**

```json
{"GET_ENGINEERS":0}
```

Returns:

```json
{
  "Bathroom": {
    "DEADBAND": 0,
    "DEVICE_ID": 1,
    "DEVICE_TYPE": 1,
    "FLOOR_LIMIT": 28,
    "FROST_TEMP": 12,
    "MAX_PREHEAT": 3,
    "OUTPUT_DELAY": 0,
    "PUMP_DELAY": 0,
    "RF_SENSOR_MODE": "self",
    "STAT_FAILSAFE": 0,
    "STAT_VERSION": 101,
    "SWITCHING DIFFERENTIAL": 1,
    "SWITCH_DELAY": 0,
    "SYSTEM_TYPE": 0,
    "TIMESTAMP": 1518535921,
    "USER_LIMIT": 0,
    "WINDOW_SWITCH_OPEN": false
  }
}
```

This data is then repeated for every device on the system.

### Profile Timestamps

- `TIMESTAMP_PROFILE_COMFORT_LEVELS` -- Profile comfort levels contains the saved thermostat profiles.
- `TIMESTAMP_PROFILE_TIMERS` -- Profile timers contains the saved time clock profiles.
- `TIMESTAMP_PROFILE_0` -- Refers to the last time there was a change on the profile 0 (comfort levels) of any device. Accessed by `{"GET_PROFILE_0":"<device>"}`.
- `TIMESTAMP_PROFILE_TIMERS_0` -- Refers to the last time there was a change on the profile 0 (timer levels) of any device. Accessed by `{"GET_TIMER_0":"<device>"}`.

If a device doesn't have an active profile and the `TIMESTAMP_PROFILE_COMFORT_LEVELS` or `TIMESTAMP_PROFILE_TIMERS` is newer than the last time, then you should update the cache for that device.

If a device has an active profile and the `TIMESTAMP_PROFILE_COMFORT_LEVELS` or `TIMESTAMP_PROFILE_TIMERS` isn't newer than the last time, then an update to the cache isn't needed.

---

## Comfort Levels

A comfort level is 2 variables: time and temperature. For heating and cooling systems there are 4 variables.

The thermostat will attempt to achieve the required temperature at the stated time, then maintain that temperature until the next comfort level is reached.

By default, there are 4 comfort levels per day. This can be increased to 6 comfort levels per day:

```json
{"SET_LEVEL_4":0}
{"SET_LEVEL_6":0}
```

A group of comfort levels is called a Profile.

**Read comfort levels:**

```json
{"READ_COMFORT_LEVELS":"<device(s)>"}
```

> This command has been deprecated, use `GET_PROFILE_0`.

**SET_COMFORT_LEVELS:**

```json
{"SET_COMFORT_LEVELS":"<device(s)>"}
```

> This command has been deprecated, use `STORE_PROFILE_0`.

> **Note:** A switching time of 24:00 hours or 00:00 hours will disable that level. The target temperature will then remain where it was set by the last valid comfort level, until the next comfort level with a valid time is reached or the user changes it manually. This will show as 2 dashes (--) on the thermostat.

### GLOBAL_DEV_LIST

The global device list contains the id number for all devices attached to the system that will be affected by the `AWAY` command.

---

## Time and Date Settings

The neoHub will automatically connect to the network time server to get the current time and date (GMT). This function can be disabled. If disabled, the time and date will need to be set manually.

The neoHub will then use its built-in clock to synchronise all devices. The back-up battery will keep the clock running if power fails for 4 hours.

The time and date in the neoHub can be seen in Unix format as UTC in system cache. `HUB_TIME` shown in live data includes daylight savings and time zone adjustments and is the time shown on the neoStats.

```json
{"NTP_OFF":0}
{"NTP_ON":0}
```

> **Note:** In some circumstances the reconnection attempt will fail. The neoHub will then keep trying to reconnect until it succeeds.

**Setting the Date:**

Under normal circumstances you will not need to set the date, but it can be set if the network time server (ntp) cannot be contacted. Please note setting the time/date manually will turn off the ntp.

```json
{"SET_DATE":[2018, 12, 09]}
{"SET_TIME":[14, 25]}
```

The current time is available in Unix format in the live data array.

### Time Zone Adjustment

```json
{"TIME_ZONE":10.5}
```

Will adjust the clock 10 hours 30 minutes ahead of GMT. The `.5` is for those areas that use half hour offsets.

```json
{"TIME_ZONE":-5.0}
```

Will adjust the clock backwards by 5 hours from GMT.

Because most countries use UTC + Time Zone + DST it is possible to set the time by only adjusting the time zone variable, but only in 15-minute steps.

### Daylight Savings

This function is being expanded and full details have been moved to [Appendix F](#appendix-f---daylight-saving).

The DST function automatically advances the clock by 1 hour in the warmer months and reduces it by 1 hour in the cooler months. The dates that these changes take place is country specific, this is because daylight savings times and dates vary from country to country and sometimes year to year around the world.

When turning automatic daylight savings off you must also send the `{"MANUAL_DST":0}` command to prevent errors.

### Manual DST

Adds 1 hour to the neoHub time which moves the system to daylight saving.

```json
{"MANUAL_DST":0}
```

neoHub Time = (GMT + Time zone) = no daylight savings.

```json
{"MANUAL_DST":1}
```

neoHub Time = (GMT + Time zone) + 1 = daylight savings of 1 hour.

---

## Adding Thermostats, Devices and Accessories

Most devices are added to the system using the standard command:

```json
{"PERMIT_JOIN":[120,"kitchen"]}
```

In this case you have 120 seconds to pair the device you want to call "kitchen". The device will show up as a zone in the Get Zones list or a device in the Get Devices list.

However, repeaters or boosters use a different pairing command:

```json
{"PERMIT_JOIN":["repeater", 120]}
```

In this case you have 120 seconds to pair your repeater to the neoHub. Each repeater will then be visible as `repeaternodexxxxx`, where xxxxx is a random but unique identifier.

Repeater status information is available in the Live data function.

> **Note:** Care must be taken when removing repeaters from the system as the same repeater can be added multiple times, each time with a new unique ID but the old status information will remain until it is properly removed.

### Zone Title

Used to change the room name after installation:

```json
{"ZONE_TITLE":["HCtest","HCtest2"]}
```

### Removing a Device

```json
{"REMOVE_ZONE":"test"}
```

This command will tell the device called "test" to disconnect from the network and all reference to it in the neohub will be deleted. The wifi connected symbol on the thermostats will go off and accessing feature setting 01 will show no connection.

> **Note:** If the command fails to reach the neoStat before the deletion process within the hub completes, the neoStat will need to be factory reset before it can be paired to the system again.

Similarly:

```json
{"REMOVE_REPEATER":"<repeater>"}
```

Will remove a repeater.

neoPlug's do not indicate when they are connected. Instead they flash a red LED every 20 seconds to indicate no connection.

---

## Devices

neoStat's are listed as zones within the system. Anything that is not a neoStat or neoAir is a Device. neoPlug's, door switches and remote sensors are the most common devices.

It is possible to link devices to zones by linking them to a neoStat that's already in that zone. This allows all neo devices to be displayed under the same zone name.

```json
{"GET_DEVICES":0}
```

Returns a list of all devices attached to the neoHub.

**LINK_DEVICE:**

```json
{"LINK_DEVICE":["Kitchen","neoplug"]}
```

Links a device to a thermostat zone.

**GET_DEVICE_LIST:**

```json
{"GET_DEVICE_LIST":"zone name"}
```

Returns a list of devices linked to a neoStat zone.

**DETACH_DEVICE:**

```json
{"DETACH_DEVICE":["Kitchen","neoplug"]}
```

Detaches a device from a neoStat zone.

> **Note:** The link is broken but both devices remain connected to the system.

**DEVICES_SN:**

```json
{"DEVICES_SN":0}
```

Returns the serial number of the device.

**CLEAR_DEVICE_LIST:**

```json
{"CLEAR_DEVICE_LIST":"Kitchen"}
```

Deletes all items in a zone's device list and disconnects them.

### Window and Door Switches

These are battery powered wireless switches that send a simple open/close signal directly to the neoHub.

When linked to a room they will put the thermostat into standby which effectively turns the heating down or off while the door or window is open. To prevent premature triggering, you can set a delay in the neoHub:

```json
{"SET_CLOSE_DELAY":10}
{"SET_OPEN_DELAY":10}
```

The delay is global, so all switches will be delayed by the same amount.

To add a switch, use the permit join command. It will then show up as a zone in the system.

> **Note:** One switch can be used with multiple zones.

### Wireless Sensors

These are battery powered wireless temperature sensors. They can be used to monitor areas or linked to a neoStat zone.

When linked to a zone they can be used as simple monitors, averaged with the neoStat temperature reading, or replace the neoStat temperature sensor:

```json
{"SET_RF_MODE":["<mode>", "<devices>"]}
```

The options are:

| Mode | Description |
|------|-------------|
| `MIX` | The neoStat reports the average of the remote sensor and the neoStat's internal room sensor |
| `REMOTE` | The neoStat uses the remote sensor temperature |
| `SELF` | The neoStat uses its own internal sensor; the wireless sensor monitors temperature at its own location |

> **Note:** If the sensor loses connection to the neoHub the neoStat will reconnect its own internal temperature sensor after 10 minutes.

**Example:**

```json
{"SET_RF_MODE":["mix", "Kitchen"]}
```

Tells the neoStat in the kitchen to average the temperature from the wireless sensor with the kitchen neoStat's internal sensor.

> **Note:** Adding more than one sensor will cause the average of all wireless sensors to be calculated, then the average of those sensors will be averaged with the neoStat sensor in MIX mode or used as the temperature reading in REMOTE mode.

To add a sensor, use the permit join command. It will then show up as a zone in the system.

---

## Profiles

Profiles are a collection of comfort levels or a collection of switching times for timeclocks. The exact layout of a profile is determined by the program mode and number of comfort levels in a day.

| Mode | 4 Levels | 6 Levels |
|------|----------|----------|
| 7day | 28 comfort levels | 42 comfort levels |
| 5/2 day | 8 comfort levels | 12 comfort levels |
| 24hour | 4 comfort levels | 6 comfort levels |

Profiles cannot be used in nonprogrammable mode because there are no comfort levels.

Timeclocks always have 4 on and 4 off times regardless of the number of comfort levels per day that have been set. Timeclock profiles therefore have a different structure and different commands than comfort level profiles.

| Mode | On Times | Off Times |
|------|----------|-----------|
| 7day | 28 | 28 |
| 5/2day | 8 | 8 |
| 24hour | 4 | 4 |

Time clocks cannot be set to nonprogrammable mode.

It follows that changing between program modes and the number of levels will affect the operation of saved profiles. For this reason, changing program mode will automatically delete any saved profiles.

### Clear Current Profile

Thermostats and timeclocks use a profile id number to tell the neoHub what profiles they are currently using. This means the neoHub only needs to read the profile id to know what is stored in the profile structure within the device. It also means that editing the profile automatically edits the settings in all devices using that profile. Devices are effectively grouped by a shared profile.

To "remove" a device from this "group" you need to set its profile id to 0:

```json
{"CLEAR_CURRENT_PROFILE":"kitchen"}
```

> **Note:** The settings are not affected by this command. The user will then need to load the full set of comfort levels from the device.

### JSON Structures Within Profiles

The introduction of 6 levels forced a change in the layout of the structure from the original. `"wake, leave, return and sleep"` is still used for 4 comfort levels per day. `"wake, 1, 2, 3, 4, sleep"` is used for 6 comfort levels. This was done to maintain backward compatibility with older neoStat hardware.

**For neoHub firmware versions up to Version 2077**, the JSON structure for each comfort level is:

```json
"wake": ["07:00", 21]
```

**From version 2079 onwards**, this has changed to:

```json
"wake": ["10:00", 25.0, 0.0, false]
```

The variables are: `[time, temperature 1, temperature 2, enable temperature 2]`. The difference is due to upcoming products that support heating and cooling.

**4 levels per day (pre-2079):**

```json
{
  "sunday": {"wake":["07:00",21], "leave":["09:30",17], "return":["17:30",21], "sleep":["22:30",15]},
  "monday": {"wake":["07:00",14], "leave":["09:30",17], "return":["17:30",25], "sleep":["22:30",15]}
}
```

**6 levels per day (pre-2079):**

```json
{
  "monday": {
    "wake":["10:00",25], "level1":["17:00",14], "level2":["23:00",16],
    "level3":["22:00",15], "level4":["22:05",15], "sleep":["23:45",35]
  },
  "sunday": {
    "wake":["24:00",21], "level1":["24:00",23], "level2":["24:00",18],
    "level3":["24:00",21], "level4":["24:00",16], "sleep":["24:00",16]
  }
}
```

**4 levels (from version 2079):**

```json
{
  "sunday": {
    "wake":["07:00",21.0,0.0,false], "leave":["09:30",17.0,0.0,false],
    "return":["17:30",21.0,0.0,false], "sleep":["22:30",15.0,0.0,false]
  },
  "monday": {
    "wake":["07:00",14.0,0.0,false], "leave":["09:30",17.0,0.0,false],
    "return":["17:30",25.0,0.0,false], "sleep":["22:30",15.0,0.0,false]
  }
}
```

**6 levels (from version 2079):**

```json
{
  "monday": {
    "wake":["10:00",25.0,0.0,false], "level1":["17:00",14.0,0.0,false],
    "level2":["23:00",16.0,0.0,false], "level3":["22:00",14.0,0.0,false],
    "level4":["22:05",15.0,0.0,false], "sleep":["23:45",35.0,0.0,false]
  },
  "sunday": {
    "wake":["24:00",21.0,0.0,false], "level1":["24:00",23.0,0.0,false],
    "level2":["24:00",18.0,0.0,false], "level3":["24:00",21.0,0.0,false],
    "level4":["24:00",16.0,0.0,false], "sleep":["24:00",16.0,0.0,false]
  }
}
```

> **Note:** The temperatures are no longer integers -- this is to allow 0.5 degree set points to be implemented. In older hardware that cannot display the 0.5 degree set point the display will be rounded down.

The order of each level is not significant, but all levels must be included and match the neoHub settings. Complete tested examples for all modes are given in [Appendix A](#appendix-a---profile-examples).

### Saving Profiles

Profiles are stored in the neoHub using the `STORE_PROFILE` command.

> **WARNING: DO NOT USE `STORE_PROFILE` or `STORE_PROFILE2` WITH NEOSTAT HC. Use `STORE_PROFILE_0` instead.**

```json
{"STORE_PROFILE":{"info":{"sunday": {"wake":["07:00",21], "leave":["09:30",17], "return":["17:30",21], "sleep":["22:30",15]}, "monday": {"wake":["07:00",14], "leave":["09:30",17], "return":["17:30",25], "sleep":["22:30",15]}}, "name":"my profile"}}
```

Timer profile example:

```json
{"STORE_PROFILE":{"info": {"monday": {"time1": ["07:00","09:00"],"time2": ["16:00","20:00"],"time3": ["24:00","24:00"],"time4": ["24:00","24:00"]},"sunday": {"time1": ["07:00","09:00"],"time2": ["16:00","20:00"],"time3": ["24:00","24:00"],"time4": ["24:00","24:00"]}},"name": "my timer profile"}}
```

When saved they are automatically given a profile id number. This profile id can then be used to load the profile into a neoStat without sending all the data again.

**STORE_PROFILE2** -- Identical to Store Profile but returns the ID field in its response:

```json
{"STORE_PROFILE2":{"info":{"sunday": {"wake":["07:00",21], "leave":["09:30",17], "return":["17:30",21], "sleep":["22:30",15]}, "monday": {"wake":["07:00",14], "leave":["09:30",17], "return":["17:30",25], "sleep":["22:30",15]}}, "name":"my profile"}}
```

Returns:

```json
{"ID": 3, "result": "profile created"}
```

### Retrieving Profiles

```json
{"GET_PROFILE_NAMES":0}
```

Returns a list of profile names.

```json
{"GET_PROFILES":0}
```

Returns all the thermostat profiles complete with names and profile ids.

```json
{"GET_PROFILE_TIMERS":0}
```

Returns all the timeclock profiles complete with names and profile ids.

```json
{"GET_PROFILE":"kitchen"}
```

Returns the named profile:

```json
{
  "PROFILE_ID": 3,
  "group": null,
  "info": {
    "monday": {
      "leave": ["24:00",18,127.5,true], "return": ["24:00",23,127.5,true],
      "sleep": ["22:00",21,5,true], "wake": ["07:30",35,5,true]
    },
    "sunday": {
      "leave": ["24:00",18,127.5,true], "return": ["24:00",23,127.5,true],
      "sleep": ["22:00",21,5,true], "wake": ["07:30",35,5,true]
    }
  },
  "name": "kitchen"
}
```

Timer profile example:

```json
{"GET_PROFILE":"Timer"}
```

Returns:

```json
{
  "PROFILE_ID": 2,
  "group": null,
  "info": {
    "monday": {
      "time1": ["24:00","24:00"], "time2": ["24:00","24:00"],
      "time3": ["24:00","24:00"], "time4": ["24:00","24:00"]
    },
    "sunday": {
      "time1": ["07:30","09:00"], "time2": ["11:30","13:45"],
      "time3": ["16:15","18:00"], "time4": ["21:45","22:05"]
    }
  },
  "name": "Timer"
}
```

### Changing Profile Names

```json
{"PROFILE_TITLE":["old name","new name"]}
```

**Example:**

```json
{"PROFILE_TITLE":["Summer","Winter"]}
```

### Editing Profiles

To edit profiles, you must first load the profile then overwrite the existing data. The profile ID number and the profile's timestamp will be updated.

**Example:**

`GET_PROFILES` returns the original:

```json
{
  "ball": {
    "PROFILE_ID": 25,
    "info": {
      "monday": {"leave": ["09:30",17], "return": ["17:30",25], "sleep": ["22:30",15], "wake": ["07:00",14]},
      "sunday": {"leave": ["09:30",17], "return": ["17:30",21], "sleep": ["22:30",15], "wake": ["07:00",21]}
    },
    "name": "ball"
  }
}
```

Sending (with modifications):

```json
{"STORE_PROFILE": {"ID": 25, "info": {"monday": {"leave": ["09:30",17], "return": ["17:30",25], "sleep": ["22:30",15], "wake": ["01:00",14]}, "sunday": {"leave": ["09:30",17], "return": ["17:30",21], "sleep": ["22:30",15], "wake": ["07:00",21]}}, "name": "ball"}}
```

`GET_PROFILES` then returns the modified profile with the same profile id and the same name.

> **Note:** Using `PROFILE_ID` instead of `ID` in the store command will result in a different profile id number, which stops the devices from being updated.

### Activating Profiles

Once the profile ID is known it can be used with:

```json
{"RUN_PROFILE_ID":[25,"Kitchen","Lounge"]}
```

This will make the neoHub send the complete profile to each neoStat named in the command. The neoStats will report the profile id they are using in the live data field, eliminating the need to send the full profile more than once to the App.

### Deleting Profiles

Profiles can be deleted by name or ID number:

```json
{"CLEAR_PROFILE":"winter"}
{"CLEAR_PROFILE_ID":2}
```

### Profile 0

Comfort levels or switching times that have been programmed into a neoStat but have not been saved to the neoHub are always called profile_0. These profiles use the profile id of 0 which is reported as 0 in the live data field and indicates the need to read the device directly.

**GET_PROFILE_0** returns the data in the named thermostat:

```json
{"GET_PROFILE_0":"Bathroom"}
```

Returns:

```json
{
  "TIMESTAMP": 1518180429,
  "profiles": [{
    "device": "Bathroom",
    "monday": {"leave": ["09:30",17], "return": ["17:30",25], "sleep": ["22:30",15], "wake": ["07:00",14]},
    "sunday": {"leave": ["09:30",17], "return": ["17:30",21], "sleep": ["22:30",15], "wake": ["07:00",21]}
  }]
}
```

**GET_TIMER_0** returns the data in the named timeclock:

```json
{"GET_TIMER_0":"Timer"}
```

Returns:

```json
{
  "TIMESTAMP": 1518535946,
  "profiles": [{
    "device": "Office",
    "monday": {"time1": ["07:00","09:00"], "time2": ["16:00","20:00"], "time3": ["24:00","00:00"], "time4": ["24:00","00:00"]},
    "sunday": {"time1": ["07:00","09:00"], "time2": ["16:00","20:00"], "time3": ["24:00","00:00"], "time4": ["24:00","00:00"]}
  }]
}
```

### Saving Profiles Directly to the Device

**STORE_PROFILE_0** -- Stores the profile directly to the named thermostat:

```json
{"STORE_PROFILE_0":[{"sunday": {"wake":["07:00",22], "leave":["24:00",17],"return":["24:00",21], "sleep":["22:30",17]},"monday": {"wake":["07:00",34], "leave":["24:00",17],"return":["24:00",21], "sleep":["22:30",15]}},"bedroom1"]}
```

**STORE_PROFILE_TIMER_0** -- Stores the profile directly to the named timeclock:

```json
{"STORE_PROFILE_TIMER_0":[{"monday":{"time1":["01:11","09:00"],"time2":["16:00","20:00"],"time3":["24:00","00:00"],"time4":["24:00","00:00"]},"sunday":{"time1":["07:00","09:00"],"time2":["16:00","20:00"],"time3":["24:00","00:00"],"time4":["24:00","00:00"]}},"Office"]}
```

The following profile commands have been deprecated. The original profile command structure included the target devices within it. The newer profiles structure does not. For backward compatibility these commands are still valid:

- `{"STORE_PROFILE":"<profile ob>"}` -- deprecated
- `{"CLEAR_PROFILE":"<profile name>"}` -- deprecated
- `{"GET_PROFILE":"<profile name>"}` -- deprecated
- `{"RUN_PROFILE":"<profile name>"}` -- deprecated
- `{"GET_PROFILE_NAMES":0}` -- deprecated

---

## Boost Function

Used to turn a timeclock on or off which overrides the schedule for a fixed length of time. To turn it on when its off use `BOOST_ON`. To turn it off when its on use `BOOST_OFF`.

```json
{"BOOST_ON":[{"hours":1,"minutes":10},["floor1","clock"]]}
```

To cancel:

```json
{"BOOST_ON":[{"hours":0,"minutes":0},["floor1","clock"]]}
```

```json
{"BOOST_OFF":[{"hours":1,"minutes":10},["floor1","clock"]]}
```

To cancel:

```json
{"BOOST_OFF":[{"hours":0,"minutes":0},["floor1","clock"]]}
```

---

## Engineers Settings

Engineers settings are those found in the neoStat feature menu that is accessed on the device itself through the setup menu. Changing these settings affects the target device only. Settings that must be done during installation only are not available. Some of these settings can be edited remotely:

```json
{"SET_DIFF":[2,["test"]]}
```

Adjust the switching differential in the thermostat to 2 degrees.

```json
{"SET_FLOOR":[28, "floor1"]}
```

Sets the upper limit to the floor temperature.

```json
{"SET_PREHEAT":[3,["test"]]}
```

Sets the maximum preheat time in the optimization function.

```json
{"SET_FROST":[9,"test"]}
```

Sets the frost protection temperature.

```json
{"SET_DELAY":[5, "test"]}
```

Sets the output delay in minutes.

### Failsafe

Used on neoAir thermostats to enable the failsafe function in the radio signal sent to the Rf Switch and UH8-RF radio receivers. If no signal is received for 50 minutes, failsafe brings on the heating for 12 minutes every hour.

```json
{"SET_FAILSAFE":[true, "neoair"]}
{"SET_FAILSAFE":[false, "neoair"]}
```

**Firmware version:**

```json
{"FIRMWARE":0}
```

Returns the neoHub firmware version.

---

## Groups

Groups different zones under a command group name. Allows a single command to be sent to all devices in the group.

```json
{"CREATE_GROUP":[["lounge","bed1"], "bob"]}
```

This puts the "lounge" and "bed1" in the "bob" group. Any command sent to "bob" will be sent to the lounge and bed1.

```json
{"GET_GROUPS":0}
```

Returns a list of groups.

```json
{"DELETE_GROUP":"bob"}
```

Deletes the group "bob" but has no effect on the members of the group.

```json
{"CANCEL_HGROUP":"<group>"}
```

Cancels the holds in any group.

---

## Hold Function

Tells a thermostat to maintain the current temperature for a fixed time. To allow different holds across a system, they can be named -- this is the "id" field in the JSON.

**To hold the heating temperature:**

```json
{"HOLD":[{"temp":16, "hours":2, "minutes":30, "id":"Box"}, ["<devices>"]]}
```

**To hold the cooling temperature:**

```json
{"HOLD":[{"cool":24, "hours":2, "minutes":30, "id":"Box"}, ["<devices>"]]}
```

**To hold both heating and cooling temperatures:**

```json
{"HOLD":[{"temp":16, "cool":24, "hours":2, "minutes":30, "id":"Box"}, ["<devices>"]]}
```

**To cancel:**

```json
{"HOLD":[{"temp":16, "cool":24, "hours":0, "minutes":0, "id":"Box"}, ["<devices>"]]}
```

The neoHub will read the hold time and if 00, cancel the hold (the other variables will be ignored).

### Cancelling Holds

```json
{"CANCEL_HOLD_ALL":0}
```

Cancels all hold commands.

```json
{"CANCEL_HGROUP":"id"}
```

Cancels the specific groups of holds.

```json
{"GET_HOLD":0}
```

Returns the active holds set by the App but not those set on the device.

---

## Identify

Used to identify a device on the system. Introduced for Homekit compliance but can be used directly.

```json
{"IDENTIFY":0}
```

This command flashes the link LED on the neoHub. To be used correctly it needs to be sent to the correct IP address for the neoHub. It is therefore best used as confirmation that you have the correct IP address.

```json
{"IDENTIFY_DEV":"test"}
```

This command flashes the LCD backlight on neoStats connected to a neoHub. It serves to indicate which physical device matches the name.

---

## INFO Command

```json
{"INFO":0}
```

> Deprecated. Use `{"GET_LIVE_DATA":0}` instead.

---

## Lock Command

This command pin locks the thermostats. This command can be used in conjunction with the user limit to allow limited access to the device.

```json
{"LOCK":[[1,2,3,4], ["Bathroom","kitchen"]]}
```

Locks both the Bathroom and kitchen neoStat's with pin number 1234.

```json
{"UNLOCK":["Bathroom","kitchen"]}
```

Will unlock both the bathroom and the kitchen.

---

## Standby Function

The standby function was initially called frost protection on, which automatically disabled the schedule and enabled frost protection.

```json
{"FROST_ON":"<device(s)>"}
```

Disables the schedule and sets the target temperature to the preset frost protection temperature.

> **Note:** When this is active the highest temperature that can be set is 17 degrees Celsius.

**Example:**

```json
{"FROST_ON":["bed1","lounge"]}
```

For timeclocks it disables the schedule and turns the output off.

```json
{"FROST_OFF":["bed1","lounge"]}
```

Cancels frost protection and reinstates the schedule.

---

## Summer

A variation of the Frost command. It was originally used to put all thermostats into frost protection but has no effect on time clocks.

```json
{"SUMMER_ON":["lounge","bed1"]}
{"SUMMER_OFF":["Bathroom"]}
```

---

## Statistics

```json
{"GET_HOURSRUN":"<devices>"}
```

Returns the number of hours each day the output was on in the named device.

**Example:**

```json
{"GET_HOURSRUN":"Kitchen"}
```

Returns:

```json
{
  "day:1": {"Kitchen": 0}, "day:2": {"Kitchen": 0}, "day:3": {"Kitchen": 9},
  "day:4": {"Kitchen": 12}, "day:5": {"Kitchen": 2}, "day:6": {"Kitchen": 4},
  "day:7": {"Kitchen": 3}, "today": {"Kitchen": 12}
}
```

```json
{"GET_TEMPLOG":"<device(s)>"}
```

Returns the temperature reading for the previous 7 days and up to the current time in 15-minute intervals.

**Example:**

```json
{"GET_TEMPLOG":["Kitchen"]}
```

Returns 96 temperature readings per day for the last 8 days (7 + today).

> `{"STATISTICS":0}` -- deprecated, do not use.

---

## Home Kit

`"Homekit": true` -- This flag indicates the neoHub is compatible with Apple HomeKit. For details on how to use the HomeKit features please contact Apple. The absence of this flag indicates the device is not compatible.

> **Note:** This flag will be deprecated and replaced by a `HUB_TYPE` variable.

Currently there are 2 types: G1 and G2, where G2 is HomeKit compatible. Others are expected to be added.

`HUB_TYPE` variable can be found in the system cache and server login data. It identifies 3 distinct types of device:

| HUB_TYPE | Description |
|----------|-------------|
| 1 | Generation 1 neoHub |
| 2 | Generation 2 neoHub |
| 3 | neoHub Mini |

---

## Timeclock Commands

Commands specific to time clocks and neoPlug's.

### TIMER_HOLD_ON

If a device output is currently off or unknown, this command will override it on for the stated time. The schedule will be ignored.

```json
{"TIMER_HOLD_ON":[15, "clock"]}
```

To cancel:

```json
{"TIMER_HOLD_ON":[0, "clock"]}
```

### TIMER_HOLD_OFF

If a device output is currently on or unknown, this command will override it off for the stated time. The schedule will be ignored.

```json
{"TIMER_HOLD_OFF":[15, "clock"]}
```

To cancel:

```json
{"TIMER_HOLD_OFF":[0, "clock"]}
```

---

## NeoPlug Commands

The neoPlugs use the same structure as any of the timeclocks and therefore use the same commands with the addition of the on/off command.

```json
{"MANUAL_ON":"<devices>"}
```

Disables the timeclock built into the neoPlug.

```json
{"MANUAL_OFF":"<devices>"}
```

Reinstates the timeclock built into the neoPlug.

Disabling the timeclock turns the neoPlug into a simple on/off device with no schedule. It can then be directly controlled with:

```json
{"TIMER_ON":"plug"}
```

Turns the output on.

```json
{"TIMER_OFF":"plug"}
```

Turns the output off.

---

## Timeclock Switching Times

Returns the full set of programmed on/off times from a neoStat, neoPlug or NeoAir.

> **Note:** When a neoAir is operating in combined mode a full set of comfort levels and switching times is available in the device. The neoHub will treat it as 2 different devices so this command will only return the time clock settings.

### READ_TIMECLOCK

```json
{"READ_TIMECLOCK":"<device(s)>"}
```

Returns an object with keys named after the requested devices. The values will be objects with weekday names as keys, of which the value will be another object with keys `time1`, `time2`, `time3` and `time4`. The values there will be an array with the start and end time for that period:

```json
{
  "kitchen": {
    "monday": {"time1":["01:00","02:00"], "time2":["03:00","04:00"], "time3":["05:00","06:01"], "time4":["12:34","15:59"]},
    "tuesday": {"time1":["01:00","02:00"], "time2":["03:00","04:00"], "time3":["05:00","06:01"], "time4":["12:34","15:59"]},
    "wednesday": {"time1":["01:00","02:00"], "time2":["03:00","04:00"], "time3":["05:00","06:01"], "time4":["12:34","15:59"]},
    "thursday": {"time1":["07:00","09:00"], "time2":["16:00","20:00"], "time3":["24:00","00:00"], "time4":["24:00","00:00"]},
    "friday": {"time1":["07:00","09:00"], "time2":["16:00","20:00"], "time3":["24:00","00:00"], "time4":["24:00","00:00"]},
    "saturday": {"time1":["07:00","09:00"], "time2":["16:00","20:00"], "time3":["24:00","00:00"], "time4":["24:00","00:00"]},
    "sunday": {"time1":["01:00","02:00"], "time2":["03:00","04:00"], "time3":["05:00","06:01"], "time4":["12:34","15:59"]}
  }
}
```

**Example:**

```json
{"READ_TIMECLOCK":"Hot water"}
```

### SET_TIMECLOCK

```json
{"SET_TIMECLOCK":["<levels>", "<device(s)>"]}
```

For `<levels>` see `READ_TIMECLOCK` result format.

**Example:**

```json
{"SET_TIMECLOCK":[{"monday":{"time1":["01:00","02:00"],"time2":["03:00","04:00"],"time3":["05:00","06:01"],"time4":["12:34","15:59"]},"sunday":{"time1":["01:00","02:00"],"time2":["03:00","04:00"],"time3":["05:00","06:01"],"time4":["12:34","15:59"]}}, "kitchen"]}
```

---

## User Limit

The user limit sets a range limit for the target temperature settings. Any non-zero number sets the limit to that value.

So, if the programmed temperature is 20 degrees and the user limit is set to 2, then the user can only adjust the target temperature up or down by 2 degrees using the buttons on the thermostat.

When the thermostat is locked, the user limit allows minor adjustments to the target temperature without the need to unlock the device. This function is useful in public areas or children's rooms.

Setting the user limit to 0 removes the restrictions on unlocked thermostats and reinstates the lock on locked devices so that a pin number is always required to change the temperature.

**Example:**

```json
{"USER_LIMIT":[5, ["bed1","lounge"]]}
```

To cancel:

```json
{"USER_LIMIT":[0, ["bed1","lounge"]]}
```

---

## Optimisation

Calculates how long it will take for a room to reach the next comfort level target temperature. If enabled the thermostat will start preheating the room before the programmed switching time to ensure it reaches the desired temperature at the stated time.

The user can set a maximum pre heat period to ensure they are not disturbed by the heating system starting up too early in the morning:

```json
{"SET_PREHEAT":[3, "Bathroom"]}
```

Sets maximum preheat time to 3 hours.

### ROC

ROC is the rate of change -- this is the time it takes the heating system to raise the room temperature by 1 degree. It is used in the optimum start function and is recalculated at every comfort level.

The calculated value can be viewed on the device itself or by using:

```json
{"VIEW_ROC":["Bathroom1","HCtest"]}
```

Returns the calculated rate of change for these rooms in minutes per degree.

---

## Recipes

Recipes are a list of individual commands that are named and were originally stored in peoples' phones. These recipes are now stored in the neoHub.

```json
{"STORE_RECIPE":["<name>", ["<commands>"], ["<default devices>"]]}
```

Recipes include a list of commands and devices. To link the two together, replace the device names in the command list with the variable `DEVICES`. The store recipe command includes a list of default devices -- these devices can be referenced using the zone title or device number.

**Example:**

```json
{"STORE_RECIPE":["test4",["{\"SET_TEMP\":[30,DEVICES]}", "{\"LOCK\":[[1,2,3,4],DEVICES]}"],["kitchen", "lounge"]]}
```

Or using device IDs:

```json
{"STORE_RECIPE":["test3",["{\"SET_TEMP\":[30,DEVICES]}", "{\"LOCK\":[[1,2,3,4],DEVICES]}"],[5,6]]}
```

The last section contains the default device ID numbers. Internally the neoHub will automatically insert the target device ID numbers in the DEVICES variable.

**Running recipes:**

```json
{"RUN_RECIPE":["test2"]}
```

Runs on the default devices.

```json
{"RUN_RECIPE":["test2", ["living room","kitchen"]]}
```

Runs the recipe on the living room and kitchen.

**Deleting recipes:**

```json
{"DELETE_RECIPE":"<name>"}
```

**Getting recipes:**

```json
{"GET_RECIPES":0}
```

Returns a list of recipe names and their contents.

**Editing recipes:** To edit a recipe, it is necessary to copy the original, modify it, delete the original, then save the new version. The Hub will allow duplicate recipe names but will ignore all but the last one to be created. Deleting a recipe will delete all recipes with the same name.

---

## Set Temperature

Used to adjust the thermostat's set temperature. This setting is temporary and will be reset when the next comfort level is reached. If you need to adjust the temperature beyond this time then use the hold command.

> **Note:** This does not apply in nonprogrammable mode.

```json
{"SET_TEMP":[9.0,"Zone 3"]}
{"SET_TEMP":[34.5,["Zone 3","Zone 4"]]}
```

Will set Zone 3 and Zone 4 to 34.5 degrees.

---

## NeoStat HC Commands

### Cooling

Changes have been made in the structure of profiles to allow for the introduction of the neoStat HC -- a heating and cooling fan coil thermostat. To use these devices the neoHub firmware must be up to date.

The most significant change is in the JSON structure of the comfort levels. The new structure is composed of set temperatures which can be set in 0.5 degree increments. The structure format is:

```
[time, heating temperature, cooling temperature, cooling enabled]
```

**Example:**

```json
"wake": ["10:00", 25.0, 28.0, true]
```

The profile 0 examples in [Appendix A](#appendix-a---profile-examples) show the complete structures including the cooling variables. Mixing existing neoStat and neoStat HC devices on the same system is allowed -- the neoStat's will just ignore the cooling information.

The neoStat HC is designed to work with different types of heating and cooling systems. But every device on the system must be in the same mode or they all must be completely independent.

Regardless of the different systems, the neoStat can be in 1 of 3 modes: Heating or cooling, cooling only, and independent. The Neo system needs to be set up to match.

### Setting Up the System

**Step 1:** Set up the Global System type:

```json
{"GLOBAL_SYSTEM_TYPE":"HeatOrCool"}
```

Allows the neoStat HC to be in heating or cooling mode. Normally used for 2-pipe district heating systems which provide heat in the winter and cooling in the summer.

```json
{"GLOBAL_SYSTEM_TYPE":"CoolOnly"}
```

Allows the neoStat HC to be in cooling mode only. Normally used for 2-pipe cooling systems which only provide cooling.

```json
{"GLOBAL_SYSTEM_TYPE":"Independent"}
```

Allows the neoStat HC's to be in any mode required for the system on a room by room basis. Should also be used with mixed systems.

These are global settings and will affect the entire system and limit the choices in Step 2.

**Step 2:** Adjust the neoHub settings as required.

For `HeatOrCool`:

```json
{"SET_GLOBAL_HC_MODE":"heating"}
{"SET_GLOBAL_HC_MODE":"cooling"}
```

For `CoolOnly`:

```json
{"SET_GLOBAL_HC_MODE":"cooling"}
```

For `Independent`:

```json
{"SET_GLOBAL_HC_MODE":"heating"}
{"SET_GLOBAL_HC_MODE":"cooling"}
{"SET_GLOBAL_HC_MODE":"auto"}
```

These are global settings and will affect the entire system and limit the choices in Step 3.

Step 3 is automatically carried out by Step 2 for heating and cooling systems and cooling only systems. But must be carried out for independent systems.

**Step 3:** Set the mode on the individual thermostats:

```json
{"SET_HC_MODE":["COOLING", ["Device1","device2","device3","deviceN"]]}
{"SET_HC_MODE":["HEATING", ["Device1","device2","device3","deviceN"]]}
{"SET_HC_MODE":["AUTO", ["Device1","device2","device3","deviceN"]]}
{"SET_HC_MODE":["VENT", ["Device1","device2","device3","deviceN"]]}
```

- **COOLING** -- Sets the HC to cooling mode
- **HEATING** -- Sets the HC to heating mode
- **AUTO** -- Sets the HC to auto mode which means it can heat or cool the room as required
- **VENT** -- Runs the fan on the fan coil without heating or cooling the room. Used to circulate air in the room or draw in air from the outside.

VENT mode is always available regardless of the system settings in Step 1 and Step 2. The stat will alternate between vent mode and heating or cooling depending on the settings in Step 2.

The neoStat HC will respond to all normal commands. However, if the target temperature is set to 36 or above it will disable cooling for that level. The lowest cooling temperature that can be set is 18 degrees C.

### HC-Specific Commands

**Set cooling temperature:**

```json
{"SET_COOL_TEMP":[27.5,"HCtest"]}
{"SET_COOL_TEMP":[27,["device1","device2","device3","deviceN"]]}
```

**Set fan speed:**

```json
{"SET_FAN_SPEED":["HIGH",["device1","device2","device3","deviceN"]]}
{"SET_FAN_SPEED":["AUTO",["device1","device2","device3","deviceN"]]}
{"SET_FAN_SPEED":["MED",["device1","device2","device3","deviceN"]]}
{"SET_FAN_SPEED":["LOW",["device1","device2","device3","deviceN"]]}
{"SET_FAN_SPEED":["OFF",["device1","device2","device3","deviceN"]]}
```

> **Note:** In Vent mode, automatic control is disabled.

**Disable automatic fan speed control:**

```json
{"AUTO_MODE_OFF":["Device1","device2","device3","deviceN"]}
```

Will disable the automatic fan speed control but leave the fan running at its current speed.

> **WARNING:** The neoStat HC devices do not use profiles, which means the `STORE_PROFILE` and `STORE_PROFILE2` commands do not work. Use `STORE_PROFILE_0`.

---

## Appendix A - Profile Examples

Worked examples of profile 0 and named profiles for each of the programmable modes and 4 and 6 levels.

### Profile 0 Examples

#### 4 Levels

**5/2 day:**

```json
{"STORE_PROFILE_0":[{
  "monday": {
    "wake":["07:00",21,127.5,true], "leave":["09:00",16,127.5,true],
    "return":["16:00",21,127.5,true], "sleep":["22:00",16,127.5,true]
  },
  "sunday": {
    "wake":["07:00",21,127.5,true], "leave":["09:00",16,127.5,true],
    "return":["16:00",21,127.5,true], "sleep":["22:00",16,127.5,true]
  }
}, ["Device Name"]]}
```

**24 hour:**

```json
{"STORE_PROFILE_0":[{
  "sunday": {
    "wake":["07:00",21,127.5,true], "leave":["09:00",16,127.5,true],
    "return":["16:00",21,127.5,true], "sleep":["22:00",16,127.5,true]
  }
}, ["Device Name"]]}
```

**7 day:**

```json
{"STORE_PROFILE_0":[{
  "monday": {"wake":["07:00",21,127.5,true], "leave":["09:00",16,127.5,true], "return":["16:00",21,127.5,true], "sleep":["22:00",16,127.5,true]},
  "tuesday": {"wake":["07:00",21,127.5,true], "leave":["09:00",16,127.5,true], "return":["16:00",21,127.5,true], "sleep":["22:00",16,127.5,true]},
  "wednesday": {"wake":["07:00",21,127.5,true], "leave":["09:00",16,127.5,true], "return":["16:00",21,127.5,true], "sleep":["22:00",16,127.5,true]},
  "thursday": {"wake":["07:00",21,127.5,true], "leave":["09:00",16,127.5,true], "return":["16:00",21,127.5,true], "sleep":["22:00",16,127.5,true]},
  "friday": {"wake":["07:00",21,127.5,true], "leave":["09:00",16,127.5,true], "return":["16:00",21,127.5,true], "sleep":["22:00",16,127.5,true]},
  "saturday": {"wake":["07:00",21,127.5,true], "leave":["09:00",16,127.5,true], "return":["16:00",21,127.5,true], "sleep":["22:00",16,127.5,true]},
  "sunday": {"wake":["07:00",21,127.5,true], "leave":["09:00",16,127.5,true], "return":["16:00",21,127.5,true], "sleep":["22:00",16,127.5,true]}
}, ["Device Name"]]}
```

#### 6 Levels

**5/2 Day:**

```json
{"STORE_PROFILE_0":[{
  "monday": {
    "wake":["07:00",21,127.5,true], "level1":["09:00",16,127.5,true],
    "level2":["16:00",21,127.5,true], "level3":["22:00",16,127.5,true],
    "level4":["24:00",16,127.5,true], "sleep":["24:00",16,127.5,true]
  },
  "sunday": {
    "wake":["09:00",21,127.5,true], "level1":["22:00",16,127.5,true],
    "level2":["24:00",21,127.5,true], "level3":["24:00",16,127.5,true],
    "level4":["24:00",16,127.5,true], "sleep":["24:00",16,127.5,true]
  }
}, ["device Name"]]}
```

**24 hour:**

```json
{"STORE_PROFILE_0":[{
  "sunday": {
    "wake":["09:00",21,127.5,true], "level1":["22:00",16,127.5,true],
    "level2":["24:00",21,127.5,true], "level3":["24:00",16,127.5,true],
    "level4":["24:00",16,127.5,true], "sleep":["24:00",16,127.5,true]
  }
}, ["device Name"]]}
```

**7 day:**

```json
{"STORE_PROFILE_0":[{
  "monday": {"wake":["07:00",21,127.5,true], "level1":["09:00",16,127.5,true], "level2":["16:00",21,127.5,true], "level3":["22:00",16,127.5,true], "level4":["24:00",16,127.5,true], "sleep":["24:00",16,127.5,true]},
  "tuesday": {"wake":["07:00",21,127.5,true], "level1":["09:00",16,127.5,true], "level2":["16:00",21,127.5,true], "level3":["22:00",16,127.5,true], "level4":["24:00",16,127.5,true], "sleep":["24:00",16,127.5,true]},
  "wednesday": {"wake":["07:00",21,127.5,true], "level1":["09:00",16,127.5,true], "level2":["16:00",21,127.5,true], "level3":["22:00",16,127.5,true], "level4":["24:00",16,127.5,true], "sleep":["24:00",16,127.5,true]},
  "thursday": {"wake":["07:00",21,127.5,true], "level1":["09:00",16,127.5,true], "level2":["16:00",21,127.5,true], "level3":["22:00",16,127.5,true], "level4":["24:00",16,127.5,true], "sleep":["24:00",16,127.5,true]},
  "friday": {"wake":["07:00",21,127.5,true], "level1":["09:00",16,127.5,true], "level2":["16:00",21,127.5,true], "level3":["22:00",16,127.5,true], "level4":["24:00",16,127.5,true], "sleep":["24:00",16,127.5,true]},
  "saturday": {"wake":["09:00",21,27.5,true], "level1":["22:00",16,127.5,true], "level2":["24:00",21,127.5,true], "level3":["24:00",16,127.5,true], "level4":["24:00",16,127.5,true], "sleep":["24:00",16,127.5,true]},
  "sunday": {"wake":["09:00",21,127.5,true], "level1":["22:00",16,127.5,true], "level2":["24:00",21,127.5,true], "level3":["24:00",16,127.5,true], "level4":["24:00",16,127.5,true], "sleep":["24:00",16,127.5,true]}
}, ["device Name"]]}
```

### Named Profile Examples

#### 4 Levels

**5/2 day:**

```json
{"STORE_PROFILE": {"info": {
  "sunday": {"wake": ["10:00",10.0,25.0,true], "leave": ["11:00",11.0,25.0,true], "return": ["12:00",12.0,25.0,true], "sleep": ["13:00",13.0,25.0,true]},
  "monday": {"wake": ["15:00",15.0,25.0,true], "leave": ["16:00",16.0,25.0,true], "return": ["17:00",17.0,25.0,true], "sleep": ["18:00",18.0,25.0,true]}
}, "name": "Test21"}}
```

**24 hour:**

```json
{"STORE_PROFILE": {"info": {
  "sunday": {"wake": ["10:00",10.0,25.0,true], "leave": ["11:00",11.0,25.0,true], "return": ["12:00",12.0,25.0,true], "sleep": ["13:00",13.0,25.0,true]}
}, "name": "Test23"}}
```

**7 day:**

```json
{"STORE_PROFILE": {"info": {
  "sunday": {"wake": ["10:00",10.0,25.0,true], "leave": ["11:00",11.0,25.0,true], "return": ["12:00",12.0,25.0,true], "sleep": ["13:00",13.0,25.0,true]},
  "monday": {"wake": ["15:00",15.0,25.0,true], "leave": ["16:00",16.0,25.0,true], "return": ["17:00",17.0,25.0,true], "sleep": ["18:00",18.0,25.0,true]},
  "tuesday": {"wake": ["15:00",15.0,25.0,true], "leave": ["16:00",16.0,25.0,true], "return": ["17:00",17.0,25.0,true], "sleep": ["18:00",18.0,25.0,true]},
  "wednesday": {"wake": ["15:00",15.0,25.0,true], "leave": ["16:00",16.0,25.0,true], "return": ["17:00",17.0,25.0,true], "sleep": ["18:00",18.0,25.0,true]},
  "thursday": {"wake": ["15:00",15.0,25.0,true], "leave": ["16:00",16.0,25.0,true], "return": ["17:00",17.0,25.0,true], "sleep": ["18:00",18.0,25.0,true]},
  "friday": {"wake": ["15:00",15.0,25.0,true], "leave": ["16:00",16.0,25.0,true], "return": ["17:00",17.0,25.0,true], "sleep": ["18:00",18.0,25.0,true]},
  "saturday": {"wake": ["15:00",15.0,25.0,true], "leave": ["16:00",16.0,25.0,true], "return": ["17:00",17.0,25.0,true], "sleep": ["18:00",18.0,25.0,true]}
}, "name": "Test24"}}
```

#### 6 Levels

**5/2 day:**

```json
{"STORE_PROFILE": {"info": {
  "sunday": {"wake": ["09:00",16.0,25.0,true], "level1": ["10:00",11.0,25.0,true], "level2": ["11:00",12.0,25.0,true], "level3": ["12:00",13.0,25.0,true], "level4": ["13:00",14.0,25.0,true], "sleep": ["14:00",15.0,25.0,true]},
  "monday": {"wake": ["15:00",21.0,25.0,true], "level1": ["16:00",15.0,25.0,true], "level2": ["17:00",17.0,25.0,true], "level3": ["18:00",18.0,25.0,true], "level4": ["19:00",19.0,25.0,true], "sleep": ["20:00",20.0,25.0,true]}
}, "name": "Test8"}}
```

**24 hour:**

```json
{"STORE_PROFILE": {"info": {
  "sunday": {"wake": ["09:00",15.0,25.0,true], "level1":["10:00",15.0,25.0,true], "level2": ["11:00",15.0,25.0,true], "level3": ["12:00",15.0,25.0,true], "level4": ["13:00",15.0,25.0,true], "sleep": ["14:00",15.0,25.0,true]}
}, "name": "Test1"}}
```

**7 day:**

```json
{"STORE_PROFILE": {"info": {
  "sunday": {"wake": ["10:00",15.0,25.0,true], "level1": ["10:00",15.0,25.0,true], "level2": ["10:00",15.0,25.0,true], "level3": ["10:00",15.0,25.0,true], "level4": ["10:00",15.0,25.0,true], "sleep": ["10:00",15.0,25.0,true]},
  "monday": {"wake": ["10:00",15.0,25.0,true], "level1": ["10:00",15.0,25.0,true], "level2": ["10:00",15.0,25.0,true], "level3": ["10:00",15.0,25.0,true], "level4": ["10:00",15.0,25.0,true], "sleep": ["10:00",15.0,25.0,true]},
  "tuesday": {"wake": ["01:00",10.0,25.0,true], "level1": ["02:00",12.0,25.0,true], "level2": ["03:00",13.0,25.0,true], "level3": ["04:00",14.0,25.0,true], "level4": ["05:00",15.0,25.0,true], "sleep": ["06:00",16.0,25.0,false]},
  "wednesday": {"wake": ["10:00",15.0,25.0,true], "level1": ["10:00",15.0,25.0,true], "level2": ["10:00",15.0,25.0,true], "level3": ["10:00",15.0,25.0,true], "level4": ["10:00",15.0,25.0,true], "sleep": ["10:00",15.0,25.0,true]},
  "thursday": {"wake": ["10:00",15.0,25.0,true], "level1": ["10:00",15.0,25.0,true], "level2": ["10:00",15.0,25.0,true], "level3": ["10:00",15.0,25.0,true], "level4": ["10:00",15.0,25.0,true], "sleep": ["10:00",15.0,25.0,true]},
  "friday": {"wake": ["10:00",10.0,25.0,true], "level1": ["11:00",16.0,25.0,true], "level2": ["12:00",11.0,25.0,true], "level3": ["13:00",12.0,25.0,true], "level4": ["14:00",13.0,25.0,true], "sleep": ["15:00",14.0,25.0,true]},
  "saturday": {"wake": ["09:00",09.0,25.0,true], "level1": ["11:00",11.0,25.0,true], "level2": ["12:00",12.0,25.0,true], "level3": ["13:00",13.0,25.0,true], "level4": ["14:00",13.0,25.0,true], "sleep": ["15:00",15.0,25.0,true]}
}, "name": "Test2"}}
```

### Editing Profiles Example

To edit profiles, load the original, edit it and save. Please note the profile ID number changes.

> **Note:** To use any of the above profiles, make sure you change the profile's name or create a zone with the same name.

1. **Get the original:**

```json
{"ball": {"PROFILE_ID": 25, "info": {"monday": {"leave": ["09:30",17], "return": ["17:30",25], "sleep": ["22:30",15], "wake": ["07:00",14]}, "sunday": {"leave": ["09:30",17], "return": ["17:30",21], "sleep": ["22:30",15], "wake": ["07:00",21]}}, "name": "ball"}}
```

2. **Edit and store it:**

```json
{"STORE_PROFILE": {"ID": 25, "info": {"monday": {"leave": ["09:30",17], "return": ["17:30",25], "sleep": ["22:30",15], "wake": ["01:00",14]}, "sunday": {"leave": ["09:30",17], "return": ["17:30",21], "sleep": ["22:30",15], "wake": ["07:00",21]}}, "name": "ball"}}
```

3. **Get the updated copy:**

```json
{"ball": {"PROFILE_ID": 25, "info": {"monday": {"leave": ["09:30",17], "return": ["17:30",25], "sleep": ["22:30",15], "wake": ["01:00",14]}, "sunday": {"leave": ["09:30",17], "return": ["17:30",21], "sleep": ["22:30",15], "wake": ["01:00",21]}}, "name": "ball"}}
```

### Default Profile 0 Examples (0.5 Degree)

**7 day mode:**

```json
{
  "STORE_PROFILE_0": [{
    "monday": {"wake": ["07:15",20.5,0,false], "leave": ["09:15",13.5,0,false], "return": ["16:15",21.5,0,false], "sleep": ["22:15",13.5,0,false]},
    "tuesday": {"wake": ["07:15",21.5,0,false], "leave": ["09:15",13.5,0,false], "return": ["16:15",21.5,0,false], "sleep": ["22:15",13.5,0,false]},
    "wednesday": {"wake": ["07:15",21.5,0,false], "leave": ["09:15",13.5,0,false], "return": ["16:15",21.5,0,false], "sleep": ["22:15",13.5,0,false]},
    "thursday": {"wake": ["07:15",21.5,0,false], "leave": ["09:15",13.5,0,false], "return": ["16:15",21.5,0,false], "sleep": ["22:15",13.5,0,false]},
    "friday": {"wake": ["07:15",21.5,0,false], "leave": ["09:15",13.5,0,false], "return": ["16:15",21.5,0,false], "sleep": ["22:15",13.5,0,false]},
    "saturday": {"wake": ["09:15",21.5,0,false], "leave": ["17:15",13.5,0,false], "return": ["21:15",21.5,0,false], "sleep": ["24:15",13.5,0,false]},
    "sunday": {"wake": ["09:15",20.5,0,false], "leave": ["16:15",13.5,0,false], "return": ["19:10",21.5,0,false], "sleep": ["23:05",13.5,0,false]}
  }, "device name"]
}
```

**5/2 day mode:**

> **Note:** Monday is all weekdays, Sunday is all weekend.

```json
{
  "STORE_PROFILE_0": [{
    "monday": {"wake": ["07:15",20.5,0,false], "leave": ["09:15",13.5,0,false], "return": ["16:15",21.5,0,false], "sleep": ["22:15",13.5,0,false]},
    "sunday": {"wake": ["09:15",20.5,0,false], "leave": ["16:15",13.5,0,false], "return": ["19:10",21.5,0,false], "sleep": ["23:05",13.5,0,false]}
  }, "device name"]
}
```

**24 hour mode:**

```json
{
  "STORE_PROFILE_0": [{
    "sunday": {"wake": ["09:15",20.5,0,false], "leave": ["16:15",13.5,0,false], "return": ["19:10",21.5,0,false], "sleep": ["23:05",13.5,0,false]}
  }, "device name"]
}
```

---

## Appendix B - Deprecated Commands

The following commands have been deprecated. For backward compatibility these commands are still valid but should not be used in new designs.

| Command | Syntax |
|---------|--------|
| INFO | `{"INFO":0}` |
| ENGINEERS_DATA | `{"ENGINEERS_DATA":0}` |
| STORE_PROFILE | `{"STORE_PROFILE":"<profile ob>"}` |
| CLEAR_PROFILE | `{"CLEAR_PROFILE":"<profile name>"}` |
| GET_PROFILE | `{"GET_PROFILE":"<profile name>"}` |
| RUN_PROFILE | `{"RUN_PROFILE":"<profile name>"}` |
| GET_PROFILE_NAMES | `{"GET_PROFILE_NAMES":0}` |

---

## Appendix C - Alphabetical Command List

| Command | Syntax |
|---------|--------|
| AUTO_MODE_OFF | `{"AUTO_MODE_OFF":"HCtest"}` |
| AWAY_OFF | `{"AWAY_OFF":"<device(s)>"}` |
| AWAY_ON | `{"AWAY_ON":"<device(s)>"}` |
| BOOST_OFF | `{"BOOST_OFF":[{"hours":0,"minutes":10},"<devices>"]}` |
| BOOST_ON | `{"BOOST_ON":[{"hours":0,"minutes":10},"<devices>"]}` |
| CANCEL_HGROUP | `{"CANCEL_HGROUP":"<group>"}` |
| CANCEL_HOLD_ALL | `{"CANCEL_HOLD_ALL":0}` |
| CANCEL_HOLIDAY | `{"CANCEL_HOLIDAY":0}` |
| CLEAR_CURRENT_PROFILE | `{"CLEAR_CURRENT_PROFILE":"<devices>"}` |
| CLEAR_DEVICE_LIST | `{"CLEAR_DEVICE_LIST":"<device>"}` |
| CLEAR_PROFILE | `{"CLEAR_PROFILE":"<profile name>"}` |
| CLEAR_PROFILE_ID | `{"CLEAR_PROFILE_ID":"<number>"}` |
| CREATE_GROUP | `{"CREATE_GROUP":[["<devices>"], "<name>"]}` |
| DELETE_GROUP | `{"DELETE_GROUP":"<group>"}` |
| DELETE_RECIPE | `{"DELETE_RECIPE":"<name>"}` |
| DETACH_DEVICE | `{"DETACH_DEVICE":["<zone>","<device>"]}` |
| DEVICES_SN | `{"DEVICES_SN":0}` |
| DST_OFF | `{"DST_OFF":0}` |
| DST_ON | `{"DST_ON":0}` |
| ENGINEERS_DATA | `{"ENGINEERS_DATA":0}` |
| FIRMWARE | `{"FIRMWARE":0}` |
| FROST_OFF | `{"FROST_OFF":"<device(s)>"}` |
| FROST_ON | `{"FROST_ON":"<device(s)>"}` |
| GET_DEVICE_LIST | `{"GET_DEVICE_LIST":"<device>"}` |
| GET_DEVICES | `{"GET_DEVICES":0}` |
| GET_ENGINEERS | `{"GET_ENGINEERS":0}` |
| GET_GROUPS | `{"GET_GROUPS":0}` |
| GET_HOLD | `{"GET_HOLD":0}` |
| GET_HOLIDAY | `{"GET_HOLIDAY":0}` |
| GET_HOURSRUN | `{"GET_HOURSRUN":"<device(s)>"}` |
| GET_LIVE_DATA | `{"GET_LIVE_DATA":0}` |
| GET_PROFILE | `{"GET_PROFILE":"<profile name>"}` |
| GET_PROFILE_0 | `{"GET_PROFILE_0":"<devices>"}` |
| GET_PROFILE_NAMES | `{"GET_PROFILE_NAMES":0}` |
| GET_PROFILE_TIMERS | `{"GET_PROFILE_TIMERS":0}` |
| GET_PROFILES | `{"GET_PROFILES":0}` |
| GET_RECIPES | `{"GET_RECIPES":0}` |
| GET_SYSTEM | `{"GET_SYSTEM":0}` |
| GET_TEMPLOG | `{"GET_TEMPLOG":"<device(s)>"}` |
| GET_TIMER_0 | `{"GET_TIMER_0":"<device>"}` |
| GET_ZONES | `{"GET_ZONES":0}` |
| GLOBAL_DEV_LIST | `{"GLOBAL_DEV_LIST":"<devices>"}` |
| GLOBAL_SYSTEM_TYPE | `{"GLOBAL_SYSTEM_TYPE":"<type>"}` |
| HOLD | `{"HOLD":[{"temp":"<number>","id":"<string>","hours":"<number>","minutes":"<number>"},"<device(s)>"]}` |
| HOLIDAY | `{"HOLIDAY":["HHMMSSDDMMYYYY","HHMMSSDDMMYYYY"]}` |
| IDENTIFY | `{"IDENTIFY":0}` |
| IDENTIFY_DEV | `{"IDENTIFY_DEV":"<device>"}` |
| INFO | `{"INFO":0}` |
| LINK_DEVICE | `{"LINK_DEVICE":["<zone>","<device>"]}` |
| LOCK | `{"LOCK":[["<pin1>","<pin2>","<pin3>","<pin4>"],"<device(s)>"]}` |
| MANUAL_DST | `{"MANUAL_DST":"<number>"}` |
| MANUAL_OFF | `{"MANUAL_OFF":"<devices>"}` |
| MANUAL_ON | `{"MANUAL_ON":"<devices>"}` |
| NTP_OFF | `{"NTP_OFF":0}` |
| NTP_ON | `{"NTP_ON":0}` |
| PERMIT_JOIN (device) | `{"PERMIT_JOIN":["<seconds>","<device>"]}` |
| PERMIT_JOIN (repeater) | `{"PERMIT_JOIN":["repeater","<seconds>"]}` |
| PROFILE_TITLE | `{"PROFILE_TITLE":["<oldname>","<newname>"]}` |
| READ_COMFORT_LEVELS | `{"READ_COMFORT_LEVELS":"<device(s)>"}` |
| READ_DCB | `{"READ_DCB":100}` |
| READ_TIMECLOCK | `{"READ_TIMECLOCK":"<device(s)>"}` |
| REMOVE_REPEATER | `{"REMOVE_REPEATER":"<repeater>"}` |
| REMOVE_ZONE | `{"REMOVE_ZONE":"<zone>"}` |
| RESET | `{"RESET":0}` |
| RUN_PROFILE | `{"RUN_PROFILE":"<profile name>"}` |
| RUN_PROFILE_ID | `{"RUN_PROFILE_ID":["<profid>","<devices>"]}` |
| RUN_RECIPE | `{"RUN_RECIPE":["<name>","<devices>"]}` |
| SET_CHANNEL | `{"SET_CHANNEL":"<channel>"}` |
| SET_CLOSE_DELAY | `{"SET_CLOSE_DELAY":"<seconds>"}` |
| SET_COMFORT_LEVELS | `{"SET_COMFORT_LEVELS":["<levels>","<device(s)>"]}` |
| SET_COOL_TEMP | `{"SET_COOL_TEMP":["<temp>","<device(s)>"]}` |
| SET_DATE | `{"SET_DATE":["<year>","<month>","<day>"]}` |
| SET_DELAY | `{"SET_DELAY":["<delay>","<device(s)>"]}` |
| SET_DIFF | `{"SET_DIFF":["<switching differential>","<device(s)>"]}` |
| SET_FAILSAFE | `{"SET_FAILSAFE":["<true/false>","<device>"]}` |
| SET_FAN_SPEED | `{"SET_FAN_SPEED":["<speed>","<device(s)>"]}` |
| SET_FLOOR | `{"SET_FLOOR":["<temp>","<device(s)>"]}` |
| SET_FORMAT | `{"SET_FORMAT":"<format>"}` |
| SET_FROST | `{"SET_FROST":["<temp>","<device(s)>"]}` |
| SET_GLOBAL_HC_MODE | `{"SET_GLOBAL_HC_MODE":"<mode>"}` |
| SET_HC_MODE | `{"SET_HC_MODE":["<mode>","<device(s)>"]}` |
| SET_LEVEL_4 | `{"SET_LEVEL_4":0}` |
| SET_LEVEL_6 | `{"SET_LEVEL_6":0}` |
| SET_OPEN_DELAY | `{"SET_OPEN_DELAY":"<seconds>"}` |
| SET_PREHEAT | `{"SET_PREHEAT":["<hours>","<device(s)>"]}` |
| SET_RF_MODE | `{"SET_RF_MODE":["<mode>","<devices>"]}` |
| SET_TEMP | `{"SET_TEMP":["<temp>","<device(s)>"]}` |
| SET_TEMP_FORMAT | `{"SET_TEMP_FORMAT":"<format>"}` |
| SET_TIME | `{"SET_TIME":["<hours>","<minutes>"]}` |
| SET_TIMECLOCK | `{"SET_TIMECLOCK":["<levels>","<device(s)>"]}` |
| STATISTICS | `{"STATISTICS":0}` |
| STORE_PROFILE | `{"STORE_PROFILE":"<profile ob>"}` |
| STORE_PROFILE_0 | `{"STORE_PROFILE_0":["<profile obj>","<devices>"]}` |
| STORE_PROFILE_TIMER_0 | `{"STORE_PROFILE_TIMER_0":["<profile obj>","<devices>"]}` |
| STORE_RECIPE | `{"STORE_RECIPE":["<name>","<commands>","<devices>"]}` |
| STORE_C_PROFILE | `{"STORE_C_PROFILE":{"ID":"<id>","info":"<profile>","name":"<name>"}}` |
| SUMMER_OFF | `{"SUMMER_OFF":"<device(s)>"}` |
| SUMMER_ON | `{"SUMMER_ON":"<device(s)>"}` |
| TIME_ZONE | `{"TIME_ZONE":"<timezone offset>"}` |
| TIMER_HOLD_OFF | `{"TIMER_HOLD_OFF":["<minutes>","<device(s)>"]}` |
| TIMER_HOLD_ON | `{"TIMER_HOLD_ON":["<minutes>","<device(s)>"]}` |
| TIMER_OFF | `{"TIMER_OFF":"<device(s)>"}` |
| TIMER_ON | `{"TIMER_ON":"<device(s)>"}` |
| UNLOCK | `{"UNLOCK":"<device(s)>"}` |
| USER_LIMIT | `{"USER_LIMIT":["<int>","<device(s)>"]}` |
| VIEW_ROC | `{"VIEW_ROC":"<device(s)>"}` |
| ZONE_TITLE | `{"ZONE_TITLE":["<oldname>","<newname>"]}` |

---

## Appendix D - Examples of Cached Files

### Get System Example

```json
{
  "ALT_TIMER_FORMAT": 2,
  "CORF": "C",
  "DEVICE_ID": "NeoHub",
  "DST_AUTO": false,
  "DST_ON": false,
  "FORMAT": 2,
  "HEATING_LEVELS": 4,
  "HEATORCOOL": "HeatOnly",
  "HUB_VERSION": 2081,
  "NTP_ON": "Running",
  "PARTITION": "4",
  "TIMESTAMP": 1518607836,
  "TIME_ZONE": 0,
  "UTC": 1519038792
}
```

### Get Live Data Example

```json
{
  "CLOSE_DELAY": 0,
  "COOL_INPUT": false,
  "GLOBAL_SYSTEM_TYPE": "HeatOnly",
  "HOLIDAY_END": 0,
  "HUB_AWAY": false,
  "HUB_HOLIDAY": false,
  "HUB_TIME": 1519038584,
  "OPEN_DELAY": 0,
  "TIMESTAMP_DEVICE_LISTS": 1519038219,
  "TIMESTAMP_ENGINEERS": 1519038219,
  "TIMESTAMP_PROFILE_0": 1519038270,
  "TIMESTAMP_PROFILE_COMFORT_LEVELS": 1518604883,
  "TIMESTAMP_PROFILE_TIMERS": 1518600089,
  "TIMESTAMP_PROFILE_TIMERS_0": 1519038219,
  "TIMESTAMP_SYSTEM": 1518607836,
  "devices": [
    {
      "ACTIVE_LEVEL": 2,
      "ACTIVE_PROFILE": 28,
      "ACTUAL_TEMP": "24.5",
      "AVAILABLE_MODES": ["heat"],
      "AWAY": false,
      "COOL_MODE": false,
      "COOL_ON": false,
      "COOL_TEMP": 0,
      "CURRENT_FLOOR_TEMPERATURE": 127,
      "DATE": "monday",
      "DEVICE_ID": 1,
      "FAN_CONTROL": "Automatic",
      "FAN_SPEED": "Custom",
      "FLOOR_LIMIT": false,
      "HC_MODE": "VENT",
      "HEAT_MODE": true,
      "HEAT_ON": false,
      "HOLD_OFF": true,
      "HOLD_ON": false,
      "HOLD_TEMP": 30,
      "HOLD_TIME": "0:00",
      "HOLIDAY": false,
      "LOCK": false,
      "LOW_BATTERY": false,
      "MANUAL_OFF": true,
      "MODELOCK": false,
      "MODULATION_LEVEL": 0,
      "OFFLINE": false,
      "PIN_NUMBER": "1111",
      "PREHEAT_ACTIVE": false,
      "RECENT_TEMPS": ["18.4", "...", "24.2"],
      "SET_TEMP": "17.0",
      "STANDBY": false,
      "SWITCH_DELAY_LEFT": "0:00",
      "TEMPORARY_SET_FLAG": false,
      "THERMOSTAT": true,
      "TIME": "11:08",
      "TIMER_ON": false,
      "WINDOW_OPEN": false,
      "WRITE_COUNT": 115,
      "ZONE_NAME": "Bathroom"
    },
    {
      "ACTIVE_LEVEL": 0,
      "ACTIVE_PROFILE": 0,
      "ACTUAL_TEMP": "23.6",
      "AVAILABLE_MODES": ["heat"],
      "AWAY": false,
      "COOL_MODE": false,
      "COOL_ON": false,
      "COOL_TEMP": 23,
      "CURRENT_FLOOR_TEMPERATURE": 127,
      "DATE": "monday",
      "DEVICE_ID": 3,
      "FAN_CONTROL": "Manual",
      "FAN_SPEED": "Off",
      "FLOOR_LIMIT": false,
      "HC_MODE": "HEATING",
      "HEAT_MODE": true,
      "HEAT_ON": false,
      "HOLD_OFF": true,
      "HOLD_ON": false,
      "HOLD_TEMP": 0,
      "HOLD_TIME": "0:00",
      "HOLIDAY": false,
      "LOCK": false,
      "LOW_BATTERY": false,
      "MANUAL_OFF": true,
      "MODELOCK": false,
      "MODULATION_LEVEL": 0,
      "OFFLINE": false,
      "PIN_NUMBER": "0000",
      "PREHEAT_ACTIVE": false,
      "RECENT_TEMPS": ["18.0", "...", "23.5"],
      "SET_TEMP": "16.0",
      "STANDBY": false,
      "SWITCH_DELAY_LEFT": "0:00",
      "TEMPORARY_SET_FLAG": false,
      "TIME": "11:09",
      "TIMECLOCK": true,
      "TIMER_ON": false,
      "WINDOW_OPEN": false,
      "WRITE_COUNT": 70,
      "ZONE_NAME": "Office"
    }
  ]
}
```

### Get Engineers Example

```json
{
  "Bathroom": {
    "DEADBAND": 0,
    "DEVICE_ID": 1,
    "DEVICE_TYPE": 1,
    "FLOOR_LIMIT": 28,
    "FROST_TEMP": 12,
    "MAX_PREHEAT": 3,
    "OUTPUT_DELAY": 0,
    "PUMP_DELAY": 0,
    "RF_SENSOR_MODE": "self",
    "STAT_FAILSAFE": 0,
    "STAT_VERSION": 101,
    "SWITCHING DIFFERENTIAL": 1,
    "SWITCH_DELAY": 0,
    "SYSTEM_TYPE": 0,
    "TIMESTAMP": 1519038219,
    "USER_LIMIT": 0,
    "WINDOW_SWITCH_OPEN": false
  },
  "Office": {
    "DEADBAND": 2,
    "DEVICE_ID": 3,
    "DEVICE_TYPE": 12,
    "FLOOR_LIMIT": 28,
    "FROST_TEMP": 12,
    "MAX_PREHEAT": 0,
    "OUTPUT_DELAY": 0,
    "PUMP_DELAY": 0,
    "RF_SENSOR_MODE": "self",
    "STAT_FAILSAFE": 0,
    "STAT_VERSION": 12,
    "SWITCHING DIFFERENTIAL": 1,
    "SWITCH_DELAY": 0,
    "SYSTEM_TYPE": 0,
    "TIMESTAMP": 1519038219,
    "USER_LIMIT": 0,
    "WINDOW_SWITCH_OPEN": false
  }
}
```

### Get Profiles Example

```json
{
  "ball": {
    "PROFILE_ID": 28,
    "group": null,
    "info": {
      "monday": {"leave": ["09:30",17], "return": ["17:30",25], "sleep": ["22:30",15], "wake": ["01:00",14]},
      "sunday": {"leave": ["09:30",17], "return": ["17:30",21], "sleep": ["22:30",15], "wake": ["01:00",21]}
    },
    "name": "ball"
  }
}
```

**Get Profile Timers:**

```json
{
  "Timer": {
    "PROFILE_ID": 26,
    "group": null,
    "info": {
      "monday": {"time1": ["07:00","09:00"], "time2": ["16:00","20:00"], "time3": ["24:00","24:00"], "time4": ["24:00","24:00"]},
      "sunday": {"time1": ["07:00","09:00"], "time2": ["16:00","20:00"], "time3": ["24:00","24:00"], "time4": ["24:00","24:00"]}
    },
    "name": "Timer"
  }
}
```

### Cooling Profiles

Saving a cooling profile after editing:

```json
{"STORE_C_PROFILE": {
  "ID": 7,
  "info": {
    "sunday": {"wake": ["09:00",20,true], "leave": ["16:00",20,true], "return": ["19:10",20,true], "sleep": ["23:05",20,true]},
    "monday": {"wake": ["09:00",20,true], "leave": ["09:05",20,true], "return": ["16:05",20,true], "sleep": ["22:00",20,true]},
    "tuesday": {"wake": ["07:00",20,true], "leave": ["09:00",20,true], "return": ["16:00",20,true], "sleep": ["22:00",20,true]},
    "wednesday": {"wake": ["07:00",20,true], "leave": ["09:00",20,true], "return": ["16:00",20,true], "sleep": ["22:00",20,true]},
    "thursday": {"wake": ["07:00",20,true], "leave": ["09:00",20,true], "return": ["16:00",20,true], "sleep": ["22:00",20,true]},
    "friday": {"wake": ["07:00",20,true], "leave": ["09:00",20,true], "return": ["16:00",20,true], "sleep": ["22:00",20,true]},
    "saturday": {"wake": ["09:00",20,true], "leave": ["17:00",20,true], "return": ["21:00",20,true], "sleep": ["24:00",20,true]}
  },
  "group": null,
  "name": "Cooling Profile 6"
}}
```

---

## Appendix E - Device Type List

| Device Type ID | Device |
|----------------|--------|
| 1 | TCM (neoStat) |
| 2 | Wi-Fi STAT / SMARTSTAT |
| 3 | COOLSWITCH |
| 4 | TCM-RH |
| 5 | WDS (Window/Door Switch) |
| 6 | NEOPLUG |
| 7 | NEOAIR |
| 8 | Smart Stat HC |
| 9 | NeoAir HW (combined model) |
| 10 | REPEATER |
| 11 | NEOSTAT-HC |
| 12 | Neostat-V2 |
| 13 | Neoair V2 |
| 14 | Remote Air Sensor |
| 15 | NeoAir-V2 combined mode |
| 16 | RF Switch Wifi |
| 17 | Edge wifi thermostat |

> **Note:** The neoStat and neoStat V2 have different device IDs because they use different hardware and firmware, and the neoHub needs to know the difference when doing firmware updates. The same applies to neoAir V1 and neoAir V2. The JSON commands are unaffected by the differences.

For Generation 2 NeoHub from software version 2112 onwards, to get the neoHub type look for `"HUB_TYPE": 2` in the system cache.

---

## Appendix F - Daylight Saving

Different countries use different dates for moving their clocks back and forward. Making these adjustments automatically means the user must select the appropriate Location.

For example, the UK and most of Europe use the last Sunday of March to go forward by 1 hour and last Sunday of October to go back again.

The original `{"DST_ON":0}` command will default to UK dates until the default is changed.

To read the current DST settings, read `"TIMEZONESTR": "UK"` in the System cache.

To turn off automatic daylight saving:

```json
{"DST_OFF":0}
{"MANUAL_DST":0}
```

**Example: Setting time for New Zealand:**

```json
{"NTP_ON":0}
{"TIME_ZONE":12}
{"DST_ON":"NZ"}
```

- Enables time server
- Sets time zone
- Enables daylight savings at the required dates

**Available DST zones:**

| Zone Code | Region |
|-----------|--------|
| `"UK"` | United Kingdom |
| `"EU"` | European Union |
| `"NZ"` | New Zealand |

---

## Addendum - Additional Settings

**Constant Fan:**
Used to keep fans running when there is no call for heat or cooling. Often used in large buildings to maintain a constant air flow. Setting it true or false (1 or 0). Corresponds to feature setting number 12 in neoStat HC.
Location: engineers cache.

**Cool Proof:**
Used to delay the start of the fans to give the water in the pipes time to warm up. Settings are 00 to 95 seconds in 5-second steps.
Location: engineers cache.

**HUB_TYPE variable:**
A variable used to denote the model of neoHub being used. Found in the system cache.

| HUB_TYPE | Description |
|----------|-------------|
| 1 | Original neoHub Generation 1 |
| 2 | neoHub Generation 2 with HomeKit |
| 3 | neoAir Hub |
