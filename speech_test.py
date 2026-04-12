"""
JARVIS Mic Diagnostic — run this FIRST before jarvis.py
python test_mic.py

Tells you exactly:
1. Which mic devices are available
2. Whether Google SR can hear you
3. What it transcribes
4. Any errors
"""
import speech_recognition as sr
import pyaudio

print("=" * 60)
print("  JARVIS MIC DIAGNOSTIC")
print("=" * 60)

# ── Step 1: List ALL audio devices ───────────────────────────────
print("\n[1] PyAudio devices:")
pa = pyaudio.PyAudio()
input_devices = []
for i in range(pa.get_device_count()):
    info = pa.get_device_info_by_index(i)
    if info["maxInputChannels"] > 0:
        print(f"    [{i}] {info['name']}  "
              f"channels={info['maxInputChannels']}  "
              f"rate={int(info['defaultSampleRate'])}")
        input_devices.append(i)
pa.terminate()

if not input_devices:
    print("    ❌ NO INPUT DEVICES FOUND — check mic is plugged in")
    exit(1)

# ── Step 2: List SR microphones ───────────────────────────────────
print("\n[2] SpeechRecognition microphones:")
try:
    mics = sr.Microphone.list_microphone_names()
    for i, name in enumerate(mics):
        print(f"    [{i}] {name}")
except Exception as e:
    print(f"    ❌ Error listing SR mics: {e}")

# ── Step 3: Try opening each input device ────────────────────────
print("\n[3] Testing each input device:")
working = []
for idx in input_devices:
    try:
        mic = sr.Microphone(device_index=idx)
        with mic as src:
            pass   # just open and close
        print(f"    [{idx}] ✓ Opens OK")
        working.append(idx)
    except Exception as e:
        print(f"    [{idx}] ❌ Failed: {e}")

if not working:
    print("\n❌ No working mic found at all!")
    exit(1)

# ── Step 4: Pick best and test Google SR ─────────────────────────
print(f"\n[4] Using device index {working[0]} for live test")
print("    >>> Speak something when you see 'Listening...'")
print("    >>> (you have 5 seconds)")

r = sr.Recognizer()
r.energy_threshold = 300
r.dynamic_energy_threshold = False

mic = sr.Microphone(device_index=working[0])

print("\n    Calibrating...")
try:
    with mic as src:
        r.adjust_for_ambient_noise(src, duration=1)
    print(f"    Energy threshold after calibration: {r.energy_threshold:.0f}")
except Exception as e:
    print(f"    ❌ Calibration failed: {e}")
    exit(1)

print("\n    Listening...")
try:
    with mic as src:
        audio = r.listen(src, timeout=5, phrase_time_limit=8)
    print("    Audio captured — sending to Google...")
    try:
        text = r.recognize_google(audio, language="en-IN")
        print(f"\n    ✅ Google SR heard: '{text}'")
    except sr.UnknownValueError:
        print("    ⚠  Google SR: audio captured but could not understand it")
        print("       (mic works, but speech wasn't clear enough)")
    except sr.RequestError as e:
        print(f"    ❌ Google SR request failed: {e}")
        print("       Check internet connection!")
except sr.WaitTimeoutError:
    print("    ⚠  Timeout — no speech detected in 5 seconds")
    print("       Either mic is too quiet or energy_threshold is too high")
    print(f"       Current threshold: {r.energy_threshold:.0f}")
    print("       Try speaking louder, or the threshold needs lowering")
except Exception as e:
    print(f"    ❌ Listen failed: {e}")

print("\n" + "=" * 60)
print("  Copy the working device index into jarvis.py:")
print(f"  Set MIC_INDEX={working[0]} in your .env file")
print("=" * 60)