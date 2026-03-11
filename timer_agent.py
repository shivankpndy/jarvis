import threading
import time
import re
from datetime import datetime, timedelta

# Global notify function — set by jarvis.py on startup
_notify_func = None

def set_notify(func):
    global _notify_func
    _notify_func = func

def _notify(msg):
    if _notify_func:
        _notify_func(msg)
    else:
        print(f"TIMER: {msg}")


def parse_timer(text):
    text = text.lower()
    patterns = [
        (r'(\d+)\s*hour[s]?\s*(\d+)\s*minute[s]?', lambda m: int(m.group(1))*3600 + int(m.group(2))*60),
        (r'(\d+)\s*hour[s]?',                        lambda m: int(m.group(1))*3600),
        (r'(\d+)\s*minute[s]?',                      lambda m: int(m.group(1))*60),
        (r'(\d+)\s*second[s]?',                      lambda m: int(m.group(1))),
        (r'half\s*an?\s*hour',                        lambda m: 1800),
        (r'quarter\s*hour',                           lambda m: 900),
    ]
    for pattern, calculator in patterns:
        match = re.search(pattern, text)
        if match:
            return calculator(match)
    return None


def parse_alarm(text):
    text = text.lower()
    match = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)?', text)
    if match:
        hour   = int(match.group(1))
        minute = int(match.group(2))
        period = match.group(3)
        if period == 'pm' and hour != 12: hour += 12
        if period == 'am' and hour == 12: hour = 0
        now   = datetime.now()
        alarm = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if alarm <= now: alarm += timedelta(days=1)
        return (alarm - now).total_seconds()

    match = re.search(r'(\d{1,2})\s*(am|pm)', text)
    if match:
        hour   = int(match.group(1))
        period = match.group(2)
        if period == 'pm' and hour != 12: hour += 12
        if period == 'am' and hour == 12: hour = 0
        now   = datetime.now()
        alarm = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if alarm <= now: alarm += timedelta(days=1)
        return (alarm - now).total_seconds()

    return None


def format_duration(seconds):
    if seconds >= 3600:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        if m: return f"{h} hour{'s' if h>1 else ''} and {m} minute{'s' if m>1 else ''}"
        return f"{h} hour{'s' if h>1 else ''}"
    elif seconds >= 60:
        m = int(seconds // 60)
        return f"{m} minute{'s' if m>1 else ''}"
    else:
        return f"{int(seconds)} second{'s' if seconds>1 else ''}"


def start_timer(seconds, label):
    def _run():
        print(f"Timer started: {label} — {format_duration(seconds)}")
        time.sleep(seconds)
        message = f"Sir, your {label} is complete."
        print(f"Timer done: {message}")
        _notify(message)
    threading.Thread(target=_run, daemon=True).start()


def handle(user_text, notify_func=None):
    """Handle timer/alarm. notify_func overrides global if provided."""
    global _notify_func
    if notify_func:
        _notify_func = notify_func

    text     = user_text.lower()
    is_alarm = any(w in text for w in ["alarm", "wake me", "wake up", "remind me at"])
    is_timer = any(w in text for w in ["timer", "remind me in", "set a timer",
                                        "minutes", "seconds", "hours", "timer of"])

    if is_alarm:
        seconds = parse_alarm(text)
        if seconds:
            start_timer(seconds, "alarm")
            return f"Alarm set sir. I will alert you in {format_duration(seconds)}."
        return "I could not understand the alarm time sir. Please say something like set alarm at 7am."

    if is_timer:
        seconds = parse_timer(text)
        if seconds:
            label = "timer"
            start_timer(seconds, label)
            return f"Timer set for {format_duration(seconds)} sir."
        return "I could not understand the duration sir. Please say something like set a timer for 5 minutes."

    return ""


TIMER_KEYWORDS = ["set a timer", "set timer", "timer for", "timer of",
                  "remind me in", "set an alarm", "set alarm", "alarm at",
                  "alarm for", "wake me at", "wake me up", "remind me at",
                  "in 1 minute", "in 2 minutes", "in 5 minutes",
                  "in 10 minutes", "in 15 minutes", "in 30 minutes",
                  "in an hour", "in 1 hour", "after 5 minutes"]