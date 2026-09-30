# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

"""Vision pipelines for the RZ/G3E vision demo.

Everything here runs on the Cortex-A55 cluster through OpenCV's DNN module —
no extra Python packages, no accelerator. Three OpenCV Zoo models are used:

  YuNet   (face detection)      cv2.FaceDetectorYN     ~230 KB
  SFace   (face recognition)    cv2.FaceRecognizerSF   ~37 MB
  NanoDet (person detection)    cv2.dnn.readNet        ~3.6 MB

Two pipelines run as daemon threads, each fed by a CameraSource:

  FacePipeline       who is in front of camera 1 — enrolled identities vs unknown
  OccupancyPipeline  how many people are in camera 2's zone, entries/exits, dwell

Both publish annotated frames to web_stream feeds and expose a results dict
that app.py folds into /IOTCONNECT telemetry.
"""

import json
import os
import subprocess
import threading
import time

import cv2
import numpy as np

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
FACES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'faces')

YUNET_MODEL = os.path.join(MODEL_DIR, 'face_detection_yunet_2023mar.onnx')
SFACE_MODEL = os.path.join(MODEL_DIR, 'face_recognition_sface_2021dec.onnx')
NANODET_MODEL = os.path.join(MODEL_DIR, 'object_detection_nanodet_2022nov.onnx')

CAM_WIDTH = 640
CAM_HEIGHT = 480
CAM_FPS = 15
MIRROR = True       # flip frames horizontally (selfie view); toggled by app.py from config/command


def missing_models() -> list:
    """Return the list of missing model files (empty when all are installed)."""
    return [os.path.basename(p) for p in (YUNET_MODEL, SFACE_MODEL, NANODET_MODEL)
            if not os.path.isfile(p)]


# ─── Camera source ────────────────────────────────────────────────────────────

class CameraSource:
    """Owns one V4L2 device and hands the latest frame to any number of readers.

    V4L2 devices cannot be opened by two processes (or two VideoCapture objects)
    at once, so both pipelines share a source when only one camera is attached.
    """

    def __init__(self, dev: str):
        self.dev = dev
        self._cond = threading.Condition()
        self._frame = None
        self._seq = 0
        self._stop = threading.Event()
        self.ok = False          # True once frames are flowing
        self.error = ''          # last open/read error for the status cards
        self._thread = threading.Thread(target=self._loop, name=f'cam:{dev}', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def get_frame(self, last_seq: int, timeout: float = 1.0):
        """Block until a frame newer than last_seq arrives. Returns (frame, seq) or (None, last_seq)."""
        with self._cond:
            self._cond.wait_for(lambda: self._seq != last_seq or self._stop.is_set(), timeout=timeout)
            if self._seq != last_seq and self._frame is not None:
                return self._frame, self._seq
            return None, last_seq

    @staticmethod
    def _constant_framerate(dev: str):
        # UVC auto-exposure otherwise stretches the frame interval in dim light
        # (down to 1-2 fps on a C920), which stalls both pipelines.
        try:
            subprocess.run(['v4l2-ctl', '-d', dev, '--set-ctrl=exposure_dynamic_framerate=0'],
                           capture_output=True, timeout=5)
        except Exception:
            pass

    def _loop(self):
        cap = None
        ctrl_set = False
        while not self._stop.is_set():
            if cap is None:
                cap = cv2.VideoCapture(self.dev, cv2.CAP_V4L2)
                if not cap.isOpened():
                    cap.release()
                    cap = None
                    self.ok = False
                    self.error = 'cannot open camera'
                    time.sleep(2.0)
                    continue
                # MJPG keeps two cameras well inside USB 2.0 bandwidth.
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_HEIGHT)
                cap.set(cv2.CAP_PROP_FPS, CAM_FPS)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
                ctrl_set = False
            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                cap = None
                self.ok = False
                self.error = 'camera read failed (unplugged?)'
                time.sleep(1.0)
                continue
            if not ctrl_set:
                self._constant_framerate(self.dev)
                ctrl_set = True
            if MIRROR:
                frame = cv2.flip(frame, 1)
            self.ok = True
            self.error = ''
            with self._cond:
                self._frame = frame
                self._seq += 1
                self._cond.notify_all()
        if cap is not None:
            cap.release()


# ─── Drawing helpers ──────────────────────────────────────────────────────────

def _header(frame, text: str, color=(255, 255, 255)):
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 26), (0, 0, 0), -1)
    cv2.putText(frame, text, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)


def _label(frame, x: int, y: int, text: str, color):
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
    y0 = max(y - th - 6, 0)
    cv2.rectangle(frame, (x, y0), (x + tw + 6, y0 + th + 6), color, -1)
    cv2.putText(frame, text, (x + 3, y0 + th + 1), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)


def status_card(label: str, detail: str = ''):
    img = np.full((CAM_HEIGHT, CAM_WIDTH, 3), 40, dtype=np.uint8)
    cv2.putText(img, label, (30, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2, cv2.LINE_AA)
    cv2.putText(img, detail, (30, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 180, 220), 1, cv2.LINE_AA)
    return img


def _iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    if inter <= 0:
        return 0.0
    return inter / ((ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter)


# ─── Base pipeline ────────────────────────────────────────────────────────────

class _Pipeline(threading.Thread):
    """Common thread scaffolding: enable/disable, camera hand-over, fps/latency stats."""

    idle_label = 'pipeline idle'

    def __init__(self, name: str, feed):
        super().__init__(name=name, daemon=True)
        self.feed = feed                 # web_stream feed to publish annotated frames to
        self.enabled = True
        self._source = None
        self._lock = threading.Lock()
        self._fps_t = time.time()
        self._fps_n = 0
        self.fps = 0.0
        self.infer_ms = 0.0
        self._last_card = 0.0

    def set_source(self, source):
        with self._lock:
            self._source = source

    @property
    def source(self):
        with self._lock:
            return self._source

    @property
    def active(self) -> bool:
        src = self.source
        return self.enabled and src is not None and src.ok

    def _tick_fps(self):
        self._fps_n += 1
        now = time.time()
        if now - self._fps_t >= 2.0:
            self.fps = round(self._fps_n / (now - self._fps_t), 1)
            self._fps_n = 0
            self._fps_t = now

    def _card(self, label: str, detail: str = ''):
        # Status cards are published at most once a second to keep the MJPEG light.
        if time.time() - self._last_card > 1.0:
            self.feed.publish(status_card(label, detail))
            self._last_card = time.time()
        time.sleep(0.2)

    def run(self):
        last_seq = -1
        while True:
            if not self.enabled:
                self.fps = 0.0
                self._card(self.idle_label, 'send set_mode to enable')
                continue
            src = self.source
            if src is None:
                self.fps = 0.0
                self._card(self.idle_label, 'no camera assigned - plug in a USB camera')
                continue
            if not src.ok:
                self.fps = 0.0
                self._card(self.idle_label, f'{src.dev}: {src.error or "starting camera..."}')
                continue
            frame, last_seq = src.get_frame(last_seq)
            if frame is None:
                continue
            try:
                self.process(frame)
            except Exception as e:  # never let one bad frame kill the pipeline
                print(f'[{self.name}] frame error: {e}')
                time.sleep(0.5)
            self._tick_fps()

    def process(self, frame):
        raise NotImplementedError


# ─── Face identity pipeline ───────────────────────────────────────────────────

class FacePipeline(_Pipeline):
    """YuNet detection + SFace recognition against an on-device gallery.

    Recognition is cached per face track (matched frame to frame by IoU) and
    refreshed once a second, so SFace only runs on new or stale faces and the
    detector sets the frame rate.
    """

    idle_label = 'Face identity pipeline stopped'
    DETECT_W, DETECT_H = 320, 240          # detector runs on a half-size frame
    MAX_FPS = 8.0                          # leave CPU for the person detector when both run
    RECOG_REFRESH_S = 1.0
    TRACK_TIMEOUT_S = 0.7
    ENROLL_SAMPLES = 5
    ENROLL_WINDOW_S = 4.0

    def __init__(self, feed, match_threshold: float = 0.363):
        super().__init__('faces', feed)
        self.match_threshold = match_threshold   # cosine similarity (OpenCV Zoo default 0.363)
        self.detector = cv2.FaceDetectorYN.create(
            YUNET_MODEL, '', (self.DETECT_W, self.DETECT_H),
            score_threshold=0.75, nms_threshold=0.3, top_k=50)
        self.recognizer = cv2.FaceRecognizerSF.create(SFACE_MODEL, '')
        self.gallery = {}          # name -> list of 128-d feature vectors
        self._gallery_lock = threading.Lock()
        self._tracks = []          # [{box, face, identity, score, recog_t, seen_t}]
        self._enroll = None        # {name, deadline, feats, crop, done: Event, result}
        self.unknown_seen = False  # sticky until telemetry consumes it
        self.known_seen = set()    # names seen since last telemetry read
        self.result = {'face_count': 0, 'known_count': 0, 'unknown_count': 0,
                       'identities': '', 'top_identity': '', 'top_confidence': 0.0}
        self.load_gallery()

    # ── gallery persistence ──
    def load_gallery(self):
        path = os.path.join(FACES_DIR, 'gallery.json')
        gallery = {}
        try:
            with open(path) as f:
                raw = json.load(f)
            for name, feats in raw.items():
                gallery[name] = [np.asarray(v, dtype=np.float32).reshape(1, -1) for v in feats]
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f'[faces] gallery load failed: {e}')
        with self._gallery_lock:
            self.gallery = gallery
        print(f'[faces] gallery: {len(gallery)} enrolled ({", ".join(gallery) or "none"})')

    def _save_gallery(self):
        os.makedirs(FACES_DIR, exist_ok=True)
        with self._gallery_lock:
            raw = {n: [v.flatten().tolist() for v in feats] for n, feats in self.gallery.items()}
        tmp = os.path.join(FACES_DIR, 'gallery.json.tmp')
        with open(tmp, 'w') as f:
            json.dump(raw, f)
        os.replace(tmp, os.path.join(FACES_DIR, 'gallery.json'))

    def enrolled_names(self) -> list:
        with self._gallery_lock:
            return sorted(self.gallery)

    def forget(self, name: str) -> bool:
        with self._gallery_lock:
            if name not in self.gallery:
                return False
            del self.gallery[name]
        self._save_gallery()
        try:
            os.remove(os.path.join(FACES_DIR, f'{name}.jpg'))
        except OSError:
            pass
        for t in self._tracks:
            if t['identity'] == name:
                t['identity'] = ''
        return True

    def enroll(self, name: str) -> tuple:
        """Capture several samples of the largest face and add them to the gallery.

        Blocks (up to ENROLL_WINDOW_S) so the command ack can report the outcome.
        """
        name = name.strip()
        if not name:
            return False, 'enroll needs a name'
        if not self.active:
            return False, 'face pipeline is not running (no camera / disabled)'
        if self._enroll is not None:
            return False, 'an enrollment is already in progress'
        req = {'name': name, 'deadline': time.time() + self.ENROLL_WINDOW_S,
               'feats': [], 'crop': None, 'done': threading.Event(), 'result': (False, 'timeout')}
        self._enroll = req
        req['done'].wait(self.ENROLL_WINDOW_S + 1.0)
        self._enroll = None
        return req['result']

    def _finish_enroll(self, req):
        if req['feats']:
            with self._gallery_lock:
                self.gallery.setdefault(req['name'], []).extend(req['feats'])
                n = len(self.gallery[req['name']])
            self._save_gallery()
            if req['crop'] is not None:
                os.makedirs(FACES_DIR, exist_ok=True)
                cv2.imwrite(os.path.join(FACES_DIR, f'{req["name"]}.jpg'), req['crop'])
            for t in self._tracks:      # re-identify immediately
                t['recog_t'] = 0.0
            req['result'] = (True, f'enrolled {req["name"]} ({len(req["feats"])} samples, {n} total)')
        else:
            req['result'] = (False, f'no face seen while enrolling {req["name"]}')
        req['done'].set()

    # ── recognition ──
    def _match(self, feat) -> tuple:
        """Return (name, cosine score) of the best gallery match, or ('', best)."""
        best_name, best = '', -1.0
        with self._gallery_lock:
            for name, feats in self.gallery.items():
                for g in feats:
                    s = float(self.recognizer.match(feat, g, cv2.FaceRecognizerSF_FR_COSINE))
                    if s > best:
                        best, best_name = s, name
        if best >= self.match_threshold:
            return best_name, best
        return '', best

    _last_frame_t = 0.0

    def process(self, frame):
        t0 = time.time()
        wait = self._last_frame_t + 1.0 / self.MAX_FPS - t0
        if wait > 0:
            time.sleep(wait)
            t0 = time.time()
        self._last_frame_t = t0
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (self.DETECT_W, self.DETECT_H), interpolation=cv2.INTER_AREA)
        sx, sy = w / self.DETECT_W, h / self.DETECT_H
        _, faces = self.detector.detect(small)
        faces = faces if faces is not None else np.zeros((0, 15), dtype=np.float32)
        # Scale the 14 geometry columns (box + 5 landmarks) back to full resolution
        # so alignCrop reads the sharp original, not the detector's downscale.
        if len(faces):
            faces = faces.copy()
            faces[:, 0:14:2] *= sx
            faces[:, 1:14:2] *= sy

        now = time.time()
        boxes = [(float(f[0]), float(f[1]), float(f[0] + f[2]), float(f[1] + f[3])) for f in faces]

        # Associate detections with existing tracks by IoU (greedy).
        new_tracks = []
        unused = list(range(len(self._tracks)))
        for i, box in enumerate(boxes):
            best_j, best_iou = -1, 0.3
            for j in unused:
                iou = _iou(box, self._tracks[j]['box'])
                if iou > best_iou:
                    best_j, best_iou = j, iou
            if best_j >= 0:
                t = self._tracks[best_j]
                unused.remove(best_j)
                t['box'] = box
            else:
                t = {'box': box, 'identity': '', 'score': 0.0, 'recog_t': 0.0}
            t['seen_t'] = now
            t['face'] = faces[i]
            new_tracks.append(t)
        # Keep briefly-lost tracks so a blink doesn't reset an identity.
        for j in unused:
            if now - self._tracks[j]['seen_t'] < self.TRACK_TIMEOUT_S:
                new_tracks.append(self._tracks[j])
        self._tracks = new_tracks

        # Recognise at most two stale faces per frame to bound latency.
        req = self._enroll
        budget = 2
        for t in sorted(self._tracks, key=lambda t: -(t['box'][2] - t['box'][0])):
            if t['seen_t'] != now or budget == 0:
                continue
            if req is None and now - t['recog_t'] < self.RECOG_REFRESH_S:
                continue
            aligned = self.recognizer.alignCrop(frame, t['face'])
            feat = self.recognizer.feature(aligned)
            budget -= 1
            if req is not None and len(req['feats']) < self.ENROLL_SAMPLES:
                # Enrollment uses the largest live face only (first in sorted order).
                req['feats'].append(feat.copy())
                if req['crop'] is None:
                    req['crop'] = aligned.copy()
                t['identity'], t['score'], t['recog_t'] = req['name'], 1.0, now
                if len(req['feats']) >= self.ENROLL_SAMPLES:
                    self._finish_enroll(req)
                req = None   # only one face per frame feeds the enrollment
                continue
            t['identity'], t['score'] = self._match(feat)
            t['recog_t'] = now
        if req is not None and now > req['deadline']:
            self._finish_enroll(req)

        self.infer_ms = round((time.time() - t0) * 1000.0, 1)

        # Results + annotation
        live = [t for t in self._tracks if t['seen_t'] == now]
        known = [t for t in live if t['identity']]
        unknown = [t for t in live if not t['identity']]
        if unknown and self._enroll is None:   # a face mid-enrolment is not an intruder
            self.unknown_seen = True
        for t in known:
            self.known_seen.add(t['identity'])
        top = max(known, key=lambda t: t['score']) if known else None
        names = sorted({t['identity'] for t in known})
        if unknown:
            names.append('unknown' if len(unknown) == 1 else f'unknown x{len(unknown)}')
        self.result = {
            'face_count': len(live),
            'known_count': len(known),
            'unknown_count': len(unknown),
            'identities': ', '.join(names),
            'top_identity': top['identity'] if top else '',
            'top_confidence': round(top['score'] * 100.0, 1) if top else 0.0,
        }

        out = frame.copy()
        enroll = self._enroll
        for t in live:
            x1, y1, x2, y2 = (int(v) for v in t['box'])
            if enroll is not None and t['identity'] == enroll['name']:
                color = (0, 220, 255)
                text = f'enrolling {t["identity"]} {len(enroll["feats"])}/{self.ENROLL_SAMPLES}'
            elif t['identity']:
                color, text = (80, 220, 80), f'{t["identity"]} {t["score"]:.2f}'
            else:
                color, text = (60, 60, 255), 'unknown'
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            _label(out, x1, y1, text, color)
        with self._gallery_lock:
            n_enrolled = len(self.gallery)
        _header(out, f'FACES  {len(live)} seen  {len(known)} known  {len(unknown)} unknown  |  '
                     f'{n_enrolled} enrolled  |  {self.infer_ms:.0f} ms  {self.fps:.1f} fps')
        self.feed.publish(out)

    def consume_events(self) -> tuple:
        """Return (unknown_seen, known_names) since the last call and reset them."""
        u, k = self.unknown_seen, sorted(self.known_seen)
        self.unknown_seen = False
        self.known_seen = set()
        return u, k


# ─── Occupancy pipeline ───────────────────────────────────────────────────────

class _NanoDet:
    """NanoDet-Plus-m 416 (COCO) through cv2.dnn — ported from OpenCV Zoo's nanodet.py."""

    STRIDES = (8, 16, 32, 64)
    SIZE = 416
    REG_MAX = 7

    def __init__(self, path: str):
        self.net = cv2.dnn.readNet(path)
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        self.project = np.arange(self.REG_MAX + 1, dtype=np.float32)
        self.mean = np.array([103.53, 116.28, 123.675], dtype=np.float32).reshape(1, 1, 3)
        self.std = np.array([57.375, 57.12, 58.395], dtype=np.float32).reshape(1, 1, 3)
        self.anchors = []
        for s in self.STRIDES:
            n = self.SIZE // s
            xv, yv = np.meshgrid(np.arange(n) * s, np.arange(n) * s)
            self.anchors.append(np.column_stack((xv.flatten() + 0.5 * (s - 1),
                                                 yv.flatten() + 0.5 * (s - 1))).astype(np.float32))

    def _letterbox(self, img):
        h, w = img.shape[:2]
        scale = self.SIZE / max(h, w)
        nh, nw = int(round(h * scale)), int(round(w * scale))
        resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
        top, left = (self.SIZE - nh) // 2, (self.SIZE - nw) // 2
        canvas = np.zeros((self.SIZE, self.SIZE, 3), dtype=np.uint8)
        canvas[top:top + nh, left:left + nw] = resized
        return canvas, scale, top, left

    def detect(self, frame_bgr, conf: float, class_id: int = 0, iou: float = 0.6):
        """Return [(x1, y1, x2, y2, score), ...] in frame coordinates for one class."""
        canvas, scale, top, left = self._letterbox(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        blob = cv2.dnn.blobFromImage(((canvas.astype(np.float32) - self.mean) / self.std))
        self.net.setInput(blob)
        outs = self.net.forward(self.net.getUnconnectedOutLayersNames())
        cls_scores, bbox_preds = outs[::2], outs[1::2]
        boxes, scores = [], []
        for stride, cs, bp, anchors in zip(self.STRIDES, cls_scores, bbox_preds, self.anchors):
            cs = cs.reshape(-1, cs.shape[-1])
            bp = bp.reshape(-1, 4 * (self.REG_MAX + 1))
            s = cs[:, class_id]
            keep = s > conf
            if not keep.any():
                continue
            cs_k, bp_k, an_k = s[keep], bp[keep], anchors[keep]
            x = np.exp(bp_k.reshape(-1, self.REG_MAX + 1))
            x /= x.sum(axis=1, keepdims=True)
            d = (x @ self.project).reshape(-1, 4) * stride
            x1 = np.clip(an_k[:, 0] - d[:, 0], 0, self.SIZE)
            y1 = np.clip(an_k[:, 1] - d[:, 1], 0, self.SIZE)
            x2 = np.clip(an_k[:, 0] + d[:, 2], 0, self.SIZE)
            y2 = np.clip(an_k[:, 1] + d[:, 3], 0, self.SIZE)
            boxes.append(np.column_stack([x1, y1, x2 - x1, y2 - y1]))
            scores.append(cs_k)
        if not boxes:
            return []
        boxes = np.concatenate(boxes)
        scores = np.concatenate(scores)
        idx = cv2.dnn.NMSBoxes(boxes.tolist(), scores.tolist(), conf, iou)
        dets = []
        for i in np.array(idx).flatten():
            x, y, w, h = boxes[i]
            dets.append(((x - left) / scale, (y - top) / scale,
                         (x + w - left) / scale, (y + h - top) / scale, float(scores[i])))
        return dets


class OccupancyPipeline(_Pipeline):
    """Person detection + centroid tracking against a configurable zone."""

    idle_label = 'Occupancy pipeline stopped'
    MAX_MISSED = 8              # detection cycles before a track is dropped
    MATCH_IOU = 0.25

    def __init__(self, feed, confidence: float = 0.4, zone=(0.3, 0.05, 0.7, 0.95)):
        super().__init__('occupancy', feed)
        self.confidence = confidence
        self.zone = tuple(zone)     # normalised (x1, y1, x2, y2)
        self.detector = _NanoDet(NANODET_MODEL)
        self._tracks = {}           # id -> {box, score, missed, first_seen, inside, entered_t}
        self._next_id = 1
        self.entries_total = 0
        self.exits_total = 0
        self.result = {'person_count': 0, 'zone_count': 0, 'dwell_max_s': 0.0, 'dwell_avg_s': 0.0}

    def reset_counts(self):
        self.entries_total = 0
        self.exits_total = 0

    def set_zone(self, zone) -> bool:
        x1, y1, x2, y2 = (float(v) for v in zone)
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            return False
        self.zone = (x1, y1, x2, y2)
        return True

    def _inside(self, box, w, h) -> bool:
        cx = (box[0] + box[2]) / 2 / w
        cy = (box[1] + box[3]) / 2 / h
        zx1, zy1, zx2, zy2 = self.zone
        return zx1 <= cx <= zx2 and zy1 <= cy <= zy2

    def process(self, frame):
        t0 = time.time()
        h, w = frame.shape[:2]
        dets = self.detector.detect(frame, self.confidence)
        self.infer_ms = round((time.time() - t0) * 1000.0, 1)
        now = time.time()

        # Greedy IoU association, largest detections first.
        dets = sorted(dets, key=lambda d: -((d[2] - d[0]) * (d[3] - d[1])))
        unmatched = set(self._tracks)
        assigned = {}
        for d in dets:
            box = d[:4]
            best, best_iou = None, self.MATCH_IOU
            for tid in unmatched:
                iou = _iou(box, self._tracks[tid]['box'])
                if iou > best_iou:
                    best, best_iou = tid, iou
            if best is None:
                best = self._next_id
                self._next_id += 1
                self._tracks[best] = {'box': box, 'score': d[4], 'missed': 0, 'first_seen': now,
                                      'inside': False, 'entered_t': 0.0}
            else:
                unmatched.discard(best)
            t = self._tracks[best]
            t['box'], t['missed'], t['score'] = box, 0, d[4]
            inside = self._inside(box, w, h)
            if inside and not t['inside']:
                self.entries_total += 1
                t['entered_t'] = now
            elif t['inside'] and not inside:
                self.exits_total += 1
            t['inside'] = inside
            assigned[best] = t
        for tid in unmatched:
            t = self._tracks[tid]
            t['missed'] += 1
            if t['missed'] > self.MAX_MISSED:
                if t['inside']:
                    self.exits_total += 1      # left the frame from inside the zone
                del self._tracks[tid]

        in_zone = [t for t in assigned.values() if t['inside']]
        dwell = [now - t['entered_t'] for t in in_zone]
        self.result = {
            'person_count': len(assigned),
            'zone_count': len(in_zone),
            'dwell_max_s': round(max(dwell), 1) if dwell else 0.0,
            'dwell_avg_s': round(sum(dwell) / len(dwell), 1) if dwell else 0.0,
        }

        out = frame.copy()
        zx1, zy1, zx2, zy2 = (int(self.zone[0] * w), int(self.zone[1] * h),
                              int(self.zone[2] * w), int(self.zone[3] * h))
        overlay = out.copy()
        cv2.rectangle(overlay, (zx1, zy1), (zx2, zy2), (255, 200, 0), -1)
        cv2.addWeighted(overlay, 0.12, out, 0.88, 0, out)
        cv2.rectangle(out, (zx1, zy1), (zx2, zy2), (255, 200, 0), 2)
        cv2.putText(out, 'ZONE', (zx1 + 6, zy2 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 200, 0), 1, cv2.LINE_AA)
        for tid, t in assigned.items():
            x1, y1, x2, y2 = (int(v) for v in t['box'])
            color = (80, 220, 80) if t['inside'] else (200, 200, 200)
            cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
            text = f'#{tid} {t["score"]:.2f}'
            if t['inside']:
                text += f'  {now - t["entered_t"]:.0f}s'
            _label(out, x1, y1, text, color)
        _header(out, f'OCCUPANCY  {len(assigned)} people  {len(in_zone)} in zone  |  '
                     f'in {self.entries_total}  out {self.exits_total}  |  '
                     f'{self.infer_ms:.0f} ms  {self.fps:.1f} fps')
        self.feed.publish(out)
