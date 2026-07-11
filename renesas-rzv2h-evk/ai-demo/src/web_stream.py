# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

"""Board-hosted MJPEG streaming for the RZ/V2H AI demo.

Serves both demo video feeds over HTTP so no HDMI monitor is needed to watch
them:

  http://<board-ip>:8080/       — HTML page showing both feeds side by side
  http://<board-ip>:8080/cv     — Python CV annotated camera frames (MJPEG)
  http://<board-ip>:8080/drpai  — Weston desktop capture (MJPEG)

The DRP-AI binaries render straight to the Wayland compositor, so their feed
is produced by screenshotting the compositor with weston-screenshooter. That
requires weston to be started with --debug (output-capture authorization).

Frames are captured/encoded lazily — only while at least one HTTP client is
connected to the corresponding endpoint.
"""

import glob
import os
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

PORT = 8080
_BOUNDARY = 'mjpegframe'
_JPEG_QUALITY = 75
_CAPTURE_DIR = '/tmp/webstream_capture'
_DESKTOP_MAX_WIDTH = 1280   # downscale desktop grabs to keep the stream light
_DESKTOP_PERIOD = 0.5       # target ~2 fps; screenshooter round-trip is ~300ms
_READER_TIMEOUT = 2.0       # send placeholder if no fresh frame within this


def _placeholder_jpeg(text: str) -> bytes:
    img = np.full((360, 640, 3), 40, dtype=np.uint8)
    cv2.putText(img, text, (30, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
    ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY])
    return buf.tobytes() if ok else b''


class _Feed:
    """Latest-frame buffer with change notification and reader accounting."""

    def __init__(self, idle_text: str):
        self._cond = threading.Condition()
        self._jpeg = None
        self._seq = 0
        self._readers = 0
        self._placeholder = _placeholder_jpeg(idle_text)

    @property
    def has_readers(self) -> bool:
        return self._readers > 0

    def add_reader(self):
        with self._cond:
            self._readers += 1

    def remove_reader(self):
        with self._cond:
            self._readers -= 1

    def publish_text(self, label: str, detail: str = '') -> None:
        """Publish a status card (e.g. 'stopped', 'in use by ...') to the feed."""
        self.publish(_info_frame(label, detail))

    def publish(self, frame) -> None:
        """Encode a BGR ndarray and wake all waiting readers."""
        ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY])
        if not ok:
            return
        with self._cond:
            self._jpeg = buf.tobytes()
            self._seq += 1
            self._cond.notify_all()

    def next_jpeg(self, last_seq: int) -> tuple:
        """Block until a frame newer than last_seq arrives (or timeout).

        Returns (jpeg_bytes, seq). On timeout the LAST frame is re-sent, never
        the placeholder — swapping to a placeholder during a slow patch makes
        the stream visibly flicker. The placeholder appears only before the
        first frame ever arrives; capture loops publish explicit status cards
        for busy/stopped states.
        """
        with self._cond:
            self._cond.wait_for(lambda: self._seq != last_seq, timeout=_READER_TIMEOUT)
            if self._jpeg is not None:
                return self._jpeg, self._seq
            return self._placeholder, self._seq


cv_feed = _Feed('CV inference not running (send start_detection)')
desktop_feed = _Feed('Desktop capture idle (is Weston running?)')

# endpoint name ('cam1') -> (label, device path, _Feed) — populated by start()
camera_feeds = {}


# ─── Direct USB camera feeds ──────────────────────────────────────────────────

_CAM_WIDTH = 640
_CAM_HEIGHT = 480
_CAM_FPS = 15


def _disable_dynamic_framerate(dev: str) -> None:
    """Stop UVC auto-exposure from stretching the frame interval.

    With exposure_dynamic_framerate=1 (the C920 default) the camera drops to
    1-2 fps in anything less than bright light, which makes the MJPEG stream
    stutter badly. Constant framerate costs a slightly darker image instead.
    """
    try:
        subprocess.run(
            ['v4l2-ctl', '-d', dev, '--set-ctrl=exposure_dynamic_framerate=0'],
            capture_output=True, timeout=5,
        )
    except Exception as e:
        print(f'[web_stream] could not set constant framerate on {dev}: {e}')


def _info_frame(label: str, detail: str):
    img = np.full((360, 640, 3), 40, dtype=np.uint8)
    cv2.putText(img, label, (30, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
    cv2.putText(img, detail, (30, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 180, 220), 1)
    return img


def _camera_capture_loop(label: str, dev: str, feed: _Feed, busy_fn):
    """Stream a USB camera while it is not claimed by CV inference or DRP-AI.

    V4L2 devices cannot be streamed by two processes at once, so this loop
    releases the camera the moment busy_fn reports another owner and shows an
    'in use' card instead. It also releases when nobody is watching the feed.
    """
    cap = None
    last_info_pub = 0.0
    ctrl_set = False  # constant-framerate control asserted for the current open

    def _release():
        nonlocal cap
        if cap is not None:
            cap.release()
            cap = None

    while True:
        if not feed.has_readers:
            _release()
            time.sleep(0.5)
            continue

        reason = busy_fn(dev) if busy_fn else ''
        if reason:
            _release()
            if time.time() - last_info_pub > 1.0:
                feed.publish(_info_frame(label, f'in use by {reason}'))
                last_info_pub = time.time()
            time.sleep(0.2)
            continue

        if cap is None:
            cap = cv2.VideoCapture(dev)
            if cap.isOpened():
                # MJPG uses ~1/10th the USB bandwidth of raw YUYV. The RZ/V2H
                # xHCI drops isochronous transfers (torn frames) under the
                # combined load of two cameras — compressed capture avoids it.
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, _CAM_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, _CAM_HEIGHT)
                cap.set(cv2.CAP_PROP_FPS, _CAM_FPS)
                ctrl_set = False
            else:
                _release()
                if time.time() - last_info_pub > 1.0:
                    feed.publish(_info_frame(label, 'camera unavailable (device busy?)'))
                    last_info_pub = time.time()
                time.sleep(2.0)
                continue

        ret, frame = cap.read()
        if not ret:
            _release()
            time.sleep(1.0)
            continue

        if not ctrl_set:
            # Must be asserted after streaming has begun — the C920 reverts
            # this control on stream start, undoing a set done at open time.
            _disable_dynamic_framerate(dev)
            ctrl_set = True

        cv2.rectangle(frame, (0, 0), (frame.shape[1], 26), (0, 0, 0), -1)
        cv2.putText(frame, f'{label} ({dev})', (8, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        feed.publish(frame)


# ─── Weston desktop capture (DRP-AI demo output) ─────────────────────────────

def _desktop_capture_loop(wayland_env: dict):
    os.makedirs(_CAPTURE_DIR, exist_ok=True)
    env = {**os.environ, **wayland_env}
    warned = False
    while True:
        if not desktop_feed.has_readers:
            time.sleep(0.5)
            continue
        t0 = time.time()
        try:
            for stale in glob.glob(os.path.join(_CAPTURE_DIR, '*.png')):
                os.remove(stale)
            r = subprocess.run(
                ['weston-screenshooter'],
                cwd=_CAPTURE_DIR, env=env, capture_output=True, timeout=5,
            )
            shots = glob.glob(os.path.join(_CAPTURE_DIR, '*.png'))
            if not shots:
                if not warned:
                    err = r.stderr.decode(errors='replace').strip()
                    print(f'[web_stream] desktop capture failed: {err or "no screenshot produced"} '
                          f'(weston running with --debug?)')
                    warned = True
                time.sleep(2.0)
                continue
            warned = False
            img = cv2.imread(shots[0])
            os.remove(shots[0])
            if img is None:
                continue
            h, w = img.shape[:2]
            if w > _DESKTOP_MAX_WIDTH:
                scale = _DESKTOP_MAX_WIDTH / w
                img = cv2.resize(img, (_DESKTOP_MAX_WIDTH, int(h * scale)))
            desktop_feed.publish(img)
        except Exception as e:
            if not warned:
                print(f'[web_stream] desktop capture error: {e}')
                warned = True
            time.sleep(2.0)
        time.sleep(max(0.0, _DESKTOP_PERIOD - (time.time() - t0)))


# ─── HTTP server ──────────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>RZ/V2H AI Demo — Live Feeds</title>
<style>
  body { background:#16161a; color:#ddd; font-family:sans-serif; margin:1.5em; }
  h1 { font-size:1.3em; } h2 { font-size:1em; color:#9ac; }
  .feeds { display:flex; flex-wrap:wrap; gap:1.5em; }
  .feed img { max-width:100%%; border:1px solid #333; border-radius:4px; }
  .feed { flex:1 1 480px; max-width:1280px; }
</style>
</head>
<body>
<h1>RZ/V2H EVK AI Demo — Live Feeds</h1>
<div class="feeds">
%s
</div>
</body>
</html>
"""


def _index_html() -> bytes:
    panels = []
    for name, (label, dev, _feed) in camera_feeds.items():
        panels.append(f'  <div class="feed"><h2>{label} — {dev}</h2><img src="/{name}" alt="{label}"></div>')
    panels.append('  <div class="feed"><h2>Python CV — face/person detection</h2><img src="/cv" alt="CV feed"></div>')
    panels.append('  <div class="feed"><h2>DRP-AI demo — HDMI desktop capture</h2><img src="/drpai" alt="DRP-AI feed"></div>')
    return (_HTML_TEMPLATE % '\n'.join(panels)).encode('utf-8')


class _Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass  # keep the app console clean

    def do_GET(self):
        name = self.path.lstrip('/')
        if self.path in ('/', '/index.html'):
            body = _index_html()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == '/cv':
            self._stream(cv_feed)
        elif self.path == '/drpai':
            self._stream(desktop_feed)
        elif name in camera_feeds:
            self._stream(camera_feeds[name][2])
        else:
            self.send_response(404)
            self.send_header('Content-Length', '0')
            self.end_headers()

    def _stream(self, feed: _Feed):
        self.send_response(200)
        self.send_header('Cache-Control', 'no-cache, private')
        self.send_header('Content-Type', f'multipart/x-mixed-replace; boundary={_BOUNDARY}')
        self.end_headers()
        feed.add_reader()
        last_seq = -1
        try:
            while True:
                jpeg, last_seq = feed.next_jpeg(last_seq)
                self.wfile.write(
                    b'--' + _BOUNDARY.encode() + b'\r\n'
                    b'Content-Type: image/jpeg\r\n'
                    b'Content-Length: ' + str(len(jpeg)).encode() + b'\r\n\r\n'
                )
                self.wfile.write(jpeg)
                self.wfile.write(b'\r\n')
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass  # viewer closed the tab
        finally:
            feed.remove_reader()


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '<board-ip>'


_started = False


def start(wayland_env: dict, cameras: list = None, camera_busy_fn=None) -> None:
    """Start the MJPEG HTTP server and capture threads (idempotent).

    cameras: list of V4L2 device paths — one raw feed is served per camera
    (endpoints /cam1, /cam2, ...). camera_busy_fn(dev) returns a human-readable
    owner name when another consumer (CV inference, DRP-AI) holds the device,
    or '' when the camera is free to stream.
    """
    global _started
    if _started:
        return
    _started = True

    for i, dev in enumerate(cameras or [], start=1):
        name = f'cam{i}'
        label = f'Camera {i}'
        feed = _Feed(f'{label} idle')
        camera_feeds[name] = (label, dev, feed)
        threading.Thread(
            target=_camera_capture_loop,
            args=(label, dev, feed, camera_busy_fn),
            daemon=True,
        ).start()

    server = ThreadingHTTPServer(('0.0.0.0', PORT), _Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=_desktop_capture_loop, args=(wayland_env,), daemon=True).start()
    endpoints = ', '.join(f'/{n}' for n in camera_feeds) + ', /cv, /drpai'
    print(f'Live video feeds: http://{_local_ip()}:{PORT}/  (MJPEG: {endpoints})')
