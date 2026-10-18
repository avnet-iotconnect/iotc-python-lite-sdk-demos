# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

import argparse
import json
import os
import random
import socket
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

try:
    import cv2
    import numpy as np
    CV_AVAILABLE = True
except ImportError:
    CV_AVAILABLE = False

HWMON_ROOT = '/sys/class/hwmon'
BRIDGE_UDP_PORT = 5577       # ros2_bridge.py sends topic data here
BRIDGE_CMD_PORT = 5578       # ros2-call requests are forwarded here
BRIDGE_STALE_S = 30.0

client = None
restart_pending = threading.Event()

# --- System telemetry ---------------------------------------------------------

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
    try:
        for entry in sorted(os.listdir(HWMON_ROOT)):
            try:
                with open(os.path.join(HWMON_ROOT, entry, 'name')) as f:
                    if f.read().strip().startswith(prefix):
                        return os.path.join(HWMON_ROOT, entry)
            except OSError:
                continue
    except OSError:
        pass
    return ''


def get_ps_temp(ams_path: str) -> float:
    if not ams_path:
        return 0.0
    try:
        with open(os.path.join(ams_path, 'temp1_input')) as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except (OSError, ValueError):
        return 0.0


# --- Camera and inspection ----------------------------------------------------

class Inspector:
    """Reference-image inspection: capture a golden reference of the ROI, then
    score each inspection as the normalized mean absolute difference (0..1)
    between the current ROI and the reference. score <= threshold is a pass.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.cap = None
        self.camera_index = -1
        self.reference = None
        self.threshold = 0.15
        self.roi = None          # (x, y, w, h) or None for full frame
        self.active = False
        self.pass_count = 0
        self.fail_count = 0
        self.last_result = 'none'
        self.last_score = 0.0
        self.cycle_ms = 0.0
        self.fps = 0.0

    # camera -------------------------------------------------------------

    def _open_camera_locked(self) -> bool:
        if self.cap is not None and self.cap.isOpened():
            # isOpened() is a cached flag that stays true after an unplug;
            # grab() touches the device, so a dead camera is noticed here and
            # the rescan below handles a replug.
            if self.cap.grab():
                return True
            self.cap.release()
            self.cap = None
            self.camera_index = -1
        for idx in range(4):
            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            ok, frame = cap.read()
            # Require a plausible BGR image so a metadata node (such as the
            # C920's second /dev/video device) is never adopted as the camera.
            if ok and frame is not None and getattr(frame, 'ndim', 0) == 3 \
                    and frame.shape[0] >= 120 and frame.shape[1] >= 160:
                self.cap = cap
                self.camera_index = idx
                return True
            cap.release()
        self.cap = None
        self.camera_index = -1
        return False

    def _grab_locked(self):
        if not self._open_camera_locked():
            return None
        # read twice to drop a potentially stale buffered frame
        self.cap.read()
        ok, frame = self.cap.read()
        if not ok or frame is None:
            self.cap.release()
            self.cap = None
            return None
        return frame

    def camera_connected(self) -> bool:
        with self.lock:
            return self._open_camera_locked()

    # inspection ---------------------------------------------------------

    def _roi_gray_locked(self, frame):
        if self.roi is not None:
            x, y, w, h = self.roi
            fh, fw = frame.shape[:2]
            x = max(0, min(x, fw - 1))
            y = max(0, min(y, fh - 1))
            w = max(1, min(w, fw - x))
            h = max(1, min(h, fh - y))
            frame = frame[y:y + h, x:x + w]
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    def capture_reference(self) -> tuple:
        with self.lock:
            try:
                frame = self._grab_locked()
                if frame is None:
                    return False, 'camera not available'
                self.reference = self._roi_gray_locked(frame)
                return True, 'reference captured (%dx%d)' % (self.reference.shape[1], self.reference.shape[0])
            except Exception as e:
                return False, 'capture error: %s' % e

    def set_roi(self, arg: str) -> tuple:
        with self.lock:
            arg = arg.strip().lower()
            if arg == 'full':
                self.roi = None
                self.reference = None
                return True, 'ROI reset to full frame; capture a new reference'
            try:
                x, y, w, h = (int(v) for v in arg.split(','))
                if w <= 0 or h <= 0 or x < 0 or y < 0:
                    raise ValueError
            except ValueError:
                return False, 'expected "x,y,w,h" with positive w,h or "full"'
            self.roi = (x, y, w, h)
            self.reference = None
            return True, 'ROI set to %d,%d,%d,%d; capture a new reference' % (x, y, w, h)

    def inspect(self) -> tuple:
        """Run one inspection. Returns (result, score)."""
        start = time.monotonic()
        with self.lock:
            if self.reference is None:
                self.last_result = 'no_reference'
                return self.last_result, 0.0
            try:
                frame = self._grab_locked()
                if frame is None:
                    self.last_result = 'error'
                    return self.last_result, 0.0
                gray = self._roi_gray_locked(frame)
                if gray.shape != self.reference.shape:
                    self.last_result = 'no_reference'
                    return self.last_result, 0.0
                score = float(np.mean(cv2.absdiff(gray, self.reference))) / 255.0
            except Exception as e:
                print('inspection error: %s' % e)
                self.last_result = 'error'
                return self.last_result, 0.0
            self.last_score = round(score, 4)
            if score <= self.threshold:
                self.last_result = 'pass'
                self.pass_count += 1
            else:
                self.last_result = 'fail'
                self.fail_count += 1
            elapsed = time.monotonic() - start
            self.cycle_ms = round(elapsed * 1000.0, 1)
            self.fps = round(1.0 / elapsed, 1) if elapsed > 0 else 0.0
            return self.last_result, self.last_score

    def yield_percent(self) -> float:
        total = self.pass_count + self.fail_count
        if total == 0:
            return 0.0
        return round(100.0 * self.pass_count / total, 1)


inspector = Inspector() if CV_AVAILABLE else None

# --- Optional ROS 2 bridge ingest ----------------------------------------------

bridge_state = {'data': {}, 'last_seen': 0.0}


def bridge_listener():
    """Receive JSON datagrams from ros2_bridge.py on localhost."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while True:
        try:
            sock.bind(('127.0.0.1', BRIDGE_UDP_PORT))
            break
        except OSError as e:
            print('bridge listener: bind failed (%s); retrying in 10 s' % e)
            time.sleep(10)
    while True:
        try:
            payload, _ = sock.recvfrom(4096)
            data = json.loads(payload.decode('utf-8'))
            if isinstance(data, dict):
                bridge_state['data'].update(data)
                bridge_state['last_seen'] = time.monotonic()
        except (ValueError, UnicodeDecodeError):
            continue
        except OSError:
            time.sleep(1)


def bridge_active() -> bool:
    return (time.monotonic() - bridge_state['last_seen']) < BRIDGE_STALE_S if bridge_state['last_seen'] else False


def bridge_forward(command: str) -> bool:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(command.encode('utf-8'), ('127.0.0.1', BRIDGE_CMD_PORT))
        sock.close()
        return True
    except OSError:
        return False


# --- Telemetry collection -------------------------------------------------------

def collect_telemetry(ams_path: str) -> dict:
    cam_ok = inspector.camera_connected() if inspector else False
    return {
        'sdk_version': SDK_VERSION,
        'cpu_percent': get_cpu_percent(),
        'memory_percent': get_memory_percent(),
        'som_temp_ps_c': get_ps_temp(ams_path),
        'camera_connected': cam_ok,
        'camera_kind': 'usb' if cam_ok else 'none',
        'inspection_active': inspector.active if inspector else False,
        'last_result': inspector.last_result if inspector else 'error',
        'last_score': inspector.last_score if inspector else 0.0,
        'pass_count': inspector.pass_count if inspector else 0,
        'fail_count': inspector.fail_count if inspector else 0,
        'yield_percent': inspector.yield_percent() if inspector else 0.0,
        'cycle_time_ms': inspector.cycle_ms if inspector else 0.0,
        'fps': inspector.fps if inspector else 0.0,
        'ros2_bridge_active': bridge_active(),
        'ros2_data': json.dumps(bridge_state['data'])[:512],
        'random': random.randint(0, 100)
    }


# --- OTA / file-download handling -----------------------------------------------

def extract_and_run_tar_gz(targz_filename: str) -> bool:
    try:
        subprocess.run(('tar', '-xzvf', targz_filename, '--overwrite'), check=True)
        script = os.path.join(os.getcwd(), 'install.sh')
        if os.path.isfile(script):
            try:
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
    # Release the camera first: OpenCV's V4L2 fd is opened without O_CLOEXEC,
    # so it would survive execv as an orphan that keeps the device busy and
    # makes the camera unusable in the restarted process.
    if inspector is not None:
        with inspector.lock:
            if inspector.cap is not None:
                inspector.cap.release()
                inspector.cap = None
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable, __file__] + sys.argv[1:])


# --- Cloud-to-device commands -----------------------------------------------------

def on_command(msg):
    print('Received command', msg.command_name, msg.command_args, msg.ack_id)
    args = msg.command_args or []

    if inspector is None and msg.command_name in (
            'start-inspection', 'stop-inspection', 'trigger-inspection',
            'capture-reference', 'reset-counters', 'set-roi', 'set-threshold'):
        client.send_command_ack(msg, C2dAck.CMD_FAILED, 'OpenCV is not installed; re-run install.sh')
        return

    if msg.command_name == 'start-inspection':
        if inspector.reference is None:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'No reference captured; send capture-reference first')
            return
        inspector.active = True
        client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, 'Inspection started')

    elif msg.command_name == 'stop-inspection':
        inspector.active = False
        client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, 'Inspection stopped')

    elif msg.command_name == 'trigger-inspection':
        result, score = inspector.inspect()
        if result in ('pass', 'fail'):
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, '%s (score %.4f)' % (result, score))
        else:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, result)

    elif msg.command_name == 'capture-reference':
        ok, detail = inspector.capture_reference()
        ack = C2dAck.CMD_SUCCESS_WITH_ACK if ok else C2dAck.CMD_FAILED
        client.send_command_ack(msg, ack, detail)

    elif msg.command_name == 'reset-counters':
        inspector.pass_count = 0
        inspector.fail_count = 0
        inspector.last_result = 'none'
        inspector.last_score = 0.0
        client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, 'Counters reset')

    elif msg.command_name == 'set-roi':
        if len(args) != 1 or not args[0].strip():
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Expected 1 argument: "x,y,w,h" or "full"')
            return
        ok, detail = inspector.set_roi(args[0])
        ack = C2dAck.CMD_SUCCESS_WITH_ACK if ok else C2dAck.CMD_FAILED
        client.send_command_ack(msg, ack, detail)

    elif msg.command_name == 'set-threshold':
        try:
            value = float(args[0])
            if not 0.0 <= value <= 1.0:
                raise ValueError
        except (ValueError, IndexError):
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Expected a number between 0.0 and 1.0')
            return
        inspector.threshold = value
        client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, 'Threshold set to %.3f' % value)

    elif msg.command_name == 'ros2-call':
        if len(args) != 1 or not args[0].strip():
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Expected 1 argument: "<service> <json-args>"')
            return
        if not bridge_active():
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'ROS 2 bridge is not active')
            return
        if bridge_forward(args[0]):
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, 'Forwarded to ROS 2 bridge')
        else:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Could not reach the bridge socket')

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


# --- Main -------------------------------------------------------------------------

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='IOTCONNECT KR260 inspection cell demo')
    parser.add_argument('--dry-run', action='store_true',
                        help='capture a reference, run one inspection, print telemetry JSON, and exit')
    cli = parser.parse_args()

    if not CV_AVAILABLE:
        print('WARNING: OpenCV/numpy not installed; camera features disabled. Run install.sh.')

    ams_path = find_hwmon('ams')

    if cli.dry_run:
        if inspector:
            ok, detail = inspector.capture_reference()
            print('capture-reference: %s (%s)' % (ok, detail))
            if ok:
                result, score = inspector.inspect()
                print('inspect: %s (score %.4f)' % (result, score))
        print(json.dumps(collect_telemetry(ams_path), indent=2))
        sys.exit(0)

    if not SDK_AVAILABLE:
        print('iotconnect-sdk-lite is not installed. Run: '
              'python3 -m pip install iotconnect-sdk-lite requests --break-system-packages')
        sys.exit(1)

    # Started only in connected mode so a dry run never contends for the port
    # with a running instance.
    threading.Thread(target=bridge_listener, daemon=True).start()

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

            if inspector and inspector.active:
                inspector.inspect()

            telemetry = collect_telemetry(ams_path)
            print('Telemetry: cam=%s active=%s result=%s score=%s pass=%d fail=%d' % (
                telemetry['camera_connected'], telemetry['inspection_active'],
                telemetry['last_result'], telemetry['last_score'],
                telemetry['pass_count'], telemetry['fail_count']))
            client.send_telemetry(telemetry)
            time.sleep(5)

    except KeyboardInterrupt:
        print('Exiting.')
        client.disconnect()
        sys.exit(0)
