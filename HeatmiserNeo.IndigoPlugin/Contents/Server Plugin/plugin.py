#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2016-2018 Alan Carter. All rights reserved.
#
#
################################################################################
# Imports
################################################################################
import re
import json
import socket
import ssl
import datetime
import threading

try:
    from websockets.sync.client import connect as ws_connect
    from websockets.exceptions import ConnectionClosed
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    ConnectionClosed = type(None)  # safe fallback for except clause

################################################################################
# Globals
################################################################################

########################################
def updateVar(name, value, folder=0):
    if name not in indigo.variables:
        indigo.variable.create(name, value=value, folder=folder)
    else:
        indigo.variable.updateValue(name, value)

################################################################################
class Plugin(indigo.PluginBase):
    ########################################
    # Class properties
    ########################################

    @staticmethod
    def _coerce_bool(value):
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes")

    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs, **kwargs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs, **kwargs)
        self.neohubIP = pluginPrefs.get("neohubIP", "127.0.0.1")
        self.logComms = self._coerce_bool(pluginPrefs.get("logComms", False))
        self.timeSync = self._coerce_bool(pluginPrefs.get("timeSync", False))
        self.connectionMode = pluginPrefs.get("connectionMode", "wss")
        self.neohubGen2 = True if self.connectionMode == "wss" else self._coerce_bool(pluginPrefs.get("neohubGen2", True))
        self.neohubToken = pluginPrefs.get("neohubToken", "").strip()
        self.commsEnabled = True
        self.connectErrorCount = 0
        self.sendErrorCount = 0
        self._wss_lock = threading.Lock()
        self._command_id = 0
        self.timeUpdateRequired = None
        self.dcbUpdateRequired = None
        self.engUpdateRequired = None
        self.firstTime = True
        self.responseKeysLogged = False
        self._deviceListStamp = None
        self._discoveryDone = False
        self._hubHostZone = None
        self._missingZonesWarned = set()
        self._zoneListWarned = set()
        self._knownZones = frozenset()
        self._failedPolls = 0
        self._pendingRebind = {}  # devId -> (old zone, new zone), stashed by validateDeviceConfigUi


    ########################################
    def startup(self):
        self.logger.info("Starting Heatmiser Neo plugin")
        if self.connectionMode == "wss":
            if not self.neohubToken:
                self.logger.warning("WSS mode selected but no API token configured — enter token in plugin preferences")
            elif not HAS_WEBSOCKETS:
                self.logger.warning("WSS mode selected but websockets library not available — falling back to legacy TCP (port 4242)")
            else:
                self.logger.info("Using WSS connection (port 4243)")
        else:
            if self.neohubGen2:
                self.logger.info("Using legacy TCP connection (port 4242) with Gen 2 API commands")
            else:
                self.logger.info("Using legacy TCP connection (port 4242) with Gen 1 API commands")
        if self.logComms:
            self.logger.info("Neo comms logging is on")
        else:
            self.logger.info("Neo comms logging is off")
        self.createDevices()
        if self.timeSync:
            self.timeUpdateRequired = True
            self.logger.info("Neo time will be synchronised daily with Indigo")
        else:
            self.logger.info("Neo time will be syncronised via NTP server")


    def deviceStartComm(self, dev):
        dev.stateListOrDisplayStateIdChanged()

    def shutdown(self):
        self.logger.info("Stopping Heatmiser Neo plugin")
        self.commsEnabled = False

        
    ########################################
    def runConcurrentThread(self):
        self.logger.info("Starting Heatmiser Neo monitoring thread")
        try:
            while True:
                try:
                    self.updateReadings()
                except Exception as exc:
                    self.logger.exception("Error in updateReadings")
                self.sleep(1)
                if self.firstTime:
                    if self.timeSync:
                        self.ntpOff()
                    else:
                        self.ntpOn()
                    self.sleep(1)
                    try:
                        self.updateDCB()
                    except Exception as exc:
                        self.logger.exception("Error in updateDCB")
                    try:
                        self.updateEng()
                    except Exception as exc:
                        self.logger.exception("Error in updateEng")
                    self.firstTime = False
                else:
                    try:
                        self.checkDCB()
                    except Exception as exc:
                        self.logger.exception("Error in checkDCB")
                    try:
                        self.checkEng()
                    except Exception as exc:
                        self.logger.exception("Error in checkEng")
                if self.timeSync:
                    self.checkTime()
                self.sleep(29)

        except self.StopThread:
            self.commsEnabled = False
            pass


    ########################################
    # Called when user prefs are changed
    
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        # If the user saved preferences, update logging parameters
        if userCancelled == False:
            self.oldLogValue = self.logComms
            self.logComms = self._coerce_bool(valuesDict.get("logComms", False))
            if self.logComms != self.oldLogValue:
                if self.logComms:
                    self.logger.info("Neo comms logging is on")
                else:
                    self.logger.info("Neo comms logging is off")
            self.oldTimeValue = self.timeSync
            self.timeSync = self._coerce_bool(valuesDict.get("timeSync", False))
            if self.timeSync != self.oldTimeValue:
                if self.timeSync:
                    self.ntpOff()
                    self.timeUpdateRequired = True
                    self.logger.info("Neo time will be synchronised daily with Indigo")
                else:
                    self.ntpOn()
                    self.logger.info("Neo time will be syncronised via NTP server")
                self.updateDCB()
            oldMode = self.connectionMode
            self.connectionMode = valuesDict.get("connectionMode", "wss")
            self.neohubGen2 = True if self.connectionMode == "wss" else self._coerce_bool(valuesDict.get("neohubGen2", True))
            oldToken = self.neohubToken
            self.neohubToken = valuesDict.get("neohubToken", "").strip()
            if self.connectionMode != oldMode or self.neohubToken != oldToken:
                if self.connectionMode == "wss" and self.neohubToken:
                    self.logger.info("Using WSS connection (port 4243)")
                else:
                    self.logger.info("Using legacy TCP connection (port 4242)")
            oldIP = self.neohubIP
            self.neohubIP = valuesDict.get("neohubIP")
            if self.neohubIP != oldIP:
                self.logger.info("Neohub IP address is now %s" % self.neohubIP)

                        
    ########################################
    # Heatmiser Neo specific functions
    
    # Zone-name matching helpers (issue #33)
    #
    # Each Indigo device stores the hub's ZONE_NAME in a "zoneName" plugin
    # prop. That is the key for readings and commands; the Indigo device
    # name is free to change, and "address" mirrors the hub list position
    # (refreshed via pluginProps["address"] for bound devices on each
    # discovery) and is used only for display and for the pre-discovery
    # hub-host fallback.

    def _liveDevices(self):
        return [dev for dev in indigo.devices.iter("self") if "SUPERSEDED" not in dev.name]

    def _zoneName(self, dev):
        """Hub zone name a device is bound to, or None if it has not been bound yet."""
        return dev.pluginProps.get("zoneName") or None

    def _zonesByName(self, neoInfo):
        """{ZONE_NAME: (hub list index, device data)} from a live-data response.

        Entries that cannot be used are logged (once per discovery, not every poll):
        a nameless entry is ignored, and when a name appears twice the first entry wins."""
        zones = {}
        for index, devData in enumerate(neoInfo.get("devices", [])):
            name = devData.get("ZONE_NAME", devData.get("device"))
            if not name:
                self._warnZoneListOnce("nameless %d" % index, "Hub device list entry %d has no zone name; ignoring it" % index)
                continue
            if name in zones:
                self._warnZoneListOnce("duplicate %s" % name,
                                       "Hub lists zone '%s' twice (entries %d and %d); using the first" % (name, zones[name][0], index))
                continue
            zones[name] = (index, devData)
        return zones

    def _warnZoneListOnce(self, key, message):
        if key not in self._zoneListWarned:
            self._zoneListWarned.add(key)
            self.logger.warning(message)

    @staticmethod
    def _legacyZoneName(indigoName):
        """Zone name implied by a pre-migration device's Indigo name.
        Some installs suffixed the hub name with " Heatmiser"."""
        name = indigoName.strip()
        if name.endswith(" Heatmiser"):
            name = name[: -len(" Heatmiser")].rstrip()
        return name

    # Device ConfigUI: rebind a device to another hub zone (e.g. after a zone rename on the hub)

    def hubZoneList(self, filter="", valuesDict=None, typeId="", targetId=0):
        """Menu items for the "Hub zone" field: zones from the last discovery, plus the device's current zone.

        Uses _knownZones (no hub round-trip) and only asks the hub if discovery never succeeded.
        The current value is always present, so a hub outage while the dialog is open cannot blank the binding."""
        current = None
        try:
            current = valuesDict.get("zoneName") if valuesDict else None
        except Exception:
            current = None
        try:
            hubZones = set(self._knownZones)
            if not hubZones:
                reply = self.getNeoData("\"GET_LIVE_DATA\":0" if self.neohubGen2 else "\"INFO\":0")
                if isinstance(reply, dict):
                    hubZones = set(self._zonesByName(reply))
                if not hubZones:
                    self.logger.debug("hubZoneList: no zone list from the hub; offering only the current zone")
            items = {zone: zone for zone in hubZones}
            if current and current not in items:
                items[current] = "%s (not on hub)" % current
            return [(zone, items[zone]) for zone in sorted(items)]
        except Exception:
            self.logger.exception("Could not build the hub zone list")
            return [(current, "%s (not on hub)" % current)] if current else []

    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        zone = valuesDict.get("zoneName")
        errorsDict = indigo.Dict()
        if not zone:
            errorsDict["zoneName"] = "Choose the hub zone this device is bound to"
            errorsDict["showAlertText"] = "Choose the hub zone this device is bound to."
            return (False, valuesDict, errorsDict)
        for other in self._liveDevices():
            if other.id != devId and other.pluginProps.get("zoneName") == zone:
                msg = "Zone '%s' is already bound to device '%s'. Rename that one with SUPERSEDED first." % (zone, other.name)
                errorsDict["zoneName"] = msg
                errorsDict["showAlertText"] = msg
                return (False, valuesDict, errorsDict)
        # Indigo saves the new props only after this returns True, so this is the last chance to read the old zone.
        # A zone absent from _knownZones is deliberately accepted: the hub may be unreachable, and the poll
        # loop flags a genuinely missing zone as ZONE NOT ON HUB.
        try:
            old = indigo.devices[devId].pluginProps.get("zoneName") if devId else None
        except Exception:
            self.logger.exception("Could not read the current zone of device %s" % devId)
            old = None
        if old != zone:
            self._pendingRebind[devId] = (old, zone)
        else:
            self._pendingRebind.pop(devId, None)
        return (True, valuesDict)

    def closedDeviceConfigUi(self, valuesDict, userCancelled, typeId, devId):
        # Base implementation is a no-op, so no super() call.
        change = self._pendingRebind.pop(devId, None)
        if userCancelled or not change or change[0] == change[1]:
            return
        old, new = change
        try:
            name = indigo.devices[devId].name
        except Exception:
            name = str(devId)
        self.logger.info("Device '%s' rebound from hub zone '%s' to '%s'; rediscovering" % (name, old, new))
        self._missingZonesWarned.discard(old)
        self._discoveryDone = False  # next poll runs createDevices(), which refreshes address/type and error state

    def createDevices(self):
        self.commsEnabled = True
        deviceTypeMap = {}
        if self.neohubGen2:
            # GET_ENGINEERS provides DEVICE_TYPE per device (keyed by name)
            engData = self.getNeoData("\"GET_ENGINEERS\":0")
            if engData and engData != "":
                for devName, devInfo in engData.items():
                    if isinstance(devInfo, dict) and "DEVICE_TYPE" in devInfo:
                        deviceTypeMap[devName] = devInfo["DEVICE_TYPE"]
                if not deviceTypeMap:
                    self.logger.warning("GET_ENGINEERS returned no device type data; keys: %s" % list(engData.keys())[:5])
            else:
                self.logger.warning("GET_ENGINEERS failed; device types unknown this pass")

        neoInfo = self.getNeoData("\"GET_LIVE_DATA\":0" if self.neohubGen2 else "\"INFO\":0")
        if not isinstance(neoInfo, dict) or "devices" not in neoInfo:
            self.logger.error("Cannot detect devices: no device list in hub response; will retry on the next successful poll")
            return
        stamp = neoInfo.get("TIMESTAMP_DEVICE_LISTS")
        self._missingZonesWarned = set()
        self._zoneListWarned = set()
        zones = self._zonesByName(neoInfo)
        self._hubHostZone = next((z for z, (i, _) in zones.items() if i == 0), None)

        # Pass 1: devices that already carry a zoneName claim their zone.
        claimed = {}
        legacy = []
        for dev in self._liveDevices():
            zoneName = dev.pluginProps.get("zoneName")
            if not zoneName:
                legacy.append(dev)
                continue
            if zoneName not in zones:
                self.logger.warning("Device '%s' is bound to hub zone '%s', which is no longer on the hub (removed or renamed). "
                                    "It will not be updated. Rename it with SUPERSEDED or delete it. "
                                    "If the zone was renamed on the hub, a new device is created for the new name; repoint automations to it."
                                    % (dev.name, zoneName))
                self._missingZonesWarned.add(zoneName)
                dev.setErrorStateOnServer("ZONE NOT ON HUB")
                continue
            if zoneName in claimed:
                self.logger.warning("Devices '%s' and '%s' both claim hub zone '%s'; using '%s'. "
                                    "Rename one with SUPERSEDED." % (claimed[zoneName].name, dev.name, zoneName, claimed[zoneName].name))
                dev.setErrorStateOnServer("DUPLICATE ZONE")
                continue
            claimed[zoneName] = dev

        # Pass 2: migrate pre-zoneName devices by Indigo name, never by position.
        # A device renamed in Indigo before this version cannot be matched safely, so it is left alone.
        unmatchedLegacy = []
        for dev in legacy:
            zoneName = self._legacyZoneName(dev.name)
            if zoneName in zones and zoneName not in claimed:
                props = dev.pluginProps
                props["zoneName"] = zoneName
                dev.replacePluginPropsOnServer(props)
                claimed[zoneName] = dev
                self.logger.info("Bound device '%s' to hub zone '%s'" % (dev.name, zoneName))
            else:
                unmatchedLegacy.append(dev)
        if unmatchedLegacy:
            # Creating a device for an unclaimed zone would give it that zone's zoneName, so the legacy
            # device could never claim it afterwards and would be orphaned for good. Hold creation until
            # legacy devices are resolved.
            unclaimed = ", ".join(z for z in zones if z not in claimed) or "none"
            for dev in unmatchedLegacy:
                dev.setErrorStateOnServer("NO HUB ZONE")
                if unclaimed == "none":
                    self.logger.warning("Device '%s' has no stored hub zone and every hub zone is already bound to another device. "
                                        "It will not be updated. Its stat is probably no longer on the hub: "
                                        "add SUPERSEDED to its name or delete it." % dev.name)
                else:
                    self.logger.warning("Device '%s' has no stored hub zone and no unclaimed hub zone matches its name. "
                                        "It will not be updated. If it is one of the unclaimed hub zones (%s), rename it in Indigo "
                                        "to exactly that zone name (or '<zone> Heatmiser'), restart the plugin, then rename it as you like. "
                                        "If its stat is no longer on the hub, add SUPERSEDED to its name or delete it."
                                        % (dev.name, unclaimed))
            self.logger.warning("Not creating devices for unclaimed hub zones until the %d device(s) above are bound (rename + restart) "
                                "or retired (SUPERSEDED/delete)" % len(unmatchedLegacy))

        # Pass 3: every hub zone gets a device of the right type, with current props and position.
        for zoneName, (index, devData) in zones.items():
            try:
                self._syncZoneDevice(neoInfo, zoneName, index, devData, claimed.get(zoneName), deviceTypeMap, bool(unmatchedLegacy))
            except Exception:
                self.logger.exception("Discovery failed for hub zone '%s'; continuing with the others" % zoneName)
                try:
                    if claimed.get(zoneName) is not None:
                        claimed[zoneName].setErrorStateOnServer("SYNC FAILED")
                except Exception as exc:
                    self.logger.debug("Could not set SYNC FAILED on '%s': %s" % (claimed[zoneName].name, exc))
        self._deviceListStamp = stamp
        self._knownZones = frozenset(zones)
        self._discoveryDone = True

    def _syncZoneDevice(self, neoInfo, zoneName, index, devData, device, deviceTypeMap, holdCreation):
        """Create or refresh the Indigo device for one hub zone and push its readings."""
        deviceType = deviceTypeMap.get(zoneName, devData.get("DEVICE_TYPE", 0)) if self.neohubGen2 else devData.get("DEVICE_TYPE", 0)
        if not deviceType and device is not None:
            # Type unknown this pass (GET_ENGINEERS blip, or hub reports 0 for an offline device):
            # trust what we stored rather than treat the device as a mis-typed thermostat.
            deviceType = int(device.pluginProps.get("neoDeviceType", 0) or 0)
        if deviceType == 14:
            expectedTypeId = "heatmiserNeoSensor"
        elif deviceType == 6:
            expectedTypeId = "heatmiserNeoplug"
        elif devData.get("TIMECLOCK", False):
            expectedTypeId = "heatmiserNeoTimeclock"
        else:
            expectedTypeId = "heatmiserNeostat"
        typeDeferred = False
        if device is not None and deviceType and device.deviceTypeId != expectedTypeId:
            if holdCreation:
                # Superseding would create a replacement, which is held; keep the old device and its stored type.
                self.logger.warning("Device '%s' should become %s but creation is held; keeping it until the unmatched devices above are resolved"
                                    % (device.name, expectedTypeId))
                typeDeferred = True
            else:
                # Wrong device type — supersede and recreate
                self.logger.info("Upgrading %s from %s to %s" % (device.name, device.deviceTypeId, expectedTypeId))
                device.name = device.name + " SUPERSEDED"
                device.replaceOnServer()
                device = None
        if device is None:
            if holdCreation:
                return
            if not deviceType:
                self.logger.warning("Hub zone '%s' has no device type yet (hub reports it offline, or GET_ENGINEERS failed); "
                                    "not creating a device for it. Restart the plugin once it is online." % zoneName)
                return
            self.logger.info("Creating Heatmiser device for %s (type: %s)" % (zoneName, expectedTypeId))
            props = {"neoDeviceType": str(deviceType), "zoneName": zoneName}
            # Hub zones are room names, so an unrelated Indigo device may already own the name.
            name = zoneName
            if zoneName in indigo.devices:
                name = zoneName + " Heatmiser"
                self.logger.warning("Indigo already has a device named '%s'; creating the Heatmiser device as '%s'" % (zoneName, name))
            device = indigo.device.create(protocol=indigo.kProtocol.Plugin, address=index, name=name,
                pluginId="com.racarter.indigoplugin.heatmiser-neo", deviceTypeId=expectedTypeId, props=props)
        else:
            localPropsCopy = device.pluginProps
            if deviceType and not typeDeferred:
                localPropsCopy["neoDeviceType"] = str(deviceType)
            localPropsCopy["zoneName"] = zoneName
            if expectedTypeId == "heatmiserNeostat":
                localPropsCopy["SupportsCoolSetpoint"] = False
                localPropsCopy["SupportsHvacFanMode"] = False
            # address mirrors the hub list position (display only); Indigo migrates pluginProps["address"] to dev.address
            localPropsCopy["address"] = str(index)
            device.replacePluginPropsOnServer(localPropsCopy)
        self.updateStatState(neoInfo, index, device)


    def updateReadings(self):
        update = self.getNeoData("\"GET_LIVE_DATA\":0" if self.neohubGen2 else "\"INFO\":0")
        if update != "":
            if self._failedPolls >= 3:
                self.logger.info("Hub reachable again; clearing HUB UNREACHABLE")
                # updateStatesOnServer's list form is not documented to clear the error state, and some readings
                # (e.g. an offline stat) never do, so clear it explicitly. The per-device loop below then
                # re-asserts ZONE NOT ON HUB / DUPLICATE ZONE / OFFLINE where they still apply.
                for dev in self._liveDevices():
                    if self._zoneName(dev):
                        dev.setErrorStateOnServer(None)
            self._failedPolls = 0
            # Log response keys once on first successful response for field name verification
            if not self.responseKeysLogged and update.get("devices"):
                self.logger.info("GET_LIVE_DATA top-level keys: %s" % list(update.keys()))
                self.logger.info("GET_LIVE_DATA first device keys: %s" % list(update["devices"][0].keys()))
                self.responseKeysLogged = True
            devices = update.get("devices")
            if devices is None:
                self.logger.error("updateReadings: response missing 'devices' key; top-level keys: %s" % list(update.keys()))
                return
            stamp = update.get("TIMESTAMP_DEVICE_LISTS")
            if not self._discoveryDone:
                # Discovery hasn't succeeded this session (hub unreachable or no device list at startup); run it before trusting any binding.
                self.logger.info("Device discovery has not completed yet; running it now")
                self.createDevices()
                return
            # The stamp catches Gen 2 device-list changes; the new-zone check below catches additions on both
            # generations (Gen 1 INFO has no TIMESTAMP_DEVICE_LISTS, so stamp is None there).
            if stamp is not None and stamp != self._deviceListStamp:
                self.logger.info("Hub device list changed; rediscovering devices")
                self.createDevices()
                return
            zones = self._zonesByName(update)
            # Only ADDED zones trigger rediscovery. A zone that vanishes is handled per poll (ZONE NOT ON HUB) and
            # recovers by itself; an offline stat dropping out of the list must not churn discovery.
            newZones = [z for z in zones if z not in self._knownZones]
            if newZones:
                self.logger.info("New hub zone(s) %s; rediscovering devices" % ", ".join(newZones))
                self.createDevices()
                return
            seen = set()
            for dev in self._liveDevices():
                zoneName = dev.pluginProps.get("zoneName")
                if not zoneName:
                    dev.setErrorStateOnServer("NO HUB ZONE")  # createDevices warned; re-assert so a HUB UNREACHABLE clear doesn't leave it stale
                    continue
                if zoneName in seen:
                    dev.setErrorStateOnServer("DUPLICATE ZONE")  # createDevices warned; the first device wins
                    continue
                seen.add(zoneName)
                if zoneName not in zones:
                    if zoneName not in self._missingZonesWarned:
                        self._missingZonesWarned.add(zoneName)
                        self.logger.warning("Device '%s': hub zone '%s' is not in the hub's device list; not updating it" % (dev.name, zoneName))
                    dev.setErrorStateOnServer("ZONE NOT ON HUB")
                    continue
                self._missingZonesWarned.discard(zoneName)
                self.updateStatState(update, zones[zoneName][0], dev)
        else:
            self._failedPolls += 1
            if self._failedPolls == 3:
                self.logger.warning("Hub unreachable for %d polls; marking devices HUB UNREACHABLE" % self._failedPolls)
            if self._failedPolls >= 3:
                for dev in self._liveDevices():
                    dev.setErrorStateOnServer("HUB UNREACHABLE")

    def _hubHostDevice(self):
        """Return the live neostat that owns hub-level states.

        Hub-level info (firmware, DST, NTP, units, program format) exists
        only on heatmiserNeostat (see Devices.xml). It is written onto the
        device bound to the hub zone at list position 0 (as recorded by the
        last createDevices()) when that is a neostat; otherwise onto the
        bound neostat with the lowest numeric address (non-numeric last).
        If there is no neostat, returns None. We re-resolve per call rather
        than caching, so the host device is always the current one after any
        rediscovery or SUPERSEDED replacement.

        Fallback (before discovery has completed): whichever live neostat
        has address 0. Non-numeric addresses are skipped silently. Addresses
        are refreshed only for bound devices, so once discovery has completed
        a stale address is never trusted.
        """
        hostZone = getattr(self, "_hubHostZone", None)
        if hostZone:
            for dev in self._liveDevices():
                if dev.pluginProps.get("zoneName") == hostZone:
                    if dev.deviceTypeId == "heatmiserNeostat":
                        return dev
                    break
        if self._discoveryDone:
            def addressKey(dev):
                try:
                    return (0, int(dev.address))
                except (TypeError, ValueError):
                    return (1, 0)
            neostats = sorted((d for d in self._liveDevices()
                               if self._zoneName(d) and d.deviceTypeId == "heatmiserNeostat"), key=addressKey)
            if not neostats:
                self.logger.debug("No live bound neostat for hub-level states (host zone '%s'); hub-level states not updated" % hostZone)
                return None
            self.logger.debug("Hub host zone '%s' has no neostat device; using '%s' (lowest-address bound neostat) for hub-level states"
                              % (hostZone, neostats[0].name))
            return neostats[0]
        host = None
        duplicates = []
        for dev in indigo.devices.iter("self"):
            if "SUPERSEDED" in dev.name or dev.deviceTypeId != "heatmiserNeostat":
                continue
            try:
                if int(dev.address) != 0:
                    continue
            except (TypeError, ValueError):
                continue
            if host is None:
                host = dev
            else:
                duplicates.append(dev)

        if duplicates:
            # Multiple live devices claim address 0 — that's a rediscovery
            # inconsistency and exactly the class of bug the old cached
            # self.neoDevice attribute made silent. Log it loudly.
            names = ", ".join([host.name] + [d.name for d in duplicates])
            self.logger.warning(
                "Multiple devices have address 0 (%s). Using '%s'; "
                "rename one with SUPERSEDED to silence this warning."
                % (names, host.name)
            )
        return host


    def updateStatState(self, neoRep, index, indigoDevice):
        devData = neoRep["devices"][index]
        # Read device type from pluginProps (stored during createDevices)
        deviceType = int(indigoDevice.pluginProps.get("neoDeviceType", devData.get("DEVICE_TYPE", 0)))

        if indigoDevice.deviceTypeId == "heatmiserNeoTimeclock":
            # Timeclock device (e.g. hot water, towel rails) — on/off with temperature
            if devData.get("OFFLINE", False):
                indigoDevice.setErrorStateOnServer('OFFLINE')
                return
            timerOn = devData.get("TIMER_ON", devData.get("TIMER", False))
            curTemp = round(float(devData.get("ACTUAL_TEMP", devData.get("CURRENT_TEMPERATURE", 0))), 1)
            frost = devData.get("STANDBY", False)
            holdOn = devData.get("HOLD_ON", devData.get("TEMP_HOLD", False))
            if frost:
                shortMode = "Frost"
            elif holdOn:
                shortMode = "Boost"
            else:
                shortMode = "Auto"
            stateList = [
                {"key": "onOffState", "value": timerOn},
                {"key": "ShortMode", "value": shortMode},
                {"key": "Away", "value": devData.get("AWAY", False)},
                {"key": "Holiday", "value": devData.get("HOLIDAY", False)},
                {"key": "HoldTimeRemaining", "value": devData.get("HOLD_TIME", "0:00")},
            ]
            if curTemp > 0:
                stateList.append({"key": "temperatureInput1", "value": curTemp, "uiValue": "%s °C" % curTemp, "clearErrorState": True})
            indigoDevice.updateStatesOnServer(stateList)
            if timerOn:
                indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
            else:
                indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)

        elif deviceType in (1, 7, 12, 13, 24):
            # Neostat (1), NeoAir (7), NeoStat-e (12), NeoAir (13), NeoStat V2 (24)
            if devData.get("OFFLINE", False):
                indigoDevice.setErrorStateOnServer('OFFLINE')
                return

            heating = devData.get("HEAT_ON", devData.get("HEATING", False))
            preHeat = devData.get("PREHEAT_ACTIVE", devData.get("PREHEAT", False))
            timerOn = devData.get("TIMER_ON", devData.get("TIMER", False))
            heatIsOn = heating or preHeat or timerOn
            curTemp = round(float(devData.get("ACTUAL_TEMP", devData.get("CURRENT_TEMPERATURE", 0))), 1)

            frost = devData.get("STANDBY", False)
            tempHold = devData.get("HOLD_ON", devData.get("TEMP_HOLD", False))
            if frost:
                hvacMode = indigo.kHvacMode.Cool
                shortMode = "Frost"
            elif tempHold:
                hvacMode = indigo.kHvacMode.Heat
                shortMode = "Boost"
            else:
                hvacMode = indigo.kHvacMode.ProgramHeat
                shortMode = "Auto"

            stateList = [
                {"key": "heatIsOn", "value": heatIsOn},
                {"key": "preHeat", "value": preHeat},
                {"key": "setpointHeat", "value": devData.get("SET_TEMP", devData.get("CURRENT_SET_TEMPERATURE", 0))},
                {"key": "hvacOperationMode", "value": hvacMode},
                {"key": "ShortMode", "value": shortMode},
                {"key": "Away", "value": devData.get("AWAY", False)},
                {"key": "Holiday", "value": devData.get("HOLIDAY", False)},
                {"key": "HoldTimeRemaining", "value": devData.get("HOLD_TIME", "0:00")},
                {"key": "HoldTemperature", "value": devData.get("HOLD_TEMP", 0)},
                {"key": "WindowOpen", "value": devData.get("WINDOW_OPEN", False)},
                {"key": "lowBattery", "value": devData.get("LOW_BATTERY", False)},
                {"key": "Locked", "value": devData.get("LOCK", False)},
            ]

            # Holiday_End is a hub-level field — set on every neostat so all devices show it
            holidayEnd = neoRep.get("HOLIDAY_END", 0)
            if holidayEnd and str(holidayEnd) not in ("0", ""):
                if isinstance(holidayEnd, (int, float)):
                    endDate = datetime.datetime.fromtimestamp(holidayEnd).strftime("%d/%m/%Y %H:%M")
                else:
                    endDate = str(holidayEnd).strip()
                stateList.append({"key": "Holiday_End", "value": endDate})
            else:
                stateList.append({"key": "Holiday_End", "value": "None"})

            floorTemp = devData.get("CURRENT_FLOOR_TEMPERATURE", 127)
            if floorTemp != 127:
                stateList.append({"key": "FloorTemperature", "value": round(float(floorTemp), 1),
                                   "uiValue": "%s °C" % round(float(floorTemp), 1)})

            if curTemp > 0:
                stateList.append({"key": "temperatureInput1", "value": curTemp, "uiValue": "%s °C" % curTemp, "clearErrorState": True})
            else:
                self.logger.error("Neo temperature error for %s" % indigoDevice.name)

            indigoDevice.updateStatesOnServer(stateList)

            if heatIsOn:
                indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.HvacHeating)
            else:
                indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.HvacHeatMode)

        elif deviceType == 6:
            # Neoplug
            timerOn = devData.get("TIMER_ON", devData.get("TIMER", False))
            indigoDevice.updateStateOnServer(key="onOffState", value=timerOn, clearErrorState=True)
            if timerOn:
                indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
            else:
                indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)

        elif deviceType == 0:
            indigoDevice.setErrorStateOnServer('OFFLINE')

        elif deviceType == 14:
            # Wireless air sensor
            curTemp = round(float(devData.get("ACTUAL_TEMP", devData.get("CURRENT_TEMPERATURE", 0))), 1)

            if devData.get("OFFLINE", False):
                stateList = [
                    {"key": "lowBattery", "value": devData.get("LOW_BATTERY", False)},
                    {"key": "sensorValid", "value": False},
                    {"key": "temperatureInput1", "value": 0, "uiValue": "offline"},
                ]
                indigoDevice.updateStatesOnServer(stateList)
                indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                indigoDevice.setErrorStateOnServer('OFFLINE')  # same as stats/timeclocks: offline is an error state, not a healthy "offline" label
                return

            stateList = [
                {"key": "lowBattery", "value": devData.get("LOW_BATTERY", False)},
            ]

            if curTemp > 0:
                stateList.append({"key": "temperatureInput1", "value": curTemp, "uiValue": "%s °C" % curTemp, "clearErrorState": True})
                stateList.append({"key": "sensorValid", "value": True})
            else:
                indigoDevice.setErrorStateOnServer('INVALID TEMPERATURE')
                stateList.append({"key": "sensorValid", "value": False})

            indigoDevice.updateStatesOnServer(stateList)

        else:
            self.logger.error("updateStatState: Unknown device type '%s'" % deviceType)


    def getNeoData(self, cmdPhrase):
        if not self.commsEnabled:
            return ""
        if self.connectionMode == "wss" and self.neohubToken and HAS_WEBSOCKETS:
            return self._get_neo_data_wss(cmdPhrase)
        else:
            if self.connectionMode == "wss" and not getattr(self, '_wss_fallback_warned', False):
                self.logger.warning("WSS mode configured but not available (token=%s, library=%s) — using TCP fallback"
                    % ("set" if self.neohubToken else "missing", "available" if HAS_WEBSOCKETS else "missing"))
                self._wss_fallback_warned = True
            return self._get_neo_data_tcp(cmdPhrase)

    def _send_wss(self, cmdPhrase):
        """Send command via WSS over a fresh connection and return parsed response.

        The Heatmiser WSS protocol uses a two-layer JSON envelope: the outer
        message has message_type + message fields, the inner payload contains
        the API token and COMMANDS array. The hub may send async messages
        between command/response pairs, so we filter for hm_set_command_response.

        A new connection is opened per call (and closed in finally). An earlier
        persistent-connection design got into a state where the websockets
        library raised ProtocolError("incorrect masking") under Python 3.13 /
        websockets 15.x — opening fresh per call avoids that class of bug
        entirely at the cost of one TLS handshake per poll.
        """
        with self._wss_lock:
            self._command_id += 1
            cmd_id = self._command_id
            # NeoHub WSS API expects Python-style dict string representation, not JSON
            inner_command = json.dumps({
                "token": self.neohubToken,
                "COMMANDS": [{"COMMAND": str(json.loads("{" + cmdPhrase + "}")), "COMMANDID": cmd_id}]
            })
            message = json.dumps({
                "message_type": "hm_get_command_queue",
                "message": inner_command
            })
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE  # NeoHub uses self-signed cert on local network
            uri = "wss://%s:4243" % self.neohubIP
            ws = ws_connect(uri, ssl=ssl_context, open_timeout=8)
            try:
                ws.send(message)
                if self.logComms:
                    log_msg = message.replace(self.neohubToken, "***") if self.neohubToken else message
                    self.logger.info("WSS --> %s" % log_msg)
                for _ in range(5):
                    response_text = ws.recv(timeout=10)
                    if self.logComms:
                        self.logger.info("WSS <-- %s" % response_text)
                    try:
                        response = json.loads(response_text)
                    except json.JSONDecodeError as exc:
                        self.logger.error("WSS: failed to parse response: %s" % exc)
                        continue
                    msg_type = response.get("message_type", "unknown")
                    if msg_type == "hm_set_command_response":
                        try:
                            return json.loads(response["response"])
                        except (json.JSONDecodeError, KeyError) as exc:
                            self.logger.error("WSS: failed to parse command response: %s" % exc)
                            return ""
                    else:
                        self.logger.debug("WSS: skipping message type '%s'" % msg_type)
                self.logger.warning("No command response received after 5 messages")
                return ""
            finally:
                try:
                    ws.close()
                except Exception as exc:
                    self.logger.debug("WSS close error (ignored): %s" % exc)

    def _get_neo_data_wss(self, cmdPhrase):
        """WSS equivalent of _get_neo_data_tcp. Each call opens its own
        connection inside _send_wss and closes it in finally."""
        try:
            result = self._send_wss(cmdPhrase)
            self.connectErrorCount = 0
            self.sendErrorCount = 0
            if isinstance(result, dict) and "error" in result:
                self.logger.error("Command: {%s}" % cmdPhrase)
                self.logger.error(result["error"])
                return ""
            return result
        except (ConnectionClosed, ConnectionError, TimeoutError, OSError) as exc:
            self.connectErrorCount += 1
            if self.connectErrorCount <= 3 or self.connectErrorCount % 10 == 0:
                self.logger.error("getNeoData WSS: connection error #%d (%s)" % (self.connectErrorCount, exc))
            return ""
        except Exception as exc:
            self.sendErrorCount += 1
            if self.sendErrorCount <= 3 or self.sendErrorCount % 10 == 0:
                self.logger.error("getNeoData WSS: unexpected error #%d [%s]: %s" % (self.sendErrorCount, type(exc).__name__, exc))
            return ""

    def _get_neo_data_tcp(self, cmdPhrase):
        tcp_ip = self.neohubIP
        tcp_port = 4242
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(8)
        try:
            try:
                sock.connect((tcp_ip, tcp_port))
                self.connectErrorCount = 0
            except socket.timeout:
                self.connectErrorCount += 1
                if self.connectErrorCount <= 3 or self.connectErrorCount % 10 == 0:
                    self.logger.error("getNeoData TCP: Socket timeout error (attempt %d)" % self.connectErrorCount)
                return ""
            except Exception as exc:
                self.connectErrorCount += 1
                if self.connectErrorCount <= 3 or self.connectErrorCount % 10 == 0:
                    self.logger.error("getNeoData TCP: Socket connect error (attempt %d): %s" % (self.connectErrorCount, exc))
                return ""
            cmdPhrase = b"{"+bytes(cmdPhrase, 'ascii')+b"}"
            try:
                if self.logComms:
                    self.logger.info("--> %s" % cmdPhrase)
                sock.send(cmdPhrase+b"\0")
                dataj = sock.recv(4096)
                while ((b"GET_LIVE_DATA" in cmdPhrase or b"INFO" in cmdPhrase) and (b"}]}" not in dataj[len(dataj)-5:len(dataj)-1])) or ((b"GET_ENGINEERS" in cmdPhrase or b"ENGINEERS_DATA" in cmdPhrase or b"GET_HOURSRUN" in cmdPhrase or b"GET_TEMPLOG" in cmdPhrase) and (b"}}" not in dataj[len(dataj)-4:len(dataj)-1])):
                    chunk = sock.recv(4096)
                    if not chunk:
                        raise ConnectionError("NeoHub connection closed unexpectedly")
                    dataj = dataj + chunk
                self.sendErrorCount = 0
                if self.logComms:
                    self.logger.info("<-- %s" % dataj)
            except socket.error as exc:
                self.sendErrorCount += 1
                if self.sendErrorCount <= 3 or self.sendErrorCount % 10 == 0:
                    self.logger.error("getNeoData TCP: Socket send error (attempt %d): %s" % (self.sendErrorCount, exc))
                return ""
            if dataj is not None:
                datak = re.sub(b'[^\s!-~]', b'', dataj)   #Filter extraneous characters which cause json decode to fail
                try:
                    data = json.loads(datak)
                except (json.JSONDecodeError, ValueError) as exc:
                    self.logger.error("getNeoData TCP: JSON parse error: %s" % exc)
                    if self.logComms:
                        self.logger.error("Raw response: %s" % datak[:500])
                    return ""
                self.connectErrorCount = 0
                self.sendErrorCount = 0
                if "error" in data:
                    self.logger.error("Command: %s" % cmdPhrase)
                    self.logger.error(data["error"])
                    return ""
                else:
                    return data
            else:
                return ""
        finally:
            sock.close()


    def checkTime(self):
        dt = datetime.datetime.now()
        if self.timeUpdateRequired == None:
            self.timeUpdateRequired = True
        if (dt.hour == 3) and self.timeUpdateRequired:
            update = self.getNeoData("\"SET_TIME\":["+str(dt.hour)+", "+str(dt.minute)+"]")
            if update and "result" in update:
                self.logger.info("Device time synchronised with Indigo")
            else:
                self.logger.error("Device time sync failed")

            update = self.getNeoData("\"SET_DATE\":["+str(dt.year)+", "+str(dt.month)+", "+str(dt.day)+"]")
            if update and "result" in update:
                self.logger.info("Device date synchronised with Indigo")
            else:
                self.logger.error("Device date sync failed")
                
            self.timeUpdateRequired = False
        elif (dt.hour == 4) and self.timeUpdateRequired == False:
            self.timeUpdateRequired = True


    def checkDCB(self):
        """ Fetch DCB data once per day to update Hub firmware version and DST/NTP info
                and store as states in first Neostat device """
        dt = datetime.datetime.now()
        if self.dcbUpdateRequired == None:
            self.dcbUpdateRequired = True
        if (dt.hour == 0) and self.dcbUpdateRequired:
            self.updateDCB()
            self.dcbUpdateRequired = False
        elif (dt.hour == 1) and self.dcbUpdateRequired == False:
            self.dcbUpdateRequired = True

            
    def updateDCB(self):
        update = self.getNeoData("\"GET_SYSTEM\":0" if self.neohubGen2 else "\"READ_DCB\":100")
        if update == "":
            return
        self.logger.debug("GET_SYSTEM keys: %s" % list(update.keys()))
        hubDevice = self._hubHostDevice()
        if hubDevice is None:
            return
        hubDevice.updateStateOnServer(key="HubFirmwareVersion", value=str(update.get("HUB_VERSION", update.get("Firmware version", "unknown"))))
        hubDevice.updateStateOnServer(key="DST_Auto", value=str(update.get("DST_AUTO", update.get("DSTAUTO", ""))))
        hubDevice.updateStateOnServer(key="DST_On", value=str(update.get("DST_ON", update.get("DSTON", ""))))
        hubDevice.updateStateOnServer(key="NTP_Status", value=str(update.get("NTP_ON", update.get("NTP", ""))))
        hubDevice.updateStateOnServer(key="Units", value="deg"+str(update.get("CORF", "")))
        pfi = update.get("FORMAT", update.get("PROGFORMAT", 0))
        pfiString = "Unknown"
        if pfi == 0:
            pfiString = "Non-programmable"
        elif pfi == 1:
            pfiString = "24 hours fixed"
        elif pfi == 2:
            pfiString = "5day/2day"
        elif pfi == 3:
            pfiString = "Illegal"
        elif pfi == 4:
            pfiString = "7day"
        else:
            pfiString = str(pfi)
        hubDevice.updateStateOnServer(key="Prog_Format", value=pfiString)
            

    def checkEng(self):
        """ Fetch Engineering data once per day """
        dt = datetime.datetime.now()
        if self.engUpdateRequired == None:
            self.engUpdateRequired = True
        if (dt.hour == 5) and self.engUpdateRequired:
            self.updateEng()
            self.engUpdateRequired = False
        elif (dt.hour == 6) and self.engUpdateRequired == False:
            self.engUpdateRequired = True

            
    def updateEng(self):
        update = self.getNeoData("\"GET_ENGINEERS\":0" if self.neohubGen2 else "\"ENGINEERS_DATA\":0")
        if update != "":
            self.logger.debug("GET_ENGINEERS keys: %s" % list(update.keys())[:10])
            # Log first device's engineer data keys for field verification
            for key, val in update.items():
                if isinstance(val, dict):
                    self.logger.debug("GET_ENGINEERS device keys: %s" % list(val.keys()))
                    break
            seen = set()
            for dev in indigo.devices.iter("self"):
                if "SUPERSEDED" in dev.name:
                    continue
                zoneName = self._zoneName(dev)
                if zoneName in seen:
                    continue  # duplicate claim; the first device wins, as in updateReadings
                if zoneName:
                    seen.add(zoneName)
                # Skip sensors, neoplugs, and timeclocks — they don't have engineering states
                if dev.deviceTypeId in ("heatmiserNeoSensor", "heatmiserNeoplug", "heatmiserNeoTimeclock"):
                    continue
                if not zoneName:
                    continue
                if zoneName not in update:
                    self.logger.debug("GET_ENGINEERS has no entry for zone '%s' (device '%s')" % (zoneName, dev.name))
                    continue
                try:
                    devData = update[zoneName]
                    frostTemp = devData.get("FROST_TEMP", devData.get("FROST TEMPERATURE", None))
                    if frostTemp is not None:
                        dev.updateStateOnServer(key="FrostTemp", value=frostTemp)
                    swDiff = devData.get("SWITCHING DIFFERENTIAL", 0)
                    if swDiff == 0:
                        swDiff = 0.5
                    dev.updateStateOnServer(key="SwitchDiff", value=swDiff)
                    roc = devData.get("RATE OF CHANGE", "")
                    dev.updateStateOnServer(key="ROC", value=str(roc))
                except Exception as exc:
                    self.logger.exception("Cannot update GET_ENGINEERS for %s" % dev.name)
         

    def ntpOn(self):
        update = self.getNeoData("\"NTP_ON\":0")
        if not update or "result" not in update:
            self.logger.error("NTP_ON command failed")
        self.sleep(1)
        update = self.getNeoData("\"DST_ON\":0")
        if not update or "result" not in update:
            self.logger.error("DST_ON command failed")


    def ntpOff(self):
        update = self.getNeoData("\"NTP_OFF\":0")
        if not update or "result" not in update:
            self.logger.error("NTP_OFF command failed")
        self.sleep(1)
        update = self.getNeoData("\"DST_OFF\":0")
        if not update or "result" not in update:
            self.logger.error("DST_OFF command failed")
        
    
    ########################################
    # Menu Item functions
    ######################

    def discoverNeohub(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(5)
        try:
            sock.sendto(b"hubseek", ("255.255.255.255", 19790))
            data, addr = sock.recvfrom(1024)
            response = json.loads(data.decode())
            foundIp = response.get("ip", "")
            deviceId = response.get("device_id", "").strip()
            if foundIp:
                ipChanged = foundIp != self.neohubIP
                if ipChanged:
                    self.neohubIP = foundIp
                    self.pluginPrefs["neohubIP"] = foundIp
                    self.savePluginPrefs()
                self.logger.info("NeoHub found at %s (device: %s)" % (foundIp, deviceId))
            else:
                self.logger.warning("NeoHub responded but no IP in response")
        except socket.timeout:
            self.logger.warning("No NeoHub found on network (timed out)")
        except json.JSONDecodeError as exc:
            self.logger.error("HubSeek: received non-JSON response from hub: %s" % exc)
        except Exception as exc:
            self.logger.error("HubSeek error: %s" % exc)
        finally:
            sock.close()

    def testConnection(self):
        mode = "WSS (port 4243)" if (self.connectionMode == "wss" and self.neohubToken and HAS_WEBSOCKETS) else "TCP (port 4242)"
        self.logger.info("Testing %s connection to %s..." % (mode, self.neohubIP))
        result = self.getNeoData('"GET_LIVE_DATA":0' if self.neohubGen2 else '"INFO":0')
        if result and isinstance(result, dict):
            count = len(result.get("devices", []))
            self.logger.info("Connection OK — found %d devices" % count)
        elif result:
            self.logger.info("Connection OK — received response")
        else:
            self.logger.error("Connection test failed")


    ########################################
    # Action functions
    ######################

    def setCool(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        if dev.deviceTypeId not in ("heatmiserNeostat", "heatmiserNeoTimeclock"):
            self.logger.warning("setCool: action not supported for device type '%s'" % dev.deviceTypeId)
            return
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        update = self.getNeoData("\"FROST_ON\":[\""+device+"\"]")
        if update and "result" in update:
            self.logger.info("%s set to Cool" % device)
        else:
            self.logger.error("%s Cool command failed" % device)              

    def setAuto(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        if dev.deviceTypeId not in ("heatmiserNeostat", "heatmiserNeoTimeclock"):
            self.logger.warning("setAuto: action not supported for device type '%s'" % dev.deviceTypeId)
            return
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        zilch = "0"
        holdTemp = "20"
        update = self.getNeoData("\"FROST_OFF\":[\""+device+"\"]")
        if not (update and "result" in update):
            self.logger.error("%s Auto command failed (FROST_OFF)" % device)
            return
        update = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"Off\""+", \"hours\":"+zilch+", \"minutes\":"+zilch+"}, \""+device+"\"]")
        if update and "result" in update:
            self.logger.info("%s set to Auto" % device)
        else:
            self.logger.error("%s Auto command failed" % device)
 
    def setOverride(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        holdTemp = pluginAction.props["overrideTemp"]
        holdHours = pluginAction.props["numberOfHours"]
        if holdHours == "0.5":
        	holdHours = "0"
        	holdMins = "30"
        else:
        	holdMins = "0"
        update = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"Off\""+", \"hours\":"+holdHours+", \"minutes\":"+holdMins+"}, \""+device+"\"]")
        if update and "result" in update:
            if holdHours[0] == "0":
                holdHours = holdHours[1:]
            self.logger.info("%s set to Override at %s degrees for %s hours" % (device, holdTemp, holdHours))
        else:
            self.logger.error("%s Override command failed" % device)
            
 
            
    ########################################
    # Timeclock and Holiday Action callbacks
    ######################
    def timerBoost(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        minutes = pluginAction.props.get("boostMinutes", "30")
        update = self.getNeoData("\"TIMER_HOLD_ON\":[%s, \"%s\"]" % (minutes, device))
        if update and "result" in update:
            self.logger.info("%s timer boost on for %s minutes" % (device, minutes))
        else:
            self.logger.error("%s timer boost command failed" % device)

    def timerBoostOff(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        update = self.getNeoData("\"TIMER_HOLD_ON\":[0, \"%s\"]" % device)
        if update and "result" in update:
            self.logger.info("%s timer boost cancelled" % device)
        else:
            self.logger.error("%s cancel timer boost failed" % device)

    def setHoliday(self, pluginAction):
        endDateStr = pluginAction.props.get("holidayEndDate", "")
        endTimeStr = pluginAction.props.get("holidayEndTime", "12:00")
        if not endDateStr:
            self.logger.error("Set Holiday: end date is required (DD/MM/YYYY)")
            return
        try:
            endDate = datetime.datetime.strptime(endDateStr.strip(), "%d/%m/%Y")
        except ValueError:
            self.logger.error("Set Holiday: invalid date format '%s' (expected DD/MM/YYYY)" % endDateStr)
            return
        try:
            timeParts = endTimeStr.strip().split(":")
            endHour = int(timeParts[0])
            endMinute = int(timeParts[1]) if len(timeParts) > 1 else 0
            endDate = endDate.replace(hour=endHour, minute=endMinute)
        except (ValueError, IndexError):
            self.logger.error("Set Holiday: invalid time format '%s' (expected HH:MM)" % endTimeStr)
            return
        now = datetime.datetime.now()
        if endDate <= now:
            self.logger.error("Set Holiday: end date %s is not in the future" % endDate.strftime("%d/%m/%Y %H:%M"))
            return
        startStr = now.strftime("%H%M%S%d%m%Y")
        endStr = endDate.strftime("%H%M00%d%m%Y")
        update = self.getNeoData('"HOLIDAY":["%s","%s"]' % (startStr, endStr))
        if update and "result" in update:
            self.logger.info("Holiday mode set until %s" % endDate.strftime("%d/%m/%Y %H:%M"))
        else:
            self.logger.error("Set Holiday command failed")

    def cancelHoliday(self, pluginAction):
        update = self.getNeoData('"CANCEL_HOLIDAY":0')
        if update and "result" in update:
            self.logger.info("Holiday mode cancelled")
        else:
            self.logger.error("Cancel Holiday command failed")

    def awayOn(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        update = self.getNeoData('"AWAY_ON":["%s"]' % device)
        if update and "result" in update:
            self.logger.info("%s away mode on" % device)
        else:
            self.logger.error("%s away on command failed" % device)

    def awayOff(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        update = self.getNeoData('"AWAY_OFF":["%s"]' % device)
        if update and "result" in update:
            self.logger.info("%s away mode off" % device)
        else:
            self.logger.error("%s away off command failed" % device)

    def lockKeypad(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        pin = pluginAction.props.get("lockPin", "0000")
        digits = [int(d) for d in pin[:4]]
        update = self.getNeoData('"LOCK":[[%s], ["%s"]]' % (",".join(str(d) for d in digits), device))
        if update and "result" in update:
            self.logger.info("%s keypad locked" % device)
        else:
            self.logger.error("%s lock keypad command failed" % device)

    def unlockKeypad(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        update = self.getNeoData('"UNLOCK":["%s"]' % device)
        if update and "result" in update:
            self.logger.info("%s keypad unlocked" % device)
        else:
            self.logger.error("%s unlock keypad command failed" % device)

    def cancelHold(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        update = self.getNeoData('"HOLD":[{"temp":20, "id":"Off", "hours":0, "minutes":0}, "%s"]' % device)
        if update and "result" in update:
            self.logger.info("%s hold cancelled" % device)
        else:
            self.logger.error("%s cancel hold command failed" % device)

    def setFrostTemp(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        temp = pluginAction.props.get("frostTemp", "12")
        update = self.getNeoData('"SET_FROST":[%s, "%s"]' % (temp, device))
        if update and "result" in update:
            self.logger.info("%s frost temperature set to %s°C" % (device, temp))
        else:
            self.logger.error("%s set frost temp command failed" % device)

    def identifyDevice(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        update = self.getNeoData('"IDENTIFY":[1, 3, ["%s"]]' % device)
        if update and "result" in update:
            self.logger.info("%s identify LED flashing" % device)
        else:
            self.logger.error("%s identify command failed" % device)

    def getHoursRun(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        update = self.getNeoData('"GET_HOURSRUN":"%s"' % device)
        if isinstance(update, dict) and update:
            self.logger.info("%s hours run: %s" % (device, json.dumps(update)))
        else:
            self.logger.error("%s get hours run command failed (response: %r)" % (device, update))

    def getTempLog(self, pluginAction):
        dev = indigo.devices[pluginAction.deviceId]
        device = self._zoneName(dev)
        if not device:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        update = self.getNeoData('"GET_TEMPLOG":["%s"]' % device)
        if isinstance(update, dict) and update:
            self.logger.info("%s temp log: %s" % (device, json.dumps(update)))
        else:
            self.logger.error("%s get temp log command failed (response: %r)" % (device, update))

    def changeIp(self, action):
        oldIP = self.neohubIP
        newIp = action.props.get("newIp", "")
        if newIp == "":
            self.logger.error("Invalid IP address supplied")
            return
        if newIp != oldIP:
            self.neohubIP = newIp
            self.logger.info("Neohub IP address is now %s" % self.neohubIP)
                


    ########################################
    # NeoPlug Action callback
    ######################
    # Main switch action bottleneck called by Indigo Server.
    def actionControlDevice(self, action, dev):
        zone = self._zoneName(dev)
        if not zone:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            resDict = self.getNeoData("\"TIMER_ON\":[\""+zone+"\"]")
            if resDict and "result" in resDict:
                dev.updateStateOnServer("onOffState", True)
                dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
            else:
                self.logger.error("%s turn on command failed" % dev.name)
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            resDict = self.getNeoData("\"TIMER_OFF\":[\""+zone+"\"]")
            if resDict and "result" in resDict:
                dev.updateStateOnServer("onOffState", False)
                dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
            else:
                self.logger.error("%s turn off command failed" % dev.name)
        else:
            self.logger.error("This action is not currently supported")
            
                
    ########################################
    # NeoStat Action callback
    ######################
    # Main thermostat action bottleneck called by Indigo Server.
    def actionControlThermostat(self, action, dev):
        zone = self._zoneName(dev)
        if not zone:
            self.logger.error("'%s' is not bound to a hub zone; command not sent" % dev.name)
            return
        if action.thermostatAction == indigo.kThermostatAction.SetHeatSetpoint:
            newSetpoint = str(action.actionValue)
            update = self.getNeoData("\"SET_TEMP\":["+newSetpoint+", \""+zone+"\"]")
            if update and "result" in update:
                dev.updateStateOnServer("setpointHeat", newSetpoint)
                self.logger.info("%s setpoint set to %s degC" % (dev.name, newSetpoint))
            else:
                self.logger.error("%s setpoint command failed" % dev.name)
            
        elif action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint:
            newSetpoint = str(dev.heatSetpoint - action.actionValue)
            update = self.getNeoData("\"SET_TEMP\":["+newSetpoint+", \""+zone+"\"]")
            if update and "result" in update:
                dev.updateStateOnServer("setpointHeat", newSetpoint)
                self.logger.info("%s setpoint decreased to %s degC" % (dev.name, newSetpoint))
            else:
                self.logger.error("%s setpoint command failed" % dev.name)
        
        elif action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint:
            newSetpoint = str(dev.heatSetpoint + action.actionValue)
            update = self.getNeoData("\"SET_TEMP\":["+newSetpoint+", \""+zone+"\"]")
            if update and "result" in update:
                dev.updateStateOnServer("setpointHeat", newSetpoint)
                self.logger.info("%s setpoint increased to %s degC" % (dev.name, newSetpoint))
            else:
                self.logger.error("%s setpoint command failed" % dev.name)
                    
        elif action.thermostatAction == indigo.kThermostatAction.SetHvacMode:
            newMode = action.actionMode
            resDict = None
            if newMode == indigo.kHvacMode.Off:
                self.logger.error("Thermostat does not have an 'Off' mode")
                return False
            elif newMode == indigo.kHvacMode.HeatCool:
                self.logger.info("Setting %s to 'Auto' mode" % dev.name)
                resDict = self.getNeoData("\"FROST_OFF\":[\""+zone+"\"]")
                if not (resDict and "result" in resDict):
                    self.logger.error("%s SetHvacMode: FROST_OFF command failed" % dev.name)
                    return
                holdTemp = "20"
                zilch = "0"
                resDict = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"Off\""+", \"hours\":"+zilch+", \"minutes\":"+zilch+"}, \""+zone+"\"]")
            elif newMode == indigo.kHvacMode.Heat:
                self.logger.info("Setting %s to 'Heat' mode" % dev.name)
                resDict = self.getNeoData("\"FROST_OFF\":[\""+zone+"\"]")
                if not (resDict and "result" in resDict):
                    self.logger.error("%s SetHvacMode: FROST_OFF command failed" % dev.name)
                    return
                holdTemp = "20"
                holdHours = "1"
                holdMins = "0"
                resDict = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"On\""+", \"hours\":"+holdHours+", \"minutes\":"+holdMins+"}, \""+zone+"\"]")
            elif newMode == indigo.kHvacMode.Cool:
                self.logger.info("Setting %s to 'Cool' mode" % dev.name)
                holdTemp = "20"
                zilch = "0"
                resDict = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"Off\""+", \"hours\":"+zilch+", \"minutes\":"+zilch+"}, \""+zone+"\"]")
                if not (resDict and "result" in resDict):
                    self.logger.error("%s SetHvacMode: HOLD command failed" % dev.name)
                    return
                resDict = self.getNeoData("\"FROST_ON\":[\""+zone+"\"]")
            else:
                self.logger.error("%s: HVAC mode %s is not supported" % (dev.name, newMode))
                return
            if resDict and "result" in resDict:
                dev.updateStateOnServer("hvacOperationMode", newMode)
            else:
                self.logger.error("%s SetHvacMode command failed" % dev.name)
            
        elif action.thermostatAction in [indigo.kThermostatAction.RequestStatusAll, indigo.kThermostatAction.RequestMode,
            indigo.kThermostatAction.RequestEquipmentState, indigo.kThermostatAction.RequestTemperatures, indigo.kThermostatAction.RequestHumidities,
            indigo.kThermostatAction.RequestDeadbands, indigo.kThermostatAction.RequestSetpoints]:
            self.logger.info("Status automatically updated every 30 seconds")
        
        elif (action.thermostatAction == indigo.kThermostatAction.DecreaseCoolSetpoint) or (action.thermostatAction == indigo.kThermostatAction.IncreaseCoolSetpoint):
            self.logger.debug("Cool setpoint change ignored — Heatmiser devices do not support cooling")
            
        else:
            self.logger.error("Action %s is not currently supported" % action.thermostatAction)


