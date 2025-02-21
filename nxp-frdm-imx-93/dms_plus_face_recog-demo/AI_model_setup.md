# Face Recognition + DMS on i.MX93

This project merges facial recognition and a Driver Monitoring System (DMS) into a single application. With facial recognition integrated into the DMS, you can implement rules for known drivers—for example, exempting trusted drivers from certain alerts or adjusting sensitivity based on historical data.

> **Note:** The original FaceNet model (~24MB) was too large for the i.MX93 NPU. We replaced it with a smaller, optimized MobileFaceNet model to ensure fast, efficient inference on the NPU.

## Repository Structure

```
nxp-frdm-imx-93/eiq-examples-git/
├── models/
│   ├── MobileFaceNet_INT8.tflite
│   ├── face_detection_front_128_full_integer_quant.tflite
│   ├── face_landmark_192_full_integer_quant.tflite
│   ├── iris_landmark_quant.tflite
│   └── ssd_mobilenet_v1_quant.tflite
├── merged_face_dms/
│   ├── merged-main.py
│   ├── face_detection.py
│   ├── face_recognition.py
│   └── face_database.py
└── README.md
```

## Merged Application File Changes

<details>
  <summary>Click to expand the details of changes in each file</summary>

- **merged-main.py:**  
  - Serves as the new entry point for the combined application.
  - Integrates both face recognition and DMS functionalities into a single processing loop.
  - Uses SSD-based face detection (or a DMS-specific detection model) to locate faces.
  - Invokes DMS models (for face and iris landmark extraction) to compute key metrics (e.g., mouth_ratio, eye ratios, yaw, pitch, roll).
  - Handles user input for adding or deleting driver identities and overlays detection results on the display.

- **face_detection.py:**  
  - Modified to support the merged workflow.
  - Adapted to work with the DMS face detection model (`face_detection_front_128_full_integer_quant.tflite`), ensuring proper scaling and bounding box extraction.
  - Includes additional pre- and post-processing logic needed to interface with the DMS modules.

- **face_recognition.py:**  
  - Updated to use the new `MobileFaceNet_INT8.tflite` model instead of the larger FaceNet model.
  - Contains logic to extract face embeddings from detected face regions.
  - Optimized for quantized inference on the i.MX93 NPU, ensuring faster and more efficient recognition.

- **face_database.py:**  
  - Provides storage and retrieval of driver identities.
  - Updated methods (e.g., `add_name` and `del_name`) to support the merged application.
  - Ensures that when a face is recognized, its embedding is compared against stored entries to retrieve the driver’s identity.

</details>

## Quick Setup Guide

### 1. Install Required Dependencies

On the i.MX93 device, run:
```bash
apt update
apt install -y wget unzip python3-opencv python3-numpy
pip install tflite-runtime
```
This installs OpenCV, NumPy, and the TensorFlow Lite runtime.

### 2. Download and Prepare Models

Ensure that you have placed the required five model files (listed below) in the `models/` folder of the repository:

1. **MobileFaceNet_INT8.tflite** – Face Recognition model  
2. **face_detection_front_128_full_integer_quant.tflite** – DMS Face Detection  
3. **face_landmark_192_full_integer_quant.tflite** – DMS Face Landmark Detection  
4. **iris_landmark_quant.tflite** – DMS Iris Landmark Detection  
5. **ssd_mobilenet_v1_quant.tflite** – SSD Face Detection model (used for general-purpose face detection)

### 3. Convert MobileFaceNet for i.MX93 NPU

The MobileFaceNet model must be converted to INT8 quantization for full NPU compatibility. If you wish to create your own INT8 MobileFaceNet model, run the following script on your PC (not on i.MX93):

<details>
  <summary>How to Convert MobileFaceNet to INT8</summary>

```python
import tensorflow as tf

# Load MobileFaceNet model (adjust the path if needed)
converter = tf.lite.TFLiteConverter.from_saved_model("MobileFaceNet.tflite")

# Enable INT8 quantization
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.target_spec.supported_types = [tf.int8]
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]

# Convert and save the quantized model
tflite_model = converter.convert()
with open("MobileFaceNet_INT8.tflite", "wb") as f:
    f.write(tflite_model)

print("Successfully converted MobileFaceNet to INT8 format!")
```

Transfer the converted model to the `models/` folder on your i.MX93 device:
```bash
scp MobileFaceNet_INT8.tflite root@imx93:/bin/eiq-examples-git/eiq-examples-git/models/
```
</details>

### 4. Modify the Application

Update your script (e.g., `merged-main.py`) to use the MobileFaceNet model and SSD-based face detection.

**For Face Recognition:**
```python
face_rec_interpreter = tflite.Interpreter(
    model_path="models/MobileFaceNet_INT8.tflite",
    experimental_delegates=[tflite.load_delegate('/usr/lib/libethosu_delegate.so')]
)
face_rec_interpreter.allocate_tensors()
```

**For Face Detection (using SSD):**
```python
# Using ssd_mobilenet_v1_quant.tflite for face detection.
# Adjust your detection pipeline to process outputs from this model.
ssd_detector = cv2.dnn.readNetFromTensorflow("models/ssd_mobilenet_v1_quant.tflite")
```
*Note: Adjust your detection pipeline to handle the SSD model outputs appropriately.*

### 5. Run the Final Application

Execute the merged script:
```bash
python3 merged-main.py
```
The NPU should now process MobileFaceNet efficiently, the SSD face detection will provide accurate results, and the DMS models will extract facial and iris landmarks for computing key metrics. This enables rule-based actions for known drivers.

## Model Overview and Metrics

Below is a table summarizing the five key models used in this demo, including their approximate file sizes (as observed from the file system) and key performance metrics derived from our conversion logs.

| **Demo**          | **Model Name**                                     | **Purpose / Classification**            | **Execution Target**           | **Approx. Size (MB)** | **Key Performance Metrics / Notes**                                                                                                                                                           |
|-------------------|----------------------------------------------------|-----------------------------------------|--------------------------------|-----------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Face Recognition  | MobileFaceNet_INT8.tflite                           | Face Recognition                        | ~100% NPU                      | ~1.5 MB               | Optimized for NPU; delivers fast inference with high throughput; converted successfully with INT8 quantization.                                                                                 |
| DMS               | face_detection_front_128_full_integer_quant.tflite | DMS Face Detection                      | ~96.6% NPU, ~3.4% CPU            | ~0.20 MB              | Batch Inference Time: ~1.51 ms; low memory usage (257.39 KiB SRAM, 514.06 KiB DRAM); tailored for detecting the driver’s face in a controlled environment.                                  |
| DMS               | face_landmark_192_full_integer_quant.tflite       | DMS Face Landmark Detection             | ~98.2% NPU, ~1.8% CPU            | ~0.76 MB              | Batch Inference Time: ~4.45 ms; critical for extracting facial landmarks for head pose and mouth analysis.                                                                    |
| DMS               | iris_landmark_quant.tflite                          | DMS Iris Landmark Detection             | ~99% NPU, ~1% CPU                | ~0.85 MB              | Batch Inference Time: ~3.07 ms; used for computing detailed eye metrics (left/right eye ratios).                                                                             |
| Face Detection    | ssd_mobilenet_v1_quant.tflite                       | SSD Face Detection                      | ~98.4% NPU, ~1.6% CPU            | ~5.0 MB (approx.)      | Batch Inference Time: ~7.76 ms; robust and accurate face detection with moderate memory usage; provides an alternative, general-purpose face detection option.                               |

> **Tip:** To further inspect or visualize these models (layer configurations, data types, etc.), use [Netron](https://netron.app/).

## Data Output and Interpretation

When the demo runs, it computes several key parameters from the detected face. Below is a table summarizing these parameters:

| **Parameter**      | **Description**                                                                                         | **Typical Range**             | **Interpretation**                                                                                         |
|--------------------|---------------------------------------------------------------------------------------------------------|-------------------------------|------------------------------------------------------------------------------------------------------------|
| **mouth_ratio**    | A ratio computed from facial landmarks indicating how open the mouth is.                               | ~0.0 – 0.5 (or higher)         | Higher values (e.g. > 0.3) may indicate that the mouth is open (possibly yawning).                         |
| **left_eye_ratio** | A ratio estimating the openness of the left eye based on eye landmarks.                                 | ~0.0 – 1.0                     | Values below ~0.2 may indicate a closed eye; higher values indicate open eyes.                             |
| **right_eye_ratio**| A ratio estimating the openness of the right eye based on eye landmarks.                                | ~0.0 – 1.0                     | Values below ~0.2 may indicate a closed eye; similar interpretation as the left eye ratio.                 |
| **yaw**            | The horizontal head rotation angle (turning left or right).                                           | Approximately -90° to +90°      | Positive yaw suggests the head is turned to the left; negative yaw suggests it’s turned right.             |
| **pitch**          | The vertical head rotation angle (nodding up or down).                                                 | Approximately -90° to +90°      | Positive pitch means the head is tilted upward; negative pitch indicates a downward tilt.                |
| **roll**           | The head tilt angle (rotation along the front-to-back axis).                                           | Approximately -45° to +45°      | Values near 0° are level; deviations indicate sideways tilt.                                             |

## Summary

**Problem:**  
- The original FaceNet model was too large (~24MB) for the i.MX93 NPU, causing slow inference and CPU fallback.

**Solution:**  
- Replaced FaceNet with a smaller MobileFaceNet model.
- Converted MobileFaceNet to INT8 for full NPU acceleration.
- Switched from older face detection methods to using SSD-based face detection (via ssd_mobilenet_v1_quant.tflite) for improved accuracy.
- Integrated DMS models (face and iris landmark detection) to compute facial metrics (mouth_ratio, eye_ratios, yaw, pitch, roll).
- Merged Face Recognition with DMS to enable rule-based actions for known drivers.

**Next Steps & Future Improvements:**  
- Test different input resolutions for optimal accuracy.
- Further optimize the DMS models for NPU acceleration.
- Consider custom training of MobileFaceNet for even better performance.

## Related Resources

- [NXP i.MX AI Documentation](https://www.nxp.com/design/development-boards/i.mx-ai-platforms)
- [MobileFaceNet GitHub](https://github.com/MCarlomagno/FaceRecognitionAuth)
- [Netron Model Viewer](https://netron.app/)
