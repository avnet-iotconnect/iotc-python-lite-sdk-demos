import sys
import os
import ssl as ssl
import paho.mqtt.client as mqtt
import json
import time
from iotconnect.IoTConnectSDKException import IoTConnectSDKException

authType = {
	"KEY": 1,
	"CA_SIGNED": 2,
	"CA_SELF_SIGNED": 3,
    "SKEY": 5,
	"CA_ind": 7
    
}


class mqttclient:
    _name = None
    _auth_type = None
    _sdk_config = None
    _config = None
    _subTopic = None
    _pubTopic = None
    _pubACK=None
    _pubOfline=None
    _pubRpt=None
    _pubERpt=None
    _pubFlt=None
    _pubHB=None
    _pubERm=None
    _pubDL=None
    _pubDi=None
    _twin_pub_topic = None
    _twin_sub_topic = None
    _twin_sub_res_topic = None
    _client = None
    _keepalive = 60
    _onMessage = None
    _onTwinMessage = None
    _isConnected = False
    _rc_status = None
    _path_to_root_cert=None
    _onDirectMethod=None
    _direct_sub="$iothub/methods/POST/#"
    _direct_pub_res_topic="$iothub/methods/res/{status}/?$rid={request id}"
    _mqtt_status = {
        0: "MQTT: Connection successful",
        1: "MQTT: Connection refused - incorrect protocol version",
        2: "MQTT: Connection refused - invalid client identifier",
        3: "MQTT: Connection refused - server unavailable",
        4: "MQTT: Connection refused - bad username or password",
        5: "MQTT: Connection refused - not authorised"
    }

    class disconnect_msg:
        payload=u'{"ct": 116,"data": {"guid": "","uniqueId":"_uniqueId","command": "False","ack": "False","ackId": "","ct": 116}}'
    class connect_msg:
        payload=u'{"ct": 116,"data": {"guid": "","uniqueId":"_uniqueId","command": "True","ack": "False","ackId": "","ct": 116}}'

    def _on_connect(self, mqtt_self, client, userdata, rc):
        if rc != 0:
            self._isConnected = False
        else:
            self._isConnected = True
            msg =self.connect_msg()
            msg_data=json.loads(msg.payload)
            self._onMessage(msg_data)

        if self._isConnected and mqtt_self:
            mqtt_self.subscribe(self._subTopic)
            mqtt_self.subscribe(self._twin_sub_topic)
            mqtt_self.subscribe(self._twin_sub_res_topic)
            if self._config["pf"] == "az":
                mqtt_self.subscribe(self._direct_sub)
        self._rc_status = rc
    
    # old
    # def _on_disconnect(self, client, userdata,rc=0):
    #     self._rc_status = rc
    #     msg=self.disconnect_msg()
    #     msg_data=json.loads(msg.payload)
    #     self._onMessage(msg_data)
    #     self._isConnected = False
    #     self._client.loop_stop()

    # change with Python 3.0.4 SDK
    def _on_disconnect(self, client, userdata,rc=0):
        self._rc_status = rc
        self._isConnected = False
        if self._client != None:
            self._client.loop_stop()
        msg=self.disconnect_msg()
        msg_data=json.loads(msg.payload)
        self._onMessage(msg_data)
        

    def get_twin(self):
        if self._isConnected:
            # print("_twin_pub_res_topic")
            self._client.publish(self._twin_pub_res_topic, payload="", qos=1)

    def has_key(self, data, key):
        try:
            return key in data
        except:
            return False

    def _on_message(self, client, userdatam, msg):
        if self.has_key("payload", msg) == False and msg.payload == None:
            return
        else:
            msg_data = msg.payload.decode("utf-8")
            if msg_data == None or len(msg_data) == 0:
                return
        msg_data=json.loads(msg_data)
        if msg.topic.find(self._subTopic[:-1]) > -1 and self._onMessage != None:
            self._onMessage(msg_data)
        if msg.topic.find(self._twin_sub_topic[:-1]) > -1 and self._onTwinMessage != None:
            # print ("_twin_sub_topic")
            print(msg_data)
            self._onTwinMessage(msg_data,1)
        if msg.topic.find(self._twin_sub_res_topic[:-1]) > -1:
            # print ("twin_sub_res_topic")
            print(msg_data)
            self._onTwinMessage(msg_data,0)
        if msg.topic.find(self._direct_sub[:-1]) > -1 and self._onDirectMethod != None:
            method=str(msg.topic.replace(self._direct_sub[:-1],''))
            leng=method.find('/')
            method=method.replace(method[leng:],'')
            #print(method)
            leng=msg.topic.find("rid=")
            if leng > -1:
                rid=msg.topic[leng+4:]
                rid=str(rid)
                self._onDirectMethod(msg_data,method,rid)    

    def _connect(self):
        try:
            try:
                if self._isConnected == False:
                    self._client.connect(self._config["h"], self._config["p"], self._keepalive)
                    self._client.loop_start()
            except Exception as ex:
                self._rc_status = 5
            
            while self._rc_status == None:
                time.sleep(0.5)
            
            if self._rc_status == 0:
                print("\n____________________\n\nProtocol Initialized\nDevice Is Connected with IoTConnect\n____________________\n")
                # print("Device Is Connected with IoTConnect\n")
            else:
                raise(IoTConnectSDKException("06", self._mqtt_status[self._rc_status]))
        except Exception as ex:
            return False
            #raise ex
    
    def _validateSSL(self, certificate):
        is_valid_path = True
        if certificate == None:
            raise(IoTConnectSDKException("01", "Certificate info"))
        
        for prop in certificate:
            if os.path.isfile(certificate[prop]) == False:
                is_valid_path = False
        
        if is_valid_path:
            return certificate
        else:
            raise(IoTConnectSDKException("05"))
    
    def Disconnect(self):
        try:
            if self._client != None:
                self._client.disconnect()
                self._client.loop_stop()
                while self._isConnected == True:
                    time.sleep(1)
                    self._isConnected = False
                self._client = None
            self._rc_status = None
        except:
            self._client = None
            self._rc_status = None
    
    def send_HB(self):
        try:
            data="{}"
            _obj=None
            if self._isConnected:
                if self._client and self._pubHB != None:
                    _obj = self._client.publish(self._pubHB, payload=data)
            if _obj and _obj.rc == 0:
                return True
            else:
                return False
        except:
            return False

    def Send(self,data,msgtype):
        try:
            _obj = None
            pubtopic=None
            if self._isConnected:
                if msgtype == "RPTEDGE":
                    print(data)
                    pubtopic=self._pubERpt
                elif msgtype == "RMEdge":
                    pubtopic=self._pubERm
                elif msgtype == "CMD_ACK" or msgtype == "FW":
                    pubtopic=self._pubACK
                elif msgtype == "OD":
                    pubtopic=self._pubOfline
                elif msgtype ==  "RPT":
                    pubtopic=self._pubRpt
                elif msgtype == "DL":
                    pubtopic=self._pubDL
                elif msgtype == "Di":
                    pubtopic=self._pubDi
                else:
                    pubtopic=self._pubFlt

                if self._client and pubtopic != None:
                    if pubtopic == self._pubACK:
                        _obj = self._client.publish(pubtopic, payload=json.dumps(data),qos=0)
                        return True
                    else:
                        _obj = self._client.publish(pubtopic, payload=json.dumps(data),qos=0)
                        if sys.version_info >=(3,5):
                            _obj.wait_for_publish(timeout=2)
                        else:
                            time.sleep(0.2)
                            while(_obj._published==False):
                                if count == 5:
                                    break
                                time.sleep(1)
                                count+=1
                        if _obj and _obj._published == True:
                            return True
                        else:
                            return False
            # if _obj and _obj.rc == 0:
            #     return True
            else:
                return False
        except:
            return True
    
    def SendTwinData(self, data):
        try:
            _obj = None
            if self._isConnected:
                # print("_twin_pub_topic")
                print(data)
                if self._client and self._twin_pub_topic != None:
                    _obj = self._client.publish(self._twin_pub_topic, payload=json.dumps(data), qos=1)
            
            if _obj and _obj.rc == 0:
                return True
            else:
                return False
        except:
            return False

    def SendDirectData(self,data,status,requestId):
        try:
            if self._isConnected:
                if self._direct_pub_res_topic:
                    self._direct_pub_res_topic=self._direct_pub_res_topic.replace("{status}", status)
                    self._direct_pub_res_topic=self._direct_pub_res_topic.replace("{request id}",requestId)
                    obj=self._client.publish(self._direct_pub_res_topic, payload=json.dumps(data))
                    #print(obj)
        except:
            return False

    def _init_mqtt(self):
        try:
            self.Disconnect()
            self._client = mqtt.Client(client_id=self._config['id'], clean_session=True, userdata=None, protocol=mqtt.MQTTv311)
            #Check Auth Type
            if (self._auth_type == authType["KEY"]) or (self._auth_type == authType["SKEY"]):
                if self._config['pf'] == "az":
                    self._client.username_pw_set(self._config["un"], self._config["pwd"])
                if self._path_to_root_cert != None:
                    self._client.tls_set(self._path_to_root_cert, tls_version = ssl.PROTOCOL_TLSv1_2)
            elif (self._auth_type == authType["CA_SIGNED"] or self._auth_type == authType["CA_ind"]) :
                if self._config['pf'] == "az":
                    self._client.username_pw_set(self._config["un"], password=None)
                cert_setting = self._validateSSL(self._sdk_config["certificate"])
                if len(cert_setting) != 3:
                    raise(IoTConnectSDKException("01", "Certificate/Key in Sdkoption"))
                if cert_setting != None:
                    if self._path_to_root_cert != None:
                        self._client.tls_set(self._path_to_root_cert, certfile=str(cert_setting["SSLCertPath"]), keyfile=str(cert_setting["SSLKeyPath"]), cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)
                    else:
                        self._client.tls_set(str(cert_setting["SSLCaPath"]), certfile=str(cert_setting["SSLCertPath"]), keyfile=str(cert_setting["SSLKeyPath"]), cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)    
                    self._client.tls_insecure_set(False)
            elif self._auth_type == authType["CA_SELF_SIGNED"]:
                if self._config['pf'] == "az":
                    self._client.username_pw_set(self._config["un"], password=None)
                cert_setting = self._validateSSL(self._sdk_config["certificate"])
                if len(cert_setting) != 3:
                    raise(IoTConnectSDKException("01", "Certificate/Key in Sdkoption"))
                if cert_setting != None:
                    if self._path_to_root_cert != None:
                        self._client.tls_set(self._path_to_root_cert, certfile=str(cert_setting["SSLCertPath"]), keyfile=str(cert_setting["SSLKeyPath"]), cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)
                    else:
                        self._client.tls_set(str(cert_setting["SSLCaPath"]), certfile=str(cert_setting["SSLCertPath"]), keyfile=str(cert_setting["SSLKeyPath"]), cert_reqs=ssl.CERT_REQUIRED, tls_version=ssl.PROTOCOL_TLSv1_2, ciphers=None)
                    self._client.tls_insecure_set(False)
            self._client.on_connect = self._on_connect
            self._client.on_disconnect = self._on_disconnect
            self._client.on_message = self._on_message
            self._client.disable_logger()
            if self._client != None:
                if (self._connect()!= None):
                    _path = os.path.abspath(os.path.dirname(__file__))
                    _config_path = os.path.join(_path, "assets/DigiCertGlobalRootG2.txt")
                    _config_path=_config_path.replace("client","")
                    self._path_to_root_cert=_config_path
                    self._init_mqtt()                   
                else:
                    print ("IoTConnect Python 2.1 SDK(Release Date: 24 December 2022) will connect with -> Microsoft Azure Cloud <-")


        except Exception as ex:
            raise ex
    
    @property
    def isConnected(self):
        return self._isConnected
    
    @property
    def name(self):
        return self._config["n"]
    
    def __init__(self, auth_type, config, sdk_config, onMessage,onDirectMethod,onTwinMessage = None):
        
        self._auth_type = auth_type
        self._config = config
        self._sdk_config = sdk_config
        self._keepalive= sdk_config["keepalive"] if "keepalive" in sdk_config else 60
        self._onMessage = onMessage
        self._onTwinMessage = onTwinMessage
        self._onDirectMethod=onDirectMethod
        self._subTopic = str(config['topics']['c2d'])
        self._pubACK = str(config['topics']['ack'])
        self._pubOfline=str(config['topics']['od'])
        self._pubRpt=str(config['topics']['rpt'])
        if 'erpt' in config['topics']:
            self._pubERpt=str(config['topics']['erpt'])
            self._pubERm=str(config['topics']['erm'])
        self._pubFlt=str(config['topics']['flt'])
        self._pubHB=str(config['topics']['hb'])
        self._pubDL=str(config['topics']['dl'])
        self._pubDi=str(config['topics']['di'])
        platfrom = config["pf"]
        # print (platfrom)
        if config["pf"] == "az":
            print ("\n============>>>>>>>>>>>\n")
            print ("IoTConnect Python 2.1 SDK(Release Date: 24 December 2022) will connect with -> Microsoft Azure Cloud <-")
            print ("\n<<<<<<<<<<<============\n")
            self._twin_pub_topic = str(sdk_config['az']['twin_pub_topic'])
            self._twin_sub_topic = str(sdk_config['az']['twin_sub_topic'])
            self._twin_sub_res_topic = str(sdk_config['az']['twin_sub_res_topic'])
            self._twin_pub_res_topic = str(sdk_config['az']['twin_pub_res_topic'])
            _path = os.path.abspath(os.path.dirname(__file__))            
            _config_path = os.path.join(_path, "assets/az_crt.txt")
            #_config_path = os.path.join(_path, "assets/DigiCertGlobalRootG2.txt")
            _config_path=_config_path.replace("client","")
            self._path_to_root_cert=_config_path
        else:
            print ("\n============>>>>>>>>>>>\n")
            print ("IoTConnect Python 2.1 SDK(Release Date: 24 December 2022) will connect with -> AWS Cloud <-")
            print ("\n<<<<<<<<<<<============\n")
            cpid_uid = (config["id"])
            self._twin_pub_topic = str(sdk_config['aws']['twin_pub_topic']) 
            # print (type(self._twin_pub_topic))
            self._twin_pub_topic = self._twin_pub_topic.replace("{Cpid_DeviceID}", cpid_uid) # to publish desired twin/shadow from d2c
            # print (type(self._twin_pub_topic))
            self._twin_sub_topic = str(sdk_config['aws']['twin_sub_topic'])
            self._twin_sub_topic = self._twin_sub_topic.replace("{Cpid_DeviceID}", cpid_uid)
            self._twin_sub_res_topic = str(sdk_config['aws']['twin_sub_res_topic'])
            self._twin_sub_res_topic = self._twin_sub_res_topic.replace("{Cpid_DeviceID}", cpid_uid)
            self._twin_pub_res_topic = str(sdk_config['aws']['twin_pub_res_topic'])
            self._twin_pub_res_topic = self._twin_pub_res_topic.replace("{Cpid_DeviceID}", cpid_uid)
            # _path = os.path.abspath(os.path.dirname(__file__))            
            # _config_path = os.path.join(_path, "assets/aws_crt.txt")
            # _config_path=_config_path.replace("client","")
            # self._path_to_root_cert=_config_path 
            # pass   
        self._init_mqtt()
