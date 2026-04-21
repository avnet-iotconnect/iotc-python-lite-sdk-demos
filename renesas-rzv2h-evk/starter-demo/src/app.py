# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

import random
import sys
import time
import subprocess
import os
import urllib.request
import requests

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dOta

client: Client = None

# ─── System monitoring ───────────────────────────────────────────────────────

def _read_proc_stat():
    with open('/proc/stat') as f:
        fields = f.readline().split()
    idle = int(fields[4])
    total = sum(int(x) for x in fields[1:])
    return idle, total


def get_cpu_percent() -> float:
    idle1, total1 = _read_proc_stat()
    time.sleep(0.2)
    idle2, total2 = _read_proc_stat()
    delta_total = total2 - total1
    if delta_total == 0:
        return 0.0
    return round(100.0 * (1.0 - (idle2 - idle1) / delta_total), 1)


def get_memory_percent() -> float:
    info = {}
    with open('/proc/meminfo') as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                info[parts[0].rstrip(':')] = int(parts[1])
    total = info.get('MemTotal', 1)
    available = info.get('MemAvailable', total)
    return round(100.0 * (total - available) / total, 1)


def get_cpu_temps() -> tuple:
    temps = []
    for i in range(2):
        try:
            with open(f'/sys/class/thermal/thermal_zone{i}/temp') as f:
                temps.append(round(int(f.read().strip()) / 1000.0, 1))
        except Exception:
            temps.append(0.0)
    while len(temps) < 2:
        temps.append(0.0)
    return temps[0], temps[1]


# ─── OTA / file-download handling ────────────────────────────────────────────

def extract_and_run_tar_gz(targz_filename: str) -> bool:
    try:
        subprocess.run(('tar', '-xzvf', targz_filename, '--overwrite'), check=True)
        script = os.path.join(os.getcwd(), 'install.sh')
        if os.path.isfile(script):
            try:
                subprocess.run(['bash', script], check=True)
                os.remove(script)
                print('Successfully executed install.sh')
                return True
            except subprocess.CalledProcessError as e:
                os.remove(script)
                print(f'Error executing install.sh: {e}')
                return False
        return True
    except subprocess.CalledProcessError:
        return False


def on_command(msg: C2dCommand):
    print('Received command', msg.command_name, msg.command_args, msg.ack_id)
    if msg.command_name == 'file-download':
        if len(msg.command_args) == 1:
            status_message = 'Downloading %s to device' % msg.command_args[0]
            response = requests.get(msg.command_args[0])
            if response.status_code == 200:
                with open('package.tar.gz', 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print('File downloaded successfully and saved to package.tar.gz')
            else:
                print(f'Failed to download the file. Status code: {response.status_code}')
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status_message)
            print(status_message)
            extract_and_run_tar_gz('package.tar.gz')
            print('Download command successful. Will restart the application...')
            sys.stdout.flush()
            os.execv(sys.executable, [sys.executable, __file__] + sys.argv[1:])
        else:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Expected 1 argument')
    else:
        print('Command %s not implemented!' % msg.command_name)
        if msg.ack_id is not None:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Not Implemented')


def on_ota(msg: C2dOta):
    print('Starting OTA downloads for version %s' % msg.version)
    client.send_ota_ack(msg, C2dAck.OTA_DOWNLOADING)
    extraction_success = False
    for url in msg.urls:
        print('Downloading OTA file %s from %s' % (url.file_name, url.url))
        try:
            urllib.request.urlretrieve(url.url, url.file_name)
        except Exception as e:
            print('Encountered download error', e)
            break
        if url.file_name.endswith('.tar.gz'):
            extraction_success = extract_and_run_tar_gz(url.file_name)
            if not extraction_success:
                break
        else:
            print('ERROR: Unhandled file format for file %s' % url.file_name)
    if extraction_success:
        print('OTA successful. Will restart the application...')
        client.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_DONE)
        sys.stdout.flush()
        os.execv(sys.executable, [sys.executable, __file__] + sys.argv[1:])
    else:
        print('Encountered a download processing error. Not restarting.')


def on_disconnect(reason: str, disconnected_from_server: bool):
    print(f'Disconnected. Reason: {reason}')


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    try:
        device_config = DeviceConfig.from_iotc_device_config_json_file(
            device_config_json_path='iotcDeviceConfig.json',
            device_cert_path='device-cert.pem',
            device_pkey_path='device-pkey.pem'
        )
    except DeviceConfigError as e:
        print(e)
        sys.exit(1)

    client = Client(
        config=device_config,
        callbacks=Callbacks(
            ota_cb=on_ota,
            command_cb=on_command,
            disconnected_cb=on_disconnect
        )
    )

    try:
        while True:
            if not client.is_connected():
                print('(re)connecting...')
                client.connect()
                if not client.is_connected():
                    print('Unable to connect. Exiting.')
                    sys.exit(2)

            cpu = get_cpu_percent()
            mem = get_memory_percent()
            temp0, temp1 = get_cpu_temps()

            telemetry = {
                'sdk_version': SDK_VERSION,
                'cpu_percent': cpu,
                'memory_percent': mem,
                'cpu_temp_0_c': temp0,
                'cpu_temp_1_c': temp1,
                'random': random.randint(0, 100)
            }
            print(f'Telemetry: cpu={cpu}% mem={mem}% temp0={temp0}°C temp1={temp1}°C')
            client.send_telemetry(telemetry)
            time.sleep(10)

    except KeyboardInterrupt:
        print('Exiting.')
        client.disconnect()
        sys.exit(0)
