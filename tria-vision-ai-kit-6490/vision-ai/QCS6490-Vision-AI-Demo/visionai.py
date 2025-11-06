#!/usr/bin/env python3
"""
Vision AI Demo Manager Application

This application provides a GUI for managing vision AI demonstrations on embedded hardware.
It handles dual camera pipelines, real-time performance monitoring, IoT telemetry, and 
dynamic graph visualization of system metrics.

Key Features:
- Dual camera pipeline management with GStreamer
- Real-time system performance monitoring (CPU, GPU, DSP, Memory)
- IoT connectivity for remote command and control
- Dynamic graph rendering for utilization and thermal data
- Multi-threaded architecture for responsive UI

Author: Avnet
Platform: QCS6490 Vision AI Kit
"""

import collections
import os
import sys
import threading
import time
import gi
import signal
import atexit
import json
import fcntl

from vai.common import (APP_HEADER, CPU_THERMAL_KEY, CPU_UTIL_KEY,
                        GPU_THERMAL_KEY, GPU_UTIL_KEY, GRAPH_SAMPLE_SIZE,
                        MEM_THERMAL_KEY, MEM_UTIL_KEY, DSP_UTIL_KEY, NPU_THERMAL_KEY, TIME_KEY, 
                        TRIA, TRIA_BLUE_RGBH, TRIA_PINK_RGBH, TRIA_YELLOW_RGBH, 
                        TRIA_GREEN_RGBH, GRAPH_SAMPLE_WINDOW_SIZE_s,
                        get_ema)
from vai.graphing import (draw_axes_and_labels,
                          draw_graph_background_and_border, draw_graph_data)
from vai.handler import Handler
from vai.qprofile import QProfProcess

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, Callbacks, C2dAck, DeviceConfigError


def safe_read_json(path):
    """
    Thread-safe JSON file reader using file locking.
    
    Acquires a shared lock before reading to prevent race conditions
    with concurrent writers.
    
    Args:
        path (str): Path to the JSON file
        
    Returns:
        dict: Parsed JSON data
        
    Raises:
        json.JSONDecodeError: If file contains invalid JSON
        FileNotFoundError: If file doesn't exist
    """
    with open(path, "r") as f:
        fcntl.flock(f, fcntl.LOCK_SH)  # Acquire shared lock
        data = json.load(f)
        fcntl.flock(f, fcntl.LOCK_UN)  # Release lock
    return data


class FdFilter:
    """
    Low-level file descriptor filter for suppressing unwanted log messages.
    
    This class intercepts stdout and stderr at the file descriptor level,
    filtering out specified strings before they reach the terminal. This is
    necessary because some C libraries write directly to file descriptors,
    bypassing Python's sys.stdout/sys.stderr redirection.
    
    The filter operates by:
    1. Creating pipes to intercept stdout/stderr
    2. Redirecting file descriptors to these pipes
    3. Running background threads that read from pipes, filter content, 
       and write to original destinations
    
    Attributes:
        filter_strings (list): Lowercase strings to filter out
        original_stdout_fd (int): File descriptor for original stdout
        original_stderr_fd (int): File descriptor for original stderr
        stdout_pipe_r (int): Read end of stdout pipe
        stdout_pipe_w (int): Write end of stdout pipe
        stderr_pipe_r (int): Read end of stderr pipe
        stderr_pipe_w (int): Write end of stderr pipe
        stdout_thread (Thread): Thread processing stdout
        stderr_thread (Thread): Thread processing stderr
    """
    
    def __init__(self, filter_strings):
        """
        Initialize the file descriptor filter.
        
        Args:
            filter_strings (list): List of strings to filter from output
        """
        # Convert filter strings to lowercase for case-insensitive matching
        self.filter_strings = [s.lower() for s in filter_strings]
        
        # Duplicate original file descriptors to preserve them
        self.original_stdout_fd = os.dup(1)
        self.original_stderr_fd = os.dup(2)

        # Create pipes to intercept stdout and stderr
        self.stdout_pipe_r, self.stdout_pipe_w = os.pipe()
        self.stderr_pipe_r, self.stderr_pipe_w = os.pipe()

        # Redirect stdout (1) and stderr (2) to the write ends of our pipes
        os.dup2(self.stdout_pipe_w, 1)
        os.dup2(self.stderr_pipe_w, 2)

        # Create daemon threads to read from pipes, filter, and write to original FDs
        self.stdout_thread = threading.Thread(
            target=self._pipe_reader, 
            args=(self.stdout_pipe_r, self.original_stdout_fd)
        )
        self.stderr_thread = threading.Thread(
            target=self._pipe_reader, 
            args=(self.stderr_pipe_r, self.original_stderr_fd)
        )
        self.stdout_thread.daemon = True
        self.stderr_thread.daemon = True
        self.stdout_thread.start()
        self.stderr_thread.start()

    def _pipe_reader(self, pipe_r_fd, original_dest_fd):
        """
        Read from pipe, filter lines, and write to original destination.
        
        This method runs in a separate thread for each stream (stdout/stderr).
        It reads line by line, checks against filter strings, and only writes
        lines that don't match any filter.
        
        Args:
            pipe_r_fd (int): File descriptor for pipe read end
            original_dest_fd (int): File descriptor for original destination
        """
        with os.fdopen(pipe_r_fd, 'r') as pipe_file:
            for line in iter(pipe_file.readline, ''):
                # Only write line if it doesn't contain any filter string
                if not any(f in line.lower() for f in self.filter_strings):
                    os.write(original_dest_fd, line.encode('utf-8'))


# Lock GTK/GStreamer versions to prevent API incompatibility warnings
gi.require_version("Gdk", "3.0")
gi.require_version("Gst", "1.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gst, Gtk, GLib

# ============================================================================
# GRAPHING CONSTANTS
# ============================================================================

# Color mappings for utilization graphs (RGB float values)
UTIL_GRAPH_COLORS_RGBF = {
    CPU_UTIL_KEY: tuple(c / 255.0 for c in TRIA_PINK_RGBH),   # Pink for CPU
    MEM_UTIL_KEY: tuple(c / 255.0 for c in TRIA_BLUE_RGBH),   # Blue for Memory
    GPU_UTIL_KEY: tuple(c / 255.0 for c in TRIA_YELLOW_RGBH), # Yellow for GPU
    DSP_UTIL_KEY: tuple(c / 255.0 for c in TRIA_GREEN_RGBH),  # Green for DSP
}

# Color mappings for thermal graphs
THERMAL_GRAPH_COLORS_RGBF = {
    CPU_THERMAL_KEY: tuple(c / 255.0 for c in TRIA_PINK_RGBH),   # Pink for CPU
    MEM_THERMAL_KEY: tuple(c / 255.0 for c in TRIA_BLUE_RGBH),   # Blue for Memory
    GPU_THERMAL_KEY: tuple(c / 255.0 for c in TRIA_YELLOW_RGBH), # Yellow for GPU
}

# Graph display parameters
GRAPH_LABEL_FONT_SIZE = 14
MAX_TIME_DISPLAYED = 0      # Right edge of time axis (current time)
MIN_TEMP_DISPLAYED = 35     # Minimum temperature on Y-axis (°C)
MAX_TEMP_DISPLAYED = 95     # Maximum temperature on Y-axis (°C)
MIN_UTIL_DISPLAYED = 0      # Minimum utilization on Y-axis (%)
MAX_UTIL_DISPLAYED = 100    # Maximum utilization on Y-axis (%)

# ============================================================================
# END GRAPHING CONSTANTS
# ============================================================================


def is_monitor_above_2k():
    """
    Detect if any connected monitor has resolution greater than 2K (2560x1440).
    
    This function reads EDID (Extended Display Identification Data) from
    /sys/class/drm/ to determine native monitor resolution. It's used to
    decide which UI resource set to load (high-res vs standard).
    
    EDID Structure:
    - Byte 54-71: Detailed Timing Descriptor (DTD) 1
    - Bytes 2-4: Horizontal active pixels
    - Bytes 5-7: Vertical active lines
    
    Returns:
        bool: True if any monitor has resolution > 2560x1440, False otherwise
    """
    drm_path = '/sys/class/drm/'
    above_2k = False

    try:
        # Iterate through all DRM devices
        for device in os.listdir(drm_path):
            # Skip non-card devices
            if not device.startswith('card'):
                continue

            status_file = os.path.join(drm_path, device, 'status')
            edid_file = os.path.join(drm_path, device, 'edid')

            # Only check connected monitors with EDID data
            if os.path.exists(status_file) and os.path.exists(edid_file):
                with open(status_file, 'r') as f:
                    if f.read().strip() != 'connected':
                        continue

                # Read binary EDID data
                with open(edid_file, 'rb') as f:
                    edid_data = f.read()

                # EDID must be at least 128 bytes
                if len(edid_data) < 128:
                    continue

                # Parse first Detailed Timing Descriptor (preferred mode)
                dtd_start = 54
                if dtd_start + 18 <= len(edid_data):
                    dtd = edid_data[dtd_start:dtd_start+18]

                    # Extract horizontal resolution (10-bit value)
                    h_active_lo = dtd[2]
                    h_active_hi = (dtd[4] & 0xF0) >> 4
                    width = h_active_lo + (h_active_hi << 8)

                    # Extract vertical resolution (10-bit value)
                    v_active_lo = dtd[5]
                    v_active_hi = (dtd[7] & 0xF0) >> 4
                    height = v_active_lo + (v_active_hi << 8)

                    # Check if resolution exceeds 2K (2560x1440)
                    if width > 2560 or height > 1440:
                        # Verify it's a valid high-resolution display (4K+)
                        if width >= 3840 or height >= 2160:
                            above_2k = True
                            break  # Found 4K or higher, no need to continue

    except Exception as e:
        print(f"Error reading EDID: {e}")
        return False

    return above_2k


# Initialize GTK builder for UI construction
GladeBuilder = Gtk.Builder()
APP_FOLDER = os.path.dirname(__file__)

# Select appropriate resource folder based on monitor resolution
if is_monitor_above_2k():
    print("Connected monitor resolution is above 2K (e.g., 4K).")
    RESOURCE_FOLDER = os.path.join(APP_FOLDER, "resources_high")
else:
    print("No monitor above 2K resolution detected.")
    RESOURCE_FOLDER = os.path.join(APP_FOLDER, "resources_low")

# Path to GTK layout definition file
LAYOUT_PATH = os.path.join(RESOURCE_FOLDER, "GSTLauncher.glade")


def get_min_time_delta_smoothed(time_series: list):
    """
    Calculate smoothed time delta for graph X-axis.
    
    Computes the time difference between current time and oldest data point,
    with smoothing to reduce jitter near the window boundary.
    
    Args:
        time_series (list): List of monotonic timestamps
        
    Returns:
        int: Negative time delta in seconds (for left edge of graph)
    """
    if not time_series:
        return 0

    # Calculate raw time delta
    x_min = -int(time.monotonic() - time_series[0])

    # Snap to window size if within 1 second to reduce jitter
    if abs(x_min - GRAPH_SAMPLE_WINDOW_SIZE_s) <= 1:
        x_min = -GRAPH_SAMPLE_WINDOW_SIZE_s

    return x_min


class VaiDemoManager:
    """
    Main application manager for Vision AI Demo.
    
    This class orchestrates all application components including:
    - GTK UI management
    - GStreamer video pipelines
    - System performance monitoring
    - IoT connectivity and telemetry
    - Real-time graph rendering
    - Thread lifecycle management
    
    The application uses a multi-threaded architecture:
    - Main thread: GTK event loop
    - QProf thread: Performance monitoring
    - GStreamer thread: Video pipeline processing
    - Telemetry thread: IoT data transmission
    - GUI update thread: Periodic UI updates
    
    Attributes:
        eventHandler (Handler): Event handler for UI callbacks
        running (bool): Application running state
        demo0Interval (int): Demo 0 update interval
        demo1Interval (int): Demo 1 update interval
        demo0RunningIndex (int): Current demo 0 pipeline index
        demo1RunningIndex (int): Current demo 1 pipeline index
        shutdown_in_progress (bool): Flag to prevent duplicate shutdown
        stop_event (Event): Threading event for graceful shutdown
        iotc (Client): IoTConnect client instance
        main_window_dims (tuple): Current window dimensions (width, height)
        graphs_enabled (bool): Flag to enable/disable graph rendering
        util_data (dict): Utilization graph data buffers
        thermal_data (dict): Thermal graph data buffers
    """
    
    def __init__(self, port=7001):
        """
        Initialize the VaiDemoManager.
        
        Args:
            port (int): Port number for network services (default: 7001)
        """
        self.eventHandler = Handler()
        self.running = True
        self.demo0Interval = 0
        self.demo1Interval = 0
        self.demo0RunningIndex = 0
        self.demo1RunningIndex = 0
        self.shutdown_in_progress = False
        self.stop_event = threading.Event()
        self.iotc = None
        self.main_window_dims = (1920, 1080)  # Default dimensions, updated on resize

        # These hold the demo state for each demo
        # ["None", "Camera", "Pose Detection", "Segmentation", "Image Classification", "Object Detection", "Depth Segmentation"]
        self.demo0_index = 0
        self.demo1_index = 0


        # Register cleanup handler for abnormal exits
        atexit.register(self.cleanup_on_exit)
        self.graphs_enabled = True

    def cleanup_on_exit(self):
        """
        Emergency cleanup handler called on abnormal exit.
        
        This is registered with atexit to ensure cleanup occurs even if
        the application crashes or is terminated unexpectedly.
        """
        if not self.shutdown_in_progress:
            print("exit cleanup triggered")
            self.perform_shutdown()

    def perform_shutdown(self):
        """
        Perform graceful shutdown of all application components.
        
        Shutdown sequence:
        1. Disable graphs to prevent drawing during cleanup
        2. Set stop event to signal all threads
        3. Disconnect IoTConnect
        4. Stop GStreamer pipelines
        5. Wait for pipeline threads to complete
        6. Close performance monitoring
        
        This method is idempotent - calling it multiple times is safe.
        """
        # Prevent duplicate shutdown attempts
        if self.shutdown_in_progress:
            return
        
        self.shutdown_in_progress = True
        print("\n[SHUTDOWN] Starting graceful shutdown...")
        
        # Step 1: Disable graphs to prevent callbacks during cleanup
        self.graphs_enabled = False
        self.stop_event.set()
        
        # Step 2: Brief pause for in-flight callbacks to complete
        time.sleep(0.1)
        
        # Step 3: Disconnect IoTConnect
        if self.iotc:
            try:
                print("[SHUTDOWN] Disconnecting IoTConnect...")
                self.iotc.disconnect()
            except Exception as e:
                print(f"[SHUTDOWN] IoTConnect disconnect error: {e}")
        
        # Step 4: Stop GStreamer pipelines
        try:
            if hasattr(self.eventHandler, 'pipelineCtrl') and self.eventHandler.pipelineCtrl:
                print("[SHUTDOWN] Stopping pipelines...")
                self.eventHandler.pipelineCtrl.stop_pipeline(0)
                self.eventHandler.pipelineCtrl.stop_pipeline(1)
                
                # Wait for pipelines to stop gracefully
                max_wait = 2.0
                wait_interval = 0.1
                elapsed = 0
                while elapsed < max_wait and not self.eventHandler.pipelineCtrl.pipelines_finished():
                    time.sleep(wait_interval)
                    elapsed += wait_interval
                
                if self.eventHandler.pipelineCtrl.pipelines_finished():
                    print("[SHUTDOWN] Pipelines stopped successfully")
                else:
                    print("[SHUTDOWN] Warning: Pipelines did not stop cleanly")
                
                # Wait for GStreamer thread to terminate
                if hasattr(self.eventHandler.pipelineCtrl, 'gst_thread') and \
                   self.eventHandler.pipelineCtrl.gst_thread and \
                   self.eventHandler.pipelineCtrl.gst_thread.is_alive():
                    print("[SHUTDOWN] Waiting for GStreamer thread...")
                    self.eventHandler.pipelineCtrl.quit_gstreamer_main_loop()
                    self.eventHandler.pipelineCtrl.gst_thread.join(timeout=1.5)
                    print("[SHUTDOWN] GStreamer thread stopped")
        except Exception as e:
            print(f"[SHUTDOWN] Error stopping pipelines: {e}")
        
        # Step 5: Close performance monitoring
        if hasattr(self.eventHandler, 'QProf') and self.eventHandler.QProf:
            try:
                print("[SHUTDOWN] Closing QProf...")
                self.eventHandler.QProf.Close()
                if self.eventHandler.QProf.is_alive():
                    self.eventHandler.QProf.join(timeout=1.0)
            except Exception as e:
                print(f"[SHUTDOWN] QProf cleanup error: {e}")
        
        print("[SHUTDOWN] Cleanup complete")

    def handle_shutdown_signal(self, *args):
        """
        Handle OS shutdown signals (SIGINT, SIGTERM).
        
        This handler is registered with GLib's signal infrastructure to
        catch Ctrl+C and kill signals, allowing graceful shutdown.
        
        Args:
            *args: Signal arguments (unused)
            
        Returns:
            bool: False to allow signal propagation
        """
        print("\n[SIGNAL] Shutdown signal received")
        
        if not self.shutdown_in_progress:
            self.perform_shutdown()
            # Quit GTK main loop if running
            if Gtk.main_level() > 0:
                GLib.idle_add(Gtk.main_quit)
        
        return False

    def send_iotc_telemetry_loop(self):
        """
        Background thread for sending telemetry to IoTConnect.
        
        This thread runs continuously, collecting system metrics and demo
        inference results, then transmitting them to the cloud every 5 seconds.
        
        Telemetry includes:
        - System utilization (CPU, GPU, Memory, DSP)
        - System temperatures
        - Demo-specific inference results:
          * Pose Estimation: Keypoint positions and confidence
          * Object Detection: Detected objects and counts
          * Image Classification: Top-5 classifications
        
        The thread responds to stop_event for graceful shutdown.
        """
        demo_names = ["None", "Camera", "Pose Estimation", "Segmentation", "Image Classification", "Object Detection", "Depth Segmentation"]
        while not self.stop_event.is_set():
            try:
                # Check stop event before doing work
                if self.stop_event.is_set():
                    break
                
                # Collect system metrics
                sample_data = self.eventHandler.sample_data
                telemetry = {
                    "cpu_usage": sample_data.get(CPU_UTIL_KEY, 0),
                    "gpu_usage": sample_data.get(GPU_UTIL_KEY, 0),
                    "memory_usage": sample_data.get(MEM_UTIL_KEY, 0),
                    "npu_usage": sample_data.get(DSP_UTIL_KEY, 0),
                    "cpu_temp": sample_data.get(CPU_THERMAL_KEY, 0),
                    "gpu_temp": sample_data.get(GPU_THERMAL_KEY, 0),
                    "memory_temp": sample_data.get(MEM_THERMAL_KEY, 0),
                    "npu_temp": sample_data.get(NPU_THERMAL_KEY, 0),
                    "critical": 85,  # Critical temperature threshold
                }
                
                # Collect Demo 0 inference results
                try:
                    data_0 = safe_read_json("/var/rootdirs/opt/QCS6490-Vision-AI-Demo/data_0.json")
                    if data_0 and self.demo0_index in [2, 4, 5]:
                        name = demo_names[self.demo0_index]
                        # Pose Estimation telemetry
                        if name == "Pose Estimation":
                            telemetry["D0_Name"] = "Pose Estimation"
                            telemetry["D0_Pose_Confidence"] = 100 * data_0.get("PoseConfidence")
                            # Add all 17 keypoints
                            telemetry["D0_Nose"] = data_0.get("Nose")
                            telemetry["D0_Left_Eye"] = data_0.get("Left Eye")
                            telemetry["D0_Right_Eye"] = data_0.get("Right Eye")
                            telemetry["D0_Left_Ear"] = data_0.get("Left Ear")
                            telemetry["D0_Left_Shoulder"] = data_0.get("Left Shoulder")
                            telemetry["D0_Right_Shoulder"] = data_0.get("Right Shoulder")
                            telemetry["D0_Left_Elbow"] = data_0.get("Left Elbow")
                            telemetry["D0_Right_Elbow"] = data_0.get("Right Elbow")
                            telemetry["D0_Left_Wrist"] = data_0.get("Left Wrist")
                            telemetry["D0_Right_Wrist"] = data_0.get("Right Wrist")
                            telemetry["D0_Left_Hip"] = data_0.get("Left Hip")
                            telemetry["D0_Right_Hip"] = data_0.get("Right Hip")
                            telemetry["D0_Left_Knee"] = data_0.get("Left Knee")
                            telemetry["D0_Right_Knee"] = data_0.get("Right Knee")
                            telemetry["D0_Left_Ankle"] = data_0.get("Left Ankle")
                            telemetry["D0_Right_Ankle"] = data_0.get("Right Ankle")
                        
                        # Object Detection telemetry
                        elif name == "Object Detection":
                            telemetry["D0_Name"] = "Object Detection"
                            num_objs = data_0.get("Number_Objects_Detected")
                            telemetry["D0_Number_Objects_Detected"] = num_objs
                            # Add each detected object
                            if num_objs > 0:
                                for x in range(0, num_objs):
                                    telemetry_key = f"D0_Object_{x}"
                                    data_0_key = f"Object {x}"
                                    telemetry[telemetry_key] = data_0.get(data_0_key)
                        
                        # Image Classification telemetry
                        elif name == "Image Classification":
                            telemetry["D0_Name"] = "Image Classification"
                            # Add top-5 classifications
                            for x in range(0, 5):
                                telemetry_key = f"D0_Classification_{x}"
                                data_0_key = f"Classification {x}"
                                if data_0.get(data_0_key) is not None:
                                    telemetry[telemetry_key] = data_0.get(data_0_key)
                    else:
                        telemetry["D0_Name"] = demo_names[self.demo0_index]

                except (json.JSONDecodeError, FileNotFoundError):
                    telemetry["D0_Name"] = demo_names[self.demo0_index]
                
                # Collect Demo 1 inference results (same structure as Demo 0)
                try:
                    data_1 = safe_read_json("/var/rootdirs/opt/QCS6490-Vision-AI-Demo/data_1.json")
                    if data_1 and self.demo1_index in [2, 4, 5]:
                        name = demo_names[self.demo1_index]
                        if name == "Pose Estimation":
                            telemetry["D1_Name"] = "Pose Estimation"
                            telemetry["D1_Pose_Confidence"] = data_1.get("PoseConfidence")
                            telemetry["D1_Nose"] = data_1.get("Nose")
                            telemetry["D1_Left_Eye"] = data_1.get("Left Eye")
                            telemetry["D1_Right_Eye"] = data_1.get("Right Eye")
                            telemetry["D1_Left_Ear"] = data_1.get("Left Ear")
                            telemetry["D1_Left_Shoulder"] = data_1.get("Left Shoulder")
                            telemetry["D1_Right_Shoulder"] = data_1.get("Right Shoulder")
                            telemetry["D1_Left_Elbow"] = data_1.get("Left Elbow")
                            telemetry["D1_Right_Elbow"] = data_1.get("Right Elbow")
                            telemetry["D1_Left_Wrist"] = data_1.get("Left Wrist")
                            telemetry["D1_Right_Wrist"] = data_1.get("Right Wrist")
                            telemetry["D1_Left_Hip"] = data_1.get("Left Hip")
                            telemetry["D1_Right_Hip"] = data_1.get("Right Hip")
                            telemetry["D1_Left_Knee"] = data_1.get("Left Knee")
                            telemetry["D1_Right_Knee"] = data_1.get("Right Knee")
                            telemetry["D1_Left_Ankle"] = data_1.get("Left Ankle")
                            telemetry["D1_Right_Ankle"] = data_1.get("Right Ankle")
                        
                        elif name == "Object Detection":
                            telemetry["D1_Name"] = "Object Detection"
                            # Note: Bug fix needed - should use data_1 not data_0
                            num_objs = data_1.get("Number_Objects_Detected")
                            telemetry["D1_Number_Objects_Detected"] = num_objs
                            if num_objs > 0:
                                for x in range(0, num_objs):
                                    telemetry_key = f"D1_Object_{x}"
                                    data_1_key = f"Object {x}"
                                    telemetry[telemetry_key] = data_1.get(data_1_key)
                        
                        elif name == "Image Classification":
                            telemetry["D1_Name"] = "Image Classification"
                            for x in range(0, 5):
                                telemetry_key = f"D1_Classification_{x}"
                                data_1_key = f"Classification {x}"
                                if data_1.get(data_1_key) is not None:
                                    telemetry[telemetry_key] = data_1.get(data_1_key)
                    else:
                        telemetry["D1_Name"] = demo_names[self.demo1_index]
                        
                except (json.JSONDecodeError, FileNotFoundError):
                    telemetry["D1_Name"] = demo_names[self.demo1_index]
                
                # Send telemetry if IoTConnect is connected
                if self.iotc and not self.stop_event.is_set():
                    self.iotc.send_telemetry(telemetry)
            
            except Exception as e:
                if not self.stop_event.is_set():
                    print(f"[IOTC] Telemetry error: {e}")
            
            # Wait 5 seconds before next telemetry transmission
            # Using stop_event.wait() allows immediate shutdown response
            self.stop_event.wait(timeout=5.0)

    def handle_iotconnect_command(self, command):
        """
        Handle commands received from IoTConnect cloud.
        
        Processes remote commands to start/stop demos on either camera.
        Commands are executed in the GTK main thread using GLib.idle_add.
        
        Supported commands:
        - start_demo <camera> <pipeline>: Start a demo on specified camera
          * camera: 'cam0' or 'cam1'
          * pipeline: '1' through '6' (maps to demo selection index)
        - stop_demo <camera>: Stop demo on specified camera
        
        Args:
            command: IoTConnect command object containing:
                - command_name (str): Command identifier
                - command_args (list): Command arguments
        
        Acknowledgment is sent back to cloud with status:
        - CMD_SUCCESS_WITH_ACK: Command executed successfully
        - CMD_FAILED: Command failed (with error message)
        """
        cmd_name = command.command_name
        print(f"[IOTCONNECT] Command received: {cmd_name}")

        # Default response setup
        ack_message = "Unknown command"
        ack_status = C2dAck.CMD_FAILED

        if cmd_name == 'start_demo':
            try:
                # Parse command arguments
                camera = command.command_args[0].lower()
                pipeline = command.command_args[1].lower()

                # Map pipeline string to GUI combo box index
                # Index 0 is reserved for "Stop" option
                pipeline_mapping = {
                    "1": 1,
                    "2": 2,
                    "3": 3,
                    "4": 4,
                    "5": 5,
                    "6": 6
                }

                pipeline_index = pipeline_mapping.get(pipeline)
                if pipeline_index is None:
                    raise ValueError(f"Invalid pipeline: {pipeline}")

                # Execute command in GTK main thread
                if camera == 'cam0':
                    GLib.idle_add(self.eventHandler.demo_selection0.set_active, pipeline_index)
                    ack_message = f"CAM0 started {pipeline}"
                    ack_status = C2dAck.CMD_SUCCESS_WITH_ACK
                    self.demo0_index = pipeline_index
                elif camera == 'cam1':
                    GLib.idle_add(self.eventHandler.demo_selection1.set_active, pipeline_index)
                    ack_message = f"CAM1 started {pipeline}"
                    ack_status = C2dAck.CMD_SUCCESS_WITH_ACK
                    self.demo1_index = index
                else:
                    raise ValueError(f"Invalid camera: {camera}")

            except Exception as e:
                ack_message = f"Failed to start demo: {e}"
                ack_status = C2dAck.CMD_FAILED

            # Send acknowledgment back to cloud
            self.iotc.send_command_ack(command, ack_status, ack_message)

        elif cmd_name == 'stop_demo':
            try:
                camera = command.command_args[0].lower()

                # Set combo box to index 0 (Stop option)
                if camera == 'cam0':
                    GLib.idle_add(self.eventHandler.demo_selection0.set_active, 0)
                    ack_message = "CAM0 demo stopped"
                    ack_status = C2dAck.CMD_SUCCESS_WITH_ACK
                    self.demo0_index = 0
                elif camera == 'cam1':
                    GLib.idle_add(self.eventHandler.demo_selection1.set_active, 0)
                    ack_message = "CAM1 demo stopped"
                    ack_status = C2dAck.CMD_SUCCESS_WITH_ACK
                    self.demo1_index = 0
                else:
                    raise ValueError(f"Invalid camera: {camera}")

            except Exception as e:
                ack_message = f"Failed to stop demo: {e}"
                ack_status = C2dAck.CMD_FAILED

            self.iotc.send_command_ack(command, ack_status, ack_message)

        else:
            # Unknown command: send failure acknowledgment
            self.iotc.send_command_ack(command, ack_status, ack_message)

    def gui_data_update_loop(self):
        """
        Background thread for periodic GUI data updates.
        
        Currently a placeholder for future GUI update logic. This thread
        wakes every second and could be used for periodic UI refreshes
        that don't fit into the draw callbacks.
        """
        print("[GUI] Update thread started")
        while not self.stop_event.is_set():
            # Periodic GUI updates would go here
            self.stop_event.wait(timeout=1.0)
        print("[GUI] Update thread stopped")

    def resize_graphs_dynamically(self, parent_widget, _allocation):
        """
        Dynamically resize graph areas to fill available space.
        
        This callback is triggered on GTK size-allocate signal. It calculates
        remaining space after accounting for data grids and distributes it
        equally between the two graph areas.
        
        The function also adjusts the bottom box height to maintain proper
        layout when the window is resized.
        
        Args:
            parent_widget: GTK widget that triggered the signal
            _allocation: GTK allocation object (unused)
        """
        # Skip if graphs aren't initialized
        if not self.eventHandler.GraphDrawAreaTop or not self.eventHandler.GraphDrawAreaBottom:
            return
        
        # Get current window dimensions
        total_width = parent_widget.get_allocated_width()
        total_height = parent_widget.get_allocated_height()

        # Update stored dimensions for graph rendering
        self.main_window_dims = (total_width, total_height)
        
        # Skip if window hasn't been laid out yet
        if total_width == 0:
            return

        # Get bottom box container
        BottomBox = GladeBuilder.get_object("BottomBox")
        if not BottomBox:
            return

        BottomBox_width = BottomBox.get_allocated_width()
        if BottomBox_width == 0:
            return

        # Get data grid widgets (these determine remaining graph space)
        data_grid = GladeBuilder.get_object("DataGrid")
        data_grid1 = GladeBuilder.get_object("DataGrid1")
        if not data_grid or not data_grid1:
            return

        # Calculate remaining width for graphs
        remaining_graph_width = BottomBox_width - (
            data_grid.get_allocated_width() + data_grid1.get_allocated_width()
        )
        
        # Account for margins not included in allocated width
        remaining_graph_width -= (
            data_grid.get_margin_start() + data_grid.get_margin_end() + 10
        )
        remaining_graph_width -= (
            data_grid1.get_margin_start() + data_grid1.get_margin_end() + 10
        )

        # Split remaining space equally between two graphs
        half = remaining_graph_width // 2
        if half < 0:
            return

        # Adjust bottom box height based on camera position
        try:
            # Get absolute position of video display area
            window_x, window_y = self.eventHandler.DrawArea1.translate_coordinates(
                self.eventHandler.DrawArea1.get_toplevel(), 0, 0
            )

            camera_bottom_position = window_y + self.eventHandler.DrawArea1.get_allocated_height()

            # Resize bottom box if camera area is large enough
            if camera_bottom_position > 148:
                BottomBox.set_size_request(-1, round(total_height - camera_bottom_position))
        except:
            # Silently handle coordinate translation errors
            pass

        graph_top = self.eventHandler.GraphDrawAreaTop
        graph_bottom = self.eventHandler.GraphDrawAreaBottom
        
        # Only resize if dimensions have changed (prevents resize loops)
        if (
            graph_top.get_allocated_width() != half
            or graph_bottom.get_allocated_width() != half
        ):
            graph_top.set_size_request(half, -1)
            graph_bottom.set_size_request(half, -1)

    def init_graph_data(self, sample_size=GRAPH_SAMPLE_SIZE):
        """
        Initialize graph data structures with fixed-size buffers.
        
        Creates deque (double-ended queue) structures for efficient
        rolling window data storage. When maxlen is reached, oldest
        items are automatically discarded.
        
        Args:
            sample_size (int): Maximum number of samples to store
        """
        # Utilization data buffers (CPU, GPU, Memory, DSP)
        self.util_data = {
            TIME_KEY: collections.deque([], maxlen=sample_size),
            CPU_UTIL_KEY: collections.deque([], maxlen=sample_size),
            MEM_UTIL_KEY: collections.deque([], maxlen=sample_size),
            GPU_UTIL_KEY: collections.deque([], maxlen=sample_size),
            DSP_UTIL_KEY: collections.deque([], maxlen=sample_size),
        }
        
        # Thermal data buffers (CPU, GPU, Memory)
        self.thermal_data = {
            TIME_KEY: collections.deque([], maxlen=sample_size),
            CPU_THERMAL_KEY: collections.deque([], maxlen=sample_size),
            MEM_THERMAL_KEY: collections.deque([], maxlen=sample_size),
            GPU_THERMAL_KEY: collections.deque([], maxlen=sample_size),
        }

    def _sample_util_data(self):
        """
        Sample and smooth utilization data for graphing.
        
        This method:
        1. Timestamps the current sample
        2. Retrieves current utilization values
        3. Applies exponential moving average (EMA) smoothing
        4. Appends smoothed values to data buffers
        5. Removes samples outside the time window
        
        EMA smoothing reduces noise while maintaining responsiveness
        to real changes in system load.
        """
        # Initialize data structures if needed
        if self.util_data is None or self.thermal_data is None:
            self.init_graph_data()

        # Timestamp this sample
        self.util_data[TIME_KEY].append(time.monotonic())

        # Get current raw values
        cur_cpu = self.eventHandler.sample_data[CPU_UTIL_KEY]
        cur_gpu = self.eventHandler.sample_data[GPU_UTIL_KEY]
        cur_mem = self.eventHandler.sample_data[MEM_UTIL_KEY]
        cur_dsp = self.eventHandler.sample_data[DSP_UTIL_KEY]

        # Get previous values for smoothing (or use current if first sample)
        last_cpu = self.util_data[CPU_UTIL_KEY][-1] if self.util_data[CPU_UTIL_KEY] else cur_cpu
        last_gpu = self.util_data[GPU_UTIL_KEY][-1] if self.util_data[GPU_UTIL_KEY] else cur_gpu
        last_mem = self.util_data[MEM_UTIL_KEY][-1] if self.util_data[MEM_UTIL_KEY] else cur_mem
        last_dsp = self.util_data[DSP_UTIL_KEY][-1] if self.util_data[DSP_UTIL_KEY] else cur_dsp

        # Apply exponential moving average smoothing
        ema_cpu = get_ema(cur_cpu, last_cpu)
        ema_gpu = get_ema(cur_gpu, last_gpu)
        ema_mem = get_ema(cur_mem, last_mem)
        ema_dsp = get_ema(cur_dsp, last_dsp)

        # Append smoothed values
        self.util_data[CPU_UTIL_KEY].append(ema_cpu)
        self.util_data[GPU_UTIL_KEY].append(ema_gpu)
        self.util_data[MEM_UTIL_KEY].append(ema_mem)
        self.util_data[DSP_UTIL_KEY].append(ema_dsp)

        # Remove samples outside the time window
        cur_time = time.monotonic()
        while (
            self.util_data[TIME_KEY]
            and cur_time - self.util_data[TIME_KEY][0] > GRAPH_SAMPLE_WINDOW_SIZE_s
        ):
            self.util_data[TIME_KEY].popleft()
            self.util_data[CPU_UTIL_KEY].popleft()
            self.util_data[GPU_UTIL_KEY].popleft()
            self.util_data[MEM_UTIL_KEY].popleft()
            self.util_data[DSP_UTIL_KEY].popleft()

    def on_util_graph_draw(self, widget, cr):
        """
        GTK draw callback for utilization graph.
        
        This method is called by GTK whenever the graph widget needs to be
        redrawn. It performs the following steps:
        1. Check if shutdown is in progress
        2. Sample current utilization data
        3. Draw graph background and border
        4. Draw axes with labels
        5. Draw data lines for CPU, GPU, Memory, DSP
        
        Args:
            widget: GTK DrawingArea widget
            cr: Cairo context for drawing
            
        Returns:
            bool: True to prevent further event propagation
        """
        # Skip drawing if shutting down or graphs disabled
        if self.shutdown_in_progress or not self.graphs_enabled:
            return False
        
        try:
            # Verify graph widget exists
            if not self.eventHandler.GraphDrawAreaTop:
                return True

            # Verify data structures initialized
            if not hasattr(self, 'util_data') or not self.util_data:
                self.eventHandler.GraphDrawAreaTop.queue_draw()
                return True
            
            # Sample current data
            self._sample_util_data()

            # Get widget dimensions
            width = widget.get_allocated_width()
            height = widget.get_allocated_height()

            # Draw background and border
            draw_graph_background_and_border(
                width, height, cr, res_tuple=self.main_window_dims
            )

            # Calculate time axis limits
            x_min = get_min_time_delta_smoothed(self.util_data[TIME_KEY])
            x_lim = (x_min, MAX_TIME_DISPLAYED)
            y_lim = (MIN_UTIL_DISPLAYED, MAX_UTIL_DISPLAYED)

            # Draw axes with tick marks and labels
            x_axis, y_axis = draw_axes_and_labels(
                cr, width, height, x_lim, y_lim,
                x_ticks=4, y_ticks=2, dynamic_margin=True,
                x_label="seconds", y_label="%",
                res_tuple=self.main_window_dims,
            )
            
            # Draw data lines
            draw_graph_data(
                self.util_data, UTIL_GRAPH_COLORS_RGBF,
                x_axis, y_axis, cr, y_lim=y_lim,
                res_tuple=self.main_window_dims,
            )

            self.eventHandler.GraphDrawAreaTop.queue_draw()

        except Exception as e:
            # Log errors unless shutting down
            if not self.shutdown_in_progress:
                print(f"[GRAPH] Error in util graph draw: {e}")
            return False
        
        return True

    def _sample_thermal_data(self):
        """
        Sample and smooth thermal data for graphing.
        
        Similar to _sample_util_data but for temperature sensors.
        Applies EMA smoothing to reduce noise from thermal sensor readings.
        """
        # Initialize data structures if needed
        if self.thermal_data is None:
            self.init_graph_data()

        # Timestamp this sample
        self.thermal_data[TIME_KEY].append(time.monotonic())

        # Get current raw temperature values
        cur_cpu = self.eventHandler.sample_data[CPU_THERMAL_KEY]
        cur_gpu = self.eventHandler.sample_data[GPU_THERMAL_KEY]
        cur_mem = self.eventHandler.sample_data[MEM_THERMAL_KEY]

        # Get previous values for smoothing
        last_cpu = self.thermal_data[CPU_THERMAL_KEY][-1] if self.thermal_data[CPU_THERMAL_KEY] else cur_cpu
        last_gpu = self.thermal_data[GPU_THERMAL_KEY][-1] if self.thermal_data[GPU_THERMAL_KEY] else cur_gpu
        last_mem = self.thermal_data[MEM_THERMAL_KEY][-1] if self.thermal_data[MEM_THERMAL_KEY] else cur_mem

        # Apply exponential moving average smoothing
        ema_cpu = get_ema(cur_cpu, last_cpu)
        ema_gpu = get_ema(cur_gpu, last_gpu)
        ema_mem = get_ema(cur_mem, last_mem)

        # Append smoothed values
        self.thermal_data[CPU_THERMAL_KEY].append(ema_cpu)
        self.thermal_data[GPU_THERMAL_KEY].append(ema_gpu)
        self.thermal_data[MEM_THERMAL_KEY].append(ema_mem)

        # Remove samples outside the time window
        cur_time = time.monotonic()
        while (
            self.thermal_data[TIME_KEY]
            and cur_time - self.thermal_data[TIME_KEY][0] > GRAPH_SAMPLE_WINDOW_SIZE_s
        ):
            self.thermal_data[TIME_KEY].popleft()
            self.thermal_data[CPU_THERMAL_KEY].popleft()
            self.thermal_data[GPU_THERMAL_KEY].popleft()
            self.thermal_data[MEM_THERMAL_KEY].popleft()

    def on_thermal_graph_draw(self, widget, cr):
        """
        GTK draw callback for thermal graph.
        
        Similar to on_util_graph_draw but renders temperature data
        instead of utilization percentages.
        
        Args:
            widget: GTK DrawingArea widget
            cr: Cairo context for drawing
            
        Returns:
            bool: True to prevent further event propagation
        """
        # Skip drawing if shutting down or graphs disabled
        if self.shutdown_in_progress or not self.graphs_enabled:
            return False
        
        try:
            # Verify graph widget exists
            if not self.eventHandler.GraphDrawAreaBottom:
                return False
            
            # Verify data structures initialized
            if not hasattr(self, 'thermal_data') or not self.thermal_data:
                self.eventHandler.GraphDrawAreaBottom.queue_draw()
                return True
            
            # Sample current thermal data
            self._sample_thermal_data()

            # Get widget dimensions
            width = widget.get_allocated_width()
            height = widget.get_allocated_height()

            # Draw background and border
            draw_graph_background_and_border(
                width, height, cr, res_tuple=self.main_window_dims
            )
            
            # Calculate axis limits
            x_min = get_min_time_delta_smoothed(self.thermal_data[TIME_KEY])
            x_lim = (x_min, MAX_TIME_DISPLAYED)
            y_lim = (MIN_TEMP_DISPLAYED, MAX_TEMP_DISPLAYED)

            # Draw axes with tick marks and labels
            x_axis, y_axis = draw_axes_and_labels(
                cr, width, height, x_lim, y_lim,
                x_ticks=4, y_ticks=2, dynamic_margin=True,
                x_label="seconds", y_label="°C",
                res_tuple=self.main_window_dims,
            )
            
            # Draw temperature lines
            draw_graph_data(
                self.thermal_data, THERMAL_GRAPH_COLORS_RGBF,
                x_axis, y_axis, cr, y_lim=y_lim,
                res_tuple=self.main_window_dims,
            )

            self.eventHandler.GraphDrawAreaBottom.queue_draw()

        except Exception as e:
            # Log errors unless shutting down
            if not self.shutdown_in_progress:
                print(f"[GRAPH] Error in thermal graph draw: {e}")
            return False
        
        return True

    def localApp(self):
        """
        Initialize and configure the GTK application.
        
        This is the main application setup method that:
        1. Initializes GStreamer
        2. Loads UI from Glade file
        3. Configures CSS styling
        4. Sets up all UI elements and connections
        5. Starts background threads
        6. Configures IoTConnect
        7. Shows the main window
        
        The method constructs the entire application UI and prepares
        all components for operation before entering the GTK main loop.
        """
        global GladeBuilder

        # Initialize GStreamer (log level controlled by GST_DEBUG env var)
        Gst.init(None)

        self.eventHandler.vai_manager = self

        # Initialize graph data structures
        self.init_graph_data()

        # Load UI definition from Glade file
        GladeBuilder.add_from_file(LAYOUT_PATH)
        GladeBuilder.connect_signals(self.eventHandler)

        # Load and apply CSS styling
        screen = Gdk.Screen.get_default()
        provider = Gtk.CssProvider()
        provider.load_from_path(os.path.join(RESOURCE_FOLDER, "app.css"))
        Gtk.StyleContext.add_provider_for_screen(
            screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # ===== Connect UI Elements =====
        
        # Main window setup
        self.eventHandler.MainWindow = GladeBuilder.get_object("mainWindow")
        self.eventHandler.MainWindow.connect(
            "size-allocate", self.resize_graphs_dynamically
        )
        
        # Dialog windows
        self.eventHandler.aboutWindow = GladeBuilder.get_object("aboutWindow")
        self.eventHandler.dialogWindow = GladeBuilder.get_object("dialogWindow")
        
        # Performance metric labels
        self.eventHandler.FPSRate0 = GladeBuilder.get_object("FPS_rate_0")
        self.eventHandler.FPSRate1 = GladeBuilder.get_object("FPS_rate_1")
        self.eventHandler.CPU_load = GladeBuilder.get_object("CPU_load")
        self.eventHandler.GPU_load = GladeBuilder.get_object("GPU_load")
        self.eventHandler.DSP_load = GladeBuilder.get_object("DSP_load")
        self.eventHandler.MEM_load = GladeBuilder.get_object("MEM_load")
        self.eventHandler.CPU_temp = GladeBuilder.get_object("CPU_temp")
        self.eventHandler.GPU_temp = GladeBuilder.get_object("GPU_temp")
        self.eventHandler.MEM_temp = GladeBuilder.get_object("MEM_temp")
        
        # Layout containers
        self.eventHandler.TopBox = GladeBuilder.get_object("TopBox")
        self.eventHandler.DataGrid = GladeBuilder.get_object("DataGrid")
        self.eventHandler.BottomBox = GladeBuilder.get_object("BottomBox")
        
        # Video display areas
        self.eventHandler.DrawArea1 = GladeBuilder.get_object("videosink0")
        self.eventHandler.DrawArea2 = GladeBuilder.get_object("videosink1")
        self.eventHandler.set_video_sink(0, GladeBuilder.get_object("videosink0"))
        self.eventHandler.set_video_sink(1, GladeBuilder.get_object("videosink1"))
        
        # Graph drawing areas
        self.eventHandler.GraphDrawAreaTop = GladeBuilder.get_object("GraphDrawAreaTop")
        self.eventHandler.GraphDrawAreaBottom = GladeBuilder.get_object("GraphDrawAreaBottom")
        
        # Demo selection combo boxes
        self.eventHandler.demo_selection0 = GladeBuilder.get_object("demo_selection0")
        self.eventHandler.demo_selection1 = GladeBuilder.get_object("demo_selection1")
        
        # Disable pipeline selection until cameras are detected
        self.eventHandler.demo_selection0.set_sensitive(False)
        self.eventHandler.demo_selection1.set_sensitive(False)

        # Get demo selection counts
        model = self.eventHandler.demo_selection0.get_model()
        if model is not None:
            self.eventHandler.demoSelection0Cnt = len(model)

        model = self.eventHandler.demo_selection1.get_model()
        if model is not None:
            self.eventHandler.demoSelection1Cnt = len(model)

        # Connect graph draw callbacks
        self.eventHandler.GraphDrawAreaTop.connect("draw", self.on_util_graph_draw)
        self.eventHandler.GraphDrawAreaBottom.connect("draw", self.on_thermal_graph_draw)

        # ===== Start Performance Monitoring =====
        
        self.eventHandler.QProf = QProfProcess()
        self.eventHandler.QProf.daemon = True  # Don't block app exit
        self.eventHandler.QProf.start()

        # ===== Configure Window Appearance =====
        
        # Set background colors (TODO: Move to CSS)
        self.eventHandler.MainWindow.override_background_color(
            Gtk.StateFlags.NORMAL, Gdk.RGBA(23 / 255, 23 / 255, 23 / 255, 0)
        )
        self.eventHandler.TopBox.override_background_color(
            Gtk.StateType.NORMAL, Gdk.RGBA(23 / 255, 23 / 255, 23 / 255, 0.5)
        )
        self.eventHandler.BottomBox.override_background_color(
            Gtk.StateType.NORMAL, Gdk.RGBA(0 / 255, 23 / 255, 23 / 255, 1)
        )

        # Configure window properties
        self.eventHandler.MainWindow.set_decorated(False)  # No title bar
        self.eventHandler.MainWindow.set_keep_below(True)  # Stay below other windows
        self.eventHandler.MainWindow.maximize()  # Start maximized

        # Configure cursor theme
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-cursor-theme-name", "Adwaita")
        settings.set_property("gtk-cursor-theme-size", 32)

        # ===== Filter Unwanted Log Messages =====
        
        # The QNN plugin prints unavoidable log messages, so we filter them
        # at the file descriptor level
        filter_list = [
            "<W> No usable logger handle was found",
            "<W> Logs will be sent to the system's default channel",
            "Could not find ncvt for conv cost",
            "Could not find conv_ctrl for conv cost"
        ]
        self.log_filter = FdFilter(filter_list)

        # ===== Initialize IoTConnect =====
        
        try:
            # Load device configuration from JSON files
            device_config = DeviceConfig.from_iotc_device_config_json_file(
                device_config_json_path="iotc_config/iotcDeviceConfig.json",
                device_cert_path="iotc_config/device-cert.pem",
                device_pkey_path="iotc_config/device-pkey.pem"
            )
            
            # Create client with command callback
            self.iotc = Client(
                config=device_config,
                callbacks=Callbacks(command_cb=self.handle_iotconnect_command)
            )
            
            # Connect to IoT platform
            self.iotc.connect()
            print("[IOTC] Connected successfully")
        except DeviceConfigError as dce:
            print(f"[IOTC] Configuration error: {dce}")
            self.iotc = None  # Disable IoT features
        except Exception as e:
            print(f"[IOTC] Connection error: {e}")
            self.iotc = None

        # ===== Launch Background Threads =====
        
        # Telemetry transmission thread
        threading.Thread(target=self.send_iotc_telemetry_loop, daemon=True).start()
        
        # GUI update thread
        threading.Thread(target=self.gui_data_update_loop, daemon=True).start()

        # ===== Show Application Window =====
        
        self.eventHandler.MainWindow.show_all()


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Print application header
    print(TRIA)
    print(f"\nLaunching {APP_HEADER}")
    
    # Create application instance
    video = VaiDemoManager()
    
    # Register signal handlers for graceful shutdown
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGINT, video.handle_shutdown_signal)
    GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal.SIGTERM, video.handle_shutdown_signal)
    
    # Initialize the application
    video.localApp()
    
    # Run GTK main event loop
    try:
        print("[MAIN] Entering GTK main loop")
        Gtk.main()
    except KeyboardInterrupt:
        print("\n[MAIN] KeyboardInterrupt caught")
    except Exception as e:
        print(f"\n[MAIN] Exception in main loop: {e}")
    finally:
        print("[MAIN] GTK main loop exited")
        
        # Clean up temporary JSON files
        for filename in ["data_0.json", "data_1.json"]:
            if os.path.exists(filename):
                os.remove(filename)
        
        # Perform final shutdown if not already done
        if not video.shutdown_in_progress:
            video.perform_shutdown()
        
        # Brief pause to let cleanup complete
        time.sleep(0.2)
        print("[MAIN] Application exit")
