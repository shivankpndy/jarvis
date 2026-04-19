![JARVIS Banner](banner.png)

# JARVIS — Personal AI Operating System (vERSION 2 in dev)

> **Fully Local. Completely Offline. Zero Cloud.**
> Built by Shivank Pandey 

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

## 🎙️ Voice Pipeline

```
Microphone → SpeechRecognition (VAD) → faster-whisper (small.en)
    → Hallucination filter → Intent router → Agent
    → Ollama response → Piper TTS → Speakers
```

- **Wake words:** `Hey JARVIS` / `Okay JARVIS` / `Hi JARVIS`
- **Sleep words:** `Standby mode` / `Bye JARVIS` / `Go to sleep`
- **Interruption:** Say 4+ words while JARVIS is speaking to interrupt
- **Notifications:** Dedicated thread speaks alerts even in standby mode
- **Voice:** Iron Man JARVIS voice (Paul Bettany) via community Piper model — auto-falls back to British Alan if not downloaded

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

### Components
- Windows 11 PC (CPU-only, no GPU needed)
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

```
ESP32-CAM  ←  powered from phone charger (NOT Arduino 5V)
Arduino Uno:  RESET → GND  (disables chip, USB-Serial bridge only)
              TX → ESP32 GPIO3 (RX)
              RX → ESP32 GPIO1 (TX)
```

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

**Proactive calendar hook:** When you ask *"What's on my calendar this week?"* and JARVIS sees *"Meeting in Delhi on Friday"*, it automatically says:
> *"Sir, I noticed 'Meeting in Delhi' on Friday at 3 PM. It looks like it may be in Delhi. Shall I search for flights?"*

---

## 📧 Email — Step-by-Step Dictation

JARVIS listens to each part separately and falls back to typing if it can't hear:

```
You:    Hey JARVIS, send an email to Rahul
JARVIS: What's the subject?
You:    Meeting tomorrow
JARVIS: What should the email say?
You:    Tell him it's at 3pm in the office, bring his laptop
JARVIS: Here's the draft: "Dear Rahul, just a reminder that..."
JARVIS: Say 'send it', 'edit', or 'cancel'
You:    Send it
JARVIS: Email sent to rahul@example.com successfully.
```

---

## 🗂️ File Structure

```
D:\JARVIS\
├── jarvis.py               ← Main loop + voice pipeline + agent boot
├── agent_router.py         ← 18-agent intent detection + routing
├── iot_agent.py            ← MQTT + LED control + tea scheduler
├── gmail_agent.py          ← IMAP watcher + Ollama filter
├── email_sender.py         ← Step-by-step voice email compose + send
├── slack_agent.py          ← Slack DM watcher
├── memory_agent.py         ← Persistent JSON memory + fact extraction
├── timer_agent.py          ← Natural language timers + alarms
├── camera_agent.py         ← OpenCV motion detection
├── camera_stream.py        ← MJPEG stream server (port 8766)
├── sensor_agent.py         ← DHT11 + flame sensor via MQTT
├── search_agent.py         ← DuckDuckGo + Wikipedia
├── finance_agent.py        ← Live market data via yfinance
├── morning_briefing.py     ← Daily 8AM briefing
├── coding_agent.py         ← qwen2.5-coder:3b
├── crew_orchestrator.py    ← CrewAI orchestration
├── calendar_agent.py       ← Google Calendar via CalDAV
├── drive_agent.py          ← Google Drive via rclone
├── contacts_manager.py     ← Local contacts.json
├── flight_agent.py         ← AirLabs API + MakeMyTrip
├── zepto_agent.py          ← Zepto Café Playwright ordering
├── dashboard_server.py     ← WebSocket server (port 8765)
├── dashboard/              ← React HUD dashboard
├── iot_esp32_code/         ← Arduino sketches for ESP32-CAM
├── piper_extracted/        ← Piper TTS binary (not committed)
├── voices/                 ← TTS voice models (not committed)
├── memory/                 ← Conversation logs (not committed)
├── snapshots/              ← Motion snapshots (not committed)
├── workspace/              ← Coding agent output (not committed)
└── .env                    ← Credentials (never commit)
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

### 1 — Python dependencies
```powershell
cd D:\JARVIS
python -m venv venv
.\venv\Scripts\activate

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

### 3 — Iron Man JARVIS voice (optional but highly recommended)
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
# Terminal 1 — Ollama
ollama serve

# Terminal 2 — JARVIS
cd D:\JARVIS
.\venv\Scripts\activate
python jarvis.py

# Terminal 3 — Dashboard (optional)
cd D:\JARVIS\dashboard && npm start
```

---

## 🗣️ Voice Commands

```
# Wake / Sleep
Hey JARVIS                               → wake up
Bye JARVIS / Standby mode               → sleep

# Lights & IoT
Turn on / off the lights                → white LED
Make tea / Tea time                     → green LED 30 min
Trigger alert / Intruder                → red LED blinks
Everything off                          → all LEDs off

# Communication
Send an email to [name]                 → step-by-step compose
Check my emails                         → reads unread inbox
Check my Slack                          → reads recent DMs

# Calendar & Planning
What's on my calendar today             → today's events
What do I have this week                → week events
Add a meeting with Rahul tomorrow 3pm  → creates event
Search flights to Delhi tomorrow        → AirLabs + MakeMyTrip

# Smart Home
What's the room temperature             → DHT11 reading
Is there any fire                       → flame sensor
Start / stop camera                     → motion detection

# Productivity
Good morning JARVIS                     → full briefing
What is Nifty today                     → live market data
Bitcoin price                           → crypto
Write a Python script for...            → coding agent
Search for [topic]                      → web search

# Files & Cloud
Upload [path] to Drive                  → rclone upload
List my Drive files                     → file listing
Backup my memory                        → midnight auto-backup
```

---

## 🔧 Technology Stack

| Layer | Technology |
|-------|------------|
| AI Brain | Ollama + llama3.2:3b (fully local, CPU) |
| Coding | qwen2.5-coder:3b |
| Orchestration | CrewAI + litellm |
| STT | faster-whisper small.en (offline) |
| TTS | Piper TTS — JARVIS Iron Man / Alan voice |
| IoT Protocol | MQTT (Mosquitto, local broker) |
| IoT Hardware | ESP32-CAM (WiFi + MQTT) |
| Camera | OpenCV MOG2 + MJPEG HTTP server |
| Sensors | DHT11 + Flame sensor over MQTT/serial |
| Telegram | Telethon MTProto |
| Gmail | IMAP + App Password |
| Slack | Slack Web API |
| Calendar | CalDAV (App Password, no OAuth) |
| Drive | rclone CLI |
| Flights | AirLabs REST API |
| Ordering | Playwright + Firefox (persistent session) |
| Search | DuckDuckGo + Wikipedia |
| Finance | yfinance + requests |
| Dashboard | React + WebSocket |
| Memory | JSON + Ollama fact extraction |

---

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
#
