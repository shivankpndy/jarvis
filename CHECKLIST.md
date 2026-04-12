# JARVIS — Complete Test Checklist
**Test every feature before submitting to Hack Club Manifesto**

Mark each item ✅ when it passes, ❌ if it fails (note the error).

---

## 🔧 PRE-FLIGHT (do these before testing anything else)

- [ ] `ollama serve` is running in Terminal 1
- [ ] Mosquitto MQTT broker is running (`mosquitto` or check Services)
- [ ] ESP32-CAM is powered and connected to WiFi
- [ ] `python jarvis.py` starts without any import errors
- [ ] All `[Boot]` lines print without `error` — check each one:
  - [ ] `[Boot] Dashboard server on ws://localhost:8765`
  - [ ] `[Boot] Timer agent ready`
  - [ ] `[Boot] IoT + Camera agents ready`
  - [ ] `[Boot] Camera stream on http://localhost:8766/stream`
  - [ ] `[Boot] Sensor agent ready (DHT11 + Flame)`
  - [ ] `[Boot] Calendar agent ready (CalDAV)`
  - [ ] `[Boot] Drive agent ready (rclone)`
  - [ ] `[Boot] Contacts manager ready`
  - [ ] `[Boot] Email sender ready`
  - [ ] `[Boot] Gmail watcher started`
  - [ ] `[Boot] Slack watcher started`
  - [ ] `[Boot] Morning briefing scheduled at 08:00`
  - [ ] `[Boot] Swiggy ready` or `[Boot] Zepto Café ready`
  - [ ] `[Boot] Flight agent ready`
  - [ ] `[Boot] Notification threads started`
  - [ ] `[Boot] Telegram watcher` — logged in as your name
- [ ] Dashboard opens at `http://localhost:3000` without errors
- [ ] Dashboard shows JARVIS HUD — not blank/error screen

---

## 🎤 1. VOICE PIPELINE

### Wake Word
- [ ] Say `Hey JARVIS` → JARVIS wakes up and says "Yes sir, how can I help?"
- [ ] Say `Okay JARVIS` → wakes up
- [ ] Say `Hi JARVIS` → wakes up
- [ ] Say nothing for 10 seconds → JARVIS asks "Are you still there, sir?"

### Sleep / Standby
- [ ] Say `Standby mode` → JARVIS sleeps, says standby message
- [ ] Say `Bye JARVIS` → sleeps
- [ ] After sleeping → say `Hey JARVIS` again → wakes back up

### Interruption
- [ ] Start JARVIS speaking a long response → speak 4+ words while it talks → JARVIS stops and processes your new command
- [ ] Say 1-2 words while JARVIS speaks → should NOT interrupt (too short)

### Dashboard Voice Feedback
- [ ] Wake JARVIS → dashboard status indicator changes to AWAKE
- [ ] Say something → dashboard shows listening indicator
- [ ] Go to standby → dashboard shows STANDBY

---

## 🧠 2. BRAIN (General Conversation)

- [ ] `What is the capital of France?` → correct answer
- [ ] `Tell me about quantum physics` → brain gives explanation (not coding agent)
- [ ] `Who is Tony Stark?` → brain answers
- [ ] `Write a poem about rain` → brain writes poem (NOT coding agent)
- [ ] Ask something you asked in a previous session → JARVIS references memory: *"As we discussed..."*
- [ ] Check `D:\JARVIS\memory\jarvis_memory.json` exists and has entries

---

## 💡 3. IOT — ESP32-CAM + LEDS

### Lights (White LED — GPIO2)
- [ ] `Turn on the lights` → white LED turns ON, JARVIS confirms
- [ ] `Turn off the lights` → white LED turns OFF
- [ ] `Lights on` → ON
- [ ] `Room lights off` → OFF
- [ ] Dashboard shows white LED state change

### Tea (Green LED — GPIO12)
- [ ] `Make tea` → green LED turns ON, JARVIS says "Tea is brewing sir"
- [ ] Wait 30 minutes OR check it auto-offs (or manually test the timer logic)
- [ ] `Cancel tea` → green LED turns OFF
- [ ] `Tea time` → turns ON

### Alert (Red LED — GPIO13)
- [ ] `Trigger alert` → red LED BLINKS (not stays on)
- [ ] `Intruder` → red LED blinks
- [ ] `Clear alert` → red LED turns OFF
- [ ] After alert sequence → red LED ends in OFF state (important!)
- [ ] Dashboard shows red LED state

### All Off
- [ ] `Everything off` → all 3 LEDs turn off
- [ ] `Turn off everything` → all off

---

## ⏱️ 4. TIMER & ALARM

- [ ] `Set a timer for 1 minute` → JARVIS confirms → 60 seconds later speaks alert
- [ ] `Set a timer for 5 minutes` → confirms → fires at 5 min
- [ ] `Alarm at [time 2 minutes from now]` → fires at that time
- [ ] Timer alert fires even when JARVIS is in STANDBY mode
- [ ] Set 2 timers at once → both fire independently

---

## 📷 5. CAMERA AGENT

- [ ] `Start camera` → JARVIS says camera is active
- [ ] `Camera status` → JARVIS says on/off + motion events count
- [ ] Walk in front of webcam → JARVIS says "Motion detected sir"
- [ ] Motion alert fires even in STANDBY (notification speaker thread)
- [ ] Check `D:\JARVIS\snapshots\` → new snapshot files created on motion
- [ ] `Stop camera` → monitoring stops
- [ ] `Camera off` → stops

### MJPEG Stream
- [ ] Open browser → `http://localhost:8766/stream` → live video feed visible
- [ ] Feed shows timestamp overlay
- [ ] Feed shows REC indicator
- [ ] Dashboard camera panel shows live feed when camera is active

---

## 🌡️ 6. SENSORS (DHT11 + Flame)

- [ ] `What's the room temperature?` → JARVIS reads DHT11 temperature
- [ ] `What's the humidity?` → JARVIS reads humidity %
- [ ] `Is there any fire?` → JARVIS reads flame sensor (should say no)
- [ ] Trigger flame sensor (lighter near it, briefly) → JARVIS speaks fire alert
- [ ] Fire alert fires even in STANDBY mode
- [ ] Fire alert triggers red LED blink (IoT alert integration)

---

## 📧 7. GMAIL

### Read
- [ ] `Check my emails` → JARVIS reads unread emails with sender + subject
- [ ] `Any new emails?` → reads inbox
- [ ] Send yourself a test email → wait ~60 seconds → JARVIS auto-announces it by voice
- [ ] Gmail auto-announce fires even in STANDBY

### Send (Step-by-Step)
- [ ] `Send an email to [contact name]` → JARVIS asks for subject separately
- [ ] JARVIS asks for subject → speak it → JARVIS confirms
- [ ] JARVIS asks for content → speak it → JARVIS drafts with Ollama
- [ ] JARVIS reads draft back
- [ ] Say `send it` → email actually arrives in recipient inbox
- [ ] Say `edit` → JARVIS asks for changes
- [ ] Say `cancel` → cancelled cleanly
- [ ] **Type fallback:** stay silent when asked for subject → JARVIS offers to type → type in terminal → works

---

## 💬 8. SLACK

- [ ] `Check my Slack` → reads recent DMs
- [ ] `Any Slack messages?` → reads
- [ ] Send yourself a Slack DM → wait ~30 seconds → JARVIS auto-announces

---

## 📱 9. TELEGRAM

- [ ] JARVIS starts → Telegram watcher shows "logged in as [your name]"
- [ ] From another phone/account → call your Telegram and don't answer → JARVIS speaks "Missed call from [name]"
- [ ] Caller receives auto-reply message from JARVIS
- [ ] Reply to JARVIS on Telegram → JARVIS responds intelligently
- [ ] Summary appears in your Telegram Saved Messages

---

## 👥 10. CONTACTS

- [ ] `Show my contacts` → lists contacts
- [ ] `Add contact` → JARVIS asks for name and email → saves to contacts.json
- [ ] `Delete contact [name]` → removed
- [ ] Check `D:\JARVIS\contacts.json` → file exists and has correct data
- [ ] Send email to a saved contact name → JARVIS resolves name to email automatically
- [ ] Send email to unknown name → JARVIS asks for email → offers to save

---

## 📅 11. CALENDAR (CalDAV)

- [ ] `What's on my calendar today?` → reads today's events from Google Calendar
- [ ] `What do I have this week?` → reads week events
- [ ] `Add a meeting with Rahul tomorrow at 3pm` → JARVIS confirms → check Google Calendar on phone — event appears
- [ ] `Schedule team call on Friday at 11am` → creates event
- [ ] CalDAV connection shown as working in boot log

---

## ☁️ 12. GOOGLE DRIVE (rclone)

- [ ] `List my Drive files` → lists files in JARVIS folder on Drive
- [ ] `Upload D:\JARVIS\README.md to Drive` → JARVIS confirms → check Google Drive — file appears
- [ ] `Find README on Drive` → finds it
- [ ] `Backup my memory` → backs up memory folder → check Drive
- [ ] Auto-backup: set system clock to midnight (or wait) → backup fires
- [ ] `Download [filename] from Drive` → file appears in `D:\JARVIS\downloads\`

---

## 🔍 13. WEB SEARCH

- [ ] `Search for latest AI news` → JARVIS reads results
- [ ] `What happened in cricket yesterday?` → searches and reads
- [ ] `Look up Python asyncio tutorial` → searches
- [ ] Ask brain something uncertain → auto-search fallback triggers

---

## 📈 14. FINANCE

- [ ] `What is Nifty today?` → live NSE index value
- [ ] `What is Sensex?` → BSE value
- [ ] `Bitcoin price` → live BTC/INR
- [ ] `Gold price` → gold rate
- [ ] `Dollar rate` → USD/INR
- [ ] `Ethereum price` → ETH value

---

## ☀️ 15. MORNING BRIEFING

- [ ] `Good morning JARVIS` → full briefing: date, weather/temp, calendar, emails, market
- [ ] `Morning briefing` → same
- [ ] `Brief me` → same
- [ ] Auto-briefing: verify it's scheduled for 08:00 in boot log

---

## ✈️ 16. FLIGHT AGENT (AirLabs)

- [ ] Verify `AIRLABS_KEY` is set in `.env`
- [ ] `Search flights to Delhi tomorrow` → JARVIS reads flight options (airline, depart, arrive, duration)
- [ ] `Find flights from Lucknow to Mumbai on Friday` → reads results
- [ ] After reading options → say `yes` → MakeMyTrip opens in browser on correct search
- [ ] Say `no` → cancelled cleanly
- [ ] No AirLabs key → JARVIS says to add key (not crash)
- [ ] **Proactive hook:** `What's on my calendar this week?` AND you have an event with a city name → JARVIS asks "Shall I search for flights?"

---

## 🛵 17. ZEPTO CAFÉ

- [ ] `python zepto_agent.py --login` → Firefox opens → login saved
- [ ] `Order coffee from Zepto` → Firefox opens → searches Zepto
- [ ] JARVIS reads store name + item options with prices
- [ ] Pick an item → JARVIS reads full order summary (item, store, price)
- [ ] Say `yes` → order proceeds
- [ ] Say `cancel` → cancelled cleanly
- [ ] `Zepto café sandwich` → searches sandwiches

---

## 💻 18. CODING AGENT

- [ ] `Write a Python function to sort a list` → qwen2.5-coder generates code
- [ ] `Create a script that reads a CSV file` → generates code
- [ ] Code saves to `D:\JARVIS\workspace\` → check file appears
- [ ] `Write a poem about AI` → goes to BRAIN not coding agent (brain override)
- [ ] `Explain recursion` → goes to BRAIN not coding agent

---

## 🖥️ 19. REACT DASHBOARD

Open `http://localhost:3000` and verify:
- [ ] JARVIS HUD loads without errors
- [ ] Status shows STANDBY / AWAKE correctly
- [ ] LED indicators update when voice commands change LEDs
- [ ] Listening indicator pulses when JARVIS is listening
- [ ] Activity log shows recent commands and responses
- [ ] Camera feed panel shows stream when camera is active
- [ ] Motion flash animation triggers on motion detection
- [ ] Agent list shows all agents
- [ ] Stats counter increments with each command

---

## 🧪 20. EDGE CASES & STRESS TESTS

- [ ] Say wake word while JARVIS is already speaking → handles gracefully
- [ ] Give a completely unknown command → defaults to brain
- [ ] Speak very quietly → STT doesn't crash
- [ ] Run JARVIS for 30 minutes → no memory leak / crash
- [ ] Disconnect ESP32 WiFi → JARVIS doesn't crash, gives MQTT error gracefully
- [ ] Disconnect webcam → camera agent fails gracefully
- [ ] Bad internet → search agent fails gracefully with message

---

## 📁 21. FILE & SETUP CHECKS

- [ ] `D:\JARVIS\.env` has all required keys
- [ ] `D:\JARVIS\contacts.json` exists (even if empty `[]`)
- [ ] `D:\JARVIS\memory\jarvis_memory.json` exists
- [ ] `D:\JARVIS\snapshots\` folder exists
- [ ] `D:\JARVIS\downloads\` folder exists
- [ ] `D:\JARVIS\workspace\` folder exists
- [ ] `contact_manager.py` renamed to `contacts_manager.py` ← CRITICAL
- [ ] `.gitignore` is in `D:\JARVIS\` root
- [ ] `.env` is NOT committed to git (`git status` should not show it)
- [ ] `jarvis_telegram.session` is NOT committed to git
- [ ] `swiggy_session\` is NOT committed to git
- [ ] `zepto_session\` is NOT committed to git
- [ ] `piper_extracted\` is NOT committed to git
- [ ] `venv\` is NOT committed to git

---

## 🎯 DEMO RUN — Final Check

Do this full run-through as if you're recording your demo video:

1. - [ ] Start JARVIS → all agents boot cleanly
2. - [ ] Open dashboard → HUD shows correctly
3. - [ ] Say `Hey JARVIS` → wakes up
4. - [ ] `Turn on the lights` → white LED ON + dashboard updates
5. - [ ] `What's the room temperature?` → sensor reads correctly
6. - [ ] `Check my emails` → reads inbox
7. - [ ] `What's on my calendar today?` → reads events
8. - [ ] `Search flights to Delhi this Friday` → reads options
9. - [ ] `Make tea` → green LED ON
10. - [ ] `Start camera` → monitoring active
11. - [ ] Walk in front of camera → motion alert fires
12. - [ ] `What is Nifty today?` → market data
13. - [ ] `Everything off` → all LEDs off
14. - [ ] `Standby mode` → JARVIS sleeps
15. - [ ] Verify dashboard shows STANDBY

---

**Total items: ~120**
**Suggested order:** Pre-flight → Voice → IoT → Timer → Brain → then all others
**Estimated time:** 2-3 hours for a full run-through

---

*If something fails — note the error message and we can fix it.*