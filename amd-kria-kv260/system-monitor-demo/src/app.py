# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

import argparse
import json
import os
import random
import subprocess
import sys
import threading
import time
import urllib.request

try:
    import requests
    from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks, DeviceConfigError
    from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
    from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dOta
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False
    SDK_VERSION = 'unavailable'

HWMON_ROOT = '/sys/class/hwmon'
XMUTIL = '/usr/bin/xmutil'

client = None
restart_pending = threading.Event()

# --- System telemetry --------------------------------------------------------

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


def find_hwmon(prefix: str) -> str:
    """Locate the /sys/class/hwmon/hwmonN directory whose name starts with prefix.

    hwmon indexes are not stable across boots or kits, so devices must be found
    by name (e.g. 'ams' for the Zynq UltraScale+ SYSMON, 'ina260' for the SOM
    power monitor, which is ina260_u14 on the K26 starter kits).
    """
    try:
        for entry in sorted(os.listdir(HWMON_ROOT)):
            name_file = os.path.join(HWMON_ROOT, entry, 'name')
            try:
                with open(name_file) as f:
                    if f.read().strip().startswith(prefix):
                        return os.path.join(HWMON_ROOT, entry)
            except OSError:
                continue
    except OSError:
        pass
    return ''


def _read_int(path: str):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def get_som_temps(ams_path: str) -> tuple:
    """SOM die temperatures in C from the AMS/SYSMON hwmon: (PS, remote, PL)."""
    temps = []
    for ch in (1, 2, 3):
        raw = _read_int(os.path.join(ams_path, 'temp%d_input' % ch)) if ams_path else None
        temps.append(round(raw / 1000.0, 1) if raw is not None else 0.0)
    return temps[0], temps[1], temps[2]


def get_som_power(ina_path: str) -> tuple:
    """SOM 5V rail (volts, amps, watts) from the INA260 power monitor."""
    if not ina_path:
        return 0.0, 0.0, 0.0
    mv = _read_int(os.path.join(ina_path, 'in1_input'))
    ma = _read_int(os.path.join(ina_path, 'curr1_input'))
    uw = _read_int(os.path.join(ina_path, 'power1_input'))
    volts = round(mv / 1000.0, 2) if mv is not None else 0.0
    amps = round(ma / 1000.0, 3) if ma is not None else 0.0
    watts = round(uw / 1000000.0, 2) if uw is not None else 0.0
    return volts, amps, watts


def get_board_name() -> str:
    try:
        with open('/proc/device-tree/model') as f:
            model = f.read().strip('\x00').strip()
        for kit in ('KV260', 'KR260', 'KD240'):
            if kit in model.upper():
                return kit.lower()
        return model
    except OSError:
        return 'unknown'


# --- Accelerator app management (xmutil front end for dfx-mgr) ---------------

def run_xmutil(*args) -> tuple:
    """Run xmutil, via passwordless sudo when not root. Returns (ok, output).

    sudo -n fails fast instead of hanging on a password prompt; install.sh sets
    up the /etc/sudoers.d/99-iotc-xmutil rule that makes it succeed.
    """
    if os.geteuid() == 0:
        cmd = [XMUTIL] + list(args)
    else:
        # Wrap xmutil in a root-owned timeout(1): the unprivileged app cannot
        # signal a root sudo child, so subprocess.run's own timeout could not
        # kill a wedged xmutil and would hang forever on Popen cleanup.
        cmd = ['sudo', '-n', '/usr/bin/timeout', '-k', '5', '115', XMUTIL] + list(args)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output


def get_app_state() -> tuple:
    """Parse 'xmutil listapps' into (loaded_app, installed_apps).

    listapps rows end with 'slot->handle' pairs such as '0->0,' for a loaded
    accelerator and '-1' for an installed but unloaded one.
    """
    ok, output = run_xmutil('listapps')
    if not ok:
        return 'unavailable', []
    loaded = 'none'
    installed = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 3 or fields[0] == 'Accelerator':
            continue
        name = fields[0]
        installed.append(name)
        if '->' in fields[-1]:
            loaded = name
    return loaded, installed


# --- Telemetry collection ----------------------------------------------------

def collect_telemetry(ams_path: str, ina_path: str, board: str) -> dict:
    cpu = get_cpu_percent()
    mem = get_memory_percent()
    temp_ps, temp_rem, temp_pl = get_som_temps(ams_path)
    volts, amps, watts = get_som_power(ina_path)
    loaded, installed = get_app_state()
    return {
        'sdk_version': SDK_VERSION,
        'board': board,
        'cpu_percent': cpu,
        'memory_percent': mem,
        'som_temp_ps_c': temp_ps,
        'som_temp_rem_c': temp_rem,
        'som_temp_pl_c': temp_pl,
        'som_voltage_v': volts,
        'som_current_a': amps,
        'som_power_w': watts,
        'loaded_app': loaded,
        'apps_installed': json.dumps(installed),
        'random': random.randint(0, 100)
    }


# --- OTA / file-download handling --------------------------------------------

def extract_and_run_tar_gz(targz_filename: str) -> bool:
    try:
        subprocess.run(('tar', '-xzvf', targz_filename, '--overwrite'), check=True)
        script = os.path.join(os.getcwd(), 'install.sh')
        if os.path.isfile(script):
            try:
                # Detach stdin and flag the OTA context so install.sh never
                # waits on an interactive sudo password prompt.
                subprocess.run(['bash', script], check=True, stdin=subprocess.DEVNULL,
                               env=dict(os.environ, IOTC_OTA='1'))
                os.remove(script)
                print('Successfully executed install.sh')
                return True
            except subprocess.CalledProcessError as e:
                os.remove(script)
                print('Error executing install.sh: %s' % e)
                return False
        return True
    except subprocess.CalledProcessError:
        return False


def restart_app():
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable, __file__] + sys.argv[1:])


# --- Cloud-to-device commands --------------------------------------------------

def on_command(msg):
    print('Received command', msg.command_name, msg.command_args, msg.ack_id)
    args = msg.command_args or []

    if msg.command_name == 'list-apps':
        loaded, installed = get_app_state()
        if loaded == 'unavailable':
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'xmutil unavailable; see install.sh sudoers note')
        else:
            status = 'loaded=%s installed=%s' % (loaded, ','.join(installed) if installed else 'none')
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status)

    elif msg.command_name == 'load-app':
        if len(args) != 1 or not args[0].strip():
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Expected 1 argument: accelerator app name')
            return
        target = args[0].strip()
        loaded, installed = get_app_state()
        if loaded == 'unavailable':
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'xmutil unavailable; see install.sh sudoers note')
            return
        if target not in installed:
            client.send_command_ack(msg, C2dAck.CMD_FAILED,
                                    'Unknown app %s; installed: %s' % (target, ','.join(installed) or 'none'))
            return
        if target == loaded:
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, '%s is already loaded' % target)
            return
        if loaded != 'none':
            ok, output = run_xmutil('unloadapp')
            if not ok:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, 'unloadapp failed: %s' % output)
                return
        ok, output = run_xmutil('loadapp', target)
        if ok:
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, 'Loaded %s' % target)
        else:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'loadapp failed: %s' % output)

    elif msg.command_name == 'unload-app':
        loaded, _ = get_app_state()
        if loaded == 'unavailable':
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'xmutil unavailable; see install.sh sudoers note')
            return
        if loaded == 'none':
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, 'No app was loaded')
            return
        ok, output = run_xmutil('unloadapp')
        if ok:
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, 'Unloaded %s' % loaded)
        else:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'unloadapp failed: %s' % output)

    elif msg.command_name == 'file-download':
        if len(args) == 1:
            url = args[0]
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    with open('package.tar.gz', 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    print('File downloaded successfully')
                    if extract_and_run_tar_gz('package.tar.gz'):
                        client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, 'Downloaded and applied %s' % url)
                        print('OTA package applied. Restart scheduled...')
                        # Restart from the main loop: exec'ing here would drop
                        # the queued ack before the network thread sends it.
                        restart_pending.set()
                    else:
                        client.send_command_ack(msg, C2dAck.CMD_FAILED,
                                                'Package extract or install.sh failed; not restarting')
                else:
                    status = 'Download failed: HTTP %d' % response.status_code
                    print(status)
                    client.send_command_ack(msg, C2dAck.CMD_FAILED, status)
            except Exception as e:
                status = 'Download error: %s' % e
                print(status)
                client.send_command_ack(msg, C2dAck.CMD_FAILED, status)
        else:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Expected 1 argument')

    else:
        print('Command %s not implemented!' % msg.command_name)
        if msg.ack_id is not None:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Not Implemented')


def on_ota(msg):
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
        print('OTA successful. Restart scheduled...')
        client.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_DONE)
        restart_pending.set()
    else:
        print('Encountered a download processing error. Not restarting.')
        client.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_FAILED, 'OTA download or extraction failed')


def on_disconnect(reason: str, disconnected_from_server: bool):
    print('Disconnected. Reason: %s' % reason)


# --- Main ---------------------------------------------------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='IOTCONNECT Kria system and accelerator monitor')
    parser.add_argument('--dry-run', action='store_true',
                        help='print one telemetry sample as JSON and exit without connecting')
    cli = parser.parse_args()

    ams_path = find_hwmon('ams')
    ina_path = find_hwmon('ina260')
    board = get_board_name()
    if not ams_path:
        print('WARNING: AMS/SYSMON hwmon device not found; temperatures will read 0.')
    if not ina_path:
        print('WARNING: INA260 hwmon device not found; SOM power will read 0.')

    if cli.dry_run:
        print(json.dumps(collect_telemetry(ams_path, ina_path, board), indent=2))
        sys.exit(0)

    if not SDK_AVAILABLE:
        print('iotconnect-sdk-lite is not installed. Run: '
              'python3 -m pip install iotconnect-sdk-lite requests --break-system-packages')
        sys.exit(1)

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
            if restart_pending.is_set():
                print('Applying update: restarting after ack flush...')
                time.sleep(2)
                restart_app()

            if not client.is_connected():
                print('(re)connecting...')
                client.connect()
                if not client.is_connected():
                    print('Unable to connect. Exiting.')
                    sys.exit(2)

            telemetry = collect_telemetry(ams_path, ina_path, board)
            print('Telemetry: cpu=%s%% mem=%s%% ps=%sC power=%sW app=%s' % (
                telemetry['cpu_percent'], telemetry['memory_percent'],
                telemetry['som_temp_ps_c'], telemetry['som_power_w'],
                telemetry['loaded_app']))
            client.send_telemetry(telemetry)
            time.sleep(10)

    except KeyboardInterrupt:
        print('Exiting.')
        client.disconnect()
        sys.exit(0)
