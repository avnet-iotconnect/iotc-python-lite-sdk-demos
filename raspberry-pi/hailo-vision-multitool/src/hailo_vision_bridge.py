"""
"Hailo Vision Multi-Tool" — cloud-retaskable CNN vision on Hailo-8 + /IOTCONNECT.

One device, three heavyweight YOLOv8m pipelines — object detection, pose
estimation, instance segmentation — switched live from the /IOTCONNECT
dashboard (`set-mode pose`). Where the CLIP demo re-aims *what* the camera
looks for, this demo re-tasks *the entire vision workload* — and these
CNN pipelines are what the Hailo-8 excels at (full camera rate, yolov8m).

Telemetry @1 Hz (template HVISION): mode, person_count, object_count,
objects (json label->count), top_object, fps, cpu_temp, alert.
Commands: set-mode (detect|pose|segment), set-alert-count <n>.
Local fallback control (no cloud needed): GET /cmd?name=set-mode&arg=pose

Run on the board:  ./run.sh   (from this directory; certs optional)
"""

import argparse
import json
import os
import sys
import threading
import time
from collections import Counter

BRIDGE_DIR = os.path.dirname(os.path.abspath(__file__))

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, Callbacks
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck

os.environ["GST_PLUGIN_FEATURE_RANK"] = "vaapidecodebin:NONE"
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

import hailo
from hailo_apps.python.core.gstreamer.gstreamer_app import app_callback_class
from hailo_apps.python.core.common.buffer_utils import get_caps_from_pad, get_numpy_from_buffer

MODES = ("detect", "pose", "segment")


class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.mode = "detect"
        self.requested_mode = None      # set by commands; consumed by main loop
        self.person_count = 0
        self.object_counts = {}
        self.alert_count = 3            # alert when person_count >= this
        self.frame = None
        self.last_frame_copy = 0.0
        self.frame_times = []
        self.commands = []
        self.app_ref = None             # current GStreamerApp, for shutdown()

    def record_command(self, source, name, args):
        with self.lock:
            self.commands.append({
                "t": time.strftime("%H:%M:%S"),
                "source": source,
                "name": name,
                "args": " ".join(args) if args else "",
            })
            del self.commands[:-15]

    def fps(self):
        with self.lock:
            t = [x for x in self.frame_times if x > time.time() - 5.0]
            self.frame_times = t
        if len(t) < 2:
            return 0.0
        return (len(t) - 1) / max(t[-1] - t[0], 1e-6)


STATE = SharedState()


def app_callback(element, buffer, user_data):
    if buffer is None or not isinstance(buffer, Gst.Buffer):
        return Gst.PadProbeReturn.OK
    now = time.time()

    persons, labels = 0, Counter()
    try:
        roi = hailo.get_roi_from_buffer(buffer)
        for det in roi.get_objects_typed(hailo.HAILO_DETECTION):
            label = det.get_label()
            labels[label] += 1
            if label == "person":
                persons += 1
    except Exception:
        pass

    with STATE.lock:
        STATE.frame_times.append(now)
        STATE.person_count = persons
        STATE.object_counts = dict(labels)
        want_frame = now - STATE.last_frame_copy > 0.1
    if want_frame and user_data.use_frame:
        try:
            pad = element.get_static_pad("src") if hasattr(element, "get_static_pad") else element
            fmt, width, height = get_caps_from_pad(pad)
            if fmt is not None:
                frame = get_numpy_from_buffer(buffer, fmt, width, height)
                with STATE.lock:
                    STATE.frame = frame[:, :, ::-1].copy()
                    STATE.last_frame_copy = now
        except Exception:
            pass
    return Gst.PadProbeReturn.OK


# ---------------- commands ----------------

def request_mode(mode):
    mode = mode.strip().lower()
    if mode not in MODES:
        return False, "unknown mode %r (use %s)" % (mode, "|".join(MODES))
    with STATE.lock:
        if mode == STATE.mode:
            return True, "already in %s mode" % mode
        STATE.requested_mode = mode
        app = STATE.app_ref
    if app is not None:
        app.shutdown()   # run() returns; main loop starts the new pipeline
    return True, "switching to %s" % mode


def handle_command(source, name, args):
    STATE.record_command(source, name, args)
    if name == "set-mode" and args:
        return request_mode(args[0])
    if name == "set-alert-count" and args:
        try:
            STATE.alert_count = max(0, int(float(args[0])))
            return True, "alert_count=%d" % STATE.alert_count
        except ValueError:
            return False, "bad number"
    return False, "unknown command"


def make_command_cb(client_ref):
    def on_command(msg: C2dCommand):
        ok, note = handle_command("cloud", msg.command_name, msg.command_args or [])
        c = client_ref.get("client")
        if c is not None and msg.ack_id is not None:
            c.send_command_ack(
                msg, C2dAck.CMD_SUCCESS_WITH_ACK if ok else C2dAck.CMD_FAILED, note)
        print("[iotc] cmd %s %s -> %s" % (msg.command_name, msg.command_args, note))
    return on_command


# ---------------- telemetry ----------------

def cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return -1.0


def telemetry_loop(client_ref):
    while True:
        time.sleep(1.0)
        c = client_ref.get("client")
        if c is None or not getattr(c, "is_connected", lambda: True)():
            continue
        with STATE.lock:
            mode = STATE.mode
            persons = STATE.person_count
            counts = dict(STATE.object_counts)
            alert_n = STATE.alert_count
        top_object = max(counts, key=counts.get) if counts else ""
        try:
            c.send_telemetry({
                "mode": mode,
                "person_count": persons,
                "object_count": sum(counts.values()),
                "objects": json.dumps(counts),
                "top_object": top_object,
                "fps": round(STATE.fps(), 2),
                "cpu_temp": round(cpu_temp(), 1),
                "alert": 1 if persons >= alert_n else 0,
            })
        except Exception as e:
            print("[iotc] telemetry error:", e)


def start_iotc():
    client_ref = {"client": None}
    cfg_json = os.path.join(BRIDGE_DIR, "iotcDeviceConfig.json")
    if not os.path.isfile(cfg_json):
        print("[iotc] %s not found — running OFFLINE" % cfg_json)
        return client_ref
    device_config = DeviceConfig.from_iotc_device_config_json_file(
        device_config_json_path=cfg_json,
        device_cert_path=os.path.join(BRIDGE_DIR, "device-cert.pem"),
        device_pkey_path=os.path.join(BRIDGE_DIR, "device-pkey.pem"),
    )
    c = Client(config=device_config,
               callbacks=Callbacks(command_cb=make_command_cb(client_ref)))
    c.connect()
    client_ref["client"] = c
    print("[iotc] connected")
    return client_ref


# ---------------- web ----------------

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Hailo Vision Multi-Tool</title><style>
 body{margin:0;background:#0d0d0d;color:#fff;font:16px/1.5 system-ui,sans-serif;padding:20px}
 .wrap{display:flex;flex-wrap:wrap;gap:16px}
 img{max-width:100%;border-radius:8px}
 .video{flex:2;min-width:320px}.side{flex:1;min-width:260px}
 h1{font-size:17px;margin:0 0 10px;color:#c3c2b7}
 .mode{display:inline-block;padding:6px 14px;margin:0 8px 12px 0;border-radius:16px;
       background:#2c2c2a;color:#c3c2b7;cursor:pointer;border:none;font:inherit}
 .mode.active{background:#0ca30c;color:#fff;font-weight:700}
 .big{font-size:44px;font-weight:800}
 .muted{color:#898781;font-size:13px}
 .obj{margin:2px 0;color:#e8e7e0}
</style></head><body>
<div class="wrap">
 <div class="video"><img src="/stream.mjpg"></div>
 <div class="side">
  <h1>PIPELINE</h1>
  <div id="modes"></div>
  <h1>PEOPLE IN VIEW</h1><div class="big" id="persons">0</div>
  <h1>OBJECTS</h1><div id="objects" class="muted">(none)</div>
  <div class="muted" id="meta" style="margin-top:10px"></div>
 </div>
</div><script>
const MODES = ["detect","pose","segment"];
function setMode(m){ fetch('/cmd?name=set-mode&arg='+m); }
async function tick(){
 try{
  const s = await (await fetch('/state.json')).json();
  document.getElementById('modes').innerHTML = MODES.map(m=>
    `<button class="mode ${m===s.mode?'active':''}" onclick="setMode('${m}')">${m}</button>`).join('');
  document.getElementById('persons').textContent = s.person_count;
  const objs = Object.entries(s.objects);
  document.getElementById('objects').innerHTML = objs.length
    ? objs.sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<div class="obj">${k} × ${v}</div>`).join('')
    : '(none)';
  document.getElementById('meta').textContent =
    `fps ${s.fps} · cpu ${s.cpu_temp}°C · alert at ≥${s.alert_count} people`;
 }catch(e){}
 setTimeout(tick, 1000);
}
tick();
</script></body></html>"""

CAMERA_PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Camera</title><style>html,body{margin:0;height:100%;background:#000}
img{width:100%;height:100%;object-fit:contain;display:block}</style></head>
<body><img src="/stream.mjpg"></body></html>"""


def start_web(port):
    import cv2
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlparse, parse_qs

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path in ("/", "/index.html"):
                self._send(200, "text/html; charset=utf-8", PAGE.encode())
            elif u.path == "/camera":
                self._send(200, "text/html; charset=utf-8", CAMERA_PAGE.encode())
            elif u.path == "/cmd":
                q = parse_qs(u.query)
                name = (q.get("name") or [""])[0]
                arg = (q.get("arg") or [None])[0]
                ok, note = handle_command("web", name, [arg] if arg else [])
                self._send(200 if ok else 400, "application/json",
                           json.dumps({"ok": ok, "note": note}).encode())
            elif u.path == "/state.json":
                with STATE.lock:
                    data = {
                        "mode": STATE.mode,
                        "person_count": STATE.person_count,
                        "objects": dict(STATE.object_counts),
                        "alert_count": STATE.alert_count,
                        "commands": list(STATE.commands),
                    }
                # fps() takes STATE.lock itself — must be called outside it
                data["fps"] = round(STATE.fps(), 1)
                data["cpu_temp"] = round(cpu_temp(), 1)
                self._send(200, "application/json", json.dumps(data).encode())
            elif u.path == "/stream.mjpg":
                self.send_response(200)
                self.send_header("Content-Type",
                                 "multipart/x-mixed-replace; boundary=frame")
                self.end_headers()
                try:
                    while True:
                        with STATE.lock:
                            frame = STATE.frame
                        if frame is not None:
                            ok, jpg = cv2.imencode(".jpg", frame,
                                                   [cv2.IMWRITE_JPEG_QUALITY, 70])
                            if ok:
                                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                                 b"Content-Length: " + str(len(jpg)).encode()
                                                 + b"\r\n\r\n" + jpg.tobytes() + b"\r\n")
                        time.sleep(0.1)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self._send(404, "text/plain", b"not found")

    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print("[web] serving on port %d" % port)
    return srv


# ---------------- app factory / main ----------------

def build_app(mode, input_arg):
    """Construct the pipeline app for a mode. Each parses sys.argv itself."""
    sys.argv = [sys.argv[0], "--input", input_arg, "--use-frame", "--disable-sync"]
    user_data = app_callback_class()
    if mode == "pose":
        from hailo_apps.python.pipeline_apps.pose_estimation.pose_estimation_pipeline import GStreamerPoseEstimationApp
        return GStreamerPoseEstimationApp(app_callback, user_data)
    if mode == "segment":
        from hailo_apps.python.pipeline_apps.instance_segmentation.instance_segmentation_pipeline import GStreamerInstanceSegmentationApp
        return GStreamerInstanceSegmentationApp(app_callback, user_data)
    from hailo_apps.python.pipeline_apps.detection.detection_pipeline import GStreamerDetectionApp
    return GStreamerDetectionApp(app_callback, user_data)


def main():
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--input", default="/dev/video0")
    ap.add_argument("--serve", type=int, default=8081)
    ap.add_argument("--mode", default="detect", choices=MODES)
    args, _ = ap.parse_known_args()

    with STATE.lock:
        STATE.mode = args.mode

    client_ref = start_iotc()
    if args.serve:
        start_web(args.serve)
    threading.Thread(target=telemetry_loop, args=(client_ref,), daemon=True).start()

    while True:
        with STATE.lock:
            mode = STATE.requested_mode or STATE.mode
            STATE.mode = mode
            STATE.requested_mode = None
        print("[mode] starting %s pipeline" % mode)
        app = build_app(mode, args.input)
        with STATE.lock:
            STATE.app_ref = app
        try:
            app.run()   # framework always sys.exit()s after its loop ends
        except SystemExit:
            pass        # swallow it: we own the process lifecycle, not the app
        with STATE.lock:
            STATE.app_ref = None
            pending = STATE.requested_mode
        if pending is None:
            print("[mode] pipeline exited with no pending mode; quitting")
            break
        time.sleep(1.0)  # let the device/camera settle before rebuild


if __name__ == "__main__":
    main()
