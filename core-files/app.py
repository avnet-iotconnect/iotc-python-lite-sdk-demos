# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# Authors: Nikola Markovic <nikola.markovic@avnet.com> et al.
# This is a self-updating app with OTA support that can update itself with a new OTA package.

import random
import sys
import time
from dataclasses import dataclass
import subprocess
import os
import urllib.request


from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dOta

"""
See minimal.py example for a way to configure the device without the JSON file
You can download the iotcDeviceConfig.json by clicking the cog icon in the upper right of your device's info panel
NOTE: If you do not pass the server certificate, we will use the system's trusted certificate store, if available.
For example, the trusted Root CA certificates from the in /etc/ssl/certs will be used on Linux.
However, it is more secure to pass the actual server CA Root certificate in order to avoid potential MITM attacks.
On Linux, you can use server_ca_cert_path="/etc/ssl/certs/DigiCert_Global_Root_CA.pem" for Azure
or server_ca_cert_path="/etc/ssl/certs/Amazon_Root_CA_1.pem" for AWS
"""

@dataclass
class ExampleAccelerometerData:
    x: float
    y: float
    z: float


@dataclass
class ExampleSensorData:
    temperature: float
    humidity: float
    accel: ExampleAccelerometerData


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
                subprocess.run(("tar", "-xzvf", url.file_name, "--overwrite"), check=True)
                filename = "install.sh"
                current_directory = os.getcwd()
                file_path = os.path.join(current_directory, filename)
                # If ota-install.sh is found in the current directory, give it executable permissions and execute it
                if os.path.isfile(file_path):
                    try:
                        subprocess.run(['bash', file_path], check=True)
                        print(f"Successfully executed {filename}")

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
        print("")  # Print a blank line so it doesn't look as confusing in the output.
        sys.stdout.flush()
        # restart the process
        os.execv(sys.executable, [sys.executable, __file__] + [sys.argv[0]])


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
