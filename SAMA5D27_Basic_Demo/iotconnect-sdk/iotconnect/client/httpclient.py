import sys
import json

if sys.version_info >= (3, 5):
    import http.client as httplib
else:
    import httplib

class httpclient:
    _name = None
    _config = None
    _sdk_config = None
    _isConnected = False
    _header = None
    _scheme = None
    _host = None
    _api_path = None
    
    @property
    def isConnected(self):
        return self._isConnected
    
    @property
    def name(self):
        return self._config["n"]
    
    def Send(self, data):
        try:
            _client = None
            if self.name == "https":
                _client = httplib.HTTPSConnection(self._host)
            if self.name == "http":
                _client = httplib.HTTPConnection(self._host)
            
            if _client != None :
                _client.request("POST", self._api_path,json.dumps(data), self._header)
                _client.getresponse()
                _client.close()
            
            self._isConnected = True
            return True
        except:
            self._isConnected = False
            return False
    
    def __init__(self, config, sdk_config):
        self._config = config
        self._sdk_config = sdk_config
        self._host = self._config["h"]
        self._api_path = self._sdk_config["api_path"]
        self._api_path = self._api_path.replace("{clientId}", self._config["clientId"])
        self._api_path = self._api_path.replace("{api_version}", self._sdk_config["api_version"])
        self._header = {"Content-type": "application/json", "Accept": "application/json", "Authorization": self._config['pwd']}

