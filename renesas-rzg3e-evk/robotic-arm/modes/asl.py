"""ASL gesture-recognition mode.

Wraps the original MediaPipe + PointNet pipeline. Per-frame: detect hands,
classify the sign with PointNet, and dispatch a mapped arm action. Only one
action fires per distinct gesture (cooldown until the recognized sign changes).
"""

import os
import time

import cv2
import mediapipe as mp
import numpy as np
import torch

from .base import Mode

TELEMETRY_INTERVAL_S = 2.0

try:
    from point_net import PointNet
except ImportError:
    print("Warning: point_net module not found. Please ensure model/point_net.py exists and that the project root is on PYTHONPATH.")
    PointNet = None


CHAR2INT = {
    "A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6, "H": 7, "I": 8, "K": 9, "L": 10,
    "M": 11, "N": 12, "O": 13, "P": 14, "Q": 15, "R": 16, "S": 17, "T": 18, "U": 19,
    "V": 20, "W": 21, "X": 22, "Y": 23,
}
INT2CHAR = {v: k for k, v in CHAR2INT.items()}

LEFT_GESTURE_TO_ACTION = {
    'A': 'advance', 'B': 'backup', 'L': 'left', 'R': 'right',
    'U': 'up', 'Y': 'down', 'H': 'home',
}
RIGHT_GESTURE_TO_ACTION = {
    'A': 'close_gripper', 'B': 'open_gripper',
}

TEXT_FONT = cv2.FONT_HERSHEY_SIMPLEX
TEXT_SIZE = 0.75
TEXT_LINE = 2


class ASLMode(Mode):
    name = "asl"

    def __init__(self, model_dir="./model", model_name="point_net_1.pth"):
        self.model_dir = model_dir
        self.model_name = model_name
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = None
        self.hands = None
        self.last_gesture = None
        self.gesture_cooldown = 0
        self.last_telemetry_at = 0.0

    def get_state(self):
        return "ASL-Gesture"

    def setup(self, arm):
        if PointNet is None:
            raise RuntimeError("PointNet module not available; cannot run ASL mode.")
        path = os.path.join(self.model_dir, self.model_name)
        self.model = torch.load(path, weights_only=False, map_location=self.device)
        print(f"PointNet model loaded from {path}")
        mp_hands = mp.solutions.hands
        self.hands = mp_hands.Hands(min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self._mp_hands = mp_hands

    def teardown(self, arm):
        if self.hands is not None:
            self.hands.close()
            self.hands = None

    def process_frame(self, frame, arm):
        # Inject lazily to avoid a circular import at module load time.
        from main import execute_arm_action, send_telemetry, ACTION_LABELS

        cv2_image = cv2.flip(frame.copy(), 1)
        results = self.hands.process(cv2_image)
        h, w, _ = cv2_image.shape
        annotated = cv2_image.copy()
        current_gesture = None

        if results.multi_hand_landmarks:
            for hand_id, hand_landmarks in enumerate(results.multi_hand_landmarks):
                handedness = results.multi_handedness[hand_id].classification[0].label

                if handedness == "Left":
                    hand_x, hand_y, hand_color, hand_msg = 10, 30, (0, 255, 0), 'LEFT='
                else:
                    hand_x, hand_y, hand_color, hand_msg = w - 128, 30, (0, 0, 255), 'RIGHT='

                points_raw = np.array([[lm.x, lm.y, lm.z] for lm in hand_landmarks.landmark])
                points_norm = points_raw.copy()
                min_x, max_x = points_raw[:, 0].min(), points_raw[:, 0].max()
                min_y, max_y = points_raw[:, 1].min(), points_raw[:, 1].max()
                if max_x > min_x:
                    points_norm[:, 0] = (points_norm[:, 0] - min_x) / (max_x - min_x)
                if max_y > min_y:
                    points_norm[:, 1] = (points_norm[:, 1] - min_y) / (max_y - min_y)
                if handedness == "Right":
                    points_norm[:, 0] = 1.0 - points_norm[:, 0]

                for hc in self._mp_hands.HAND_CONNECTIONS:
                    cv2.line(
                        annotated,
                        (int(points_raw[hc[0]][0] * w), int(points_raw[hc[0]][1] * h)),
                        (int(points_raw[hc[1]][0] * w), int(points_raw[hc[1]][1] * h)),
                        hand_color, 2,
                    )

                try:
                    pointst = torch.tensor([points_norm]).float().to(self.device)
                    label = self.model(pointst).detach().cpu().numpy()
                    asl_id = int(np.argmax(label))
                    asl_sign = INT2CHAR[asl_id]
                    confidence = float(label[0][asl_id])

                    cv2.putText(annotated, hand_msg + asl_sign, (hand_x, hand_y),
                                TEXT_FONT, TEXT_SIZE, hand_color, TEXT_LINE, cv2.LINE_AA)

                    action_name = (LEFT_GESTURE_TO_ACTION if handedness == "Left"
                                   else RIGHT_GESTURE_TO_ACTION).get(asl_sign)
                    if action_name:
                        cv2.putText(annotated, '[' + ACTION_LABELS[action_name] + ']',
                                    (hand_x, hand_y * 2),
                                    TEXT_FONT, TEXT_SIZE, hand_color, TEXT_LINE, cv2.LINE_AA)

                    current_gesture = (handedness, asl_sign, confidence)
                except Exception as e:
                    print(f"[ERROR] ASL classification: {e}")

        if self.gesture_cooldown > 0:
            self.gesture_cooldown -= 1
        elif current_gesture is not None:
            sig = current_gesture[:2]
            if sig != self.last_gesture:
                self.last_gesture = sig
                self.gesture_cooldown = 1
                self._dispatch(arm, current_gesture[0], current_gesture[1],
                               execute_arm_action, send_telemetry, ACTION_LABELS)

        now = time.time()
        if now - self.last_telemetry_at >= TELEMETRY_INTERVAL_S:
            self.last_telemetry_at = now
            try:
                send_telemetry(arm)
            except Exception as e:
                print(f"[asl] telemetry failed: {e}")

        return annotated

    @staticmethod
    def _dispatch(arm, handedness, sign, execute_arm_action, send_telemetry, action_labels):
        if handedness == 'Left':
            action_name = LEFT_GESTURE_TO_ACTION.get(sign)
        elif handedness == 'Right':
            action_name = RIGHT_GESTURE_TO_ACTION.get(sign)
        else:
            print(f"Unknown handedness '{handedness}' for gesture '{sign}'")
            return
        if not action_name:
            return
        try:
            execute_arm_action(arm, action_name)
            print(f"Action: {action_labels[action_name]}")
            send_telemetry(arm)
        except Exception as e:
            print(f"Error controlling arm: {e}")
