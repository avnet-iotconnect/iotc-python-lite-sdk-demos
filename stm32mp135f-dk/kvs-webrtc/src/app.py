# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

import sys
import time
import random
import subprocess
import signal
import os
import urllib.request
import requests
import threading
import queue
import traceback
from typing import Optional

import numpy as np
import app_webrtc

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, C2dOta, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck

client: Client = None
device_config: DeviceConfig = None
_stream_process: Optional[subprocess.Popen] = None
_webrtc_thread: Optional[threading.Thread] = None
_frame_queue: queue.Queue = queue.Queue(maxsize=1)

camera_options = {
    "video": {
        "width": 640,
        "height": 480,
        "framerate": 15
    },
    "verbose": False
}


def extract_and_run_tar_gz(targz_filename: str):
    try:
        subprocess.run(("tar", "-xzvf", targz_filename, "--overwrite"), check=True)
        current_directory = os.getcwd()
        script_file_path = os.path.join(current_directory, "install.sh")
        # If install.sh is found in the current directory, execute it and then delete it
        # so it is not executed automatically again for future packages (may not include an install.sh)
        if os.path.isfile(script_file_path):
            try:
                subprocess.run(['bash', script_file_path], check=True)
                os.remove(script_file_path)
                print(f"Successfully executed install.sh")
                return True
            except subprocess.CalledProcessError as e:
                os.remove(script_file_path)
                print(f"Error executing install.sh: {e}")
                return False
            except Exception as e:
                os.remove(script_file_path)
                print(f"An error occurred: {e}")
                return False
        else:
            print("install.sh not found in the current directory.")
            return True
    except subprocess.CalledProcessError:
        return False


def detect_video_device() -> Optional[str]:
    # On the STM32MP135F-DK the onboard camera interface (dcmipp) also appears as
    # a /dev/videoN node. To reliably pick a USB camera regardless of which port it
    # is plugged into or what number it is assigned, we check the sysfs path for
    # each video device: USB-connected devices have "usb" in their resolved sysfs
    # path while onboard devices do not.
    try:
        devices = sorted([d for d in os.listdir("/dev") if d.startswith("video")])
        for dev in devices:
            sysfs_path = f"/sys/class/video4linux/{dev}"
            if os.path.exists(sysfs_path):
                real_path = os.path.realpath(sysfs_path)
                if "usb" in real_path:
                    video_device = f"/dev/{dev}"
                    print(f"Detected USB video device: {video_device}")
                    return video_device
        print("No USB video devices found")
        return None
    except Exception as e:
        print(f"Error detecting video device: {e}")
        return None


def start_capture_process() -> Optional[subprocess.Popen]:
    global _stream_process

    if sys.platform not in ('linux', 'linux2'):
        print("GStreamer video capture is only supported on Linux")
        return None

    print("Starting GStreamer capture pipeline...")

    device_port = camera_options.get("deviceport") or detect_video_device()
    if not device_port:
        print("No video device available")
        return None

    video_width = camera_options.get("video", {}).get("width", 640)
    video_height = camera_options.get("video", {}).get("height", 480)
    video_framerate = camera_options.get("video", {}).get("framerate", 15)

    verbose = camera_options.get("verbose", False)
    verbose_flag = "-v " if verbose else ""

    # GStreamer pipeline: capture raw RGB frames from USB camera and write to stdout.
    # The STM32MP135F-DK has no hardware H264 encoder, but for WebRTC that is not
    # needed — aiortc handles encoding on the Python side. We capture raw YUY2 from
    # v4l2src, convert to RGB, and pipe the raw bytes to the frame reader thread.
    # The default is 640x480@15fps to stay within the Cortex-A7's budget alongside
    # the WebRTC encoding performed by aiortc. Adjust camera_options as needed.
    gst_command = (
        f"gst-launch-1.0 {verbose_flag}"
        f"v4l2src device={device_port} do-timestamp=true ! "
        f"video/x-raw,format=YUY2,width={video_width},height={video_height},framerate={video_framerate}/1 ! "
        f"videoconvert ! video/x-raw,format=RGB ! "
        f"fdsink fd=1"
    )

    if verbose:
        print(f"GStreamer command:\n{gst_command}")

    try:
        _stream_process = subprocess.Popen(
            gst_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid,
            text=False
        )

        # Start thread to read raw RGB frames from stdout and feed into _frame_queue
        threading.Thread(
            target=_frame_reader,
            args=(_stream_process, video_width, video_height),
            daemon=True
        ).start()

        # Start thread to drain stderr (prevents pipe buffer from blocking GStreamer)
        threading.Thread(
            target=_pipe_reader,
            args=("GSTERR", _stream_process.stderr, verbose),
            daemon=True
        ).start()

        # Wait a moment and verify GStreamer started successfully
        time.sleep(2.0)
        return_code = _stream_process.poll()
        if return_code is not None:
            print(f"GStreamer exited immediately with code {return_code}")
            print("This usually means:")
            print("   - GStreamer is not installed")
            print("   - Video device is not accessible")
            print("   - Camera does not support the requested format/resolution")
            _stream_process = None
            return None

        print("GStreamer capture pipeline started successfully")
        return _stream_process

    except FileNotFoundError:
        print("GStreamer is NOT installed on this system")
        print("Install with: apt-get install gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good")
        return None
    except Exception as e:
        print(f"Error starting GStreamer: {e}")
        return None


def _frame_reader(proc: subprocess.Popen, width: int, height: int):
    """Read raw RGB frames from the GStreamer fdsink subprocess and enqueue them."""
    frame_size = width * height * 3
    while True:
        data = b''
        while len(data) < frame_size:
            try:
                chunk = proc.stdout.read(frame_size - len(data))
            except Exception:
                return
            if not chunk:
                return
            data += chunk
        frame = np.frombuffer(data, dtype=np.uint8).reshape((height, width, 3)).copy()
        try:
            _frame_queue.put_nowait(frame)
        except queue.Full:
            pass


def _pipe_reader(prefix: str, pipe, verbose: bool = False):
    try:
        for line in iter(pipe.readline, b''):
            if verbose:
                decoded = line.decode(errors='replace').rstrip()
                print(f"{decoded}")
    except Exception as e:
        print(f"Error reading pipe: {e}")
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def stop_video_stream() -> bool:
    global _stream_process

    if sys.platform not in ('linux', 'linux2'):
        print("Stopping GStreamer is only supported on Linux")
        return False

    if _stream_process is None:
        print("No capture pipeline is running")
        return False

    try:
        print("Stopping capture pipeline...")
        os.killpg(os.getpgid(_stream_process.pid), signal.SIGTERM)
        _stream_process = None
        print("Capture pipeline stopped")
        return True
    except Exception as e:
        print(f"Error stopping capture pipeline: {e}")
        return False


def is_streaming() -> bool:
    global _stream_process

    if _stream_process is None:
        return False

    if _stream_process.poll() is not None:
        _stream_process = None
        return False

    return True


def check_and_refresh_credentials(kvs_client):
    """Check KVS credentials expiry and refresh if needed, updating the WebRTC client."""
    if kvs_client is not None and kvs_client.get_secs_to_expiry() < 60:
        print("Refreshing KVS credentials...")
        creds = kvs_client.obtain_credentials()
        if app_webrtc.webrtc_client is not None:
            app_webrtc.webrtc_client.refresh_credentials(
                creds.access_key_id,
                creds.secret_access_key,
                creds.session_token
            )


def on_video_stream(kvs_client):
    global _webrtc_thread

    if kvs_client.is_streaming():
        print("Starting WebRTC video stream...")

        if is_streaming():
            print("Video stream is already running")
            return

        try:
            check_and_refresh_credentials(kvs_client)
            creds = kvs_client.get_credentials()

            if creds is None:
                print("Failed to get AWS credentials")
                return

            channel_arn = kvs_client.get_signaling_channel_arn()
            if not channel_arn:
                print("No KVS signaling channel ARN available.")
                print("Ensure the device is created with the 'kvswebrtc' template.")
                return

            proc = start_capture_process()
            if proc is None:
                print("Failed to start video capture pipeline")
                return

            # Start the WebRTC signaling thread only if it is not already running.
            # On stop/start cycles the existing thread continues to handle signaling;
            # restarting capture is sufficient to resume frame delivery.
            if _webrtc_thread is None or not _webrtc_thread.is_alive():
                _webrtc_thread = threading.Thread(
                    target=app_webrtc.start_webrtc,
                    args=(
                        "us-east-1",
                        channel_arn,
                        creds.access_key_id,
                        creds.secret_access_key,
                        creds.session_token,
                        _frame_queue
                    ),
                    daemon=True
                )
                _webrtc_thread.start()

            print("WebRTC stream started successfully")

        except Exception as e:
            print(f"Error starting WebRTC stream: {e}")
            traceback.print_exc()
    else:
        if not is_streaming():
            print("No video stream is running")
            return

        if not stop_video_stream():
            print("Failed to stop video stream")


def on_command(msg: C2dCommand):
    print("Received command", msg.command_name, msg.command_args, msg.ack_id)
    if msg.command_name == "file-download":
        if len(msg.command_args) == 1:
            status_message = "Downloading %s to device" % (msg.command_args[0])
            response = requests.get(msg.command_args[0])
            if response.status_code == 200:
                with open('package.tar.gz', 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                print(f"File downloaded successfully and saved to package.tar.gz")
            else:
                print(f"Failed to download the file. Status code: {response.status_code}")
            client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status_message)
            print(status_message)
            extract_and_run_tar_gz('package.tar.gz')
            print("Download command successful. Will restart the application...")
            print("")
            sys.stdout.flush()
            os.execv(sys.executable, [sys.executable, __file__] + sys.argv[1:])
        else:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")
            print("Expected 1 command argument, but got", len(msg.command_args))
    else:
        print("Command %s not implemented!" % msg.command_name)
        if msg.ack_id is not None:
            client.send_command_ack(msg, C2dAck.CMD_FAILED, "Not Implemented")


def on_ota(msg: C2dOta):
    print("Starting OTA downloads for version %s" % msg.version)
    client.send_ota_ack(msg, C2dAck.OTA_DOWNLOADING)
    extraction_success = False
    for url in msg.urls:
        print("Downloading OTA file %s from %s" % (url.file_name, url.url))
        try:
            urllib.request.urlretrieve(url.url, url.file_name)
        except Exception as e:
            print("Encountered download error", e)
            break
        if url.file_name.endswith(".tar.gz"):
            extraction_success = extract_and_run_tar_gz(url.file_name)
            if extraction_success is False:
                break
        else:
            print("ERROR: Unhandled file format for file %s" % url.file_name)
    if extraction_success is True:
        print("OTA successful. Will restart the application...")
        client.send_ota_ack(msg, C2dAck.OTA_DOWNLOAD_DONE)
        print("")
        sys.stdout.flush()
        os.execv(sys.executable, [sys.executable, __file__] + [sys.argv[0]])
    else:
        print('Encountered a download processing error. Not restarting.')


def on_disconnect(reason: str, disconnected_from_server: bool):
    print(f"Disconnected. Reason: {reason}")
    if is_streaming():
        print("Stopping capture pipeline due to disconnect...")
        stop_video_stream()


if __name__ == "__main__":

    try:
        device_config = DeviceConfig.from_iotc_device_config_json_file(
            device_config_json_path="iotcDeviceConfig.json",
            device_cert_path="device-cert.pem",
            device_pkey_path="device-pkey.pem"
        )
    except DeviceConfigError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    callbacks = Callbacks(
        command_cb=on_command,
        ota_cb=on_ota,
        disconnected_cb=on_disconnect,
        vs_cb=on_video_stream
    )

    try:
        client = Client(device_config, callbacks)
    except Exception as e:
        print(f"Failed to create client: {e}")
        sys.exit(1)

    print("Connecting to /IOTCONNECT...")
    client.connect()

    if not client.is_connected():
        print("Failed to connect")
        sys.exit(1)

    print("Connected to /IOTCONNECT")

    kvs_client = client.get_kvs_client()
    if kvs_client is not None:
        kvs_client.obtain_credentials()
        print(f"\nKinesis Video Streaming is ENABLED")
        print(f"Credentials endpoint: {kvs_client.credentials_endpoint}")
        print(f"Signaling channel ARN: {kvs_client.get_signaling_channel_arn()}")
        print(f"Auto-start: {kvs_client.is_auto_start()}")
        if kvs_client.is_auto_start():
            print("Auto-starting WebRTC stream in 3 seconds...")
            time.sleep(3)
            on_video_stream(kvs_client)
    else:
        print("\nKinesis Video Streaming is NOT enabled")

    print("\n" + "=" * 50)
    print("Waiting for commands from /IOTCONNECT...")
    print("Send command type 112 to start streaming")
    print("Send command type 113 to stop streaming")
    print("Press Ctrl+C to exit")
    print("=" * 50 + "\n")

    try:
        while True:
            if not client.is_connected():
                print("Connection lost, attempting to reconnect...")
                client.connect()

            check_and_refresh_credentials(kvs_client)

            client.send_telemetry({
                "random": random.randint(0, 100),
                "streaming": is_streaming()
            })

            time.sleep(10)

    except KeyboardInterrupt:
        print("\nShutting down...")
        if is_streaming():
            print("Stopping capture pipeline...")
            stop_video_stream()
        client.disconnect()
        print("Shutdown complete.")
