Author: Softweb Solutions An Avnet Company
Brief: IOT Connect SDK: Software Development Kit 1.0
Modify: 02-January-2023

This IoTConnect Python SDK package will show you how to install and run the firmware file.

Getting started

Prerequisites
Before you install and run the firmware file, we recommend to check with the following set up requirements:
1. Python: IoTConnect's Python SDK supports 2.7, 3.6, 3.7 and 3.8 Python versions. However, we suggest to install the most stable Python version 3.7.9
2. pip: pip is compatible with the Python version
3. setuptools: It requires to manage the Python packages

Installation 
1. Download "iotconnect-python-sdk-v1.0.zip" and extract.

2. If your device is already having previous IoTConnect Python SDK version, uninstall before going to install the latest version. 
	- Note: Ensure your pip version matches with the Python version you are uninstalling. (pip3.7,python3.7)
    - pipx.x list 
    - Find your package name (iotconnect-sdk)
    - pipx.x uninstall <<iotconnect-sdk>>    
	
3. Use the below commands to install the required libraries:
	- Go to SDK directory path using terminal/command prompt
	- cd iotconnect-python-sdk-v1.0/
    - For the Python versions 3.6, 3.7 and 3.8:
		- pip3 install iotconnect-sdk-1.0.tar.gz
	- For the Python version 2.7:
		- Extract the iotconnect-sdk-1.0.tar.gz
		- cd iotconnect-sdk-1.0/
		- python setup.py install		

4. Use the terminal/command prompt to go to the sample folder.
	- cd sample/
	
5. Edit your firmware file (iotconnect-sdk-1.0-firmware-python_msg-2_1.py) and update the following details:
	- Edit the required fields as explained in the below Prerequisite configuration (UniqueId, SId, interval)
	- If your device is secured, configure the x.509 certificate path mentioned in sdkOptions given below. Else, do not make any changes
	- Set your discoveryUrl as per your environment as shown below in sdkOptions
	- Configure offlineStorage in sdkOptions
	- Update sensor attributes (name and data type) exactly as added in the IoTConnect platform

Run
	- For the Python versions 3.6, 3.7 and 3.8: 
		- python3 iotconnect-sdk-1.0-firmware-python_msg-2_1.py
	- For the Python version 2.7: 
		- python iotconnect-sdk-1.0-firmware-python_msg-2_1.py
	The above script will send data to the cloud as per the configured device details.
	
Explanation
- Import the below SDK package to initialize the SDK object.
```python
from iotconnect import IoTConnectSDK
```

Prerequisite configuration
```python
#This Python SDK works with two options. Option:1 UniqueID+SId or Option:2 UniqueId+cpid+env
#If you have Option1 details then leave cpid+env details as ""
#If you have Option2 details then leave SId detail as ""
#Don't Comment or remove this veriables.
UniqueId = "<<Device UniqueID>>"
SId = ""
cpid = ""
env = ""
interval = 30
```
"UniqueId": Your device uniqueId
"SId" 	  : SId is the company code. You can get it from the IoTConnect UI portal "Settings -> Key Vault -> SDK Identities -> select language Python and Version 1.0"
"cpid"    : Company ID
"env"     : Environment
"interval": Set telemtetry data interval as per yuor device use case

SdkOptions
- SdkOptions is for the SDK configuration. It needs to parse in SDK object initialize call. Manage the below configuration as per your device authentication type.
```python
SdkOptions={
	"certificate" : { 
		"SSLKeyPath"  : "",    #aws=pk_devicename.pem   ||   #az=device.key
		"SSLCertPath" : "",    #aws=cert_devicename.crt ||   #az=device.pem
		"SSLCaPath"   : ""     #aws=root-CA.pem         ||   #az=rootCA.pem 
        
	},
    "offlineStorage":{
        "disabled": False,
	    "availSpaceInMb": 0.01,
	    "fileCount": 5,
        "keepalive":60
    },
    "skipValidation":False,
    # "devicePrimaryKey":"<<DevicePrimaryKey>>",
    # "discoveryUrl":"https://eudiscovery.iotconnect.io" #Azure EU environment 
    # "discoveryUrl":"https://discovery.iotconnect.io", #Azure QA, Avnet, Prod environment 
    "discoveryUrl":"http://52.204.155.38:219", #AWS pre-QA Environment
    "IsDebug": False
   
}
```
 sdkOptions is mandatory for "certificate" X.509 device authentication type.
 "certificate": It requires the path of the certificate file. Mandatory for X.509/SSL device CA-signed or self-signed authentication type.
 	- SSLKeyPath: your device key
 	- SSLCertPath: your device certificate
 	- SSLCaPath: Root CA certificate
 	- Windows + Linux OS: Use "/" forward slash (Example: Windows: "E:/folder1/folder2/certificate", Linux: "/home/folder1/folder2/certificate)
 "offlineStorage": Define the configuration related to the offline data storage 
 	- disabled: False = offline data storing, True = not storing offline data 
 	- availSpaceInMb: Define the file size of offline data in MB
 	- fileCount: Number of files need to create for offline data
 "devicePrimaryKey": It is mandatory for the Symmetric Key Authentication support. You can get it from the IoTConnect UI portal "Device -> Select device -> info(Tab) -> Connection Info -> Device Connection"
    - "devicePrimaryKey": "<<your Key>>"
 Note: 
SSL/X.509 device CA-signed or self-signed authentication type requires sdkOptions. Define the proper certification path.
If you do not provide offline storage, the firmware file will set the default settings as defined above. 
The extensive data storage may harm your device. Also, once memory gets full, the SDK execution may stop.

To initialize the SDK object and connect to the cloud
```python
	with IoTConnectSDK(UniqueId,SId,SdkOptions,DeviceConectionCallback) as Sdk:
```

To receive the command from cloud-to-device 	
```python
	def DeviceCallback(msg):
		print(json.dumps(msg))
		if cmdType == 0:
			#Device comand Received 
			if "id" in data:
					if "ack" in data and data["ack"]:
						Sdk.sendAckCmd(data["ack"],7,"sucessfull",data["id"])  #fail=4,executed= 5,sucess=7,6=executedack 
						#To send ACK for gateway type device
				else:
					if "ack" in data and data["ack"]:
						Sdk.sendAckCmd(data["ack"],7,"sucessfull") #fail=4,executed= 5,sucess=7,6=executedack	
						#To send ACK for non-gateway type device
```

To receive the OTA command from cloud-to-device 
```python
	def DeviceFirmwareCallback(msg):
		print(json.dumps(msg))
		if cmdType == 1:
			if ("urls" in data) and data["urls"]:
					for url_list in data["urls"]:
						if "tg" in url_list:
							for i in device_list:
								if "tg" in i and (i["tg"] == url_list["tg"]):
									Sdk.sendOTAAckCmd(data["ack"],0,"sucessfull",i["id"]) #Success=0, Failed = 1, Executed/DownloadingInProgress=2, Executed/DownloadDone=3, Failed/DownloadFailed=4
									#To send ACK for gateway type device
						else:
							Sdk.sendOTAAckCmd(data["ack"],0,"sucessfull") #Success=0, Failed = 1, Executed/DownloadingInProgress=2, Executed/DownloadDone=3, Failed/DownloadFailed=4
							#To send ACK for non-gateway type device
```

Device Connect Disconnect Command
```python
	def DeviceConectionCallback(msg):  
		if cmdType == 116:
			#Device connection status e.g. data["command"] = true(connected) or false(disconnected)
			print(json.dumps(msg))
```

To receive the twin from cloud-to-device 
```python
	def TwinUpdateCallback(msg):
		print(json.dumps(msg))
		sdk.UpdateTwin(key, value)
```
"key" 	:	Desired property key received from Twin callback message
"value"	:	Value of the respective desired property

To publish the data on cloud device to cloud
```python
	def sendBackToSDK(sdk, dataArray):
    sdk.SendData(dataArray)
    time.sleep(interval)
```

To get device attributes in firmware
```python
	def attributeDetails(data):
		print ("attribute received in firmware")
		print (data)
```

To request the list of attributes with the respective device type
```python
	devices=sdk.GetAttributes()
```

Standard data input format for gateway and non-gateway device to send the data on IoTConnect
```python
1. For non-gateway device 
data = [{"temperature":random.randint(30, 50)}
    dObj= [{
	"uniqueId": UniqueId,
	"time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
	"data": data
	}]

2. For gateway and multiple child devices 
dObj = [{
	"uniqueId": "<< Gateway Device UniqueId >>",
	"time": "<< date >>",
	"data": {"temperature":random.randint(30, 50)}
},
{
	"uniqueId":"<< Child DeviceId >>", 
	"time": "<< date >>",
	"data": {"temperature":random.randint(30, 50)}
}]
sendBackToSDK(Sdk, dObj)
```
"time": Date format should be #"2021-01-24T10:06:17.857Z" 
"data": JSON data type format # {"temperature": 15.55, "gyroscope" : { 'x' : -1.2 }}


To disconnect the device from the cloud
```python
	sdk.Dispose()
```

To get all the twin property desired and reported
```python
	sdk.GetAllTwins();
```

## Release Note :
IOT Connect SDK: Software Development Kit 1.0, Message type 2.1

** New Feature **
 SDK will work in AWS and Azure environment.

** Improvements **
 SDK connection on azure and aws based on platform name received from discoveryUrl
 help.txt and help site documentation improevment

