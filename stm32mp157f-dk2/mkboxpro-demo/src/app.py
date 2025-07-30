# SPDX-License-Identifier: MIT
# Copyright (C) 2024 Avnet
# Authors: Zackary Andraka <zackary.andraka@avnet.com> et al.
# This is a self-updating app with support to update itself with a new update package via OTA or a command.

import sys
import time
import subprocess
import os
import urllib.request
import requests
import threading
import asyncio
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
import pexpect
import struct

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dOta


def extract_and_run_tar_gz(targz_filename: str):
    try:
        subprocess.run(('tar', '-xzvf', targz_filename, '--overwrite'), check=True)
        current_directory = os.getcwd()
        script_file_path = os.path.join(current_directory, 'install.sh')
        if os.path.isfile(script_file_path):
            try:
                subprocess.run(['bash', script_file_path], check=True)
                os.remove(script_file_path)
                print('Successfully executed install.sh')
                return True
            except subprocess.CalledProcessError as e:
                os.remove(script_file_path)
                print(f'Error executing install.sh: {e}')
                return False
            except Exception as e:
                os.remove(script_file_path)
                print(f'An error occurred: {e}')
                return False
        else:
            print('install.sh not found in the current directory.')
            return True
    except subprocess.CalledProcessError:
        return False


def on_command(msg: C2dCommand):
    global c
    print('Received command', msg.command_name, msg.command_args, msg.ack_id)
    if msg.command_name == 'file-download':
        if len(msg.command_args) == 1:
            status_message = 'Downloading %s to device' % (msg.command_args[0])
            response = requests.get(msg.command_args[0])
            if response.status_code == 200:
                with open('package.tar.gz', 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192): 
                        file.write(chunk)
                print('File downloaded successfully and saved to package.tar.gz')
            else:
                print(f'Failed to download the file. Status code: {response.status_code}')
            c.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status_message)
            print(status_message)
            extraction_success = extract_and_run_tar_gz('package.tar.gz')
            print('Download command successful. Will restart the application...')
            print('')
            sys.stdout.flush()
            os.execv(sys.executable, [sys.executable, __file__] + [sys.argv[0]])
        else:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, 'Expected 1 argument')
            print('Expected 1 command argument, but got', len(msg.command_args))	
    else:
        print('Command %s not implemented!' % msg.command_name)
        if msg.ack_id is not None:
            c.send_command_ack(msg, C2dAck.CMD_FAILED, 'Not Implemented')


def on_ota(msg: C2dOta):
    global c
    print('Starting OTA downloads for version %s' % msg.version)
    c.send_ota_ack(msg, C2dAck.OTA_DOWNLOADING)
    extraction_success = False
    for url in msg.urls:
        print('Downloading OTA file %s from %s' % (url.file_name, url.url))
        try:
            urllib.request.urlretrieve(url.url, url.file_name)
        except Exception as e:
            print('Encountered download error', e)
            error_msg = 'Download error for %s' % url.file_name
            break
        if url.file_name.endswith('.tar.gz'):
            extraction_success = extract_and_run_tar_gz(url.file_name)
            if extraction_success is False:
                break
        else:
            print('ERROR: Unhandled file format for file %s' % url.file_name)
    if extraction_success is True:
        print('OTA successful. Will restart the application...')
        c.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_DONE)
        print('')
        sys.stdout.flush()
        os.execv(sys.executable, [sys.executable, __file__] + [sys.argv[0]])
    else:
        print('Encountered a download processing error. Not restarting.')


def on_disconnect(reason: str, disconnected_from_server: bool):
    print('Disconnected%s. Reason: %s' % (' from server' if disconnected_from_server else '', reason))


telemetry = {
    "temperature_deg_C":0,
    "battery_percentage":0,
    "battery_voltage":0,
    "battery_current":0,
    "battery_status": "Not_Available",
    "accel_x_mGs":0,
    "accel_y_mGs":0,
    "accel_z_mGs":0,
    "gyro_x_dps":0,
    "gyro_y_dps":0,
    "gyro_z_dps":0,
    "magnet_x_mGa":0,
    "magnet_y_mGa":0,
    "magnet_z_mGa":0,
    "pressure_mBar":0
}


temperature_pressure_characteristic = "00140000-0001-11e1-ac36-0002a5d5c51b"
accel_gyro_magnet_characteristic =  "00e00000-0001-11e1-ac36-0002a5d5c51b"
battery_characteristic = "00020000-0001-11e1-ac36-0002a5d5c51b"


def setup_bluetooth():
    setup_process = pexpect.spawn('bluetoothctl', encoding='utf-8')
    setup_process.expect('#')
    setup_process.sendline('power off')
    time.sleep(1)
    setup_process.sendline('power on')
    time.sleep(1)
    setup_process.close()


def temperature_pressure_data_handler(characteristic: BleakGATTCharacteristic, data:bytearray):
    global telemetry
    try:
        telemetry["pressure_mBar"] = int.from_bytes(data[2:6], "little")/100.0
        telemetry["temperature_deg_C"] = int.from_bytes(data[6:8], "little")/10.0
    except Exception as ex:
        debug_print_to_file("temperature_pressure_data_handler exception: " + str(ex))
        debug_print_to_file(str(traceback.format_exc()))


def battery_data_handler(characteristic: BleakGATTCharacteristic, data:bytearray):
    global telemetry
    try:
        telemetry["battery_percentage"] = int.from_bytes(data[2:4], "little")/10.0
        telemetry["battery_voltage"] = int.from_bytes(data[4:6], "little")/1000.0
        telemetry["battery_current"] = int.from_bytes(data[6:8], "little")
        status_options = ["Low Battery", "Discharging", "Plugged not Charging", "Charging", "Unknown"]
        telemetry["battery_status"] = status_options[data[8]]
    except Exception as ex:
        debug_print_to_file("battery_data_handler exception: " + str(ex))
        debug_print_to_file(str(traceback.format_exc()))	


def accel_gyro_magnet_data_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    global telemetry
    try:
        telemetry["accel_x_mGs"] = int.from_bytes(data[2:4], "little", signed=True)
        telemetry["accel_y_mGs"] = int.from_bytes(data[4:6], "little", signed=True)
        telemetry["accel_z_mGs"] = int.from_bytes(data[6:8], "little", signed=True)
        telemetry["gyro_x_dps"] = int.from_bytes(data[8:10], "little", signed=True)
        telemetry["gyro_y_dps"] = int.from_bytes(data[10:12], "little", signed=True)
        telemetry["gyro_z_dps"] = int.from_bytes(data[12:14], "little", signed=True)
        telemetry["magnet_x_mGa"] = int.from_bytes(data[14:16], "little", signed=True)
        telemetry["magnet_y_mGa"] = int.from_bytes(data[16:18], "little", signed=True)
        telemetry["magnet_z_mGa"] = int.from_bytes(data[18:20], "little", signed=True)
    except Exception as ex:
        debug_print_to_file("accel_gyro_magnet_data_handler exception: " + str(ex))
        debug_print_to_file(str(traceback.format_exc()))


async def mkboxpro_setup():
    setup_bluetooth()
    print('starting scan...')
    device = await BleakScanner.find_device_by_name("BLEPnP")
    if device is None:
        print('ERROR: could not find MKBOXPRO device')
        return
    print('Connecting to device...')
    async with BleakClient(device) as client:
        print('Connected')
        await client.start_notify(accel_gyro_magnet_characteristic, accel_gyro_magnet_data_handler)
        await client.start_notify(temperature_pressure_characteristic, temperature_pressure_data_handler)
        await client.start_notify(battery_characteristic, battery_data_handler)
        while True:
            await asyncio.sleep(1)


def mkboxpro_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(proteus_setup())
    loop.close()


try:
    device_config = DeviceConfig.from_iotc_device_config_json_file(
        device_config_json_path='iotcDeviceConfig.json',
        device_cert_path='device-cert.pem',
        device_pkey_path='device-pkey.pem'
    )

    c = Client(
        config=device_config,
        callbacks=Callbacks(
            ota_cb=on_ota,
            command_cb=on_command,
            disconnected_cb=on_disconnect
        )
    )
    mkboxpro_thread = threading.Thread(target=mkboxpro_loop)
    mkboxpro_thread.start()
    while True:
        if not c.is_connected():
            print('(re)connecting...')
            c.connect()
            if not c.is_connected():
                print('Unable to connect. Exiting.')
                if mkboxpro_thread and mkboxpro_thread.is_alive():
                    mkboxpro_thread.join()
                sys.exit(2)

        c.send_telemetry(telemetry)
        time.sleep(3)

except Exception as e:
    print(e)
    if mkboxpro_thread and mkboxpro_thread.is_alive():
        mkboxpro_thread.join()
    sys.exit(1)

except KeyboardInterrupt:
    print('Exiting.')
    if mkboxpro_thread and mkboxpro_thread.is_alive():
        mkboxpro_thread.join()
    sys.exit(0)

