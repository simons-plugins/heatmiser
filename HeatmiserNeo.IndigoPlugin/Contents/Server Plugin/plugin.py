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
import datetime

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
    
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs, **kwargs):
        super().__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs, **kwargs)
        self.neohubIP = pluginPrefs.get("neohubIP", "127.0.0.1")
        self.logComms = pluginPrefs.get("logComms", False)
        self.timeSync = pluginPrefs.get("timeSync", False)
        self.commsEnabled = True
        self.connectErrorCount = 0
        self.sendErrorCount = 0
        self.neoDevice = None
        self.timeUpdateRequired = None
        self.dcbUpdateRequired = None
        self.engUpdateRequired = None
        self.firstTime = True


    ########################################
    def startup(self):
        self.logger.info("Starting Heatmiser Neo plugin")
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
        return

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
                    self.logger.error("Error in updateReadings: %s" % str(exc))
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
                        self.logger.error("Error in updateDCB: %s" % str(exc))
                    try:
                        self.updateEng()
                    except Exception as exc:
                        self.logger.error("Error in updateEng: %s" % str(exc))
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
            self.logComms = valuesDict.get("logComms", False)
            if self.logComms != self.oldLogValue:
                if self.logComms:
                    self.logger.info("Neo comms logging is on")
                else:
                    self.logger.info("Neo comms logging is off")
            self.oldTimeValue = self.timeSync
            self.timeSync = valuesDict.get("timeSync", False)
            if self.timeSync != self.oldTimeValue:
                if self.timeSync:
                    self.ntpOff()
                    self.timeUpdateRequired = True
                    self.logger.info("Neo time will be synchronised daily with Indigo")
                else:
                    self.ntpOn()
                    self.logger.info("Neo time will be syncronised via NTP server")
                self.updateDCB()
            oldIP = self.neohubIP
            self.neohubIP = valuesDict.get("neohubIP")
            if self.neohubIP != oldIP:
                self.logger.info("Neohub IP address is now %s" % self.neohubIP)

                        
    ########################################
    # Heatmiser Neo specific functions
    
    def createDevices(self):
        self.commsEnabled = True
        neoInfo = self.getNeoData("\"INFO\":0")
        try:
            max_devices = len(neoInfo["devices"])
        except Exception:
            self.logger.error("Cannot detect devices")
            max_devices = 0
        for stat in range(0, max_devices):
            if neoInfo["devices"][stat]["DEVICE_TYPE"] == 14:
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
                    statName = neoInfo["devices"][stat]["device"]
                    self.logger.info("Creating Heatmiser sensor device for %s" % neoInfo["devices"][stat]["device"])
                    device = indigo.device.create(protocol=indigo.kProtocol.Plugin,
                    address=stat,
                    name=neoInfo["devices"][stat]["device"],
                    pluginId="com.racarter.indigoplugin.heatmiser-neo",
                    deviceTypeId="heatmiserNeoSensor",
                    props={})
                self.updateStatState(neoInfo, stat, device)
                continue
            device = None
            for dev in indigo.devices.iter("self"):
                if "SUPERSEDED" not in dev.name:
                    if int(dev.address) == stat:
                        device = dev
            if device == None:
                statName = neoInfo["devices"][stat]["device"]
                if statName.isidentifier() == False:
                    self.logger.error("%s: name contains characters not allowed in Python variable names; please rename this device and restart the plugin" % statName)
                if neoInfo["devices"][stat]["DEVICE_TYPE"] == 6:
                    self.logger.info("Creating Heatmiser device for %s" % neoInfo["devices"][stat]["device"])
                    device = indigo.device.create(protocol=indigo.kProtocol.Plugin,
                    address=stat,
                    name=neoInfo["devices"][stat]["device"],  
                    pluginId="com.racarter.indigoplugin.heatmiser-neo",
                    deviceTypeId="heatmiserNeoplug",
                    props={})
                else:
                    self.logger.info("Creating Heatmiser device for %s" % neoInfo["devices"][stat]["device"])
                    device = indigo.device.create(protocol=indigo.kProtocol.Plugin,
                    address=stat,
                    name=neoInfo["devices"][stat]["device"],
                    pluginId="com.racarter.indigoplugin.heatmiser-neo",
                    deviceTypeId="heatmiserNeostat",
                    props={})
            if neoInfo["devices"][stat]["DEVICE_TYPE"] != 6:
                localPropsCopy = device.pluginProps
                localPropsCopy.update({"SupportsCoolSetpoint":False})
                localPropsCopy.update({"SupportsHvacFanMode":False})
                device.replacePluginPropsOnServer(localPropsCopy)                    
            self.updateStatState(neoInfo, stat, device)

        
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
                            # Match device type: sensor (14) should be heatmiserNeoSensor, others should be thermostat/plug
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
        deviceType = devData["DEVICE_TYPE"]

        if deviceType in (1, 7, 12, 13, 24):
            # Neostat (1), NeoAir (7), NeoStat-e (12), NeoAir (13), NeoStat V2 (24)
            if devData["OFFLINE"]:
                indigoDevice.setErrorStateOnServer('OFFLINE')
                return

            heating = devData["HEATING"] or devData["PREHEAT"] or devData["TIMER"]
            curTemp = round(float(devData["CURRENT_TEMPERATURE"]), 1)

            frost = devData["STANDBY"]
            tempHold = devData["TEMP_HOLD"]
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
                {"key": "heatIsOn", "value": heating},
                {"key": "preHeat", "value": devData["PREHEAT"]},
                {"key": "setpointHeat", "value": devData["CURRENT_SET_TEMPERATURE"]},
                {"key": "hvacOperationMode", "value": hvacMode},
                {"key": "ShortMode", "value": shortMode},
                {"key": "Away", "value": devData["AWAY"]},
                {"key": "Holiday", "value": devData["HOLIDAY"]},
                {"key": "Holiday_Days", "value": devData["HOLIDAY_DAYS"]},
            ]

            if curTemp > 0:
                stateList.append({"key": "temperatureInput1", "value": curTemp, "uiValue": "%s °C" % curTemp, "clearErrorState": True})
            else:
                self.logger.error("Neo temperature error for %s" % indigoDevice.name)

            indigoDevice.updateStatesOnServer(stateList)

            if heating:
                indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.HvacHeating)
            else:
                indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.HvacHeatMode)

        elif deviceType == 6:
            # Neoplug
            timerOn = devData["TIMER"]
            indigoDevice.updateStateOnServer(key="onOffState", value=timerOn, clearErrorState=True)
            if timerOn:
                indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
            else:
                indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)

        elif deviceType == 0:
            indigoDevice.setErrorStateOnServer('OFFLINE')

        elif deviceType == 14:
            # Wireless air sensor
            curTemp = round(float(devData["CURRENT_TEMPERATURE"]), 1)

            if devData["OFFLINE"]:
                stateList = [
                    {"key": "lowBattery", "value": devData["LOW_BATTERY"]},
                    {"key": "sensorValid", "value": False},
                    {"key": "temperatureInput1", "value": 0, "uiValue": "offline"},
                ]
                indigoDevice.updateStatesOnServer(stateList)
                indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.SensorOff)
                return

            stateList = [
                {"key": "lowBattery", "value": devData["LOW_BATTERY"]},
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
        if self.commsEnabled:
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
                    if (self.connectErrorCount == 3):
                        self.logger.error("getNeoData: Socket timeout error")
                    return ""
                except Exception:
                    self.connectErrorCount += 1
                    if (self.connectErrorCount == 3):
                        self.logger.error("getNeoData: Socket connect error")
                    return ""
                cmdPhrase = b"{"+bytes(cmdPhrase, 'ascii')+b"}"
                try:
                    if self.logComms:
                        self.logger.debug("--> %s" % cmdPhrase)
                    sock.send(cmdPhrase+b"\0")
                    dataj = None
                    dataj = sock.recv(4096)
                    while ((b"INFO" in cmdPhrase) and (b"}]}" not in dataj[len(dataj)-5:len(dataj)-1])) or ((b"ENGINEERS_DATA" in cmdPhrase) and (b"}}" not in dataj[len(dataj)-4:len(dataj)-1])):
                        dataj = dataj + sock.recv(4096)
                    self.sendErrorCount = 0
                    if self.logComms:
                        self.logger.debug("<-- %s" % dataj)
                except socket.error as v:
                    self.sendErrorCount += 1
                    if (self.sendErrorCount == 3):
                        self.logger.error("getNeoData: Socket send error (%s)" % v)
                        self.sendErrorCount = 0
                    return ""
                if dataj != None:
                    datak = re.sub(b'[^\s!-~]', b'', dataj)   #Filter extraneous characters which cause json decode to fail
                    data = json.loads(datak)
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
        else:
            pass
    
    
    def checkTime(self):
        dt = datetime.datetime.now()
        if self.timeUpdateRequired == None:
            self.timeUpdateRequired = True
        if (dt.hour == 3) and self.timeUpdateRequired:
            update = self.getNeoData("\"SET_TIME\":["+str(dt.hour)+", "+str(dt.minute)+"]")
            if "result" in update:
                self.logger.info("Device time synchronised with Indigo")
            else:
                self.logger.error("Device time sync failed")

            update = self.getNeoData("\"SET_DATE\":["+str(dt.year)+", "+str(dt.month)+", "+str(dt.day)+"]")
            if "result" in update:
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
        update = self.getNeoData("\"READ_DCB\":100")
        if update != "" and self.neoDevice is not None:
            self.neoDevice.updateStateOnServer(key="HubFirmwareVersion", value=str(update["Firmware version"]))
            self.neoDevice.updateStateOnServer(key="DST_Auto", value=str(update["DSTAUTO"]))
            self.neoDevice.updateStateOnServer(key="DST_On", value=str(update["DSTON"]))
            self.neoDevice.updateStateOnServer(key="NTP_Status", value=str(update["NTP"]))
            self.neoDevice.updateStateOnServer(key="Units", value="deg"+str(update["CORF"]))
            pfi = update["PROGFORMAT"]
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
        update = self.getNeoData("\"ENGINEERS_DATA\":0")
        if update != "":
            for dev in indigo.devices.iter("self"):
                if "SUPERSEDED" in dev.name:
                    continue
                if dev.name not in update:
                    continue
                try:
                    devData = update[dev.name]
                    if devData.get("RATE OF CHANGE", 0) > 0:
                        dev.updateStateOnServer(key="ROC", value=devData["RATE OF CHANGE"])
                        dev.updateStateOnServer(key="FrostTemp", value=devData["FROST TEMPERATURE"])
                        swDiff = devData["SWITCHING DIFFERENTIAL"]
                        if swDiff == 0:
                            swDiff = 0.5
                        dev.updateStateOnServer(key="SwitchDiff", value=swDiff)
                except Exception as exc:
                    self.logger.error("Cannot update ENGINEERS_DATA for %s: %s" % (dev.name, str(exc)))
         

    def ntpOn(self):
        update = self.getNeoData("\"NTP_ON\":0")
        self.sleep(1)
        update = self.getNeoData("\"DST_ON\":0")

        
    def ntpOff(self):
        update = self.getNeoData("\"NTP_OFF\":0")
        self.sleep(1)
        update = self.getNeoData("\"DST_OFF\":0")
        
    
    ########################################
    # Menu Item functions
    ######################
    



    ########################################
    # Action functions
    ######################

    def setCool(self, pluginAction):
        device = indigo.devices[pluginAction.deviceId].name
        if device:
            update = self.getNeoData("\"FROST_ON\":[\""+device+"\"]")
            if "result" in update:
                self.logger.info("%s set to Cool" % device)
            else:
                self.logger.error("%s Cool command failed" % device)              
    
    def setAuto(self, pluginAction):
        device = indigo.devices[pluginAction.deviceId].name
        if device:
            zilch = "0"
            holdTemp = "20"
            update = self.getNeoData("\"FROST_OFF\":[\""+device+"\"]")
            update = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"Off\""+", \"hours\":"+zilch+", \"minutes\":"+zilch+"}, \""+device+"\"]")
            if "result" in update:
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
            if "result" in update:
                if holdHours[0] == "0":
                    holdHours = holdHours[1:]
                self.logger.info("%s set to Override at %s degrees for %s hours" % (device, holdTemp, holdHours))
            else:
                self.logger.error("%s Override command failed" % device)
                
 
                
    ########################################
    # NeoPlug Action callback
    ######################
    # Main Neohub action bottleneck called by Indigo Server.                
    def changeIp(self, action):
        oldIP = self.neohubIP
        newIp = action.props.get("newIp", "")
        if newIp != "":
            self.neohubIP = newIp
            if self.neohubIP != oldIP:
                self.logger.info("Neohub IP address is now %s" % self.neohubIP)
        else:
            self.logger.error("Invalid IP address supplied")
                


    ########################################
    # NeoPlug Action callback
    ######################
    # Main switch action bottleneck called by Indigo Server.
    def actionControlDevice(self, action, dev):
        if action.deviceAction == indigo.kDeviceAction.TurnOn:
            resDict = self.getNeoData("\"TIMER_ON\":[\""+dev.name+"\"]")
            dev.updateStateOnServer("onOffState", True)
            dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
        elif action.deviceAction == indigo.kDeviceAction.TurnOff:
            resDict = self.getNeoData("\"TIMER_OFF\":[\""+dev.name+"\"]")
            dev.updateStateOnServer("onOffState", False)
            dev.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
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
            if "result" in update:
                dev.updateStateOnServer("setpointHeat", newSetpoint)
                self.logger.info("%s setpoint set to %s degC" % (dev.name, newSetpoint))
            
        elif action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint:
            newSetpoint = str(dev.heatSetpoint - action.actionValue)
            update = self.getNeoData("\"SET_TEMP\":["+newSetpoint+", \""+dev.name+"\"]")
            if "result" in update:
                dev.updateStateOnServer("setpointHeat", newSetpoint)
                self.logger.info("%s setpoint decreased to %s degC" % (dev.name, newSetpoint))
        
        elif action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint:
            newSetpoint = str(dev.heatSetpoint + action.actionValue)
            update = self.getNeoData("\"SET_TEMP\":["+newSetpoint+", \""+dev.name+"\"]")
            if "result" in update:
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
            dev.updateStateOnServer("hvacOperationMode", newMode)
            
        elif action.thermostatAction in [indigo.kThermostatAction.RequestStatusAll, indigo.kThermostatAction.RequestMode,
            indigo.kThermostatAction.RequestEquipmentState, indigo.kThermostatAction.RequestTemperatures, indigo.kThermostatAction.RequestHumidities,
            indigo.kThermostatAction.RequestDeadbands, indigo.kThermostatAction.RequestSetpoints]:
            self.logger.info("Status automatically updated every 30 seconds")
        
        elif (action.thermostatAction == indigo.kThermostatAction.DecreaseCoolSetpoint) or (action.thermostatAction == indigo.kThermostatAction.IncreaseCoolSetpoint):
            pass
            
        else:
            self.logger.error("Action %s is not currently supported" % action.thermostatAction)


