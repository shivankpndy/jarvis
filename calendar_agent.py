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
from llm import chat, chat_raw

load_dotenv(r"D:\JARVIS\.env")

GMAIL_EMAIL    = os.getenv("GMAIL_EMAIL", "")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
CALDAV_URL     = f"https://www.google.com/calendar/dav/{GMAIL_EMAIL}/"

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
    """
    Parse natural language datetime. Regex-first (instant), LLM as fallback.
    Handles: today, tomorrow, Monday, 'at 9am', 'at 7:43pm', '3 PM' etc.
    """
    now  = datetime.datetime.now()
    t    = text.lower()

    # ── Step 1: Resolve date ──────────────────────────────────────
    date = None
    if "today" in t:
        date = now.date()
    elif "day after tomorrow" in t:
        date = now.date() + datetime.timedelta(days=2)
    elif "tomorrow" in t:
        date = now.date() + datetime.timedelta(days=1)
    else:
        days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
        for i, d in enumerate(days):
            if d in t:
                diff = (i - now.weekday()) % 7
                if diff == 0: diff = 7
                date = now.date() + datetime.timedelta(days=diff)
                break

    if date is None:
        date = now.date()   # default today

    # ── Step 2: Resolve time ──────────────────────────────────────
    hour, minute = 9, 0   # default 9am

    # Match patterns like: 7:43pm, 7:43 pm, 9am, 9 am, 3pm, 3:00PM, 19:00
    time_patterns = [
        r'(\d{1,2}):(\d{2})\s*(am|pm)',   # 7:43pm
        r'(\d{1,2})\s*(am|pm)',             # 9am / 3 pm
        r'(\d{1,2}):(\d{2})',               # 19:00 / 7:43 (24h)
    ]
    for pat in time_patterns:
        m = re.search(pat, t)
        if m:
            groups = m.groups()
            h = int(groups[0])
            mn = int(groups[1]) if len(groups) > 1 and groups[1] and groups[1].isdigit() else 0
            meridiem = None
            for g in groups:
                if g in ("am", "pm"):
                    meridiem = g
                    break
            if meridiem == "pm" and h != 12:
                h += 12
            elif meridiem == "am" and h == 12:
                h = 0
            hour, minute = h, mn
            break

    dt = datetime.datetime.combine(date, datetime.time(hour, minute))
    print(f"[Calendar] Parsed datetime: {dt} from '{text}'")
    return dt


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
def _check_travel_reminder(events: list[dict]) -> str:
    """Check if any upcoming event is travel-related and prompt flight search."""
    try:
        from travel_agent import check_upcoming_travel
        reminder = check_upcoming_travel(events, days_ahead=2)
        return reminder or ""
    except Exception:
        return ""


def handle(user_text: str) -> str:
    t = user_text.lower()

    # ── Scheduling intent FIRST — must come before "today/week" view checks ──
    # "schedule X", "add X", "create X", "book X", "remind me", etc.
    SCHEDULE_TRIGGERS = [
        "add", "schedule", "create", "book", "set a meeting",
        "set a reminder", "new meeting", "new event", "remind me",
        "block time", "put on my calendar", "add to calendar",
        "set up a", "set up an",
    ]
    if any(t.startswith(k) or f" {k} " in f" {t} " for k in SCHEDULE_TRIGGERS):
        return _add_flow(user_text)

    # ── View today ────────────────────────────────────────────────────────────
    if any(k in t for k in ["today", "my day", "today's events",
                             "what's today", "calendar today", "do i have anything today"]):
        events = get_today()
        if not events:
            return "You have nothing scheduled for today Shivank."
        out = [f"You have {len(events)} event{'s' if len(events) != 1 else ''} today Shivank."]
        for e in events:
            out.append(f"{e['time']} — {e['title']}.")
        reminder = _check_travel_reminder(events)
        if reminder: out.append(reminder)
        return " ".join(out)

    # ── View this week ────────────────────────────────────────────────────────
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
        reminder = _check_travel_reminder(events)
        if reminder: out.append(reminder)
        return " ".join(out)

    return ""


def _ask_cal(prompt: str, timeout: int = 12) -> str:
    """Speak prompt → listen → fall back to terminal."""
    _speak(prompt)
    result = _listen(timeout=timeout)
    if result and len(result.strip()) > 1:
        return result.strip()
    print(f"\n[Calendar] {prompt}")
    print("[Calendar] Type your answer (or press Enter to cancel):")
    try:
        return input(">>> ").strip()
    except Exception:
        return ""


def _add_flow(user_text: str) -> str:
    t = user_text.lower()

    # Try extracting title from command
    title = None
    for pat in [
        r'(?:schedule|add|create|book|set up)\s+(?:a\s+|an\s+)?(?:team\s+)?(.+?)(?:\s+(?:on|at|for|tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{1,2})|$)',
        r'(?:add|schedule|create|book)\s+(?:a\s+|an\s+)?(.+)',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip().rstrip(" .")
            # Strip trailing time words
            candidate = re.sub(r'\s+(?:on|at|for|tomorrow|today|this|next)\s*.*$', '', candidate, flags=re.IGNORECASE).strip()
            if len(candidate) >= 2:
                title = candidate.title()
                break

    if not title:
        title = _ask_cal("What's the name of the event?")
        if not title:
            _speak("Event creation cancelled.")
            return "Event creation cancelled."

    # Parse datetime from original command
    dt = _parse_dt(user_text)

    if not dt:
        when = _ask_cal(f"When is '{title}'? Tell me the date and time.")
        if not when:
            _speak("Event creation cancelled.")
            return "Event creation cancelled."
        dt = _parse_dt(when)
        if not dt:
            _speak("I couldn't understand that date. Event creation cancelled.")
            return "Could not parse the date and time."

    time_str = dt.strftime("%A %B %d at %I:%M %p")
    confirm  = _ask_cal(f"Adding '{title}' on {time_str}. Confirm? Say yes or cancel.")

    if not confirm or any(w in confirm.lower() for w in ["no", "cancel", "stop", "don't"]):
        _speak("Event creation cancelled.")
        return "Event creation cancelled."

    ok = add_event(title, dt)
    if ok:
        msg = f"'{title}' added to your Google Calendar for {time_str} sir."
        _speak(msg)
        if _notify_fn: _notify_fn(f"Calendar: '{title}' → {time_str}")
        return msg
    else:
        msg = (
            "I couldn't add the event. Make sure GMAIL_EMAIL and "
            "GMAIL_APP_PASSWORD are set in your .env file sir."
        )
        _speak(msg)
        return msg


# ── Travel detection ────────────────────────────────────────────────────────────
def _check_travel_events(events: list[dict]):
    """
    After fetching calendar events, check if any look like travel.
    If so, ask user if they want to search flights.
    Runs in background thread so it doesn't block the voice response.
    """
    import datetime as dt_mod

    travel_keywords = [
        "travel", "trip", "flight", "fly", "visit", "tour",
        "vacation", "holiday", "conference", "meet", "go to"
    ]

    for event in events:
        title = event.get("title", "")
        if not any(k in title.lower() for k in travel_keywords):
            continue

        # Parse event date from "day" field e.g. "Saturday March 15"
        try:
            event_dt = dt_mod.datetime.strptime(
                event["day"] + f" {dt_mod.datetime.now().year}",
                "%A %B %d %Y"
            )
        except Exception:
            continue

        days_until = (event_dt.date() - dt_mod.date.today()).days
        if days_until < 0 or days_until > 14:
            continue

        # Build suggestion
        if days_until == 0:
            when = "today"
        elif days_until == 1:
            when = "tomorrow"
        elif days_until == 2:
            when = "in 2 days"
        else:
            when = f"in {days_until} days"

        suggestion = (
            f"Sir, your event '{title}' is {when}. "
            f"Would you like me to search for flights?"
        )

        def _ask_and_search(s=suggestion, t=title):
            _speak(s)
            ans = _listen(timeout=10)
            if ans and any(w in ans.lower() for w in
                           ["yes", "sure", "please", "yeah", "go ahead", "search"]):
                # Extract destination from event title
                dest = ""
                for kw in ["to ", "in ", "at ", "visit "]:
                    idx = t.lower().find(kw)
                    if idx != -1:
                        dest = t[idx + len(kw):].strip().split()[0].title()
                        break

                try:
                    from travel_agent import _flight_flow
                    query = f"search flights to {dest}" if dest else "search flights"
                    _flight_flow(query)
                except Exception as e:
                    print(f"[Calendar] Travel search error: {e}")
                    _speak("Please ask me to search flights separately Shivank.")

        threading.Thread(target=_ask_and_search, daemon=True).start()
        break  # Only prompt for first travel event found


# ── Startup ─────────────────────────────────────────────────────────────────────
def start():
    """Connect to CalDAV in background thread so startup isn't blocked."""
    threading.Thread(target=_connect, daemon=True).start()