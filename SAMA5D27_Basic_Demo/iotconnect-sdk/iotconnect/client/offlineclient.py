import sys, os
import json
import datetime
import math
import time
import threading
from threading import Timer
from iotconnect.IoTConnectSDKException import IoTConnectSDKException
import shutil

class offlineclient:
    _data_path = None
    _sdk_config = None
    _lock = False
    data_rate = False
    is_timer_start=True

    def Send(self, data):
        if self._file_size == 0:
            print("\nFile Size not found")
            return
        _data = json.dumps(data) + "\n"
        self._data_path = self.new_active_file(self._data_path) 
        if self._data_path:
            try:
                with open(self._data_path, "a") as dfile:
                    dfile.write(_data)
            except:
                return False
        return True

    def data_frq(self):
        self.data_rate = True

    def start_timer(self,timer_value):
        thread = Timer(timer_value, self.data_frq)
        thread.name = "DR"
        thread.start()
        self.is_timer_start = False

    def send_back_to_client(self):
        try:
            #self._lock = False
            #return
            time.sleep(1)
            count=0
            freqency=10
            total_count=0
            #log_path = os.path.join(sys.path[0], "logs")
            files = self.get_log_files()
            files.sort()
            self.is_timer_start= True
            self.data_rate=False
            if len(files) > 0:
                for f in files:
                    count=0
                    isAction = 0
                    logs = self.read_file_data(f)
                    print("\nstart Publishing offline file : " + str(f))
                    dummy=logs
                    rData=[]
                    if len(logs) > 0:
                        rData = []
                        for obj in logs:
                            isSend = False
                            if self.sendBackToClient != None:
                                isSend = self.sendBackToClient(obj)
                            if isSend == False:
                                rData.append(obj)
                            else:
                                count=count+1
                                total_count=total_count+1
                            if self.is_timer_start:
                                self.start_timer(freqency)
                            if (self.data_rate == True) and (count > 0):
                                print("\nPublish offline data : " + str(count)+" "+ datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.000"))
                                self.write_file(f,dummy[count:])
                                dummy=dummy[count:]
                                count = 0
                                self.data_rate=False
                                self.is_timer_start=True
                                files = self.get_log_files()
                                files.sort()
                                #time.sleep(freqency)        
                    if len(rData) > 0:
                        isAction = 1             
                    if isAction == 0: #DELETE
                        #print("\nPublish total offline data : " + str(count) +"  Time:"+ datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.000"))
                        self.delete_file(f)
                    if isAction == 1: #WRITE
                        self.write_file(f, rData)
                print ("\n---------------------------------")
                print("Publish offline data total : " + str(total_count) +"  Time:"+ datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.000"))
                print ("---------------------------------\n")
            self._lock = False
        except:
            self._lock = False
    
    def PublishData(self):
        if self._lock == False:
            self._lock = True
            p_thread=None
            p_thread=threading.Thread(target = self.send_back_to_client, args = [])
            p_thread.setName("send_data")
            p_thread.daemon = True
            p_thread.start()
            #self.send_back_to_client()
    
    def get_active_file(self):
        try:
            data_path = None
            log_path = os.path.join(sys.path[0], "logs")
            path_staus=os.path.exists(log_path)
            if path_staus:
                for sub_folder in ["offline",self._cpid_uniqid]:
                    log_path = os.path.join(log_path,sub_folder)
                    path_staus=os.path.exists(log_path)
                    if path_staus:
                        files = os.listdir(log_path)
                        for f in files:
                            if f != self._cpid_uniqid:
                                if os.path.isdir(log_path+"\\"+f):
                                    shutil.rmtree(log_path+"\\"+f)
                    else:
                        os.mkdir(log_path)                        
            else:
                os.mkdir(log_path)
                for sub_folder in ["offline",self._cpid_uniqid]:
                    log_path = os.path.join(log_path,sub_folder)
                    os.mkdir(log_path)
            files = os.listdir(log_path)
            if len(files) > 0:
                for f in files:
                    if f.startswith("active"):
                        fpath = os.path.join(sys.path[0] + "/logs/offline/"+self._cpid_uniqid, f)
                        fsize = round(self.convert_unit(float(os.stat(fpath).st_size), self._file_unit), 2)
                        if fsize < self._file_size or self._file_size == 1:
                            data_path = fpath
                        else:
                            os.rename(fpath, os.path.join(sys.path[0] + "/logs/offline/"+self._cpid_uniqid, f.replace("active_", "")))
            if data_path == None:
                data_path = os.path.join(sys.path[0], "logs/offline/"+self._cpid_uniqid+"/active_" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".txt")
            #Remove first file if size limit exceed 
            self.remove_first_file()
            return data_path
        except Exception as ex:
            print(ex)
            return os.path.join(sys.path[0], "logs/offline/"+self._cpid_uniqid+"/active_" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".txt")
    
    def new_active_file(self, file_path):
        try:
            is_new = False
            data_path = None
            if os.path.exists(file_path):
                fsize = round(self.convert_unit(float(os.stat(file_path).st_size), self._file_unit), 2)

                if fsize < self._file_size or self._file_size == 1:
                    data_path = file_path
                else:
                    os.rename(file_path, file_path.replace("active_", ""))
            if data_path == None:
                is_new = True
                data_path = os.path.join(sys.path[0], "logs/offline/"+self._cpid_uniqid+"/active_" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".txt")
            #Remove first file if size limit exceed
            if is_new:
                self.remove_first_file()
            return data_path
        except Exception as ex:
            print(ex)
            return os.path.join(sys.path[0], "logs/offline/"+self._cpid_uniqid+"/active_" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".txt")
    
    def get_log_files(self):
        logs = []
        try:
            log_path = os.path.join(sys.path[0], "logs")
            path_staus=os.path.exists(log_path)
            if path_staus:
                for sub_folder in ["offline",self._cpid_uniqid]:
                    log_path = os.path.join(log_path,sub_folder)
                    path_staus=os.path.exists(log_path)
                    if path_staus:
                        pass
                    else:
                        os.mkdir(log_path)
            else:
                os.mkdir(log_path)
                for sub_folder in ["offline",self._cpid_uniqid]:
                    log_path = os.path.join(log_path,sub_folder)
                    os.mkdir(log_path)
            files = os.listdir(log_path)
            if len(files) > 0:
                for f in files:
                    fpath = os.path.join(sys.path[0] + "/logs/offline/"+self._cpid_uniqid, f)
                    if f.startswith("active"):
                        os.rename(fpath, fpath.replace("active_", ""))
                        fpath = fpath.replace("active_", "")
                    
                    if os.path.exists(fpath):
                        logs.append(fpath)
            return logs
        except:
            return logs
    
    def read_file_data(self, file_path):
        logs = []
        try:
            try:
                with open(file_path, "r") as dfile:
                    _data = dfile.read()
            except:
                _data = None
            
            if _data != None:
                _data = _data.split("\n")
            
            for obj in _data:
                try:
                    if len(obj) > 0:
                        logs.append(json.loads(obj))
                except:
                    print("\nInvalid file data : " + obj)
            return logs
        except:
            return logs
    
    def delete_file(self, file_path):
        try:
            os.remove(file_path)
            print("\nLog file deleted successfully")
        except:
            print("\nErrro while delete file")
    
    def clear_all_files(self):
        try:
            log_path = os.path.join(sys.path[0], "logs/offline/"+self._cpid_uniqid)
            filelist = [ f for f in os.listdir(log_path) if f ]
            for f in filelist:
                if os.path.isfile(os.path.join(log_path, f)):
                    os.remove(os.path.join(log_path, f))
        except:
            print("\nyou can not clear the directory.....\n")

    def write_file(self, file_path, logs):
        try:
            isDone = False
            try:
                wData = []
                for log in logs:
                    wData.append(json.dumps(log))
                wData = "\n".join(wData)
                with open(file_path, "w") as dfile:
                    dfile.write(wData)
                isDone = True
            except:
                print("\nErrro while write file")
            if isDone:
                print("\nLog file write successfully")
            else:
                self.delete_file(file_path)
        except:
            print("\nErrro while write file")
    
    def convert_unit(self, size_in_bytes, unit = 0):
        try:
            if unit == 1:#KB
                return size_in_bytes/1024
            elif unit == 2:#MB
                return size_in_bytes/(1024*1024)
            elif unit == 3:#GB
                return size_in_bytes/(1024*1024*1024)
            else:
                return size_in_bytes
        except:
            return size_in_bytes
    
    def get_file_size(self, max_size, file_count):
        try:
            if max_size == 0:
                return 1
            else:
                tSize = max_size * (1024 * 1024)
                sSize = tSize / file_count
                return self.convert_unit(sSize, 1)
        except:
            return 0
    
    def remove_first_file(self):
        try:
            log_path = os.path.join(sys.path[0], "logs/offline/"+self._cpid_uniqid)
            files = os.listdir(log_path)
            if len(files) >= self.file_count:
                v=[]
                for i in range(0,len(files)):
                    v.append(int(files[i].replace('-','').replace('.txt','')))
                fpath = os.path.join(sys.path[0] + "/logs/offline/"+self._cpid_uniqid, files[v.index(min(v))])
                os.remove(fpath)
        except:
            pass
    
    def has_key(self, data, key):
        try:
            return key in data
        except:
            return False
    
    def __init__(self,cpid_uniqid,sdk_config, sendBackToClient):
        self._cpid_uniqid=cpid_uniqid
        self._sdk_config = sdk_config
        self.max_size = 0 #MB
        self.file_count = 1
        
        if self.has_key(sdk_config, "offlineStorage"):
            if "availSpaceInMb" in sdk_config["offlineStorage"] and sdk_config["offlineStorage"]["availSpaceInMb"]:
                self.max_size = float(sdk_config["offlineStorage"]["availSpaceInMb"])
        
        if self.has_key(sdk_config, "offlineStorage"):
            if "fileCount" in sdk_config["offlineStorage"] and sdk_config["offlineStorage"]["fileCount"]:
                self.file_count = int(sdk_config["offlineStorage"]["fileCount"])
        
        self._file_size = self.get_file_size(self.max_size, self.file_count) #KB
        self._file_unit = 1 #KB
        self._data_path = self.get_active_file()
        self.sendBackToClient = sendBackToClient
