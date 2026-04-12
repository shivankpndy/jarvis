"""
JARVIS Camera Agent — Human-Only Detection via HOG Person Descriptor
- Uses OpenCV's built-in HOG + SVM pedestrian detector (no model download needed)
- Only alerts when an actual HUMAN is detected in frame
- Black frame / covered camera → silently skipped, no false alerts
- Night mode: voice alerts only between 9PM–9AM
- Daytime: silent snapshot only
"""
import cv2, time, threading, datetime, os
import numpy as np

CAMERA_INDEX     = 0
ALERT_COOLDOWN   = 30        # seconds between voice alerts
SNAPSHOT_DIR     = r"D:\JARVIS\snapshots"

# Process every Nth frame to reduce CPU load
PROCESS_EVERY_N  = 5
RESOLUTION       = (640, 480)

# Night watch hours: alert between 9PM (21) and 9AM (9)
NIGHT_START_H    = 21
NIGHT_END_H      = 9

# HOG detection tuning
# winStride: smaller = more accurate but slower. (8,8) is good balance.
# scale: lower = detects more (slower). 1.05 catches small/partial humans.
# hitThreshold: higher = fewer false positives. 0 = most sensitive.
HOG_WIN_STRIDE   = (8, 8)
HOG_PADDING      = (4, 4)
HOG_SCALE        = 1.05
HOG_HIT_THRESH   = 0.0       # raised internally per environment

# Minimum bounding box area to count as a real person (filters tiny ghosts)
MIN_PERSON_AREA  = 4000      # width*height pixels in RESIZED (320x240) frame

# Minimum average brightness — below this = covered/dark room
MIN_BRIGHTNESS   = 15

_notify_fn       = None
_speak_fn        = None
_iot_trigger_fn  = None
_dashboard_fn    = None
_camera_notify   = None
_running         = False
_last_alert_time = 0
_thread          = None
_motion_count    = 0


def set_notify(fn):           global _notify_fn;      _notify_fn      = fn
def set_speak(fn):            global _speak_fn;       _speak_fn       = fn
def set_iot_trigger(fn):      global _iot_trigger_fn; _iot_trigger_fn = fn
def set_dashboard_motion(fn): global _dashboard_fn;   _dashboard_fn   = fn
def set_dashboard_camera(fn): global _camera_notify;  _camera_notify  = fn

def get_motion_count(): return _motion_count
def is_running():       return _running


def _is_night_watch_time() -> bool:
    h = datetime.datetime.now().hour
    return h >= NIGHT_START_H or h < NIGHT_END_H


def _save_snapshot(frame) -> str:
    try:
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        ts       = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(SNAPSHOT_DIR, f"human_{ts}.jpg")
        cv2.imwrite(filepath, frame)
        print(f"[Camera] Snapshot → {filepath}")
        return filepath
    except Exception as e:
        print(f"[Camera] Snapshot error: {e}")
        return ""


def _is_black_frame(frame) -> bool:
    """True if frame is too dark — lens cap / no light / covered camera."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return gray.mean() < MIN_BRIGHTNESS


def _alert(frame):
    global _last_alert_time, _motion_count
    now = time.time()
    if now - _last_alert_time < ALERT_COOLDOWN:
        return
    _last_alert_time = now
    _motion_count   += 1

    ts_str = datetime.datetime.now().strftime("%I:%M %p")
    print(f"[Camera] HUMAN DETECTED #{_motion_count} at {ts_str}")

    _save_snapshot(frame)

    if _iot_trigger_fn:
        threading.Thread(target=_iot_trigger_fn, args=("intruder",), daemon=True).start()

    if _dashboard_fn:
        try: _dashboard_fn()
        except Exception: pass

    if _is_night_watch_time():
        msg = f"Sir, a person has been detected at {ts_str}. Possible intruder. Snapshot saved."
        if _notify_fn: _notify_fn(msg)
    else:
        print(f"[Camera] Daytime human detected — snapshot saved (silent mode)")


def _camera_loop():
    global _running

    # ── Init HOG person detector (built into OpenCV — no download) ───────────
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
    print("[Camera] HOG person detector loaded ✓")

    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[Camera] Cannot open camera index {CAMERA_INDEX}")
        _running = False
        if _camera_notify:
            try: _camera_notify(False)
            except Exception: pass
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  RESOLUTION[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, RESOLUTION[1])
    cap.set(cv2.CAP_PROP_FPS, 15)

    frame_count = 0
    black_count = 0

    if _camera_notify:
        try: _camera_notify(True)
        except Exception: pass

    print(f"[Camera] Started on index {CAMERA_INDEX} — warming up 3s...")
    warmup = time.time()
    while time.time() - warmup < 3.0:
        cap.read()
    print("[Camera] Ready — watching for humans only")

    while _running:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.5)
            continue

        # ── Black frame / covered camera guard ───────────────────────────────
        if _is_black_frame(frame):
            black_count += 1
            if black_count == 5:
                print("[Camera] Black frames — camera covered or dark room. Detection paused.")
            time.sleep(0.5)
            continue
        else:
            if black_count >= 5:
                print("[Camera] Light restored — resuming human detection.")
            black_count = 0

        frame_count += 1
        if frame_count % PROCESS_EVERY_N != 0:
            continue

        # ── HOG detection on small frame for speed ───────────────────────────
        # Resize to 320x240 — enough for HOG, much faster than 640x480
        small = cv2.resize(frame, (320, 240))

        # Convert to grayscale — HOG works on grayscale
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)

        # Run HOG detector
        # Returns list of (x, y, w, h) bounding boxes for detected people
        rects, weights = hog.detectMultiScale(
            gray,
            winStride   = HOG_WIN_STRIDE,
            padding     = HOG_PADDING,
            scale       = HOG_SCALE,
            hitThreshold= HOG_HIT_THRESH,
        )

        # ── Filter by minimum bounding box area ──────────────────────────────
        # Tiny rects are HOG noise / partial detections
        humans_found = False
        if len(rects) > 0:
            for (x, y, w, h) in rects:
                area = w * h
                if area >= MIN_PERSON_AREA:
                    humans_found = True
                    # Draw box on FULL frame for snapshot
                    # Scale coords back up (frame is 640x480, detection on 320x240)
                    fx, fy, fw, fh = x*2, y*2, w*2, h*2
                    cv2.rectangle(frame, (fx, fy), (fx+fw, fy+fh), (0, 255, 0), 2)
                    break   # one confirmed human is enough to trigger alert

        if humans_found:
            _alert(frame)

        time.sleep(0.02)

    cap.release()
    print("[Camera] Stopped")
    if _camera_notify:
        try: _camera_notify(False)
        except Exception: pass


def start() -> bool:
    global _running, _thread
    if _running: return True
    os.environ.setdefault("OPENCV_LOG_LEVEL", "SILENT")
    cap = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_DSHOW)
    ok  = cap.isOpened(); cap.release()
    if not ok:
        print(f"[Camera] Index {CAMERA_INDEX} not available")
        return False
    _running = True
    _thread  = threading.Thread(target=_camera_loop, daemon=True)
    _thread.start()
    return True


def stop():
    global _running
    _running = False


def handle(user_text: str) -> str:
    t = user_text.lower()
    if any(k in t for k in ["start camera", "enable camera", "camera on",
                              "start monitoring", "security on",
                              "activate camera", "turn on camera"]):
        if _running: return "Camera is already running sir."
        ok = start()
        return ("Camera activated sir. I will alert you when a person is detected, "
                "with voice alerts between 9PM and 9AM.") if ok else \
               "Could not open camera sir. Check USB connection."

    if any(k in t for k in ["stop camera", "disable camera", "camera off",
                              "stop monitoring", "security off",
                              "turn off camera"]):
        if not _running: return "Camera is not running sir."
        stop()
        return "Camera monitoring deactivated sir."

    if any(k in t for k in ["camera status", "is camera on",
                              "camera running", "camera active"]):
        if _running:
            mode = "night watch active" if _is_night_watch_time() else "daytime silent mode"
            return (f"Camera is running sir. {_motion_count} person detection"
                    f"{'s' if _motion_count != 1 else ''} this session. Currently {mode}.")
        return "Camera is off sir. Say start camera to activate."

    return ""