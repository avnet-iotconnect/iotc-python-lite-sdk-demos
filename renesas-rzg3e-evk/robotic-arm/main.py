#!/usr/bin/env python3
"""
IOTCONNECT XArm Vision Control

Outer loop owns: camera, display window, IoTConnect command pump, arm bring-up.
Per-frame inference + arm decisions live in modes/<name>.py and are selected
with --mode. Default mode is 'asl' (the original gesture-controlled demo).
"""

import argparse
import json
import os
import queue
import threading
import time
from collections import deque
from dataclasses import asdict
from datetime import datetime

import cv2

import systemdata
import xarm

from modes import make_mode

try:
    from avnet.iotconnect.sdk.lite import Client, DeviceConfig, Callbacks, DeviceConfigError
    from avnet.iotconnect.sdk.sdklib.mqtt import C2dCommand, C2dAck
    IOTC_AVAILABLE = True
except ImportError:
    IOTC_AVAILABLE = False
    Client = None
    DeviceConfig = None
    Callbacks = None
    DeviceConfigError = None
    C2dCommand = None
    C2dAck = None


ACTION_LABELS = {
    'advance': "A : Advance",
    'backup': "B : Back-Up",
    'left': "L : Left",
    'right': "R : Right",
    'up': "U : Up",
    'down': "Y : Down",
    'home': "H : Home",
    'move_to': "Move To Position",
    'close_gripper': "A : Close Gripper",
    'open_gripper': "B : Open Gripper",
    'wrist_roll_cw': "Wrist Roll CW",
    'wrist_roll_ccw': "Wrist Roll CCW",
    'wrist_flex_up': "Wrist Flex Up",
    'wrist_flex_down': "Wrist Flex Down",
    'demo_wave': "Demo: Wave Hello",
    'demo_bow': "Demo: Bow",
    'demo_stretch': "Demo: Stretch Up",
    'demo_scan': "Demo: Scan Sweep",
    'demo_shake_no': "Demo: Shake No",
    'demo_pickup': "Demo: Pick & Place",
}

HOME_POSITIONS = [[1, 500], [2, 500], [3, 500], [4, 500], [5, 500], [6, 500]]

# Scripted demo sequences. Each item is (positions, duration_ms).
# Every sequence must end at HOME_POSITIONS so the next action starts from a known pose.
DEMO_SEQUENCES = {
    'demo_wave': [
        ([[5, 250], [4, 250], [3, 500], [2, 500]], 1500),
        ([[2, 300]], 350),
        ([[2, 700]], 350),
        ([[2, 300]], 350),
        ([[2, 700]], 350),
        ([[2, 500]], 350),
        (HOME_POSITIONS, 1500),
    ],
    'demo_bow': [
        ([[5, 700], [4, 600], [3, 600]], 1500),
        ([[5, 700]], 800),
        (HOME_POSITIONS, 1500),
    ],
    'demo_stretch': [
        ([[5, 150], [4, 500], [3, 500], [2, 500]], 1800),
        ([[3, 350]], 800),
        ([[3, 650]], 800),
        ([[3, 500]], 400),
        (HOME_POSITIONS, 1800),
    ],
    'demo_scan': [
        ([[5, 350], [4, 400], [3, 500]], 1200),
        ([[6, 100]], 1500),
        ([[6, 900]], 2500),
        ([[6, 500]], 1200),
        (HOME_POSITIONS, 1200),
    ],
    'demo_shake_no': [
        ([[5, 300], [4, 350]], 1200),
        ([[6, 400]], 250),
        ([[6, 600]], 250),
        ([[6, 400]], 250),
        ([[6, 600]], 250),
        ([[6, 400]], 250),
        ([[6, 500]], 250),
        (HOME_POSITIONS, 1200),
    ],
    'demo_pickup': [
        ([[1, 100]], 600),
        ([[5, 750], [4, 650], [3, 550], [6, 500]], 1800),
        ([[1, 650]], 700),
        ([[5, 300], [4, 400]], 1500),
        ([[6, 200]], 1500),
        ([[5, 750], [4, 650]], 1500),
        ([[1, 100]], 600),
        ([[5, 300], [4, 400]], 1200),
        (HOME_POSITIONS, 1500),
    ],
}

IOTC_COMMAND_TO_ACTION = {
    'move_to': 'move_to',
    'move_to_home': 'home',
    'open_gripper': 'open_gripper',
    'close_gripper': 'close_gripper',
    'move_forward': 'advance',
    'move_backward': 'backup',
    'move_left': 'left',
    'move_right': 'right',
    'move_up': 'up',
    'move_down': 'down',
    'wrist_roll_cw': 'wrist_roll_cw',
    'wrist_roll_ccw': 'wrist_roll_ccw',
    'wrist_flex_up': 'wrist_flex_up',
    'wrist_flex_down': 'wrist_flex_down',
    'demo_wave': 'demo_wave',
    'demo_bow': 'demo_bow',
    'demo_stretch': 'demo_stretch',
    'demo_scan': 'demo_scan',
    'demo_shake_no': 'demo_shake_no',
    'demo_pickup': 'demo_pickup',
}


iotc_command_queue = deque()
command_queue_lock = threading.Lock()
iotc_publisher = None
iotc_warning_flags = {
    'sdk_missing': False,
    'not_connected': False,
}


def iotc_on_command(msg):
    print(f"Received IoTConnect command: {msg.command_name} args={msg.command_args} ack_id={msg.ack_id}")
    with command_queue_lock:
        iotc_command_queue.append(msg)


def iotc_on_disconnect(reason: str, disconnected_from_server: bool):
    print(f"IoTConnect disconnected ({'server' if disconnected_from_server else 'client'}): {reason}")


def _init_iotconnect_client():
    global iotc_publisher
    iotc_publisher = None
    if not IOTC_AVAILABLE:
        if not iotc_warning_flags['sdk_missing']:
            print('Warning: IoTConnect SDK not installed.')
            iotc_warning_flags['sdk_missing'] = True
        return

    try:
        device_config_path = 'iotcDeviceConfig.json'
        if not os.path.exists(device_config_path):
            print(f"Warning: IoTConnect device config file not found: {device_config_path}")
            return

        device_cert_path = 'device-cert.pem'
        device_pkey_path = 'device-pkey.pem'
        config = DeviceConfig.from_iotc_device_config_json_file(
            device_config_json_path=device_config_path,
            device_cert_path=device_cert_path,
            device_pkey_path=device_pkey_path
        )

        print('Device Config', config)
        callbacks = Callbacks(command_cb=iotc_on_command, disconnected_cb=iotc_on_disconnect)
        iotc_publisher = Client(config=config, callbacks=callbacks)
        iotc_publisher.connect()
        iotc_warning_flags['not_connected'] = False
        print('IOTCONNECT client connected')
    except Exception as e:
        iotc_warning_flags['not_connected'] = True
        print(f'Warning: Failed to initialize IoTConnect client: {e}.')
        iotc_publisher = None


def _parse_move_to_positions(command_args):
    if isinstance(command_args, dict):
        if 'positions' in command_args:
            raw_positions = command_args['positions']
        elif 'position' in command_args:
            raw_positions = command_args['position']
        else:
            raw_positions = ','.join(str(value) for value in command_args.values())
    else:
        raw_positions = command_args

    if isinstance(raw_positions, str):
        tokens = [token.strip() for token in raw_positions.split(',') if token.strip()]
    elif isinstance(raw_positions, (list, tuple)):
        tokens = [str(token).strip() for token in raw_positions if str(token).strip()]
    else:
        raise ValueError('move_to command_args must be a comma-separated string or list of positions')

    if len(tokens) != 6:
        raise ValueError(f'move_to requires 6 servo positions, received {len(tokens)}')

    positions = []
    for servo_id, token in enumerate(tokens, start=1):
        positions.append([servo_id, clamp_position(int(token))])

    return positions


def process_iotconnect_commands(arm):
    if not IOTC_AVAILABLE or iotc_publisher is None or not iotc_publisher.is_connected():
        return

    with command_queue_lock:
        queued_commands = list(iotc_command_queue)
        iotc_command_queue.clear()

    for msg in queued_commands:
        command_name = getattr(msg, 'command_name', '').lower()
        command_args = getattr(msg, 'command_args', {}) or {}
        print(f"Processing IoTConnect command '{command_name}' with args={command_args}")
        ack_status = C2dAck.CMD_SUCCESS_WITH_ACK
        ack_message = 'Executed command'
        try:
            action_name = IOTC_COMMAND_TO_ACTION.get(command_name)
            if action_name is None:
                ack_status = C2dAck.CMD_FAILED
                ack_message = f"Unknown command '{command_name}'"
                print(ack_message)
            else:
                action_detected = execute_arm_action(arm, action_name, command_args)
                print(f"Action: {action_detected}")
                send_telemetry(arm)
        except Exception as e:
            ack_status = C2dAck.CMD_FAILED
            ack_message = f"Command failed: {e}"
            print(ack_message)
        try:
            iotc_publisher.send_command_ack(msg, ack_status, ack_message)
        except Exception as e:
            print(f"Warning: Failed to send IoTConnect command ack: {e}")


def _send_iotconnect_telemetry(payload: dict):
    if not IOTC_AVAILABLE:
        if not iotc_warning_flags['sdk_missing']:
            print('Warning: IoTConnect SDK not installed.')
            iotc_warning_flags['sdk_missing'] = True
        return

    if iotc_publisher is None or not iotc_publisher.is_connected():
        if not iotc_warning_flags['not_connected']:
            print('Warning: IoTConnect client not connected.')
            iotc_warning_flags['not_connected'] = True
        return

    try:
        iotc_publisher.send_telemetry(payload)
    except Exception as e:
        print(f'IoTConnect telemetry publish error: {e}')


# Background telemetry — systemdata.collect_data() blocks ~600ms (psutil cpu_percent
# with 0.5s interval + process iteration sleeps) and IoTConnect MQTT publish adds
# more. Doing that synchronously from a per-frame perception loop destroys fps, so
# we snapshot the arm positions on the caller's thread (USB HID is not multi-thread
# safe) and hand the rest off to a worker thread.
_telemetry_queue = queue.Queue(maxsize=1)
_telemetry_worker_started = False
# Tracks the currently running mode so send_telemetry can stamp every
# payload with a top-level `state` (e.g. SCANNING/TRACKING/GRABBING/HOLDING
# for ball mode, "ASL-Gesture" for ASL). Set by run_mode.
_current_mode = None


def _telemetry_worker_loop():
    while True:
        arm_positions, extras = _telemetry_queue.get()
        try:
            sysdata = systemdata.collect_data()
            sys_obj = {'hostname': sysdata.hostname, 'uptime': sysdata.uptime, **asdict(sysdata.system_info)}
            cpu_obj = {**asdict(sysdata.cpu), 'temp': sysdata.cpu_temp}
            mem_obj = {**asdict(sysdata.memory), 'temp': sysdata.memory_temp}
            telemetry = {
                **arm_positions,
                'sysInfo_system': sys_obj,
                'sysInfo_cpu': cpu_obj,
                'sysInfo_memory': mem_obj,
                'sysInfo_storage': asdict(sysdata.storage),
                'sysInfo_gpu': {'usage_percent': sysdata.gpu_usage, 'temp': sysdata.gpu_temp},
            }
            if extras:
                telemetry.update(extras)
            print(f"IoTConnect Telemetry: {json.dumps(telemetry)}")
            _send_iotconnect_telemetry(telemetry)
        except Exception as e:
            print(f"[telemetry] worker error: {e}")


def _ensure_telemetry_worker():
    global _telemetry_worker_started
    if _telemetry_worker_started:
        return
    _telemetry_worker_started = True
    threading.Thread(target=_telemetry_worker_loop, daemon=True).start()


def send_telemetry(arm, extras=None, positions=None):
    """Publish telemetry. Pass `positions={id: pos}` to skip re-reading servos
    (caller already did a batched read)."""
    _ensure_telemetry_worker()
    if positions is not None:
        arm_positions = {
            'gripper': positions.get(1, 0),
            'wrist_roll': positions.get(2, 0),
            'wrist_flex': positions.get(3, 0),
            'elbow_flex': positions.get(4, 0),
            'shoulder_lift': positions.get(5, 0),
            'shoulder_pan': positions.get(6, 0),
        }
    else:
        # USB HID is not thread-safe — read on caller's thread.
        arm_positions = {
            'gripper': arm.getPosition(1),
            'wrist_roll': arm.getPosition(2),
            'wrist_flex': arm.getPosition(3),
            'elbow_flex': arm.getPosition(4),
            'shoulder_lift': arm.getPosition(5),
            'shoulder_pan': arm.getPosition(6),
        }
    # Stamp every payload with top-level `state` from the active mode.
    if _current_mode is not None:
        try:
            mode_state = _current_mode.get_state()
        except Exception as e:
            print(f"[telemetry] get_state failed: {e}")
            mode_state = None
        if mode_state is not None:
            extras = dict(extras) if extras else {}
            extras.setdefault("state", mode_state)

    item = (arm_positions, extras)
    try:
        _telemetry_queue.put_nowait(item)
    except queue.Full:
        # Drop the stale queued sample, replace with the fresh one.
        try:
            _telemetry_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            _telemetry_queue.put_nowait(item)
        except queue.Full:
            pass


def clamp_position(value, minimum=0, maximum=1000):
    return max(minimum, min(maximum, int(value)))


def execute_arm_action(arm, action_name, command_args=None):
    if action_name == 'home':
        arm.setPosition(HOME_POSITIONS, duration=1500, wait=True)
    elif action_name == 'move_to':
        positions = _parse_move_to_positions(command_args)
        arm.setPosition(positions, duration=1500, wait=True)
    elif action_name == 'open_gripper':
        arm.setPosition(1, clamp_position(arm.getPosition(1) - 100), duration=1000, wait=True)
    elif action_name == 'close_gripper':
        arm.setPosition(1, clamp_position(arm.getPosition(1) + 100), duration=1000, wait=True)
    elif action_name == 'advance':
        arm.setPosition(5, clamp_position(arm.getPosition(5) + 100), duration=1500, wait=True)
    elif action_name == 'backup':
        arm.setPosition(5, clamp_position(arm.getPosition(5) - 100), duration=1500, wait=True)
    elif action_name == 'left':
        arm.setPosition(6, clamp_position(arm.getPosition(6) - 100), duration=1500, wait=True)
    elif action_name == 'right':
        arm.setPosition(6, clamp_position(arm.getPosition(6) + 100), duration=1500, wait=True)
    elif action_name == 'up':
        arm.setPosition(4, clamp_position(arm.getPosition(4) - 100), duration=1500, wait=True)
    elif action_name == 'down':
        arm.setPosition(4, clamp_position(arm.getPosition(4) + 100), duration=1500, wait=True)
    elif action_name == 'wrist_roll_cw':
        arm.setPosition(2, clamp_position(arm.getPosition(2) + 100), duration=1000, wait=True)
    elif action_name == 'wrist_roll_ccw':
        arm.setPosition(2, clamp_position(arm.getPosition(2) - 100), duration=1000, wait=True)
    elif action_name == 'wrist_flex_up':
        arm.setPosition(3, clamp_position(arm.getPosition(3) - 100), duration=1000, wait=True)
    elif action_name == 'wrist_flex_down':
        arm.setPosition(3, clamp_position(arm.getPosition(3) + 100), duration=1000, wait=True)
    elif action_name in DEMO_SEQUENCES:
        for positions, duration_ms in DEMO_SEQUENCES[action_name]:
            arm.setPosition(positions, duration=duration_ms, wait=True)
    else:
        raise ValueError(f"Unknown action '{action_name}'")

    return ACTION_LABELS[action_name]


class _FreshCamera:
    """Background-threaded camera reader.

    The driver buffers frames internally while the main thread is blocked on
    arm moves (wait=True). CAP_PROP_BUFFERSIZE=1 is advisory and not honored
    by all V4L2 devices, so we run a worker that continuously grabs frames
    and keeps only the latest. The main loop always sees a fresh frame.
    """

    def __init__(self, index, frame_w, frame_h):
        self.cap = cv2.VideoCapture(index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, frame_w)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, frame_h)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._latest = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        if not self.cap.isOpened():
            return False
        self._thread.start()
        return True

    def _loop(self):
        while not self._stop.is_set():
            ok, frame = self.cap.read()
            if not ok:
                time.sleep(0.005)
                continue
            with self._lock:
                self._latest = frame

    def read(self):
        with self._lock:
            return self._latest

    def release(self):
        self._stop.set()
        self._thread.join(timeout=1.0)
        self.cap.release()


def run_mode(arm, mode, camera_index=2, frame_w=640, frame_h=480,
             window_title="IOTCONNECT XArm Control", headless=False, perf_every=30,
             web_port=None):
    """Generic camera loop. Each frame: capture -> mode.process_frame -> display -> IoTConnect cmd pump.
    Exits on ESC or 'q' (or Ctrl-C in headless).

    If ``web_port`` is set, every annotated frame is also published as
    MJPEG on that port — point a browser at http://<board-ip>:<web_port>/
    to watch the live demo from anywhere on the LAN. Useful on boards
    without a local display."""
    global _current_mode
    cam = _FreshCamera(camera_index, frame_w, frame_h)
    if not cam.start():
        print("[ERROR] Camera failed to open!")
        return
    print(f"[INFO] Camera input: {camera_index} ({frame_w}, {frame_h}) — mode={mode.name} headless={headless}")

    web = None
    if web_port:
        try:
            from web_view import WebView
            web = WebView(port=web_port)
            print(f"[INFO] Live web view: {web.url_hint()}")
        except Exception as e:
            print(f"[WARN] web view failed to start on port {web_port}: {e}")

    _current_mode = mode
    mode.setup(arm)

    # rolling perf counters
    n = 0
    t_cap_sum = 0.0
    t_proc_sum = 0.0
    t_total_sum = 0.0
    t_window_start = time.time()

    try:
        # wait briefly for first frame
        t0 = time.time()
        while cam.read() is None and time.time() - t0 < 2.0:
            time.sleep(0.02)

        while True:
            frame_t0 = time.perf_counter()
            t_a = time.perf_counter()
            frame = cam.read()
            if frame is None:
                time.sleep(0.01)
                continue
            t_cap = time.perf_counter() - t_a

            t_b = time.perf_counter()
            display = mode.process_frame(frame, arm)
            t_proc = time.perf_counter() - t_b
            if display is None:
                display = frame

            if not headless:
                cv2.imshow(window_title, display)
                key = cv2.waitKey(1)
                if key == 27 or key == 113:
                    break

            if web is not None:
                try:
                    web.publish(display, state=mode.get_state(), mode=mode.name)
                except Exception as e:
                    print(f"[web] publish failed: {e}")

            if arm is not None:
                process_iotconnect_commands(arm)

            t_total = time.perf_counter() - frame_t0
            n += 1
            t_cap_sum += t_cap
            t_proc_sum += t_proc
            t_total_sum += t_total
            if n >= perf_every:
                elapsed = time.time() - t_window_start
                fps = n / elapsed if elapsed > 0 else 0.0
                print(f"[perf] n={n} fps={fps:.1f}  cap={t_cap_sum/n*1000:.1f}ms  "
                      f"proc={t_proc_sum/n*1000:.1f}ms  total={t_total_sum/n*1000:.1f}ms")
                if web is not None:
                    web.publish(display, fps_hint=fps)
                n = 0
                t_cap_sum = t_proc_sum = t_total_sum = 0.0
                t_window_start = time.time()
    finally:
        mode.teardown(arm)
        cam.release()
        if not headless:
            cv2.destroyAllWindows()
        if web is not None:
            web.stop()
        _current_mode = None


def parse_args():
    parser = argparse.ArgumentParser(description="IOTCONNECT XArm vision demo")
    parser.add_argument('--mode', default='ball',
                        help="Vision mode (default: ball — the supported mode on RZ/G3E. "
                             "Use 'asl' only if torch + mediapipe are installed)")
    parser.add_argument('--camera', type=int, default=0,
                        help="OpenCV camera index (default: 0 — RZ/G3E exposes the USB UVC camera as /dev/video0)")
    parser.add_argument('--headless', action='store_true', help="Disable preview window (for SSH/perf testing)")
    parser.add_argument('--perf-every', type=int, default=30, help="Print perf stats every N frames")
    parser.add_argument('--web-port', type=int, default=None,
                        help="Serve live MJPEG view of the annotated frames on this port "
                             "(e.g. 8000). Open http://<board-ip>:<port>/ in a browser.")
    return parser.parse_args()


def main():
    args = parse_args()
    arm = None
    try:
        print("Connecting to XArm 1S...")
        arm = xarm.Controller('USB')
        print("Connected to XArm 1S successfully!")

        print("Connecting to IoTConnect...")
        _init_iotconnect_client()
        if iotc_publisher is not None and iotc_publisher.is_connected():
            print("Connected to IoTConnect successfully!")
        else:
            print("IoTConnect is unavailable; running without cloud connectivity.")

        print("Initializing to home position...")
        arm.setPosition(HOME_POSITIONS, duration=2000, wait=True)
        print("Home position reached!")

        mode = make_mode(args.mode)
        print(f"Starting vision mode: {mode.name}")
        run_mode(arm, mode, camera_index=args.camera,
                 headless=args.headless, perf_every=args.perf_every,
                 web_port=args.web_port)

    except Exception as e:
        print(f"Error: {e}")
        print("Make sure XArm 1S is connected via USB and powered on.")
        print("Also ensure camera is available and any required model files exist.")

    finally:
        try:
            print("Turning off servos...")
            if arm is not None:
                arm.servoOff()
        except Exception:
            pass
        if iotc_publisher is not None:
            try:
                iotc_publisher.disconnect()
            except Exception:
                pass


if __name__ == "__main__":
    main()
