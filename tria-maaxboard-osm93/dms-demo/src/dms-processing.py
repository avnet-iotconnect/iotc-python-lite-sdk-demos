
#!/usr/bin/env python3
#
# Copyright (c) 2020-2023 NXP
# Modifications Copyright (c) 2025 Avnet
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
#
# SPDX-License-Identifier: Apache-2.0
#
# -----------------------------------------------------------------------------
# PURPOSE:
#   This script performs face detection, landmark/eye/mouth detection,
#   then streams results over HTTPS via Flask (so it can be embedded in an
#   IoTConnect dashboard), and also displays them locally in an OpenCV window.
#
#   The four state values:
#       "head_direction"
#       "yawning"
#       "eyes_open"
#       "alert"
#
#   are updated if a candidate new value is confirmed over THRESHOLD consecutive frames.
#   This helps reduce noise in the detection.
#
#   Thresholds and forced states are controlled by reading from a local JSON
#   config file ("/opt/demo/dms-config.json"), which is updated by your
#   IoTConnect script. No Flask endpoints are used for setting thresholds/states;
#   we only use Flask for video streaming.
#
# -----------------------------------------------------------------------------

import pathlib
import sys
import time
import argparse
import json
import os
import cv2
import threading
import numpy as np
from flask import Flask, Response, request, jsonify
import fcntl
import collections  # For temporal smoothing

import logging
logging.getLogger('werkzeug').setLevel(logging.INFO)

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# -----------------------------------------------------------------------------
# ENVIRONMENT CONFIGS (FOR NXP BOARDS)
os.environ["ETHOSU_CACHE"] = "0"
os.environ["MESA_LOADER_DRIVER_OVERRIDE"] = "llvmpipe"
os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
os.environ["QT_X11_NO_MITSHM"] = "1"
os.environ["DISPLAY"] = ":0"
os.environ["XDG_RUNTIME_DIR"] = "/tmp/"
os.environ["QT_QPA_PLATFORM"] = "xcb"

# -----------------------------------------------------------------------------
# SSL CERTIFICATE FILES (for HTTPS streaming)
cert_file = os.path.join(os.path.dirname(__file__), 'cert.pem')
key_file = os.path.join(os.path.dirname(__file__), 'key.pem')

# -----------------------------------------------------------------------------
# TFLite-based modules (face detection, face/eye landmark, etc.)
from face_detection import FaceDetector
from eye_landmark import EyeMesher
from face_landmark import FaceMesher
from utils import get_face_angle, get_eye_ratio, get_iris_ratio

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS FOR DETECTION

def get_hw_ratio(landmarks, points):
    """
    Calculate a ratio based on given landmark points, avoiding division by zero.
    Usually used for measuring mouth height/width ratio (for yawning).
    """
    landmarks = landmarks.astype(int)
    mouth_h = cv2.norm(landmarks[points[0]] - landmarks[points[1]])
    mouth_w = cv2.norm(landmarks[points[2]] - landmarks[points[3]])
    if mouth_w == 0:
        return 0
    return mouth_h / mouth_w

def get_mouth_ratio(landmarks, image):
    """
    Calculates the mouth ratio to help detect yawning.
    We measure the distance between certain mouth landmarks vs mouth width.
    """
    if landmarks.shape[0] <= 308:
        return 0
    POINTS = (13, 14, 78, 308)
    return get_hw_ratio(landmarks, POINTS)

def get_eye_boxes_5point(landmarks, img_shape, eye_box_size=30):
    """
    Defines bounding boxes for the eyes, given 5-point face landmarks (0=left eye center, 1=right eye center).
    Ensures they don't exceed image boundaries.
    """
    left_eye_center = landmarks[0]
    right_eye_center = landmarks[1]
    left_box = (
        (int(max(left_eye_center[0] - eye_box_size/2, 0)),
         int(max(left_eye_center[1] - eye_box_size/2, 0))),
        (int(min(left_eye_center[0] + eye_box_size/2, img_shape[1]-1)),
         int(min(left_eye_center[1] + eye_box_size/2, img_shape[0]-1)))
    )
    right_box = (
        (int(max(right_eye_center[0] - eye_box_size/2, 0)),
         int(max(right_eye_center[1] - eye_box_size/2, 0))),
        (int(min(right_eye_center[0] + eye_box_size/2, img_shape[1]-1)),
         int(min(right_eye_center[1] + eye_box_size/2, img_shape[0]-1)))
    )
    return left_box, right_box

# -----------------------------------------------------------------------------
# SMOOTHING FOR EYE RATIOS

left_eye_history = collections.deque(maxlen=3)
right_eye_history = collections.deque(maxlen=3)

def compute_eye_ratio_by_lid_median(eye_landmarks):
    """
    Compute an eye ratio based on median y-values of the upper/lower lids,
    normalized by the eye's horizontal width. Smaller ratio => more closed.
    """
    pts = eye_landmarks[:, :2]
    if pts.shape[0] < 2:
        return 0
    sorted_pts = pts[np.argsort(pts[:, 1])]
    mid = len(sorted_pts) // 2
    upper = sorted_pts[:mid]
    lower = sorted_pts[mid:]
    median_upper = np.median(upper[:, 1])
    median_lower = np.median(lower[:, 1])
    vertical_distance = median_lower - median_upper
    horizontal_distance = np.max(pts[:, 0]) - np.min(pts[:, 0])
    if horizontal_distance == 0:
        return 0
    return vertical_distance / horizontal_distance

def smooth_value(new_value, history, reset_threshold=0.1):
    """
    Append new_value to the history (deque) and return the average.
    If new_value is far off from the current average, reset the history.
    Helps filter out noise in the detection.
    """
    if history:
        current_smoothed = sum(history) / len(history)
        if abs(new_value - current_smoothed) > reset_threshold:
            history.clear()
    history.append(new_value)
    return sum(history) / len(history)

# -----------------------------------------------------------------------------
# GLOBAL STATES FOR THRESHOLDS & DETECTION

# "stable_state" holds the last 'confirmed' values for each of the 4 states.
stable_state = {
    "head_direction": 5,
    "yawning": 0,
    "eyes_open": 2,
    "alert": 3
}
transition_counts = {
    "head_direction": 0,
    "yawning": 0,
    "eyes_open": 0,
    "alert": 0
}

# We set some default thresholds here, but they can be overridden by reading
# from /opt/demo/dms-config.json
THRESHOLD = 8            # # of consecutive frames needed to confirm a state transition
EYE_RATIO_THRESHOLD = 0.20

# We also support forced states, which override detection logic if not None.
forced_states = {
    "head_direction": None,
    "yawning": None,
    "eyes_open": None
}

# -----------------------------------------------------------------------------
# LOAD CONFIG FROM JSON
#   This is how we apply threshold changes and forced states from IoTConnect,
#   without using Flask for them. The IoTConnect script writes this file,
#   and we read it each loop.
# -----------------------------------------------------------------------------

CONFIG_PATH = "/opt/demo/dms-config.json"

def load_config_from_json():
    global THRESHOLD, EYE_RATIO_THRESHOLD
    global forced_states

    if not os.path.exists(CONFIG_PATH):
        return  # If no config file yet, just skip

    try:
        with open(CONFIG_PATH, "r") as f:
            config_data = json.load(f)
    except Exception as e:
        print(f"Warning: could not read config {CONFIG_PATH}: {e}")
        return

    if "transition_threshold" in config_data:
        THRESHOLD = int(config_data["transition_threshold"])
    if "eye_ratio_threshold" in config_data:
        EYE_RATIO_THRESHOLD = float(config_data["eye_ratio_threshold"])

    if "forced_states" in config_data:
        for k in ["head_direction", "yawning", "eyes_open"]:
            forced_states[k] = config_data["forced_states"].get(k, None)

# -----------------------------------------------------------------------------
# JSON UTILS FOR DMS-DATA

JSON_PATH = "/opt/demo/dms-data.json"

def safe_read_json(path):
    with open(path, "r") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        data = json.load(f)
        fcntl.flock(f, fcntl.LOCK_UN)
    return data

def safe_write_json(path, data):
    with open(path, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(data, f)
        fcntl.flock(f, fcntl.LOCK_UN)

def ensure_json_file_valid(json_path):
    """
    Ensures /opt/demo/dms-data.json exists and has valid JSON structure.
    If missing or invalid, create a default.
    """
    if not os.path.exists(json_path) or os.path.getsize(json_path) == 0:
        #print(f"{json_path} is missing or empty. Creating a default JSON.")
        default_data = {
            "head_direction": 5,
            "yawning": 0,
            "eyes_open": 2,
            "alert": 3,
            "bbox_xmin": 0,
            "bbox_ymin": 0,
            "bbox_xmax": 0,
            "bbox_ymax": 0
        }
        with open(json_path, "w") as f:
            json.dump(default_data, f)
    else:
        try:
            with open(json_path, "r") as f:
                json.load(f)
        except json.JSONDecodeError:
            #print(f"{json_path} has invalid JSON. Overwriting with defaults.")
            default_data = {
                "head_direction": 5,
                "yawning": 0,
                "eyes_open": 2,
                "alert": 3,
                "bbox_xmin": 0,
                "bbox_ymin": 0,
                "bbox_xmax": 0,
                "bbox_ymax": 0
            }
            with open(json_path, "w") as f:
                json.dump(default_data, f)

ensure_json_file_valid(JSON_PATH)

# -----------------------------------------------------------------------------
# GLOBAL DETECTION VARIABLES
yawning, eyes_open, head_direction, alert = 0, 2, 5, 3
bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax = 0, 0, 0, 0

pitch = 0
roll = 0
yaw_val = 0
mouth_ratio_val = 0
left_eye_ratio_smoothed = None
right_eye_ratio_smoothed = None
left_eye_landmarks = None
right_eye_landmarks = None

# -----------------------------------------------------------------------------
# UPDATE JSON: writes the current detection states + extra fields to /opt/demo/dms-data.json
# -----------------------------------------------------------------------------

def update_json():
    global yawning, eyes_open, head_direction, alert
    global bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax
    global pitch, roll, yaw_val, mouth_ratio_val
    global left_eye_ratio_smoothed, right_eye_ratio_smoothed
    global left_eye_landmarks, right_eye_landmarks

    try:
        dms_data = safe_read_json(JSON_PATH)
    except (json.JSONDecodeError, FileNotFoundError):
        dms_data = {
            "head_direction": 5,
            "yawning": 0,
            "eyes_open": 2,
            "alert": 3,
            "bbox_xmin": 0,
            "bbox_ymin": 0,
            "bbox_xmax": 0,
            "bbox_ymax": 0
        }

    dms_data["head_direction"] = int(head_direction)
    dms_data["yawning"] = int(yawning)
    dms_data["eyes_open"] = int(eyes_open)
    dms_data["alert"] = int(alert)
    dms_data["bbox_xmin"] = int(bbox_xmin)
    dms_data["bbox_ymin"] = int(bbox_ymin)
    dms_data["bbox_xmax"] = int(bbox_xmax)
    dms_data["bbox_ymax"] = int(bbox_ymax)

    # Additional fields for debugging or telemetry
    dms_data["pitch"] = pitch
    dms_data["roll"] = roll
    dms_data["yaw_val"] = yaw_val
    dms_data["mouth_ratio"] = mouth_ratio_val
    dms_data["left_eye_ratio_smoothed"] = left_eye_ratio_smoothed
    dms_data["right_eye_ratio_smoothed"] = right_eye_ratio_smoothed

    if left_eye_landmarks is not None:
        dms_data["left_eye_landmarks"] = left_eye_landmarks.tolist()
    else:
        dms_data["left_eye_landmarks"] = None
    if right_eye_landmarks is not None:
        dms_data["right_eye_landmarks"] = right_eye_landmarks.tolist()
    else:
        dms_data["right_eye_landmarks"] = None

    safe_write_json(JSON_PATH, dms_data)

# -----------------------------------------------------------------------------
# MODEL LOADING & FLASK SETUP

def safe_read(cap, retries=10, delay=0.1):
    """Try reading from the camera several times before failing."""
    for _ in range(retries):
        ret, frame = cap.read()
        if ret and frame is not None:
            return frame
        time.sleep(delay)
    raise RuntimeError("Camera did not return a frame")


app = Flask(__name__)
MODEL_PATH = pathlib.Path("/usr/bin/eiq-examples-git/models/")
DETECT_MODEL = "face_detection_front_128_full_integer_quant.tflite"
FACE_LANDMARK_MODEL = "face_landmark_192_full_integer_quant.tflite"
EYE_LANDMARK_MODEL = "iris_landmark_quant.tflite"

log_dir = "/opt/demo/log"
stream_mode = "live"  # 'live', 'off', or 'freeze'
frozen_snapshot = None

os.makedirs(log_dir, exist_ok=True)

# PARSE ARGS
parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input', default='/dev/video0', help='camera/video input')
parser.add_argument('-d', '--delegate', default='', help='delegate path')
args = parser.parse_args()

cap = cv2.VideoCapture(args.input, cv2.CAP_V4L2)
frame = safe_read(cap, retries=20, delay=0.2)

h, w, _ = frame.shape
target_dim = max(w, h)

# Load TFLite models
face_detector = FaceDetector(
    model_path=str(MODEL_PATH / DETECT_MODEL),
    delegate_path=args.delegate,
    img_size=(target_dim, target_dim)
)
face_mesher = FaceMesher(
    model_path=str(MODEL_PATH / FACE_LANDMARK_MODEL),
    delegate_path=args.delegate
)
eye_mesher = EyeMesher(
    model_path=str(MODEL_PATH / EYE_LANDMARK_MODEL),
    delegate_path=args.delegate
)

# THREADING LOCKS
latest_frame = None
frame_lock = threading.Lock()
latest_snapshot = None
snapshot_lock = threading.Lock()
model_lock = threading.Lock()

# -----------------------------------------------------------------------------
# DRAW_FACE_BOX (for visualization)

def draw_face_box(image, bboxes, landmarks, scores):
    global bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax
    min_confidence = 0.93
    for bbox, landmark, score in zip(bboxes.astype(int), landmarks.astype(int), scores):
        if score < min_confidence:
            continue
        cv2.rectangle(image, tuple(bbox[:2]), tuple(bbox[2:]), (255, 0, 0), 2)
        landmark = landmark.reshape(-1, 2)
        bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax = bbox[0], bbox[1], bbox[2], bbox[3]
        score_label = f"Conf: {score:.2f}"
        (label_width, label_height), baseline = cv2.getTextSize(score_label,
                                                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
        label_btmleft = bbox[:2].copy() + 10
        label_btmleft[0] += label_width
        label_btmleft[1] += label_height
        cv2.rectangle(image, tuple(bbox[:2]), tuple(label_btmleft),
                      (255, 0, 0), thickness=cv2.FILLED)
        cv2.putText(image, score_label, (bbox[0] + 5, label_btmleft[1] - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        break  # Only process first face
    return image

# -----------------------------------------------------------------------------
# MAIN DETECTION LOGIC PER FRAME

def main(image):
    global yawning, eyes_open, head_direction, alert
    global bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax
    global pitch, roll, yaw_val
    global mouth_ratio_val
    global left_eye_ratio_smoothed, right_eye_ratio_smoothed
    global left_eye_landmarks, right_eye_landmarks

    # 1) Load config each loop to see if IoTConnect changed thresholds/forced states
    load_config_from_json()

    with model_lock:
        # Pad input to square
        padded_size = [
            (target_dim - h) // 2,
            (target_dim - h + 1) // 2,
            (target_dim - w) // 2,
            (target_dim - w + 1) // 2
        ]
        padded = cv2.copyMakeBorder(image.copy(), *padded_size,
                                    cv2.BORDER_CONSTANT, value=[0, 0, 0])
        padded = cv2.flip(padded, 1)

        bboxes_decoded, landmarks, scores = face_detector.inference(padded)
        image_show = padded.copy()

        # No face detected: Set alert to "no face" state and return early
        if bboxes_decoded is None or bboxes_decoded.size == 0:
            alert = 3
            head_direction = 5
            eyes_open = 2
            bbox_xmin, bbox_ymin, bbox_xmax, bbox_ymax = 0, 0, 0, 0
            update_json()  # Ensure no-face state is saved
            #print("No face detected: alert=3, head_direction=5, eyes_open=2")
            return image_show  # Exit early since no face is present

        # If a face is detected, continue processing
        image_show = draw_face_box(image_show, bboxes_decoded, landmarks, scores)

        face_found = False
        if (bbox_xmin != 0 or bbox_ymin != 0 or bbox_xmax != 0 or bbox_ymax != 0):
            face_found = True
            for bbox, landmark in zip(bboxes_decoded, landmarks):
                aligned_face, M, angle = face_detector.align(padded, landmark)
                mesh_landmark, mesh_scores = face_mesher.inference(aligned_face)
                mesh_landmark_inverse = face_detector.inverse(mesh_landmark, M)
                landmarks_2d = mesh_landmark_inverse[:, :2]

                left_box, right_box = get_eye_boxes_5point(landmarks_2d, padded.shape, 30)

                lw = left_box[1][0] - left_box[0][0]
                lh = left_box[1][1] - left_box[0][1]
                if lw > 10 and lh > 10:
                    left_eye_img = padded[left_box[0][1]:left_box[1][1],
                                          left_box[0][0]:left_box[1][0]]
                else:
                    left_eye_img = None

                rw = right_box[1][0] - right_box[0][0]
                rh = right_box[1][1] - right_box[0][1]
                if rw > 10 and rh > 10:
                    right_eye_img = padded[right_box[0][1]:right_box[1][1],
                                           right_box[0][0]:right_box[1][0]]
                else:
                    right_eye_img = None

                r_vec, t_vec = face_detector.decode_pose(landmark)
                pitch, roll, yaw_val = get_face_angle(r_vec, t_vec)

                # Eye detection
                if isinstance(left_eye_img, np.ndarray) and left_eye_img.size != 0:
                    left_eye_landmarks, left_iris_landmarks = eye_mesher.inference(left_eye_img)
                    left_eye_ratio = compute_eye_ratio_by_lid_median(left_eye_landmarks)
                    left_eye_ratio_smoothed = smooth_value(left_eye_ratio, left_eye_history)
                else:
                    left_eye_landmarks, left_iris_landmarks = None, None
                    left_eye_ratio_smoothed = None

                if isinstance(right_eye_img, np.ndarray) and right_eye_img.size != 0:
                    right_eye_landmarks, right_iris_landmarks = eye_mesher.inference(right_eye_img)
                    right_eye_ratio = compute_eye_ratio_by_lid_median(right_eye_landmarks)
                    right_eye_ratio_smoothed = smooth_value(right_eye_ratio, right_eye_history)
                else:
                    right_eye_landmarks, right_iris_landmarks = None, None
                    right_eye_ratio_smoothed = None

                # If yaw is large left, assume right eye not visible:
                if yaw_val > 45:
                    left_eye_ratio_smoothed = None
                # If yaw is large right, assume left eye not visible:
                if yaw_val < 9:
                    right_eye_ratio_smoothed = None

                # Determine eyes_open from combined ratio
                combined_ratio = 0
                if left_eye_ratio_smoothed and right_eye_ratio_smoothed:
                    combined_ratio = min(left_eye_ratio_smoothed, right_eye_ratio_smoothed)
                elif left_eye_ratio_smoothed:
                    combined_ratio = left_eye_ratio_smoothed
                elif right_eye_ratio_smoothed:
                    combined_ratio = right_eye_ratio_smoothed

                if combined_ratio > EYE_RATIO_THRESHOLD:
                    eyes_open = 1
                    cv2.putText(image_show, "Eyes: Open", (50, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                else:
                    eyes_open = 0
                    cv2.putText(image_show, "Eyes: Closed", (50, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

                # Yawning
                mouth_ratio_val = get_mouth_ratio(mesh_landmark_inverse, image_show)
                if mouth_ratio_val > 0.3:
                    yawning = 1
                    cv2.putText(image_show, "Yawning: Yes", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                else:
                    yawning = 0
                    cv2.putText(image_show, "Yawning: No", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

                # Head direction
                if yaw_val > 35:
                    head_direction = 3
                    cv2.putText(image_show, "Face: Left", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                elif yaw_val < -35:
                    head_direction = 4
                    cv2.putText(image_show, "Face: Right", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                elif pitch > 30:
                    head_direction = 1
                    cv2.putText(image_show, "Face: Up", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                elif pitch < -20:
                    head_direction = 2
                    cv2.putText(image_show, "Face: Down", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                else:
                    head_direction = 0
                    cv2.putText(image_show, "Face: Forward", (50, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

                # Alert: 0=normal, 1= inattentive, 2= drowsy
                if head_direction == 0 and yawning == 0 and eyes_open == 1:
                    alert = 0
                elif head_direction != 0:
                    alert = 1
                elif yawning == 1:
                    alert = 2
                break

        # Override with forced states if any
        if forced_states["head_direction"] is not None:
            head_direction = forced_states["head_direction"]
        if forced_states["yawning"] is not None:
            yawning = forced_states["yawning"]
        if forced_states["eyes_open"] is not None:
            eyes_open = forced_states["eyes_open"]

        # Transition logic
        new_state = {
            "head_direction": head_direction,
            "yawning": yawning,
            "eyes_open": eyes_open,
            "alert": alert
        }
        transition_occurred = False
        for key in new_state:
            if new_state[key] != stable_state[key]:
                transition_counts[key] += 1
                if transition_counts[key] >= THRESHOLD:
                    old_val = stable_state[key]
                    stable_state[key] = new_state[key]
                    transition_counts[key] = 0
                    transition_occurred = True
                    #print(f"STATE CHANGE: '{key}' from {old_val} to {new_state[key]} "
                    #f"(pitch={pitch:.2f}, yaw={yaw_val:.2f}, mouth={mouth_ratio_val:.2f})")
            else:
                transition_counts[key] = 0

        # remove padding
        image_show = image_show[padded_size[0]:target_dim - padded_size[1],
                                padded_size[2]:target_dim - padded_size[3]]
        update_json()
        return image_show

# -----------------------------------------------------------------------------
# FLASK ROUTES: NO /set_thresholds or /set_conditions ANYMORE
# Only for streaming and snapshots
# -----------------------------------------------------------------------------

@app.route('/set_mode', methods=['POST'])
def set_mode():
    global stream_mode
    data = request.get_json(force=True)
    new_mode = data.get("mode", "")
    if new_mode == "live":
        stream_mode = "live"
        return jsonify({"status": "OK", "message": "Stream mode set to LIVE"}), 200
    elif new_mode == "off":
        stream_mode = "off"
        return jsonify({"status": "OK", "message": "Stream mode set to OFF"}), 200
    elif new_mode == "snapshot":
        filepath = save_snapshot()
        if filepath:
            freeze_current_snapshot()
            def unfreeze_after_delay():
                global stream_mode
                time.sleep(5)
                stream_mode = "live"
                print("Snapshot freeze ended; back to LIVE mode.")
            threading.Thread(target=unfreeze_after_delay, daemon=True).start()
            return jsonify({"status": "OK", "message": f"Snapshot saved and freezing for 5s: {filepath}"}), 200
        else:
            return jsonify({"status": "ERROR", "message": "No snapshot available"}), 400
    else:
        return jsonify({"status": "ERROR", "message": f"Unknown mode: {new_mode}"}), 400

def freeze_current_snapshot():
    global stream_mode, frozen_snapshot, latest_snapshot
    with snapshot_lock:
        if latest_snapshot is not None:
            frozen_snapshot = latest_snapshot[:]
            stream_mode = "freeze"
            print("Stream set to FREEZE mode.")
        else:
            print("No snapshot to freeze.")

@app.route('/snapshot')
def snapshot():
    with snapshot_lock:
        img = latest_snapshot
    if img is None:
        placeholder = np.zeros((target_dim, target_dim, 3), dtype=np.uint8)
        smaller_frame = cv2.resize(placeholder, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), 50]
        ret, buffer = cv2.imencode('.jpg', smaller_frame, encode_params)
        if ret:
            img = buffer.tobytes()
        else:
            return "No snapshot available", 404
    response = Response(img, mimetype='image/jpeg')
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route('/live')
def live():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Live Feed with Refresh Button</title>
      <style>
        body { margin: 0; background-color: #000; padding-top: 20vh; text-align: center; color: #fff; }
        img { width: 100%; height: auto; display: block; margin: 0 auto; }
        button { padding: 10px 20px; font-size: 1em; margin-top: 20px; cursor: pointer; }
      </style>
    </head>
    <body>
       <img src="/mjpeg" alt="Live Feed">
       <button onclick="location.reload()">Refresh</button>
    </body>
    </html>
    '''

@app.route('/snapshot_page')
def snapshot_page():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Snapshot Page</title>
      <style>
        body { margin: 0; background-color: #000; padding-top: 20vh; }
        img { width: 100%; height: auto; display: block; }
      </style>
      <script type="text/javascript">
        function refreshImage(){
          var img = document.getElementById("liveImage");
          img.src = "/snapshot?" + new Date().getTime();
        }
        setInterval(refreshImage, 10000);
        window.onload = refreshImage;
      </script>
    </head>
    <body>
      <img id="liveImage" src="/snapshot" alt="Snapshot">
    </body>
    </html>
    '''

@app.route('/mjpeg')
def mjpeg():
    def generate():
        while True:
            if stream_mode == "off":
                black_frame = np.zeros((240, 320, 3), dtype=np.uint8)
                ret, buffer = cv2.imencode('.jpg', black_frame)
                if ret:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                time.sleep(1.0)
                continue
            elif stream_mode == "freeze":
                with snapshot_lock:
                    if frozen_snapshot is not None:
                        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frozen_snapshot + b'\r\n')
                time.sleep(1.0)
                continue
            else:
                with snapshot_lock:
                    img = latest_snapshot
                if img is not None:
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + img + b'\r\n')
                time.sleep(0.2)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

def save_snapshot():
    global latest_snapshot, alert
    with snapshot_lock:
        snap_data = latest_snapshot
    if snap_data is None:
        print("No snapshot available to save!")
        return None
    np_data = np.frombuffer(snap_data, dtype=np.uint8)
    frame_bgr = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
    if frame_bgr is None:
        print("Error: Could not decode snapshot data.")
        return None
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"dms-log-alert{alert}-{timestamp}.jpg"
    filepath = os.path.join(log_dir, filename)
    cv2.imwrite(filepath, frame_bgr)
    print(f"Saved snapshot to: {filepath}")
    return filepath

# -----------------------------------------------------------------------------
# CAPTURE THREAD & SNAPSHOT THREAD
# -----------------------------------------------------------------------------

def capture_frames():
    global latest_frame
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        with frame_lock:
            latest_frame = frame.copy()
        time.sleep(0.1)

def snapshot_worker():
    global latest_snapshot
    while True:
        with frame_lock:
            frame = latest_frame.copy() if latest_frame is not None else None
        if frame is not None:
            image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            processed = main(image_rgb)
            processed_bgr = cv2.cvtColor(processed, cv2.COLOR_RGB2BGR)
            ret, buffer = cv2.imencode('.jpg', processed_bgr)
            if ret:
                with snapshot_lock:
                    latest_snapshot = buffer.tobytes()
        time.sleep(0.1)

capture_thread = threading.Thread(target=capture_frames, daemon=True)
capture_thread.start()
snapshot_thread = threading.Thread(target=snapshot_worker, daemon=True)
snapshot_thread.start()

# -----------------------------------------------------------------------------
# RUN FLASK SERVER ON HTTPS
# -----------------------------------------------------------------------------

def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False, ssl_context=(cert_file, key_file))

flask_thread = threading.Thread(target=run_flask, daemon=True)
flask_thread.start()

# -----------------------------------------------------------------------------
# LOCAL DISPLAY LOOP
# -----------------------------------------------------------------------------

iteration = 0
while True:
    with frame_lock:
        frame = latest_frame.copy() if latest_frame is not None else None
    if frame is None:
        continue
    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    processed = main(image_rgb)
    result = cv2.cvtColor(processed, cv2.COLOR_RGB2BGR)
    cv2.imshow('Local Display', result)
    iteration += 1
    if cv2.waitKey(30) & 0xFF == ord('q'):
        break

time.sleep(2)
cap.release()
cv2.destroyAllWindows()
