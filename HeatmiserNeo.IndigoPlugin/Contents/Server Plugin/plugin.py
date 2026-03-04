#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# Copyright (c) 2016-2018 Alan Carter. All rights reserved.
#
#
################################################################################
# Imports
################################################################################
import sys
import os
import re
import http.client
import urllib
import json
import socket
import datetime
import errno

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
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs): 
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
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
    def __del__(self):
        indigo.PluginBase.__del__(self)

        
    ########################################
    def startup(self):
        indigo.server.log("Starting Heatmiser Neo plugin")
        if self.logComms:
            indigo.server.log("Neo comms logging is on")
        else:
            indigo.server.log("Neo comms logging is off")   
        self.createDevices()
        if self.timeSync:
            self.timeUpdateRequired = True
            indigo.server.log("Neo time will be synchronised daily with Indigo")
        else:
            indigo.server.log("Neo time will be syncronised via NTP server")


    def deviceStartComm(self, dev):
        dev.stateListOrDisplayStateIdChanged()
        return

    def shutdown(self):
        indigo.server.log("Stopping Heatmiser Neo plugin")
        self.commsEnabled = False
        pass

        
    ########################################
    def runConcurrentThread(self):
        indigo.server.log("Starting Heatmiser Neo monitoring thread")
        try:
            while True:
                self.updateReadings()
                self.sleep(1)
                if self.firstTime:
                    if self.timeSync:
                        self.ntpOff()
                    else:
                        self.ntpOn()
                    self.sleep(1)
                    self.updateDCB()
                    self.updateEng()
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
                    indigo.server.log("Neo comms logging is on")
                else:
                    indigo.server.log("Neo comms logging is off")
            self.oldTimeValue = self.timeSync
            self.timeSync = valuesDict.get("timeSync", False)
            if self.timeSync != self.oldTimeValue:
                if self.timeSync:
                    self.ntpOff()
                    self.timeUpdateRequired = True
                    indigo.server.log("Neo time will be synchronised daily with Indigo")
                else:
                    self.ntpOn()
                    indigo.server.log("Neo time will be syncronised via NTP server")                
                self.updateDCB()
            oldIP = self.neohubIP
            self.neohubIP = valuesDict.get("neohubIP")
            if self.neohubIP != oldIP:
                indigo.server.log("Neohub IP address is now %s" % self.neohubIP)

                        
    ########################################
    # Heatmiser Neo specific functions
    
    def createDevices(self):
        self.commsEnabled = True
        neoInfo = self.getNeoData("\"INFO\":0")
        try:
            max_devices = len(neoInfo["devices"])
        except:
            indigo.server.log("Cannot detect devices", isError=True)
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
            device = None
            for dev in indigo.devices.iter("self"):
                if "SUPERSEDED" not in dev.name:
                    if int(dev.address) == stat:
                        device = dev
            if device == None:
                statName = neoInfo["devices"][stat]["device"]
                if statName.isidentifier() == False:
                    indigo.server.log("%s: name contains characters not allowed in Python variable names; please rename this device and restart the plugin" % statName, isError=True)
                if neoInfo["devices"][stat]["DEVICE_TYPE"] == 6:
                    indigo.server.log("Creating Heatmiser device for %s" % neoInfo["devices"][stat]["device"])
                    device = indigo.device.create(protocol=indigo.kProtocol.Plugin,
                    address=stat,
                    name=neoInfo["devices"][stat]["device"],  
                    pluginId="com.racarter.indigoplugin.heatmiser-neo",
                    deviceTypeId="heatmiserNeoplug",
                    props={})
                else:
                    indigo.server.log("Creating Heatmiser device for %s" % neoInfo["devices"][stat]["device"])
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
            deviceType = neoRep["devices"][index]["DEVICE_TYPE"]
            if deviceType in (1, 7, 12, 13, 24):
                # This device is a Neostat (1) or NeoAir (7) or NeoStat-e (12) or NeoAir (13) or NeoStat V2 (24)
                # Check if device is offline first
                if neoRep["devices"][index]["OFFLINE"]:
                    indigoDevice.setErrorStateOnServer('OFFLINE')
                    return

                if neoRep["devices"][index]["HEATING"] or neoRep["devices"][index]["PREHEAT"] or neoRep["devices"][index]["TIMER"]:
                    # HEATING for Thermostats, TIMER for Timeclocks
                    indigoDevice.updateStateOnServer(key="heatIsOn", value=True)
                    indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.HvacHeating)
                else:
                    indigoDevice.updateStateOnServer(key="heatIsOn", value=False)
                    indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.HvacHeatMode)
                indigoDevice.updateStateOnServer(key="preHeat", value=neoRep["devices"][index]["PREHEAT"])
                indigoDevice.updateStateOnServer(key="setpointHeat", value=neoRep["devices"][index]["CURRENT_SET_TEMPERATURE"])
                curTemp = uiValue=neoRep["devices"][index]["CURRENT_TEMPERATURE"]
                curTempf = float(curTemp)
                curTempr = round(curTempf, 1)
                if curTempr > 0:
                    indigoDevice.updateStateOnServer(key="temperatureInput1", value=curTempr, uiValue=str(curTempr)+" °C", clearErrorState=True)
                else:
                    # Only log error if not offline (offline already handled above)
                    indigo.server.log("Neo temperature error for %s" % indigoDevice.name, isError=True)
                frost = neoRep["devices"][index]["STANDBY"]
                tempHold = neoRep["devices"][index]["TEMP_HOLD"]
                if frost:
                    indigoDevice.updateStateOnServer(key="hvacOperationMode", value=indigo.kHvacMode.Cool)
                    indigoDevice.updateStateOnServer(key="ShortMode", value="Frost")
                elif tempHold:
                    indigoDevice.updateStateOnServer(key="hvacOperationMode", value=indigo.kHvacMode.Heat)
                    indigoDevice.updateStateOnServer(key="ShortMode", value="Boost")
                else:
                    indigoDevice.updateStateOnServer(key="hvacOperationMode", value=indigo.kHvacMode.ProgramHeat)
                    indigoDevice.updateStateOnServer(key="ShortMode", value="Auto")
                indigoDevice.updateStateOnServer(key="Away", value=neoRep["devices"][index]["AWAY"])
                indigoDevice.updateStateOnServer(key="Holiday", value=neoRep["devices"][index]["HOLIDAY"])
                indigoDevice.updateStateOnServer(key="Holiday_Days", value=neoRep["devices"][index]["HOLIDAY_DAYS"])
                
            elif deviceType == 6:
                # This device is a Neoplug
                if neoRep["devices"][index]["TIMER"]:
                    indigoDevice.updateStateOnServer(key="onOffState", value=True, clearErrorState=True)
                    indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.PowerOn)
                else:
                    indigoDevice.updateStateOnServer(key="onOffState", value=False, clearErrorState=True)
                    indigoDevice.updateStateImageOnServer(indigo.kStateImageSel.PowerOff)
                    
            elif deviceType == 0:
                # This device is offline
                indigoDevice.setErrorStateOnServer('OFFLINE')
                
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

            else:
                indigo.server.log("updateStatState: Unknown device type '"+str(deviceType)+"'", isError=True)   


    def getNeoData(self, cmdPhrase):
        if self.commsEnabled:
            tcp_ip = self.neohubIP
            tcp_port = 4242
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(8)
            errorcode = 0
            try:
                self.sock.connect((tcp_ip, tcp_port))
                self.connectErrorCount = 0
            except socket.timeout:
                self.connectErrorCount += 1
                if (self.connectErrorCount == 3):
                    indigo.server.log("getNeoData: Socket timeout error", isError=True)
                return ""
            except:
                self.connectErrorCount += 1
                if (self.connectErrorCount == 3):
                    indigo.server.log("getNeoData: Socket connect error", isError=True)
                return ""
            cmdPhrase = b"{"+bytes(cmdPhrase, 'ascii')+b"}"
            try:
                if self.logComms:
                    indigo.server.log("--> "+str(cmdPhrase))
                self.sock.send(cmdPhrase+b"\0")
                dataj = None
                dataj = self.sock.recv(4096)
                while ((b"INFO" in cmdPhrase) and (b"}]}" not in dataj[len(dataj)-5:len(dataj)-1])) or ((b"ENGINEERS_DATA" in cmdPhrase) and (b"}}" not in dataj[len(dataj)-4:len(dataj)-1])):  
                    dataj = dataj + self.sock.recv(4096)
                self.sendErrorCount = 0
                if self.logComms:
                    indigo.server.log("<-- "+str(dataj))
            except socket.error as v:
                self.sendErrorCount += 1
                if (self.sendErrorCount == 3):
                    indigo.server.log("getNeoData: Socket send error ("+str(v)+")", isError=True)
                    self.sendErrorCount = 0
                return ""
            if dataj != None:
                datak = re.sub(b'[^\s!-~]', b'', dataj)   #Filter extraneous characters which cause json decode to fail
                data = json.loads(datak)
                self.connectErrorCount = 0
                self.sendErrorCount = 0
                if "error" in data:
                    indigo.server.log(str(cmdPhrase), isError=True)
                    errMsg = data["error"]
                    indigo.server.log(errMsg, isError=True)
                    return ""
                else:
                    return data
            else:
                return ""
        else:
            pass
    
    
    def checkTime(self):
        dt = datetime.datetime.now()
        if self.timeUpdateRequired == None:
            self.timeUpdateRequired = True
        if (dt.hour == 3) and self.timeUpdateRequired:
            update = self.getNeoData("\"SET_TIME\":["+str(dt.hour)+", "+str(dt.minute)+"]")
            if "result" in update:
                indigo.server.log("Device time synchronised with Indigo")
            else:
                indigo.server.log("Device time sync failed", isError=True)
                
            update = self.getNeoData("\"SET_DATE\":["+str(dt.year)+", "+str(dt.month)+", "+str(dt.day)+"]")
            if "result" in update:
                indigo.server.log("Device date synchronised with Indigo")
            else:
                indigo.server.log("Device date sync failed", isError=True)
                
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
        if update != "":
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
                pfiString == pfi
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
        stepName = "Get Data"
        try:
            update = self.getNeoData("\"ENGINEERS_DATA\":0")
            if update != "":
                max_devices = len(update)
                stepName = "Get Device"
                for stat in range(0, max_devices):
                    device = None
                    for dev in indigo.devices.iter("self"):
                        if "SUPERSEDED" not in dev.name:
                            if int(dev.address) == stat:
                                stepName = "Get ROC"
                                if update[dev.name]["RATE OF CHANGE"] > 0:
                                    stepName = "ROC"
                                    dev.updateStateOnServer(key="ROC", value=update[dev.name]["RATE OF CHANGE"])
                                    stepName = "Frost Temp"
                                    dev.updateStateOnServer(key="FrostTemp", value=update[dev.name]["FROST TEMPERATURE"])
                                    stepName = "Switching Differential"
                                    swDiff = update[dev.name]["SWITCHING DIFFERENTIAL"]
                                    if swDiff == 0:
                                        swDiff = 0.5
                                    dev.updateStateOnServer(key="SwitchDiff", value=swDiff)
        except:
            indigo.server.log("Cannot update ENGINEERS_DATA.  Will try again tomorrow.", isError=True)
            indigo.server.log("Update failed at step '%s' for %s" % (stepName, dev.name))
         

    def ntpOn(self):
        update = self.getNeoData("\"NTP_ON\":0")
        self.sleep(1)
        update = self.getNeoData("\"DST_ON\":0")

        
    def ntpOff(self):
        update = self.getNeoData("\"NTP_OFF\":0")
        self.sleep(1)
        update = self.getNeoData("\"DST_OFF\":0")
        
    
    def fixStatName(self, name):    # Not currently used
        name = name.replace(' ','+')
        name = name.replace('/','%2F')
        return name


    ########################################
    # Menu Item functions
    ######################
    



    ########################################
    # Action functions
    ######################

    def setCool(self, pluginAction):
        devToProcess = pluginAction.deviceId
        device = None
        for dev in indigo.devices.iter("self"):
            if dev.id == devToProcess:
                device = dev.name
        if device != None:
            update = self.getNeoData("\"FROST_ON\":[\""+device+"\"]")
            if "result" in update:
                indigo.server.log("%s set to Cool" % device)
            else:
                indigo.server.log("%s Cool command failed" % device, isError=True)              
    
    def setAuto(self, pluginAction):
        devToProcess = pluginAction.deviceId
        device = None
        for dev in indigo.devices.iter("self"):
            if dev.id == devToProcess:
                device = dev.name
        if device != None:
            zilch = "0"
            holdTemp = "20"
            update = self.getNeoData("\"FROST_OFF\":[\""+device+"\"]")
            update = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"Off\""+", \"hours\":"+zilch+", \"minutes\":"+zilch+"}, \""+device+"\"]")
            if "result" in update:
                indigo.server.log("%s set to Auto" % device)
            else:
                indigo.server.log("%s Auto command failed" % device, isError=True)
 
    def setOverride(self, pluginAction):
        devToProcess = pluginAction.deviceId
        device = None
        for dev in indigo.devices.iter("self"):
            if dev.id == devToProcess:
                device = dev.name
        if device != None:
            holdTemp = pluginAction.props["overrideTemp"]
            holdHours = pluginAction.props["numberOfHours"]
            if holdHours == "0.5":
            	holdHours = "0"
            	holdMins = "30"
            else:
            	holdMins = "0"
            #update = self.getNeoDataupdate = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"Off\""+", \"hours\":"+holdHours+", \"minutes\":"+holdMins+"}, \""+device.name+"\"]")
            update = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"Off\""+", \"hours\":"+holdHours+", \"minutes\":"+holdMins+"}, \""+device+"\"]")
            if "result" in update:
                if holdHours[0] == "0":
                    holdHours = holdHours[1:]
                indigo.server.log("%s set to Override at %s degrees for %s hours" % (device, holdTemp, holdHours))
            else:
                indigo.server.log("%s Override command failed" % device, isError=True)
                
 
                
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
                indigo.server.log("Neohub IP address is now %s" % self.neohubIP)
        else:
            indigo.server.log("Invalid IP address supplied", isError=True)
                


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
            indigo.server.log("This action is not currently supported", isError=True)
            
                
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
                indigo.server.log("%s setpoint set to %s degC" % (dev.name, newSetpoint))
            
        elif action.thermostatAction == indigo.kThermostatAction.DecreaseHeatSetpoint:
            newSetpoint = str(dev.heatSetpoint - action.actionValue)
            update = self.getNeoData("\"SET_TEMP\":["+newSetpoint+", \""+dev.name+"\"]")
            if "result" in update:
                dev.updateStateOnServer("setpointHeat", newSetpoint)
                indigo.server.log("%s setpoint decreased to %s degC" % (dev.name, newSetpoint))
        
        elif action.thermostatAction == indigo.kThermostatAction.IncreaseHeatSetpoint:
            newSetpoint = str(dev.heatSetpoint + action.actionValue)
            update = self.getNeoData("\"SET_TEMP\":["+newSetpoint+", \""+dev.name+"\"]")
            if "result" in update:
                dev.updateStateOnServer("setpointHeat", newSetpoint)
                indigo.server.log("%s setpoint increased to %s degC" % (dev.name, newSetpoint))     
                    
        elif action.thermostatAction == indigo.kThermostatAction.SetHvacMode:
            newMode = action.actionMode
            if newMode == indigo.kHvacMode.Off:
                indigo.server.log(u"Thermostat does not have an 'Off' mode", isError=True)
                return False
            elif newMode == indigo.kHvacMode.HeatCool:
                indigo.server.log("Setting %s to 'Auto' mode" % dev.name)
                resDict = self.getNeoData("\"FROST_OFF\":[\""+dev.name+"\"]")
                holdTemp = "20"
                zilch = "0"
                resDict = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"Off\""+", \"hours\":"+zilch+", \"minutes\":"+zilch+"}, \""+dev.name+"\"]")
            elif newMode == indigo.kHvacMode.Heat:
                indigo.server.log("Setting %s to 'Heat' mode" % dev.name)
                resDict = self.getNeoData("\"FROST_OFF\":[\""+dev.name+"\"]")
                holdTemp = "20"
                holdHours = "1"
                holdMins = "0"
                resDict = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"On\""+", \"hours\":"+holdHours+", \"minutes\":"+holdMins+"}, \""+dev.name+"\"]")
            elif newMode == indigo.kHvacMode.Cool:
                indigo.server.log("Setting %s to 'Cool' mode" % dev.name)
                holdTemp = "20"
                zilch = "0"
                resDict = self.getNeoData("\"HOLD\":[{\"temp\":"+holdTemp+", \"id\":"+"\"Off\""+", \"hours\":"+zilch+", \"minutes\":"+zilch+"}, \""+dev.name+"\"]")
                resDict = self.getNeoData("\"FROST_ON\":[\""+dev.name+"\"]")
            dev.updateStateOnServer("hvacOperationMode", newMode)
            
        elif action.thermostatAction in [indigo.kThermostatAction.RequestStatusAll, indigo.kThermostatAction.RequestMode,
            indigo.kThermostatAction.RequestEquipmentState, indigo.kThermostatAction.RequestTemperatures, indigo.kThermostatAction.RequestHumidities,
            indigo.kThermostatAction.RequestDeadbands, indigo.kThermostatAction.RequestSetpoints]:
            indigo.server.log(u"Status automatically updated every minute", isError=True)
        
        elif (action.thermostatAction == indigo.kThermostatAction.DecreaseCoolSetpoint) or (action.thermostatAction == indigo.kThermostatAction.IncreaseCoolSetpoint):
            pass
            
        else:
            indigo.server.log("Action %s is not currently supported" % (action.thermostatAction), isError=True)


