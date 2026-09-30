# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

"""Board-hosted MJPEG streaming and status page for the RZ/G3E vision demo.

No HDMI monitor is needed: both annotated pipeline feeds are served over HTTP.

  http://<board-ip>:8080/            page with both feeds and a live stats strip
  http://<board-ip>:8080/faces       face identity feed (MJPEG)
  http://<board-ip>:8080/occupancy   occupancy feed (MJPEG)
  http://<board-ip>:8080/status      current telemetry snapshot (JSON)
  http://<board-ip>:8080/gallery     enrolled face thumbnails (HTML)

Frames are JPEG-encoded only while at least one HTTP client is watching the
corresponding feed, so the streams cost nothing when nobody is looking.
"""

import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

PORT = 8080
_BOUNDARY = 'mjpegframe'
_JPEG_QUALITY = 75
_READER_TIMEOUT = 2.0       # re-send the last frame if nothing new arrives within this


def _placeholder_jpeg(text: str) -> bytes:
    img = np.full((480, 640, 3), 40, dtype=np.uint8)
    cv2.putText(img, text, (30, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2, cv2.LINE_AA)
    ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY])
    return buf.tobytes() if ok else b''


class Feed:
    """Latest-frame buffer with change notification and reader accounting."""

    def __init__(self, idle_text: str):
        self._cond = threading.Condition()
        self._jpeg = None
        self._seq = 0
        self._readers = 0
        self._last_pub = 0.0
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

    def publish(self, frame) -> None:
        """Encode a BGR ndarray and wake all waiting readers.

        Without stream readers, frames are still encoded about once a second so
        the single-frame endpoints (/faces.jpg, /occupancy.jpg) stay current.
        """
        now = time.time()
        if self._readers == 0 and now - self._last_pub < 1.0:
            return
        ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY])
        if not ok:
            return
        with self._cond:
            self._jpeg = buf.tobytes()
            self._seq += 1
            self._last_pub = now
            self._cond.notify_all()

    def latest_jpeg(self) -> bytes:
        with self._cond:
            return self._jpeg or self._placeholder

    def next_jpeg(self, last_seq: int) -> tuple:
        """Block until a frame newer than last_seq arrives (or timeout, re-sending the last)."""
        with self._cond:
            self._cond.wait_for(lambda: self._seq != last_seq, timeout=_READER_TIMEOUT)
            if self._jpeg is not None:
                return self._jpeg, self._seq
            return self._placeholder, self._seq


faces_feed = Feed('Face identity feed starting...')
occupancy_feed = Feed('Occupancy feed starting...')

_status_fn = None     # callable returning the telemetry dict
_faces_dir = ''


_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>RZ/G3E Vision Demo</title>
<style>
  body { background:#16161a; color:#ddd; font-family:sans-serif; margin:1.2em; }
  h1 { font-size:1.3em; margin:0 0 .4em 0; } h2 { font-size:1em; color:#9ac; margin:.2em 0; }
  .feeds { display:flex; flex-wrap:wrap; gap:1.2em; }
  .feed { flex:1 1 480px; max-width:960px; }
  .feed img { width:100%%; border:1px solid #333; border-radius:4px; }
  .stats { display:flex; flex-wrap:wrap; gap:.6em 1.6em; margin:.6em 0 1em 0; font-size:.95em; }
  .stats span b { color:#fff; }
  .alert { color:#ff6b6b; font-weight:bold; }
  a { color:#9ac; }
</style>
</head>
<body>
<h1>Renesas RZ/G3E — /IOTCONNECT Vision Demo</h1>
<div class="stats" id="stats">loading status...</div>
<div class="feeds">
  <div class="feed"><h2>Camera 1 — face identity (YuNet + SFace)</h2><img src="/faces" alt="faces"></div>
  <div class="feed"><h2>Camera 2 — occupancy (NanoDet person detector)</h2><img src="/occupancy" alt="occupancy"></div>
</div>
<p><a href="/gallery">Enrolled faces</a> &middot; <a href="/status">Raw status JSON</a></p>
<script>
async function poll() {
  try {
    const s = await (await fetch('/status', {cache: 'no-store'})).json();
    const f = (k, d=0) => (s[k] === undefined ? d : s[k]);
    document.getElementById('stats').innerHTML =
      `<span>Mode <b>${f('mode','-')}</b></span>` +
      `<span>Cameras <b>${f('cameras_connected')}</b></span>` +
      `<span>Faces <b>${f('face_count')}</b> known <b>${f('known_count')}</b> unknown <b>${f('unknown_count')}</b></span>` +
      `<span>Identities <b>${f('identities','') || '-'}</b></span>` +
      (f('unknown_present') ? `<span class="alert">UNKNOWN PERSON</span>` : '') +
      `<span>People <b>${f('person_count')}</b> in zone <b>${f('zone_count')}</b></span>` +
      `<span>Entries <b>${f('entries_total')}</b> exits <b>${f('exits_total')}</b> dwell max <b>${f('dwell_max_s')}s</b></span>` +
      `<span>Face ${f('face_infer_ms')} ms / ${f('face_fps')} fps &middot; Detector ${f('det_infer_ms')} ms / ${f('det_fps')} fps</span>` +
      `<span>CPU <b>${f('cpu_percent')}%%</b> ${f('cpu_temp_c')}&deg;C &middot; RAM ${f('memory_percent')}%%</span>` +
      `<span>Cloud <b>${f('cloud_connected') ? 'connected' : 'offline'}</b></span>`;
  } catch (e) { /* board restarting */ }
}
poll(); setInterval(poll, 2000);
</script>
</body>
</html>
"""


class _Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass  # keep the app console clean

    def _send(self, code: int, ctype: str, body: bytes):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path in ('/', '/index.html'):
            self._send(200, 'text/html; charset=utf-8', _HTML.encode('utf-8'))
        elif path == '/faces':
            self._stream(faces_feed)
        elif path == '/occupancy':
            self._stream(occupancy_feed)
        elif path == '/faces.jpg':
            self._send(200, 'image/jpeg', faces_feed.latest_jpeg())
        elif path == '/occupancy.jpg':
            self._send(200, 'image/jpeg', occupancy_feed.latest_jpeg())
        elif path == '/status':
            data = _status_fn() if _status_fn else {}
            self._send(200, 'application/json', json.dumps(data).encode('utf-8'))
        elif path == '/gallery':
            self._send(200, 'text/html; charset=utf-8', _gallery_html().encode('utf-8'))
        elif path.startswith('/gallery/') and path.endswith('.jpg'):
            name = os.path.basename(path)
            fpath = os.path.join(_faces_dir, name)
            if _faces_dir and os.path.isfile(fpath):
                with open(fpath, 'rb') as f:
                    self._send(200, 'image/jpeg', f.read())
            else:
                self._send(404, 'text/plain', b'not found')
        else:
            self._send(404, 'text/plain', b'not found')

    def _stream(self, feed: Feed):
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
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            pass  # viewer closed the tab
        finally:
            feed.remove_reader()


def _gallery_html() -> str:
    items = []
    if _faces_dir and os.path.isdir(_faces_dir):
        for fn in sorted(os.listdir(_faces_dir)):
            if fn.endswith('.jpg'):
                items.append(f'<div style="text-align:center"><img src="/gallery/{fn}" width="112" height="112" '
                             f'style="border-radius:6px;border:1px solid #333"><br>{fn[:-4]}</div>')
    body = ''.join(items) or '<p>No faces enrolled yet. Send the <code>enroll &lt;name&gt;</code> command from /IOTCONNECT.</p>'
    return (f'<!doctype html><html><head><meta charset="utf-8"><title>Enrolled faces</title>'
            f'<style>body{{background:#16161a;color:#ddd;font-family:sans-serif;margin:1.2em}}'
            f'.g{{display:flex;flex-wrap:wrap;gap:1em}} a{{color:#9ac}}</style></head><body>'
            f'<h1 style="font-size:1.2em">Enrolled faces</h1><div class="g">{body}</div>'
            f'<p><a href="/">back</a></p></body></html>')


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '<board-ip>'


_started = False


def start(status_fn, faces_dir: str) -> None:
    """Start the HTTP server (idempotent). status_fn returns the telemetry dict."""
    global _started, _status_fn, _faces_dir
    if _started:
        return
    _started = True
    _status_fn = status_fn
    _faces_dir = faces_dir
    server = ThreadingHTTPServer(('0.0.0.0', PORT), _Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f'Live video feeds: http://{local_ip()}:{PORT}/  (MJPEG: /faces, /occupancy; JSON: /status)')
