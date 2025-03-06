# SPDX-License-Identifier: MIT
# Copyright (C) 2025 Avnet
# Authors: Nikola Markovic <nikola.markovic@avnet.com>, Zackary Andraka <zackary.andraka@avnet.com>, et al.
# -----------------------------------------------------------------------------
# PURPOSE:
#   This script runs on an NXP i.MX platform (e.g. i.MX93) and accomplishes the following:
#    1) Starts the DMS (Driver Monitoring System) Python script as a subprocess.
#    2) Connects to Avnet IoTConnect with your device configuration and credentials.
#    3) Periodically reads /home/weston/dms-data.json for new detection states (yawning,
#       eyes_open, bounding box, etc.) and sends that telemetry to IoTConnect.
#    4) Listens for IoTConnect commands (MQTT) such as 'image', 'get-ip', 'set-user-led',
#       'set-thresholds', 'set-conditions', and acts on them:
#        - "image": updates the DMS Flask server's stream mode via a local HTTPS POST.
#        - "get-ip": returns the device's local IP address.
#        - "set-user-led": example to set an RGB LED (just logs it by default).
#        - "set-thresholds": writes new threshold values to /home/weston/dms-config.json
#          so the DMS script can pick them up (no Flask usage).
#        - "set-conditions": similarly writes forced states to /home/weston/dms-config.json.
#
#   NOTE: We pass `verify=False` to requests.post(...) because we're using a self-signed
#   certificate locally. This avoids certificate verification errors when connecting to
#   https://127.0.0.1:8080.
#
# -----------------------------------------------------------------------------

import random
import sys
import time
import subprocess
import json
import socket
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import urllib.request
import requests
import fcntl
import os
import re

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dOta

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS FOR SAFE JSON READ/WRITE
# -----------------------------------------------------------------------------
face_detection_model = ""
face_landmark_model = ""
eye_landmark_model = ""
# Open the Python script and read its contents
with open("/home/weston/dms-processing.py", 'r') as file:
    dms_script = file.read()        

# Iterate over each line in the script
for line in dms_script.splitlines():
    if "DETECT_MODEL =" in line:
        pattern = r'=\s*(.*)'
        match = re.search(pattern, line)
        if match:
            face_detection_model = match.group(1).strip().strip('"') 
    elif "FACE_LANDMARK_MODEL =" in line:
        pattern = r'=\s*(.*)'
        match = re.search(pattern, line)
        if match:
            face_landmark_model = match.group(1).strip().strip('"')
    if "EYE_LANDMARK_MODEL =" in line:
        pattern = r'=\s*(.*)'
        match = re.search(pattern, line)
        if match:
            eye_landmark_model = match.group(1).strip().strip('"')


def safe_write_json(path, data):
    """
    Writes JSON to the specified file using an exclusive lock so no other process
    can write simultaneously, preventing file corruption.
    """
    with open(path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(data, f, indent=2)
        fcntl.flock(f, fcntl.LOCK_UN)

def safe_read_json(path):
    """
    Reads JSON from the specified file using a shared lock so other processes
    won't overwrite while reading.
    """
    with open(path, "r") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        data = json.load(f)
        fcntl.flock(f, fcntl.LOCK_UN)
    return data

# -----------------------------------------------------------------------------
# TELEMETRY DATA DICTIONARY
# -----------------------------------------------------------------------------
# This dictionary is periodically sent to IoTConnect. We update it with current
# DMS data read from /home/weston/dms-data.json.
telemetry = {
    "dms_face_detection_model": face_detection_model,
    "dms_landmark_model": face_landmark_model,
    "dms_eye_model": eye_landmark_model,
    "dms_head_direction": 0,
    "dms_yawning": 0,
    "dms_eyes_open": 1, 
    "dms_alert": 0,
    "dms_bbox_xmin": 0,
    "dms_bbox_ymin": 0,
    "dms_bbox_xmax": 0,
    "dms_bbox_ymax": 0,
    "dms_pitch": 0,
    "dms_roll": 0,
    "dms_yaw_val": 0,
    "dms_mouth_ratio": 0,
    "dms_left_eye_ratio_smoothed": 0,
    "dms_right_eye_ratio_smoothed": 0,
    "camera_ip": ""
}

# -----------------------------------------------------------------------------
# UTILITY TO GET LOCAL IP
# -----------------------------------------------------------------------------

def get_local_ip():
    """
    Attempt to find the local IP address by connecting to a public IP (like 8.8.8.8)
    without sending data. This returns the interface IP used for outbound traffic.
    If anything goes wrong, default to 127.0.0.1.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ipaddr = s.getsockname()[0]
    except Exception:
        ipaddr = "127.0.0.1"
    finally:
        s.close()
    return ipaddr

# -----------------------------------------------------------------------------
# DMS CONFIG FILE UPDATER
# -----------------------------------------------------------------------------
# If IoTConnect commands change thresholds or forced states, we update
# /home/weston/dms-config.json. The DMS script will poll this file periodically
# (via load_config_from_json()) to apply the changes.
# -----------------------------------------------------------------------------

CONFIG_PATH = "/home/weston/dms-config.json"

def update_config_file(transition_threshold=None, eye_threshold=None, forced_states=None):
    """
    Reads /home/weston/dms-config.json, updates any fields that are provided,
    and writes it back. If the file doesn't exist, we create a default structure.
    """
    # If file not present, create minimal defaults
    if not os.path.exists(CONFIG_PATH):
        base = {
            "transition_threshold": 8,
            "eye_ratio_threshold": 0.2,
            "forced_states": {
                "head_direction": None,
                "yawning": None,
                "eyes_open": None
            }
        }
        safe_write_json(CONFIG_PATH, base)

    # Read existing config
    current = safe_read_json(CONFIG_PATH)

    # Update threshold values if provided
    if transition_threshold is not None:
        current["transition_threshold"] = transition_threshold
    if eye_threshold is not None:
        current["eye_ratio_threshold"] = eye_threshold

    # Update forced states if provided
    if forced_states is not None:
        # Merge with existing forced_states
        if "forced_states" not in current:
            current["forced_states"] = {
                "head_direction": None,
                "yawning": None,
                "eyes_open": None
            }
        current["forced_states"].update(forced_states)

    # Write updated config back to file
    safe_write_json(CONFIG_PATH, current)


# -----------------------------------------------------------------------------
# COMMAND CALLBACKS
# -----------------------------------------------------------------------------

def on_command(msg: C2dCommand):
    """
    Called when a command arrives from IoTConnect. Checks command name and arguments,
    then performs the requested action.
    """
    print("Received command", msg.command_name, msg.command_args, msg.ack_id)

    if msg.command_name == "image":
        # Expects exactly 1 argument: 'live', 'off', or 'snapshot'
        if len(msg.command_args) == 1:
            param = msg.command_args[0]
            if param in ["live", "off", "snapshot"]:
                # The DMS is presumably listening at https://127.0.0.1:8080/set_mode
                # We must pass verify=False if using a self-signed cert (User Note).
                url = "https://127.0.0.1:8080/set_mode"
                payload = {"mode": param}
                try:
                    r = requests.post(url, json=payload, verify=False)
                    if r.status_code == 200:
                        print(f"Set mode to {param}. Response:", r.json())
                        c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f"Set mode to {param}")
                    else:
                        print(f"Failed to set mode. Status {r.status_code}. Resp: {r.text}")
                        c.send_command_ack(msg, C2dAck.CMD_FAILED, f"Failed with {r.status_code}")
                except Exception as e:
                    print("Error calling set_mode:", e)
                    c.send_command_ack(msg, C2dAck.CMD_FAILED, str(e))
            else:
                print("Unknown image param:", param)
                c.send_command_ack(msg, C2dAck.CMD_FAILED, f"Unknown param {param}")
        else:
            print("Expected 1 argument for image command, got", len(msg.command_args))
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument for image command")

    elif msg.command_name == "get-ip":
        # Retrieve local IP
        ip_addr = get_local_ip()
        ack_message = f"The camera IP is: {ip_addr}"
        print(ack_message)
        if msg.ack_id is not None:
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, ack_message)

    elif msg.command_name == "set-user-led":
        # Example command with 3 arguments for R/G/B. We just log it here.
        if len(msg.command_args) == 3:
            r_val = int(msg.command_args[0])
            g_val = int(msg.command_args[1])
            b_val = int(msg.command_args[2])
            status_message = f"Setting User LED to R:{r_val} G:{g_val} B:{b_val}"
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status_message)
            print(status_message)
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 3 arguments")
            print("Expected three command arguments, but got", len(msg.command_args))

    elif msg.command_name == "set-thresholds":
        # Expect 2 arguments: [transition_threshold, eye_ratio_threshold]
        if len(msg.command_args) == 2:
            try:
                t_thresh = int(msg.command_args[0])
                e_thresh = float(msg.command_args[1])
                update_config_file(transition_threshold=t_thresh, eye_threshold=e_thresh)
                c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK,
                                   f"Updated thresholds: transition={t_thresh}, eye={e_thresh}")
            except Exception as e:
                print("Error in set-thresholds command:", e)
                c.send_command_ack(msg, C2dAck.CMD_FAILED, str(e))
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED,
                               "Expected 2 arguments: transition_threshold, eye_ratio_threshold")

    elif msg.command_name == "set-conditions":
        # Expect 3 arguments: [head_direction, yawning, eyes_open]
        # If you want to "unset" a forced state, you could pass 'null' or similar in IoTConnect.
        if len(msg.command_args) == 3:
            try:
                hd = None if msg.command_args[0].lower() == "null" else int(msg.command_args[0])
                yn = None if msg.command_args[1].lower() == "null" else int(msg.command_args[1])
                eo = None if msg.command_args[2].lower() == "null" else int(msg.command_args[2])
                forced = {
                    "head_direction": hd,
                    "yawning": yn,
                    "eyes_open": eo
                }
                update_config_file(forced_states=forced)
                c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK,
                                   f"Forced states updated: {forced}")
            except Exception as e:
                print("Error in set-conditions command:", e)
                c.send_command_ack(msg, C2dAck.CMD_FAILED, str(e))
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED,
                               "Expected 3 arguments: head_direction, yawning, eyes_open")

    else:
        # Not a recognized command
        print(f"Command {msg.command_name} not implemented!")
        if msg.ack_id is not None:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Not Implemented")

# -----------------------------------------------------------------------------
# OTA CALLBACK
# -----------------------------------------------------------------------------
def exit_and_restart():
    print("")  # Print a blank line so it doesn't look as confusing in the output.
    sys.stdout.flush()
    # restart the process
    os.execv(sys.executable, [sys.executable, __file__] + [sys.argv[0]])


def subprocess_run_with_print(args):
    print("Running command:", ' '.join(args))
    subprocess.run(args, check=True)


def on_ota(msg: C2dOta):
    # We just print the URL. The actual handling of the OTA request would be project specific.
    print("Starting OTA downloads for version %s" % msg.version)
    error_msg = None
    c.send_ota_ack(msg, C2dAck.OTA_DOWNLOADING)
    for url in msg.urls:
        print("Downloading OTA file %s from %s" % (url.file_name, url.url))
        try:
            urllib.request.urlretrieve(url.url, url.file_name)
        except Exception as e:
            print("Encountered download error", e)
            error_msg = "Download error for %s" % url.file_name
            break
        try:
            if url.file_name.endswith(".tar.gz"):
                subprocess_run_with_print(("tar", "-xzvf", url.file_name, "--overwrite"))
                # If there is an ota-install.sh script in the OTA package, execute it
                filename = "ota-install.sh"
                current_directory = os.getcwd()
                file_path = os.path.join(current_directory, filename)
                if os.path.isfile(file_path):
                    try:
                        # Give the file executable permissions
                        os.chmod(file_path, 0o755)
                        print(f"{filename} is now executable.")
                        # Execute the file
                        subprocess.run(['bash', file_path], check=True)
                        print(f"Successfully executed {filename}")
                        # Delete the ota_install.sh file after execution
                        os.remove(file_path)
                        print(f"{filename} has been deleted.")

                    except subprocess.CalledProcessError as e:
                        print(f"Error executing {filename}: {e}")
                    except Exception as e:
                        print(f"An error occurred: {e}")
                else:
                    print(f"{filename} not found in the current directory.")
            else:
                print("ERROR: Unhandled file format for file %s" % url.file_name)
                error_msg = "Processing error for %s" % url.file_name
                break
        except subprocess.CalledProcessError:
            print("ERROR: Failed to install %s" % url.file_name)
            error_msg = "Install error for %s" % url.file_name
            break
    if error_msg is not None:
        c.send_ota_ack(msg, C2dAck.OTA_FAILED, error_msg)
        print('Encountered a download processing error "%s". Not restarting.' % error_msg)  # In hopes that someone pushes a better update
    else:
        print("OTA successful. Will restart the application...")
        c.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_DONE)
        exit_and_restart()



# -----------------------------------------------------------------------------
# FUNCTION: read_dms_data
# -----------------------------------------------------------------------------
def read_dms_data():
    """
    Reads the current DMS data from /home/weston/dms-data.json (if present),
    and updates the 'telemetry' dictionary with new values. This data will be
    sent to IoTConnect on each loop iteration below.
    """
    global telemetry
    try:
        dms_data = safe_read_json("/home/weston/dms-data.json")
    except (json.JSONDecodeError, FileNotFoundError):
        print("WARNING: dms-data.json missing or invalid. Using defaults.")
        dms_data = {
            "head_direction": 5,
            "yawning": 0,
            "eyes_open": 2,
            "alert": 3,
            "bbox_xmin": 0,
            "bbox_ymin": 0,
            "bbox_xmax": 0,
            "bbox_ymax": 0
        }

    telemetry["dms_head_direction"] = dms_data.get("head_direction", 5)
    telemetry["dms_yawning"]        = dms_data.get("yawning", 0)
    telemetry["dms_eyes_open"]      = dms_data.get("eyes_open", 2)
    telemetry["dms_alert"]          = dms_data.get("alert", 3)
    telemetry["dms_bbox_xmin"]      = dms_data.get("bbox_xmin", 0)
    telemetry["dms_bbox_ymin"]      = dms_data.get("bbox_ymin", 0)
    telemetry["dms_bbox_xmax"]      = dms_data.get("bbox_xmax", 0)
    telemetry["dms_bbox_ymax"]      = dms_data.get("bbox_ymax", 0)
    telemetry["dms_pitch"]                     = dms_data.get("pitch", 0)
    telemetry["dms_roll"]                      = dms_data.get("roll", 0)
    telemetry["dms_yaw_val"]                   = dms_data.get("yaw_val", 0)
    telemetry["dms_mouth_ratio"]               = dms_data.get("mouth_ratio", 0)
    telemetry["dms_left_eye_ratio_smoothed"]   = dms_data.get("left_eye_ratio_smoothed", 0)
    telemetry["dms_right_eye_ratio_smoothed"]  = dms_data.get("right_eye_ratio_smoothed", 0)

# -----------------------------------------------------------------------------
# DISCONNECTION CALLBACK
# -----------------------------------------------------------------------------
def on_disconnect(reason: str, disconnected_from_server: bool):
    """
    Called when the device is disconnected from IoTConnect, either because
    the server closed the connection or the client did.
    """
    print("Disconnected%s. Reason: %s" % (" from server" if disconnected_from_server else "", reason))

# -----------------------------------------------------------------------------
# MAIN EXECUTION
# -----------------------------------------------------------------------------
# Start the DMS as a separate process, connect to IoTConnect, and loop.
# -----------------------------------------------------------------------------

# Start up the DMS program as a separate process
# (Make sure /usr/bin/eiq-examples-git/dms/dms-processing.py is the correct path)
DMS_process = subprocess.Popen(["python3", "/home/weston/dms-processing.py"])

try:
    # Gather local IP address to put in the telemetry
    ip_str = get_local_ip()
    telemetry["camera_ip"] = ip_str
    print(f"Camera IP at startup: {ip_str}")

    # Load device config from iotcDeviceConfig.json
    device_config = DeviceConfig.from_iotc_device_config_json_file(
        device_config_json_path="iotcDeviceConfig.json",
        device_cert_path="device-cert.pem",
        device_pkey_path="device-pkey.pem"
    )

    # Create the IoTConnect client with our callbacks
    c = Client(
        config=device_config,
        callbacks=Callbacks(
            ota_cb = on_ota,
            command_cb=on_command,
            disconnected_cb=on_disconnect
        )
    )

    # Continuously ensure connection and send telemetry every 2 seconds
    while True:
        if not c.is_connected():
            print('(re)connecting...')
            c.connect()
            if not c.is_connected():
                print('Unable to connect. Exiting.')
                sys.exit(2)

        # Read fresh data from dms-data.json, update our telemetry dict
        read_dms_data()
        # Send the telemetry to IoTConnect
        c.send_telemetry(telemetry)
        # Wait before next iteration
        time.sleep(2)

except DeviceConfigError as dce:
    print(dce)
    DMS_process.terminate()
    sys.exit(1)

except KeyboardInterrupt:
    print("Exiting.")
    DMS_process.terminate()
    sys.exit(0)

except Exception as ex:
    print("Exception occurred:", ex)
    DMS_process.terminate()
    sys.exit(0)
