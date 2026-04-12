"""
JARVIS Terminal Test Mode
=========================
Type commands directly — no mic, no TTS, no API quota used.
Tests every agent exactly as jarvis.py would route them.

Usage:
    cd D:/JARVIS
    .\\venv\\Scripts\\activate
    python test_jarvis.py
"""

import sys, os, time, threading
sys.path.insert(0, r"D:\JARVIS")
os.chdir(r"D:\JARVIS")
from dotenv import load_dotenv
load_dotenv(r"D:\JARVIS\.env")

# ── Colours ────────────────────────────────────────────────────────
G  = "\033[92m"
Y  = "\033[93m"
R  = "\033[91m"
B  = "\033[94m"
C  = "\033[96m"
W  = "\033[97m"
DIM= "\033[2m"
RST= "\033[0m"

def pr(label, text, color=W):
    print(f"{color}[{label:8s}]{RST} {text}")

print(f"""
{B}╔══════════════════════════════════════════════════╗
║       JARVIS Terminal Test Mode  v2              ║
║  No mic · No TTS · No quota used                 ║
║  Type a command and press Enter                  ║
║  Type  :help  for special commands               ║
║  Type  :quit  to exit                            ║
╚══════════════════════════════════════════════════╝{RST}
""")

# ── Load agent router ─────────────────────────────────────────────
try:
    from agent_router import route
    pr("Boot", "agent_router loaded OK", G)
except Exception as e:
    pr("Boot", f"agent_router FAILED: {e}", R)
    sys.exit(1)

# ── Load LLM ──────────────────────────────────────────────────────
try:
    from llm import chat, chat_raw
    pr("Boot", "llm.py loaded OK", G)
except Exception as e:
    pr("Boot", f"llm.py FAILED: {e}", R)

# ── Import checks ─────────────────────────────────────────────────
AGENTS = [
    ("iot_agent",        "from iot_agent import handle as iot_handle"),
    ("sensor_agent",     "from sensor_agent import get_readings, start as sensor_start, handle as sensor_handle"),
    ("timer_agent",      "from timer_agent import handle as timer_handle"),
    ("gmail_agent",      "from gmail_agent import handle as gmail_handle"),
    ("finance_agent",    "from finance_agent import handle as finance_handle"),
    ("search_agent",     "from search_agent import handle as search_handle"),
    ("calendar_agent",   "from calendar_agent import handle as cal_handle"),
    ("memory_agent",     "from memory_agent import on_session_start"),
    ("contacts_manager", "from contacts_manager import list_contacts"),
    ("email_sender",     "from email_sender import handle as mail_handle"),
    ("coding_agent",     "from coding_agent import run as coding_run"),
    ("flight_agent",     "from flight_agent import handle as flight_handle"),
    ("zepto_agent",      "from zepto_agent import handle as zepto_handle"),
]

print()
pr("Agents", "Checking imports...", Y)
for name, imp in AGENTS:
    try:
        exec(imp)
        pr("  OK  ", name, G)
    except Exception as e:
        pr(" FAIL ", f"{name}: {e}", R)

# ── MQTT check ────────────────────────────────────────────────────
print()
pr("MQTT", "Testing broker...", Y)
try:
    import paho.mqtt.client as mqtt
    c = mqtt.Client(client_id="jarvis_test_probe")
    c.connect("localhost", 1883, 5)
    c.disconnect()
    pr("MQTT", "Mosquitto reachable on localhost:1883", G)
except Exception as e:
    pr("MQTT", f"FAILED: {e} — run: net start mosquitto", R)

# ── Sensor: start agent + wait for live reading ───────────────────
print()
pr("Sensor", "Starting MQTT listener and waiting for ESP32...", Y)
try:
    from sensor_agent import start as sensor_start, get_temperature, get_readings
    from iot_agent import start as iot_start, set_notify as iot_set_notify

    # Wire a simple printer as notify
    def _test_notify(msg): pr("Notify", msg, C)
    iot_set_notify(_test_notify)
    iot_start()

    sensor_start()

    # Poll up to 12s for first reading
    for i in range(24):
        time.sleep(0.5)
        t = get_temperature()
        if t is not None:
            r = get_readings()
            pr("Sensor", f"temperature={t}°C  humidity={r['humidity']}%  flame={r['flame']}", G)
            pr("Sensor", "ESP32 data received ✓", G)
            break
    else:
        pr("Sensor", "No data in 12s — ESP32 may be offline or firmware needs boot-publish fix", Y)
        r = get_readings()
        pr("Sensor", f"readings: {r}", DIM)
except Exception as e:
    pr("Sensor", f"Error: {e}", R)

# ── Finance: quick yfinance smoke test ───────────────────────────
print()
pr("Finance", "Testing yfinance (Nifty 50)...", Y)
try:
    from finance_agent import _fetch_yf
    d = _fetch_yf("^NSEI")
    if d and d.get("price"):
        pr("Finance", f"Nifty 50 = ₹{d['price']:,.2f}  ({d['change_pct']:+.2f}%)", G)
    else:
        pr("Finance", "No data returned — market may be closed or yfinance offline", Y)
except Exception as e:
    pr("Finance", f"Error: {e} — run: pip install yfinance", R)

# ── Help text ─────────────────────────────────────────────────────
HELP_TEXT = f"""
{C}Special commands:{RST}
  {Y}:sensor{RST}              — print live DHT11 + flame readings
  {Y}:sensor wait{RST}         — wait up to 12s for fresh ESP32 reading
  {Y}:iot <cmd>{RST}           — publish MQTT command
                       cmds: on | off | tea | alert | all off
  {Y}:mqtt{RST}                — test Mosquitto broker connection
  {Y}:llm <prompt>{RST}        — send prompt directly to LLM
  {Y}:search <query>{RST}      — run web search
  {Y}:finance <name>{RST}      — fetch stock/crypto price (e.g. :finance reliance)
  {Y}:history{RST}             — show conversation history
  {Y}:clear{RST}               — clear conversation history
  {Y}:agents{RST}              — re-run agent import checks
  {Y}:quit{RST}                — exit

{C}Example queries to test agents:{RST}
  "what's the temperature"       → sensor
  "turn on the lights"           → iot
  "price of Reliance"            → finance
  "set a timer for 5 minutes"    → timer
  "check my email"               → gmail
  "search for latest AI news"    → search
  "write a python function"      → coding
  "good morning jarvis"          → briefing
"""


# ── Special command handler ───────────────────────────────────────
def run_special(cmd: str):
    parts = cmd.strip().split(None, 1)
    base  = parts[0].lower()
    arg   = parts[1].strip() if len(parts) > 1 else ""

    if base == ":help":
        print(HELP_TEXT)

    elif base == ":quit":
        pr("Bye", "Exiting test mode", Y)
        sys.exit(0)

    elif base == ":sensor":
        if arg == "wait":
            pr("Sensor", "Waiting up to 12s for fresh reading...", Y)
            for i in range(24):
                time.sleep(0.5)
                t = get_temperature()
                elapsed = f"{(i+1)*0.5:.1f}s"
                if t is not None:
                    r = get_readings()
                    pr("Sensor", f"[{elapsed}] temperature={t}°C  humidity={r['humidity']}%  flame={r['flame']}", G)
                    break
                else:
                    print(f"  {DIM}{elapsed}: waiting...{RST}", end="\r")
            else:
                pr("Sensor", "No data in 12s — ESP32 offline?", R)
        else:
            try:
                r = get_readings()
                pr("Sensor", f"temperature={r['temperature']}°C  humidity={r['humidity']}%  flame={r['flame']}", W)
            except Exception as e:
                pr("Sensor", f"Error: {e}", R)

    elif base == ":iot":
        try:
            import paho.mqtt.client as mqtt
            c = mqtt.Client(client_id="jarvis_test_iot")
            c.connect("localhost", 1883, 5)
            topic_map = {
                "on":      ("jarvis/lights", "on"),
                "off":     ("jarvis/lights", "off"),
                "tea":     ("jarvis/tea",    "on"),
                "alert":   ("jarvis/alert",  "blink"),
                "all off": ("jarvis/all",    "off"),
            }
            key = arg.lower()
            if key in topic_map:
                topic, msg = topic_map[key]
                c.publish(topic, msg)
                time.sleep(0.2)
                c.disconnect()
                pr("IoT", f"Published '{msg}' → '{topic}'", G)
            else:
                pr("IoT", f"Unknown: '{arg}'. Options: on | off | tea | alert | all off", Y)
        except Exception as e:
            pr("IoT", f"MQTT error: {e}", R)

    elif base == ":mqtt":
        try:
            import paho.mqtt.client as mqtt
            c = mqtt.Client(client_id="jarvis_test_mqtt")
            c.connect("localhost", 1883, 5)
            c.disconnect()
            pr("MQTT", "Broker OK on localhost:1883", G)
        except Exception as e:
            pr("MQTT", f"FAILED: {e}", R)

    elif base == ":llm":
        if not arg:
            pr("LLM", "Usage: :llm <your prompt>", Y); return
        try:
            resp = chat_raw(arg)
            pr("LLM", resp, W)
        except Exception as e:
            pr("LLM", f"Error: {e}", R)

    elif base == ":search":
        if not arg:
            pr("Search", "Usage: :search <query>", Y); return
        try:
            from search_agent import handle as search_handle
            result = search_handle(arg)
            pr("Search", result[:600] if result else "No results", W)
        except Exception as e:
            pr("Search", f"Error: {e}", R)

    elif base == ":finance":
        if not arg:
            pr("Finance", "Usage: :finance <name>  e.g. :finance reliance", Y); return
        try:
            from finance_agent import handle as finance_handle
            result = finance_handle(arg)
            pr("Finance", result, W)
        except Exception as e:
            pr("Finance", f"Error: {e}", R)

    elif base == ":history":
        if not history[1:]:
            pr("History", "(empty)", DIM); return
        for m in history[1:]:
            role  = m["role"].upper()
            color = G if role == "ASSISTANT" else Y
            pr(role[:8], m["content"][:120], color)

    elif base == ":clear":
        history.clear()
        history.append({"role": "system", "content": "You are JARVIS. Be brief and address user as sir."})
        pr("History", "Cleared", G)

    elif base == ":agents":
        print()
        pr("Agents", "Re-checking imports...", Y)
        for name, imp in AGENTS:
            try:
                exec(imp)
                pr("  OK  ", name, G)
            except Exception as e:
                pr(" FAIL ", f"{name}: {e}", R)

    else:
        pr("?", f"Unknown command '{base}'. Type :help", Y)


# ── Main conversation loop ─────────────────────────────────────────
history = [{"role": "system", "content": "You are JARVIS. Be brief and address user as sir."}]

print(f"\n{G}Ready. Type your command (or :help):{RST}\n")

while True:
    try:
        user_input = input(f"{Y}You > {RST}").strip()
    except (EOFError, KeyboardInterrupt):
        pr("Bye", "Exiting", Y)
        break

    if not user_input:
        continue

    if user_input.startswith(":"):
        run_special(user_input)
        print()
        continue

    history.append({"role": "user", "content": user_input})
    print(f"{DIM}Routing...{RST}")

    try:
        intent, response = route(user_input, history)
        pr("Intent", intent, B)

        if response:
            pr("JARVIS", response, G)
            history.append({"role": "assistant", "content": response})
        else:
            pr("JARVIS", "(agent returned empty — it may have spoken via TTS or needs input)", Y)

    except Exception as e:
        pr("ERROR", str(e), R)
        import traceback; traceback.print_exc()

    print()