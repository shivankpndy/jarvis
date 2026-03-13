![JARVIS Banner](banner.png)

# JARVIS — Personal AI Operating System

> **Fully Local. Completely Offline. Zero Cloud.**
> Built by Shivank Pandey • March 2026

JARVIS is a voice-controlled personal AI operating system that runs entirely on your own hardware — no API keys for the core brain, no cloud, no subscriptions. Inspired by Tony Stark's AI assistant, JARVIS manages your digital life, physical environment, and communications through natural conversation, powered by local LLMs via Ollama.

---

## ✨ Feature Overview

| Category | Features |
|----------|----------|
| 🎤 Voice | Wake word, Whisper STT, Piper TTS (Iron Man JARVIS voice), interruption handling |
| 🧠 Brain | llama3.2:3b via Ollama, 18-agent router, conversation memory |
| 💡 IoT | ESP32-CAM, 3 LEDs, tea scheduler, MQTT over WiFi |
| 📷 Camera | Motion detection, MJPEG live stream, HUD dashboard feed |
| 🌡️ Sensors | DHT11 temperature/humidity, flame sensor, voice alerts |
| 📧 Gmail | IMAP watcher, Ollama filter, voice send with step-by-step dictation |
| 💬 Slack | DM watcher, AI summaries, voice notifications |
| 📱 Telegram | Missed call interception, auto-reply, conversation summaries |
| 📅 Calendar | Google Calendar via CalDAV, event reading, voice event creation |
| ☁️ Drive | Google Drive via rclone, upload/download/search, midnight auto-backup |
| 👥 Contacts | Local contacts.json, auto-save from emails, name→email resolution |
| ✈️ Flights | AirLabs API, real schedules, proactive calendar-triggered suggestions |
| 🛵 Zepto | Zepto Café ordering via Playwright, full voice ordering flow |
| 🔍 Search | DuckDuckGo, Wikipedia fallback, auto-search when brain uncertain |
| 📈 Finance | Nifty, Sensex, crypto, gold, forex — live prices via yfinance |
| ☀️ Briefing | Daily 8AM briefing — calendar, emails, market summary |
| ⏱️ Timer | Natural language timers and alarms, fires even in standby |
| 💻 Coding | qwen2.5-coder:3b, saves to workspace\, CrewAI orchestration |

---


## 🧠 Agent Router — 18 Agents

| Priority | Agent | Trigger Examples |
|----------|-------|-----------------|
| 1 | Timer | `Set a timer for 10 minutes`, `Alarm at 7 AM` |
| 2 | IoT | `Turn on the lights`, `Make tea`, `Trigger alert` |
| 3 | Gmail (read) | `Check my emails`, `Any new mail` |
| 4 | Slack | `Check my Slack`, `Any Slack messages` |
| 5 | Email send | `Send an email to Rahul about the meeting` |
| 6 | Briefing | `Good morning JARVIS`, `Morning briefing` |
| 7 | Calendar | `What's on my calendar today`, `Add a meeting` |
| 8 | Drive | `Upload file to Drive`, `List my Drive files` |
| 9 | Contacts | `Show my contacts`, `Add contact` |
| 10 | Sensor | `What's the room temperature`, `Any fire` |
| 11 | Search | `Search for`, `Latest news about` |
| 12 | Camera | `Start camera`, `Stop monitoring` |
| 13 | Finance | `What is Nifty today`, `Bitcoin price` |
| 14 | Flight | `Search flights to Delhi tomorrow` |
| 15 | Zepto | `Order from Zepto`, `Zepto café coffee` |
| 16 | Brain override | `Explain`, `What is`, `Tell me about` |
| 17 | Coding | `Write a Python script for...` |
| 18 | Brain (default) | Everything else + auto web search fallback |

---

## 💡 Hardware

- USB microphone + speakers
- ESP32-CAM module (AI Thinker)
- USB webcam (motion detection + MJPEG stream)
- DHT11 temperature/humidity sensor
- Flame sensor module (DO output)
- 3x LEDs: green, white, red
- 3x 220Ω resistors + 1x 10KΩ (DHT11 pull-up)
- Breadboard + jumper wires
- Arduino Uno (USB-Serial bridge only)
- Phone charger / power bank (ESP32 power)

### ESP32-CAM Wiring

| GPIO | Component | Function |
|------|-----------|----------|
| GPIO12 | Green LED + 220Ω | Tea reminder (6AM + 5PM auto, 30 min) |
| GPIO2 | White LED + 220Ω | Room lights (stays on) |
| GPIO13 | Red LED + 220Ω | Alert / intruder (blink only) |
| GPIO14 | DHT11 DATA + 10KΩ→3.3V | Temperature + humidity |
| GPIO15 | Flame sensor DO | Fire detection (LOW = flame) |


---

## 📷 Camera System

- **Motion detection:** OpenCV MOG2 background subtraction
- **Live stream:** MJPEG server on `http://localhost:8766/stream`
- **Snapshots:** Saved to `D:\JARVIS\snapshots\` on motion
- **Dashboard feed:** Live camera in React HUD with REC badge + motion flash
- **Standby alerts:** Motion notifications speak even when JARVIS is sleeping

---

## ✈️ Flight Agent

Uses **AirLabs API** (free, 1000 queries/month) for real scheduled flight data.

```
Hey JARVIS → Search flights to Delhi tomorrow
Hey JARVIS → Find flights from Delhi to Mumbai on Friday
```

---

## 🚀 Installation

### Prerequisites
- Python 3.11.9
- [Ollama](https://ollama.ai)
- [Mosquitto MQTT](https://mosquitto.org)
- [rclone](https://rclone.org) — `winget install Rclone.Rclone`
- Node.js 18+ (for dashboard)
- Arduino IDE + ESP32 board support

pip install faster-whisper pyaudio ollama SpeechRecognition
pip install crewai crewai-tools litellm
pip install telethon python-dotenv paho-mqtt pyserial schedule
pip install requests yfinance duckduckgo-search wikipedia
pip install opencv-python caldav vobject httpx
pip install playwright && playwright install firefox
```

### 2 — Ollama models
```powershell
ollama pull llama3.2:3b
ollama pull qwen2.5-coder:3b
```

### 3 — Voice Model for JARVIS (optional but highly recommended)
```powershell
cd D:\JARVIS\voices
curl -L -o jarvis-medium.onnx "https://huggingface.co/jgkawell/jarvis/resolve/main/en/en_GB/jarvis/medium/jarvis-medium.onnx"
curl -L -o jarvis-medium.onnx.json "https://huggingface.co/jgkawell/jarvis/resolve/main/en/en_GB/jarvis/medium/jarvis-medium.onnx.json"
```
JARVIS auto-detects this on startup — no code change needed.

### 4 — Configure `.env`
```env
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
GMAIL_EMAIL=your@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password
SLACK_TOKEN=xoxp-your-token
AIRLABS_KEY=your_key_from_airlabs.co
HOME_CITY=XCITYX
HOME_IATA=XXX
HOME_LAT=XX.XXX
HOME_LNG=XX.XXXX
ZEPTO_PHONE=9XXXXXXXXX
ZEPTO_ADDRESS=Home
```

### 5 — One-time setups
```powershell
# Google Drive
rclone config
# → n → name: jarvis_drive → type: 24 (Google Drive) → follow prompts

# Zepto Café login
python zepto_agent.py --login
```

### 6 — Dashboard
```powershell
cd D:\JARVIS\dashboard
npm install && npm start
```

### 7 — Start JARVIS
```powershell
cd D:\JARVIS
.\venv\Scripts\activate
python jarvis.py
cd D:\JARVIS\dashboard && npm start
```


## 🔒 Privacy

Everything runs on your machine. Your voice never leaves your PC. No data is sent to any cloud service. Outbound connections only to your own accounts (Telegram, Gmail, Slack, Drive) and AirLabs flight data.

---

## Why JARVIS?

Most AI assistants are cloud-dependent — your voice goes to a server, your data is stored remotely, and you pay per API call. JARVIS is a statement against that model.

Everything runs on your own hardware. Your conversations never leave your PC. No monthly fees, no rate limits, no single point of failure. If the internet goes down, JARVIS still works — voice, IoT, sensors, memory, all of it.

JARVIS proves that a fully capable personal AI OS — voice, hardware, communications, memory, intelligent routing — can be built by a single developer on consumer hardware using entirely open-source tools.

---

*"Just a local AI, sir."*

**Built with ❤️ by Shivank Pandey March 2026**
