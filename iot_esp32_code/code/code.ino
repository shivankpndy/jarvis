/*
 * JARVIS — Stage 3: Complete Firmware
 * LEDs + DHT11 + Flame Sensor
 * 
 * GPIO12 → Green LED    (Tea — 30s auto-off)
 * GPIO2  → White LED    (Lights — stays ON)
 * GPIO13 → Red LED      (Alert — blink only)
 * GPIO14 → DHT11 DATA   (Temperature + Humidity)
 * GPIO15 → Flame Sensor DO (LOW = flame detected)
 * 
 * Flame sensor wiring:
 *   VCC → ESP32 3.3V
 *   GND → GND rail
 *   DO  → GPIO15
 *   AO  → nothing
 * 
 * Libraries needed:
 *   - PubSubClient       by Nick O'Leary
 *   - DHT sensor library by Adafruit
 *   - Adafruit Unified Sensor by Adafruit
 * 
 * Board: AI Thinker ESP32-CAM
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

// ── WiFi ──────────────────────────────────────────────────────────
const char* WIFI_SSID = "WIFI_PASSWORD";
const char* WIFI_PASS = "PASSWORD";

// ── MQTT ──────────────────────────────────────────────────────────
const char* MQTT_BROKER = "192.168.1.5";
const int   MQTT_PORT   = 1883;
const char* MQTT_ID     = "jarvis_esp32";

// ── Pins ──────────────────────────────────────────────────────────
#define LED_GREEN   12
#define LED_WHITE    2
#define LED_RED     13
#define DHT_PIN     14
#define DHT_TYPE    DHT11
#define FLAME_PIN   15

// ── Objects ───────────────────────────────────────────────────────
DHT          dht(DHT_PIN, DHT_TYPE);
WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);

// ── State ─────────────────────────────────────────────────────────
bool          greenActive   = false;
unsigned long greenOnTime   = 0;
unsigned long lastDHTRead   = 0;
unsigned long lastFlameCheck= 0;
bool          lastFlameState= false;

const unsigned long DHT_INTERVAL   = 10000;  // 10 seconds
const unsigned long FLAME_INTERVAL =  1000;  //  1 second


// ── MQTT callback ─────────────────────────────────────────────────
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String msg = "";
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  msg.trim();
  msg.toLowerCase();
  String t = String(topic);

  Serial.printf("[MQTT] %s -> %s\n", topic, msg.c_str());

  // Green LED — Tea
  if (t == "jarvis/tea") {
    if (msg == "on") {
      digitalWrite(LED_GREEN, HIGH);
      greenActive = true;
      greenOnTime = millis();
      mqtt.publish("jarvis/status", "tea_on");
      Serial.println("Tea started — auto-off in 30s");
    } else {
      digitalWrite(LED_GREEN, LOW);
      greenActive = false;
      mqtt.publish("jarvis/status", "tea_off");
    }
  }

  // White LED — Lights
  if (t == "jarvis/lights") {
    if (msg == "on") {
      digitalWrite(LED_WHITE, HIGH);
      mqtt.publish("jarvis/status", "lights_on");
      Serial.println("Lights ON");
    } else {
      digitalWrite(LED_WHITE, LOW);
      mqtt.publish("jarvis/status", "lights_off");
      Serial.println("Lights OFF");
    }
  }

  // Red LED — Alert blink
  if (t == "jarvis/alert" && msg == "blink") {
    Serial.println("Alert blinking...");
    for (int i = 0; i < 8; i++) {
      digitalWrite(LED_RED, HIGH); delay(100);
      digitalWrite(LED_RED, LOW);  delay(100);
    }
    mqtt.publish("jarvis/status", "alert_done");
    Serial.println("Alert done");
  }

  // All off
  if (t == "jarvis/all" && msg == "off") {
    digitalWrite(LED_GREEN, LOW);
    digitalWrite(LED_WHITE, LOW);
    digitalWrite(LED_RED,   LOW);
    greenActive = false;
    mqtt.publish("jarvis/status", "all_off");
    Serial.println("All LEDs off");
  }
}


// ── Read DHT11 ────────────────────────────────────────────────────
void readDHT() {
  float temp = dht.readTemperature();
  float hum  = dht.readHumidity();

  if (isnan(temp) || isnan(hum)) {
    Serial.println("[DHT11] Read failed");
    return;
  }

  char tBuf[8], hBuf[8];
  dtostrf(temp, 4, 1, tBuf);
  dtostrf(hum,  4, 1, hBuf);
  mqtt.publish("jarvis/temperature", tBuf);
  mqtt.publish("jarvis/humidity",    hBuf);
  Serial.printf("[DHT11] Temp: %.1fC  Humidity: %.1f%%\n", temp, hum);

  if (temp >= 40.0) {
    mqtt.publish("jarvis/status", "high_temp");
    Serial.println("[DHT11] WARNING: High temperature!");
  }
}


// ── Check flame sensor ────────────────────────────────────────────
void checkFlame() {
  // DO pin goes LOW when flame is detected (active LOW)
  bool flameNow = (digitalRead(FLAME_PIN) == LOW);

  if (flameNow && !lastFlameState) {
    // Flame just detected
    Serial.println("[FLAME] FLAME DETECTED!");
    mqtt.publish("jarvis/flame", "detected");

    // Blink red LED rapidly as visual warning
    for (int i = 0; i < 5; i++) {
      digitalWrite(LED_RED, HIGH); delay(80);
      digitalWrite(LED_RED, LOW);  delay(80);
    }
  }
  else if (!flameNow && lastFlameState) {
    // Flame just cleared
    Serial.println("[FLAME] Flame cleared");
    mqtt.publish("jarvis/flame", "clear");
  }

  lastFlameState = flameNow;
}


// ── WiFi connect ──────────────────────────────────────────────────
void connectWiFi() {
  Serial.printf("Connecting to %s", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 40) {
    delay(500);
    Serial.print(".");
    tries++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nWiFi connected! IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("\nWiFi failed — restarting");
    ESP.restart();
  }
}


// ── MQTT connect ──────────────────────────────────────────────────
void connectMQTT() {
  while (!mqtt.connected()) {
    Serial.print("Connecting MQTT...");
    if (mqtt.connect(MQTT_ID)) {
      Serial.println(" connected!");
      mqtt.subscribe("jarvis/tea");
      mqtt.subscribe("jarvis/lights");
      mqtt.subscribe("jarvis/alert");
      mqtt.subscribe("jarvis/all");
      mqtt.publish("jarvis/status", "connected");
      Serial.println("JARVIS Complete firmware ready!");
    } else {
      Serial.printf(" failed (rc=%d) retrying...\n", mqtt.state());
      delay(3000);
    }
  }
}


// ── Setup ─────────────────────────────────────────────────────────
void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

  Serial.begin(115200);
  delay(500);
  Serial.println("\n\nJARVIS Complete — Stage 3 starting...");

  // LED pins
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_WHITE, OUTPUT);
  pinMode(LED_RED,   OUTPUT);
  digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_WHITE, LOW);
  digitalWrite(LED_RED,   LOW);

  // Sensor pins
  pinMode(FLAME_PIN, INPUT);
  dht.begin();

  // Startup LED test — confirms all 3 LEDs wired correctly
  Serial.println("Testing LEDs...");
  digitalWrite(LED_GREEN, HIGH); delay(400); digitalWrite(LED_GREEN, LOW);
  digitalWrite(LED_WHITE, HIGH); delay(400); digitalWrite(LED_WHITE, LOW);
  digitalWrite(LED_RED,   HIGH); delay(400); digitalWrite(LED_RED,   LOW);
  Serial.println("LED test done");

  connectWiFi();
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt.setCallback(mqttCallback);
  connectMQTT();

  // First DHT11 read
  delay(2000);
  readDHT();

  Serial.println("JARVIS Stage 3 — All systems online!");
}


// ── Loop ──────────────────────────────────────────────────────────
void loop() {
  if (!mqtt.connected()) {
    connectMQTT();
  }
  mqtt.loop();

  unsigned long now = millis();

  // Green LED 30s auto-off
  if (greenActive && (now - greenOnTime >= 30000)) {
    digitalWrite(LED_GREEN, LOW);
    greenActive = false;
    mqtt.publish("jarvis/status", "tea_autooff");
    Serial.println("Tea auto-off");
  }

  // DHT11 every 10 seconds
  if (now - lastDHTRead >= DHT_INTERVAL) {
    lastDHTRead = now;
    readDHT();
  }

  // Flame sensor every 1 second
  if (now - lastFlameCheck >= FLAME_INTERVAL) {
    lastFlameCheck = now;
    checkFlame();
  }
}
