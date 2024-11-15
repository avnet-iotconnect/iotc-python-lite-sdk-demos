import sys

ERROR_CODE = {
    "01" : "{msg} not found.",
    "02" : "Unable to read base URL.",
    "03" : "Sync response # {msg}",
    "04" : "Unable to proceed without info # {msg}",
    "05" : "Invalid certificate path, please check 'SdkOption'",
    "06" : "Protocol initialization failed # {msg}",
    "07" : "Template initialization failed for # {msg}",
    "08" : "Tumbling window initialization failed for attribute # {msg}",
    "09" : "Data processing falied."
}

class IoTConnectSDKException(Exception):
    def __init__(self, code, message = ""):
        if code in ERROR_CODE:
            self.message  = ("\nSDK ERR[%s]: %s" % (code, ERROR_CODE[code])).replace("{msg}", message)
        else:
            if message == "":
                self.message  = "\nERR[00] : Internal Error"
            else:
                self.message  = "\nERR[00] : Internal Error # " + message
