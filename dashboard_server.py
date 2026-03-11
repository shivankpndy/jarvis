"""
JARVIS Dashboard WebSocket Server
"""
import asyncio
import websockets
import json
import threading
import datetime

_clients      = set()
_loop         = None
_led_state    = {"green": False, "white": False, "red": False}
_is_awake     = False
_is_listening = False
_camera_state = {"active": False, "motionEvents": 0}
_stats        = {"total_calls": 0, "motion_events": 0, "emails_read": 0, "slack_dms": 0}
_agents       = [
    {"name": "Brain",    "sub": "llama3.2:3b",      "status": "idle",   "calls": 0},
    {"name": "Coder",    "sub": "qwen2.5-coder:3b", "status": "idle",   "calls": 0},
    {"name": "IoT",      "sub": "MQTT",             "status": "active", "calls": 0},
    {"name": "Gmail",    "sub": "IMAP",             "status": "active", "calls": 0},
    {"name": "Slack",    "sub": "API",              "status": "active", "calls": 0},
    {"name": "Telegram", "sub": "MTProto",          "status": "active", "calls": 0},
    {"name": "Memory",   "sub": "JSON + Ollama",    "status": "idle",   "calls": 0},
    {"name": "Search",   "sub": "DuckDuckGo",       "status": "idle",   "calls": 0},
    {"name": "Camera",   "sub": "MOG2 / OpenCV",    "status": "idle",   "calls": 0},
    {"name": "Sensor",   "sub": "DHT11 + Flame",    "status": "active", "calls": 0},
]


def _broadcast(msg: dict):
    if not _clients or not _loop:
        return
    data = json.dumps(msg)
    asyncio.run_coroutine_threadsafe(_broadcast_async(data), _loop)


async def _broadcast_async(data: str):
    dead = set()
    for ws in _clients:
        try:
            await ws.send(data)
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)


# ── Public API ────────────────────────────────────────────────────
def notify_listening(active: bool):
    global _is_listening
    _is_listening = active
    _broadcast({"type": "listening", "active": active})


def notify_awake(active: bool):
    global _is_awake
    _is_awake = active
    _broadcast({"type": "awake", "active": active})


def notify_command(text: str):
    _stats["total_calls"] += 1
    _broadcast({"type": "command", "text": text})


def notify_response(text: str):
    _broadcast({"type": "response", "text": text})


def notify_led(led: str, state: bool):
    _led_state[led] = state
    _broadcast({"type": "leds", "data": dict(_led_state)})


def notify_activity(notif_type: str, msg: str):
    _broadcast({"type": "activity", "data": {
        "time": datetime.datetime.now().strftime("%H:%M"),
        "type": notif_type,
        "msg":  msg,
    }})


def notify_camera(active: bool):
    """Called when camera starts or stops."""
    global _camera_state
    _camera_state["active"] = active
    # Update camera agent status in agents list
    for a in _agents:
        if a["name"] == "Camera":
            a["status"] = "active" if active else "idle"
            break
    _broadcast({"type": "camera", "data": dict(_camera_state)})
    _broadcast({"type": "agents", "data": _agents})


def notify_motion():
    """Called on every motion detection event."""
    global _camera_state
    _camera_state["motionEvents"] += 1
    _stats["motion_events"]       += 1
    # Update camera agent call count
    for a in _agents:
        if a["name"] == "Camera":
            a["calls"] += 1
            break
    _broadcast({"type": "camera", "data": dict(_camera_state)})
    _broadcast({"type": "stats",  "data": dict(_stats)})
    notify_activity("Camera", f"Motion detected — snapshot saved")


def _full_state():
    return {
        "type":      "init",
        "leds":      dict(_led_state),
        "awake":     _is_awake,
        "listening": _is_listening,
        "agents":    _agents,
        "stats":     dict(_stats),
        "mqtt":      {"connected": True, "broker": "localhost:1883"},
        "esp32":     {"connected": True, "ip":     "192.168.1.8"},
        "camera":    dict(_camera_state),
    }


async def handler(websocket):
    _clients.add(websocket)
    print(f"Dashboard: client connected ({len(_clients)} total)")
    try:
        await websocket.send(json.dumps(_full_state()))
        async for message in websocket:
            try:
                msg = json.loads(message)
                if msg.get("type") == "led_toggle":
                    led   = msg.get("led")
                    state = msg.get("state")
                    if led in _led_state:
                        _led_state[led] = state
                        try:
                            from iot_agent import publish
                            topics = {
                                "green": "jarvis/tea",
                                "white": "jarvis/lights",
                                "red":   "jarvis/alert"
                            }
                            if led in topics:
                                val = "on" if state else "off"
                                if led == "red" and state:
                                    val = "blink"
                                publish(topics[led], val)
                        except Exception as e:
                            print(f"Dashboard LED toggle error: {e}")
            except Exception:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        _clients.discard(websocket)
        print(f"Dashboard: client disconnected ({len(_clients)} total)")


async def _serve():
    async with websockets.serve(handler, "localhost", 8765):
        print("Dashboard WebSocket running on ws://localhost:8765")
        await asyncio.Future()


def start():
    global _loop
    def _run():
        global _loop
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
        _loop.run_until_complete(_serve())
    threading.Thread(target=_run, daemon=True).start()