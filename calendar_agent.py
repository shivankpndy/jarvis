"""
JARVIS Calendar Agent
Google Calendar via CalDAV — uses your existing Gmail App Password.
No OAuth, no Cloud Console needed.

Install: pip install caldav vobject
"""
import re
import threading
import datetime
import os
from dotenv import load_dotenv
import ollama

load_dotenv(r"D:\JARVIS\.env")

GMAIL_EMAIL    = os.getenv("GMAIL_EMAIL", "")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
CALDAV_URL     = f"https://www.google.com/calendar/dav/{GMAIL_EMAIL}/"
BRAIN_MODEL    = "llama3.2:3b"

_speak_fn  = None
_listen_fn = None
_notify_fn = None
_cal       = None
_connected = False


def set_speak(fn):  global _speak_fn;  _speak_fn  = fn
def set_listen(fn): global _listen_fn; _listen_fn = fn
def set_notify(fn): global _notify_fn; _notify_fn = fn


def _speak(text):
    if _speak_fn: _speak_fn(text)
    else: print(f"[Calendar] {text}")


def _listen(timeout=12) -> str:
    if _listen_fn: return _listen_fn(timeout=timeout) or ""
    return ""


# ── Connection ──────────────────────────────────────────────────────────────────
def _connect() -> bool:
    global _cal, _connected
    try:
        import caldav
        client    = caldav.DAVClient(
            url=CALDAV_URL,
            username=GMAIL_EMAIL,
            password=GMAIL_PASSWORD,
        )
        principal  = client.principal()
        calendars  = principal.calendars()
        if not calendars:
            print("[Calendar] No calendars found on account")
            return False
        _cal       = calendars[0]
        _connected = True
        print(f"[Calendar] Connected — {len(calendars)} calendar(s) found")
        return True
    except ImportError:
        print("[Calendar] caldav not installed — run: pip install caldav vobject")
        return False
    except Exception as e:
        print(f"[Calendar] Connection error: {e}")
        _connected = False
        return False


def _ensure() -> bool:
    if _connected and _cal:
        return True
    return _connect()


# ── Fetch ───────────────────────────────────────────────────────────────────────
def _parse_event(event) -> dict | None:
    try:
        comp    = event.vobject_instance.vevent
        summary = str(comp.summary.value) if hasattr(comp, "summary") else "Untitled"
        dtstart = comp.dtstart.value
        if isinstance(dtstart, datetime.datetime):
            day_str  = dtstart.strftime("%A %B %d")
            time_str = dtstart.strftime("%I:%M %p")
        elif isinstance(dtstart, datetime.date):
            day_str  = dtstart.strftime("%A %B %d")
            time_str = "All day"
        else:
            day_str  = str(dtstart)
            time_str = ""
        return {"title": summary, "day": day_str, "time": time_str}
    except Exception:
        return None


def _fetch(start: datetime.datetime, end: datetime.datetime) -> list[dict]:
    if not _ensure():
        return []
    try:
        raw    = _cal.date_search(start=start, end=end, expand=True)
        events = [_parse_event(e) for e in raw]
        return [e for e in events if e]
    except Exception as e:
        print(f"[Calendar] Fetch error: {e}")
        return []


def get_today() -> list[dict]:
    today = datetime.date.today()
    return _fetch(
        datetime.datetime.combine(today, datetime.time.min),
        datetime.datetime.combine(today, datetime.time.max),
    )


def get_week() -> list[dict]:
    today = datetime.date.today()
    return _fetch(
        datetime.datetime.combine(today, datetime.time.min),
        datetime.datetime.combine(today + datetime.timedelta(days=7), datetime.time.max),
    )


# ── Add event ───────────────────────────────────────────────────────────────────
def _parse_dt(text: str) -> datetime.datetime | None:
    """Use Ollama to parse natural language datetime."""
    try:
        now    = datetime.datetime.now()
        prompt = (
            f"Extract date and time from this text.\n"
            f"Today is {now.strftime('%Y-%m-%d')}, current time {now.strftime('%H:%M')}.\n"
            f"Text: {text}\n"
            f"Rules:\n"
            f"- If no time given, use 09:00\n"
            f"- If no date given, use today\n"
            f"- 'tomorrow' = {(now + datetime.timedelta(days=1)).strftime('%Y-%m-%d')}\n"
            f"Return ONLY this format, nothing else: YYYY-MM-DD HH:MM"
        )
        resp = ollama.chat(model=BRAIN_MODEL, messages=[{"role": "user", "content": prompt}])
        raw  = resp["message"]["content"].strip()
        # Extract just the datetime pattern
        m = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}', raw)
        if m:
            return datetime.datetime.strptime(m.group(), "%Y-%m-%d %H:%M")
        return None
    except Exception as e:
        print(f"[Calendar] Parse datetime error: {e}")
        return None


def add_event(title: str, dt: datetime.datetime, duration_mins: int = 60) -> bool:
    if not _ensure():
        return False
    try:
        import uuid
        end  = dt + datetime.timedelta(minutes=duration_mins)
        ical = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{uuid.uuid4()}@jarvis\r\n"
            f"DTSTART:{dt.strftime('%Y%m%dT%H%M%S')}\r\n"
            f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}\r\n"
            f"SUMMARY:{title}\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        _cal.save_event(ical)
        print(f"[Calendar] Added: '{title}' at {dt}")
        return True
    except Exception as e:
        print(f"[Calendar] Add event error: {e}")
        return False


# ── Voice commands ───────────────────────────────────────────────────────────────
def handle(user_text: str) -> str:
    t = user_text.lower()

    # Today
    if any(k in t for k in ["today", "my day", "today's events",
                             "what's today", "calendar today", "do i have anything today"]):
        events = get_today()
        if not events:
            return "You have nothing scheduled for today Shivank."
        out = [f"You have {len(events)} event{'s' if len(events) != 1 else ''} today Shivank."]
        for e in events:
            out.append(f"{e['time']} — {e['title']}.")
        return " ".join(out)

    # This week
    if any(k in t for k in ["this week", "week", "upcoming", "next few days",
                             "what's coming up", "do i have anything this week"]):
        events = get_week()
        if not events:
            return "Nothing coming up this week Shivank."
        out = [f"You have {len(events)} event{'s' if len(events) != 1 else ''} this week Shivank."]
        for e in events[:5]:
            out.append(f"{e['day']} at {e['time']} — {e['title']}.")
        if len(events) > 5:
            out.append(f"And {len(events) - 5} more.")
        return " ".join(out)

    # Add event — runs conversational flow in thread
    if any(k in t for k in ["add", "schedule", "create", "book",
                             "set a meeting", "set a reminder", "new meeting", "new event"]):
        threading.Thread(target=_add_flow, args=(user_text,), daemon=True).start()
        return ""

    return ""


def _add_flow(user_text: str):
    t = user_text.lower()

    # Try extracting title from command
    title = None
    for pat in [
        r'(?:add|schedule|create|book|set)\s+(?:a\s+)?(?:meeting|event|call|reminder|appointment)?\s*(?:with\s+[\w ]+?)?\s*(?:about\s+)?(.+?)(?:\s+(?:on|at|for|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{1,2}))',
        r'(?:add|schedule|create|book)\s+(?:a\s+)?(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip().rstrip(" .")
            if len(candidate) >= 3:
                title = candidate
                break

    if not title:
        _speak("What's the name of the event Shivank?")
        title = _listen()
        if not title:
            _speak("Event creation cancelled.")
            return

    # Parse datetime from original command
    dt = _parse_dt(user_text)

    if not dt:
        _speak(f"When is '{title}'? Tell me the date and time.")
        when = _listen()
        if not when:
            _speak("Event creation cancelled.")
            return
        dt = _parse_dt(when)
        if not dt:
            _speak("I couldn't understand that date and time. Event creation cancelled.")
            return

    time_str = dt.strftime("%A %B %d at %I:%M %p")
    _speak(f"Adding '{title}' on {time_str}. Shall I confirm?")

    confirm = _listen()
    if not confirm:
        _speak("No response — event creation cancelled.")
        return
    if any(w in confirm.lower() for w in ["no", "cancel", "stop", "don't"]):
        _speak("Event creation cancelled.")
        return

    ok = add_event(title, dt)
    if ok:
        _speak(f"'{title}' has been added to your Google Calendar Shivank.")
        if _notify_fn:
            _notify_fn(f"Calendar: '{title}' added for {time_str}")
    else:
        _speak(
            "I couldn't add the event. Please make sure CalDAV is set up — "
            "your Gmail email and App Password should be in the dot env file."
        )


# ── Startup ─────────────────────────────────────────────────────────────────────
def start():
    """Connect to CalDAV in background thread so startup isn't blocked."""
    threading.Thread(target=_connect, daemon=True).start()