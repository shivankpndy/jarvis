"""
JARVIS Camera Agent — OpenCV MOG2 motion detection
"""
import cv2
import time
import threading
import datetime
import os

CAMERA_INDEX     = 1        # 1 = external USB webcam, 0 = built-in
MIN_CONTOUR_AREA = 4000     # lower = more sensitive
ALERT_COOLDOWN   = 20       # seconds between alerts
SNAPSHOT_DIR     = r"D:\JARVIS\snapshots"
PROCESS_EVERY_N  = 3        # process every 3rd frame
RESOLUTION       = (640, 480)

_notify_fn       = None
_iot_trigger_fn  = None
_dashboard_fn    = None     # notify_motion from dashboard_server
_camera_notify   = None     # notify_camera from dashboard_server
_running         = False
_last_alert_time = 0
_thread          = None
_motion_count    = 0


def set_notify(fn):
    global _notify_fn
    _notify_fn = fn


def set_iot_trigger(fn):
    global _iot_trigger_fn
    _iot_trigger_fn = fn


def set_dashboard_motion(fn):
    """Pass dashboard_server.notify_motion here."""
    global _dashboard_fn
    _dashboard_fn = fn


def set_dashboard_camera(fn):
    """Pass dashboard_server.notify_camera here."""
    global _camera_notify
    _camera_notify = fn


def get_motion_count() -> int:
    return _motion_count


def is_running() -> bool:
    return _running


def _save_snapshot(frame) -> str:
    try:
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(SNAPSHOT_DIR, f"motion_{ts}.jpg")
        cv2.imwrite(filepath, frame)
        print(f"[Camera] Snapshot → {filepath}")
        return filepath
    except Exception as e:
        print(f"[Camera] Snapshot error: {e}")
        return ""


def _alert(frame):
    global _last_alert_time, _motion_count
    now = time.time()
    if now - _last_alert_time < ALERT_COOLDOWN:
        return
    _last_alert_time = now
    _motion_count   += 1

    print(f"[Camera] MOTION DETECTED — event #{_motion_count}")

    # Save snapshot
    _save_snapshot(frame)

    # Blink red LED
    if _iot_trigger_fn:
        threading.Thread(
            target=_iot_trigger_fn,
            args=("intruder",),
            daemon=True
        ).start()

    # Update dashboard
    if _dashboard_fn:
        try: _dashboard_fn()
        except Exception: pass

    # Voice alert — this is what triggers JARVIS to speak
    if _notify_fn:
        ts = datetime.datetime.now().strftime("%I:%M %p")
        _notify_fn(
            f"Motion detected at {ts} Shivank. "
            f"Possible intruder. Snapshot saved."
        )


def _camera_loop():
    global _running

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"[Camera] Cannot open camera index {CAMERA_INDEX}")
        _running = False
        if _notify_fn:
            _notify_fn(
                f"Could not open camera Shivank. "
                f"Try changing CAMERA_INDEX in camera_agent.py"
            )
        if _camera_notify:
            try: _camera_notify(False)
            except Exception: pass
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  RESOLUTION[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION[1])
    cap.set(cv2.CAP_PROP_FPS, 15)

    bg     = cv2.createBackgroundSubtractorMOG2(
        history=500, varThreshold=50, detectShadows=False
    )
    kernel      = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    frame_count = 0

    # Notify dashboard camera is active
    if _camera_notify:
        try: _camera_notify(True)
        except Exception: pass

    print(f"[Camera] Started on index {CAMERA_INDEX} — warming up...")

    # Warm up background model
    warmup = time.time()
    while time.time() - warmup < 2.0:
        cap.read()

    print("[Camera] Ready — watching for motion")

    # Speak ready message
    if _notify_fn:
        _notify_fn(
            "Camera monitoring activated Shivank. "
            "I will alert you if I detect any movement."
        )

    while _running:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.5)
            continue

        frame_count += 1
        if frame_count % PROCESS_EVERY_N != 0:
            continue

        small   = cv2.resize(frame, (320, 240))
        fg_mask = bg.apply(small)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN,  kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
        fg_mask = cv2.dilate(fg_mask, kernel, iterations=2)

        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for contour in contours:
            area = cv2.contourArea(contour) * 4
            if area > MIN_CONTOUR_AREA:
                print(f"[Camera] Motion area={area:.0f}")
                _alert(frame)
                break

        time.sleep(0.02)

    cap.release()
    print("[Camera] Stopped")

    # Notify dashboard camera is off
    if _camera_notify:
        try: _camera_notify(False)
        except Exception: pass

    if _notify_fn:
        _notify_fn("Camera monitoring deactivated Shivank.")


def start() -> bool:
    """Start motion detection. Returns True if camera opened OK, False if not available."""
    global _running, _thread
    if _running:
        return True

    # Quick check — can we open the camera at all?
    import cv2
    cap = cv2.VideoCapture(CAMERA_INDEX)
    ok  = cap.isOpened()
    cap.release()
    if not ok:
        print(f"[Camera] Index {CAMERA_INDEX} not available — not starting")
        return False

    _running = True
    _thread  = threading.Thread(target=_camera_loop, daemon=True)
    _thread.start()
    print(f"[Camera] Started on index {CAMERA_INDEX}")
    return True


def stop():
    global _running
    _running = False


def handle(user_text: str) -> str:
    text = user_text.lower()

    if any(k in text for k in [
        "start camera", "enable camera", "camera on",
        "start monitoring", "security on", "watch for intruder",
        "activate camera", "turn on camera",
    ]):
        if _running:
            return "Camera is already running Shivank."
        start()
        return ""   # camera_loop speaks via notify_fn when ready

    if any(k in text for k in [
        "stop camera", "disable camera", "camera off",
        "stop monitoring", "security off",
        "deactivate camera", "turn off camera",
    ]):
        if not _running:
            return "Camera is not running Shivank."
        stop()
        return ""   # camera_loop speaks via notify_fn when stopped

    if any(k in text for k in [
        "camera status", "is camera on",
        "camera running", "camera active",
    ]):
        if _running:
            return (
                f"Camera is active Shivank. "
                f"{_motion_count} motion event"
                f"{'s' if _motion_count != 1 else ''} detected this session."
            )
        return "Camera is off Shivank. Say start camera to activate it."

    return ""