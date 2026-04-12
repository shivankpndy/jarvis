import paho.mqtt.client as mqtt
import time
import threading
import schedule

MQTT_BROKER = "localhost"
MQTT_PORT   = 1883

# Use unique client ID so it never clashes with sensor_agent
client      = mqtt.Client(client_id="jarvis_iot_py", clean_session=True)
_connected  = False
_notify_fn  = None
_notif_lock = threading.Lock()


def set_notify(fn):
    global _notify_fn
    _notify_fn = fn


def _speak_once(text):
    with _notif_lock:
        if _notify_fn:
            _notify_fn(text)


def connect():
    global _connected
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        _connected = True
        print("[IoT] Connected to MQTT broker")
    except Exception as e:
        print(f"[IoT] MQTT connection failed: {e}")
        _connected = False


# ── Tea Scheduler ─────────────────────────────────────────────────
def morning_tea():
    print("[IoT] Morning tea time!")
    publish("jarvis/tea", "on")
    _speak_once("Good morning sir. It is time for your morning tea.")


def evening_tea():
    print("[IoT] Evening tea time!")
    publish("jarvis/tea", "on")
    _speak_once("Good evening sir. It is time for your evening tea.")


def start_tea_scheduler():
    schedule.every().day.at("08:00").do(morning_tea)
    schedule.every().day.at("17:00").do(evening_tea)

    def _run():
        print("[IoT] Tea scheduler running — 6AM and 5PM")
        while True:
            schedule.run_pending()
            time.sleep(30)

    threading.Thread(target=_run, daemon=True, name="tea_scheduler").start()


def publish(topic, message):
    try:
        client.publish(topic, message)
        print(f"[IoT] '{message}' → '{topic}'")
        return True
    except Exception as e:
        print(f"[IoT] Publish error: {e}")
        return False


# ── Voice Command Handler ─────────────────────────────────────────
def handle(user_text: str) -> str:
    text = user_text.lower()

    if any(k in text for k in ["turn on the lights", "turn on the light",
                                "lights on", "light on", "room lights on",
                                "room light on", "switch on the light",
                                "switch on the lights", "white led on"]):
        publish("jarvis/lights", "on")
        return "Room lights on sir."

    if any(k in text for k in ["turn off the lights", "turn off the light",
                                "lights off", "light off", "room lights off",
                                "room light off", "switch off the light",
                                "switch off the lights", "white led off"]):
        publish("jarvis/lights", "off")
        return "Room lights off sir."

    if any(k in text for k in ["make tea", "tea time", "brew tea",
                                "start tea", "prepare tea", "chai",
                                "green led on"]):
        publish("jarvis/tea", "on")
        return "Tea reminder on sir. Green LED will turn off in 30 seconds."

    if any(k in text for k in ["tea off", "green led off", "cancel tea"]):
        publish("jarvis/tea", "off")
        return "Tea reminder off sir."

    if any(k in text for k in ["trigger alert", "alert on", "red alert",
                                "intruder", "red led"]):
        if any(k in text for k in ["off", "clear", "cancel", "stop"]):
            return "Alert already off sir, red LED only blinks."
        publish("jarvis/alert", "blink")
        return "Alert triggered sir. Red LED is blinking."

    if any(k in text for k in ["all off", "everything off",
                                "turn off everything", "all lights off"]):
        publish("jarvis/all", "off")
        return "All LEDs off sir."

    return ""


def trigger_alert(alert_type="blink"):
    """Called externally by camera/sensor agents."""
    publish("jarvis/alert", "blink")
    _speak_once("Sir, movement detected. Intruder alert.")


# ── start() called explicitly by jarvis.py — NOT at import time ──
def start():
    connect()
    start_tea_scheduler()
    print("[IoT] IoT agent ready")


# NOTE: No connect() or start_tea_scheduler() call here at module level.
# jarvis.py calls iot_agent.start() explicitly after all agents are set up.