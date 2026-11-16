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

# --- AMD FOC Motor Control bindings (xlnx-app-kd240-foc-motor-ctrl 0.5) ------

FMC_PREFIX = '/opt/xilinx/xlnx-app-kd240-foc-motor-ctrl'
FMC_LIB = os.path.join(FMC_PREFIX, 'lib')


def _relaunch_with_motor_env():
    """The py_foc_motor_ctrl module needs LD_LIBRARY_PATH to find
    libfoc_motor_ctrl.so.1, and the dynamic linker only honors it at process
    start. Re-exec once with the environment the official launch script uses.
    """
    if os.environ.get('IOTC_FMC_RELAUNCH') == '1' or not os.path.isdir(FMC_LIB):
        return
    env = dict(os.environ, IOTC_FMC_RELAUNCH='1')
    env['PYTHONPATH'] = FMC_LIB + os.pathsep + env.get('PYTHONPATH', '')
    env['LD_LIBRARY_PATH'] = FMC_LIB + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    sys.stdout.flush()
    os.execve(sys.executable, [sys.executable, os.path.abspath(__file__)] + sys.argv[1:], env)


if os.path.isdir(FMC_LIB) and FMC_LIB not in sys.path:
    sys.path.insert(0, FMC_LIB)
try:
    import py_foc_motor_ctrl as fmc
    FMC_AVAILABLE = True
except ImportError:
    FMC_AVAILABLE = False
    # The re-exec happens in __main__ only, so importing this module (tests,
    # tooling) never hijacks the importing process.

HWMON_ROOT = '/sys/class/hwmon'
BASELINE_PATH = 'baseline.json'

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


# --- Motor rig -----------------------------------------------------------------

FAULT_IDS = ('kPhaseA_OC', 'kPhaseB_OC', 'kPhaseC_OC', 'kDCLink_OC',
             'kDCLink_OV', 'kDCLink_UV', 'kPhaseImbalance', 'kAvgPowerFault')

SPEED_MIN = 250.0       # library convention: |speed| within 250..10000 rpm
SPEED_MAX = 10000.0
TORQUE_MAX = 2.5        # amps, dashboard-enforced range


class MotorRig:
    """Thin, lock-guarded wrapper around the py_foc_motor_ctrl singleton."""

    def __init__(self):
        self.lock = threading.Lock()
        self.mc = None
        self.mode = 'off'
        self.speed_setpoint = 0.0
        self.torque_setpoint = 0.0
        self._last_connect_try = 0.0

    def connect(self, force: bool = False) -> bool:
        """Attach to the motor stack. Init runs gate-drive calibration, so
        failed attempts are rate limited; init fails (None) when the 24V DC
        link is not powered (kDCLink_UV)."""
        if not FMC_AVAILABLE:
            return False
        with self.lock:
            if self.mc is not None:
                return True
            now = time.monotonic()
            if not force and now - self._last_connect_try < 30.0:
                return False
            self._last_connect_try = now
            try:
                self.mc = fmc.MotorControl.getMotorControlInstance(1)
            except Exception as e:
                print('motor init error: %s' % e)
                self.mc = None
            if self.mc is None:
                print('Motor stack not ready (is the 24V DC link powered and '
                      'the kd240-motor-ctrl-qei app loaded?)')
            return self.mc is not None

    def sample(self):
        """One telemetry sample, or None when the motor stack is unavailable."""
        with self.lock:
            if self.mc is None:
                return None
            try:
                foc = self.mc.getFocCalc()
                faults = {name: bool(self.mc.getFaultStatus(getattr(fmc.FaultId, name)))
                          for name in FAULT_IDS}
                return {
                    'speed_rpm': float(self.mc.getSpeed()),
                    'speed_setpoint_rpm': float(self.speed_setpoint if self.mode == 'speed' else 0.0),
                    'position_deg': float(self.mc.getPosition()),
                    'current_ia_ma': round(float(self.mc.getCurrent(fmc.ElectricalData.kPhaseA)), 2),
                    'current_ib_ma': round(float(self.mc.getCurrent(fmc.ElectricalData.kPhaseB)), 2),
                    'current_ic_ma': round(float(self.mc.getCurrent(fmc.ElectricalData.kPhaseC)), 2),
                    'dc_link_v': round(float(self.mc.getVoltage(fmc.ElectricalData.kDCLink)), 2),
                    'i_q': round(float(foc.i_q), 4),
                    'i_d': round(float(foc.i_d), 4),
                    'faults': faults,
                }
            except Exception as e:
                print('motor sample error: %s' % e)
                return None

    def set_mode(self, name: str) -> tuple:
        modes = {'off': 'kModeOff', 'speed': 'kModeSpeed', 'torque': 'kModeTorque'}
        if name not in modes:
            return False, 'mode must be one of: off, speed, torque'
        with self.lock:
            if self.mc is None:
                return False, 'motor stack not available'
            try:
                # The library retains the last setpoints across mode changes,
                # so make them explicit before engaging a driving mode; an
                # unqualified "set-mode speed" must never resume a stale rpm.
                if name == 'speed':
                    if abs(self.speed_setpoint) < SPEED_MIN:
                        return False, 'no stored speed setpoint; use set-speed instead'
                    self.mc.setSpeed(self.speed_setpoint)
                elif name == 'torque':
                    self.mc.setTorque(self.torque_setpoint)
                self.mc.setOperationMode(getattr(fmc.MotorOpMode, modes[name]))
                self.mode = name
                if name == 'off':
                    self.speed_setpoint = 0.0
                    self.torque_setpoint = 0.0
                return True, 'mode set to %s' % name
            except Exception as e:
                return False, 'setOperationMode failed: %s' % e

    def set_speed(self, rpm: float) -> tuple:
        if rpm == 0.0:
            return self.set_mode('off')
        if not SPEED_MIN <= abs(rpm) <= SPEED_MAX:
            return False, 'speed must be 0 (stop) or %g..%g rpm in magnitude' % (SPEED_MIN, SPEED_MAX)
        with self.lock:
            if self.mc is None:
                return False, 'motor stack not available'
            try:
                self.mc.setSpeed(float(rpm))
                self.mc.setOperationMode(fmc.MotorOpMode.kModeSpeed)
                self.mode = 'speed'
                self.speed_setpoint = float(rpm)
                return True, 'speed setpoint %g rpm' % rpm
            except Exception as e:
                return False, 'setSpeed failed: %s' % e

    def set_torque(self, amps: float) -> tuple:
        if not -TORQUE_MAX <= amps <= TORQUE_MAX:
            return False, 'torque must be within %+g..%+g A' % (-TORQUE_MAX, TORQUE_MAX)
        with self.lock:
            if self.mc is None:
                return False, 'motor stack not available'
            try:
                self.mc.setTorque(float(amps))
                self.mc.setOperationMode(fmc.MotorOpMode.kModeTorque)
                self.mode = 'torque'
                self.torque_setpoint = float(amps)
                return True, 'torque setpoint %g A' % amps
            except Exception as e:
                return False, 'setTorque failed: %s' % e

    def stop(self) -> tuple:
        return self.set_mode('off')

    def clear_faults(self) -> tuple:
        with self.lock:
            if self.mc is None:
                return False, 'motor stack not available'
            try:
                # The library forces the mode to off as part of clearFaults.
                self.mc.clearFaults()
                self.mode = 'off'
                self.speed_setpoint = 0.0
                self.torque_setpoint = 0.0
                return True, 'faults cleared; mode is off'
            except Exception as e:
                return False, 'clearFaults failed: %s' % e


rig = MotorRig()

# --- Embedded AI: anomaly detection on the motor signature ---------------------

class AnomalyModel:
    """On-device novelty detection learned from the motor's own healthy
    signature. train() fits a per-feature robust location/scale model (median
    and MAD) over samples collected at a steady operating point; score() is
    the largest robust z-score across features. No cloud, no extra packages.

    Features: speed error (rpm), FOC-frame i_q and i_d, phase-current
    imbalance ratio, and DC link voltage. Mechanical load changes, phase
    problems, and supply droop all move at least one of these.
    """

    FEATURES = ('speed_err', 'i_q', 'i_d', 'imbalance', 'dc_link_v')

    def __init__(self, path: str = BASELINE_PATH):
        self.path = path
        self.lock = threading.Lock()
        self.median = None
        self.scale = None
        self.sample_count = 0
        self.baseline_speed = 0.0
        self.threshold = 4.0
        self.training_rows = None      # list while training, else None
        self.training_until = 0.0
        self._prev_speed = 0.0
        self._load()

    @staticmethod
    def features(s: dict) -> list:
        ia, ib, ic = abs(s['current_ia_ma']), abs(s['current_ib_ma']), abs(s['current_ic_ma'])
        mean_i = (ia + ib + ic) / 3.0
        imbalance = 0.0 if mean_i < 1e-6 else max(abs(ia - mean_i), abs(ib - mean_i), abs(ic - mean_i)) / mean_i
        return [
            s['speed_rpm'] - s['speed_setpoint_rpm'],
            s['i_q'],
            s['i_d'],
            imbalance,
            s['dc_link_v'],
        ]

    def _load(self):
        try:
            with open(self.path) as f:
                data = json.load(f)
            self.median = data['median']
            self.scale = data['scale']
            self.sample_count = data['sample_count']
            self.baseline_speed = data['baseline_speed']
            self.threshold = data.get('threshold', self.threshold)
            print('Loaded anomaly baseline (%d samples at %g rpm)' % (self.sample_count, self.baseline_speed))
        except (OSError, ValueError, KeyError):
            pass

    def _save(self):
        try:
            with open(self.path, 'w') as f:
                json.dump({'median': self.median, 'scale': self.scale,
                           'sample_count': self.sample_count,
                           'baseline_speed': self.baseline_speed,
                           'threshold': self.threshold}, f)
        except OSError as e:
            print('could not save baseline: %s' % e)

    def ready(self) -> bool:
        return self.median is not None

    def training(self) -> bool:
        return self.training_rows is not None

    def start_training(self, seconds: float, speed_setpoint: float):
        with self.lock:
            self._prev_speed = self.baseline_speed
            self.training_rows = []
            self.training_until = time.monotonic() + seconds
            self.baseline_speed = speed_setpoint

    def abort_training(self, reason: str):
        with self.lock:
            if self.training_rows is None:
                return
            self.training_rows = None
            self.baseline_speed = self._prev_speed
            print('Baseline training aborted: %s' % reason)

    def ingest(self, sample: dict):
        """Called at 1 Hz by the main loop while a training window is open."""
        with self.lock:
            if self.training_rows is None:
                return
            self.training_rows.append(self.features(sample))
            if time.monotonic() >= self.training_until:
                rows = self.training_rows
                self.training_rows = None
                self._fit(rows)

    def _fit(self, rows: list):
        if len(rows) < 10:
            print('Baseline training aborted: only %d samples' % len(rows))
            self.baseline_speed = self._prev_speed
            return
        cols = list(zip(*rows))
        self.median = []
        self.scale = []
        for values in cols:
            ordered = sorted(values)
            med = ordered[len(ordered) // 2]
            mad = sorted(abs(v - med) for v in values)[len(values) // 2]
            # 1.4826 * MAD approximates a standard deviation; floor the scale
            # so a near-constant feature cannot divide by zero.
            self.median.append(med)
            self.scale.append(max(1.4826 * mad, 0.01 * abs(med), 1e-3))
        self.sample_count = len(rows)
        self._save()
        print('Anomaly baseline trained: %d samples at %g rpm' % (self.sample_count, self.baseline_speed))

    def score(self, sample: dict) -> float:
        with self.lock:
            if self.median is None:
                return 0.0
            x = self.features(sample)
            z = max(abs(x[i] - self.median[i]) / self.scale[i] for i in range(len(x)))
            return round(z, 2)


model = AnomalyModel()

# --- Telemetry collection --------------------------------------------------------

latest_sample = None   # written by the main loop only


def collect_telemetry(ams_path: str) -> dict:
    s = latest_sample
    score = model.score(s) if s else 0.0
    telemetry = {
        'sdk_version': SDK_VERSION,
        'cpu_percent': get_cpu_percent(),
        'memory_percent': get_memory_percent(),
        'som_temp_ps_c': get_ps_temp(ams_path),
        'motor_available': s is not None,
        'motor_mode': rig.mode if s is not None else 'unavailable',
        'speed_setpoint_rpm': s['speed_setpoint_rpm'] if s else 0.0,
        'speed_rpm': s['speed_rpm'] if s else 0.0,
        'position_deg': s['position_deg'] if s else 0.0,
        'current_ia_ma': s['current_ia_ma'] if s else 0.0,
        'current_ib_ma': s['current_ib_ma'] if s else 0.0,
        'current_ic_ma': s['current_ic_ma'] if s else 0.0,
        'dc_link_v': s['dc_link_v'] if s else 0.0,
        'i_q': s['i_q'] if s else 0.0,
        'i_d': s['i_d'] if s else 0.0,
        'fault_active': any(s['faults'].values()) if s else False,
        'fault_status': json.dumps(s['faults']) if s else '{}',
        'anomaly': bool(s and model.ready() and score > model.threshold),
        'anomaly_score': score,
        'anomaly_threshold': model.threshold,
        'baseline_ready': model.ready(),
        'baseline_training': model.training(),
        'baseline_speed_rpm': model.baseline_speed,
        'random': random.randint(0, 100)
    }
    return telemetry


# --- OTA / file-download handling -------------------------------------------------

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
    # Never leave the motor spinning across a restart.
    try:
        rig.stop()
    except Exception:
        pass
    sys.stdout.flush()
    os.execv(sys.executable, [sys.executable, __file__] + sys.argv[1:])


# --- Cloud-to-device commands -------------------------------------------------------

def _ack(msg, ok: bool, detail: str):
    client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK if ok else C2dAck.CMD_FAILED, detail)


def on_command(msg):
    print('Received command', msg.command_name, msg.command_args, msg.ack_id)
    args = msg.command_args or []

    motor_cmds = ('set-speed', 'set-torque', 'set-mode', 'stop', 'clear-faults', 'train-baseline')
    if msg.command_name in motor_cmds and not rig.connect(force=True):
        _ack(msg, False, 'Motor stack unavailable: check the 24V DC link supply and that '
                         'the kd240-motor-ctrl-qei app is loaded (sudo xmutil listapps)')
        return

    if msg.command_name == 'set-speed':
        try:
            rpm = float(args[0])
        except (ValueError, IndexError):
            _ack(msg, False, 'Expected 1 numeric argument: rpm (0 stops; 250..10000 magnitude)')
            return
        ok, detail = rig.set_speed(rpm)
        _ack(msg, ok, detail)

    elif msg.command_name == 'set-torque':
        try:
            amps = float(args[0])
        except (ValueError, IndexError):
            _ack(msg, False, 'Expected 1 numeric argument: amps, -2.5..2.5')
            return
        ok, detail = rig.set_torque(amps)
        _ack(msg, ok, detail)

    elif msg.command_name == 'set-mode':
        if len(args) != 1:
            _ack(msg, False, 'Expected 1 argument: off | speed | torque')
            return
        ok, detail = rig.set_mode(args[0].strip().lower())
        _ack(msg, ok, detail)

    elif msg.command_name == 'stop':
        ok, detail = rig.stop()
        _ack(msg, ok, detail)

    elif msg.command_name == 'clear-faults':
        ok, detail = rig.clear_faults()
        _ack(msg, ok, detail)

    elif msg.command_name == 'train-baseline':
        seconds = 60.0
        if args and args[0].strip():
            try:
                seconds = float(args[0])
                if not 10.0 <= seconds <= 600.0:
                    raise ValueError
            except ValueError:
                _ack(msg, False, 'Expected training window in seconds, 10..600')
                return
        if rig.mode != 'speed' or abs(rig.speed_setpoint) < SPEED_MIN:
            _ack(msg, False, 'Run the motor at a steady speed first (set-speed), then train')
            return
        if model.training():
            _ack(msg, False, 'Training already in progress')
            return
        model.start_training(seconds, rig.speed_setpoint)
        _ack(msg, True, 'Training the healthy baseline for %g s at %g rpm' % (seconds, rig.speed_setpoint))

    elif msg.command_name == 'set-anomaly-threshold':
        try:
            value = float(args[0])
            if not 1.0 <= value <= 20.0:
                raise ValueError
        except (ValueError, IndexError):
            _ack(msg, False, 'Expected a number between 1.0 and 20.0 (robust z-score units)')
            return
        with model.lock:
            model.threshold = value
        model._save()
        _ack(msg, True, 'Anomaly threshold set to %g' % value)

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
                        _ack(msg, True, 'Downloaded and applied %s' % url)
                        print('OTA package applied. Restart scheduled...')
                        restart_pending.set()
                    else:
                        _ack(msg, False, 'Package extract or install.sh failed; not restarting')
                else:
                    status = 'Download failed: HTTP %d' % response.status_code
                    print(status)
                    _ack(msg, False, status)
            except Exception as e:
                status = 'Download error: %s' % e
                print(status)
                _ack(msg, False, status)
        else:
            _ack(msg, False, 'Expected 1 argument')

    else:
        print('Command %s not implemented!' % msg.command_name)
        if msg.ack_id is not None:
            _ack(msg, False, 'Not Implemented')


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


# --- Main ----------------------------------------------------------------------------

if __name__ == '__main__':
    if not FMC_AVAILABLE:
        _relaunch_with_motor_env()

    parser = argparse.ArgumentParser(description='IOTCONNECT KD240 motor control and anomaly detection demo')
    parser.add_argument('--dry-run', action='store_true',
                        help='sample the motor stack once (no motion) and print telemetry JSON')
    parser.add_argument('--spin-test', nargs='?', const=600.0, type=float, metavar='RPM',
                        help='LOCAL test: spin the motor at RPM (default 600) for 5 seconds, print readings, stop')
    cli = parser.parse_args()

    ams_path = find_hwmon('ams')

    if not FMC_AVAILABLE:
        print('WARNING: py_foc_motor_ctrl not importable; motor features disabled. '
              'Install xlnx-app-kd240-foc-motor-ctrl (see README).')

    if cli.spin_test is not None:
        if not 250.0 <= abs(cli.spin_test) <= 3000.0:
            print('spin test rpm must be 250..3000 in magnitude')
            sys.exit(1)
        if not rig.connect(force=True):
            print('Motor stack unavailable; check 24V DC link and loaded app.')
            sys.exit(1)
        ok, detail = rig.set_speed(cli.spin_test)
        print('set_speed:', ok, detail)
        try:
            for _ in range(5):
                time.sleep(1)
                s = rig.sample()
                if s:
                    print('rpm=%(speed_rpm)s ia=%(current_ia_ma)s mA iq=%(i_q)s vdc=%(dc_link_v)s V' % s)
        finally:
            ok, detail = rig.stop()
            print('stop:', ok, detail)
        sys.exit(0)

    if cli.dry_run:
        rig.connect(force=True)
        latest_sample = rig.sample()
        print(json.dumps(collect_telemetry(ams_path), indent=2))
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

    rig.connect(force=True)

    try:
        tick = 0
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

            # 1 Hz motor sampling; every 5th tick publishes telemetry.
            if rig.mc is None:
                rig.connect()
            latest_sample = rig.sample()
            if model.training():
                # Supervise the training window: a dead motor stack or a
                # changed operating point would poison the baseline.
                if latest_sample is None:
                    model.abort_training('motor stack unavailable')
                elif rig.mode != 'speed' or rig.speed_setpoint != model.baseline_speed:
                    model.abort_training('operating point changed')
            if latest_sample is not None:
                model.ingest(latest_sample)

            tick += 1
            if tick % 5 == 0:
                telemetry = collect_telemetry(ams_path)
                print('Telemetry: mode=%s rpm=%s score=%s anomaly=%s faults=%s' % (
                    telemetry['motor_mode'], telemetry['speed_rpm'],
                    telemetry['anomaly_score'], telemetry['anomaly'],
                    telemetry['fault_active']))
                client.send_telemetry(telemetry)
            time.sleep(1)

    except KeyboardInterrupt:
        print('Stopping motor and exiting.')
    finally:
        # Every exit path, including SystemExit and unexpected SDK errors,
        # must leave the motor stopped (the FOC IP keeps driving otherwise).
        rig.stop()
        if client:
            try:
                client.disconnect()
            except Exception:
                pass
