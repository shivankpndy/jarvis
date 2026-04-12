"""
JARVIS Sensor Agent
Subscribes to MQTT topics from ESP32-CAM.
DHT11: temperature + humidity
Flame sensor: detected / clear

Sensor data is stored silently — NO console spam.
Only printed/spoken when Jarvis is asked directly.
"""
import threading, time
import paho.mqtt.client as mqtt_client

BROKER         = "localhost"
PORT           = 1883
TEMP_ALERT_C   = 40.0

_notify      = None
_speak_fn    = None
_iot_trigger = None

_readings = {
    "temperature": None,
    "humidity":    None,
    "flame":       None,
}
_esp32_online   = False
_lock           = threading.Lock()
_started        = False   # guard against calling start() twice

# ── Flame alert debounce — only alert once per flame event ────────
_flame_alert_sent    = False   # True after alert sent, reset when flame clears
_last_flame_detected = False   # previous flame state

# ── Module-level persistent client ───────────────────────────────
# Unique ID per run — rc=7 ("Not Authorized / ID in use") happens when a
# previous crashed session is still registered on the broker.
import random as _random
_client = mqtt_client.Client(
    client_id=f"jarvis_sensor_{_random.randint(10000, 99999)}",
    clean_session=True,
)


def set_notify(fn):       global _notify;      _notify      = fn
def set_speak(fn):        global _speak_fn;    _speak_fn    = fn
def set_iot_trigger(fn):  global _iot_trigger; _iot_trigger = fn

def _alert(text: str):
    if _notify: _notify(text)

def get_temperature():
    with _lock: return _readings["temperature"]

def get_humidity():
    with _lock: return _readings["humidity"]

def get_readings():
    with _lock: return dict(_readings)

def is_esp32_online():
    with _lock: return _esp32_online


# ── MQTT callbacks ────────────────────────────────────────────────
def _on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[Sensor] MQTT connected ✓")
        for topic in ["jarvis/temperature", "jarvis/humidity",
                      "jarvis/flame", "jarvis/flame_status", "jarvis/dht_error"]:
            client.subscribe(topic)
    else:
        print(f"[Sensor] MQTT connect failed rc={rc}")


def _on_disconnect(client, userdata, rc):
    print(f"[Sensor] MQTT disconnected rc={rc} — will auto-reconnect")


def _on_message(client, userdata, msg):
    global _esp32_online, _flame_alert_sent, _last_flame_detected
    topic   = msg.topic
    payload = msg.payload.decode("utf-8", errors="ignore").strip()

    with _lock:
        _esp32_online = True

    # ── Temperature ───────────────────────────────────────────────
    if topic == "jarvis/temperature":
        try:
            temp = float(payload)
            with _lock:
                _readings["temperature"] = temp
            # SILENT — no print. Only alert on dangerous temp.
            if temp >= TEMP_ALERT_C:
                _alert(f"Sir, room temperature has reached {temp:.0f}°C. Please check the room.")
        except ValueError:
            pass

    # ── Humidity ──────────────────────────────────────────────────
    elif topic == "jarvis/humidity":
        try:
            with _lock:
                _readings["humidity"] = float(payload)
            # SILENT — no print.
        except ValueError:
            pass

    # ── DHT error ─────────────────────────────────────────────────
    elif topic == "jarvis/dht_error":
        # Only print once per session, not every poll
        with _lock:
            already = _esp32_online
        if not already:
            print("[Sensor] ⚠ DHT11 read failed on ESP32 — check GPIO14 wiring")
        with _lock:
            _esp32_online = True

    # ── Flame ─────────────────────────────────────────────────────
    elif topic in ("jarvis/flame", "jarvis/flame_status"):
        detected = (payload.lower() == "detected")
        with _lock:
            prev                    = _last_flame_detected
            _readings["flame"]      = detected
            _last_flame_detected    = detected

        if detected and not prev:
            # NEW flame event — alert once
            _flame_alert_sent = True
            print("[Sensor] ⚠ FLAME DETECTED")
            if _iot_trigger:
                threading.Thread(target=_iot_trigger, daemon=True).start()
            _alert("Sir, FLAME DETECTED! Possible fire — please check immediately!")
        elif not detected and prev:
            # Flame just cleared — reset silently, no print/alert
            _flame_alert_sent = False
        # If state unchanged → do nothing (no "Flame cleared" spam)


# ── Voice handler ─────────────────────────────────────────────────
def handle(user_text: str) -> str:
    t        = user_text.lower()
    readings = get_readings()
    online   = is_esp32_online()

    offline_msg = " Note: ESP32 appears offline." if not online else ""

    if any(k in t for k in ["temperature", "how hot", "room temp", "how warm",
                              "degrees", "warm in here", "cold in here", "temp"]):
        temp = readings["temperature"]
        hum  = readings["humidity"]
        if temp is None:
            return (
                "I don't have a temperature reading yet sir. "
                "Ensure DHT11 is on GPIO14 and ESP32 is powered."
            )
        reply = f"The room temperature is {temp:.1f} degrees celsius"
        if hum is not None:
            reply += f", humidity {hum:.0f} percent"
        reply += " sir."
        if   temp > 35: reply += " It's quite hot sir."
        elif temp < 18: reply += " It's rather cold sir."
        else:           reply += " Comfortable conditions sir."
        return reply + offline_msg

    if any(k in t for k in ["humidity", "moisture", "how humid"]):
        hum = readings["humidity"]
        if hum is None:
            return "No humidity reading yet sir." + offline_msg
        comfort = " That's quite humid sir." if hum > 70 else " Air is dry sir." if hum < 30 else ""
        return f"Room humidity is {hum:.0f} percent sir.{comfort}{offline_msg}"

    if any(k in t for k in ["flame", "fire", "smoke", "burning",
                              "is there fire", "any fire", "flame sensor"]):
        flame = readings["flame"]
        if flame is None:
            return "Flame sensor hasn't reported yet sir." + offline_msg
        if flame:
            return "Sir, the flame sensor is ACTIVE — fire detected! Check immediately!"
        return "No flame detected sir. Room appears safe." + offline_msg

    if any(k in t for k in ["sensor", "all sensors", "sensor reading"]):
        temp  = readings["temperature"]
        hum   = readings["humidity"]
        flame = readings["flame"]
        parts = [
            f"Temperature: {temp:.1f}°C" if temp is not None else "Temperature: no reading",
            f"Humidity: {hum:.0f}%"      if hum  is not None else "Humidity: no reading",
            ("Flame: DETECTED ⚠" if flame is True else
             "Flame: clear"      if flame is False else "Flame: no reading"),
        ]
        return "Sensor readings — " + ", ".join(parts) + "." + offline_msg

    return ""


# ── Start (safe to call multiple times) ──────────────────────────
def start():
    global _started
    if _started:
        print("[Sensor] Already started — skipping")
        return

    _started = True
    _client.on_connect    = _on_connect
    _client.on_disconnect = _on_disconnect
    _client.on_message    = _on_message
    _client.reconnect_delay_set(min_delay=1, max_delay=10)

    def _run():
        while True:
            try:
                print(f"[Sensor] Connecting to MQTT {BROKER}:{PORT}...")
                _client.connect(BROKER, PORT, keepalive=60)
                _client.loop_forever()
            except Exception as e:
                print(f"[Sensor] MQTT error: {e} — retrying in 5s")
                time.sleep(5)

    threading.Thread(target=_run, daemon=True, name="sensor_mqtt").start()
    print("[Sensor] Sensor agent started — silent mode (ask Jarvis for readings)")