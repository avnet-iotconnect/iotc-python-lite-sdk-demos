# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

"""RZ/G3E EVK Vision Demo for /IOTCONNECT

Two USB cameras, two CPU vision pipelines, one cloud connection:

  Camera 1 -> face identity   (YuNet detect + SFace recognise, enrolment from the cloud)
  Camera 2 -> occupancy       (NanoDet person detector + zone entry/exit/dwell tracking)

This application:
  - Connects to /IOTCONNECT and streams telemetry every TELEMETRY_INTERVAL seconds
  - Hot-plugs USB cameras: pipelines pick up cameras as they appear (or share one)
  - Serves both annotated feeds and a status page at http://<board-ip>:8080/
  - Accepts C2D commands: set_mode, enroll, forget, list_faces, set_zone,
    set_confidence, set_face_threshold, reset_counts, swap_cameras, file-download
  - Applies OTA packages (tar.gz containing install.sh) and restarts itself
"""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, C2dOta, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.lite import __version__ as SDK_VERSION
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck

import system_monitor
import vision
import web_stream

TELEMETRY_INTERVAL = 5          # seconds
CAMERA_RESCAN_INTERVAL = 3      # seconds between USB camera rescans
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
MODES = ('both', 'faces', 'occupancy', 'off')

_DEFAULT_CONFIG = {
    'mode': 'both',
    'zone': [0.3, 0.05, 0.7, 0.95],
    'det_confidence': 0.4,
    'face_threshold': 0.363,
    'camera_order': [0, 1],     # index into the sorted USB camera list: [faces, occupancy]
    'mirror': True,             # horizontal flip so the feeds behave like a mirror
}

client = None
faces = None
occupancy = None
config = dict(_DEFAULT_CONFIG)
_state_lock = threading.Lock()
_cameras = []                   # current sorted list of /dev/videoN (one per USB camera)
_sources = {}                   # dev -> vision.CameraSource
_cloud_connected = False


# ─── Config persistence ───────────────────────────────────────────────────────

def load_config():
    global config
    try:
        with open(CONFIG_PATH) as f:
            saved = json.load(f)
        config = {**_DEFAULT_CONFIG, **saved}
    except FileNotFoundError:
        config = dict(_DEFAULT_CONFIG)
    except Exception as e:
        print(f'WARNING: config.json unreadable ({e}); using defaults')
        config = dict(_DEFAULT_CONFIG)


def save_config():
    try:
        tmp = CONFIG_PATH + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(config, f, indent=2)
        os.replace(tmp, CONFIG_PATH)
    except Exception as e:
        print(f'WARNING: could not save config.json: {e}')


# ─── USB camera discovery and assignment ─────────────────────────────────────

def detect_usb_cameras() -> list:
    """Return one /dev/videoN per physical USB camera, ordered by USB port path.

    A UVC camera exposes two video nodes (capture + metadata); only the lowest
    node per USB device is returned so callers see one entry per camera.
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
            last = os.path.basename(usb_iface)
            usb_root = os.path.dirname(usb_iface) if ':' in last else usb_iface
            if usb_root not in cameras:
                cameras[usb_root] = f'/dev/{dev}'
    except Exception as e:
        print(f'WARNING: USB camera detection failed: {e}')
    return [cameras[k] for k in sorted(cameras)]


def _assign_cameras(cams: list):
    """Give each pipeline a CameraSource: two cameras -> one each, one camera -> shared."""
    global _cameras
    order = config.get('camera_order', [0, 1])
    want = {}
    if len(cams) >= 2:
        want['faces'] = cams[order[0] % len(cams)]
        want['occupancy'] = cams[order[1] % len(cams)]
    elif len(cams) == 1:
        want['faces'] = want['occupancy'] = cams[0]
    # Stop sources for cameras that vanished.
    for dev in list(_sources):
        if dev not in want.values():
            _sources[dev].stop()
            del _sources[dev]
    for dev in set(want.values()):
        if dev not in _sources:
            _sources[dev] = vision.CameraSource(dev)
    faces.set_source(_sources.get(want.get('faces')))
    occupancy.set_source(_sources.get(want.get('occupancy')))
    _cameras = cams
    if cams:
        print(f'Cameras: faces={want.get("faces")}  occupancy={want.get("occupancy")}  ({len(cams)} USB camera(s))')
    else:
        print('Cameras: none detected - waiting for a USB camera to be plugged in')


def _camera_watch_loop():
    last = None
    while True:
        cams = detect_usb_cameras()
        if cams != last:
            with _state_lock:
                _assign_cameras(cams)
            last = cams
        time.sleep(CAMERA_RESCAN_INTERVAL)


def swap_cameras():
    with _state_lock:
        config['camera_order'] = list(reversed(config.get('camera_order', [0, 1])))
        save_config()
        _assign_cameras(_cameras)


# ─── Mode ─────────────────────────────────────────────────────────────────────

def apply_mode(mode: str):
    faces.enabled = mode in ('both', 'faces')
    occupancy.enabled = mode in ('both', 'occupancy')
    config['mode'] = mode


# ─── Telemetry ────────────────────────────────────────────────────────────────

_last_metrics = {}


def build_telemetry(consume_events: bool = True) -> dict:
    """Assemble the telemetry record. consume_events=False leaves the sticky
    unknown/known-seen flags untouched (used by the web status page)."""
    fr = faces.result
    orr = occupancy.result
    if consume_events:
        unknown_seen, known_names = faces.consume_events()
    else:
        unknown_seen, known_names = faces.unknown_seen, sorted(faces.known_seen)
    zone = config['zone']
    return {
        'sdk_version': SDK_VERSION,
        **_last_metrics,
        'cloud_connected': _cloud_connected,
        'mode': config['mode'],
        'cameras_connected': len(_cameras),
        # faces
        'faces_active': faces.active,
        'face_count': fr['face_count'],
        'known_count': fr['known_count'],
        'unknown_count': fr['unknown_count'],
        'identities': fr['identities'],
        'top_identity': fr['top_identity'],
        'top_confidence': fr['top_confidence'],
        'unknown_present': bool(unknown_seen),
        'known_seen': ', '.join(known_names),
        'enrolled_count': len(faces.enrolled_names()),
        'face_infer_ms': faces.infer_ms,
        'face_fps': faces.fps,
        # occupancy
        'occupancy_active': occupancy.active,
        'person_count': orr['person_count'],
        'zone_count': orr['zone_count'],
        'entries_total': occupancy.entries_total,
        'exits_total': occupancy.exits_total,
        'dwell_max_s': orr['dwell_max_s'],
        'dwell_avg_s': orr['dwell_avg_s'],
        'det_infer_ms': occupancy.infer_ms,
        'det_fps': occupancy.fps,
        'det_confidence': occupancy.confidence,
        'zone': ','.join(f'{v:.2f}' for v in zone),
        'mirror': vision.MIRROR,
    }


def _status_snapshot() -> dict:
    return build_telemetry(consume_events=False)


# ─── OTA ──────────────────────────────────────────────────────────────────────

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


def _restart_self():
    sys.stdout.flush()
    for src in _sources.values():
        src.stop()
    os.execv(sys.executable, [sys.executable, __file__] + sys.argv[1:])


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
        _restart_self()
    else:
        print('Encountered a download processing error. Not restarting.')
        client.send_ota_ack(msg, C2dAck.OTA_FAILED, 'OTA package failed to apply')


# ─── C2D commands ─────────────────────────────────────────────────────────────

def _ack(msg, ok: bool, status: str):
    print(f'  -> {"OK" if ok else "FAILED"}: {status}')
    client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK if ok else C2dAck.CMD_FAILED, status)


def on_command(msg: C2dCommand):
    name = msg.command_name
    args = list(msg.command_args or [])
    print(f'Received command: {name} args={args}')

    if name == 'set_mode':
        mode = (args[0].lower() if args else '')
        if mode not in MODES:
            return _ack(msg, False, f'Expected one of: {" | ".join(MODES)}')
        apply_mode(mode)
        save_config()
        return _ack(msg, True, f'mode={mode} (faces {"on" if faces.enabled else "off"}, '
                               f'occupancy {"on" if occupancy.enabled else "off"})')

    if name == 'enroll':
        person = ' '.join(args).strip()
        if not person:
            return _ack(msg, False, 'Expected a name, e.g. "enroll Alice"')
        print(f'  enrolling "{person}": look at camera 1 for a few seconds...')
        ok, status = faces.enroll(person)
        return _ack(msg, ok, status)

    if name == 'forget':
        person = ' '.join(args).strip()
        if not person:
            return _ack(msg, False, 'Expected a name, e.g. "forget Alice"')
        if person.lower() == 'all':
            for n in faces.enrolled_names():
                faces.forget(n)
            return _ack(msg, True, 'gallery cleared')
        ok = faces.forget(person)
        return _ack(msg, ok, f'forgot {person}' if ok else f'{person} is not enrolled')

    if name == 'list_faces':
        names = faces.enrolled_names()
        return _ack(msg, True, f'{len(names)} enrolled: {", ".join(names) or "(none)"}')

    if name == 'set_zone':
        try:
            vals = [float(v) for v in ' '.join(args).replace(',', ' ').split()]
            if len(vals) != 4 or not occupancy.set_zone(vals):
                raise ValueError
        except ValueError:
            return _ack(msg, False, 'Expected 4 normalised values x1,y1,x2,y2 in 0..1 (e.g. 0.3,0.05,0.7,0.95)')
        config['zone'] = list(occupancy.zone)
        save_config()
        return _ack(msg, True, f'zone={config["zone"]}')

    if name == 'set_confidence':
        try:
            v = float(args[0])
            if not 0.05 <= v <= 0.95:
                raise ValueError
        except (IndexError, ValueError):
            return _ack(msg, False, 'Expected a value between 0.05 and 0.95')
        occupancy.confidence = v
        config['det_confidence'] = v
        save_config()
        return _ack(msg, True, f'person detector confidence={v}')

    if name == 'set_face_threshold':
        try:
            v = float(args[0])
            if not 0.1 <= v <= 0.9:
                raise ValueError
        except (IndexError, ValueError):
            return _ack(msg, False, 'Expected a cosine-similarity threshold between 0.1 and 0.9 (default 0.363)')
        faces.match_threshold = v
        config['face_threshold'] = v
        save_config()
        return _ack(msg, True, f'face match threshold={v}')

    if name == 'set_mirror':
        val = (args[0].lower() if args else '')
        if val not in ('on', 'off', 'true', 'false', '1', '0'):
            return _ack(msg, False, 'Expected on | off')
        vision.MIRROR = val in ('on', 'true', '1')
        config['mirror'] = vision.MIRROR
        save_config()
        return _ack(msg, True, f'mirror={"on" if vision.MIRROR else "off"}')

    if name == 'reset_counts':
        occupancy.reset_counts()
        return _ack(msg, True, 'entry/exit counters reset')

    if name == 'swap_cameras':
        swap_cameras()
        return _ack(msg, True, f'camera order={config["camera_order"]} '
                               f'(faces={faces.source.dev if faces.source else "none"}, '
                               f'occupancy={occupancy.source.dev if occupancy.source else "none"})')

    if name == 'file-download':
        if len(args) != 1:
            return _ack(msg, False, 'Expected 1 argument: URL of a .tar.gz package')
        url = args[0]
        fname = os.path.basename(url.split('?', 1)[0]) or 'package.tar.gz'
        try:
            urllib.request.urlretrieve(url, fname)
        except Exception as e:
            return _ack(msg, False, f'download failed: {e}')
        if not fname.endswith('.tar.gz'):
            return _ack(msg, False, 'only .tar.gz packages are supported')
        ok = extract_and_run_tar_gz(fname)
        _ack(msg, ok, 'package applied, restarting' if ok else 'package failed to apply')
        if ok:
            _restart_self()
        return None

    return _ack(msg, False, f'unknown command: {name}')


def on_disconnect(reason: str, disconnected_from_server: bool):
    global _cloud_connected
    _cloud_connected = False
    print(f'Disconnected. Reason: {reason}')


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    global client, faces, occupancy, _cloud_connected, _last_metrics

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    load_config()

    missing = vision.missing_models()
    if missing:
        print(f'ERROR: model files missing from {vision.MODEL_DIR}: {", ".join(missing)}')
        print('Run:  bash get-models.sh')
        sys.exit(1)

    vision.MIRROR = bool(config.get('mirror', True))
    print('Loading models...')
    faces = vision.FacePipeline(web_stream.faces_feed, match_threshold=config['face_threshold'])
    occupancy = vision.OccupancyPipeline(web_stream.occupancy_feed,
                                         confidence=config['det_confidence'], zone=config['zone'])
    apply_mode(config['mode'])
    faces.start()
    occupancy.start()
    threading.Thread(target=_camera_watch_loop, name='camera-watch', daemon=True).start()
    web_stream.start(_status_snapshot, vision.FACES_DIR)

    try:
        device_config = DeviceConfig.from_iotc_device_config_json_file(
            device_config_json_path='iotcDeviceConfig.json',
            device_cert_path='device-cert.pem',
            device_pkey_path='device-pkey.pem'
        )
    except DeviceConfigError as e:
        print(e)
        print('Place iotcDeviceConfig.json, device-cert.pem and device-pkey.pem next to app.py (see README).')
        sys.exit(1)

    # Creating the Client performs HTTPS discovery, which fails while the network
    # is still coming up after boot. Keep retrying instead of crashing so the
    # web feeds stay available and the service log stays readable.
    attempt = 0
    while True:
        attempt += 1
        try:
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
            _cloud_connected = client.is_connected()
            if _cloud_connected:
                break
            print(f'Connect attempt {attempt} failed; retrying in 10 s')
        except Exception as e:
            print(f'Connect attempt {attempt} failed ({type(e).__name__}: {str(e).splitlines()[0] if str(e) else e}); '
                  f'retrying in 10 s')
        time.sleep(10)
    print('Connected to /IOTCONNECT')

    print('\n' + '=' * 60)
    print('RZ/G3E Vision Demo running')
    print(f'Mode: {config["mode"]}   Enrolled faces: {len(faces.enrolled_names())}')
    print(f'Telemetry interval: {TELEMETRY_INTERVAL} s')
    print('Commands: set_mode | enroll <name> | forget <name> | list_faces | set_zone |')
    print('          set_confidence | set_face_threshold | set_mirror | reset_counts | swap_cameras | file-download')
    print('Press Ctrl+C to exit')
    print('=' * 60 + '\n')

    try:
        while True:
            if not client.is_connected():
                _cloud_connected = False
                print('Connection lost, reconnecting...')
                client.connect()
                _cloud_connected = client.is_connected()
            _last_metrics = system_monitor.get_all_metrics()
            t = build_telemetry()
            print(f'cpu={t["cpu_percent"]}% {t["cpu_temp_c"]}C | '
                  f'faces={t["face_count"]} known={t["known_count"]} unknown={t["unknown_count"]} '
                  f'[{t["identities"] or "-"}] {t["face_infer_ms"]}ms {t["face_fps"]}fps | '
                  f'people={t["person_count"]} zone={t["zone_count"]} in={t["entries_total"]} out={t["exits_total"]} '
                  f'dwell={t["dwell_max_s"]}s {t["det_infer_ms"]}ms {t["det_fps"]}fps'
                  f'{"  ** UNKNOWN PERSON **" if t["unknown_present"] else ""}')
            client.send_telemetry(t)
            time.sleep(TELEMETRY_INTERVAL)
    except KeyboardInterrupt:
        print('\nShutting down...')
        for src in _sources.values():
            src.stop()
        client.disconnect()
        print('Shutdown complete.')
        sys.exit(0)


if __name__ == '__main__':
    main()
