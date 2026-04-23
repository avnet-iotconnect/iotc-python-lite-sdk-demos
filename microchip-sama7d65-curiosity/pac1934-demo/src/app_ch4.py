# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# PAC1934 Power Monitor Demo - Channel 4 Only (VDD_CPU)
# Monitors the VDD_CPU power rail and publishes telemetry to /IOTCONNECT.

import sys
import time
import os
import subprocess
import urllib.request
import requests

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dOta

from py_pac193x import PAC193x

# Configuration from environment
CONFIG_DIR = os.environ.get("PAC_CONFIG_DIR", ".")
TELEMETRY_INTERVAL = float(os.environ.get("PAC_TELEMETRY_SECS", "10"))

CHANNEL = 4
CHANNEL_LABEL = "VDD_CPU"

c = None
pac = None
telemetry_interval = TELEMETRY_INTERVAL


def extract_and_run_tar_gz(targz_filename: str):
    try:
        subprocess.run(("tar", "-xzvf", targz_filename, "--overwrite"), check=True)
        current_directory = os.getcwd()
        script_file_path = os.path.join(current_directory, "install.sh")
        if os.path.isfile(script_file_path):
            try:
                subprocess.run(['bash', script_file_path], check=True)
                os.remove(script_file_path)
                print("Successfully executed install.sh")
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
    global c, telemetry_interval
    print("Received command", msg.command_name, msg.command_args, msg.ack_id)

    if msg.command_name == "set-interval":
        if len(msg.command_args) == 1:
            try:
                new_interval = float(msg.command_args[0])
                if new_interval > 0:
                    telemetry_interval = new_interval
                    status = "Telemetry interval set to %.1f seconds" % new_interval
                    c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status)
                    print(status)
                else:
                    c.send_command_ack(msg, C2dAck.CMD_FAILED, "Interval must be positive")
            except ValueError:
                c.send_command_ack(msg, C2dAck.CMD_FAILED, "Invalid number")
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")

    elif msg.command_name == "file-download":
        if len(msg.command_args) == 1:
            status_message = "Downloading %s to device" % (msg.command_args[0])
            response = requests.get(msg.command_args[0])
            if response.status_code == 200:
                with open('package.tar.gz', 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                print("File downloaded successfully and saved to package.tar.gz")
            else:
                print(f"Failed to download the file. Status code: {response.status_code}")
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status_message)
            print(status_message)
            extract_and_run_tar_gz('package.tar.gz')
            print("Download command successful. Will restart the application...")
            print("")
            sys.stdout.flush()
            os.execv(sys.executable, [sys.executable, __file__] + [sys.argv[0]])
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")

    else:
        print("Command %s not implemented!" % msg.command_name)
        if msg.ack_id is not None:
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
            break
        if url.file_name.endswith(".tar.gz"):
            extraction_success = extract_and_run_tar_gz(url.file_name)
            if not extraction_success:
                break
        else:
            print("ERROR: Unhandled file format for file %s" % url.file_name)
    if extraction_success:
        print("OTA successful. Will restart the application...")
        c.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_DONE)
        print("")
        sys.stdout.flush()
        os.execv(sys.executable, [sys.executable, __file__] + [sys.argv[0]])
    else:
        print('Encountered a download processing error. Not restarting.')


def on_disconnect(reason: str, disconnected_from_server: bool):
    print("Disconnected%s. Reason: %s" % (" from server" if disconnected_from_server else "", reason))


try:
    config_path = os.path.join(CONFIG_DIR, "iotcDeviceConfig.json")
    cert_path = os.path.join(CONFIG_DIR, "device-cert.pem")
    pkey_path = os.path.join(CONFIG_DIR, "device-pkey.pem")

    device_config = DeviceConfig.from_iotc_device_config_json_file(
        device_config_json_path=config_path,
        device_cert_path=cert_path,
        device_pkey_path=pkey_path
    )

    pac = PAC193x()
    pac.initialize()
    print("PAC1934 initialized via IIO at %s" % pac.iio_path)
    print("Monitoring Channel %d: %s" % (CHANNEL, CHANNEL_LABEL))

    c = Client(
        config=device_config,
        callbacks=Callbacks(
            ota_cb=on_ota,
            command_cb=on_command,
            disconnected_cb=on_disconnect
        )
    )

    while True:
        if not c.is_connected():
            print('(re)connecting...')
            c.connect()
            if not c.is_connected():
                print('Unable to connect. Exiting.')
                sys.exit(2)

        data = pac.get_channel(CHANNEL)
        telemetry = {
            'sdk_version': SDK_VERSION,
            'telemetry_interval': telemetry_interval,
            'vdd_cpu_vbus_mv': data['vbus_mv'],
            'vdd_cpu_isense_ma': data['isense_ma'],
            'vdd_cpu_power_mw': data['power_mw'],
        }

        print("  %s: %.1f mV, %.2f mA, %.2f mW" % (
            CHANNEL_LABEL, data['vbus_mv'], data['isense_ma'], data['power_mw']
        ))

        c.send_telemetry(telemetry)
        time.sleep(telemetry_interval)

except DeviceConfigError as dce:
    print(dce)
    sys.exit(1)

except KeyboardInterrupt:
    print("Exiting.")
    if pac:
        pac.close()
    sys.exit(0)
