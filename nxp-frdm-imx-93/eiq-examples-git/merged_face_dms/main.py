import cv2
import numpy as np
import tflite_runtime.interpreter as tflite
import os

# System optimizations
os.environ["ETHOSU_CACHE"] = "0"
os.environ["MESA_LOADER_DRIVER_OVERRIDE"] = "llvmpipe"
os.environ["LIBGL_ALWAYS_SOFTWARE"] = "1"
os.environ["QT_X11_NO_MITSHM"] = "1"

import time

start_time = time.time()
print("⏳ Initializing Ethosu Delegate...")

ethosu_delegate = tflite.load_delegate('/usr/lib/libethosu_delegate.so', options={"enable_profiling": 0, "timeout": 100000000})

print(f"✅ Ethosu Delegate Initialized in {time.time() - start_time:.2f} sec")

start_time = time.time()
print("⏳ Loading Face Recognition Model...")
face_rec_interpreter = tflite.Interpreter(model_path="models/facenet_512_int_quantized.tflite", experimental_delegates=[ethosu_delegate])
face_rec_interpreter.allocate_tensors()
print(f"✅ Face Rec model loaded in {time.time() - start_time:.2f} sec")

start_time = time.time()
print("⏳ Loading DMS Model...")
dms_landmark_interpreter = tflite.Interpreter(model_path="models/face_landmark_192_full_integer_quant.tflite", experimental_delegates=[ethosu_delegate])
dms_landmark_interpreter.allocate_tensors()
print(f"✅ DMS model loaded in {time.time() - start_time:.2f} sec")

start_time = time.time()
print("⏳ Initializing Camera...")
cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 30)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
print(f"✅ Camera initialized in {time.time() - start_time:.2f} sec")

# Face Detection Model (SSD)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

# Preprocessing function
def preprocess_image(image, target_size, dtype="uint8"):
    image = cv2.resize(image, target_size)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = np.expand_dims(image, axis=0)

    return image.astype(np.float32) / 255.0 if dtype == "float32" else image.astype(np.uint8)

# Start frame capture loop
frame_count = 0
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        print("❌ ERROR: Failed to read frame from camera.")
        break

    start_time = time.time()
    print("✅ Frame captured. Processing...")

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

    print(f"📸 Detected {len(faces)} faces")

    for (x, y, w, h) in faces:
        face_roi = frame[y:y+h, x:x+w]
        face_input = preprocess_image(face_roi, (160, 160), dtype="float32")
        face_rec_interpreter.set_tensor(face_rec_interpreter.get_input_details()[0]['index'], face_input)
        face_rec_interpreter.invoke()
        person_name = "Recognized" if np.max(face_rec_interpreter.get_tensor(face_rec_interpreter.get_output_details()[0]['index'])) > 0.8 else "Unknown"

        dms_input_data = preprocess_image(face_roi, (192, 192), dtype="float32")
        dms_landmark_interpreter.set_tensor(dms_landmark_interpreter.get_input_details()[0]['index'], dms_input_data)
        dms_landmark_interpreter.invoke()
        attention_status = "Attentive"

        cv2.putText(frame, f"{person_name}, {attention_status}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    if frame_count % 3 == 0:
        cv2.imshow("Face Recognition + DMS", frame)
    frame_count += 1
    cv2.waitKey(1)

cap.release()
cv2.destroyAllWindows()

