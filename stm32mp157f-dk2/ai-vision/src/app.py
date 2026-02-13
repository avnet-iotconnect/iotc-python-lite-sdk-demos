import random
import sys
import time
from dataclasses import dataclass
import subprocess
import re
import os
import urllib.request
import requests

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
        

def extract_and_run_tar_gz(targz_filename: str):
    try:
        subprocess.run(("tar", "-xzvf", targz_filename, "--overwrite"), check=True)
        current_directory = os.getcwd()
        script_file_path = os.path.join(current_directory, "install.sh")
        # If install.sh is found in the current directory, execute it and then delete it 
        # so it is not executed automatically again for future packages (may not include an install.sh)
        if os.path.isfile(script_file_path):
            try:
                subprocess.run(['bash', script_file_path], check=True)
                os.remove(script_file_path)
                print(f"Successfully executed install.sh")
                return True
            except subprocess.CalledProcessError as e:
                os.remove(script_file_path)
                print(f"Error executing install.sh: {e}")
                return False
            except Exception as e:
                os.remove(script_file_path)
                print(f"An error occurred: {e}")
                return False
        else:
            print("install.sh not found in the current directory.")
            return True
    except subprocess.CalledProcessError:
        return False


def on_command(msg: C2dCommand):
    global c
    print("Received command", msg.command_name, msg.command_args, msg.ack_id)
    if msg.command_name == "file-download":
        if len(msg.command_args) == 1:
            status_message = "Downloading %s to device" % (msg.command_args[0])
            response = requests.get(msg.command_args[0])
            # Check if the request was successful (status code 200)
            if response.status_code == 200:
                # Open the file in binary write mode and save the content
                with open('package.tar.gz', 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192): 
                        file.write(chunk)
                print(f"File downloaded successfully and saved to package.tar.gz")
            else:
                print(f"Failed to download the file. Status code: {response.status_code}")
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status_message)
            print(status_message)
            extraction_success = extract_and_run_tar_gz('package.tar.gz')
            print("Download command successful. Will restart the application...")
            print("")  # Print a blank line so it doesn't look as confusing in the output.
            sys.stdout.flush()
            # restart the process
            os.execv(sys.executable, [sys.executable, __file__] + [sys.argv[0]])
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")
            print("Expected 1 command argument, but got", len(msg.command_args))	
    else:
        print("Command %s not implemented!" % msg.command_name)
        if msg.ack_id is not None: # it could be a command without "Acknowledgement Required" flag in the device template
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Not Implemented")


def on_ota(msg: C2dOta):
    global c
    print("Starting OTA downloads for version %s" % msg.version)
    c.send_ota_ack(msg, C2dAck.OTA_DOWNLOADING)
    extraction_success = False
    for url in msg.urls:
        print("Downloading OTA file %s from %s" % (url.file_name, url.url))
        try:
            urllib.request.urlretrieve(url.url, url.file_name)
        except Exception as e:
            print("Encountered download error", e)
            error_msg = "Download error for %s" % url.file_name
            break
        if url.file_name.endswith(".tar.gz"):
            extraction_success = extract_and_run_tar_gz(url.file_name)
            if extraction_success is False:
                break
        else:
            print("ERROR: Unhandled file format for file %s" % url.file_name)
    if extraction_success is True:
        print("OTA successful. Will restart the application...")
        c.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_DONE)
        print("")  # Print a blank line so it doesn't look as confusing in the output.
        sys.stdout.flush()
        # restart the process
        os.execv(sys.executable, [sys.executable, __file__] + [sys.argv[0]])
    else:
        print('Encountered a download processing error. Not restarting.')


def on_disconnect(reason: str, disconnected_from_server: bool):
    print("Disconnected%s. Reason: %s" % (" from server" if disconnected_from_server else "", reason))


def get_object_data():
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
    object_data.classification_a = re.sub(r'[%()\d]+', '', file_lines[0])
    object_data.confidence_a = int(re.sub(r'\D', '', file_lines[0]))
    if len(file_lines) > 1:
        object_data.classification_b = re.sub(r'[%()\d]+', '', file_lines[1])
        object_data.confidence_b = int(re.sub(r'\D', '', file_lines[1]))
    if len(file_lines) > 2:
        object_data.classification_c = re.sub(r'[%()\d]+', '', file_lines[2])
        object_data.confidence_c = int(re.sub(r'\D', '', file_lines[2]))
    index = 0
    for object in file_lines:
        objects_string += object
        if index < (len(file_lines) - 1):
            objects_string += ", "
        index += 1
    return (objects_string, object_data)

open('/opt/demo/objects-detected.txt', 'w').close()
with open('/opt/demo/ack.txt', 'w') as ack_file:
    ack_file.write("init\n")


threshold = "0.7"
AI_Process = subprocess.Popen(["bash", "/usr/local/x-linux-ai/object-detection/launch-vision-program.sh", threshold])

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
