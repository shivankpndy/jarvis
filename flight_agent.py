"""
JARVIS Flight Agent
Uses AirLabs API for real flight schedules + data.
Free tier: ~1000 queries/month — plenty for personal use.

Setup:
  1. Sign up free at https://airlabs.co
  2. Get your API key from dashboard
  3. Add to .env:  AIRLABS_KEY=your_key_here
                   HOME_CITY=Lucknow
                   HOME_IATA=LKO

Voice commands:
  Hey JARVIS → Search flights from Lucknow to Delhi tomorrow
  Hey JARVIS → Find flights to Mumbai on Friday
  Hey JARVIS → Book a flight to Bangalore next Monday
"""
import os
import re
import json
import asyncio
import threading
import datetime
import requests
from dotenv import load_dotenv

load_dotenv(r"D:\JARVIS\.env")

AIRLABS_KEY  = os.getenv("AIRLABS_KEY", "")
HOME_CITY    = os.getenv("HOME_CITY", "Lucknow")
HOME_IATA    = os.getenv("HOME_IATA", "LKO")
AIRLABS_BASE = "https://airlabs.co/api/v9"

# Indian city → IATA map
CITY_IATA = {
    "delhi": "DEL", "new delhi": "DEL",
    "mumbai": "BOM", "bombay": "BOM",
    "bangalore": "BLR", "bengaluru": "BLR",
    "hyderabad": "HYD",
    "chennai": "MAA", "madras": "MAA",
    "kolkata": "CCU", "calcutta": "CCU",
    "pune": "PNQ",
    "ahmedabad": "AMD",
    "jaipur": "JAI",
    "lucknow": "LKO",
    "goa": "GOI",
    "kochi": "COK", "cochin": "COK",
    "chandigarh": "IXC",
    "nagpur": "NAG",
    "indore": "IDR",
    "bhopal": "BHO",
    "varanasi": "VNS",
    "patna": "PAT",
    "ranchi": "IXR",
    "bhubaneswar": "BBI",
    "visakhapatnam": "VTZ", "vizag": "VTZ",
    "coimbatore": "CJB",
    "srinagar": "SXR",
    "amritsar": "ATQ",
    "leh": "IXL",
    "dubai": "DXB",
    "singapore": "SIN",
    "london": "LHR",
    "new york": "JFK",
    "bangkok": "BKK",
    "kuala lumpur": "KUL",
}

_speak_fn  = None
_listen_fn = None
_notify_fn = None


def set_speak(fn):  global _speak_fn;  _speak_fn  = fn
def set_listen(fn): global _listen_fn; _listen_fn = fn
def set_notify(fn): global _notify_fn; _notify_fn = fn


def _speak(text):
    if _speak_fn: _speak_fn(text)
    else: print(f"[Flight] {text}")


def _listen(timeout=12):
    if _listen_fn: return _listen_fn(timeout=timeout) or ""
    return ""


def _get_iata(city: str) -> str:
    return CITY_IATA.get(city.lower().strip(), city.upper()[:3])


# ── AirLabs API calls ─────────────────────────────────────────────
def _get_schedules(dep_iata: str, arr_iata: str) -> list[dict]:
    """Fetch scheduled flights between two airports."""
    if not AIRLABS_KEY:
        print("[Flight] No AIRLABS_KEY in .env")
        return []
    try:
        url    = f"{AIRLABS_BASE}/schedules"
        params = {
            "api_key":  AIRLABS_KEY,
            "dep_iata": dep_iata,
            "arr_iata": arr_iata,
        }
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if "error" in data:
            print(f"[Flight] AirLabs error: {data['error']}")
            return []
        return data.get("response", [])
    except Exception as e:
        print(f"[Flight] API error: {e}")
        return []


def _get_airport_info(iata: str) -> dict:
    """Get airport name and city from IATA code."""
    if not AIRLABS_KEY:
        return {}
    try:
        url    = f"{AIRLABS_BASE}/airports"
        params = {"api_key": AIRLABS_KEY, "iata_code": iata}
        resp   = requests.get(url, params=params, timeout=8)
        data   = resp.json()
        result = data.get("response", [])
        return result[0] if result else {}
    except Exception:
        return {}


def _get_airline_name(iata: str) -> str:
    """Get airline name from IATA code."""
    if not AIRLABS_KEY:
        return iata
    try:
        url    = f"{AIRLABS_BASE}/airlines"
        params = {"api_key": AIRLABS_KEY, "iata_code": iata}
        resp   = requests.get(url, params=params, timeout=8)
        data   = resp.json()
        result = data.get("response", [])
        if result:
            return result[0].get("name", iata)
    except Exception:
        pass
    return iata


def _format_flight(f: dict) -> str:
    """Format a flight dict into a readable string for JARVIS to speak."""
    parts = []

    airline = f.get("airline_iata", "")
    if airline:
        parts.append(_get_airline_name(airline))

    flight_num = f.get("flight_iata", f.get("flight_number", ""))
    if flight_num:
        parts.append(f"flight {flight_num}")

    dep_time = f.get("dep_time", f.get("dep_time_utc", ""))
    if dep_time:
        # Format time nicely: "14:30" → "2:30 PM"
        try:
            t = datetime.datetime.strptime(dep_time[:5], "%H:%M")
            parts.append(f"departs {t.strftime('%I:%M %p')}")
        except Exception:
            parts.append(f"departs {dep_time[:5]}")

    arr_time = f.get("arr_time", f.get("arr_time_utc", ""))
    if arr_time:
        try:
            t = datetime.datetime.strptime(arr_time[:5], "%H:%M")
            parts.append(f"arrives {t.strftime('%I:%M %p')}")
        except Exception:
            parts.append(f"arrives {arr_time[:5]}")

    duration = f.get("duration", "")
    if duration:
        try:
            mins = int(duration)
            h, m = divmod(mins, 60)
            parts.append(f"{h}h {m}m" if m else f"{h} hours")
        except Exception:
            parts.append(str(duration))

    status = f.get("status", "")
    if status and status.lower() not in ["scheduled", "active"]:
        parts.append(status)

    return ", ".join(parts) if parts else "details unavailable"


def _build_mmt_url(dep_iata: str, arr_iata: str, date: datetime.date) -> str:
    d = date.strftime("%d%m%Y")
    return (
        f"https://www.makemytrip.com/flight/search?"
        f"tripType=O&itinerary={dep_iata}-{arr_iata}-{d}"
        f"&paxType=A-1_C-0_I-0&cabinClass=E&isDomestic=true"
    )


# ── Natural language parsers ──────────────────────────────────────
def _parse_date(text: str) -> datetime.date:
    """Parse travel date from natural language, default tomorrow."""
    import ollama
    try:
        now    = datetime.datetime.now()
        prompt = (
            f"Extract a travel date from this text.\n"
            f"Today: {now.strftime('%Y-%m-%d')} ({now.strftime('%A')})\n"
            f"Text: {text}\n"
            f"Return ONLY format: YYYY-MM-DD — nothing else."
        )
        resp = ollama.chat(
            model="llama3.2:3b",
            messages=[{"role": "user", "content": prompt}]
        )
        raw = resp["message"]["content"].strip()
        m   = re.search(r'\d{4}-\d{2}-\d{2}', raw)
        if m:
            return datetime.date.fromisoformat(m.group())
    except Exception as e:
        print(f"[Flight] Date parse error: {e}")
    return datetime.date.today() + datetime.timedelta(days=1)


def _parse_cities(text: str) -> tuple[str, str]:
    t = text.lower()
    m = re.search(
        r'from\s+([a-z\s]+?)\s+to\s+([a-z\s]+?)'
        r'(?:\s+on|\s+for|\s+tomorrow|\s+next|\s+this|\s*$)', t
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()

    m = re.search(
        r'([a-z\s]+?)\s+to\s+([a-z\s]+?)'
        r'(?:\s+flight|\s+on|\s+for|\s*$)', t
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()

    m = re.search(
        r'(?:flight|fly|flights)\s+to\s+([a-z\s]+?)'
        r'(?:\s+on|\s+for|\s+from|\s*$)', t
    )
    if m:
        return HOME_CITY, m.group(1).strip()

    return HOME_CITY, ""


# ── Voice flow ────────────────────────────────────────────────────
def handle(user_text: str) -> str:
    threading.Thread(
        target=lambda: asyncio.run(_flight_flow(user_text)),
        daemon=True
    ).start()
    return ""


async def _flight_flow(user_text: str):
    if not AIRLABS_KEY:
        _speak(
            "AirLabs API key is not set Shivank. "
            "Please add AIRLABS underscore KEY to your dot env file. "
            "Sign up free at airlabs dot co."
        )
        return

    from_city, to_city = _parse_cities(user_text)

    if not to_city:
        _speak("Where would you like to fly to Shivank?")
        to_city = _listen()
        if not to_city:
            _speak("Flight search cancelled.")
            return

    if not from_city or from_city == HOME_CITY.lower():
        from_city = HOME_CITY

    travel_date = _parse_date(user_text)
    date_str    = travel_date.strftime("%A, %B %d")

    dep_iata = _get_iata(from_city)
    arr_iata = _get_iata(to_city)

    _speak(
        f"Searching flights from {from_city.title()} to {to_city.title()} "
        f"on {date_str} using AirLabs. Give me a moment sir."
    )

    # Fetch from AirLabs
    flights = _get_schedules(dep_iata, arr_iata)

    if not flights:
        _speak(
            f"No flights found from {from_city.title()} to {to_city.title()} "
            f"on {date_str} Shivank. "
            f"Opening MakeMyTrip in your browser for you."
        )
        url = _build_mmt_url(dep_iata, arr_iata, travel_date)
        import subprocess
        subprocess.Popen(["powershell", "-c", f'Start-Process "{url}"'])
        return

    # Filter by date if dep_time available
    date_flights = []
    for f in flights:
        dep_time = f.get("dep_time", f.get("dep_time_utc", ""))
        if dep_time:
            try:
                flight_date = datetime.datetime.strptime(
                    dep_time[:10], "%Y-%m-%d"
                ).date()
                if flight_date == travel_date:
                    date_flights.append(f)
            except Exception:
                date_flights.append(f)
        else:
            date_flights.append(f)

    results = date_flights[:5] if date_flights else flights[:5]

    # Speak results
    _speak(
        f"Found {len(results)} flight{'s' if len(results) != 1 else ''} "
        f"from {from_city.title()} to {to_city.title()} on {date_str} Shivank."
    )

    for i, f in enumerate(results[:3]):
        detail = _format_flight(f)
        _speak(f"Option {i + 1}: {detail}.")

    _speak(
        "Would you like me to open MakeMyTrip to book one of these Shivank?"
    )
    resp = _listen()
    if resp and any(
        w in resp.lower()
        for w in ["yes", "sure", "open", "book", "go ahead", "please"]
    ):
        url = _build_mmt_url(dep_iata, arr_iata, travel_date)
        import subprocess
        subprocess.Popen(["powershell", "-c", f'Start-Process "{url}"'])
        _speak(
            f"Opening MakeMyTrip for {from_city.title()} to "
            f"{to_city.title()} on {date_str} Shivank."
        )
    else:
        _speak("Alright, let me know whenever you'd like to book Shivank.")


# ── Proactive calendar hook ───────────────────────────────────────
def check_calendar_for_travel(events: list[dict]):
    """
    Called after fetching calendar events.
    If an event title mentions a city different from home,
    JARVIS proactively offers to search flights.
    """
    if not events:
        return
    for event in events:
        title = event.get("title", "").lower()
        day   = event.get("day", "")
        time_ = event.get("time", "")
        for city in CITY_IATA:
            if city in title and city.lower() != HOME_CITY.lower():
                def _ask(c=city, d=day, t=time_, ev=event.get("title", "")):
                    _speak(
                        f"Sir, I noticed '{ev}' on {d} at {t}. "
                        f"It looks like it may be in {c.title()}. "
                        f"Shall I search for flights?"
                    )
                    ans = _listen(timeout=10)
                    if ans and any(
                        w in ans.lower()
                        for w in ["yes", "sure", "please", "search", "go ahead"]
                    ):
                        asyncio.run(
                            _flight_flow(f"flight from {HOME_CITY} to {c} on {d}")
                        )
                threading.Thread(target=_ask, daemon=True).start()
                return