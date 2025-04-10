# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# Authors: Nikola Markovic <nikola.markovic@avnet.com> and Zackary Andraka <zackary.andraka@avnet.com> et al.
# This is a self-updating app with support to update itself with a new update package via OTA or a command.

import random
import sys
import time
from dataclasses import dataclass
import subprocess
import os
import urllib.request
import requests

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dOta


def extract_and_run_tar_gz(targz_filename: str):
    try:
        subprocess.run(("tar", "-xzvf", targz_filename, "--overwrite"), check=True)
        current_directory = os.getcwd()
        script_file_path = os.path.join(current_directory, "install.sh")
        # If install.sh is found in the current directory, execute it
        if os.path.isfile(script_file_path):
            try:
                subprocess.run(['bash', script_file_path], check=True)
                print(f"Successfully executed install.sh")
                return True
            except subprocess.CalledProcessError as e:
                print(f"Error executing install.sh: {e}")
                return False
            except Exception as e:
                print(f"An error occurred: {e}")
                return False
        else:
            print("install.sh not found in the current directory.")
            return False
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
                with open('ota-payload.tar.gz', 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192): 
                        file.write(chunk)
                print(f"File downloaded successfully and saved to ota-payload.tar.gz")
            else:
                print(f"Failed to download the file. Status code: {response.status_code}")
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status_message)
            print(status_message)
            extraction_success = extract_and_run_tar_gz('ota-payload.tar.gz')
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

try:
    device_config = DeviceConfig.from_iotc_device_config_json_file(
        device_config_json_path="iotcDeviceConfig.json",
        device_cert_path="device-cert.pem",
        device_pkey_path="device-pkey.pem"
    )

    c = Client(
        config=device_config,
        callbacks=Callbacks(
            ota_cb = on_ota,
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

        c.send_telemetry({
            'sdk_version': SDK_VERSION,
            'random': random.randint(0, 100)
        })
        time.sleep(10)

except DeviceConfigError as dce:
    print(dce)
    sys.exit(1)

except KeyboardInterrupt:
    print("Exiting.")
    sys.exit(0)
