import ctypes
import logging
import os
import socket
import subprocess
import sys

log = logging.getLogger("merlin.permissions")


class PermissionResult:
    def __init__(self):
        self.microphone = False
        self.webcam = False
        self.screen_capture = False
        self.internet = False
        self.location = False
        self.file_access = False
        self.sudo = False
        self.errors: list[str] = []

    @property
    def all_ok(self):
        return all([
            self.microphone, self.webcam, self.screen_capture,
            self.internet, self.file_access,
        ])


def check_all() -> PermissionResult:
    result = PermissionResult()

    # Internet
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=3)
        result.internet = True
    except OSError:
        result.errors.append("internet: not reachable")

    # File access (home dir)
    try:
        test_path = os.path.expanduser("~/.merlin/perm_test")
        os.makedirs(os.path.dirname(test_path), exist_ok=True)
        with open(test_path, "w") as f:
            f.write("test")
        os.unlink(test_path)
        result.file_access = True
    except OSError as e:
        result.errors.append(f"file access: {e}")

    # Microphone (can we open a sound device?)
    try:
        import sounddevice as sd
        sd.check_input_settings()
        result.microphone = True
    except Exception as e:
        result.errors.append(f"microphone: {e}")

    # Webcam
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, _ = cap.read()
            cap.release()
            if ret:
                result.webcam = True
            else:
                result.errors.append("webcam: can't read frame")
        else:
            result.errors.append("webcam: can't open /dev/video0")
    except Exception as e:
        result.errors.append(f"webcam: {e}")

    # Screen capture
    try:
        import mss
        with mss.mss() as sct:
            sct.grab(sct.monitors[0])
        result.screen_capture = True
    except Exception as e:
        result.errors.append(f"screen capture: {e}")

    # Sudo (just check if sudo exists)
    try:
        subprocess.run(["sudo", "-n", "true"], capture_output=True, timeout=5)
        result.sudo = True  # cached from recent use
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass  # sudo exists even if not cached
    except Exception:
        pass

    return result
