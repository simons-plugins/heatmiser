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
        self.neoDevice = None
        self._wss = None
        self._wss_lock = threading.Lock()
        self._command_id = 0
        self.timeUpdateRequired = None
        self.dcbUpdateRequired = None
        self.engUpdateRequired = None
        self.firstTime = True
        self.responseKeysLogged = False


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
        self._close_wss()

        
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
                    self.checkDCB()
                    self.checkEng()
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
            needs_reconnect = False
            if self.connectionMode != oldMode or self.neohubToken != oldToken:
                needs_reconnect = True
                if self.connectionMode == "wss" and self.neohubToken:
                    self.logger.info("Using WSS connection (port 4243)")
                else:
                    self.logger.info("Using legacy TCP connection (port 4242)")
            oldIP = self.neohubIP
            self.neohubIP = valuesDict.get("neohubIP")
            if self.neohubIP != oldIP:
                self.logger.info("Neohub IP address is now %s" % self.neohubIP)
                needs_reconnect = True
            if needs_reconnect:
                self._close_wss()

                        
    ########################################
    # Heatmiser Neo specific functions
    
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

        neoInfo = self.getNeoData("\"GET_LIVE_DATA\":0" if self.neohubGen2 else "\"INFO\":0")
        try:
            max_devices = len(neoInfo["devices"])
        except Exception as exc:
            self.logger.error("Cannot detect devices: %s" % exc)
            max_devices = 0
        for stat in range(0, max_devices):
            devData = neoInfo["devices"][stat]
            devName = devData.get("ZONE_NAME", devData.get("device", "unknown"))
            deviceType = deviceTypeMap.get(devName, devData.get("DEVICE_TYPE", 0)) if self.neohubGen2 else devData.get("DEVICE_TYPE", 0)
            if deviceType == 14:
                # This is a wireless air sensor
                device = None
                for dev in indigo.devices.iter("self"):
                    if "SUPERSEDED" not in dev.name:
                        if int(dev.address) == stat:
                            device = dev
                            # Check if existing device has correct type
                            if device.deviceTypeId != "heatmiserNeoSensor":
                                self.logger.info("Upgrading sensor device %s to new device type" % device.name)
                                # Rename old device
                                device.name = device.name + " SUPERSEDED"
                                device.replaceOnServer()
                                device = None
                if device == None:
                    self.logger.info("Creating Heatmiser sensor device for %s" % devName)
                    device = indigo.device.create(protocol=indigo.kProtocol.Plugin,
                    address=stat,
                    name=devName,
                    pluginId="com.racarter.indigoplugin.heatmiser-neo",
                    deviceTypeId="heatmiserNeoSensor",
                    props={"neoDeviceType": str(deviceType)})
                else:
                    # Ensure device type is stored in pluginProps
                    localPropsCopy = device.pluginProps
                    if str(localPropsCopy.get("neoDeviceType", "")) != str(deviceType):
                        localPropsCopy["neoDeviceType"] = str(deviceType)
                        device.replacePluginPropsOnServer(localPropsCopy)
                self.updateStatState(neoInfo, stat, device)
                continue
            isTimeclock = devData.get("TIMECLOCK", False)
            if deviceType == 6:
                expectedTypeId = "heatmiserNeoplug"
            elif isTimeclock:
                expectedTypeId = "heatmiserNeoTimeclock"
            else:
                expectedTypeId = "heatmiserNeostat"
            device = None
            for dev in indigo.devices.iter("self"):
                if "SUPERSEDED" not in dev.name:
                    if int(dev.address) == stat:
                        if dev.deviceTypeId == expectedTypeId:
                            device = dev
                        else:
                            # Wrong device type — supersede and recreate
                            self.logger.info("Upgrading %s from %s to %s" % (dev.name, dev.deviceTypeId, expectedTypeId))
                            dev.name = dev.name + " SUPERSEDED"
                            dev.replaceOnServer()
            if device == None:
                self.logger.info("Creating Heatmiser device for %s (type: %s)" % (devName, expectedTypeId))
                device = indigo.device.create(protocol=indigo.kProtocol.Plugin,
                    address=stat,
                    name=devName,
                    pluginId="com.racarter.indigoplugin.heatmiser-neo",
                    deviceTypeId=expectedTypeId,
                    props={"neoDeviceType": str(deviceType)})
            # Store device type and thermostat props
            localPropsCopy = device.pluginProps
            localPropsCopy["neoDeviceType"] = str(deviceType)
            if expectedTypeId == "heatmiserNeostat":
                localPropsCopy["SupportsCoolSetpoint"] = False
                localPropsCopy["SupportsHvacFanMode"] = False
            device.replacePluginPropsOnServer(localPropsCopy)
            self.updateStatState(neoInfo, stat, device)

        
    def updateReadings(self):
        update = self.getNeoData("\"GET_LIVE_DATA\":0" if self.neohubGen2 else "\"INFO\":0")
        if update != "":
            # Log response keys once on first successful response for field name verification
            if not self.responseKeysLogged and update.get("devices"):
                self.logger.info("GET_LIVE_DATA top-level keys: %s" % list(update.keys()))
                self.logger.info("GET_LIVE_DATA first device keys: %s" % list(update["devices"][0].keys()))
                self.responseKeysLogged = True
            devices = update.get("devices")
            if devices is None:
                self.logger.error("updateReadings: response missing 'devices' key; top-level keys: %s" % list(update.keys()))
                return
            max_devices = len(devices)
            for stat in range(0, max_devices):
                device = None
                for dev in indigo.devices.iter("self"):
                    if "SUPERSEDED" not in dev.name:
                        if int(dev.address) == stat:
                            # Match by Indigo device type (sensor vs thermostat/plug)
                            neoDeviceType = int(dev.pluginProps.get("neoDeviceType", 0))
                            if neoDeviceType == 14 and dev.deviceTypeId == "heatmiserNeoSensor":
                                device = dev
                                break
                            elif neoDeviceType != 14 and dev.deviceTypeId != "heatmiserNeoSensor":
                                device = dev
                                break
                if device != None:
                    self.updateStatState(update, stat, device)
                    if stat == 0:
                        self.neoDevice = device
    
            
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

    def _close_wss(self):
        with self._wss_lock:
            if self._wss is not None:
                try:
                    self._wss.close()
                except Exception as exc:
                    self.logger.debug("WSS close error (ignored): %s" % exc)
                self._wss = None

    def _ensure_wss(self):
        """Return existing WSS connection or create new one. Must be called under _wss_lock."""
        if self._wss is not None:
            return self._wss
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE  # NeoHub uses self-signed cert on local network
        uri = "wss://%s:4243" % self.neohubIP
        self._wss = ws_connect(uri, ssl=ssl_context, open_timeout=8)
        return self._wss

    def _send_wss(self, cmdPhrase):
        """Send command via WSS and return parsed response.

        The Heatmiser WSS protocol uses a two-layer JSON envelope: the outer
        message has message_type + message fields, the inner payload contains
        the API token and COMMANDS array. The hub may send async messages
        between command/response pairs, so we filter for hm_set_command_response.
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
            ws = self._ensure_wss()
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

    def _get_neo_data_wss(self, cmdPhrase):
        """WSS equivalent of _get_neo_data_tcp. On connection failure, closes
        the persistent socket so the next call reconnects via _ensure_wss."""
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
            self._close_wss()
            self.connectErrorCount += 1
            if self.connectErrorCount <= 3 or self.connectErrorCount % 10 == 0:
                self.logger.error("getNeoData WSS: connection error #%d (%s)" % (self.connectErrorCount, exc))
            return ""
        except Exception as exc:
            self._close_wss()
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
        if update != "":
            self.logger.debug("GET_SYSTEM keys: %s" % list(update.keys()))
        if update != "" and self.neoDevice is not None:
            self.neoDevice.updateStateOnServer(key="HubFirmwareVersion", value=str(update.get("HUB_VERSION", update.get("Firmware version", "unknown"))))
            self.neoDevice.updateStateOnServer(key="DST_Auto", value=str(update.get("DST_AUTO", update.get("DSTAUTO", ""))))
            self.neoDevice.updateStateOnServer(key="DST_On", value=str(update.get("DST_ON", update.get("DSTON", ""))))
            self.neoDevice.updateStateOnServer(key="NTP_Status", value=str(update.get("NTP_ON", update.get("NTP", ""))))
            self.neoDevice.updateStateOnServer(key="Units", value="deg"+str(update.get("CORF", "")))
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
            self.neoDevice.updateStateOnServer(key="Prog_Format", value=pfiString)
            

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
            for dev in indigo.devices.iter("self"):
                if "SUPERSEDED" in dev.name:
                    continue
                # Skip sensors, neoplugs, and timeclocks — they don't have engineering states
                if dev.deviceTypeId in ("heatmiserNeoSensor", "heatmiserNeoplug", "heatmiserNeoTimeclock"):
                    continue
                if dev.name not in update:
                    continue
                try:
                    devData = update[dev.name]
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
                # Close the persistent WSS first, then swap in the new IP.
                # Doing it in the opposite order leaves a brief window in
                # which another thread could dispatch a command against
                # the new IP while the old socket is still being torn down.
                if ipChanged:
                    self._close_wss()
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
        device = dev.name
        if device:
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
        device = dev.name
        if device:
            zilch = "0"
            holdTemp = "20"
            update = self.getNeoData("\"FROST_OFF\":[\""+device+"\"]")
            update = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"Off\""+", \"hours\":"+zilch+", \"minutes\":"+zilch+"}, \""+device+"\"]")
            if update and "result" in update:
                self.logger.info("%s set to Auto" % device)
            else:
                self.logger.error("%s Auto command failed" % device)
 
    def setOverride(self, pluginAction):
        device = indigo.devices[pluginAction.deviceId].name
        if device:
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
        device = indigo.devices[pluginAction.deviceId].name
        if device:
            minutes = pluginAction.props.get("boostMinutes", "30")
            update = self.getNeoData("\"TIMER_HOLD_ON\":[%s, \"%s\"]" % (minutes, device))
            if update and "result" in update:
                self.logger.info("%s timer boost on for %s minutes" % (device, minutes))
            else:
                self.logger.error("%s timer boost command failed" % device)

    def timerBoostOff(self, pluginAction):
        device = indigo.devices[pluginAction.deviceId].name
        if device:
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
        device = indigo.devices[pluginAction.deviceId].name
        update = self.getNeoData('"AWAY_ON":["%s"]' % device)
        if update and "result" in update:
            self.logger.info("%s away mode on" % device)
        else:
            self.logger.error("%s away on command failed" % device)

    def awayOff(self, pluginAction):
        device = indigo.devices[pluginAction.deviceId].name
        update = self.getNeoData('"AWAY_OFF":["%s"]' % device)
        if update and "result" in update:
            self.logger.info("%s away mode off" % device)
        else:
            self.logger.error("%s away off command failed" % device)

    def lockKeypad(self, pluginAction):
        device = indigo.devices[pluginAction.deviceId].name
        pin = pluginAction.props.get("lockPin", "0000")
        digits = [int(d) for d in pin[:4]]
        update = self.getNeoData('"LOCK":[[%s], ["%s"]]' % (",".join(str(d) for d in digits), device))
        if update and "result" in update:
            self.logger.info("%s keypad locked" % device)
        else:
            self.logger.error("%s lock keypad command failed" % device)

    def unlockKeypad(self, pluginAction):
        device = indigo.devices[pluginAction.deviceId].name
        update = self.getNeoData('"UNLOCK":["%s"]' % device)
        if update and "result" in update:
            self.logger.info("%s keypad unlocked" % device)
        else:
            self.logger.error("%s unlock keypad command failed" % device)

    def cancelHold(self, pluginAction):
        device = indigo.devices[pluginAction.deviceId].name
        update = self.getNeoData('"HOLD":[{"temp":20, "id":"Off", "hours":0, "minutes":0}, "%s"]' % device)
        if update and "result" in update:
            self.logger.info("%s hold cancelled" % device)
        else:
            self.logger.error("%s cancel hold command failed" % device)

    def setFrostTemp(self, pluginAction):
        device = indigo.devices[pluginAction.deviceId].name
        temp = pluginAction.props.get("frostTemp", "12")
        update = self.getNeoData('"SET_FROST":[%s, "%s"]' % (temp, device))
        if update and "result" in update:
            self.logger.info("%s frost temperature set to %s°C" % (device, temp))
        else:
            self.logger.error("%s set frost temp command failed" % device)

    def identifyDevice(self, pluginAction):
        device = indigo.devices[pluginAction.deviceId].name
        update = self.getNeoData('"IDENTIFY":[1, 3, ["%s"]]' % device)
        if update and "result" in update:
            self.logger.info("%s identify LED flashing" % device)
        else:
            self.logger.error("%s identify command failed" % device)

    def getHoursRun(self, pluginAction):
        device = indigo.devices[pluginAction.deviceId].name
        update = self.getNeoData('"GET_HOURSRUN":"%s"' % device)
        if isinstance(update, dict) and update:
            self.logger.info("%s hours run: %s" % (device, json.dumps(update)))
        else:
            self.logger.error("%s get hours run command failed (response: %r)" % (device, update))

    def getTempLog(self, pluginAction):
        device = indigo.devices[pluginAction.deviceId].name
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
            # Close-before-mutate: tear down the old socket first so a
            # concurrent command can't land on the new IP mid-teardown.
            self._close_wss()
            self.neohubIP = newIp
            self.logger.info("Neohub IP address is now %s" % self.neohubIP)
                


    ########################################
    # NeoPlug Action callback
    ######################
    # Main switch action bottleneck called by Indigo Server.
    def actionControlDevice(self, action, dev):
        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            resDict = self.getNeoData("\"TIMER_ON\":[\""+dev.name+"\"]")
            if resDict and "result" in resDict:
                dev.updateStateOnServer("onOffState", True)
                dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
            else:
                self.logger.error("%s turn on command failed" % dev.name)
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            resDict = self.getNeoData("\"TIMER_OFF\":[\""+dev.name+"\"]")
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
        if action.thermostatAction == indigo.kThermostatAction.SetHeatSetpoint:
            newSetpoint = str(action.actionValue)
            update = self.getNeoData("\"SET_TEMP\":["+newSetpoint+", \""+dev.name+"\"]")
            if update and "result" in update:
                dev.updateStateOnServer("setpointHeat", newSetpoint)
                self.logger.info("%s setpoint set to %s degC" % (dev.name, newSetpoint))
            
        elif action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint:
            newSetpoint = str(dev.heatSetpoint - action.actionValue)
            update = self.getNeoData("\"SET_TEMP\":["+newSetpoint+", \""+dev.name+"\"]")
            if update and "result" in update:
                dev.updateStateOnServer("setpointHeat", newSetpoint)
                self.logger.info("%s setpoint decreased to %s degC" % (dev.name, newSetpoint))
        
        elif action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint:
            newSetpoint = str(dev.heatSetpoint + action.actionValue)
            update = self.getNeoData("\"SET_TEMP\":["+newSetpoint+", \""+dev.name+"\"]")
            if update and "result" in update:
                dev.updateStateOnServer("setpointHeat", newSetpoint)
                self.logger.info("%s setpoint increased to %s degC" % (dev.name, newSetpoint))
                    
        elif action.thermostatAction == indigo.kThermostatAction.SetHvacMode:
            newMode = action.actionMode
            if newMode == indigo.kHvacMode.Off:
                self.logger.error("Thermostat does not have an 'Off' mode")
                return False
            elif newMode == indigo.kHvacMode.HeatCool:
                self.logger.info("Setting %s to 'Auto' mode" % dev.name)
                resDict = self.getNeoData("\"FROST_OFF\":[\""+dev.name+"\"]")
                holdTemp = "20"
                zilch = "0"
                resDict = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"Off\""+", \"hours\":"+zilch+", \"minutes\":"+zilch+"}, \""+dev.name+"\"]")
            elif newMode == indigo.kHvacMode.Heat:
                self.logger.info("Setting %s to 'Heat' mode" % dev.name)
                resDict = self.getNeoData("\"FROST_OFF\":[\""+dev.name+"\"]")
                holdTemp = "20"
                holdHours = "1"
                holdMins = "0"
                resDict = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"On\""+", \"hours\":"+holdHours+", \"minutes\":"+holdMins+"}, \""+dev.name+"\"]")
            elif newMode == indigo.kHvacMode.Cool:
                self.logger.info("Setting %s to 'Cool' mode" % dev.name)
                holdTemp = "20"
                zilch = "0"
                resDict = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"Off\""+", \"hours\":"+zilch+", \"minutes\":"+zilch+"}, \""+dev.name+"\"]")
                resDict = self.getNeoData("\"FROST_ON\":[\""+dev.name+"\"]")
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


