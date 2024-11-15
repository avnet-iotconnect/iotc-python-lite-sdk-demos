import sys
import json
import time
import threading
import random
from iotconnect import IoTConnectSDK
from datetime import datetime
import os
sys.path.append("/home/root/SAMA5D27_Basic_Demo")
import config

cpid = config.cpid
env = config.env
UniqueId = config.unique_id
plugin = config.plugin
pf = "AZ"

if plugin != "Default":
    plugin_module = importlib.import_module(plugin) 
	
SId = ""
Sdk=None
interval = 1
directmethodlist={}
ACKdirect=[]
device_list=[]
device_messages=[]

SdkOptions={
	"certificate" : { 
		"SSLKeyPath"  : "/home/root/SAMA5D27_Basic_Demo/device_certificates/device.key", 
		"SSLCertPath" : "/home/root/SAMA5D27_Basic_Demo/device_certificates/DeviceCertificate.pem",
		"SSLCaPath"   : "/home/root/SAMA5D27_Basic_Demo/iotconnect-sdk/iotconnect/assets/DigiCertGlobalRootG2.txt"
	},
    "offlineStorage":{
        "disabled": False,
	    "availSpaceInMb": 0.01,
	    "fileCount": 5,
        "keepalive":60
    },
    "skipValidation":False,
    "discoveryUrl":"https://discovery.iotconnect.io/",
    "IsDebug": False
}

def DeviceCallback(msg):
    global Sdk
    global device_messages
    print("\n--- IoTConnect Command Received ---")
    print(msg)
    cmdType = None
    if msg != None and len(msg.items()) != 0:
        cmdType = msg["ct"] if "ct" in msg else None
    if cmdType == 0:
        command = msg['cmd']
        device_message_str = "IOTCONNECT COMMAND RECEIVED: " + command
        device_messages.append(device_message_str)
        data=msg
        if data != None:
            if "id" in data:
                if "ack" in data and data["ack"]:
                    Sdk.sendAckCmd(data["ack"],7,"sucessfull",data["id"])  #fail=4,executed= 5,sucess=7,6=executedack
            else:
                if "ack" in data and data["ack"]:
                    Sdk.sendAckCmd(data["ack"],7,"sucessfull") #fail=4,executed= 5,sucess=7,6=executedack
    else:
        print("rule command",msg)


def DeviceFirmwareCallback(msg):
    global Sdk,device_list
    print("\n--- firmware Command Message Received ---")
    print(json.dumps(msg))
    cmdType = None
    if msg != None and len(msg.items()) != 0:
        cmdType = msg["ct"] if msg["ct"] != None else None
    if cmdType == 1:
        data = msg
        if data != None:
            if ("urls" in data) and data["urls"]:
                for url_list in data["urls"]:
                    if "tg" in url_list:
                        for i in device_list:
                            if "tg" in i and (i["tg"] == url_list["tg"]):
                                Sdk.sendOTAAckCmd(data["ack"],0,"sucessfull",i["id"]) #Success=0, Failed = 1, Executed/DownloadingInProgress=2, Executed/DownloadDone=3, Failed/DownloadFailed=4
                    else:
                        Sdk.sendOTAAckCmd(data["ack"],0,"sucessfull") #Success=0, Failed = 1, Executed/DownloadingInProgress=2, Executed/DownloadDone=3, Failed/DownloadFailed=4


def DeviceConectionCallback(msg):  
    cmdType = None
    if msg != None and len(msg.items()) != 0:
        cmdType = msg["ct"] if msg["ct"] != None else None
    #connection status
    if cmdType == 116:
        #Device connection status e.g. data["command"] = true(connected) or false(disconnected)
        print(json.dumps(msg))
	
def TwinUpdateCallback(msg):
    global Sdk
    if msg:
        print("--- Twin Message Received ---")
        print(json.dumps(msg))
        if ("desired" in msg) and ("reported" not in msg):
            for j in msg["desired"]:
                if ("version" not in j) and ("uniqueId" not in j):
                    Sdk.UpdateTwin(j,msg["desired"][j])


def sendBackToSDK(sdk, dataArray):
    sdk.SendData(dataArray)
    time.sleep(interval)


def DirectMethodCallback1(msg,methodname,rId):
    global Sdk,ACKdirect
    print(msg)
    print(methodname)
    print(rId)
    data={"data":"succed"}
    ACKdirect.append({"data":data,"status":200,"reqId":rId})


def DirectMethodCallback(msg,methodname,rId):
    global Sdk,ACKdirect
    print(msg)
    print(methodname)
    print(rId)
    data={"data":"fail"}
    ACKdirect.append({"data":data,"status":200,"reqId":rId})


def DeviceChangeCallback(msg):
    print(msg)


def InitCallback(response):
    print(response)


def main():
    global SId,cpid,env,SdkOptions,Sdk,ACKdirect,device_list,plugin, device_messages
    try:
        with IoTConnectSDK(UniqueId,SId,cpid,env,pf,SdkOptions,DeviceConectionCallback) as Sdk:
            try:
                if plugin != "Default":
                    sensor_thread = threading.Thread(target=plugin_module.main_loop)
                    sensor_thread.start()
                Sdk.onDeviceCommand(DeviceCallback)
                Sdk.onTwinChangeCommand(TwinUpdateCallback)
                Sdk.onOTACommand(DeviceFirmwareCallback)
                Sdk.onDeviceChangeCommand(DeviceChangeCallback)
                Sdk.getTwins()
                device_list=Sdk.Getdevice()
                while True:
                    if plugin != "Default":
                        dObj = [{
                            "uniqueId": UniqueId,
                            "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                            "data": plugin_module.telemetry
                        }]
                    else:
                        data = {"random_integer": random.randint(1,100)}
                        if device_messages:
                            data["device_messages"] = ""
                            for msg in device_messages:
                                if data["device_messages"] != "":
                                    data["device_messages"] += ", "
                                data["device_messages"] += msg
                            device_messages = []
                        dObj = [{
                            "uniqueId": UniqueId,
                            "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                            "data": data
                        }]
                    sendBackToSDK(Sdk, dObj)
                    
            except KeyboardInterrupt:
                print ("Keyboard Interrupt Exception")
                sys.exit(0)
                 
    except Exception as ex:
        print(ex)
        sys.exit(0)

if __name__ == "__main__":
    main()
