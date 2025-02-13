import random
import sys
import time
import subprocess
import json

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dOta

# This is the data dictionary that periodically gets updated and sent to IoTConnect
telemetry = {
    "dms_head_direction": 0,
    "dms_yawning": 0,
    "dms_eyes_open": 1,
    "dms_alert": 0,      
    "dms_bbox_xmin": 0,       
    "dms_bbox_ymin": 0,         
    "dms_bbox_xmax": 0,        
    "dms_bbox_ymax": 0
}

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


# Updates the DMS data entries of the telemetry dictionary (if data is fresh) and acknowledges that the data has been received
def read_dms_data():
    global telemetry

    # Read the DMS data JSON file
    with open("/home/weston/dms-data.json", "r") as jsonFile:
        dms_data = json.load(jsonFile)
    # If the ACK is not set, it means fresh data is available 
    if dms_data["ack"] == 0:
        # Update the DMS data entries of the telemetry dictionary
        telemetry["dms_head_direction"] = dms_data["head_direction"]
        telemetry["dms_yawning"] = dms_data["yawning"]
        telemetry["dms_eyes_open"] = dms_data["eyes_open"]
        telemetry["dms_alert"] = dms_data["alert"]
        telemetry["dms_bbox_xmin"] = dms_data["bbox_xmin"]
        telemetry["dms_bbox_ymin"] = dms_data["bbox_ymin"]
        telemetry["dms_bbox_xmax"] = dms_data["bbox_xmax"]
        telemetry["dms_bbox_ymax"] = dms_data["bbox_ymax"]
        # Set the ACK so the DMS program knows the data has been received
        dms_data["ack"] = 1
        with open("/home/weston/dms-data.json", "w") as jsonFile:
            json.dump(dms_data, jsonFile)


def on_disconnect(reason: str, disconnected_from_server: bool):
    print("Disconnected%s. Reason: %s" % (" from server" if disconnected_from_server else "", reason))

# Reset the ack in the JSON data buffer so DMS knows to populate with new data
with open("/home/weston/dms-data.json", "r") as jsonFile:
        dms_data = json.load(jsonFile)
dms_data["ack"] = 1
with open("/home/weston/dms-data.json", "w") as jsonFile:
    json.dump(dms_data, jsonFile)


# Start up the DMS program as a separate process (will make this controllable via IoTConnect commands soon)
DMS_process = subprocess.Popen(["python3", "/usr/bin/eiq-examples-git/dms/dms-processing.py"])

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

    # Ensure proper connection and send telemetry to IoTConnect every 3 seconds
    while True:
        if not c.is_connected():
            print('(re)connecting...')
            c.connect()
            if not c.is_connected():
                print('Unable to connect. Exiting.')  # Still unable to connect after 100 (default) re-tries.
                sys.exit(2)
        read_dms_data()
        c.send_telemetry(telemetry)
        time.sleep(1)

except DeviceConfigError as dce:
    print(dce)
    DMS_process.terminate()
    sys.exit(1)

except KeyboardInterrupt:
    print("Exiting.")
    DMS_process.terminate()
    sys.exit(0)

except Exception as ex:
    print(ex)
    DMS_process.terminate()
    sys.exit(0)
