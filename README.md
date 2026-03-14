![JARVIS Banner](banner.png)

# JARVIS (Just a Rather Very Intelligent System) Personal AI Operating System

> **Fully Local. Completely Offline. Zero Cloud.**
> Built by Shivank Pandey 

JARVIS is a voice-controlled personal AI operating system that runs entirely on your own hardware, no API keys for the core brain, no cloud, no subscriptions. Inspired by Tony Stark's AI assistant.

---

## 💡 Hardware

- USB microphone + speakers
- ESP32-CAM module (AI Thinker)
- USB webcam (motion detection + MJPEG stream)
- DHT11 temperature/humidity sensor
- Flame sensor module (DO output)
- 3x LEDs: green, white, red
- 3x 220Ω resistors + 1x 1KΩ (DHT11 pull-up)
- Breadboard + jumper wires
- Arduino Uno (USB-Serial bridge only)
- Phone charger / power bank (ESP32 power)

### ESP32-CAM Wiring
![wiring](circuit_image.png)


| GPIO | Component | Function |
|------|-----------|----------|
| GPIO12 | Green LED + 220Ω | Tea reminder (6AM + 5PM auto, 30 min) |
| GPIO2 | White LED + 220Ω | Room lights (stays on) |
| GPIO13 | Red LED + 220Ω | Alert / intruder (blink only) |
| GPIO14 | DHT11 DATA + 10KΩ→3.3V | Temperature + humidity |
| GPIO15 | Flame sensor DO | Fire detection (LOW = flame) |


---
### Billing of Items 
![billing of items](bom.png)

---
## 🚀 Installation

### Prerequisites
- Python 3.11.9
- [Ollama](https://ollama.ai)
- [Mosquitto MQTT](https://mosquitto.org)
- [rclone](https://rclone.org) — `winget install Rclone.Rclone`
- Node.js 18+ (for dashboard)
- Arduino IDE + ESP32 board support

``` python
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
---

*"Just a local AI, sir."*

**Built with ❤️ by Shivank Pandey**
