"""
JARVIS MQTT Diagnostic
Run this while ESP32 is powered on.
It listens to ALL jarvis/* topics and prints exactly what arrives.

Usage:
    cd D:\JARVIS
    .\venv\Scripts\activate
    python debug_mqtt.py
"""
import time
import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT   = 1883

print("=" * 55)
print("  JARVIS MQTT Diagnostic")
print("=" * 55)

received = []

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[OK] Connected to Mosquitto on {BROKER}:{PORT}")
        client.subscribe("jarvis/#")   # subscribe to ALL jarvis/* topics
        print("[OK] Subscribed to jarvis/# — waiting for ESP32 messages...")
        print("     (ESP32 publishes every 10 seconds)")
        print("-" * 55)
    else:
        codes = {
            1: "wrong protocol version",
            2: "client ID rejected",
            3: "broker unavailable",
            4: "bad username/password",
            5: "not authorised",
        }
        print(f"[FAIL] Connection refused — {codes.get(rc, f'rc={rc}')}")
        print("       Is Mosquitto running? Try: net start mosquitto")

def on_disconnect(client, userdata, rc):
    print(f"[WARN] Disconnected from broker (rc={rc})")

def on_message(client, userdata, msg):
    topic   = msg.topic
    payload = msg.payload.decode("utf-8", errors="ignore").strip()
    ts      = time.strftime("%H:%M:%S")
    print(f"[{ts}] {topic:30s} = '{payload}'")
    received.append(topic)

client = mqtt.Client(client_id="jarvis_debug")
client.on_connect    = on_connect
client.on_disconnect = on_disconnect
client.on_message    = on_message

try:
    client.connect(BROKER, PORT, keepalive=60)
except Exception as e:
    print(f"[FAIL] Cannot connect to Mosquitto: {e}")
    print()
    print("Fix options:")
    print("  1. Start Mosquitto:  net start mosquitto")
    print("  2. Or run manually:  mosquitto -v")
    print("  3. Check port 1883 is free: netstat -ano | findstr 1883")
    exit(1)

print("\nListening... Press Ctrl+C to stop and see summary.\n")

try:
    client.loop_start()
    start = time.time()
    while True:
        elapsed = time.time() - start
        if elapsed > 30 and not received:
            print("\n[WARN] No messages received in 30 seconds.")
            print("       Possible causes:")
            print("       1. ESP32 not connected to WiFi")
            print("       2. ESP32 MQTT_SERVER in firmware is wrong IP")
            print(f"          Should be your PC IP — check with: ipconfig")
            print("       3. ESP32 and PC on different networks/VLANs")
            print("       4. Firewall blocking port 1883")
            print("\n       While waiting, publishing a test message...")
            client.publish("jarvis/test", "ping")
            print("       Published jarvis/test = 'ping' — did you see it above?")
            start = time.time() + 999  # stop warning
        time.sleep(1)

except KeyboardInterrupt:
    print("\n" + "=" * 55)
    print(f"  Summary: received {len(received)} message(s)")
    if received:
        from collections import Counter
        for topic, count in Counter(received).most_common():
            print(f"    {topic}: {count}x")
        if "jarvis/temperature" in received:
            print("\n  [OK] DHT11 data is reaching Python correctly!")
            print("       The sensor_agent.py should work.")
        else:
            print("\n  [WARN] No temperature messages received.")
            print("         ESP32 may be publishing to wrong broker IP.")
    else:
        print("  [FAIL] No messages at all — ESP32 not reaching Mosquitto")
    client.loop_stop()
    client.disconnect()