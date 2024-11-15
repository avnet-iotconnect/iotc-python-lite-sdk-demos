import sys
import json
import os.path
import copy
import time
import threading
import ssl
import ntplib
import datetime
from threading import Timer
from base64 import b64encode, b64decode
from hashlib import sha256
from hmac import HMAC

if sys.version_info >= (3, 5):
    import http.client as httplib
    import urllib.request as urllib
    from urllib.parse import urlparse,quote_plus,urlencode

else:
    import httplib
    from urllib import quote_plus,urlencode
    import urllib2 as urllib
    from urlparse import urlparse

from iotconnect.client.mqttclient import mqttclient
from iotconnect.client.httpclient import httpclient
from iotconnect.client.offlineclient import offlineclient

from iotconnect.common.data_evaluation import data_evaluation
from iotconnect.common.rule_evaluation import rule_evaluation

from iotconnect.common.infinite_timer import infinite_timer

from iotconnect.IoTConnectSDKException import IoTConnectSDKException

MSGTYPE = {
    "RPT": 0,
    "FLT": 1,
    "RPTEDGE": 2,
    "RMEdge": 3,
    "LOG" : 4,
    "ACK" : 5,
    "OTA" : 6,
    "FIRMWARE": 11
}
ErorCode = {
    "OK": 0,
    "DEV_NOT_REG": 1,
    "AUTO_REG": 2,
    "DEV_NOT_FOUND": 3,
    "DEV_INACTIVE": 4,
    "OBJ_MOVED": 5,
    "CPID_NOT_FOUND": 6
}
CMDTYPE = {
    "DCOMM": 0,
    "FIRMWARE": 1,
    "MODULE":2,
    "U_ATTRIBUTE": 101,
    "U_SETTING": 102,
    "U_RULE": 103,
    "U_DEVICE": 104,
    "DATA_FRQ": 105,
    "U_barred":106,
    "D_Disabled":107,
    "D_Released":108,
    "STOP":109,
    "Start_Hr_beat":110,
    "Stop_Hr_beat":111,
    "is_connect": 116,
    "SYNC": "sync",
    "RESETPWD": "resetpwd",
    "UCART": "updatecrt"
}
OPTION = {
    "attribute": "att",
    "setting": "set",
    "protocol": "p",
    "device": "d",
    "sdkConfig": "sc",
    "rule": "r"
}
DATATYPE = {
    1: "INT",
    2:"LONG",
    3:"FLOAT", 
    4:"STRING",
    5:"Time",
    6:"Date",
    7:"DateTime",
    8:"BIT",
    9:"Boolean",
    10:"LatLong",
    11:"OBJECT"
}

class IoTConnectSDK:
    _pubRpt = None
    _subTopic = None
    _property=None
    _config = None
    _cpId = None
    _env = None
    _sId =None
    _uniqueId = None
    pf = None
    _listner_callback = None
    _listner_ota_callback = None
    _listner_device_callback = None
    _listner_attchng_callback = None
    _listner_module_callback = None
    _listner_devicechng_callback = None
    _listner_rulechng_callback = None
    _listner_creatchild_callback=None
    _listner_twin_callback = None
    _data_json = None
    _client = None
    _is_process_started = False
    _is_dispose = False
    _base_url = ""
    _thread = None
    _ruleEval = None
    _offlineClient = None
    _lock = None
    _dispose = False
    _live_device=[]
    _debug=False
    _data_frequency = 60
    _debug_error_path=None
    _debug_output_path=None
    _dftime=None
    _offlineflag = False
    _time_s=None
    _heartbeat_timer = None
    deletechild=None
    _listner_deletechild_callback = None
    _validation = True
    _getattribute_callback = None
    _data_evaluation = None
    def get_config(self):
        try:
            self._config = None
            _path = os.path.abspath(os.path.dirname(__file__))
            _config_path = os.path.join(_path, "assets/config.json")
            with open(_config_path) as config_file:
                self._config = json.loads(config_file.read())
            if not self.get_properties():
                raise(IoTConnectSDKException("01", "Config file"))
            
        except:
            raise(IoTConnectSDKException("01", "Config file"))
    
    def getTwins(self):
        if self._dispose == True:
            raise(IoTConnectSDKException("00", "you are not able to call this function"))
        if self._is_process_started == False:
            return
        if self._client:
            self._client.get_twin()

    def get_properties(self):
        try:
            _properties = self._property
            if _properties != None:
                for prop in _properties:
                    if _properties[prop]:
                        self._config[prop] = _properties[prop]
                    else:
                        self._config[prop] = None
                    if prop == 'IsDebug' and _properties[prop] == True:
                        self._debug=True
            return True
        except Exception as ex:
            return False           
            
    
    def reconnect_device(self,msg):
        # print(msg)
        try:
            print(msg)
            #self.process_sync("all")   
        except:
            self._offlineflag = True
                
    def get_base_url(self, sId):
        try:
            if not self._cpId:
                base_url = "/api/v2.1/dsdk/sid/" + sId
                base_url = self._property["discoveryUrl"] + base_url
            else:
                if self.pf == "az":
                    base_url = "/api/v2.1/dsdk/cpid/"+ self._cpId +"/env/" + self._env
                if self.pf == "aws":
                    base_url = "/api/v2.1/dsdk/cpid/"+ self._cpId +"/env/" + self._env + "?pf=aws"
                else:
                    base_url = "/api/v2.1/dsdk/cpid/"+ self._cpId +"/env/" + self._env                        
                base_url = self._property["discoveryUrl"] + base_url

            res = urllib.urlopen(base_url).read().decode("utf-8")
            data = json.loads(res)
            #print(data)
            # pf = None
            a = (data['d'].keys())
            if 'pf' in a:
                # print(pf)
                return data['d']["bu"], data['d']["pf"]
            else:
                pf = 'aws'
                return data['d']["bu"], pf  
            
        except Exception as ex:
            print (ex.message)
            return None
    
    def generate_sas_token(self,uri, key, policy_name=None, expiry=31536000):
        ttl = time.time() + expiry
        sign_key = "%s\n%d" % ((quote_plus(uri)), int(ttl))
        signature = b64encode(HMAC(b64decode(key), sign_key.encode('utf-8'), sha256).digest())
        rawtoken = {
            'sr' :  uri,
            'sig': signature,
            'se' : str(int(ttl))
        }
        if policy_name is not None:
            rawtoken['skn'] = policy_name
        return 'SharedAccessSignature ' + urlencode(rawtoken)

    def post_call(self, url):
        try:
            url=url+"/uid/"+self._uniqueId
            res = urllib.urlopen(url).read().decode("utf-8")
            data = json.loads(res)
            #print (data)
            return data
        except:
            return None
    
    def Dispose(self):
        try:
            if self._dispose == True:
                self.write_debuglog('[ERR_DC02] '+ self._time +'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] Connection not available",1)
                self.write_debuglog('[INFO_DC01] '+'['+ str(self._sId)+'_'+str(self._uniqueId)+"] Device already disconnected: "+self._time,0)
                return True
            for attr in self.attributes:
                if self.has_key(attr, "evaluation"):
                    attr["evaluation"].destroyed()
                    del attr["evaluation"]
            if self._client and hasattr(self._client, 'Disconnect'):
                
                self._client.Disconnect()
            self._is_process_started=False
            self._dispose = True
            self._property=None
            self._config = None
            self._cpId = None
            self._uniqueId = None
            self._listner_callback = None
            self._listner_twin_callback = None
            self._listner_direct_callback_list = None
            self._data_json = None
            self._client = None
            self._base_url = ""
            self._thread = None
            self._ruleEval = None
            self._offlineClient = None
            self._lock = None
            self._live_device=[]
            self._debug=False
            return True
        except:
            raise(IoTConnectSDKException("00","Dispose error.."))

    def onOTACommand(self,callback):
        if callback:
            self._listner_ota_callback = callback

    def onModuleCommand(self,callback):
        if callback:
            self._listner_module_callback = callback

    def onDeviceCommand(self,callback):
        if callback:
            self._listner_device_callback = callback

    def onTwinChangeCommand(self,callback):
        if callback:
            self._listner_twin_callback = callback

    def onAttrChangeCommand(self,callback):
        if callback:
            self._listner_attchng_callback = callback
    
    def onDeviceChangeCommand(self,callback):
        if callback:
            self._listner_devicechng_callback=callback

    def onRuleChangeCommand(self,callback):
        if callback:
            self._listner_rulechng_callback = callback

    def heartbeat_stop(self):
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
            self._heartbeat_timer = None

    def heartbeat_start(self,time):
        if self._heartbeat_timer:
            self._heartbeat_timer.cancel()
        if self._client:
            self._heartbeat_timer=infinite_timer(time,self._client.send_HB)
            self._heartbeat_timer.start()

    def onMessage(self, msg):
        # print("\n====================>>>>>>>>>>>>>>>>>>>>>>>\n")
        # print ("Cloud To Device Message Received::\n",msg)
        # print("\n<<<<<<<<<<<<<<<<<<<<<<<====================\n")
        try:            
            if self._dispose == True:
                return
            if msg == None:
                return
            else:
                self._is_process_started = True
                
                if self.has_key(msg,"data") and msg["data"]:
                    msg=msg["data"]
                if self.has_key(msg,"d") and msg["d"]:
                    msg=msg["d"]
                    print(msg)
                    if msg['ec'] == 0 and msg["ct"] == 201:
                        if self._getattribute_callback == None:
                            self._data_json["att"] = msg["att"]
                            for attr in self.attributes:
                                print(self.attributes)
                                attr["evaluation"] = data_evaluation(self.isEdge, attr, self.send_edge_data)
                            self._is_process_started = True
                            self._offlineflag=False
                            print("..........Atrributes Get Successfully...........")
                        if self._getattribute_callback:
                            self._getattribute_callback(msg["att"])
                            self._getattribute_callback = None

                    if msg['ec'] == 0 and msg["ct"] == 202:
                        self._data_json["set"] = msg["set"]
                    if msg['ec'] == 0 and msg["ct"] == 203:
                        self._data_json["r"] = msg["r"]
                    if msg['ec'] == 0 and msg["ct"] == 204 and len(msg['d']) != 0:
                        self._data_json['d']=[]
                        self._data_json['d'].append({'tg': self._data_json['meta']['gtw']['tg'],'id': self._uniqueId})
                        for i in msg["d"]:
                                self._data_json['d'].append(i)
                        if self._listner_devicechng_callback:
                            self._listner_devicechng_callback(msg)
                    if msg['ec'] == 0 and msg["ct"] == 205:
                        self._data_json["ota"] = msg["ota"]
                    if msg["ct"] == 221:
                        if self._listner_creatchild_callback:
                            if msg["ec"] == 0:
                                self._listner_creatchild_callback({"status":True,"message":self.__child_error_log(msg["ec"])})
                            else:
                                self._listner_creatchild_callback({"status":False,"message":self.__child_error_log(msg["ec"])})
                    if msg["ct"] == 222: 
                        if self._listner_deletechild_callback:
                            if msg["ec"] == 0:
                                self._listner_deletechild_callback({"status":True,"message":"sucessfuly delete child device"})
                                for i in range(0,len(self._data_json["d"])):
                                    if self._data_json["d"][i]["ename"] == self.deletechild:
                                        self._data_json["d"].pop(i)
                                        break
                            else:
                                self._listner_deletechild_callback({"status":True,"message":"fail to delete child device"})
                        self._listner_deletechild_callback=None
                    return
                else:
                    pass
                if "ct" in msg:
                    if msg["ct"] == CMDTYPE["is_connect"]:
                        # msg["data"]["uniqueId"] = self._uniqueId
                        msg["uniqueId"] = self._uniqueId
                        # if msg["data"]["command"] in "False":
                        if msg["command"] in "False":    
                            self._offlineflag = True
                            if self._is_process_started:
                                self.reconnect_device("reconnect")
                        
                        if self._listner_callback:
                            # self._listner_callback(msg["data"])
                            self._listner_callback(msg)
                        self.write_debuglog('[INFO_CM09] '+ self._time +'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] 0x116 sdk connection status: " + msg["command"],0)
                        return
            if self._is_process_started == False:
                return
            if "ct" not in msg:
                print("Command Received : " + json.dumps(msg))
                return
            _tProcess = None
            if msg["ct"] == CMDTYPE["U_ATTRIBUTE"]:
                if self._listner_attchng_callback:
                    self._listner_attchng_callback(msg)
                print(str(CMDTYPE["U_ATTRIBUTE"])+" U_ATTRIBUTE command received...")
                print(msg)
                _tProcess = threading.Thread(target = self.reset_process_sync, args = ["ATT"])
            elif msg["ct"] == CMDTYPE["Stop_Hr_beat"]:
                print(str(CMDTYPE["Start_Hr_beat"])+" Stop_Hr_beat command received...")
                print(msg)
                self.heartbeat_stop()
            elif msg["ct"] == CMDTYPE["Start_Hr_beat"]:
                HBtime=msg["f"]
                print(str(CMDTYPE["Start_Hr_beat"])+" Start_Hr_beat command received...")
                print(msg)
                self.heartbeat_start(HBtime)
            elif msg["ct"] == CMDTYPE["U_SETTING"]:
                print(str(CMDTYPE["U_SETTING"])+" U_SETTING command received...")
                print(msg)
                _tProcess = threading.Thread(target = self.reset_process_sync, args = ["SETTING"])
            elif msg["ct"] == CMDTYPE["U_DEVICE"]:
                print(str(CMDTYPE["U_DEVICE"])+" U_DEVICE command received...")
                print(msg)
                _tProcess = threading.Thread(target = self.reset_process_sync, args = ["DEVICE"])
            elif msg["ct"] == CMDTYPE["U_RULE"]:
                if self._listner_rulechng_callback:
                    self._listner_rulechng_callback(msg)
                print(str(CMDTYPE["U_RULE"])+" U_RULE command received...")
                print(msg)
                _tProcess = threading.Thread(target = self.reset_process_sync, args = ["RULE"])
            elif msg["ct"] == CMDTYPE["RESETPWD"]:
                #try to debuge
                print(str(CMDTYPE["RESETPWD"])+" RESETPWD command received...")
                print(msg)
                _tProcess = threading.Thread(target = self.reset_process_sync, args = ["protocol"])
            elif msg["ct"] == CMDTYPE["DATA_FRQ"]:
                print(str(CMDTYPE["DATA_FRQ"])+" DATA_FRQ command received...")
                print(msg)
                self._data_json['meta']["df"]= msg["df"]
                self._data_frequency = msg["df"]
            elif msg["ct"] == CMDTYPE["UCART"]:
                print(str(CMDTYPE["UCART"])+" UCART command received...")
                print(msg)
                pass
            elif msg["ct"] == CMDTYPE["DCOMM"]:
                print(str(CMDTYPE["DCOMM"])+" DCOMM command received...")
                print(msg)    
                if self._listner_device_callback != None:
                    self._listner_device_callback(msg)
            elif msg["ct"] == CMDTYPE["FIRMWARE"]:
                print(str(CMDTYPE["FIRMWARE"])+" FIRMWARE command received...")
                print(msg)
                if self._listner_ota_callback: 
                    self._listner_ota_callback(msg)
            elif msg["ct"] == CMDTYPE["MODULE"]:
                print(str(CMDTYPE["MODULE"])+" MODULE command received...")
                print(msg)
                if self._listner_module_callback: 
                    self._listner_module_callback(msg)        
            elif msg["ct"] == CMDTYPE["U_barred"] or msg["ct"] == CMDTYPE["D_Disabled"] or msg["ct"] == CMDTYPE["D_Released"] or msg["ct"] == CMDTYPE["STOP"]:
                if msg["ct"] == CMDTYPE["U_barred"]:
                    print(str(CMDTYPE["U_barred"])+" U_barred command received...")
                    print(msg)
                if msg["ct"] == CMDTYPE["D_Disabled"]:
                    print(str(CMDTYPE["D_Disabled"])+" D_Disabled command received...")
                    print(msg)
                if msg["ct"] == CMDTYPE["D_Released"]:
                    print(str(CMDTYPE["D_Released"])+" D_Released command received...")
                    print(msg)
                if msg["ct"] == CMDTYPE["STOP"]:
                    print(str(CMDTYPE["STOP"])+" STOP command received...")
                    print(msg)
                    self._dispose=True
                self._is_dispose=True
                self._is_process_started=False
                if self._offlineClient:
                    self._offlineClient.clear_all_files()
                if self._client and hasattr(self._client, 'Disconnect'):
                    self._client.Disconnect()
                # print("0x99 command received so device is barred")
            else:
                print("Message : " + json.dumps(msg))
            
            if _tProcess != None:
                _tProcess.setName("PSYNC")
                _tProcess.daemon = True
                _tProcess.start()
                
        except Exception as ex:
            print("Message process failed..."+ str(ex))
    
    def onTwinMessage(self, msg,value):
        try:
            if self._dispose == True:
                raise(IoTConnectSDKException("00", "you are not able to call this function"))    
            if self._is_process_started == False:
                return
            #if self.has_key("payload", msg) == False and ((msg.payload == None) or (msg.payload == '')):
            #    return
            #msg = msg.payload.decode("utf-8")
            #if msg == None or len(msg) == 0 :
            #    return
            #msg = json.loads(msg)
            if  value:
                temp=msg
                msg={}
                msg["desired"]=temp
                msg["uniqueId"] = self._uniqueId
            else:
                msg["uniqueId"] = self._uniqueId
            if self._listner_twin_callback != None:
                self._listner_twin_callback(msg)
        except Exception as ex:
            print("Message process failed...",ex)

    def onDirectMethodMessage(self,msg,methodname,requestId):
        try:
            if self._listner_direct_callback_list :
                self._listner_direct_callback_list[str(methodname)](msg,methodname,requestId)
        except Exception as ex:
            print(ex)

    def init_protocol(self):
        try:
            protocol_cofig = self.protocol
            name = protocol_cofig["n"]
            self._subTopic = protocol_cofig["topics"]["c2d"]
            self._pubRpt= protocol_cofig['topics']['rpt']
            protocol_cofig["pf"] = self._pf
            auth_type = self._data_json["meta"]['at']
            if auth_type == 2 or auth_type == 3:
                cert=self._config["certificate"]
                if len(cert) == 3:
                    for prop in cert:
                        if os.path.isfile(cert[prop]) == True:
                            pass
                        else:
                            self.write_debuglog('[ERR_IN06] '+ self._time +'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] sdkOption: set proper certificate file path and try again",1)
                            raise(IoTConnectSDKException("05"))
                else:
                    self.write_debuglog('[ERR_IN06] '+ self._time +'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] sdkOption: set proper certificate file path and try again",1)
                    raise(IoTConnectSDKException("01","Certificate/Key in Sdkoption"))
            if auth_type == 5:
                if ("devicePrimaryKey" in self._property) and self._property["devicePrimaryKey"]:
                    protocol_cofig["pwd"]=self.generate_sas_token(protocol_cofig["h"],self._property["devicePrimaryKey"])
                else:
                    raise(IoTConnectSDKException("01", "devicePrimaryKey"))
            if self._client != None:
                self._client = None
            if name == "mqtt":
                self._client = mqttclient(auth_type, protocol_cofig, self._config, self.onMessage,self.onDirectMethodMessage, self.onTwinMessage) 
            elif name == "http" or name == "https":
                self._client = httpclient(protocol_cofig, self._config)
            else:
                self._client = None
        except Exception as ex:
            raise(ex)
    
    def _hello_handsake(self,data):
        if self._client:
            self._client.Send(data,"Di")

    def process_sync(self, option):
        try:
            self._time_s=10
            isReChecking = False
            if option == "all":
                url = self._base_url
                response = self.post_call(url)
                print (response)
                if response == None:
                    if self._offlineflag == True:
                        isReChecking=True
                    else:
                        raise(IoTConnectSDKException("01", "Sync response"))
                else:
                    if self.has_key(response, "d"):
                        response = response["d"]
                        self.write_debuglog('[INFO_IN01] '+'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] Device information received successfully: "+ self._time ,0)
                        self._offlineflag = False
                    else:
                        raise(IoTConnectSDKException("03", response["message"]))
                    if response["ec"] != ErorCode["OK"]:
                        isReChecking = True
                        self._time_s=60
                    if response["ec"] == ErorCode["DEV_NOT_FOUND"] or response["ec"] == ErorCode["CPID_NOT_FOUND"] :
                        self.write_debuglog('[ERR_IN10] '+ self._time +'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] Device Information not found",1)
            else:
                if option == "ATT":
                    self._hello_handsake({"mt":201,"sid":self._sId})
                elif option == "SETTING":
                    self._hello_handsake({"mt":202,"sid":self._sId})
                elif option == "DEVICE":
                    self._hello_handsake({"mt":204,"sid":self._sId})
                elif option == "RULE":
                    self._hello_handsake({"mt":203,"sid":self._sId})
                else:
                    pass
            if isReChecking:
                print("\nDisConnected...")
                print("\nTrying to Connect...")
                #self._is_dispose = True
                _tProcess = threading.Thread(target = self.reset_process_sync, args = [option])
                time.sleep(self._time_s)
                _tProcess.setName("PSYNC")
                _tProcess.daemon = True
                _tProcess.start()
                return
            else:
                # Pre Process
                self.clear_object(option)
                # --------------------------------
                if option == "all":
                    self._is_process_started = False
                    self._data_json = response
                    self.init_protocol()
                    if self._pf == "aws":
                        data = { "_connectionStatus": "true" }
                        self._client.SendTwinData(data)
                        print("\nPublish connection status shadow sucessfully... %s" % self._time)
                    if self.has_key(self._data_json,"has") and self._data_json["has"]["attr"]:
                        # self._hello_handsake({"mt":201,"sid":self._sId})
                        self._hello_handsake({"mt":201})
                    if self.has_key(self._data_json,"has") and self._data_json["has"]["set"]:
                        self._hello_handsake({"mt":202,"sid":self._sId})
                    if self.has_key(self._data_json,"has") and self._data_json["has"]["r"]:
                        self._hello_handsake({"mt":203 ,"sid":self._sId})
                    if self.has_key(self._data_json,"has") and self._data_json["has"]["d"]:
                        self._hello_handsake({"mt":204,"sid":self._sId}) 
                    else:
                        if self._data_json['meta']['gtw'] != None:
                            self._data_json['d']=[{'tg': self._data_json['meta']['gtw']['tg'],'id': self._uniqueId}]
                        else:
                            self._data_json['d']=[{'tg': '','id': self._uniqueId}]
                    if self.has_key(self._data_json,"has") and self._data_json["has"]["ota"]:
                        self._hello_handsake({"mt":205,"sid":self._sId})
                    if "df" in self._data_json['meta'] and self._data_json['meta']["df"]:
                        self._data_frequency=1
                
        except Exception as ex:
            raise ex
    
    def find_df(self,seconds): 
        seconds = seconds % (24 * 3600) 
        hour = seconds // 3600
        seconds %= 3600
        minutes = seconds // 60
        seconds %= 60
        times= datetime.datetime.strptime("%02d%02d%02d" % (hour, minutes, seconds),'%H%M%S')
        return times

    def SendData(self,jsonArray):
        try:
            if self._dispose == True:
                raise(IoTConnectSDKException("00", "you are not able to call this function"))
            if self._is_process_started == False:
                self.write_debuglog('[ERR_SD04] '+ self._time +'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] Device is barred SendData() method is not permitted",1)
                return
            if self.has_key(self._data_json,"att") == False:
                print("\n")
                return
            
            nowtime=datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            time_zero = datetime.datetime.strptime('000000', '%H%M%S')
            edge_flt_flag = False
            if self._dftime != None:
                if int(nowtime) >= self._dftime:
                    nowtime=datetime.datetime.strptime(str(nowtime),"%Y%m%d%H%M%S")
                    self._dftime = int((nowtime - time_zero + self.find_df(self._data_frequency)).strftime("%Y%m%d%H%M%S"))
                    if self.isEdge:
                        edge_flt_flag=True
                else:
                    if not self.isEdge:
                        return
            else:
                nowtime=datetime.datetime.strptime(str(nowtime),"%Y%m%d%H%M%S")
                self._dftime = int((nowtime - time_zero + self.find_df(self._data_frequency)).strftime("%Y%m%d%H%M%S"))
                if self.isEdge:
                    edge_flt_flag=True
            #--------------------------------
            rul_data = []
            rpt_data = self._data_template
            flt_data = self._data_template
            for obj in jsonArray:
                rul_data = []
                uniqueId = obj["uniqueId"]
                time = obj["time"]
                sensorData = obj["data"]
                for attr in self.attributes:
                    if self.has_key(attr, "evaluation"):
                        evaluation = attr["evaluation"]
                        evaluation.reset_get_rule_data()
                for d in self.devices:
                    if d["id"] == uniqueId:
                        if uniqueId not in self._live_device:
                            self._live_device.append(uniqueId)
                        if self._data_json['has']['d']:
                            tg = d["tg"]
                            r_device = {
                                "id": uniqueId,
                                "dt": time,
                                "tg": tg 
                            }
                        else:
                            r_device = {
                                "dt": time
                            }
                        f_device = copy.deepcopy(r_device)
                        r_attr_s = {}
                        f_attr_s = {}
                        real_sensor=[]
                        for attr in self.attributes: 
                            if attr["p"] == "" and self.has_key(attr, "evaluation"):
                                evaluation = attr["evaluation"]
                                evaluation.reset_get_rule_data()
                                for dObj in attr["d"]:
                                    child=True
                                    if self._data_json['has']['d']:
                                        if tg == dObj["tg"]:
                                            pass
                                        else:
                                            child=False
                                    if child and self.has_key(sensorData, dObj["ln"]):
                                        value = sensorData[dObj["ln"]]
                                        real_sensor.append(dObj["ln"])
                                        if self.isEdge:
                                            if type(value) == str:
                                                try:
                                                    sub_value=float(value)
                                                except:
                                                    real_sensor.remove(dObj["ln"])     
                                        if value != None:
                                            row_data = evaluation.process_data(dObj, attr["p"], value,self._validation)
                                            if row_data and self.has_key(row_data,"RPT"):
                                                for key, value in row_data["RPT"].items():
                                                    r_attr_s[key] = value
                                            if row_data and self.has_key(row_data, "FLT"):
                                                for key, value in row_data["FLT"].items():
                                                    f_attr_s[key] = value
                                        else:
                                            pass
                                            #f_attr_s[sensorData[dObj]]
                                data = evaluation.get_rule_data()
                                if data != None:
                                    rul_data.append(data)
                            
                            elif attr["p"] != "" and self.has_key(attr, "evaluation") and self.has_key(sensorData, attr["p"]) == True:
                                child = True
                                if self._data_json['has']['d']:
                                    if tg == attr["tg"]:
                                        pass
                                    else:
                                        child = False
                                if child:
                                    evaluation = attr["evaluation"]
                                    evaluation.reset_get_rule_data()
                                    real_sensor.append(attr["p"])
                                    sub_sensors=[]
                                    for dObj in attr["d"]:
                                        if self.has_key(sensorData[attr["p"]], dObj["ln"]):
                                            sub_sensors.append(dObj["ln"])
                                            value = sensorData[attr["p"]][dObj["ln"]]
                                            if self.isEdge:
                                                if type(value) == str:
                                                    try:
                                                        sub_value=float(value)
                                                    except:
                                                        sub_sensors.remove(dObj["ln"]) 
                                            if value != None:
                                                row_data = evaluation.process_data(dObj, attr["p"], value,self._validation)
                                                
                                                if row_data and self.has_key(row_data, "RPT"):
                                                    if self.has_key(r_attr_s, attr["p"]) == False:
                                                        r_attr_s[attr["p"]] = {}
                                                    for key, value in row_data["RPT"].items():
                                                        r_attr_s[attr["p"]][key] = value
                                                
                                                if row_data and self.has_key(row_data, "FLT"):
                                                    if self.has_key(f_attr_s, attr["p"]) == False:
                                                        f_attr_s[attr["p"]] = {}
                                                    for key, value in row_data["FLT"].items():
                                                        f_attr_s[attr["p"]][key] = value
                                    unsensor = sensorData[attr["p"]].keys()
                                    unmatch_sensor= list((set(unsensor)- set(sub_sensors)))
                                    for unmatch in unmatch_sensor:
                                        if self.has_key(f_attr_s, attr["p"]) == False:
                                            f_attr_s[attr["p"]] = {}
                                        f_attr_s[attr["p"]][unmatch]=sensorData[attr["p"]][unmatch]          
                                    data = evaluation.get_rule_data()
                                    if data != None:
                                        rul_data.append(data)
                        unsensor=sensorData.keys()
                        unmatch_sensor= list((set(unsensor)- set(real_sensor)))
                        for unmatch in unmatch_sensor:
                            f_attr_s[unmatch]=sensorData[unmatch]
                            #--------------------------------
                        #--------------------------------
                        if self.isEdge and self.hasRules and len(rul_data) > 0:
                            for rule in self.rules:
                                rule["id"]=uniqueId
                                self._ruleEval.evalRules(rule, rul_data)
                        if len(r_attr_s.items()) > 0:
                            r_device["d"]=r_attr_s
                            rpt_data["d"].append(r_device)
                        
                        if len(f_attr_s.items()) > 0:
                            f_device["d"]=f_attr_s
                            flt_data["d"].append(f_device)        
            
            #--------------------------------
            #print("rtp: ",rpt_data)
            #print("flt: ",flt_data)
            
            if len(rpt_data["d"]) > 0:
                self.send_msg_to_broker("RPT", rpt_data)

            if len(flt_data["d"]) > 0:
                if self.isEdge:
                    if edge_flt_flag:
                        self.send_msg_to_broker("FLT", flt_data)
                else:
                    self.send_msg_to_broker("FLT", flt_data)
            #--------------------------------
            
        except Exception as ex:
            if self._dispose == False:
                print(ex)
            else:
                print(ex.message)
    
    def sendAckModule(self,ackGuid, status, msg):
        if self._dispose == True:
            raise(IoTConnectSDKException("00", "you are not able to call this function"))
        if self._is_process_started == False:
            return
        if not msg:
            print("sendAckModule: msg is empty.")
        if ackGuid != None :
            pass
        else:
            raise(IoTConnectSDKException("00", "sendAckModule: ackGuid not valid."))
        try:
            template = self._Ack_data_template
            template["type"] = 2
            template["st"] = status
            template["msg"] = msg
            template["ack"] = ackGuid
            if ackGuid != None:
                self.send_msg_to_broker("CMD_ACK", template)    
        except Exception as ex:
            raise(ex)

    def sendOTAAckCmd(self,ackGuid, status, msg,childId=None):
        if self._dispose == True:
            raise(IoTConnectSDKException("00", "you are not able to call this function"))
        if self._is_process_started == False:
            return
        ischild = False
        if childId != None and type(childId) == str:
            for d in self.devices:
                if d["id"] == childId:
                    ischild=True
        if not msg:
            print("sendAckModule: msg is empty.")
        if ackGuid != None :
            pass
        else:
            raise(IoTConnectSDKException("00", "sendAckModule: ackGuid not valid."))
        try:
            template = self._Ack_data_template
            template["d"]["type"] = 1
            template["d"]["st"] = status
            template["d"]["msg"] = msg
            template["d"]["ack"] = ackGuid
            if ischild:
                template["d"]["cid"] = childId
                if ackGuid != None:
                    print(template)
                    self.send_msg_to_broker("FW", template)
            elif childId:
                pass
            else:
                self.send_msg_to_broker("FW", template)
        except Exception as ex:
            raise(ex)

    def sendAckCmd(self,ackGuid, status, msg,childId=None):
        if self._dispose == True:
            raise(IoTConnectSDKException("00", "you are not able to call this function"))
        if self._is_process_started == False:
            return
        ischild = False
        if childId != None and type(childId) == str:
            for d in self.devices:
                if d["id"] == childId:
                    ischild=True
        if not msg:
            print("sendAckModule: msg is empty.")
        if ackGuid != None :
            pass
        else:
            raise(IoTConnectSDKException("00", "sendAckModule: ackGuid not valid."))
        try:
            template = self._Ack_data_template
            template["d"]["type"] = 0
            template["d"]["st"] = status
            template["d"]["msg"] = msg
            template["d"]["ack"] = ackGuid
            print(template)
            if ischild:
                template["d"]["cid"] = childId
                if ackGuid != None:
                    self.send_msg_to_broker("CMD_ACK", template)
            elif childId:
                pass
            else:
                self.send_msg_to_broker("CMD_ACK", template)
        except Exception as ex:
            raise(ex)

    def UpdateTwin(self, key, value):
        try:
            isvalid = True
            if self._dispose == True:
                raise(IoTConnectSDKException("00", "you are not able to call this function"))
            if self._is_process_started == False:
                self.write_debuglog('[ERR_TP02] '+ self._time +'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] Device is barred Updatetwin() method is not permitted",1)
                return
            for i in self.setting:
                if i["ln"] == key:
                    if len(i["dv"]):
                        #self._data_evaluation = data_evaluation(self.isEdge, 1, self.send_edge_data)
                        #isvalid = self._data_evaluation.twin_validate(i["dt"],i["dv"],value)
                        #isvalid = self.data_evaluation.twin_validate(i["dt"],i["dv"],value)
                        isvalid = False
                        _Online = False
                        _data = {}
                        _data[key] = value
                        if self._client: 
                            _Online = self._client.SendTwinData(_data)
                        if _Online:
                            print("\nupdate twin data sucessfully... %s" % self._time)
                    if isvalid:
                        _Online = False
                        _data = {}
                        _data[key] = value
                        if self._client: 
                            _Online = self._client.SendTwinData(_data)
                        if _Online:
                            print("\nupdate twin data sucessfully... %s" % self._time)
        except Exception as ex:
            print(ex)

    def send_edge_data(self, data):
        try:
            if self._dispose == True:
                return
            if self._is_process_started == False:
                return
            template = self._data_template
            for d in self.devices:
                if (d["tg"] == data["tg"]) and (d["id"] in self._live_device):
                    if d["tg"] == "" and (not self._data_json['has']['d']):
                        device = {
                            "dt": self._timestamp,
                            "d": [],
                        }
                    else:
                        device = {
                            "id": d["id"],
                            "dt": self._timestamp,
                            "d": [],
                            "tg": d["tg"]
                        }
                    device["d"]=data["d"]
                    template["d"].append(device)
            self.send_msg_to_broker("RPTEDGE", template)
        except Exception as ex:
            print(ex)
    
    #need to change in 2.1 format 
    def send_rule_data(self, data):
        try:
            id = self._uniqueId
            if self._data_json['meta']['gtw'] :
                for d in self.devices:
                        if id == d["id"]:
                            data["id"] = d["id"]
                            data["tg"] = d["tg"] 
            tdata = {
                "dt": "",
                "d": [data],
            }        
            tdata["dt"]=self._timestamp
            print(tdata)
            self.send_msg_to_broker("RMEdge", tdata)
        except Exception as ex:
            print(ex)
    
    def send_msg_to_broker(self, msgType, data):
        try:
            self._lock.acquire()
            #return
            
            _Online = False
            if self._client:
                _Online = self._client.Send(data,msgType)
            
            if _Online:
                if msgType == "RPTEDGE":
                    print("\nPublish edge data sucessfully... %s" % self._time)
                elif msgType == "RMEdge":
                    print("\nPublish rule matched data sucessfully... %s" % self._time)
                    print("\nPublish data  %s" % data)
                elif msgType == "CMD":
                    print("\nPublish Command data sucessfully... %s" % self._time)
                elif msgType == "FW":
                    print("\nPublish Firmware data sucessfully... %s" % self._time)
                elif msgType == "CMD_ACK":
                    #print (">>command acknowledge ack", data["d"]["ack"]) 
                    print("\nPublish command acknowledge data sucessfully... %s" % self._time)
                    self.write_debuglog('[INFO_CM10] '+'['+ str(self._sId)+'_'+str(self._uniqueId)+"] Command Acknowledgement sucessfull: "+self._time ,0)
                else:
                    print("\nPublish data sucessfully... %s" % self._time,data,msgType)
            
            if _Online == False:
              if self._is_dispose == False:
                if self._offlineClient:
                    if self._offlineClient.Send(data):
                        self.write_debuglog('[INFO_OS02] '+'['+ str(self._sId)+'_'+str(self._uniqueId)+"] Offline data saved: "+self._time,0)
                        print("\nStoring offline sucessfully... %s" % self._time)
                    else:
                        self.write_debuglog('[ERR_OS03] '+ self._time +'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] Unable to read or write file",1)
                        print("\nYou Unable to store offline data.")
                
            else:
                if self._offlineClient:
                    self._offlineClient.PublishData()
                    
            self._lock.release()
        except Exception as ex:
            print("send_msg_to_broker : ", ex)
            self._lock.release()
    
    def send_offline_msg_to_broker(self, data):
        _Online = False
        if self._client:
            data.update({"od":1})
            _Online = self._client.Send(data,"OD")
            if _Online:
                self.write_debuglog('[INFO_OS01] '+'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] Publish offline data: "+ self._time ,0)
        return _Online
    
    def command_sender(self, command_text,rule):
        try:
            if self._is_process_started == False:
                return
            template = self._command_template
            if self._data_json != None:
                for d in self.devices:
                    if (rule['con'].find(str(d["tg"])) > -1) and (d["id"] in self._live_device):
                        template["id"] = d["id"]
                        template["command"] = command_text
                        if self._listner_device_callback != None:
                            self._listner_device_callback(template)
        except Exception as ex:
            print(ex)
    
    def clear_object(self, option):
        try:
            if option == "all" or option == "attribute":
                for attr in self.attributes:
                    if self.has_key(attr, "evaluation"):
                        attr["evaluation"].destroyed()
                        del attr["evaluation"]
        except Exception as ex:
            raise(ex)
    
    def reset_process_sync(self, option):
        try:
            time.sleep(1)
            self.process_sync(option)
        except Exception as ex:
            print(ex)
    
    def event_call(self, name, taget, arg):
        _thread = threading.Thread(target=getattr(self, taget), args=arg)
        #_thread.daemon = True
        _thread.setName(name)
        _thread.start()

    def delete_chield(self,child_id,callback):
        try:
            if self._dispose == True:
                self.write_debuglog('[ERR_GD03] '+ self._time +'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] Request failed to delete the child device",1)
                raise(IoTConnectSDKException("00", "you are not able to call this function"))
            if self._is_process_started == False:
                return None
            if self._data_json["has"]["d"] != 1:
                raise(IoTConnectSDKException("00", "delete child Device not posibale. it is not gatway device. "))
            for device in self._data_json['d']:
                if child_id == device["id"]:
                    self._listner_deletechild_callback=callback
                    self.deletechild=child_id
                    template={
                        "mt": 222,
                        "d": {
                        "id": child_id
                        }}
                    if self._client:
                        self._client.send("Di",template)
                    
        except:
            return None

    def Getdevice(self):
        try:
            if self._dispose == True:
                raise(IoTConnectSDKException("00", "you are not able to call this function"))
            if self._is_process_started == False:
                return None
            return self.devices
        except:
            return None
    
    def GetAttributes(self,callback):
        try:
            if callback:
                self._getattribute_callback = callback
            # self._hello_handsake({"mt":201,"sid":self._sId})    
            self._hello_handsake({"mt":201})
        except Exception as ex:
            self.write_debuglog('[ERR_GA01] '+ self._time +'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] Get Attributes Error",1)
            return None

    def createChildDevice(self, deviceId, deviceTag, displayName, callback=None):
        try:
            if type(deviceId) != str and type(deviceTag) != str and type(displayName) != str:
                raise(IoTConnectSDKException("00", "Child Device deviceId|deviceTag|displayName all should be string"))

            if self._data_json["has"]["d"] != 1:
                self.write_debuglog('[ERR_GD04] '+ self._time +'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] Child device create : It is not a Gateway device",1)
                raise(IoTConnectSDKException("00", "create child Device not posibale it is not gatway device. "))
            if (type(deviceId)) != str and (" " in deviceId):
                raise(IoTConnectSDKException("00", "create child Device in deviceId space is not valid. "))
            template=self._child_template
            template["dn"]=displayName
            template["id"]=deviceId
            template["tg"]=deviceTag
            if callback:
                self._listner_creatchild_callback=callback
        except:
            self.write_debuglog('[ERR_GD01] '+ self._time +'['+ str(self._sId)+'_'+ str(self._uniqueId) + "] Create child Device Error",1)
            raise(IoTConnectSDKException("04", "createChildDevice"))
    
    def __child_error_log(self,errorcode):
        error={ 
            "0": "OK – No Error. Child Device created successfully",
            "1": "Message missing child tag",
            "2": "Message missing child device uniqueid",
            "3": "Message missing child device display name",
            "4": "Gateway device not found",
            "5": "Could not create device, something went wrong",
            "6": "Child device tag is not valid",
            "7": "Child device tag name cannot be same as Gateway device",
            "8": "Child uniqueid is already exists.",
            "9": "Child uniqueid should not exceed 128 characters"
        }
        return error[str(errorcode)]

    def has_key(self, data, key):
        try:
            return key in data
        except:
            return False
    
    def is_not_blank(self, s):
        return bool(s and s.strip())
    
    @property
    def isEdge(self):
        try:
            if self._data_json != None and self.has_key(self._data_json["meta"], "edge") and self._data_json["meta"]["edge"] != None:
                return (self._data_json["meta"]["edge"] == 1)
            else:
                return False
        except:
            return False

    @property
    def _child_template(self):
        guid=""
        if self.has_key(self._data_json["meta"],"gtw") and self.has_key(self._data_json["meta"]["gtw"],'g'):
            guid=self._data_json["meta"]["gtw"]['g']
        data={
            "mt": 221,
            "d": {
                    "g": guid,
                    "dn": "",
                    "id": "",
                    "tg": ""
                }
        }
        return data
    @property
    def hasRules(self):
        try:
            key = OPTION["rule"]
            if self._data_json != None and self.has_key(self._data_json, key) and self._data_json[key] != None:
                return len(self._data_json[key]) > 0
            else:
                return False
        except:
            return False
    
    @property
    def _timestamp(self):
        return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    
    @property
    def _time(self):
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.000")
    
    @property
    def _data_template(self):
        try:
            data = {
                "d": [],
                "dt": ""
            }
            data["dt"] = self._timestamp
            return data
        except:
            raise(IoTConnectSDKException("07", "telementry"))
    
    @property
    def _Ack_data_template(self):
        try:
            data = {
                "dt": "",
                "d": {
                    "ack": "",
                    "type": 0,
                    "st": 0,
                    "msg": "",
                }
            }
            data["dt"] = self._timestamp
            return data
        except:
            raise(IoTConnectSDKException("07", "telementry"))
    # @property
    def get_file(self):
        debug_path = os.path.join(sys.path[0], "logs")
        path_staus=os.path.exists(debug_path)
        if path_staus:
            for sub_folder in ["debug"]:
                debug_path = os.path.join(debug_path,sub_folder)                    
                path_staus=os.path.exists(debug_path)
                if path_staus:
                    pass
                else:
                    os.mkdir(debug_path)
        else:
            os.mkdir(debug_path)
            for sub_folder in ["debug"]:
                debug_path = os.path.join(debug_path,sub_folder)
                os.mkdir(debug_path)
        self._debug_output_path = os.path.join(debug_path,"info.txt")
        self._debug_error_path = os.path.join(debug_path,"error.txt")

    @property
    def _command_template(self):
        try:
            data = {
                "guid": "",
                "command": "",
                "ack": None,
                "ct": CMDTYPE["DCOMM"]
            }
            return data
        except:
            raise(IoTConnectSDKException("07", "command"))
    
    @property
    def attributes(self):
        try:
            key = OPTION["attribute"]
            if self._data_json != None and self.has_key(self._data_json, key) and self._data_json[key] != None:
                return self._data_json[key]
            else:
                return []
        except:
            raise(IoTConnectSDKException("04", "attributes"))
    
    @property
    def devices(self):
        try:
            key = OPTION["device"]
            if self._data_json != None and self.has_key(self._data_json, key) and self._data_json[key] != None:
                return self._data_json[key]
            else:
                return []
        except:
            raise(IoTConnectSDKException("04", "devices"))
    
    @property
    def rules(self):
        try:
            key = OPTION["rule"]
            if self._data_json != None and self.has_key(self._data_json, key) and self._data_json[key] != None:
                return self._data_json[key]
            else:
                return []
        except:
            raise(IoTConnectSDKException("04", "rules"))
    
    @property
    def protocol(self):
        try:
            key = OPTION["protocol"]
            if self._data_json != None and self.has_key(self._data_json, key) and self._data_json[key] != None:
                return self._data_json[key]
            else:
                return None
        except:
            raise(IoTConnectSDKException("04", "protocol"))
    
    @property
    def setting(self):
        try:
            key = OPTION["setting"]
            if self._data_json != None and self.has_key(self._data_json, key) and self._data_json[key] != None:
                return self._data_json[key]
            else:
                return None
        except:
            raise(IoTConnectSDKException("04", "protocol"))

    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, exc_tb):
        try:
            self._is_process_started = False
            for attr in self.attributes:
                if self.has_key(attr, "evaluation"):
                    attr["evaluation"].destroyed()
                    del attr["evaluation"]
            if self._client and hasattr(self._client, 'Disconnect'):
                self._is_process_started = False
                self._client.Disconnect()
        except:
            raise(IoTConnectSDKException("00", "Exit"))

    def write_debuglog(self,msg,is_error):
        if self._debug:
            if is_error:
                if self._debug_error_path:
                    with open(self._debug_error_path, "a") as dfile:
                        dfile.write(msg+'\n')
            else:
                if self._debug_output_path:
                    with open(self._debug_output_path,"a") as dfile:
                        dfile.write(msg+'\n')

    def win_user(self):
        import win32api
        import ntplib
        ntp_obj = ntplib.NTPClient()
        time_a=datetime.utcfromtimestamp(ntp_obj.request('europe.pool.ntp.org').tx_time)
        win32api.SetSystemTime(time_a.year, time_a.month, time_a.weekday(), time_a.day, time_a.hour , time_a.minute, time_a.second, 0)

    def linux_user(self):
        import ctypes
        import ctypes.util
        import time
        import ntplib

        CLOCK_REALTIME = 0
        class timespc(ctypes.Structure):
            _fields_ = [("tv_sec", ctypes.c_long),("tv_nsec", ctypes.c_long)]

        librt = ctypes.CDLL(ctypes.util.find_library("rt"))
        ts = timespc()
        ntp_obj = ntplib.NTPClient()
        time_a=datetime.fromtimestamp(ntp_obj.request('pool.ntp.org').tx_time)
        time_form=[time_a.year,time_a.month,time_a.day,time_a.hour,time_a.minute,time_a.second]
        ts.tv_sec = int(time.mktime(datetime(*time_form[:6]).timetuple()))
        ts.tv_nsec=0 * 1000000
        librt.clock_settime(CLOCK_REALTIME,ctypes.byref(ts))

    def __init__(self, uniqueId, sId,cpid,env,pf,sdkOptions=None,initCallback=None):
        self._lock = threading.Lock()

#        if sys.platform == 'win32':
#            self.win_user()
#        elif sys.platform == 'linux2':
#            self.linux_user()

        #ByPass SSL Verification
        if (not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None)):
            ssl._create_default_https_context = ssl._create_unverified_context
        
        if sdkOptions == None:
            self._property = {
            	"certificate" : None,
                "offlineStorage":
                    {
                    "disabled":False,
	                "availSpaceInMb": None,
	                "fileCount": 1
                    },
                "IsDebug":False,
                "keepalive":60
                }
        else:
            self._property = sdkOptions
        
        if initCallback:
            self._listner_callback=initCallback

        self.get_config()
        if self._debug:
            self.get_file()
        if not self.is_not_blank(sId) and not self.is_not_blank(cpid) and not self.is_not_blank(env):
            self.write_debuglog('[ERR_IN04] '+ self._time +'['+ str(sId or cpid)+'_'+ str(uniqueId)+']:'+'SId, CPID, ENV can not be blank',1)
            raise(IoTConnectSDKException("01", "SId , CPID, ENV can not be blank"))
        
        if not self.is_not_blank(uniqueId):
            self.write_debuglog('[ERR_IN05] '+ self._time +'['+ str(sId or cpid)+'_'+ str(uniqueId)+']:'+'uniqueId can not be blank',1)
            raise(IoTConnectSDKException("01", "Unique Id can not be blank"))

        if self._config == None:
            raise(IoTConnectSDKException("01", "Config settings"))
        
        self._sId = sId
        self._cpId = cpid
        self._env = env
        self._uniqueId = uniqueId
        self.pf = pf
        
        
        if "discoveryUrl" in self._property:
            if "http" not in self._property["discoveryUrl"] :
                self.write_debuglog('[ERR_IN02] '+ self._time +'['+ str(sId or cpid) +'_'+ str(uniqueId)+ "] Discovery URL can not be blank",1)
                raise(IoTConnectSDKException("01", "discoveryUrl"))
            else:
                pass
        else:
            self._property["discoveryUrl"]="https://discovery.iotconnect.io"

        if ("offlineStorage" in self._property) and ("disabled" in self._property["offlineStorage"]) and ("availSpaceInMb" in self._property["offlineStorage"]) and ("fileCount" in self._property["offlineStorage"]) :
            if  self._property["offlineStorage"]["disabled"] == False:
                self._offlineClient = offlineclient((sId or cpid)+'_'+uniqueId,self._config, self.send_offline_msg_to_broker)
                self.write_debuglog('[INFO_OS03] '+'['+ str(sId or cpid)+'_'+str(uniqueId)+"] File has been created to store offline data: "+self._time,0)
        else:
            print("offline storage is disabled...")

        if ("skipValidation" in self._property):
            if self._property["skipValidation"]:
                self._validation=False

        self._ruleEval = rule_evaluation(self.send_rule_data, self.command_sender)

        self._base_url, self._pf = self.get_base_url(self._sId)
        if self._base_url != None:
            self.write_debuglog('[INFO_IN07] '+'['+ str(self._sId or cpid)+'_'+ str(self._uniqueId) + "] BaseUrl received to sync the device information: "+ self._time ,0)
            self.process_sync("all")
            try:
                while self._is_process_started == False:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                sys.exit(0)
        else:
            self.write_debuglog('[ERR_IN08] '+ self._time +'['+ str(sId or cpid)+'_'+ str(uniqueId)+ "] Network connection error or invalid url",1)
            raise(IoTConnectSDKException("02"))
