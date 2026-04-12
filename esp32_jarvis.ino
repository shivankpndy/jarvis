/*
 * JARVIS ESP32-CAM Firmware — BROWNOUT FIX EDITION
 * ===================================================
 *
 * BROWNOUT FIX: Top of setup() disables brownout detector and reduces WiFi
 * TX power. This is the #1 cause of ESP32-CAM resets when powered from Arduino.
 *
 * WIRING:
 *   GPIO12 → 220Ω → Green LED  (Tea — auto-off after 30s)
 *   GPIO2  → 220Ω → White LED  (Room lights — stays on)
 *   GPIO13 → 220Ω → Red LED    (Alert — blinks, always ends LOW)
 *   GPIO14 → DHT11 DATA        (10kΩ pull-up to 3.3V between DATA and VCC)
 *   GPIO15 → Flame sensor DO   (LOW = flame detected)
 *
 *   POWER: ESP32-CAM from phone charger/power bank (NOT Arduino 5V)
 *   Arduino: RESET shorted to GND (USB-Serial bridge only)
 *   ESP32 GPIO1(TX) → Arduino RX(0)
 *   ESP32 GPIO3(RX) → Arduino TX(1)
 *
 * MQTT TOPICS (subscribe):
 *   jarvis/lights  → "on" / "off"
 *   jarvis/tea     → "on" / "off"
 *   jarvis/alert   → "blink" / "off"
 *   jarvis/all     → "off"
 *
 * MQTT TOPICS (publish):
 *   jarvis/temperature  → "28.3"
 *   jarvis/humidity     → "60.0"
 *   jarvis/flame        → "detected" / "clear"
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include "soc/soc.h"           // brownout fix
#include "soc/rtc_cntl_reg.h"  // brownout fix
#include "esp_system.h"        // esp_wifi_set_max_tx_power

// ── WiFi ──────────────────────────────────────────────────────────
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ── MQTT ──────────────────────────────────────────────────────────
const char* MQTT_SERVER   = "192.168.1.5";  // your PC IP
const int   MQTT_PORT     = 1883;
const char* MQTT_CLIENT   = "jarvis_esp32";

// ── Pins ──────────────────────────────────────────────────────────
#define PIN_GREEN  12   // Tea LED
#define PIN_WHITE   2   // Room lights LED
#define PIN_RED    13   // Alert LED
#define PIN_DHT    14   // DHT11 data
#define PIN_FLAME  15   // Flame sensor DO (LOW = fire)

// ── DHT11 ─────────────────────────────────────────────────────────
DHT dht(PIN_DHT, DHT11);

// ── State ─────────────────────────────────────────────────────────
bool  lightsOn        = false;
bool  teaOn           = false;
unsigned long teaStartMs  = 0;
const unsigned long TEA_MS = 30UL * 1000UL;   // 30 seconds

bool  alertBlink      = false;
unsigned long alertStartMs   = 0;
unsigned long alertToggleMs  = 0;
const unsigned long ALERT_TOTAL_MS  = 10UL * 1000UL;  // blink 10s total
const unsigned long ALERT_TOGGLE_MS = 300UL;           // toggle every 300ms

bool  lastFlame       = false;
unsigned long lastSensorMs = 0;
const unsigned long SENSOR_MS = 10UL * 1000UL;  // publish every 10s

WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);


// ── MQTT callback ─────────────────────────────────────────────────
void mqttCallback(char* topic, byte* payload, unsigned int len) {
  String msg = "";
  for (unsigned int i = 0; i < len; i++) msg += (char)payload[i];
  msg.trim();
  msg.toLowerCase();
  String t = String(topic);

  Serial.printf("[MQTT] %s → %s\n", topic, msg.c_str());

  // Each topic has its own isolated handler with return
  if (t == "jarvis/lights") {
    if (msg == "on")  { lightsOn = true;  digitalWrite(PIN_WHITE, HIGH); Serial.println("[LED] White ON"); }
    if (msg == "off") { lightsOn = false; digitalWrite(PIN_WHITE, LOW);  Serial.println("[LED] White OFF"); }
    return;
  }

  if (t == "jarvis/tea") {
    if (msg == "on")  { teaOn = true; teaStartMs = millis(); digitalWrite(PIN_GREEN, HIGH); Serial.println("[LED] Green ON (30s)"); }
    if (msg == "off") { teaOn = false; digitalWrite(PIN_GREEN, LOW); Serial.println("[LED] Green OFF"); }
    return;
  }

  if (t == "jarvis/alert") {
    if (msg == "blink") {
      alertBlink    = true;
      alertStartMs  = millis();
      alertToggleMs = millis();
      Serial.println("[LED] Red BLINK start");
    }
    if (msg == "off") {
      alertBlink = false;
      digitalWrite(PIN_RED, LOW);
      Serial.println("[LED] Red OFF");
    }
    return;
  }

  if (t == "jarvis/all") {
    if (msg == "off") {
      lightsOn   = false; teaOn = false; alertBlink = false;
      digitalWrite(PIN_WHITE, LOW);
      digitalWrite(PIN_GREEN, LOW);
      digitalWrite(PIN_RED,   LOW);
      Serial.println("[LED] ALL OFF");
    }
    return;
  }
}


// ── WiFi ──────────────────────────────────────────────────────────
void connectWifi() {
  Serial.printf("Connecting WiFi: %s\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int t = 0;
  while (WiFi.status() != WL_CONNECTED && t < 30) {
    delay(500); Serial.print("."); t++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nWiFi OK. IP: %s\n", WiFi.localIP().toString().c_str());
    // Reduce TX power to prevent brownout from WiFi spikes
    esp_wifi_set_max_tx_power(40);  // 10 dBm (default is 80 = 20 dBm)
    Serial.println("WiFi TX power reduced (brownout prevention)");
  } else {
    Serial.println("\nWiFi failed — rebooting");
    delay(1000);
    ESP.restart();
  }
}


// ── MQTT ──────────────────────────────────────────────────────────
void connectMqtt() {
  while (!mqtt.connected()) {
    Serial.printf("Connecting MQTT %s:%d ...\n", MQTT_SERVER, MQTT_PORT);
    if (mqtt.connect(MQTT_CLIENT)) {
      Serial.println("MQTT connected");
      mqtt.subscribe("jarvis/lights");
      mqtt.subscribe("jarvis/tea");
      mqtt.subscribe("jarvis/alert");
      mqtt.subscribe("jarvis/all");
      Serial.println("Subscribed to all jarvis/* topics");
    } else {
      Serial.printf("MQTT failed rc=%d — retry 3s\n", mqtt.state());
      delay(3000);
    }
  }
}


// ── setup ─────────────────────────────────────────────────────────
void setup() {
  // ── BROWNOUT FIX — MUST BE FIRST ──────────────────────────────
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);  // disable brownout detector
  // ──────────────────────────────────────────────────────────────

  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== JARVIS ESP32 starting ===");

  // All LEDs off
  pinMode(PIN_GREEN, OUTPUT); digitalWrite(PIN_GREEN, LOW);
  pinMode(PIN_WHITE, OUTPUT); digitalWrite(PIN_WHITE, LOW);
  pinMode(PIN_RED,   OUTPUT); digitalWrite(PIN_RED,   LOW);
  pinMode(PIN_FLAME, INPUT);

  dht.begin();
  connectWifi();

  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  connectMqtt();

  // Self-test: flash each LED once to confirm wiring
  Serial.println("Self-test...");
  digitalWrite(PIN_GREEN, HIGH); delay(200); digitalWrite(PIN_GREEN, LOW); delay(100);
  digitalWrite(PIN_WHITE, HIGH); delay(200); digitalWrite(PIN_WHITE, LOW); delay(100);
  digitalWrite(PIN_RED,   HIGH); delay(200); digitalWrite(PIN_RED,   LOW);
  Serial.println("JARVIS ESP32 ready.");
}


// ── loop ──────────────────────────────────────────────────────────
void loop() {
  if (!mqtt.connected()) connectMqtt();
  mqtt.loop();

  unsigned long now = millis();

  // Tea auto-off
  if (teaOn && (now - teaStartMs >= TEA_MS)) {
    teaOn = false;
    digitalWrite(PIN_GREEN, LOW);
    Serial.println("[LED] Green auto-off");
  }

  // Alert blink
  if (alertBlink) {
    if (now - alertStartMs >= ALERT_TOTAL_MS) {
      alertBlink = false;
      digitalWrite(PIN_RED, LOW);
      Serial.println("[LED] Red blink ended — OFF");
    } else if (now - alertToggleMs >= ALERT_TOGGLE_MS) {
      alertToggleMs = now;
      digitalWrite(PIN_RED, !digitalRead(PIN_RED));
    }
  }

  // Sensor publish every 10s
  if (now - lastSensorMs >= SENSOR_MS) {
    lastSensorMs = now;

    float temp = dht.readTemperature();
    float hum  = dht.readHumidity();
    if (!isnan(temp) && !isnan(hum)) {
      char buf[16];
      snprintf(buf, sizeof(buf), "%.1f", temp);
      mqtt.publish("jarvis/temperature", buf);
      snprintf(buf, sizeof(buf), "%.1f", hum);
      mqtt.publish("jarvis/humidity", buf);
      Serial.printf("[DHT] %.1f°C  %.0f%%\n", temp, hum);
    } else {
      Serial.println("[DHT] Read failed");
    }

    // Flame sensor (LOW = fire)
    bool flame = (digitalRead(PIN_FLAME) == LOW);
    if (flame != lastFlame) {
      lastFlame = flame;
      mqtt.publish("jarvis/flame", flame ? "detected" : "clear");
      Serial.printf("[Flame] %s\n", flame ? "DETECTED!" : "clear");
    }
  }
}
