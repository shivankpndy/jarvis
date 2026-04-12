import sounddevice as sd

try:
    sd.rec(1000, samplerate=44100, channels=1)
    sd.wait()
    print("Mic available")
except Exception as e:
    print("Mic blocked by another app:", e)