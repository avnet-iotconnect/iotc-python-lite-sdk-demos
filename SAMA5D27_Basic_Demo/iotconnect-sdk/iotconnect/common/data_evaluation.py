import sys
import string
from datetime import datetime
import json

from iotconnect.common.infinite_timer import infinite_timer
from iotconnect.IoTConnectSDKException import IoTConnectSDKException

aggrigate_type = [
    { "name": "min", "value": 1 },
    { "name": "max", "value": 2 },
    { "name": "sum", "value": 4 },
    { "name": "avg", "value": 8 },
    { "name": "count", "value": 16 },
    { "name": "lv", "value": 32 }
]
DATATYPE = {
    "INT"     : 1,
    "LONG"    : 2,
    "FLOAT"   : 3,
    "STRING"  : 4,
    "Time"    : 5,
    "Date"    : 6,
    "DateTime": 7,
    "BIT"     : 8,
    "Boolean" : 9,
    "LatLong" : 10,
    "OBJECT"  : 12
}

class data_evaluation:
    _isEdge = False
    _attribute = None
    _data = {}
    
    def parseNum(self, x,sign):
        try:
            if type(x) == str:
                if sign and '.' in x:
                    return float(x)
                else:
                    return int(x)
            elif type(x) == int:
                return int(x)
            else:
                return float(x)
        except ValueError:
            return x
    
    def parseData(self, value,sign):
        try:
            if value != None:
                if type(value) == str:
                    value = value.rstrip()
            else:
                value = ""
            return self.parseNum(value,sign)
        except:
            return value

    def DateTimeConversion(self,value,min_value,max_value,format,r_format):
        try:
            if min_value:
                min_value=min_value.replace(" ","")
                min_value=datetime.strptime(min_value, r_format)
                min_value=int(min_value.strftime(format))
            if max_value:
                max_value=max_value.replace(" ","")
                max_value=datetime.strptime(max_value, r_format)
                max_value=int(max_value.strftime(format))
            if value:
                t_value=datetime.strptime(value, r_format)
                t_value=int(t_value.strftime(format))

            return t_value,min_value,max_value
        except Exception as ex:
            print(ex)
            return None,None,None

    def parseDateTime(self,date_time,format):
        if type(date_time) == str:
            try:
                return bool(datetime.strptime(date_time, format))
            except:
                return False
        else:
            return False
    
    def get_interval(self, config):
        try:
            tumblingWindow = ""
            if config["tw"] != None and config["tw"] != "":
                tumblingWindow = config["tw"]
            
            duration = 0
            if tumblingWindow != "":
                time = tumblingWindow[:-1]
                timetype = tumblingWindow[-1:]
                if timetype == "s":
                    duration = int(time)
                elif timetype == "m":
                    duration = int(time) * 60
                elif timetype == "h":
                    duration = int(time) * 60 * 60
                else:
                    duration = 0
            
            return duration
        except:
            return 0
    
    def twin_validate(self,dataType,validation,value):
        try:
            dataValidation=validation
            isValid = False
            if dataType == DATATYPE["INT"] or dataType == DATATYPE["LONG"]:
                value = self.parseData(value,1)
                isValid=True
                if isinstance(value, (int)) and dataType == DATATYPE["INT"] and dataValidation != None and dataValidation != "" and value >= -(2**31) and value <= (2**31):
                    isValid = False
                    vlist = dataValidation.split(",")
                    if len(vlist) > 0:
                        for v in vlist:
                            if v.find("to") > -1:
                                vRange = v.split("to")
                                if(value >= float(vRange[0].strip('')) and value <= float(vRange[1].strip(''))):
                                    isValid = True
                            elif float(value) == float(v):
                                isValid = True

                if isinstance(value, (int)) and dataType == DATATYPE["LONG"] and dataValidation != None and dataValidation != "" and value >= -(2**63) and value <= (2**63):
                    isValid = False
                    vlist = dataValidation.split(",")
                    if len(vlist) > 0:
                        for v in vlist:
                            if v.find("to") > -1:
                                vRange = v.split("to")
                                if(value >= int(vRange[0].strip('')) and value <= int(vRange[1].strip(''))):
                                    isValid = True
                            elif int(value) == int(v):
                                isValid = True
                
                # --------------------------------
            elif dataType == DATATYPE["STRING"]:
                if type(value) == str:
                    isValid = True
                if isinstance(value, str) and dataValidation != None and dataValidation != "":
                    isValid = False
                    vlist = dataValidation.split(",")
                    if len(vlist) > 0:
                        for v in vlist:
                            if v.find("to") > -1:
                                vRange = v.split("to")
                                if(value >= int(vRange[0].strip()) and value <= int(vRange[1].strip())):
                                    isValid = True
                            elif str(value) == v.strip():
                                isValid = True

            elif dataType == DATATYPE["FLOAT"]:
                value = self.parseData(value,0)
                isValid = True
                if isinstance(value, (int,float)) and dataValidation != None and dataValidation != "":
                    isValid = False
                    vlist = dataValidation.split(",")
                    if len(vlist) > 0:
                        for v in vlist:
                            if v.find("to") > -1:
                                vRange = v.split("to")
                                if(value >= float(vRange[0].strip('')) and value <= float(vRange[1].strip(''))):
                                    isValid = True
                            elif float(value) == float(v):
                                isValid = True
            
            elif dataType == DATATYPE["DateTime"]:
                isValid=self.parseDateTime(value,"%Y-%m-%dT%H:%M:%S.000Z")
                if  isValid and dataValidation != None and dataValidation != "":
                    vlist = dataValidation.split(",")
                    if len(vlist) > 0:
                        for v in vlist:
                            if v.find("to") > -1:
                                vRange = v.split("to")
                                t_value,min_value,max_value=self.DateTimeConversion(value,str(vRange[0].strip('')),str(vRange[1].strip('')),"%Y%m%d%H%M%S","%Y-%m-%dT%H:%M:%S.000Z")
                                if t_value and min_value and max_value:
                                    if( t_value >= min_value and t_value <= max_value):
                                        isValid= True
                            else:
                                t_value,min_value,_=self.DateTimeConversion(value,str(v.strip('')),0,"%Y%m%d%H%M%S","%Y-%m-%dT%H:%M:%S.000Z")
                                if t_value == min_value:
                                    isValid = True

            elif dataType == DATATYPE["Date"]:
                isValid=self.parseDateTime(value,"%Y-%m-%d")
                if  isValid and dataValidation != None and dataValidation != "":
                    vlist = dataValidation.split(",")
                    if len(vlist) > 0:
                        for v in vlist:
                            if v.find("to") > -1:
                                vRange = v.split("to")
                                t_value,min_value,max_value=self.DateTimeConversion(value,str(vRange[0].strip('')),str(vRange[1].strip('')),"%Y%m%d","%Y-%m-%d")
                                if t_value and min_value and max_value:
                                    if( t_value >= min_value and t_value <= max_value):
                                        isValid= True
                            else:
                                t_value,min_value,_=self.DateTimeConversion(value,str(v.strip('')),0,"%H%M%S","%Y-%m-%d")
                                if t_value == min_value:
                                    isValid = True

            elif dataType == DATATYPE["Time"]:
                isValid=self.parseDateTime(value,"%H:%M:%S")
                if  isValid and dataValidation != None and dataValidation != "":
                    vlist = dataValidation.split(",")
                    if len(vlist) > 0:
                        for v in vlist:
                            if v.find("to") > -1:
                                vRange = v.split("to")
                                t_value,min_value,max_value=self.DateTimeConversion(value,str(vRange[0].strip('')),str(vRange[1].strip('')),"%H%M%S","%H:%M:%S")
                                if t_value and min_value and max_value:
                                    if( t_value >= min_value and t_value <= max_value):
                                        isValid= True
                            else:
                                t_value,min_value,_=self.DateTimeConversion(value,str(v.strip('')),0,"%H%M%S","%H:%M:%S")
                                if t_value == min_value:
                                    isValid = True

            elif dataType == DATATYPE["BIT"]:
                if type(value) == int and (value == 0 or value == 1):
                    isValid = True
                if dataValidation != None and dataValidation != "":
                    isValid = False
                    vlist = dataValidation.split(",")
                    if len(vlist) > 0:
                        for v in vlist:
                            if value == int(v):
                                isValid = True

            elif dataType == DATATYPE["Boolean"]:
                if type(value) == bool and (value == True or value == False):
                    isValid = True
                if dataValidation != None and dataValidation != "":
                    isValid = False
                    vlist = dataValidation.split(",")
                    if len(vlist) > 0:
                        for v in vlist:
                            if v == "true" or v == "True":
                                v=True
                            elif v == "false" or v == "False":
                                v=False
                            try:    
                                if value == bool(v):
                                    isValid = True
                            except:
                                isValid = False
            return isValid
        except:
            raise(IoTConnectSDKException("09","dataevaluation"))

    @classmethod
    def twin_validate_data(cls,dataType,validation,value):
        return cls.twin_validate(dataType,validation,value)

    def process_data(self, config, parent, value,do_validation):
        try:
            key = self.get_data_key(config, parent)
            if self.has_key(self._data, key) == False:
                return None
            
            _config = self._data[key]
            dataType = _config["dt"]
            dataValidation = _config["dv"]
            isValid = False
            if do_validation:
                # --------------------------------
                if dataType == DATATYPE["INT"] or dataType == DATATYPE["LONG"]:
                    value = self.parseData(value,1)
                    isValid=True
                    if isinstance(value, (int)) and dataType == DATATYPE["INT"] and value >= -(2**31) and value <= (2**31):
                        if dataValidation != None and dataValidation != "":
                            isValid = False
                            vlist = dataValidation.split(",")
                            if len(vlist) > 0:
                                for v in vlist:
                                    if v.find("to") > -1:
                                        vRange = v.split("to")
                                        if(value >= float(vRange[0].strip('')) and value <= float(vRange[1].strip(''))):
                                            isValid = True
                                    elif float(value) == float(v):
                                        isValid = True

                    elif isinstance(value, (int)) and dataType == DATATYPE["LONG"] and value >= -(2**63) and value <= (2**63):
                        if dataValidation != None and dataValidation != "":
                            isValid = False
                            vlist = dataValidation.split(",")
                            if len(vlist) > 0:
                                for v in vlist:
                                    if v.find("to") > -1:
                                        vRange = v.split("to")
                                        if(value >= int(vRange[0].strip('')) and value <= int(vRange[1].strip(''))):
                                            isValid = True
                                    elif int(value) == int(v):
                                        isValid = True
                    else:
                        isValid = False
                    # --------------------------------
                elif dataType == DATATYPE["STRING"]:
                    if type(value) == str:
                        isValid = True
                    if isinstance(value, str) and dataValidation != None and dataValidation != "":
                        isValid = False
                        vlist = dataValidation.split(",")
                        if len(vlist) > 0:
                            for v in vlist:
                                if v.find("to") > -1:
                                    vRange = v.split("to")
                                    if(value >= int(vRange[0].strip()) and value <= int(vRange[1].strip())):
                                        isValid = True
                                elif str(value) == v.strip():
                                    isValid = True

                elif dataType == DATATYPE["FLOAT"]:
                    value = self.parseData(value,0)
                    isValid = True
                    if isinstance(value, (int,float)): 
                        if dataValidation != None and dataValidation != "":
                            isValid = False
                            vlist = dataValidation.split(",")
                            if len(vlist) > 0:
                                for v in vlist:
                                    if v.find("to") > -1:
                                        vRange = v.split("to")
                                        if(value >= float(vRange[0].strip('')) and value <= float(vRange[1].strip(''))):
                                            isValid = True
                                    elif float(value) == float(v):
                                        isValid = True
                    else:
                        isValid = False
                elif dataType == DATATYPE["DateTime"]:
                    isValid=self.parseDateTime(value,"%Y-%m-%dT%H:%M:%S.000Z")
                    if  isValid and dataValidation != None and dataValidation != "":
                        vlist = dataValidation.split(",")
                        if len(vlist) > 0:
                            for v in vlist:
                                if v.find("to") > -1:
                                    vRange = v.split("to")
                                    t_value,min_value,max_value=self.DateTimeConversion(value,str(vRange[0].strip('')),str(vRange[1].strip('')),"%Y%m%d%H%M%S","%Y-%m-%dT%H:%M:%S.000Z")
                                    if t_value and min_value and max_value:
                                        if( t_value >= min_value and t_value <= max_value):
                                            isValid= True
                                else:
                                    t_value,min_value,_=self.DateTimeConversion(value,str(v.strip('')),0,"%Y%m%d%H%M%S","%Y-%m-%dT%H:%M:%S.000Z")
                                    if t_value == min_value:
                                        isValid = True

                elif dataType == DATATYPE["Date"]:
                    isValid=self.parseDateTime(value,"%Y-%m-%d")
                    if  isValid and dataValidation != None and dataValidation != "":
                        vlist = dataValidation.split(",")
                        if len(vlist) > 0:
                            for v in vlist:
                                if v.find("to") > -1:
                                    vRange = v.split("to")
                                    t_value,min_value,max_value=self.DateTimeConversion(value,str(vRange[0].strip('')),str(vRange[1].strip('')),"%Y%m%d","%Y-%m-%d")
                                    if t_value and min_value and max_value:
                                        if( t_value >= min_value and t_value <= max_value):
                                            isValid= True
                                else:
                                    t_value,min_value,_=self.DateTimeConversion(value,str(v.strip('')),0,"%H%M%S","%Y-%m-%d")
                                    if t_value == min_value:
                                        isValid = True

                elif dataType == DATATYPE["Time"]:
                    isValid=self.parseDateTime(value,"%H:%M:%S")
                    if  isValid and dataValidation != None and dataValidation != "":
                        vlist = dataValidation.split(",")
                        if len(vlist) > 0:
                            for v in vlist:
                                if v.find("to") > -1:
                                    vRange = v.split("to")
                                    t_value,min_value,max_value=self.DateTimeConversion(value,str(vRange[0].strip('')),str(vRange[1].strip('')),"%H%M%S","%H:%M:%S")
                                    if t_value and min_value and max_value:
                                        if( t_value >= min_value and t_value <= max_value):
                                            isValid= True
                                else:
                                    t_value,min_value,_=self.DateTimeConversion(value,str(v.strip('')),0,"%H%M%S","%H:%M:%S")
                                    if t_value == min_value:
                                        isValid = True

                elif dataType == DATATYPE["BIT"]:
                    if type(value) == int and (value == 0 or value == 1):
                        isValid = True
                    if dataValidation != None and dataValidation != "":
                        isValid = False
                        vlist = dataValidation.split(",")
                        if len(vlist) > 0:
                            for v in vlist:
                                if value == int(v):
                                    isValid = True

                elif dataType == DATATYPE["Boolean"]:
                    if type(value) == bool and (value == True or value == False):
                        isValid = True
                    if dataValidation != None and dataValidation != "":
                        isValid = False
                        vlist = dataValidation.split(",")
                        if len(vlist) > 0:
                            for v in vlist:
                                if v == "true" or v == "True":
                                    v=True
                                elif v == "false" or v == "False":
                                    v=False
                                try:    
                                    if value == bool(v):
                                        isValid = True
                                except:
                                    isValid = False
                elif dataType == DATATYPE["LatLong"] and value != None and type(value) == list:
                    if len(value) == 2:
                        isValid = True
                    else:
                        isValid = False
            else:
                isValid=True        
                # --------------------------------
            # --------------------------------
            if self._isEdge:
                if isValid and (dataType == DATATYPE["INT"] or dataType == DATATYPE["LONG"] or dataType == DATATYPE["FLOAT"]) and self.has_key(_config, "values"):
                    value=self.parseNum(value,1)
                    if type(value) != str:
                        _config["values"].append(value)
                        _config["current_value"] = value
                else:
                    data = {}
                    data[_config["ln"]] = value
                    return {"FLT": data}        
            
            if self._isEdge == False:
                data = {}
                if isValid:
                    data[_config["ln"]] = value
                    return {"RPT": data}
                else:
                    data[_config["ln"]] = value
                    return {"FLT": data}
            else:
                return None
        except:
            raise(IoTConnectSDKException("09","dataevaluation"))
    
    def callBackTimer(self, arg):
        self.process_edge_data(arg["key"], arg["p"], arg["tg"])
    
    def data_count(self, values):
        try:
            return len(values)
        except:
            return 0
    
    def data_min(self, values):
        try:
            if len(values) > 0:
                return min(values)
            else:
                return None
        except:
            return None
    
    def data_max(self, values):
        try:
            if len(values) > 0:
                return max(values)
            else:
                return None
        except:
            return None
    
    def data_avg(self, values):
        try:
            if len(values) > 0:
                return sum(values) / len(values)
            else:
                return None
        except:
            return None
    
    def data_sum(self, values):
        try:
            if len(values) > 0:
                return sum(values)
            else:
                return None
        except:
            return None
    
    def data_lv(self, values):
        try:
            if len(values) > 0:
                return values[len(values) - 1]
            else:
                return None
        except:
            return None
    
    def process_aggregate(self, config):
        values = []
        if self.has_key(config, "values") and len(config["values"]) > 0:
            values = config["values"]
        
        if len(values) == 0:
            return None

        final = []
        #final.append(int(agg_type))
        for atype in aggrigate_type:
            value = atype["value"]
            name = atype["name"]
            if value:
                final.append(getattr(self, 'data_%s' % name)(values))
        
        return final
    
    def process_edge_data(self, key, p, tg):
        edgeData = []
        final = {}
        try:
            if key == "1":
                final[p] = {}
                for config in self._data:
                    ln = self._data[config]["ln"]
                    data = self.process_aggregate(self._data[config])
                    if data != None:
                        final[p][ln] = data
                    self._data[config]["values"] = []
                if len(final[p]) > 0:
                        pass
                else:
                    final={} 
            else:
                for config in self._data:
                    if config == key:
                        ln = self._data[config]["ln"]
                        data = self.process_aggregate(self._data[config])
                        if data != None:
                            final[ln] = data
                        self._data[config]["values"] = []       
        except:
            print("Error while process aggregate...")
        if len(final) > 0:
            #edgeData.append(final)
            attr_data = { "tg": tg, "d": final}
            if self.listner_callback:
                self.listner_callback(attr_data)

    def reset_get_rule_data(self):
        for i in range(0,len(self._attribute["d"])):
            self._attribute["d"][i]['current_value']=None

    def get_rule_data(self):
        try:
            if self._isEdge == False:
                return None
            
            obj = {
                "p": self._attribute["p"],                
                "st": "",
                "d": []
            }
            for data in self._attribute["d"]:
                if data["current_value"] != None :
                    child = {                    
                        "ln": data["ln"],
                        "v": data["current_value"],
                        "tg":data["tg"] if "tg" in data else ""
                    }
                    obj["d"].append(child)
            return obj
        except:
            return None
    
    def destroyed(self):
        try:
            if self.listner_callback != None:
                self.listner_callback = None
            
            if self._data != None:
                del(self._data)
            
            if self._timer != None and len(self._timer) > 0:
                for timer in self._timer:
                    timer.cancel()
                del(self._timer)
        except:
            print("Error while destroyed data evalution")
    
    def get_data_key(self, config, parent):
        try:
            if parent == "":
                if self.has_key(config,"tg"):
                    return config["ln"] + config["tg"]
                else:
                    return config["ln"]
            else:
                if self.has_key(config,"tg"):
                    return parent + config["ln"] + config["tg"]
                else:
                    return parent + config["ln"]
        except:
            return "-1"
    
    def has_key(self, data, key):
        try:
            return key in data
        except:
            return False
    
    @property
    def _timestamp(self):
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    
    def __init__(self, isEdge, attribute, listner):
        self._data = {}
        self._isEdge = isEdge
        self._attribute = json.loads(json.dumps(attribute))
        self._timer = []
        
        if listner != None:
            self.listner_callback = listner
        
        name = self._attribute["p"]
        for data in self._attribute["d"]:
            key = self.get_data_key(data, name)
            self._data[key] = data
            if self._isEdge:
                self._data[key]["values"] = []
                self._data[key]["current_value"] = None
                if name == "":
                    self._data[key]["name"] = data["ln"]
                else:
                    self._data[key]["name"] = name + "." + data["ln"]
        
        if self._isEdge:
            if name != "":
                _key = "1"
                _tg = self._attribute["tg"] if self.has_key(self._attribute,"tg") else ""
                _p = str(self._attribute["p"])
                for data_att in self._attribute["d"]:
                    _interval = self.get_interval(data_att)
                if _interval > 0:
                    _timer = infinite_timer(_interval, self.callBackTimer, [{ "key": _key, "p": _p, "tg": _tg }])
                    _timer.start()
                    self._timer.append(_timer)
                else:
                    raise(IoTConnectSDKException("08", name))
            else:
                _p = ""
                for _key in self._data:
                    _key = str(_key)
                    tg= self._data[_key]["tg"] if self.has_key(self._data[_key],"tg") else ""
                    _tg = tg
                    _interval = self.get_interval(self._data[_key])
                    if _interval > 0:
                        _timer = infinite_timer(_interval, self.callBackTimer, [{ "key": _key, "p": _p, "tg": _tg }])
                        _timer.start()
                        self._timer.append(_timer)
                    else:
                        raise(IoTConnectSDKException("08", _key))
