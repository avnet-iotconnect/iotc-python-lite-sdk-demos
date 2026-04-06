# SPDX-License-Identifier: MIT
# Copyright (C) 2026 Avnet

import os
import random
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

from avnet.iotconnect.sdk.lite import Client, DeviceConfig, C2dCommand, C2dOta, Callbacks, DeviceConfigError
from avnet.iotconnect.sdk.sdklib.mqtt import C2dAck, C2dMessage

client: Optional[Client] = None
device_config: Optional[DeviceConfig] = None
_record_process: Optional[subprocess.Popen] = None
_uploader_thread: Optional[threading.Thread] = None
_uploader_stop_event = threading.Event()
_recording_lock = threading.Lock()
_upload_lock = threading.Lock()
_stats_lock = threading.Lock()
_uploaded_clips = 0
_upload_failures = 0
_last_uploaded_clip = ""
_last_record_error = ""
_recording_requested = False
_record_request_version = 0
_current_session_id = ""
_gst_stderr_buffer = deque(maxlen=120)

BUNDLE_LIB_PATH = "/opt/video-upload-libs"


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None or len(raw.strip()) == 0:
        return default
    try:
        value = int(raw)
        if value < minimum:
            raise ValueError()
        return value
    except ValueError:
        print(f"Invalid value for {name}={raw!r}. Using default {default}.")
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or len(raw.strip()) == 0:
        return default

    normalized = raw.strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False

    print(f"Invalid value for {name}={raw!r}. Using default {default}.")
    return default


# The NXP FRDM-IMX93 has no onboard camera hardware, only the USB camera.
# The C920 captures MJPG at 1280x720 @ 30fps over USB, which is then decoded
# in software and re-encoded to H264 via x264enc on the Cortex-A55 CPU.
camera_options = {
    "video": {
        "width": 1280,
        "height": 720,
        "framerate": 30
    },
    "verbose": False
}

clip_options = {
    "duration_secs": _env_int("VIDEO_CLIP_LENGTH_SECS", 30),
    "scan_interval_secs": _env_int("VIDEO_UPLOAD_SCAN_SECS", 5),
    "min_file_age_secs": _env_int("VIDEO_UPLOAD_MIN_FILE_AGE_SECS", 3),
    "output_dir": os.getenv("VIDEO_UPLOAD_DIR", "/opt/demo/video-clips"),
    "delete_after_upload": os.getenv("VIDEO_DELETE_AFTER_UPLOAD", "1") != "0",
}

app_options = {
    "auto_start_recording": _env_bool("VIDEO_AUTOSTART", False),
}


def extract_and_run_tar_gz(targz_filename: str):
    try:
        subprocess.run(("tar", "-xzvf", targz_filename, "--overwrite"), check=True)
        current_directory = os.getcwd()
        script_file_path = os.path.join(current_directory, "install.sh")
        if os.path.isfile(script_file_path):
            try:
                subprocess.run(["bash", script_file_path], check=True)
                os.remove(script_file_path)
                print("Successfully executed install.sh")
                return True
            except subprocess.CalledProcessError as exc:
                os.remove(script_file_path)
                print(f"Error executing install.sh: {exc}")
                return False
            except Exception as exc:
                os.remove(script_file_path)
                print(f"An error occurred: {exc}")
                return False
        print("install.sh not found in the current directory.")
        return True
    except subprocess.CalledProcessError:
        return False


def detect_video_device() -> Optional[str]:
    try:
        devices = sorted([dev for dev in os.listdir("/dev") if dev.startswith("video")])
        for dev in devices:
            sysfs_path = f"/sys/class/video4linux/{dev}"
            if not os.path.exists(sysfs_path):
                continue
            real_path = os.path.realpath(sysfs_path)
            if "usb" in real_path:
                video_device = f"/dev/{dev}"
                print(f"Detected USB video device: {video_device}")
                return video_device
        print("No USB video devices found")
        return None
    except Exception as exc:
        print(f"Error detecting video device: {exc}")
        return None


def clip_directory() -> Path:
    return Path(clip_options["output_dir"])


def ensure_clip_directory():
    clip_directory().mkdir(parents=True, exist_ok=True)


def _bundle_gst_env() -> dict:
    gst_env = os.environ.copy()
    existing_ld = gst_env.get("LD_LIBRARY_PATH", "")
    gst_env["LD_LIBRARY_PATH"] = f"{BUNDLE_LIB_PATH}:{existing_ld}" if existing_ld else BUNDLE_LIB_PATH
    existing_plugins = gst_env.get("GST_PLUGIN_PATH", "")
    gst_env["GST_PLUGIN_PATH"] = f"{BUNDLE_LIB_PATH}:{existing_plugins}" if existing_plugins else BUNDLE_LIB_PATH
    return gst_env


def _clear_gst_stderr_buffer():
    _gst_stderr_buffer.clear()


def _capture_recent_gst_stderr(stderr_output: bytes):
    for raw_line in stderr_output.splitlines():
        decoded = raw_line.decode(errors="replace").rstrip()
        if len(decoded) > 0:
            _gst_stderr_buffer.append(decoded)


def _print_recent_gst_stderr():
    if not _gst_stderr_buffer:
        print("No GStreamer stderr output was captured.")
        return

    print("Recent GStreamer stderr:")
    for line in _gst_stderr_buffer:
        print(f"GSTERR: {line}")


def _pipe_reader(prefix: str, pipe, verbose: bool = False):
    try:
        for line in iter(pipe.readline, b""):
            decoded = line.decode(errors="replace").rstrip()
            if prefix == "GSTERR" and len(decoded) > 0:
                _gst_stderr_buffer.append(decoded)
            if verbose:
                print(f"{prefix}: {decoded}")
    except Exception as exc:
        print(f"Error reading {prefix}: {exc}")
    finally:
        try:
            pipe.close()
        except Exception:
            pass


def start_clip_recording() -> Optional[subprocess.Popen]:
    global _record_process
    global _current_session_id
    global _last_record_error

    if sys.platform not in ("linux", "linux2"):
        print("GStreamer video recording is only supported on Linux")
        return None

    with _recording_lock:
        if _record_process is not None and _record_process.poll() is None:
            print("Clip recorder is already running")
            return _record_process

        ensure_clip_directory()

        device_port = camera_options.get("deviceport") or detect_video_device()
        if not device_port:
            print("No video device available")
            return None

        video_width = camera_options.get("video", {}).get("width", 1280)
        video_height = camera_options.get("video", {}).get("height", 720)
        video_framerate = camera_options.get("video", {}).get("framerate", 30)
        verbose = camera_options.get("verbose", False)
        verbose_flag = "-v " if verbose else ""

        _clear_gst_stderr_buffer()
        _last_record_error = ""
        _current_session_id = datetime.now(timezone.utc).strftime("clip-%Y%m%dT%H%M%SZ")
        output_pattern = clip_directory() / f"{_current_session_id}-%05d.mp4"
        clip_duration_ns = clip_options["duration_secs"] * 1_000_000_000

        gst_command = (
            f"gst-launch-1.0 -e {verbose_flag}"
            f"v4l2src device={device_port} do-timestamp=true ! "
            f"image/jpeg,width={video_width},height={video_height},framerate={video_framerate}/1 ! "
            "jpegdec ! "
            "videoconvert ! video/x-raw,format=I420 ! "
            f"x264enc bframes=0 key-int-max={video_framerate * 2} bitrate=2000 speed-preset=ultrafast tune=zerolatency ! "
            "h264parse config-interval=-1 ! "
            f"splitmuxsink async-finalize=true muxer-factory=mp4mux max-size-time={clip_duration_ns} "
            f"location=\"{output_pattern}\""
        )

        if verbose:
            print(f"GStreamer command:\n{gst_command}")

        try:
            _record_process = subprocess.Popen(
                gst_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
                text=False,
                env=_bundle_gst_env()
            )

            threading.Thread(
                target=_pipe_reader,
                args=("GSTOUT", _record_process.stdout, verbose),
                daemon=True
            ).start()
            threading.Thread(
                target=_pipe_reader,
                args=("GSTERR", _record_process.stderr, verbose),
                daemon=True
            ).start()

            time.sleep(2.0)

            return_code = _record_process.poll()
            if return_code is not None:
                _last_record_error = f"GStreamer exited immediately with code {return_code}"
                print(f"GStreamer exited immediately with code {return_code}")
                print("This usually means:")
                print("   - GStreamer is not installed")
                print("   - x264enc plugin is not installed")
                print("   - splitmuxsink/mp4mux plugin is not installed")
                print("   - Video device is not accessible")
                _print_recent_gst_stderr()
                _record_process = None
                _current_session_id = ""
                return None

            print(f"Clip recorder started successfully; creating {clip_options['duration_secs']}-second MP4 clips")
            return _record_process
        except FileNotFoundError:
            _last_record_error = "GStreamer is NOT installed on this system"
            print("GStreamer is NOT installed on this system")
            return None
        except Exception as exc:
            _last_record_error = f"Error starting clip recorder: {exc}"
            print(f"Error starting clip recorder: {exc}")
            _record_process = None
            _current_session_id = ""
            return None


def capture_picture_file() -> Optional[Path]:
    if sys.platform not in ("linux", "linux2"):
        print("GStreamer image capture is only supported on Linux")
        return None

    handle_recorder_exit_if_needed()
    if is_recording() or recording_requested():
        print("Stop MP4 recording before capturing a picture")
        return None

    ensure_clip_directory()

    device_port = camera_options.get("deviceport") or detect_video_device()
    if not device_port:
        print("No video device available")
        return None

    video_width = camera_options.get("video", {}).get("width", 1280)
    video_height = camera_options.get("video", {}).get("height", 720)
    video_framerate = camera_options.get("video", {}).get("framerate", 30)
    verbose = camera_options.get("verbose", False)
    verbose_flag = "-v " if verbose else ""

    picture_path = clip_directory() / (
        datetime.now(timezone.utc).strftime("picture-%Y%m%dT%H%M%S%fZ.jpg")
    )

    gst_command = (
        f"gst-launch-1.0 -e {verbose_flag}"
        f"v4l2src device={device_port} num-buffers=1 do-timestamp=true ! "
        f"image/jpeg,width={video_width},height={video_height},framerate={video_framerate}/1 ! "
        f"filesink location=\"{picture_path}\""
    )

    if verbose:
        print(f"GStreamer picture command:\n{gst_command}")

    _clear_gst_stderr_buffer()

    try:
        result = subprocess.run(
            gst_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            env=_bundle_gst_env(),
            timeout=15,
            check=False
        )
    except subprocess.TimeoutExpired:
        print("Timed out while capturing picture")
        return None
    except FileNotFoundError:
        print("GStreamer is NOT installed on this system")
        return None
    except Exception as exc:
        print(f"Error capturing picture: {exc}")
        return None

    _capture_recent_gst_stderr(result.stderr)

    if result.returncode != 0:
        print(f"Picture capture failed with code {result.returncode}")
        _print_recent_gst_stderr()
        return None

    try:
        if picture_path.stat().st_size <= 0:
            print("Picture capture produced an empty file")
            picture_path.unlink(missing_ok=True)
            return None
    except FileNotFoundError:
        print("Picture capture did not produce an output file")
        return None

    print(f"Captured picture: {picture_path.name}")
    return picture_path


def stop_clip_recording() -> bool:
    global _record_process

    if sys.platform not in ("linux", "linux2"):
        print("Stopping GStreamer is only supported on Linux")
        return False

    with _recording_lock:
        if _record_process is None:
            print("No clip recorder is running")
            return False

        process = _record_process
        _record_process = None

    try:
        print("Stopping clip recorder...")
        os.killpg(os.getpgid(process.pid), signal.SIGINT)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            process.wait(timeout=5)
        print("Clip recorder stopped")
        time.sleep(1.0)
        return True
    except ProcessLookupError:
        print("Clip recorder process already exited")
        return True
    except Exception as exc:
        print(f"Error stopping clip recorder: {exc}")
        return False


def is_recording() -> bool:
    global _record_process

    if _record_process is None:
        return False

    if _record_process.poll() is not None:
        _record_process = None
        return False

    return True


def recording_requested() -> bool:
    with _recording_lock:
        return _recording_requested


def _recording_request_snapshot() -> tuple[bool, int]:
    with _recording_lock:
        return _recording_requested, _record_request_version


def _set_recording_requested(requested: bool) -> int:
    global _recording_requested
    global _record_request_version
    with _recording_lock:
        _recording_requested = requested
        _record_request_version += 1
        return _record_request_version


def _clear_recording_request_if_version(expected_version: int) -> bool:
    global _recording_requested
    global _record_request_version
    with _recording_lock:
        if _record_request_version != expected_version or not _recording_requested:
            return False
        _recording_requested = False
        _record_request_version += 1
        return True


def session_id_for_media(media_path: Path) -> str:
    media_stem = media_path.stem
    if "-" not in media_stem:
        return ""
    return media_stem.rsplit("-", 1)[0]


def pending_media_files() -> list[Path]:
    if not clip_directory().exists():
        return []
    media_files = []
    for pattern in ("*.mp4", "*.jpg"):
        for media_path in clip_directory().glob(pattern):
            try:
                media_files.append((media_path.stat().st_mtime, media_path))
            except FileNotFoundError:
                continue
    media_files.sort(key=lambda item: item[0])
    return [item[1] for item in media_files]


def count_pending_clips() -> int:
    return len(pending_media_files())


def ready_media_files(flush_all: bool = False) -> list[Path]:
    media_files = pending_media_files()
    if not media_files:
        return []

    newest_video = None
    if is_recording() and not flush_all:
        for media_path in reversed(media_files):
            if media_path.suffix.lower() == ".mp4":
                newest_video = media_path
                break

    now = time.time()
    ready = []

    for media_path in media_files:
        if newest_video is not None and media_path == newest_video:
            continue

        try:
            clip_age = now - media_path.stat().st_mtime
        except FileNotFoundError:
            continue

        if not flush_all and clip_age < clip_options["min_file_age_secs"]:
            continue

        ready.append(media_path)

    return ready


def build_relative_upload_path(media_path: Path, upload_name: Optional[str] = None) -> str:
    media_time = datetime.fromtimestamp(media_path.stat().st_mtime, tz=timezone.utc)
    media_type_dir = "pictures" if media_path.suffix.lower() == ".jpg" else "clips"
    target_name = upload_name or media_path.name
    return f"{media_type_dir}/{media_time.strftime('%Y/%m/%d')}/{target_name}"


def handle_recorder_exit_if_needed():
    global _record_process
    global _recording_requested
    global _last_record_error
    global _current_session_id

    with _recording_lock:
        process = _record_process
        requested = _recording_requested

    if process is None:
        return False

    return_code = process.poll()
    if return_code is None:
        return False

    with _recording_lock:
        _record_process = None
        if requested:
            _recording_requested = False
            _last_record_error = (
                f"Clip recorder exited unexpectedly with code {return_code}. "
                "Recording has been disabled until record-start is requested again."
            )
        _current_session_id = ""

    if requested:
        print(_last_record_error)
        _print_recent_gst_stderr()

    return True


def media_custom_values(media_path: Path, media_size: int) -> dict:
    if media_path.suffix.lower() == ".jpg":
        return {
            "cf": {
                "type": "picture_capture",
                "size_bytes": media_size,
                "width": camera_options.get("video", {}).get("width", 1280),
                "height": camera_options.get("video", {}).get("height", 720),
                "capture_id": media_path.stem
            }
        }

    return {
        "cf": {
            "type": "video_clip",
            "duration_secs": clip_options["duration_secs"],
            "size_bytes": media_size,
            "session": session_id_for_media(media_path)
        }
    }


def create_clip_archive(clip_path: Path) -> Optional[Path]:
    archive_path = clip_path.with_name(f"{clip_path.name}.zip")

    try:
        archive_path.unlink(missing_ok=True)
        with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(clip_path, arcname=clip_path.name)
        if archive_path.stat().st_size <= 0:
            print(f"Clip archive is empty: {archive_path.name}")
            archive_path.unlink(missing_ok=True)
            return None
        return archive_path
    except Exception as exc:
        print(f"Failed to create clip archive {archive_path.name}: {exc}")
        try:
            archive_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def upload_pending_media(flush_all: bool = False):
    global _uploaded_clips
    global _upload_failures
    global _last_uploaded_clip

    with _upload_lock:
        if client is None or not client.is_connected():
            return

        for media_path in ready_media_files(flush_all=flush_all):
            try:
                media_size = media_path.stat().st_size
            except FileNotFoundError:
                continue

            if media_size <= 0:
                with _stats_lock:
                    _upload_failures += 1
                print(f"Skipping empty media artifact: {media_path.name}")
                try:
                    media_path.unlink(missing_ok=True)
                except Exception as exc:
                    print(f"Unable to remove empty media artifact {media_path.name}: {exc}")
                continue

            custom_values = media_custom_values(media_path, media_size)
            upload_path = media_path
            relative_path = build_relative_upload_path(media_path)
            remove_upload_artifact = False

            if media_path.suffix.lower() == ".mp4":
                archive_path = create_clip_archive(media_path)
                if archive_path is None:
                    with _stats_lock:
                        _upload_failures += 1
                    break
                upload_path = archive_path
                relative_path = build_relative_upload_path(media_path, upload_name=archive_path.name)
                custom_values["cf"]["archive_format"] = "zip"
                custom_values["cf"]["original_name"] = media_path.name
                remove_upload_artifact = True

            try:
                print(f"Uploading media to S3: {upload_path.name}")
                client.s3_upload(
                    local_path=str(upload_path),
                    custom_values=custom_values,
                    relative_upload_path=relative_path
                )

                if clip_options["delete_after_upload"] and media_path.exists():
                    media_path.unlink()
                if remove_upload_artifact and upload_path.exists():
                    upload_path.unlink()

                with _stats_lock:
                    _uploaded_clips += 1
                    _last_uploaded_clip = relative_path

                print(f"Uploaded media successfully: {relative_path}")
            except FileNotFoundError:
                print(f"Media disappeared before upload completed: {upload_path.name}")
                if remove_upload_artifact and upload_path.exists():
                    upload_path.unlink(missing_ok=True)
                continue
            except Exception as exc:
                with _stats_lock:
                    _upload_failures += 1
                print(f"Failed to upload {upload_path.name}: {exc}")
                if remove_upload_artifact and upload_path.exists():
                    upload_path.unlink(missing_ok=True)
                break


def upload_worker():
    print("Clip upload worker started")
    while not _uploader_stop_event.is_set():
        try:
            upload_pending_media(flush_all=False)
        except Exception as exc:
            print(f"Unexpected upload worker error: {exc}")
        _uploader_stop_event.wait(clip_options["scan_interval_secs"])

    try:
        upload_pending_media(flush_all=True)
    except Exception as exc:
        print(f"Upload worker flush failed: {exc}")

    print("Clip upload worker stopped")


def ensure_upload_worker_started():
    global _uploader_thread

    if _uploader_thread is not None and _uploader_thread.is_alive():
        return

    _uploader_stop_event.clear()
    _uploader_thread = threading.Thread(target=upload_worker, daemon=True)
    _uploader_thread.start()


def stop_upload_worker():
    global _uploader_thread

    _uploader_stop_event.set()
    if _uploader_thread is not None:
        _uploader_thread.join(timeout=10)
        _uploader_thread = None


def start_recording_if_requested() -> bool:
    global _last_record_error

    if client is None:
        return False

    if client.get_s3_client() is None:
        print("S3 support is not available for this device template")
        return False

    requested, request_version = _recording_request_snapshot()
    if not requested:
        return False

    handle_recorder_exit_if_needed()
    requested, current_version = _recording_request_snapshot()
    if not requested or current_version != request_version:
        return False

    if is_recording():
        return True

    process = start_clip_recording()
    if process is None:
        _clear_recording_request_if_version(request_version)
        if len(_last_record_error) == 0:
            _last_record_error = "Unable to start MP4 clip recording"
        return False

    requested, current_version = _recording_request_snapshot()
    if not requested or current_version != request_version:
        print("Start request was superseded before recorder stabilized; stopping clip recorder.")
        stop_clip_recording()
        return False

    return True


def request_recording_start() -> bool:
    global _last_record_error

    _set_recording_requested(True)
    _last_record_error = ""
    return start_recording_if_requested()


def request_recording_stop() -> bool:
    _set_recording_requested(False)
    handle_recorder_exit_if_needed()

    if is_recording():
        if not stop_clip_recording():
            return False
    else:
        print("Clip recorder already stopped")

    upload_pending_media(flush_all=True)
    return True


def request_picture_capture() -> bool:
    picture_path = capture_picture_file()
    if picture_path is None:
        return False

    expected_relative_path = build_relative_upload_path(picture_path)
    upload_pending_media(flush_all=True)

    with _stats_lock:
        last_uploaded_path = _last_uploaded_clip

    return last_uploaded_path == expected_relative_path


def on_generic_message(msg: C2dMessage, raw_message: dict):
    message_name = C2dMessage.TYPES.get(msg.type, f"type {msg.type}")
    print(f"Received generic message {message_name}: {raw_message}")

    if msg.type == C2dMessage.START_STREAM:
        request_recording_start()
        return

    if msg.type == C2dMessage.STOP_STREAM:
        request_recording_stop()
        return


def telemetry_snapshot() -> dict:
    handle_recorder_exit_if_needed()
    with _stats_lock:
        telemetry = {
            "recording": is_recording(),
            "pending_uploads": count_pending_clips(),
            "uploaded_clips": _uploaded_clips,
            "upload_failures": _upload_failures,
            "last_clip": _last_uploaded_clip
        }
    return telemetry


def handle_file_download(msg: C2dCommand):
    if len(msg.command_args) != 1:
        client.send_command_ack(msg, C2dAck.CMD_FAILED, "Expected 1 argument")
        print("Expected 1 command argument, but got", len(msg.command_args))
        return

    status_message = "Downloading %s to device" % msg.command_args[0]
    try:
        response = requests.get(msg.command_args[0], stream=True, timeout=60)
        response.raise_for_status()

        with open("package.tar.gz", "wb") as file_handle:
            for chunk in response.iter_content(chunk_size=8192):
                file_handle.write(chunk)

        print("File downloaded successfully and saved to package.tar.gz")
        client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, status_message)
        print(status_message)
        extract_and_run_tar_gz("package.tar.gz")
        print("Download command successful. Will restart the application...")
        print("")
        sys.stdout.flush()
        os.execv(sys.executable, [sys.executable, __file__] + sys.argv[1:])
    except Exception as exc:
        error_message = f"Failed to download package: {exc}"
        print(error_message)
        client.send_command_ack(msg, C2dAck.CMD_FAILED, error_message)


def on_command(msg: C2dCommand):
    print("Received command", msg.command_name, msg.command_args, msg.ack_id)

    if msg.command_name == "file-download":
        handle_file_download(msg)
        return

    if msg.command_name == "record-start":
        if request_recording_start():
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "MP4 clip recording started")
        else:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Unable to start MP4 clip recording")
        return

    if msg.command_name == "record-stop":
        if request_recording_stop():
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "MP4 clip recording stopped")
        else:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Unable to stop MP4 clip recording")
        return

    if msg.command_name in ("capture-picture", "record-picture"):
        if request_picture_capture():
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_SUCCESS_WITH_ACK, "Picture captured and uploaded")
        else:
            if msg.ack_id is not None:
                client.send_command_ack(msg, C2dAck.CMD_FAILED, "Unable to capture picture")
        return

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
        except Exception as exc:
            print("Encountered download error", exc)
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
        print("Encountered a download processing error. Not restarting.")


def on_disconnect(reason: str, disconnected_from_server: bool):
    print(f"Disconnected. Reason: {reason}")
    handle_recorder_exit_if_needed()
    if is_recording():
        print("Stopping clip recorder due to disconnect...")
        stop_clip_recording()


if __name__ == "__main__":
    try:
        device_config = DeviceConfig.from_iotc_device_config_json_file(
            device_config_json_path="iotcDeviceConfig.json",
            device_cert_path="device-cert.pem",
            device_pkey_path="device-pkey.pem"
        )
    except DeviceConfigError as exc:
        print(f"Configuration error: {exc}")
        sys.exit(1)

    callbacks = Callbacks(
        command_cb=on_command,
        ota_cb=on_ota,
        disconnected_cb=on_disconnect,
        generic_message_callbacks={
            C2dMessage.START_STREAM: on_generic_message,
            C2dMessage.STOP_STREAM: on_generic_message
        }
    )

    try:
        client = Client(device_config, callbacks)
    except Exception as exc:
        print(f"Failed to create client: {exc}")
        sys.exit(1)

    ensure_upload_worker_started()

    print("Connecting to /IOTCONNECT...")
    client.connect()

    if not client.is_connected():
        print("Failed to connect")
        stop_upload_worker()
        sys.exit(1)

    s3_client = client.get_s3_client()
    if s3_client is None:
        print("S3 file support is NOT enabled for this device template")
        stop_upload_worker()
        sys.exit(1)

    print("Connected to /IOTCONNECT")
    print("\nS3 file upload support is ENABLED")
    print(f"Clip length: {clip_options['duration_secs']} seconds")
    print(f"Clip directory: {clip_directory()}")
    print(f"Available buckets: {[bucket.bucket_name for bucket in s3_client.get_buckets()]}")

    print("\n" + "=" * 50)
    print("Capturing pictures or fixed-length MP4 clips and uploading them to S3")
    if app_options["auto_start_recording"]:
        request_recording_start()
        print("Auto-start recording is enabled")
    else:
        print("Auto-start recording is disabled")
        print("Use capture-picture for still images or record-start for video")
    print("Send command record-start to start recording")
    print("Send command record-stop to stop recording")
    print("Send command capture-picture to capture and upload one JPEG")
    print("Press Ctrl+C to exit")
    print("=" * 50 + "\n")

    try:
        while True:
            handle_recorder_exit_if_needed()

            if not client.is_connected():
                print("Connection lost, attempting to reconnect...")
                client.connect()
                if client.is_connected():
                    start_recording_if_requested()
            else:
                start_recording_if_requested()

            client.send_telemetry(telemetry_snapshot())
            time.sleep(10)

    except KeyboardInterrupt:
        print("\nShutting down...")
        if is_recording():
            stop_clip_recording()
        upload_pending_media(flush_all=True)
        stop_upload_worker()
        client.disconnect()
        print("Shutdown successful.")
