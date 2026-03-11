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
import time
sys.path.insert(0, r"D:\JARVIS")
os.chdir(r"D:\JARVIS")

import tempfile
import subprocess
import threading
import re
import pyaudio
import ollama
import speech_recognition as sr
from faster_whisper import WhisperModel

# ── Constants ────────────────────────────────────────────────────────────────────
OLLAMA_MODEL = "llama3.2:3b"
PIPER_EXE    = r"D:\JARVIS\piper_extracted\piper\piper.exe"
# JARVIS Iron Man voice (download from HuggingFace — see README)
JARVIS_VOICE = r"D:\JARVIS\voices\jarvis-medium.onnx"
ALAN_VOICE   = r"D:\JARVIS\voices\en_GB-alan-medium.onnx"
# Switch to JARVIS_VOICE once downloaded, keep ALAN_VOICE as fallback
VOICE_MODEL  = JARVIS_VOICE if os.path.exists(JARVIS_VOICE) else ALAN_VOICE
SAMPLE_RATE  = 16000

WAKE_WORDS  = ["hey jarvis", "okay jarvis", "hi jarvis", "jarvis"]
SLEEP_WORDS = [
    "standby mode", "stand by mode", "go to standby", "standby",
    "go to sleep", "sleep mode", "bye jarvis", "goodbye jarvis", "thats all jarvis",
]

# ── STT Setup ────────────────────────────────────────────────────────────────────
import struct, math, wave
print("Loading Whisper model...")
whisper = WhisperModel("small.en", device="cpu", compute_type="int8")

# SpeechRecognition kept only for sr.Microphone index lookup
recognizer = sr.Recognizer()

def _find_best_mic():
    """Score every input device, prefer USB/headset over built-in laptop array."""
    pa         = pyaudio.PyAudio()
    best       = None
    best_score = -99
    print("\n[Mic] Available input devices:")
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info["maxInputChannels"] < 1:
            continue
        name  = info["name"].lower()
        score = 0
        if "usb"         in name: score += 4
        if "headset"     in name: score += 3
        if "headphone"   in name: score += 3
        if "microphone"  in name: score += 2
        if "external"    in name: score += 2
        if "built-in"    in name: score -= 1
        if "array"       in name: score -= 2
        if "stereo mix"  in name: score -= 9
        if "what u hear" in name: score -= 9
        print(f"  [{i}] {info['name']}  ch={info['maxInputChannels']}  score={score}")
        if score > best_score:
            best_score = score
            best = i
    pa.terminate()
    print(f"[Mic] Auto-selected index {best}  (override: set MIC_INDEX=n in .env)\n")
    return best

_MIC_INDEX = int(os.getenv("MIC_INDEX", _find_best_mic()))
# sr_mic kept for compatibility with any code that uses sr.Microphone
sr_mic = sr.Microphone(device_index=_MIC_INDEX, sample_rate=SAMPLE_RATE)

# ── RMS-based VAD constants ───────────────────────────────────────────────────
_CHUNK        = 1024          # frames per PyAudio read
_PA_FORMAT    = pyaudio.paInt16
_PA_CHANNELS  = 1
_SILENCE_RMS  = 300           # updated by calibration
_SPEECH_MULT  = 1.6           # lowered: voice only needs to be 1.6x noise floor
_SILENCE_SECS = 1.0           # seconds of quiet that ends a phrase
_MAX_SECS     = 20            # hard cap on recording length
_MIN_SECS     = 0.3           # discard clips shorter than this
_ABS_MIN_RMS  = 120           # absolute minimum RMS to count as speech (catches quiet rooms)

def _rms(data: bytes) -> float:
    shorts = struct.unpack(f"{len(data)//2}h", data)
    return math.sqrt(sum(s*s for s in shorts) / max(len(shorts), 1))

def _calibrate_noise(seconds: float = 1.5):
    """Measure ambient RMS and set silence floor."""
    global _SILENCE_RMS
    pa     = pyaudio.PyAudio()
    stream = pa.open(format=_PA_FORMAT, channels=_PA_CHANNELS,
                     rate=SAMPLE_RATE, input=True,
                     input_device_index=_MIC_INDEX,
                     frames_per_buffer=_CHUNK)
    samples = []
    for _ in range(int(SAMPLE_RATE / _CHUNK * seconds)):
        samples.append(_rms(stream.read(_CHUNK, exception_on_overflow=False)))
    stream.stop_stream(); stream.close(); pa.terminate()
    # Use quietest 70% as true noise floor — no extra multiplier here
    floor        = sorted(samples)[:int(len(samples) * 0.7)]
    raw_floor    = sum(floor) / len(floor)
    _SILENCE_RMS = max(raw_floor, 50)   # floor in absolute terms, minimum 50
    speech_thresh = max(_SILENCE_RMS * _SPEECH_MULT, _ABS_MIN_RMS)
    print(f"[Mic] Calibrated  noise_floor={_SILENCE_RMS:.0f}  "
          f"speech_threshold={speech_thresh:.0f}  "
          f"(mult={_SPEECH_MULT}x)")
    print(f"[Mic] Tip: if JARVIS misses you, speak louder or lower _SPEECH_MULT in jarvis.py")

print("Calibrating mic — stay silent for 1.5 s...")
_calibrate_noise(1.5)
print("JARVIS is online.\n")

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
_tts_lock            = threading.Lock()   # ensures only ONE voice at a time

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


# ── STT ─────────────────────────────────────────────────────────────────────────

# Commands JARVIS must never reject no matter how short
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

# Known Whisper hallucinations from silence / ambient noise
_HALLUCINATIONS = {
    "thank you for watching", "thanks for watching", "thank you so much",
    "see you next time", "like and subscribe", "please subscribe",
    "subtitles by", "subtitled by", "captions by",
    "good august", "august", "foreign language", "foreign",
    "you", "the", "i", "a", "and", "or",
    "um", "uh", "hmm", "hm", "ah", "mm",
    "music", "applause", "laughter",
    "[music]", "[applause]", "(music)", "(applause)", "[foreign]",
}


def _record_until_silence(max_seconds: float = _MAX_SECS,
                           for_wakeword: bool = False) -> bytes | None:
    """
    Record directly via PyAudio using RMS-based VAD.
    Returns raw PCM bytes (16-bit mono 16kHz), or None if nothing was spoken.

    This bypasses SpeechRecognition entirely — SR's dynamic energy threshold
    was the main cause of missed/cut commands.
    """
    pa     = pyaudio.PyAudio()
    stream = pa.open(format=_PA_FORMAT, channels=_PA_CHANNELS,
                     rate=SAMPLE_RATE, input=True,
                     input_device_index=_MIC_INDEX,
                     frames_per_buffer=_CHUNK)

    # Use absolute minimum so quiet rooms still trigger
    speech_threshold  = max(_SILENCE_RMS * _SPEECH_MULT, _ABS_MIN_RMS)
    silence_chunks    = int(_SILENCE_SECS * SAMPLE_RATE / _CHUNK)
    max_chunks        = int(max_seconds  * SAMPLE_RATE / _CHUNK)
    # For wake word we wait longer for speech to start
    max_wait_chunks   = int((3.0 if for_wakeword else 8.0) * SAMPLE_RATE / _CHUNK)

    frames            = []
    speaking          = False
    silent_count      = 0
    waited            = 0

    peak_rms = 0.0
    try:
        while True:
            data = stream.read(_CHUNK, exception_on_overflow=False)
            rms  = _rms(data)
            if rms > peak_rms:
                peak_rms = rms

            if not speaking:
                if rms > speech_threshold:
                    speaking = True
                    # Include 3 pre-speech chunks so we don't clip the start
                    frames.append(data)
                else:
                    waited += 1
                    if waited % 20 == 0:   # print every ~0.5s so user knows it's alive
                        print(f"[VAD] waiting... rms={rms:.0f} need>{speech_threshold:.0f}")
                    if waited > max_wait_chunks:
                        print(f"[VAD] timeout — peak rms was {peak_rms:.0f}, "
                              f"threshold was {speech_threshold:.0f}")
                        return None   # nobody spoke
            else:
                frames.append(data)
                # End of speech: RMS drops below 55% of threshold
                if rms < speech_threshold * 0.55:
                    silent_count += 1
                    if silent_count >= silence_chunks:
                        break         # natural end of phrase
                else:
                    silent_count = 0
                if len(frames) >= max_chunks:
                    break             # hard cap

        duration = len(frames) * _CHUNK / SAMPLE_RATE
        if duration < _MIN_SECS:
            return None
        return b"".join(frames)

    finally:
        stream.stop_stream()
        stream.close()
        pa.terminate()


def _pcm_to_wav_file(pcm: bytes) -> str:
    """Write raw PCM to a temp WAV file and return its path."""
    tmp = tempfile.mktemp(suffix=".wav")
    with wave.open(tmp, "wb") as wf:
        wf.setnchannels(_PA_CHANNELS)
        wf.setsampwidth(2)          # 16-bit = 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm)
    return tmp


def _whisper_transcribe(wav_path: str) -> str:
    """Run Whisper on a WAV file and return cleaned text or empty string."""
    segments, info = whisper.transcribe(
        wav_path,
        language="en",
        beam_size=3,
        no_speech_threshold=0.45,
        log_prob_threshold=-1.0,
        compression_ratio_threshold=2.4,
        condition_on_previous_text=False,
        word_timestamps=False,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=400,
            speech_pad_ms=300,
            threshold=0.35,
        ),
    )
    segs = list(segments)
    if not segs:
        return ""

    # Very low language confidence = probably not English speech
    if info.language_probability < 0.45:
        print(f"[STT] ✗ lang_prob={info.language_probability:.2f}")
        return ""

    avg_lp = sum(s.avg_logprob for s in segs) / len(segs)
    if avg_lp < -1.3:
        print(f"[STT] ✗ low confidence avg_logprob={avg_lp:.2f}")
        return ""

    text    = " ".join(s.text.strip() for s in segs)
    cleaned = text.strip().strip(".!?, ").lower()
    return cleaned


def _filter(text: str) -> str:
    """Apply always-accept / hallucination filter. Returns text or empty."""
    if not text:
        return ""

    # Always accept — never filtered
    for phrase in _ALWAYS_ACCEPT:
        if text == phrase or text.startswith(phrase + " "):
            print(f"[STT] ✓ (always) '{text}'")
            return text

    # Exact hallucination match
    if text in _HALLUCINATIONS:
        print(f"[STT] ✗ hallucination '{text}'")
        return ""

    # Must have at least one real alphabetic word of 2+ chars
    real = [w for w in text.split() if w.isalpha() and len(w) >= 2]
    if not real:
        print(f"[STT] ✗ no real words '{text}'")
        return ""

    # Minimum 3 characters total
    if len(text) < 3:
        print(f"[STT] ✗ too short '{text}'")
        return ""

    print(f"[STT] ✓ '{text}'")
    return text


# ── Public STT API ────────────────────────────────────────────────────────────

_stt_lock = threading.Lock()   # one recording at a time


def listen_once(timeout: int = 10) -> str:
    """
    Record one voice phrase and return transcribed text.
    Uses direct PyAudio — no SpeechRecognition VAD drift.
    `timeout` sets how long we wait for speech to start (seconds).
    """
    if not _stt_lock.acquire(timeout=3):
        return ""
    try:
        notify_listening(True)
        thresh = max(_SILENCE_RMS * _SPEECH_MULT, _ABS_MIN_RMS)
        print(f"[Listen] noise_floor={_SILENCE_RMS:.0f}  "
              f"speech_threshold={thresh:.0f}  (speak louder than {thresh:.0f})")

        pcm = _record_until_silence(max_seconds=_MAX_SECS, for_wakeword=False)
        if pcm is None:
            return ""

        wav = _pcm_to_wav_file(pcm)
        try:
            text = _filter(_whisper_transcribe(wav))
        finally:
            try: os.unlink(wav)
            except: pass

        if text:
            print(f"You: {text}")
        return text

    except Exception as e:
        print(f"[listen_once] {e}")
        return ""
    finally:
        notify_listening(False)
        _stt_lock.release()


# Recalibrate noise floor every 45 seconds in background
_last_cal = 0.0
def _maybe_recalibrate():
    global _last_cal
    if time.time() - _last_cal > 45 and _stt_lock.acquire(blocking=False):
        try:
            _calibrate_noise(0.8)
            _last_cal = time.time()
        except Exception:
            pass
        finally:
            _stt_lock.release()


def listen_for_wakeword() -> bool:
    """
    Non-blocking poll for wake word.
    Records up to 3 s, runs Whisper, checks for wake words.
    Skips filter — we want maximum sensitivity here.
    """
    _maybe_recalibrate()

    if not _stt_lock.acquire(timeout=0.5):
        return False
    try:
        pcm = _record_until_silence(max_seconds=5, for_wakeword=True)
        if pcm is None:
            return False

        wav = _pcm_to_wav_file(pcm)
        try:
            text = _whisper_transcribe(wav)   # no filter — raw text
        finally:
            try: os.unlink(wav)
            except: pass

        if text:
            print(f"[Wake] heard: '{text}'")
        return any(w in text for w in WAKE_WORDS)

    except Exception:
        return False
    finally:
        _stt_lock.release()


# ── TTS ──────────────────────────────────────────────────────────────────────────
def _tts_to_wav(text: str, tmp_wav: str):
    subprocess.run(
        [PIPER_EXE, "--model", VOICE_MODEL, "--output_file", tmp_wav],
        input=text.encode(), capture_output=True
    )


def speak_raw(text: str):
    """Speak without interrupt detection. Waits for tts_lock so never overlaps."""
    global current_process, is_speaking
    text = re.sub(r'[`*#_]', '', text).strip()
    if not text:
        return
    print(f"JARVIS: {text}")
    with _tts_lock:                       # block until any other speech is done
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_wav = f.name
        try:
            _tts_to_wav(text, tmp_wav)
            is_speaking     = True
            current_process = subprocess.Popen(
                ["powershell", "-c", f'(New-Object Media.SoundPlayer "{tmp_wav}").PlaySync()']
            )
            current_process.wait()
        finally:
            is_speaking = False
            if os.path.exists(tmp_wav):
                try: os.unlink(tmp_wav)
                except: pass


def speak(text: str) -> tuple[bool, str]:
    """Speak with interrupt detection. Returns (was_interrupted, interrupted_text).
    Acquires tts_lock — will wait if speak_raw is currently playing."""
    global is_speaking, interrupted, interrupted_text, current_process
    text = re.sub(r'```[\s\S]*?```', 'I have saved the code to your workspace folder sir.', text)
    text = re.sub(r'[`*#_]', '', text)
    text = ' '.join(text.split())
    if not text.strip():
        text = "Done sir. Please check your workspace folder."
    print(f"JARVIS: {text}")
    with _tts_lock:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_wav = f.name
        try:
            _tts_to_wav(text, tmp_wav)
            is_speaking      = True
            interrupted      = False
            interrupted_text = ""
            listener = threading.Thread(target=_voice_interrupt_listener, daemon=True)
            listener.start()
            current_process = subprocess.Popen(
                ["powershell", "-c", f'(New-Object Media.SoundPlayer "{tmp_wav}").PlaySync()']
            )
            current_process.wait()
            is_speaking = False
            listener.join(timeout=1)
        finally:
            is_speaking = False
            if os.path.exists(tmp_wav):
                try: os.unlink(tmp_wav)
                except: pass
    return interrupted, interrupted_text


def _voice_interrupt_listener():
    """Listen for interruptions using direct PyAudio VAD (same as listen_once)."""
    global is_speaking, interrupted, interrupted_text, current_process

    time.sleep(2.0)   # let speaker reverb die down first

    while is_speaking:
        if not _stt_lock.acquire(timeout=0.3):
            time.sleep(0.1)
            continue
        try:
            pcm = _record_until_silence(max_seconds=6, for_wakeword=False)
            if pcm is None:
                continue
            wav = _pcm_to_wav_file(pcm)
            try:
                text = _whisper_transcribe(wav)
            finally:
                try: os.unlink(wav)
                except: pass

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
            acquired = False


# ── Notifications ─────────────────────────────────────────────────────────────────
def post_notification(text: str):
    """Queue a notification to be spoken — works even in standby."""
    with _notification_lock:
        if text not in _notification_queue:
            _notification_queue.append(text)
            notification_event.set()
    print(f"[Notif] Queued: {text}")
    # Update dashboard activity log
    try:
        _type = "System"
        tl = text.lower()
        if "email" in tl:                      _type = "Gmail"
        elif "slack" in tl:                    _type = "Slack"
        elif "telegram" in tl or "call" in tl: _type = "Telegram"
        elif "tea" in tl:                      _type = "Tea"
        elif "motion" in tl or "intruder" in tl: _type = "Camera"
        elif "timer" in tl or "alarm" in tl:   _type = "Timer"
        elif "calendar" in tl:                 _type = "Calendar"
        elif "drive" in tl or "backup" in tl:  _type = "Drive"
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
    """Interrupt current speech if a notification arrives."""
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
    """Speak queued notifications immediately — even in standby."""
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
        conversation_history.append({"role": "user", "content": user_text})
        response = ollama.chat(model=OLLAMA_MODEL, messages=conversation_history)
        reply    = response["message"]["content"].strip()
        conversation_history.append({"role": "assistant", "content": reply})
        remember(user_text, reply)
        notify_response(reply)
        return reply


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
        resp = ollama.chat(model=OLLAMA_MODEL, messages=[
            {"role": "system", "content":
                f"You are JARVIS, AI assistant of Shivank Pandey. "
                f"You are chatting with {caller_name} on Telegram. "
                f"Shivank is unavailable. Be polite, collect their message, be brief."},
            *history,
            {"role": "user", "content": message},
        ])
        return resp["message"]["content"].strip()

    async def summarize(caller_name, messages):
        conv = "\n".join([
            f"{'Caller' if m['role']=='user' else 'JARVIS'}: {m['content']}"
            for m in messages])
        resp = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content":
            f"You are JARVIS. Summarize this conversation with {caller_name} for Shivank in 2 sentences.\n\n{conv}"}])
        return resp["message"]["content"].strip()

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
                resp  = ollama.chat(model=OLLAMA_MODEL, messages=[{"role": "user", "content":
                    f"You are JARVIS. One sentence: notify Shivank of missed call from {caller_name} at {call_time}."}])
                brief = resp["message"]["content"].strip()
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
        # Speak any queued notifications even in standby
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
                if silence_count >= 5:   # ~5 missed listens before asking
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

# Dashboard must load first (other agents call notify_* functions)
try:
    from dashboard_server import (
        start          as dashboard_start,
        notify_command, notify_response,
        notify_listening, notify_activity,
        notify_awake,  notify_camera, notify_motion,
    )
    dashboard_start()
    print("[Boot] Dashboard server on ws://localhost:8765")
except Exception as e:
    print(f"[Boot] Dashboard error: {e}")
    def notify_command(t):     pass
    def notify_response(t):    pass
    def notify_listening(a):   pass
    def notify_activity(t, m): pass
    def notify_awake(a):       pass
    def notify_camera(a):      pass
    def notify_motion():       pass

# Timer
try:
    from timer_agent import set_notify as timer_set_notify
    timer_set_notify(post_notification)
    print("[Boot] Timer agent ready")
except Exception as e:
    print(f"[Boot] Timer error: {e}")

# IoT
try:
    from iot_agent import set_notify as iot_set_notify, trigger_alert
    iot_set_notify(post_notification)
    print("[Boot] IoT agent ready")
except Exception as e:
    print(f"[Boot] IoT error: {e}")

# Camera — auto-start on boot, auto-retry if webcam not plugged in yet
def _boot_camera():
    try:
        from camera_agent import (
            set_notify        as cam_set_notify,
            set_iot_trigger   as cam_set_iot,
            set_dashboard_motion,
            set_dashboard_camera,
            start             as cam_start,
        )
        from camera_stream import start as stream_start

        # Wire all callbacks
        cam_set_notify(post_notification)
        set_dashboard_motion(notify_motion)
        set_dashboard_camera(notify_camera)
        try:
            from iot_agent import trigger_alert as _ta
            cam_set_iot(_ta)
        except Exception:
            pass

        # Try to start right away
        if cam_start():
            stream_start()
            print("[Boot] Camera auto-started — motion detection ON")
            print("[Boot] Camera stream → http://localhost:8766/stream")
            return

        # Webcam not found yet — poll in background until plugged in
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
                        stream_start()
                        print("[Camera] Webcam detected — auto-started!")
                        post_notification(
                            "Webcam connected sir. "
                            "Camera and motion detection are now active."
                        )
                        return

        threading.Thread(target=_watch_for_camera, daemon=True).start()

    except Exception as e:
        print(f"[Boot] Camera error: {e}")

_boot_camera()

# Sensors (DHT11 + Flame)
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
    print("[Boot] Sensor agent ready (DHT11 + Flame)")
except Exception as e:
    print(f"[Boot] Sensor error: {e}")

# Google Calendar (CalDAV)
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

# Google Drive (rclone)
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

# Contacts
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

# Email sender
try:
    from email_sender import (
        set_speak     as email_set_speak,
        set_listen    as email_set_listen,
        set_notify    as email_set_notify,
        set_dashboard as email_set_dashboard,
    )
    email_set_speak(speak_raw)
    email_set_listen(listen_once)
    email_set_notify(post_notification)
    email_set_dashboard(notify_activity)
    print("[Boot] Email sender ready")
except Exception as e:
    print(f"[Boot] Email sender error: {e}")

# Gmail watcher
try:
    from gmail_agent import start_email_watcher, set_notify as gmail_set_notify
    gmail_set_notify(post_notification)
    start_email_watcher()
    print("[Boot] Gmail watcher started")
except Exception as e:
    print(f"[Boot] Gmail error: {e}")

# Slack watcher
try:
    from slack_agent import start_slack_watcher, set_notify as slack_set_notify
    slack_set_notify(post_notification)
    start_slack_watcher()
    print("[Boot] Slack watcher started")
except Exception as e:
    print(f"[Boot] Slack error: {e}")

# Travel (Amadeus API)
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
except Exception as e:
    print(f"[Boot] Travel agent error: {e}")

# Flight agent
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

# Zepto Café
try:
    from zepto_agent import (
        set_speak    as zepto_set_speak,
        set_listen   as zepto_set_listen,
        set_notify   as zepto_set_notify,
        is_logged_in as zepto_logged_in,
    )
    zepto_set_speak(speak_raw)
    zepto_set_listen(listen_once)
    zepto_set_notify(post_notification)
    if zepto_logged_in():
        print("[Boot] Zepto Café ready")
    else:
        print("[Boot] Zepto Café ready — run: python zepto_agent.py --login to set up")
except Exception as e:
    print(f"[Boot] Zepto error: {e}")

# Swiggy (Playwright)
try:
    from swiggy_agent import (
        set_speak    as swiggy_set_speak,
        set_listen   as swiggy_set_listen,
        set_notify   as swiggy_set_notify,
        is_logged_in as swiggy_logged_in,
    )
    swiggy_set_speak(speak_raw)
    swiggy_set_listen(listen_once)
    swiggy_set_notify(post_notification)
    if swiggy_logged_in():
        print("[Boot] Swiggy ready")
    else:
        print("[Boot] Swiggy ready — run: python swiggy_agent.py --login to set up")
except Exception as e:
    print(f"[Boot] Swiggy error: {e}")

# Morning briefing
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

# Notification threads
threading.Thread(target=_notification_killer,  daemon=True).start()
threading.Thread(target=_notification_speaker, daemon=True).start()
print("[Boot] Notification threads started")

# Telegram watcher
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
        on_session_end()
        audio_interface.terminate()
        break
    except Exception as e:
        print(f"Main error: {e}")
        continue