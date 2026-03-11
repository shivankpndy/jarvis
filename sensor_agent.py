"""
JARVIS Sensor Agent
Subscribes to MQTT sensor topics from ESP32-CAM.
Handles: DHT11 temperature/humidity + flame detection alerts.
"""
import threading
import paho.mqtt.client as mqtt_client

BROKER    = "localhost"
PORT      = 1883
_notify   = None
_speak    = None
_iot_trigger = None  # for red LED blink on flame

# Live sensor readings
_readings = {
    "temperature": None,
    "humidity":    None,
    "flame":       False,
}

_lock = threading.Lock()

# Temperature alert threshold
TEMP_ALERT_C = 40.0   # alert if room goes above 40°C


def set_notify(fn):
    global _notify
    _notify = fn


def set_speak(fn):
    global _speak
    _speak = fn


def set_iot_trigger(fn):
    global _iot_trigger
    _iot_trigger = fn


def get_temperature() -> float | None:
    with _lock:
        return _readings["temperature"]


def get_humidity() -> float | None:
    with _lock:
        return _readings["humidity"]


def get_readings() -> dict:
    with _lock:
        return dict(_readings)


def _alert(text: str):
    if _notify:
        _notify(text)
    else:
        print(f"[Sensor] {text}")


# ── MQTT handlers ──────────────────────────────────────────────────
def _on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[Sensor] MQTT connected")
        client.subscribe("jarvis/temperature")
        client.subscribe("jarvis/humidity")
        client.subscribe("jarvis/flame")
    else:
        print(f"[Sensor] MQTT connect failed rc={rc}")


def _on_message(client, userdata, msg):
    topic   = msg.topic
    payload = msg.payload.decode("utf-8", errors="ignore").strip()

    if topic == "jarvis/temperature":
        try:
            temp = float(payload)
            with _lock:
                _readings["temperature"] = temp
            print(f"[Sensor] Temperature: {temp}°C")
            # High temp alert
            if temp >= TEMP_ALERT_C:
                _alert(
                    f"Sir, room temperature has reached {temp:.0f} degrees celsius. "
                    f"Please check the room."
                )
        except ValueError:
            pass

    elif topic == "jarvis/humidity":
        try:
            hum = float(payload)
            with _lock:
                _readings["humidity"] = hum
            print(f"[Sensor] Humidity: {hum}%")
        except ValueError:
            pass

    elif topic == "jarvis/flame":
        if payload == "detected":
            with _lock:
                _readings["flame"] = True
            print("[Sensor] ⚠ FLAME DETECTED")
            # Blink red LED
            if _iot_trigger:
                threading.Thread(target=_iot_trigger, daemon=True).start()
            # Voice alert
            _alert(
                "Sir, FLAME DETECTED in the room! "
                "Possible fire. Please check immediately!"
            )
        elif payload == "clear":
            with _lock:
                _readings["flame"] = False
            print("[Sensor] Flame cleared")
            _alert("Sir, flame sensor is now clear. Room appears safe.")


def start():
    client = mqtt_client.Client(client_id="jarvis_sensor_py")
    client.on_connect = _on_connect
    client.on_message = _on_message

    def _run():
        try:
            client.connect(BROKER, PORT, keepalive=60)
            client.loop_forever()
        except Exception as e:
            print(f"[Sensor] MQTT error: {e}")

    threading.Thread(target=_run, daemon=True).start()
    print("[Sensor] Sensor agent started")


# ── Voice command handler ──────────────────────────────────────────
def handle(user_text: str) -> str:
    t = user_text.lower()
    readings = get_readings()

    if any(k in t for k in ["temperature", "how hot", "room temp", "how warm", "degrees"]):
        temp = readings["temperature"]
        hum  = readings["humidity"]
        if temp is None:
            return (
                "I don't have a temperature reading yet sir. "
                "Please ensure the DHT11 sensor is connected and ESP32 is online."
            )
        reply = f"The room temperature is {temp:.1f} degrees celsius"
        if hum is not None:
            reply += f" with a humidity of {hum:.0f} percent"
        reply += " sir."
        # Add comfort note
        if temp > 35:
            reply += " It's quite hot in there sir."
        elif temp < 18:
            reply += " It's rather cold sir."
        else:
            reply += " Comfortable conditions sir."
        return reply

    if any(k in t for k in ["humidity", "moisture", "how humid"]):
        hum = readings["humidity"]
        if hum is None:
            return "No humidity reading available yet sir."
        return f"Room humidity is {hum:.0f} percent sir."

    if any(k in t for k in ["flame", "fire", "smoke"]):
        flame = readings["flame"]
        return (
            "Sir, the flame sensor is currently detecting fire. Please check immediately!"
            if flame else
            "No flame detected sir. The room appears safe."
        )

    return ""