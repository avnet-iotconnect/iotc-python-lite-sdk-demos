# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

"""RZ/V2H EVK AI Demo for /IOTCONNECT

This application:
  - Connects to /IOTCONNECT and streams telemetry every 10 seconds
  - Runs Python OpenCV-based face/body detection on the USB camera
  - Launches and manages Renesas DRP-AI hardware demo binaries as subprocesses
    (these render object-detection results on the HDMI display)
  - Reports inference metrics and system performance data to the cloud
  - Accepts C2D commands to start/stop inference and control DRP-AI demos
"""

import sys
import time
import random
import subprocess
import signal
import os
import json
import threading
import queue
import urllib.request
import requests
import traceback
from typing import Optional

import cv2
import system_monitor

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, C2dOta, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck

# ─── DRP-AI demo configuration ───────────────────────────────────────────────
# These map the C2D command parameter to the pre-built AI binary on the board.
# Binaries are part of the Renesas RZ/V2H AI SDK demo set.
DRPAI_DEMOS = {
    # Q08 — Object Counter (three modes, one binary)
    'coco': {
        'dir': '/home/weston/tvm_q08',
        'cmd': './object_counter', 'args': ['COCO', 'USB'],
        'name': 'Q08 Object Counter — COCO (80 classes)',
        'results_file': '/tmp/drpai_results.json', 'kind': 'object_counter',
    },
    'animal': {
        'dir': '/home/weston/tvm_q08',
        'cmd': './object_counter', 'args': ['animal', 'USB'],
        'name': 'Q08 Object Counter — Animals',
        'results_file': '/tmp/drpai_results.json', 'kind': 'object_counter',
    },
    'vehicle': {
        'dir': '/home/weston/tvm_q08',
        'cmd': './object_counter', 'args': ['vehicle', 'USB'],
        'name': 'Q08 Object Counter — Vehicles',
        'results_file': '/tmp/drpai_results.json', 'kind': 'object_counter',
    },
    # Q13 — Analog Meter Reader (dual-model YOLOX + U-Net)
    'meter': {
        'dir': '/home/weston/Q13_analog_meter_reader/exe_v2h',
        'cmd': './analog_reader', 'args': ['USB'],
        'name': 'Q13 Analog Meter Reader',
        'results_file': '/tmp/q13_results.json', 'kind': 'meter',
    },
    # Q01 — Footfall Counter
    'footfall': {
        'dir': '/home/weston/Q01_footfall_counter/exe_v2h',
        'cmd': './object_tracker', 'args': ['USB'],
        'name': 'Q01 Footfall Counter',
        'results_file': '/tmp/drpai_q01_results.json', 'kind': 'detector',
    },
    # Q02 — Face Authentication (mouse-driven UI; telemetry = process state only)
    'face_auth': {
        'dir': '/home/weston/Q02_face_authentication/exe_v2h',
        'cmd': './face_recognition', 'args': ['USB'],
        'name': 'Q02 Face Authentication',
        'results_file': '', 'kind': 'ui_only',
    },
    # Q03 Smart Parking is RZ/V2L-only — Renesas does not ship a V2H deploy.so.
    # Q04 — Fish Classification
    'fish_class': {
        'dir': '/home/weston/Q04_fish_classification/exe_v2h',
        'cmd': './fish_classification', 'args': ['USB'],
        'name': 'Q04 Fish Classification',
        'results_file': '/tmp/drpai_q04_results.json', 'kind': 'classifier',
    },
    # Q05 — Suspicious Activity (CNN + MLP)
    'activity': {
        'dir': '/home/weston/Q05_suspicious_activity/exe_v2h',
        'cmd': './suspicious_activity', 'args': ['USB'],
        'name': 'Q05 Suspicious Activity',
        'results_file': '/tmp/drpai_q05_results.json', 'kind': 'activity',
    },
    # Q06 — Expiry Date Detection (OCR; telemetry = process state only)
    'expiry': {
        'dir': '/home/weston/Q06_expiry_date_detection/exe_v2h',
        'cmd': './date_extraction', 'args': ['USB'],
        'name': 'Q06 Expiry Date Detection',
        'results_file': '', 'kind': 'ui_only',
    },
    # Q07 — Plant Disease Classification
    'plant': {
        'dir': '/home/weston/Q07_plant_disease_classification/exe_v2h',
        'cmd': './plant_leaf_disease_classify', 'args': ['USB'],
        'name': 'Q07 Plant Disease Classification',
        'results_file': '/tmp/drpai_q07_results.json', 'kind': 'classifier',
    },
    # Q09 — Crack Segmentation (U-Net)
    'crack': {
        'dir': '/home/weston/Q09_crack_segmentation/exe_v2h',
        'cmd': './crack_segmentation', 'args': ['USB'],
        'name': 'Q09 Crack Segmentation',
        'results_file': '/tmp/drpai_q09_results.json', 'kind': 'segmentation',
    },
    # Q10 — Suspicious Person Detection
    'suspicious': {
        'dir': '/home/weston/Q10_suspicious_person_detection/exe_v2h',
        'cmd': './suspicious_person_detector', 'args': ['USB'],
        'name': 'Q10 Suspicious Person Detection',
        'results_file': '/tmp/drpai_q10_results.json', 'kind': 'detector',
    },
    # Q11 — Fish Detection
    'fish_det': {
        'dir': '/home/weston/Q11_fish_detection/exe_v2h',
        'cmd': './fish_detector', 'args': ['USB'],
        'name': 'Q11 Fish Detection',
        'results_file': '/tmp/drpai_q11_results.json', 'kind': 'detector',
    },
    # Q12 — Yoga Pose Estimation (keypoint + classifier)
    'yoga': {
        'dir': '/home/weston/Q12_yoga_pose_estimation/exe_v2h',
        'cmd': './pose_estimator', 'args': ['USB'],
        'name': 'Q12 Yoga Pose Estimation',
        'results_file': '/tmp/drpai_q12_results.json', 'kind': 'pose',
    },
    # R01 — Generic Object Detection (YOLOv3)
    'r01': {
        'dir': '/home/weston/R01_object_detection/exe_v2h',
        'cmd': './object_detection', 'args': [],
        'name': 'R01 Object Detection',
        'results_file': '/tmp/drpai_r01_results.json', 'kind': 'detector',
    },
}

# ─── Global state ─────────────────────────────────────────────────────────────
client: Client = None
_drpai_proc: Optional[subprocess.Popen] = None
_drpai_name: str = ''
_drpai_kind: str = ''          # 'object_counter' | 'meter' | ''
_drpai_results_file: str = ''  # absolute path set when a demo is launched
_drpai_lock = threading.Lock()

_cv_active = False
_cv_thread: Optional[threading.Thread] = None
_cv_device: str = ''  # camera node the CV thread actually opened
_cv_result = {
    'face_count': 0,
    'person_count': 0,
    'inference_time_ms': 0.0,
    'total_detections': 0,
    'confidence_threshold': 1.1,  # Haar scale-factor multiplier (unused in threshold sense)
}
_cv_lock = threading.Lock()
_cv_confidence = 0.5  # kept for future DNN model upgrade path


# ─── Wayland environment detection ────────────────────────────────────────────

def _find_wayland_env() -> dict:
    """Locate the active Wayland socket and return the required env vars.

    The weston compositor on RZ/V2H Yocto runs as a non-root user whose
    XDG_RUNTIME_DIR contains the wayland-1 socket. We search /run/user/ to
    find it rather than hard-coding the UID.
    """
    try:
        for uid in os.listdir('/run/user'):
            sock = f'/run/user/{uid}/wayland-1'
            if os.path.exists(sock):
                return {
                    'WAYLAND_DISPLAY': 'wayland-1',
                    'XDG_RUNTIME_DIR': f'/run/user/{uid}',
                }
    except Exception:
        pass
    return {}


# ─── DRP-AI demo subprocess management ────────────────────────────────────────

def _drain_pipe(label: str, pipe):
    """Drain a subprocess pipe to prevent buffer-full deadlocks."""
    try:
        for line in iter(pipe.readline, b''):
            decoded = line.decode(errors='replace').rstrip()
            if decoded:
                print(f'[DRPAI:{label}] {decoded}')
    except Exception:
        pass
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def start_drpai_demo(mode: str) -> bool:
    global _drpai_proc, _drpai_name, _drpai_kind, _drpai_results_file

    # DRP-AI hardcodes /dev/video0. Stop CV only if it is actually holding
    # video0; if CV is on a different device (two-camera setup) it can keep
    # running in parallel. If a second camera exists, restart CV on it after
    # DRP-AI has claimed video0.
    cv_needs_restart = False
    if _cv_active and (_cv_device == _DRPAI_HARDCODED_CAMERA or _cv_device == ''):
        cv_needs_restart = len(_detect_usb_cameras()) > 1
        print('Stopping Python CV to free /dev/video0 for DRP-AI...')
        stop_cv_inference()
        time.sleep(1.5)  # give the V4L2 device time to fully release

    started = False
    with _drpai_lock:
        if _drpai_proc is not None and _drpai_proc.poll() is None:
            print(f'DRP-AI demo already running ({_drpai_name}). Stop it first.')
            return False

        cfg = DRPAI_DEMOS.get(mode.lower())
        if cfg is None:
            print(f'Unknown DRP-AI mode: {mode}. Available: {list(DRPAI_DEMOS.keys())}')
            return False

        # Clear any stale results from a prior demo before starting
        for stale in {c['results_file'] for c in DRPAI_DEMOS.values()}:
            try:
                os.remove(stale)
            except FileNotFoundError:
                pass
            except Exception:
                pass

        wayland_env = _find_wayland_env()
        if not wayland_env:
            print('WARNING: Could not locate Wayland socket. DRP-AI demo may fail to display.')

        env = {**os.environ, **wayland_env}
        cmd = [cfg['cmd']] + cfg['args']
        print(f'Launching DRP-AI demo: {cfg["name"]} in {cfg["dir"]}')

        try:
            _drpai_proc = subprocess.Popen(
                cmd,
                cwd=cfg['dir'],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
            )
            _drpai_name = cfg['name']
            _drpai_kind = cfg['kind']
            _drpai_results_file = cfg['results_file']

            threading.Thread(target=_drain_pipe, args=('stdout', _drpai_proc.stdout), daemon=True).start()
            threading.Thread(target=_drain_pipe, args=('stderr', _drpai_proc.stderr), daemon=True).start()

            time.sleep(1.5)
            if _drpai_proc.poll() is not None:
                print(f'DRP-AI demo exited immediately (code {_drpai_proc.returncode}).')
                _drpai_proc = None
                _drpai_name = ''
                _drpai_kind = ''
                _drpai_results_file = ''
                return False

            print(f'DRP-AI demo started successfully.')
            started = True
        except Exception as e:
            print(f'Error starting DRP-AI demo: {e}')
            _drpai_proc = None
            _drpai_name = ''
            _drpai_kind = ''
            _drpai_results_file = ''
            return False

    # Two-camera setup: DRP-AI owns video0, restart CV on the second camera
    if started and cv_needs_restart:
        print('Two-camera setup: restarting Python CV on second camera...')
        ok, status = start_cv_inference()
        print(status)

    return started


def stop_drpai_demo() -> bool:
    global _drpai_proc, _drpai_name, _drpai_kind, _drpai_results_file
    with _drpai_lock:
        if _drpai_proc is None:
            print('No DRP-AI demo is running.')
            return False
        results_file = _drpai_results_file
        try:
            os.killpg(os.getpgid(_drpai_proc.pid), signal.SIGTERM)
            _drpai_proc.wait(timeout=5)
        except Exception as e:
            print(f'Error stopping DRP-AI demo: {e}')
        finally:
            _drpai_proc = None
            _drpai_name = ''
            _drpai_kind = ''
            _drpai_results_file = ''
        # Remove the results file so telemetry doesn't report stale data.
        if results_file:
            try:
                os.remove(results_file)
            except FileNotFoundError:
                pass
            except Exception:
                pass
        print('DRP-AI demo stopped.')
        return True


def is_drpai_running() -> bool:
    global _drpai_proc, _drpai_name, _drpai_kind, _drpai_results_file
    with _drpai_lock:
        if _drpai_proc is None:
            return False
        if _drpai_proc.poll() is not None:
            _drpai_proc = None
            _drpai_name = ''
            _drpai_kind = ''
            _drpai_results_file = ''
            return False
        return True


def get_drpai_name() -> str:
    return _drpai_name if is_drpai_running() else ''


def get_drpai_kind() -> str:
    return _drpai_kind if is_drpai_running() else ''


# The IoTConnect-patched DRP-AI binaries rewrite per-frame JSON to these paths.
# Stale or missing files are treated as "no results" instead of errors so the
# telemetry pipeline tolerates demos being stopped/swapped mid-stream.
DRPAI_RESULTS_STALE_SEC = 5


def read_drpai_results(results_file: str = '') -> Optional[dict]:
    """Return the latest DRP-AI inference results for the active demo.

    results_file: explicit path to read. If empty, falls back to the active
    demo's path, or returns None if no demo is active.
    """
    path = results_file or _drpai_results_file
    if not path:
        return None
    try:
        with open(path, 'r') as f:
            data = json.load(f)
        age = time.time() - data.get('timestamp', 0)
        if age > DRPAI_RESULTS_STALE_SEC:
            return None
        return data
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        return None


# ─── Python CV inference (Haar cascade — no downloads required) ───────────────

def _detect_usb_cameras() -> list:
    """Return a list of /dev/videoN — one per distinct USB camera.

    A multi-node camera (e.g. Logitech C920 exposes video0 + video1 via
    separate USB interface nodes like 1-1:1.0 and 1-1:1.1) only contributes
    the lowest video node, so callers see one entry per physical device.
    Result is ordered by the USB sysfs path so cameras keep a stable identity
    across runs as long as the cabling doesn't change.
    """
    cameras = {}
    try:
        for dev in sorted(d for d in os.listdir('/dev') if d.startswith('video')):
            sysfs = f'/sys/class/video4linux/{dev}'
            if not os.path.exists(sysfs):
                continue
            real = os.path.realpath(sysfs)
            if 'usb' not in real:
                continue
            usb_iface = real.split('/video4linux/')[0]
            # Deduplicate at the USB *device* level, not the interface level.
            # A USB interface path ends in "N-N:N.N"; its parent is the device
            # path "N-N". Both nodes from the same physical camera must map to
            # the same key or we incorrectly count one camera as two.
            last = os.path.basename(usb_iface)
            usb_root = os.path.dirname(usb_iface) if ':' in last else usb_iface
            if usb_root not in cameras:
                cameras[usb_root] = f'/dev/{dev}'
    except Exception:
        pass
    return list(cameras.values())


def _detect_usb_camera() -> str:
    """Return the first USB camera (legacy — kept for compatibility)."""
    cams = _detect_usb_cameras()
    if cams:
        return cams[0]
    print('WARNING: No USB camera found in sysfs; falling back to /dev/video0')
    return '/dev/video0'


# DRP-AI C++ binaries hardcode /dev/video0 in their GStreamer pipeline. When
# multiple cameras are connected, Python CV picks one that DRP-AI is not using
# so the two demos can run in parallel.
_DRPAI_HARDCODED_CAMERA = '/dev/video0'


def _pick_cv_camera() -> Optional[str]:
    """Choose a USB camera for the Python CV loop.

    Prefers a camera the DRP-AI binary is not using. Returns None if no
    USB cameras are available, or if only one camera exists and DRP-AI
    has it.
    """
    cams = _detect_usb_cameras()
    if not cams:
        return None
    if is_drpai_running():
        for cam in cams:
            if cam != _DRPAI_HARDCODED_CAMERA:
                return cam
        return None  # only one camera and DRP-AI owns it
    return cams[0]


_HAAR_DIR = '/usr/share/opencv4/haarcascades'


def _haar_path(filename: str) -> str:
    """Locate a Haar cascade XML file, falling back to cv2.data if available."""
    direct = os.path.join(_HAAR_DIR, filename)
    if os.path.exists(direct):
        return direct
    # cv2.data is present in some OpenCV builds (not the Yocto RZ/V2H build)
    try:
        return cv2.data.haarcascades + filename
    except AttributeError:
        return direct


_CV_FRAME_WIDTH = 640
_CV_FRAME_HEIGHT = 480
_CV_FRAME_FPS = 15


def _cv_inference_loop():
    global _cv_active, _cv_result, _cv_device

    face_cascade_path = _haar_path('haarcascade_frontalface_default.xml')
    body_cascade_path = _haar_path('haarcascade_fullbody.xml')

    face_cascade = cv2.CascadeClassifier(face_cascade_path)
    body_cascade = cv2.CascadeClassifier(body_cascade_path)

    if face_cascade.empty():
        print('WARNING: Could not load face Haar cascade')
    if body_cascade.empty():
        print('WARNING: Could not load body Haar cascade')

    device = _pick_cv_camera() or _detect_usb_camera()
    _cv_device = device
    print(f'CV inference: opening camera {device}')
    cap = cv2.VideoCapture(device)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, _CV_FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, _CV_FRAME_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, _CV_FRAME_FPS)

    if not cap.isOpened():
        print(f'ERROR: Could not open camera {device}')
        _cv_active = False
        return

    print('CV inference loop started')

    while _cv_active:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

        t0 = time.time()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        faces = []
        bodies = []
        if not face_cascade.empty():
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
        if not body_cascade.empty():
            bodies = body_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))

        t1 = time.time()
        face_count = len(faces) if hasattr(faces, '__len__') else 0
        body_count = len(bodies) if hasattr(bodies, '__len__') else 0
        inf_ms = round((t1 - t0) * 1000, 1)

        with _cv_lock:
            _cv_result = {
                'face_count': face_count,
                'person_count': body_count,
                'inference_time_ms': inf_ms,
                'total_detections': face_count + body_count,
            }

        # Throttle to ~5 fps to leave CPU headroom for IoTConnect + DRP-AI
        time.sleep(0.2)

    cap.release()
    _cv_device = ''
    print('CV inference loop stopped')


def start_cv_inference() -> tuple:
    """Start Python CV inference. Returns (ok, message).

    If a DRP-AI demo is already running, this picks a different USB camera
    (DRP-AI hardcodes /dev/video0). Refused only if every connected camera
    is already in use.
    """
    global _cv_active, _cv_thread
    if _cv_active:
        return False, 'CV inference already running'
    chosen = _pick_cv_camera()
    if chosen is None:
        return False, 'No spare USB camera available (DRP-AI is using the only one).'
    _cv_active = True
    _cv_thread = threading.Thread(target=_cv_inference_loop, daemon=True)
    _cv_thread.start()
    return True, f'CV inference started on {chosen}'


def stop_cv_inference() -> tuple:
    """Stop Python CV inference. Returns (ok, message)."""
    global _cv_active
    if not _cv_active:
        return False, 'CV inference was not running'
    _cv_active = False
    if _cv_thread:
        _cv_thread.join(timeout=3)
    with _cv_lock:
        _cv_result.update({'face_count': 0, 'person_count': 0, 'inference_time_ms': 0.0, 'total_detections': 0})
    return True, 'CV inference stopped'


def get_cv_result() -> dict:
    with _cv_lock:
        return dict(_cv_result)


# ─── OTA / file-download ──────────────────────────────────────────────────────

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


# ─── C2D command handler ──────────────────────────────────────────────────────

def on_command(msg: C2dCommand):
    print(f'Received command: {msg.command_name} args={msg.command_args}')

    if msg.command_name == 'start_detection':
        ok, status = start_cv_inference()
        client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK if ok else C2dAck.CMD_FAILED, status)
        print(status)

    elif msg.command_name == 'stop_detection':
        ok, status = stop_cv_inference()
        client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status)
        print(status)

    elif msg.command_name == 'launch_drpai':
        if len(msg.command_args) == 1:
            mode = msg.command_args[0].lower()
            ok = start_drpai_demo(mode)
            status = f'DRP-AI demo started: {mode}' if ok else f'Failed to start DRP-AI demo: {mode}'
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK if ok else C2dAck.CMD_FAILED, status)
            print(status)
        else:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Expected 1 argument: coco | animal | vehicle')

    elif msg.command_name == 'stop_drpai':
        ok = stop_drpai_demo()
        status = 'DRP-AI demo stopped' if ok else 'No DRP-AI demo was running'
        client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status)
        print(status)

    elif msg.command_name == 'set_confidence':
        if len(msg.command_args) == 1:
            try:
                val = float(msg.command_args[0])
                global _cv_confidence
                _cv_confidence = max(0.1, min(1.0, val))
                status = f'Confidence threshold set to {_cv_confidence}'
                client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status)
                print(status)
            except ValueError:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Invalid float value')
        else:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Expected 1 argument: float 0.0–1.0')

    elif msg.command_name == 'file-download':
        if len(msg.command_args) == 1:
            url = msg.command_args[0]
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    with open('package.tar.gz', 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, f'Downloaded {url}')
                    stop_cv_inference()
                    stop_drpai_demo()
                    extract_and_run_tar_gz('package.tar.gz')
                    print('OTA package applied. Restarting...')
                    sys.stdout.flush()
                    os.execv(sys.executable, [sys.executable, __file__] + sys.argv[1:])
                else:
                    status = f'Download failed: HTTP {response.status_code}'
                    print(status)
                    client.send_command_ack(msg, C2dAck.CMD_FAILED, status)
            except Exception as e:
                status = f'Download error: {e}'
                print(status)
                client.send_command_ack(msg, C2dAck.CMD_FAILED, status)
        else:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Expected 1 argument')

    else:
        print(f'Command {msg.command_name} not implemented!')
        if msg.ack_id is not None:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, 'Not Implemented')


def on_ota(msg: C2dOta):
    print(f'Starting OTA downloads for version {msg.version}')
    client.send_ota_ack(msg, C2dAck.OTA_DOWNLOADING)
    extraction_success = False
    for url in msg.urls:
        print(f'Downloading OTA file {url.file_name} from {url.url}')
        try:
            urllib.request.urlretrieve(url.url, url.file_name)
        except Exception as e:
            print(f'Download error: {e}')
            break
        if url.file_name.endswith('.tar.gz'):
            extraction_success = extract_and_run_tar_gz(url.file_name)
            if not extraction_success:
                break
        else:
            print(f'ERROR: Unhandled file format: {url.file_name}')
    if extraction_success:
        print('OTA successful. Restarting...')
        client.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_DONE)
        stop_cv_inference()
        stop_drpai_demo()
        sys.stdout.flush()
        os.execv(sys.executable, [sys.executable, __file__] + sys.argv[1:])
    else:
        print('Encountered a download processing error. Not restarting.')


def on_disconnect(reason: str, disconnected_from_server: bool):
    print(f'Disconnected. Reason: {reason}')


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Auto-populate WAYLAND_DISPLAY + XDG_RUNTIME_DIR so GStreamer's waylandsink
    # and the DRP-AI C++ binary can both find the Weston compositor even when
    # the user launches the app from a plain SSH session.
    if 'WAYLAND_DISPLAY' not in os.environ or 'XDG_RUNTIME_DIR' not in os.environ:
        env = _find_wayland_env()
        if env:
            os.environ.update(env)
            print(f'Wayland env auto-detected: XDG_RUNTIME_DIR={env["XDG_RUNTIME_DIR"]}')
        else:
            print('WARNING: Wayland socket not found — HDMI display output disabled')

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
            disconnected_cb=on_disconnect,
        )
    )

    print('Connecting to /IOTCONNECT...')
    client.connect()
    if not client.is_connected():
        print('Failed to connect. Exiting.')
        sys.exit(1)
    print('Connected to /IOTCONNECT')

    print('\n' + '=' * 55)
    print('RZ/V2H EVK AI Demo running')
    print('CV inference: STOPPED  (send start_detection to begin)')
    print('DRP-AI demo:  STOPPED  (send launch_drpai coco|animal|vehicle)')
    print('Telemetry interval: 10 seconds')
    print('Press Ctrl+C to exit')
    print('=' * 55 + '\n')

    try:
        while True:
            if not client.is_connected():
                print('Connection lost, reconnecting...')
                client.connect()

            metrics = system_monitor.get_all_metrics()
            cv = get_cv_result()
            drpai_running = is_drpai_running()
            drpai_kind = get_drpai_kind()
            drpai_data = read_drpai_results() if drpai_running else None

            # Unified fields across all DRP-AI demos
            drpai_counts = {}
            drpai_total = 0
            drpai_ai_ms = 0.0
            drpai_pre_ms = 0.0
            drpai_post_ms = 0.0
            drpai_person = 0
            drpai_primary_class = ''
            drpai_primary_confidence = 0.0

            # Meter-reader-specific fields (Q13)
            meter_value = 0.0
            meter_min = 0
            meter_max = 0
            meter_page = 0
            meter_high_deviation = False
            yolox_ai_ms = 0.0
            unet_ai_ms = 0.0

            if drpai_data:
                # Common timing — present in every patched demo's results file
                drpai_ai_ms = float(drpai_data.get('ai_time_ms', 0.0))
                drpai_pre_ms = float(drpai_data.get('pre_time_ms', 0.0))
                drpai_post_ms = float(drpai_data.get('post_time_ms', 0.0))

                if drpai_kind == 'object_counter':
                    drpai_counts = drpai_data.get('counts', {})
                    drpai_total = int(drpai_data.get('total', 0))
                    drpai_person = int(drpai_counts.get('person', 0))

                elif drpai_kind == 'meter':
                    meter_value = float(drpai_data.get('meter_value', 0.0))
                    meter_min = int(drpai_data.get('meter_min', 0))
                    meter_max = int(drpai_data.get('meter_max', 0))
                    meter_page = int(drpai_data.get('page', 0))
                    meter_high_deviation = bool(drpai_data.get('high_deviation', False))
                    yolox_ai_ms = float(drpai_data.get('yolox_ai_ms', 0.0))
                    unet_ai_ms = float(drpai_data.get('unet_ai_ms', 0.0))
                    # Aggregate into the shared drpai_inference_time_ms
                    drpai_ai_ms = yolox_ai_ms + unet_ai_ms

                elif drpai_kind in ('classifier', 'activity', 'pose'):
                    drpai_primary_class = str(drpai_data.get('primary_class', ''))
                    drpai_primary_confidence = float(drpai_data.get('primary_confidence', 0.0))
                    # Q05 activity reports cnn+mlp timing summed
                    if drpai_kind == 'activity':
                        drpai_ai_ms = float(drpai_data.get('ai_time_ms', 0.0))
                    # Q12 pose reports keypoint+classifier timing summed in ai_time_ms
                    # (already picked up above)
                    drpai_total = 1 if drpai_primary_class else 0

                elif drpai_kind == 'detector':
                    drpai_total = int(drpai_data.get('total', 0))
                    # R01 also populates primary_class / primary_confidence
                    drpai_primary_class = str(drpai_data.get('primary_class', ''))
                    drpai_primary_confidence = float(drpai_data.get('primary_confidence', 0.0))

                elif drpai_kind == 'segmentation':
                    # Q09 reports timing only for now; no count/class extraction
                    pass

                # 'ui_only' kinds (Q02/Q03/Q06) write no results file — drpai_data
                # stays None so nothing populates beyond process state.

            telemetry = {
                'sdk_version': SDK_VERSION,
                # System performance
                'cpu_percent': metrics['cpu_percent'],
                'memory_percent': metrics['memory_percent'],
                'memory_used_mb': metrics['memory_used_mb'],
                'cpu_temp_0_c': metrics['cpu_temp_0_c'],
                'cpu_temp_1_c': metrics['cpu_temp_1_c'],
                'drpai_present': metrics['drpai_present'],
                # Python CV inference results
                'cv_active': _cv_active,
                'face_count': cv['face_count'],
                'person_count': cv['person_count'],
                'total_detections': cv['total_detections'],
                'inference_time_ms': cv['inference_time_ms'],
                # DRP-AI demo state + hardware-accelerated inference results
                'drpai_demo_active': drpai_running,
                'drpai_demo_name': get_drpai_name(),
                'drpai_demo_kind': drpai_kind,
                'drpai_total': drpai_total,
                'drpai_person_count': drpai_person,
                'drpai_inference_time_ms': round(drpai_ai_ms, 1),
                'drpai_pre_time_ms': round(drpai_pre_ms, 1),
                'drpai_post_time_ms': round(drpai_post_ms, 1),
                'drpai_counts': json.dumps(drpai_counts) if drpai_counts else '',
                'drpai_primary_class': drpai_primary_class,
                'drpai_primary_confidence': round(drpai_primary_confidence, 1),
                # Meter reader (Q13)
                'meter_value': round(meter_value, 2),
                'meter_min': meter_min,
                'meter_max': meter_max,
                'meter_page': meter_page,
                'meter_calibration_warning': meter_high_deviation,
                'meter_yolox_ms': round(yolox_ai_ms, 1),
                'meter_unet_ms': round(unet_ai_ms, 1),
                # Connectivity heartbeat
                'random': random.randint(0, 100),
            }

            if not drpai_running:
                drpai_summary = 'drpai=off'
            elif drpai_kind == 'meter':
                drpai_summary = (
                    f'drpai=meter page={meter_page} value={meter_value:.2f} '
                    f'range=[{meter_min},{meter_max}] yolox={yolox_ai_ms}ms unet={unet_ai_ms}ms'
                    if drpai_data else
                    'drpai=meter (waiting for calibration / first frame)'
                )
            elif drpai_kind == 'object_counter':
                drpai_summary = (
                    f'drpai={drpai_kind} total={drpai_total} person={drpai_person} ai={drpai_ai_ms}ms'
                    if drpai_data else
                    f'drpai={drpai_kind} (no results file — binary not patched?)'
                )
            elif drpai_kind in ('classifier', 'activity', 'pose'):
                drpai_summary = (
                    f'drpai={drpai_kind} class="{drpai_primary_class}" '
                    f'conf={drpai_primary_confidence:.1f}% ai={drpai_ai_ms}ms'
                    if drpai_data else
                    f'drpai={drpai_kind} (no results yet)'
                )
            elif drpai_kind == 'detector':
                drpai_summary = (
                    f'drpai={drpai_kind} total={drpai_total} '
                    f'top="{drpai_primary_class}" ai={drpai_ai_ms}ms'
                    if drpai_data else
                    f'drpai={drpai_kind} (no results yet)'
                )
            elif drpai_kind == 'segmentation':
                drpai_summary = (
                    f'drpai=segmentation ai={drpai_ai_ms}ms pre={drpai_pre_ms}ms post={drpai_post_ms}ms'
                    if drpai_data else
                    'drpai=segmentation (no results yet)'
                )
            elif drpai_kind == 'ui_only':
                drpai_summary = f'drpai={get_drpai_name()} (UI-driven, no telemetry)'
            else:
                drpai_summary = f'drpai={drpai_kind} (unknown kind)'
            print(
                f'cpu={metrics["cpu_percent"]}% mem={metrics["memory_percent"]}% '
                f't0={metrics["cpu_temp_0_c"]}°C t1={metrics["cpu_temp_1_c"]}°C | '
                f'cv={"ON" if _cv_active else "off"} '
                f'faces={cv["face_count"]} persons={cv["person_count"]} '
                f'infer={cv["inference_time_ms"]}ms | '
                f'{drpai_summary}'
            )
            client.send_telemetry(telemetry)
            time.sleep(10)

    except KeyboardInterrupt:
        print('\nShutting down...')
        stop_cv_inference()
        stop_drpai_demo()
        client.disconnect()
        print('Shutdown complete.')
        sys.exit(0)
