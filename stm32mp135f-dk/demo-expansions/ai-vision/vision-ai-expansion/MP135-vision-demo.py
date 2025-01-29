import random
import sys
import time
from dataclasses import dataclass
import subprocess
import re

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dOta

@dataclass
class Object_Data:
    classification_a: str
    classification_b: str
    classification_c: str
    confidence_a: int
    confidence_b: int
    confidence_c: int
    confidence_threshold: int
    version: str
    
    '''def __init__(self, class_a: str, class_b: str, class_c: str, conf_a: float, conf_b: float, conf_c: float, conf_thresh: int, version: str)
        self.class_a = class_a
        self.class_b = class_b
        self.class_c = class_c
        self.conf_a = conf_a
        self.conf_b = conf_b
        self.conf_c = conf_c
        self.conf_thresh = conf_thresh
        self.version = version''' 

def on_command(msg: C2dCommand):
    print("Received command", msg.command_name, msg.command_args, msg.ack_id)
    if msg.command_name == "set-user-led":
        if len(msg.command_args) == 3:
            status_message = "Setting User LED to R:%d G:%d B:%d" % (int(msg.command_args[0]), int(msg.command_args[1]), int(msg.command_args[2]))
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status_message)
            print(status_message)
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 3 arguments")
            print("Expected three command arguments, but got", len(msg.command_args))
    else:
        print("Command %s not implemented!" % msg.command_name)
        if msg.ack_id is not None: # it could be a command without "Acknowledgement Required" flag in the device template
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Not Implemented")


def on_ota(msg: C2dOta):
    # We just print the URL. The actual handling of the OTA request would be project specific.
    # See the ota-handling.py for more details.
    print("Received OTA request. File: %s Version: %s URL: %s" % (msg.urls[0].file_name, msg.version, msg.urls[0].url))
    # OTA messages always have ack_id, so it is safe to not check for it before sending the ack
    c.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_FAILED, "Not implemented")


def on_disconnect(reason: str, disconnected_from_server: bool):
    print("Disconnected%s. Reason: %s" % (" from server" if disconnected_from_server else "", reason))

def get_object_data():
    if len(sys.argv) > 1:
        thresh = int(float(sys.argv[1])*100)
    else:
        thresh = 70
    object_data = Object_Data("none", "none", "none", 0, 0, 0, thresh, "0.0")
    file_lines = open("objects-detected.txt").read().splitlines()
    if len(file_lines) < 2: 
        return "none", object_data
    ack_string = ""
    for line in file_lines:
        ack_string += line
        ack_string += "\n"
    with open("ack.txt", "w") as ack_file:
        ack_file.write(ack_string)
    file_lines = file_lines[1:]
    objects_string = ""
    object_data.classification_a = re.sub(r'[()%\d+]', '', file_lines[0])
    object_data.confidence_a = int(re.sub('\D', '', file_lines[0]))
    if len(file_lines) > 1:
        object_data.classification_b = re.sub(r'[()%\d+]', '', file_lines[1])
        object_data.confidence_b = int(re.sub('\D', '', file_lines[1]))
    if len(file_lines) > 2:
        object_data.classification_c = re.sub(r'[()%\d+]', '', file_lines[2])
        object_data.confidence_c = int(re.sub('\D', '', file_lines[2]))
    index = 0
    for object in file_lines:
        objects_string += object
        if index < (len(file_lines) - 1):
            objects_string += ", "
        index += 1
    return (objects_string, object_data)

open('/home/weston/objects-detected.txt', 'w').close()
with open('/home/weston/ack.txt', 'w') as ack_file:
    ack_file.write("init\n")

if len(sys.argv) > 1:
    threshold = sys.argv[1]
else:
    threshold = "0.7"
AI_Process = subprocess.Popen(["/usr/local/x-linux-ai/object-detection/launch-vision-program.sh", threshold])

try:
    device_config = DeviceConfig.from_iotc_device_config_json_file(
        device_config_json_path="iotcDeviceConfig.json",
        device_cert_path="device-cert.pem",
        device_pkey_path="device-pkey.pem"
    )

    c = Client(
        config=device_config,
        callbacks=Callbacks(
            command_cb=on_command,
            disconnected_cb=on_disconnect
        )
    )
    while True:
        if not c.is_connected():
            print('(re)connecting...')
            c.connect()
            if not c.is_connected():
                print('Unable to connect. Exiting.')  # Still unable to connect after 100 (default) re-tries.
                sys.exit(2)
        detected_objects, data = get_object_data()
        c.send_telemetry({
            'sdk_version': SDK_VERSION,
            'objects_detected': detected_objects,
            'detection_data': data
        })
        time.sleep(1)

except DeviceConfigError as dce:
    print(dce)
    AI_Process.terminate()
    sys.exit(1)

except KeyboardInterrupt:
    print("Exiting.")
    AI_Process.terminate()
    sys.exit(0)

except Exception as ex:
    print(ex)
    AI_Process.terminate()
    sys.exit(0)
