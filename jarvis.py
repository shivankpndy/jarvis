"""
JARVIS — Just A Rather Very Intelligent System
Main entry point. Boot all agents, start voice loop.

Start order:
  1. ollama serve          (Window 1)
  2. python jarvis.py      (Window 2)
  3. cd dashboard && npm start  (Window 3)
"""
import sys
import os
from llm import chat, chat_raw
import time
from dotenv import load_dotenv
sys.path.insert(0, r"D:\JARVIS")
os.chdir(r"D:\JARVIS")
load_dotenv(r"D:\JARVIS\.env")

import tempfile
import subprocess
import threading
import re
import pyaudio
import speech_recognition as sr

# ── Constants ────────────────────────────────────────────────────────────────────
PIPER_EXE    = r"D:\JARVIS\piper_extracted\piper\piper.exe"
ALAN_VOICE   = r"D:\JARVIS\voices\en_GB-alan-medium.onnx"
JARVIS_VOICE = r"D:\JARVIS\voices\jarvis-medium.onnx"
VOICE_MODEL  = ALAN_VOICE
SAMPLE_RATE  = 16000

# ── ElevenLabs TTS (online — much better quality) ────────────────────────────
ELEVENLABS_KEY      = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "onwK4e9ZLuTAKqWW03F9")  # Daniel
ELEVENLABS_MODEL    = "eleven_turbo_v2"
USE_ELEVENLABS      = bool(ELEVENLABS_KEY)

WAKE_WORDS  = ["hey jarvis", "okay jarvis", "hi jarvis", "jarvis"]
SLEEP_WORDS = [
    "standby mode", "stand by mode", "go to standby", "standby",
    "go to sleep", "sleep mode", "bye jarvis", "goodbye jarvis", "thats all jarvis",
]

# ── STT Setup — Google Speech Recognition ────────────────────────────────────────
import requests as _requests

recognizer = sr.Recognizer()
# LOW threshold — calibration will raise it. Starting at 4000 means JARVIS
# never hears anything if calibration is skipped or the room is quiet.
recognizer.energy_threshold         = 300    # will be updated by calibration
recognizer.dynamic_energy_threshold = False  # FIXED — no drift mid-session
recognizer.pause_threshold          = 0.8
recognizer.phrase_threshold         = 0.3
recognizer.non_speaking_duration    = 0.5


def _find_best_mic() -> int:
    """
    Find the first mic index that SR can actually open.
    Prints all devices for diagnostics.
    Returns the best working index, or 0 as last resort.
    """
    print("\n[Mic] Scanning input devices...")
    try:
        names = sr.Microphone.list_microphone_names()
    except Exception as e:
        print(f"[Mic] Could not list SR mics: {e}")
        names = []

    pa = pyaudio.PyAudio()
    candidates = []
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info["maxInputChannels"] < 1:
            continue
        name  = info["name"].lower()
        score = 0
        if "usb"         in name: score += 4
        if "hd video"    in name: score += 3
        if "headset"     in name: score += 2
        if "headphone"   in name: score += 2
        if "microphone"  in name: score += 2
        if "external"    in name: score += 2
        if "built-in"    in name: score -= 1
        if "array"       in name: score -= 2
        if "stereo mix"  in name: score -= 9
        if "what u hear" in name: score -= 9
        if "bthhfenum"   in name: score -= 5
        print(f"  [{i}] {info['name']}  ch={info['maxInputChannels']}  score={score}")
        candidates.append((score, i, info["name"]))
    pa.terminate()

    # Sort best first, then verify each one actually opens via SR
    candidates.sort(key=lambda x: -x[0])
    for score, idx, name in candidates:
        if score < -5:
            continue
        try:
            with sr.Microphone(device_index=idx) as _test:
                pass
            print(f"[Mic] ✓ Selected index {idx} ({name})  score={score}")
            return idx
        except Exception as e:
            print(f"[Mic] ✗ Index {idx} ({name}) failed: {e}")

    print("[Mic] WARNING: No preferred mic worked — trying index 0")
    try:
        with sr.Microphone(device_index=0) as _test:
            pass
        return 0
    except Exception as e:
        print(f"[Mic] FATAL: Even index 0 failed: {e}")
        return 0


# Allow manual override via .env: MIC_INDEX=2
_env_mic = os.getenv("MIC_INDEX", "")
_MIC_INDEX = int(_env_mic) if _env_mic.strip().isdigit() else _find_best_mic()
print(f"[Mic] Using device index {_MIC_INDEX}")

# Calibrate — this sets the energy_threshold properly for the room noise
print("[STT] Calibrating ambient noise (2s) — keep quiet...")
try:
    with sr.Microphone(device_index=_MIC_INDEX) as _cal_src:
        recognizer.adjust_for_ambient_noise(_cal_src, duration=2)
    # Multiply by 1.5 so normal talking is always above threshold
    recognizer.energy_threshold = max(recognizer.energy_threshold * 1.5, 300)
    print(f"[STT] Whisper ready.. ✓  energy_threshold={recognizer.energy_threshold:.0f}")
except Exception as _cal_err:
    recognizer.energy_threshold = 500   # safe low fallback
    print(f"[STT] Calibration failed ({_cal_err}) — threshold set to {recognizer.energy_threshold:.0f}")


# ── Google Speech Recognition transcribe ─────────────────────────────────────────
def _google_transcribe(audio: sr.AudioData) -> str:
    """
    Transcribe using Google Web Speech API via SpeechRecognition.
    Returns lowercased stripped text, or "" on failure/silence.
    """
    try:
        text = recognizer.recognize_google(audio, language="en-IN")
        text = text.strip().lower().strip(".,!?").strip()
        if text:
            print(f"[STT] Google: '{text}'")
        return text
    except sr.UnknownValueError:
        # Silence / unintelligible — NOT a hallucination, just nothing heard
        return ""
    except sr.RequestError as e:
        print(f"[STT] Whisper request error: {e}")
        return ""
    except Exception as e:
        print(f"[STT] Whisper error: {e}")
        return ""


# ── Hallucination filter (minimal — Google SR is far cleaner than Whisper) ───────
_ALWAYS_ACCEPT = {
    "hey jarvis", "okay jarvis", "ok jarvis", "hi jarvis", "jarvis",
    "standby mode", "stand by mode", "bye jarvis", "goodbye jarvis",
    "go to sleep", "sleep mode", "go to standby", "standby",
    "thats all jarvis", "that's all jarvis",
    "make tea", "tea time", "chai", "brew tea", "tea off",
    "lights on", "lights off", "light on", "light off",
    "all off", "everything off",
    "send it", "cancel", "confirm", "yes", "no", "yeah", "okay",
    "start camera", "stop camera", "camera on", "camera off",
    "alert on", "alert off", "clear alert",
}

# Google SR hallucinates far less than Whisper — only block the most common noise hits
_HALLUCINATIONS = {
    "um", "uh", "hmm", "hm", "ah", "mm", "mhm",
    "music", "applause", "laughter",
    ".", ",", "!", "?", "...",
}

_TV_PHRASES = [
    "thank you for watching",
    "like and subscribe",
    "smash that like",
    "subscribe to our channel",
    "visit us online",
    "follow us on",
    "check out our",
    "see you in the next",
    "down below in the comments",
]


def _filter(text: str) -> str:
    """Apply always-accept / hallucination / TV-audio filter. Returns text or empty."""
    if not text:
        return ""

    t = text.lower().strip()

    for phrase in _ALWAYS_ACCEPT:
        if t == phrase or t.startswith(phrase + " "):
            print(f"[STT] ✓ (always) '{text}'")
            return text

    if t in _HALLUCINATIONS:
        print(f"[STT] ✗ hallucination '{text}'")
        return ""

    for tv in _TV_PHRASES:
        if tv in t:
            print(f"[STT] ✗ TV audio detected — ignoring")
            return ""

    if len(text) > 120:
        print(f"[STT] ✗ too long ({len(text)} chars) — likely background audio")
        return ""

    words = text.split()
    if len(words) > 20:
        print(f"[STT] ✗ too many words ({len(words)}) — likely background audio")
        return ""

    real = [w for w in words if w.isalpha() and len(w) >= 2]
    if not real:
        print(f"[STT] ✗ no real words '{text}'")
        return ""

    print(f"[STT] ✓ '{text}'")
    return text


# ── Early stubs — overwritten by dashboard_server at boot ────────────────────
# These must exist BEFORE listen_once / speak are called.
def notify_command(t):     pass
def notify_response(t):    pass
def notify_listening(a):   pass
def notify_activity(t, m): pass
def notify_awake(a):       pass
def notify_camera(a):      pass
def notify_motion():       pass

# ── State ────────────────────────────────────────────────────────────────────────
audio_interface      = pyaudio.PyAudio()
is_speaking          = False
interrupted          = False
interrupted_text     = ""
current_process      = None
jarvis_awake         = False
sr_mic_lock          = threading.Lock()
notification_event   = threading.Event()
_notification_queue  = []
_notification_lock   = threading.Lock()
_tts_lock            = threading.Lock()
_stt_lock            = threading.Lock()   # one recording at a time

print("JARVIS is online.\n")


def _open_mic():
    """Return a fresh Microphone — no sample_rate override (causes issues on Windows)."""
    return sr.Microphone(device_index=_MIC_INDEX)


# ── STT public API ────────────────────────────────────────────────────────────────

def listen_once(timeout: int = 8) -> str:
    """
    Record one voice phrase using Google Speech Recognition.
    Returns transcribed text, or "" if nothing heard / unintelligible.
    """
    if not _stt_lock.acquire(timeout=3):
        print("[STT] listen_once: could not acquire lock — skipping")
        return ""
    try:
        notify_listening(True)
        print(f"[STT] Listening... (threshold={recognizer.energy_threshold:.0f})")
        with _open_mic() as source:
            try:
                audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=15)
                print(f"[STT] Audio captured ({len(audio.frame_data)} bytes)")
            except sr.WaitTimeoutError:
                print("[STT] Timeout — no speech detected")
                return ""

        text = _filter(_google_transcribe(audio))
        if text:
            print(f"You: {text}")
        return text

    except Exception as e:
        print(f"[listen_once] ERROR: {e}")
        import traceback; traceback.print_exc()
        return ""
    finally:
        notify_listening(False)
        _stt_lock.release()


def listen_for_wakeword() -> bool:
    """
    Poll for wake word using Google SR.
    STRICT: must contain 'jarvis' to wake up.
    """
    if not _stt_lock.acquire(timeout=0.5):
        return False
    try:
        with _open_mic() as source:
            try:
                audio = recognizer.listen(source, timeout=4, phrase_time_limit=5)
            except sr.WaitTimeoutError:
                return False

        text = _google_transcribe(audio)
        if not text:
            return False

        t = text.lower().strip()
        print(f"[Wake] heard: '{t}'")

        JARVIS_VARIANTS = ["jarvis", "jarvi", "jarfish", "jarbes", "jarvish",
                           "javish", "jarbs", "jarbit", "jar vis"]
        has_jarvis = any(v in t for v in JARVIS_VARIANTS)

        if not has_jarvis:
            return False

        matched = any(w in t for w in WAKE_WORDS) or has_jarvis
        if matched:
            print(f"[Wake] ✓ Wake word: '{t}'")
        return matched

    except Exception as e:
        print(f"[Wake] ERROR: {e}")
        return False
    finally:
        _stt_lock.release()


# ── Persona + Memory ─────────────────────────────────────────────────────────────
JARVIS_PERSONA = """You are JARVIS, a highly intelligent personal AI assistant.
You are helpful, efficient, and slightly formal — like a British butler who is
also a genius engineer. Keep responses concise and clear.
Address the user as Shivank or sir naturally."""

from memory_agent import on_session_start, on_session_end, remember, get_memory_summary
_memory_context = on_session_start()
if _memory_context:
    JARVIS_PERSONA += f"\n\n{_memory_context}"
    print(f"Memory loaded:\n{_memory_context}\n")

conversation_history = [{"role": "system", "content": JARVIS_PERSONA}]


# ── TTS ──────────────────────────────────────────────────────────────────────────
def _normalize_tts_text(text: str) -> str:
    """Normalize text for TTS APIs that are sensitive to punctuation/formatting."""
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("—", ", ")
    text = text.replace("Mr.", "Mister")
    return text


def _tts_to_file(text: str) -> str:
    """Generate TTS audio. Returns file path (.mp3 from ElevenLabs or .wav from Piper)."""
    global USE_ELEVENLABS

    if USE_ELEVENLABS:
        try:
            import requests
            url     = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}/stream"
            headers = {
                "xi-api-key":   ELEVENLABS_KEY,
                "Content-Type": "application/json",
                "Accept":       "audio/mpeg",
            }

            def _try_elevenlabs(tts_text: str):
                payload = {
                    "text":       tts_text,
                    "model_id":   ELEVENLABS_MODEL,
                    "voice_settings": {
                        "stability":        0.55,
                        "similarity_boost": 0.80,
                        "style":            0.20,
                        "use_speaker_boost": True,
                    },
                }
                return requests.post(url, json=payload, headers=headers, stream=True, timeout=10)

            resp = _try_elevenlabs(text)
            if resp.status_code == 200:
                tmp_mp3 = tempfile.mktemp(suffix=".mp3")
                with open(tmp_mp3, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=4096):
                        if chunk:
                            f.write(chunk)
                return tmp_mp3
            else:
                if resp.status_code in (401, 403):
                    # Invalid/expired API key. Disable online TTS for this run to avoid repeated failures.
                    USE_ELEVENLABS = False
                    print("[TTS] ElevenLabs authentication failed. Check ELEVENLABS_API_KEY in .env and generate a new key if needed.")
                else:
                    # Retry once with normalized text before falling back.
                    retry_text = _normalize_tts_text(text)
                    if retry_text and retry_text != text:
                        retry = _try_elevenlabs(retry_text)
                        if retry.status_code == 200:
                            tmp_mp3 = tempfile.mktemp(suffix=".mp3")
                            with open(tmp_mp3, "wb") as f:
                                for chunk in retry.iter_content(chunk_size=4096):
                                    if chunk:
                                        f.write(chunk)
                            return tmp_mp3

                err_preview = (resp.text or "")[:120].replace("\n", " ").strip()
                print(f"[TTS] ElevenLabs {resp.status_code} ({err_preview}) — falling back to Piper")
        except Exception as e:
            print(f"[TTS] ElevenLabs failed ({e}) — falling back to Piper")

    tmp_wav = tempfile.mktemp(suffix=".wav")
    subprocess.run(
        [PIPER_EXE, "--model", VOICE_MODEL, "--output_file", tmp_wav],
        input=text.encode(), capture_output=True
    )
    return tmp_wav


def _play_audio(path: str):
    """Play .mp3 or .wav via PowerShell. Blocks until done."""
    global current_process
    if path.endswith(".mp3"):
        current_process = subprocess.Popen([
            "powershell", "-c",
            f"Add-Type -AssemblyName presentationCore; "
            f"$p = New-Object System.Windows.Media.MediaPlayer; "
            f"$p.Open([System.Uri]'{path}'); "
            f"$p.Play(); "
            f"Start-Sleep -Milliseconds 500; "
            f"while ($p.NaturalDuration.HasTimeSpan -eq $false) {{ Start-Sleep -Milliseconds 100 }}; "
            f"$dur = $p.NaturalDuration.TimeSpan.TotalMilliseconds; "
            f"Start-Sleep -Milliseconds ($dur + 200); "
            f"$p.Close()"
        ])
    else:
        current_process = subprocess.Popen([
            "powershell", "-c", f'(New-Object Media.SoundPlayer "{path}").PlaySync()'
        ])
    current_process.wait()


def speak_raw(text: str):
    """Speak without interrupt detection."""
    global current_process, is_speaking
    text = re.sub(r'[`*#_]', '', text).strip()
    if not text:
        return
    print(f"JARVIS: {text}")
    with _tts_lock:
        audio_path = _tts_to_file(text)
        try:
            is_speaking = True
            _play_audio(audio_path)
        finally:
            is_speaking = False
            if os.path.exists(audio_path):
                try: os.unlink(audio_path)
                except: pass


def speak(text: str) -> tuple[bool, str]:
    """Speak with interrupt detection. Returns (was_interrupted, interrupted_text)."""
    global is_speaking, interrupted, interrupted_text, current_process
    text = re.sub(r'```[\s\S]*?```', 'I have saved the code to your workspace folder sir.', text)
    text = re.sub(r'[`*#_]', '', text)
    text = ' '.join(text.split())
    if not text.strip():
        text = "Done sir. Please check your workspace folder."
    print(f"JARVIS: {text}")
    with _tts_lock:
        audio_path = _tts_to_file(text)
        try:
            is_speaking      = True
            interrupted      = False
            interrupted_text = ""
            listener = threading.Thread(target=_voice_interrupt_listener, daemon=True)
            listener.start()
            _play_audio(audio_path)
            is_speaking = False
            listener.join(timeout=1)
        finally:
            is_speaking = False
            if os.path.exists(audio_path):
                try: os.unlink(audio_path)
                except: pass
    return interrupted, interrupted_text


def _voice_interrupt_listener():
    """Listen for interruptions while JARVIS is speaking."""
    global is_speaking, interrupted, interrupted_text, current_process

    time.sleep(2.0)  # let speaker reverb die down first

    while is_speaking:
        if not _stt_lock.acquire(timeout=0.3):
            time.sleep(0.1)
            continue
        try:
            with _open_mic() as source:
                try:
                    audio = recognizer.listen(source, timeout=3, phrase_time_limit=6)
                except sr.WaitTimeoutError:
                    continue

            text = _google_transcribe(audio)
            if not text:
                continue

            words     = text.strip().split()
            has_wake  = any(w in text for w in WAKE_WORDS)
            has_sleep = any(w in text for w in SLEEP_WORDS)
            is_cmd    = len(words) >= 4

            if not (has_wake or has_sleep or is_cmd):
                print(f"[Interrupt] Ignored: '{text}'")
                continue

            print(f"[Interrupt] ✓ '{text}'")
            interrupted      = True
            interrupted_text = text
            is_speaking      = False
            if current_process and current_process.poll() is None:
                current_process.kill()
            return
        except Exception as e:
            print(f"[Interrupt] error: {e}")
        finally:
            try: _stt_lock.release()
            except: pass


# ── Notifications ─────────────────────────────────────────────────────────────────
def post_notification(text: str):
    """Queue a notification to be spoken — works even in standby."""
    with _notification_lock:
        if text not in _notification_queue:
            _notification_queue.append(text)
            notification_event.set()
    print(f"[Notif] Queued: {text}")
    try:
        _type = "System"
        tl = text.lower()
        if "email" in tl:                        _type = "Gmail"
        elif "slack" in tl:                      _type = "Slack"
        elif "telegram" in tl or "call" in tl:   _type = "Telegram"
        elif "tea" in tl:                        _type = "Tea"
        elif "motion" in tl or "intruder" in tl: _type = "Camera"
        elif "timer" in tl or "alarm" in tl:     _type = "Timer"
        elif "calendar" in tl:                   _type = "Calendar"
        elif "drive" in tl or "backup" in tl:    _type = "Drive"
        notify_activity(_type, text)
    except Exception:
        pass


def handle_notification():
    with _notification_lock:
        if not _notification_queue:
            notification_event.clear()
            return
        notif = _notification_queue.pop(0)
        if not _notification_queue:
            notification_event.clear()
    speak_raw(notif)


def _notification_killer():
    global is_speaking, interrupted, interrupted_text, current_process
    while True:
        notification_event.wait()
        if is_speaking:
            print("[Notif] Interrupting speech for notification")
            interrupted      = True
            interrupted_text = "__notification__"
            is_speaking      = False
            if current_process and current_process.poll() is None:
                current_process.kill()


def _notification_speaker():
    while True:
        notification_event.wait()
        if _notification_queue:
            handle_notification()
        time.sleep(0.2)


# ── Agent thinking ────────────────────────────────────────────────────────────────
def think(user_text: str) -> str:
    try:
        notify_command(user_text)
        from agent_router import route
        agent, reply = route(user_text, conversation_history)
        print(f"[Router] Agent used: {agent}")
        remember(user_text, reply)
        notify_response(reply)
        return reply
    except Exception as e:
        print(f"Think error: {e}")
        err_msg = f"I'm sorry sir, I encountered an error: {e}"
        try:
            conversation_history.append({"role": "user", "content": user_text})
            reply = chat(conversation_history).strip()
            if not reply:
                raise ValueError("empty response")
            conversation_history.append({"role": "assistant", "content": reply})
            remember(user_text, reply)
            notify_response(reply)
            return reply
        except Exception as e2:
            print(f"Think fallback also failed: {e2}")
            return err_msg


def wants_to_sleep(text: str) -> bool: return any(w in text for w in SLEEP_WORDS)
def is_wake_word(text: str)   -> bool: return any(w in text for w in WAKE_WORDS)


# ── Telegram watcher ──────────────────────────────────────────────────────────────
def start_telegram_watcher():
    import asyncio
    from dotenv import load_dotenv
    load_dotenv(r"D:\JARVIS\.env")
    from telethon import TelegramClient, events
    from telethon.tl.types import (
        UpdatePhoneCall, PhoneCallDiscarded, PhoneCallDiscardReasonMissed)
    from datetime import datetime

    API_ID   = int(os.getenv("TELEGRAM_API_ID", "0"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "")
    SESSION  = r"D:\JARVIS\jarvis_telegram"

    loop      = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    tg_client = TelegramClient(SESSION, API_ID, API_HASH, loop=loop)
    pending_calls        = {}
    active_conversations = {}

    async def get_caller_name(user_id):
        try:
            entity = await tg_client.get_entity(user_id)
            name   = getattr(entity, "first_name", "Unknown")
            if getattr(entity, "last_name", None):
                name += f" {entity.last_name}"
            return name
        except Exception:
            return f"User {user_id}"

    async def generate_reply(caller_name, message, history):
        resp = chat([
            {"role": "system", "content":
                f"You are JARVIS, AI assistant of Shivank Pandey. "
                f"You are chatting with {caller_name} on Telegram. "
                f"Shivank is unavailable. Be polite, collect their message, be brief."},
            *history,
            {"role": "user", "content": message},
        ])
        return resp.strip()

    async def summarize(caller_name, messages):
        conv = "\n".join([
            f"{'Caller' if m['role']=='user' else 'JARVIS'}: {m['content']}"
            for m in messages])
        resp = chat_raw(
            f"You are JARVIS. Summarize this conversation with {caller_name} for Shivank in 2 sentences.\n\n{conv}"
        )
        return resp.strip()

    @tg_client.on(events.Raw(UpdatePhoneCall))
    async def on_call(update):
        call = update.phone_call
        if hasattr(call, "admin_id"):
            pending_calls[call.id] = call.admin_id
        if isinstance(call, PhoneCallDiscarded):
            if isinstance(getattr(call, "reason", None), PhoneCallDiscardReasonMissed):
                caller_id   = pending_calls.pop(call.id, None)
                call_time   = datetime.now().strftime("%I:%M %p")
                caller_name = await get_caller_name(caller_id) if caller_id else "Unknown"
                print(f"[Telegram] Missed call from: {caller_name}")
                brief = chat_raw(
                    f"You are JARVIS. One sentence: notify Shivank of missed call from {caller_name} at {call_time}."
                ).strip()
                post_notification(brief)
                me = await tg_client.get_me()
                await tg_client.send_message(me.id, f"JARVIS: {brief}")
                if caller_id:
                    await tg_client.send_message(caller_id,
                        f"Hello {caller_name}!\n\nI'm JARVIS, Shivank's AI assistant. "
                        f"He missed your call. Please tell me what you need and I'll pass it on right away!")
                    active_conversations[caller_id] = {"name": caller_name, "messages": []}

    @tg_client.on(events.NewMessage(incoming=True))
    async def on_message(event):
        try:
            sender_id = event.sender_id
            me        = await tg_client.get_me()
            if sender_id == me.id: return
            if sender_id not in active_conversations: return
            conv    = active_conversations[sender_id]
            name    = conv["name"]
            msg     = event.message.message
            if not msg: return
            conv["messages"].append({"role": "user", "content": msg})
            reply   = await generate_reply(name, msg, conv["messages"][:-1])
            conv["messages"].append({"role": "assistant", "content": reply})
            await tg_client.send_message(sender_id, reply)
            summary = await summarize(name, conv["messages"])
            post_notification(f"Sir, {name} replied on Telegram. {summary}")
            conv_text = "\n".join([
                f"{'Caller ' + name if m['role']=='user' else 'JARVIS'}: {m['content']}"
                for m in conv["messages"]])
            await tg_client.send_message(me.id,
                f"Conversation with {name}:\n\n{conv_text}\n\nSummary: {summary}")
        except Exception as e:
            print(f"[Telegram] Message handler error: {e}")

    async def run():
        await tg_client.start()
        me = await tg_client.get_me()
        print(f"[Telegram] Online — logged in as {me.first_name}")
        await tg_client.run_until_disconnected()

    loop.run_until_complete(run())


# ── Main loops ────────────────────────────────────────────────────────────────────
def wait_for_wakeword():
    print("\nJARVIS on standby — say Hey JARVIS to wake up")
    notify_awake(False)
    while True:
        if notification_event.is_set() and _notification_queue:
            handle_notification()
            continue
        if listen_for_wakeword():
            return


def conversation_loop():
    global jarvis_awake
    jarvis_awake  = True
    silence_count = 0
    notify_awake(True)

    was_int, int_text = speak("Yes sir, how can I help?")
    pending_input = int_text if (was_int and int_text and int_text != "__notification__") else ""
    if was_int and int_text == "__notification__":
        handle_notification()

    while jarvis_awake:
        try:
            if notification_event.is_set():
                handle_notification()
                continue

            if pending_input:
                user_text     = pending_input
                pending_input = ""
                print(f"Processing: {user_text}")
            else:
                user_text = listen_once(timeout=8)

            if not user_text:
                silence_count += 1
                if silence_count >= 5:
                    silence_count = 0
                    was_int, int_text = speak("Are you still there, sir?")
                    if int_text == "__notification__":
                        handle_notification()
                    elif was_int and int_text:
                        pending_input = int_text
                continue

            silence_count = 0

            if wants_to_sleep(user_text):
                speak("Entering standby mode sir. Say Hey JARVIS whenever you need me.")
                on_session_end()
                jarvis_awake = False
                notify_awake(False)
                return

            print("Thinking...")
            reply = think(user_text)
            was_interrupted, int_text = speak(reply)

            if int_text == "__notification__":
                handle_notification()
                continue

            if was_interrupted and int_text:
                if wants_to_sleep(int_text):
                    speak("Entering standby mode sir.")
                    jarvis_awake = False
                    notify_awake(False)
                    return
                pending_input = int_text

        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"Conversation error: {e}")
            continue


# ══════════════════════════════════════════════════════════════════════════════════
# BOOT — Start all agents
# ══════════════════════════════════════════════════════════════════════════════════

try:
    from dashboard_server import (
        start          as dashboard_start,
        notify_command  as _nc,
        notify_response as _nr,
        notify_listening as _nl,
        notify_activity as _na,
        notify_awake    as _naw,
        notify_camera   as _ncam,
        notify_motion   as _nm,
    )
    # Replace the early stubs with real dashboard functions
    import builtins as _b
    import jarvis as _self   # noqa — update this module's globals
    import sys as _sys
    _mod = _sys.modules[__name__]
    _mod.notify_command  = _nc
    _mod.notify_response = _nr
    _mod.notify_listening = _nl
    _mod.notify_activity = _na
    _mod.notify_awake    = _naw
    _mod.notify_camera   = _ncam
    _mod.notify_motion   = _nm
    notify_command  = _nc
    notify_response = _nr
    notify_listening = _nl
    notify_activity = _na
    notify_awake    = _naw
    notify_camera   = _ncam
    notify_motion   = _nm
    dashboard_start()
    print("[Boot] Dashboard server on ws://localhost:8765")
except Exception as e:
    print(f"[Boot] Dashboard error: {e} — running without dashboard")

try:
    from timer_agent import set_notify as timer_set_notify
    timer_set_notify(post_notification)
    print("[Boot] Timer agent ready")
except Exception as e:
    print(f"[Boot] Timer error: {e}")

try:
    from iot_agent import set_notify as iot_set_notify, trigger_alert, start as iot_start
    iot_set_notify(post_notification)
    iot_start()
    print("[Boot] IoT agent ready")
except Exception as e:
    print(f"[Boot] IoT error: {e}")

def _boot_camera():
    try:
        from camera_agent import (
            set_notify        as cam_set_notify,
            set_iot_trigger   as cam_set_iot,
            set_dashboard_motion,
            set_dashboard_camera,
            start             as cam_start,
        )
        cam_set_notify(post_notification)
        set_dashboard_motion(notify_motion)
        set_dashboard_camera(notify_camera)
        try:
            from iot_agent import trigger_alert as _ta
            cam_set_iot(_ta)
        except Exception:
            pass

        if cam_start():
            print("[Boot] Camera auto-started — human detection ON")
            return

        print("[Boot] Camera not found — will auto-start when webcam is plugged in")

        def _watch_for_camera():
            import cv2, time as _t
            while True:
                _t.sleep(4)
                cap = cv2.VideoCapture(1)
                ok  = cap.isOpened()
                cap.release()
                if ok:
                    if cam_start():
                        print("[Camera] Webcam detected — auto-started!")
                        post_notification(
                            "Webcam connected sir. "
                            "Camera and human detection are now active."
                        )
                        return

        threading.Thread(target=_watch_for_camera, daemon=True).start()

    except Exception as e:
        print(f"[Boot] Camera error: {e}")

_boot_camera()

try:
    from sensor_agent import (
        start           as sensor_start,
        set_notify      as sensor_set_notify,
        set_speak       as sensor_set_speak,
        set_iot_trigger as sensor_set_iot,
    )
    sensor_set_notify(post_notification)
    sensor_set_speak(speak_raw)
    try:
        from iot_agent import trigger_alert as _ta
        sensor_set_iot(_ta)
    except Exception: pass
    sensor_start()
    print("[Boot] Waiting for ESP32 sensor data...")
    for _ in range(24):
        time.sleep(0.5)
        from sensor_agent import get_temperature
        if get_temperature() is not None:
            print("[Boot] ESP32 data received ✓")
            break
    else:
        print("[Boot] No ESP32 data yet — will populate when ESP32 publishes")
    print("[Boot] Sensor agent ready (silent mode)")
except Exception as e:
    print(f"[Boot] Sensor error: {e}")

try:
    from calendar_agent import (
        set_speak  as cal_set_speak,
        set_listen as cal_set_listen,
        set_notify as cal_set_notify,
        start      as cal_start,
    )
    cal_set_speak(speak_raw)
    cal_set_listen(listen_once)
    cal_set_notify(post_notification)
    cal_start()
    print("[Boot] Calendar agent ready (CalDAV)")
except Exception as e:
    print(f"[Boot] Calendar error: {e}")

try:
    from drive_agent import (
        set_speak         as drive_set_speak,
        set_listen        as drive_set_listen,
        set_notify        as drive_set_notify,
        start_auto_backup as drive_start_backup,
    )
    drive_set_speak(speak_raw)
    drive_set_listen(listen_once)
    drive_set_notify(post_notification)
    drive_start_backup()
    print("[Boot] Drive agent ready (rclone)")
except Exception as e:
    print(f"[Boot] Drive error: {e}")

try:
    from contacts_manager import (
        set_speak  as contacts_set_speak,
        set_listen as contacts_set_listen,
    )
    contacts_set_speak(speak_raw)
    contacts_set_listen(listen_once)
    print("[Boot] Contacts manager ready")
except Exception as e:
    print(f"[Boot] Contacts error: {e}")

try:
    from email_sender import (
        set_speak  as email_set_speak,
        set_listen as email_set_listen,
        set_notify as email_set_notify,
    )
    email_set_speak(speak_raw)
    email_set_listen(listen_once)
    email_set_notify(post_notification)
    print("[Boot] Email sender ready")
except Exception as e:
    print(f"[Boot] Email sender error: {e}")

try:
    from gmail_agent import start_email_watcher, set_notify as gmail_set_notify
    gmail_set_notify(post_notification)
    start_email_watcher()
    print("[Boot] Gmail watcher started")
except Exception as e:
    print(f"[Boot] Gmail error: {e}")

try:
    from slack_agent import start_slack_watcher, set_notify as slack_set_notify
    slack_set_notify(post_notification)
    start_slack_watcher()
    print("[Boot] Slack watcher started")
except Exception as e:
    print(f"[Boot] Slack error: {e}")

try:
    from travel_agent import (
        set_speak  as travel_set_speak,
        set_listen as travel_set_listen,
        set_notify as travel_set_notify,
    )
    travel_set_speak(speak_raw)
    travel_set_listen(listen_once)
    travel_set_notify(post_notification)
    print("[Boot] Travel agent ready (Amadeus)")
except ModuleNotFoundError:
    pass
except Exception as e:
    print(f"[Boot] Travel agent error: {e}")

try:
    from flight_agent import (
        set_speak  as flight_set_speak,
        set_listen as flight_set_listen,
        set_notify as flight_set_notify,
    )
    flight_set_speak(speak_raw)
    flight_set_listen(listen_once)
    flight_set_notify(post_notification)
    print("[Boot] Flight agent ready (MakeMyTrip)")
except Exception as e:
    print(f"[Boot] Flight agent error: {e}")

try:
    from zomato_agent import (
        set_speak  as zomato_set_speak,
        set_listen as zomato_set_listen,
        set_notify as zomato_set_notify,
    )
    zomato_set_speak(speak_raw)
    zomato_set_listen(listen_once)
    zomato_set_notify(post_notification)
    print("[Boot] Zomato agent ready (MCP)")
except Exception as e:
    print(f"[Boot] Zomato error: {e}")

try:
    from morning_briefing import (
        set_notify              as brief_set_notify,
        set_speak,
        start_briefing_scheduler,
    )
    brief_set_notify(post_notification)
    set_speak(speak_raw)
    start_briefing_scheduler("08:00")
    print("[Boot] Morning briefing scheduled at 08:00")
except Exception as e:
    print(f"[Boot] Briefing error: {e}")

threading.Thread(target=_notification_killer,  daemon=True).start()
threading.Thread(target=_notification_speaker, daemon=True).start()
print("[Boot] Notification threads started")

print("[Boot] Starting Telegram watcher...")
threading.Thread(target=start_telegram_watcher, daemon=True).start()

# ── Main loop ─────────────────────────────────────────────────────────────────────
print("\n" + "="*50)
print("  JARVIS is ready. Say Hey JARVIS to begin.")
print("="*50 + "\n")

while True:
    try:
        wait_for_wakeword()
        print("\nJARVIS awakened!")
        conversation_loop()
    except KeyboardInterrupt:
        print("\nJARVIS shutting down. Goodbye sir.")
        try:
            on_session_end()
        except Exception as mem_err:
            print(f"[Memory] Save skipped: {mem_err}")
        try:
            audio_interface.terminate()
        except:
            pass
        break
    except Exception as e:
        print(f"Main error: {e}")
        continue