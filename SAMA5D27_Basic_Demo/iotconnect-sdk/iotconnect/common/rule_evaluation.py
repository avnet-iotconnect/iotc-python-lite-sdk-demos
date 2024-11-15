import sys
import copy
import time
from datetime import datetime

class rule_evaluation:    
    _command_sender = None
    
    def replace_conditional_operator(self, condition):
        try:
            condition = condition.replace(" = ", " == ")
            condition = condition.replace("AND", "and")
            condition = condition.replace("OR", "or")
            return condition
        except Exception as ex:
            print("replace_operator : " + ex)
            return condition
            
    def eval_exp(self,exp):
        try:
            return eval(exp)
        except Exception as ex:
            return False
    
    def evalRules(self, rule, rule_data):
        try:
            if rule == None:
                return
            f_condition = ''
            condition = ""
            if self.has_key(rule, "con") and rule["con"] != None:
                condition = self.replace_conditional_operator(str(rule["con"]))
            
            command_text = ""
            if self.has_key(rule, "cmd") and rule["cmd"] != None:
                command_text = str(rule["cmd"])

            full_data={}
            if condition != "":
                for rdata in rule_data:
                    rdata["valid"] = None
                    d = {}
                    pdata={}
                    Prnt=''
                    for data in rdata["d"]:
                        if rdata["p"] == "":
                            prop = data["ln"]
                            full_data[data["ln"]] = data["v"]
                        else:
                            prnt=rdata["p"]
                            pdata[data["ln"]]=data["v"]
                            prop = rdata["p"] + "." + data["ln"]

                        if (condition.find(str(prop)) > -1) and (data["v"] != None) and (condition.find(str(data['tg'])) > -1) :
                            if "." in condition and "." in prop:
                                f_condition=condition[condition.find(str(prop)):]
                                f_condition = f_condition.replace(prop, str(data["v"]))
                                d[data["ln"]] = data["v"]
                            elif ("." not in condition) and ("." not in prop):
                                f_condition=condition[condition.find(str(prop)):]
                                f_condition = f_condition.replace(prop, str(data["v"]))
                                d[data["ln"]] = data["v"]
                    
                    if len(pdata) > 0:
                        full_data[prnt]=pdata

                    if len(d) > 0:
                        rdata["valid"] = d
                
                if self.eval_exp(f_condition) == True:
                    print("\n---- Rule Matched ---")
                    if self._command_sender and command_text != "":
                        self._command_sender(command_text,rule)

                    sdata = {}
                    for rdata in rule_data:
                        if rdata["valid"] != None and len(rdata["valid"]) > 0:
                            if rdata["p"] =='':
                                sdata["cv"]=rdata["valid"]
                            else:
                                d={}
                                d[rdata["p"]]=rdata["valid"]
                                sdata["cv"]=d
                                
                    if len(sdata) > 0:
                        sdata["d"]=full_data
                        sdata["rg"] = rule["g"]
                        sdata["ct"] = rule["con"]
                        sdata["sg"] = rule["es"]
                        #sdata["id"] = rule["id"]
                        sdata["dt"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
                        if self.listner_callback != None:
                            self.listner_callback(sdata)
                else:
                    # print("\n---- Rule Not Matched ---")
                    pass
        except Exception as ex:
            print("evalRules : " + ex)
    
    def has_key(self, data, key):
        try:
            return key in data
        except :
            return False
    
    @property
    def _timestamp(self):
        return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
    
    def __init__(self, listner, command_sender):
        if listner != None:
            self.listner_callback = listner
        
        if command_sender != None:
            self._command_sender = command_sender
