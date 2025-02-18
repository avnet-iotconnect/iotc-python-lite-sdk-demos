#!/usr/bin/env python3
"""
Merged Face Recognition + DMS Application
(C) 2020-2023 NXP
SPDX-License-Identifier: Apache-2.0
"""
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2
import time
import math
import numpy as np
import argparse
import pathlib
import sys
import os

# System optimizations
os.environ["ETHOSU_CACHE"] = "0"
os.environ["MESA_LOADER_DRIVER_OVERRIDE"] = "llvmpipe"
os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
os.environ["QT_X11_NO_MITSHM"] = "1"

# ---------------------------------------------------------------------------
# Import modules for Face Recognition (from the merged folder)
# ---------------------------------------------------------------------------
from face_detection import YoloFace
from face_recognition import Facenet
from face_database import FaceDatabase

# ---------------------------------------------------------------------------
# Import modules for DMS processing (from the dms folder)
# ---------------------------------------------------------------------------
from dms.utils import nms_oneclass
from dms.face_detection import FaceDetector
from dms.face_landmark import FaceMesher
from dms.eye_landmark import EyeMesher
from dms.utils import (
    get_mouth_ratio,
    get_eye_ratio,
    get_iris_ratio,
    get_face_angle,
    get_eye_boxes,
    nms_oneclass
)

# =============================================================================
# Extended FaceDatabase class that stores embeddings along with optional DMS info
# =============================================================================
# (You can use your existing implementation from face_database.py if preferred.)

# =============================================================================
# Helper functions for on-screen text input and long text printing
# =============================================================================
def ischar(c):
    # Accept uppercase A-Z (65-90), lowercase a-z (97-122) and space (32)
    return (65 <= c <= 90) or (97 <= c <= 122) or c == 32

def get_inputs(img, msg):
    inputs = ""
    while True:
        cv2.rectangle(img, (0, 0), (img.shape[1], 40), (0, 0, 0), -1)
        cv2.putText(img, msg + inputs, (30, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, .67, (0, 255, 0), 2)
        cv2.imshow('Merged App', img)
        key = cv2.waitKey(20) & 0xFF
        # Enter key (ASCII 13 or 141)
        if key in [13, 141]:
            break
        # Backspace key (ASCII 8)
        if key == 8 and len(inputs) > 0:
            inputs = inputs[:-1]
        elif ischar(key):
            inputs += chr(key)
    return inputs

def print_longtext(img, text):
    textsize = cv2.getTextSize("A", cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0]
    raw_num = int((img.shape[1] - 60) / textsize[0])
    line_num = math.ceil(len(text) / raw_num)
    gap = textsize[1] + 10
    total_y = (int(textsize[1] / 2) + gap) * line_num + 15
    cv2.rectangle(img, (0, 0), (img.shape[1], total_y), (0, 0, 0), -1)
    for i in range(line_num):
        line = text[i * raw_num : (i + 1) * raw_num]
        y = int((30 + textsize[1]) / 2) + i * gap + 15
        cv2.putText(img, line, (30, y), cv2.FONT_HERSHEY_SIMPLEX,
                    1, (0, 255, 0), 2, lineType=cv2.LINE_AA)

# =============================================================================
# Parse command-line arguments
# =============================================================================
parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input', default='/dev/video0', help='Input device (or file)')
parser.add_argument('-d', '--delegate', default='', help='Delegate path')
args = parser.parse_args()

# =============================================================================
# Open video capture and initialize target dimensions (for DMS models)
# =============================================================================
if args.input.isdigit():
    cap_input = int(args.input)
else:
    cap_input = args.input
cap = cv2.VideoCapture(cap_input)
ret, init_frame = cap.read()
if not ret:
    print("❌ ERROR: Unable to capture initial frame from source", args.input)
    sys.exit(-1)
h, w, _ = init_frame.shape
target_dim = max(w, h)  # For padding in DMS processing

# =============================================================================
# Initialize models
# =============================================================================
# Recognition models (for face recognition & user management)
recognition_detector = YoloFace("models/yoloface_int8.tflite", args.delegate)
recognizer = Facenet("models/facenet_512_int_quantized.tflite", args.delegate)

# DMS models (for additional face analysis)
MODEL_PATH = pathlib.Path("../models/")
DETECT_MODEL = "face_detection_front_128_full_integer_quant.tflite"
LANDMARK_MODEL = "face_landmark_192_full_integer_quant.tflite"
EYE_MODEL = "iris_landmark_quant.tflite"
dms_detector = FaceDetector(model_path=str(MODEL_PATH / DETECT_MODEL),
                            delegate_path=args.delegate,
                            img_size=(target_dim, target_dim))
face_mesher = FaceMesher(model_path=str(MODEL_PATH / LANDMARK_MODEL),
                         delegate_path=args.delegate)
eye_mesher = EyeMesher(model_path=str(MODEL_PATH / EYE_MODEL),
                       delegate_path=args.delegate)

# Initialize the face database
database = FaceDatabase()

# =============================================================================
# Function to run DMS analysis on a given frame
# =============================================================================
def process_dms(frame):
    # Create a padded image (as used in the DMS application)
    padded_size = [ (target_dim - h) // 2, (target_dim - h + 1) // 2,
                    (target_dim - w) // 2, (target_dim - w + 1) // 2 ]
    padded = cv2.copyMakeBorder(frame.copy(),
                                padded_size[0], padded_size[1],
                                padded_size[2], padded_size[3],
                                cv2.BORDER_CONSTANT, value=[0, 0, 0])
    # Flip horizontally if needed (adjust based on your requirements)
    padded = cv2.flip(padded, 1)
    
    # Run DMS face detection/inference (expects: boxes, landmarks, scores)
    bboxes_decoded, landmarks, scores = dms_detector.inference(padded)
    dms_result = None
    for bbox, landmark, score in zip(bboxes_decoded, landmarks, scores):
        # Align the face and run landmark inference
        aligned_face, M, angle = dms_detector.align(padded, landmark)
        mesh_landmark, mesh_scores = face_mesher.inference(aligned_face)
        mesh_landmark_inverse = dms_detector.inverse(mesh_landmark, M)
        # Compute mouth ratio
        mouth_ratio = get_mouth_ratio(mesh_landmark_inverse, padded)
        # Get eye box coordinates
        left_box, right_box = get_eye_boxes(mesh_landmark_inverse, padded.shape)
        
        # Extract eye regions using explicit coordinate unpacking
        left_x1, left_y1 = left_box[0]
        left_x2, left_y2 = left_box[1]
        right_x1, right_y1 = right_box[0]
        right_x2, right_y2 = right_box[1]
        left_eye_img = padded[left_y1:left_y2, left_x1:left_x2]
        right_eye_img = padded[right_y1:right_y2, right_x1:right_x2]
        
        # Check if the extracted eye regions are non-empty
        if left_eye_img.size == 0 or right_eye_img.size == 0:
            # If empty, set default eye ratios (you can adjust these defaults as needed)
            left_eye_ratio = 0.0
            right_eye_ratio = 0.0
        else:
            left_eye_landmarks, _ = eye_mesher.inference(left_eye_img)
            right_eye_landmarks, _ = eye_mesher.inference(right_eye_img)
            left_eye_ratio = get_eye_ratio(left_eye_landmarks, padded, left_box[0])
            right_eye_ratio = get_eye_ratio(right_eye_landmarks, padded, right_box[0])
            
        # Decode head pose from the original detector
        r_vec, t_vec = dms_detector.decode_pose(landmark)
        yaw, pitch, roll = get_face_angle(r_vec, t_vec)
        
        dms_result = {
            "mouth_ratio": mouth_ratio,
            "left_eye_ratio": left_eye_ratio,
            "right_eye_ratio": right_eye_ratio,
            "head_pose": (yaw, pitch, roll)
        }
        # Process only the first detected face (adjust if needed)
        break
    return dms_result

# =============================================================================
# Main processing loop
# =============================================================================
tips = "Press 'a' to add person, 'd' to delete person, 'p' to print database, 'q' to quit"
PADDING = 10

while True:
    ret, frame = cap.read()
    if not ret:
        break
    img = frame.copy()

    # -------------------------
    # Face Recognition Section
    # -------------------------
    raw_boxes = recognition_detector.detect(img)
    if isinstance(raw_boxes, list):
        raw_boxes = np.array(raw_boxes)

    if raw_boxes.size > 0:
        # Check if raw_boxes has only 4 columns (no score)
        if raw_boxes.shape[1] == 4:
            bbox = raw_boxes  # all boxes
            score = np.ones((raw_boxes.shape[0],))  # assign a default score of 1
        else:
            bbox = raw_boxes[:, :4]
            score = raw_boxes[:, 4]
    
        keep_indices = nms_oneclass(bbox, score, thresh=0.4)
        boxes = raw_boxes[keep_indices]
    else:
        boxes = []

    # Initialize recognition_results before using it:
    recognition_results = []

    for box in boxes:
        # process each unique box
        # Convert normalized box coordinates to pixel values
        box[[0, 2]] *= img.shape[1]
        box[[1, 3]] *= img.shape[0]
        x1, y1, x2, y2 = box.astype(np.int32)
        # Add padding and ensure coordinates are within image bounds
        x1 = max(x1 - PADDING, 0)
        y1 = max(y1 - PADDING, 0)
        x2 = min(x2 + PADDING, img.shape[1])
        y2 = min(y2 + PADDING, img.shape[0])
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
        face_crop = img[y1:y2, x1:x2]
        embedding = recognizer.get_embeddings(face_crop)
        name = database.find_name(embedding)
        cv2.putText(img, name, (x1, y1 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        recognition_results.append((embedding, name, (x1, y1, x2, y2)))

    # -------------------------
    # DMS Analysis Section
    # -------------------------
    dms_info = process_dms(img)
    if dms_info:
        dms_text = (f"Mouth: {dms_info['mouth_ratio']:.2f} | "
                    f"LE: {dms_info['left_eye_ratio']:.2f} | "
                    f"RE: {dms_info['right_eye_ratio']:.2f} | "
                    f"Yaw: {dms_info['head_pose'][0]:.1f}")
        cv2.putText(img, dms_text, (30, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.53, (255, 0, 0), 2)

    # -------------------------
    # Overlay instructions
    # -------------------------
    cv2.putText(img, tips, (30, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.53, (0, 255, 255), 2)
    cv2.imshow('Merged App', img)

    # -------------------------
    # Key Input Processing
    # -------------------------
    key = cv2.waitKey(1) & 0xFF

    if key == ord('a'):
        msg = "ADD. Please input name:"
        name_input = get_inputs(img, msg)
        if recognition_results:
            embedding_to_add = recognition_results[0][0]
        else:
            embedding_to_add = None
        # Change this line to call add_name instead of add_user:
        database.add_name(name_input, embedding_to_add)
    elif key == ord('d'):
        msg = "DEL. Please input name:"
        name_input = get_inputs(img, msg)
        database.del_name(name_input)
    elif key == ord('p'):
        names = ",".join(database.get_names())
        print_longtext(img, names + "   Press any key to continue.")
        cv2.imshow('Merged App', img)
        # Wait until any key is pressed
        while cv2.waitKey(100) & 0xFF == 0xFF:
            pass
    elif key == ord('q'):
        break

# =============================================================================
# Cleanup
# =============================================================================
time.sleep(2)
cap.release()
cv2.destroyAllWindows()
