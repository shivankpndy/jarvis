"""
JARVIS Flight Agent
Uses AirLabs API for real flight schedules.
Free tier: ~1000 queries/month.

Setup:
  Add to .env:
    AIRLABS_KEY=your_key_here
    HOME_CITY=Lucknow
    HOME_IATA=LKO
"""
import os, re, datetime, threading
import requests
from dotenv import load_dotenv
from llm import chat_raw

load_dotenv(r"D:\JARVIS\.env")

AIRLABS_KEY  = os.getenv("AIRLABS_KEY", "")
HOME_CITY    = os.getenv("HOME_CITY", "Lucknow")
HOME_IATA    = os.getenv("HOME_IATA", "LKO")
AIRLABS_BASE = "https://airlabs.co/api/v9"

CITY_IATA = {
    "delhi": "DEL", "new delhi": "DEL",
    "mumbai": "BOM", "bombay": "BOM",
    "bangalore": "BLR", "bengaluru": "BLR",
    "hyderabad": "HYD",
    "chennai": "MAA", "madras": "MAA",
    "kolkata": "CCU", "calcutta": "CCU",
    "pune": "PNQ", "ahmedabad": "AMD",
    "jaipur": "JAI", "lucknow": "LKO",
    "goa": "GOI", "kochi": "COK", "cochin": "COK",
    "chandigarh": "IXC", "nagpur": "NAG",
    "indore": "IDR", "bhopal": "BHO",
    "varanasi": "VNS", "patna": "PAT",
    "ranchi": "IXR", "bhubaneswar": "BBI",
    "visakhapatnam": "VTZ", "vizag": "VTZ",
    "coimbatore": "CJB", "srinagar": "SXR",
    "amritsar": "ATQ", "leh": "IXL",
    "dubai": "DXB", "singapore": "SIN",
    "london": "LHR", "new york": "JFK",
    "bangkok": "BKK", "kuala lumpur": "KUL",
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

def _ask(prompt: str, timeout: int = 12) -> str:
    """Speak prompt → listen → fall back to terminal typing."""
    _speak(prompt)
    result = _listen(timeout=timeout)
    if result and len(result.strip()) > 1:
        return result.strip()
    print(f"\n[Flight] {prompt}")
    print("[Flight] Type your answer (or press Enter to cancel):")
    try:
        return input(">>> ").strip()
    except Exception:
        return ""

def _get_iata(city: str) -> str:
    c = city.lower().strip()
    return CITY_IATA.get(c, city.upper()[:3])


# ── Parse cities — handles "from X to Y", "between X and Y", "to Y" ──
def _parse_cities(text: str) -> tuple[str, str]:
    t = text.lower()

    # "between X and Y" / "X and Y"
    m = re.search(
        r'between\s+([a-z\s]+?)\s+and\s+([a-z\s]+?)'
        r'(?:\s+on|\s+for|\s+tomorrow|\s+next|\s+this|\s*$)', t
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # "from X to Y"
    m = re.search(
        r'from\s+([a-z\s]+?)\s+to\s+([a-z\s]+?)'
        r'(?:\s+on|\s+for|\s+tomorrow|\s+next|\s+this|\s*$)', t
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()

    # "X to Y flights"
    m = re.search(
        r'([a-z\s]+?)\s+to\s+([a-z\s]+?)'
        r'(?:\s+flight|\s+on|\s+for|\s+tomorrow|\s*$)', t
    )
    if m:
        c1, c2 = m.group(1).strip(), m.group(2).strip()
        # Make sure they look like city names (in our map or short)
        if c1 in CITY_IATA or len(c1) <= 15:
            return c1, c2

    # "flights to Y" — default from home city
    m = re.search(
        r'(?:flights?|fly)\s+to\s+([a-z\s]+?)'
        r'(?:\s+on|\s+for|\s+from|\s+tomorrow|\s*$)', t
    )
    if m:
        return HOME_CITY.lower(), m.group(1).strip()

    # Check if any known city is mentioned — use home as origin
    for city in sorted(CITY_IATA.keys(), key=len, reverse=True):
        if city in t and city.lower() != HOME_CITY.lower():
            return HOME_CITY.lower(), city

    return HOME_CITY.lower(), ""


# ── Parse travel date ─────────────────────────────────────────────
def _parse_date(text: str) -> datetime.date:
    t   = text.lower()
    now = datetime.date.today()

    if "today" in t:        return now
    if "day after" in t:    return now + datetime.timedelta(days=2)
    if "tomorrow" in t:     return now + datetime.timedelta(days=1)
    if "day after tomorrow" in t: return now + datetime.timedelta(days=2)

    days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"]
    for i, d in enumerate(days):
        if d in t:
            diff = (i - now.weekday()) % 7
            if diff == 0: diff = 7   # "this Monday" means next Monday
            return now + datetime.timedelta(days=diff)

    # LLM fallback
    try:
        prompt = (
            f"Extract travel date from: '{text}'\n"
            f"Today is {now.isoformat()} ({now.strftime('%A')}).\n"
            f"Reply with ONLY: YYYY-MM-DD"
        )
        raw = chat_raw(prompt).strip()
        m = re.search(r'\d{4}-\d{2}-\d{2}', raw)
        if m:
            return datetime.date.fromisoformat(m.group())
    except Exception:
        pass

    return now + datetime.timedelta(days=1)  # default tomorrow


# ── AirLabs API ───────────────────────────────────────────────────
def _get_schedules(dep_iata: str, arr_iata: str) -> list:
    if not AIRLABS_KEY:
        print("[Flight] No AIRLABS_KEY in .env")
        return []
    try:
        resp = requests.get(
            f"{AIRLABS_BASE}/schedules",
            params={"api_key": AIRLABS_KEY, "dep_iata": dep_iata, "arr_iata": arr_iata},
            timeout=10
        )
        data = resp.json()
        if "error" in data:
            print(f"[Flight] AirLabs error: {data['error']}")
            return []
        return data.get("response", [])
    except Exception as e:
        print(f"[Flight] API error: {e}")
        return []


def _get_airline_name(iata: str) -> str:
    if not AIRLABS_KEY: return iata
    try:
        resp = requests.get(
            f"{AIRLABS_BASE}/airlines",
            params={"api_key": AIRLABS_KEY, "iata_code": iata},
            timeout=6
        )
        result = resp.json().get("response", [])
        if result: return result[0].get("name", iata)
    except Exception:
        pass
    return iata


def _format_flight(f: dict) -> str:
    parts = []
    airline = f.get("airline_iata", "")
    if airline: parts.append(_get_airline_name(airline))

    num = f.get("flight_iata", f.get("flight_number", ""))
    if num: parts.append(f"flight {num}")

    for key, label in [("dep_time","departs"), ("arr_time","arrives")]:
        t_str = f.get(key, f.get(key + "_utc", ""))
        if t_str:
            try:
                t = datetime.datetime.strptime(t_str[:5], "%H:%M")
                parts.append(f"{label} {t.strftime('%I:%M %p')}")
            except Exception:
                parts.append(f"{label} {t_str[:5]}")

    dur = f.get("duration", "")
    if dur:
        try:
            h, m = divmod(int(dur), 60)
            parts.append(f"{h}h {m}m" if m else f"{h} hours")
        except Exception:
            parts.append(str(dur))

    return ", ".join(parts) if parts else "details unavailable"


def _build_mmt_url(dep: str, arr: str, date: datetime.date) -> str:
    return (
        f"https://www.makemytrip.com/flight/search?"
        f"tripType=O&itinerary={dep}-{arr}-{date.strftime('%d%m%Y')}"
        f"&paxType=A-1_C-0_I-0&cabinClass=E&isDomestic=true"
    )


def _open_browser(url: str):
    try:
        import subprocess
        subprocess.Popen(["powershell", "-c", f'Start-Process "{url}"'])
    except Exception:
        print(f"[Flight] Open this URL: {url}")


# ── Main handler — synchronous, returns string ────────────────────
def handle(user_text: str) -> str:
    return _flight_flow(user_text)


def _flight_flow(user_text: str) -> str:
    if not AIRLABS_KEY:
        return (
            "AirLabs API key is not set sir. "
            "Add AIRLABS_KEY to your .env file. Sign up free at airlabs.co."
        )

    from_city, to_city = _parse_cities(user_text)
    print(f"[Flight] Parsed: from='{from_city}' to='{to_city}'")

    # If destination unknown — ask
    if not to_city:
        to_city = _ask("Where would you like to fly to sir?")
        if not to_city:
            return "Flight search cancelled."

    if not from_city or from_city == HOME_CITY.lower():
        from_city = HOME_CITY

    travel_date = _parse_date(user_text)
    date_str    = travel_date.strftime("%A, %B %d")
    dep_iata    = _get_iata(from_city)
    arr_iata    = _get_iata(to_city)

    print(f"[Flight] {dep_iata} → {arr_iata}  on {travel_date}")
    _speak(
        f"Searching flights from {from_city.title()} to {to_city.title()} "
        f"on {date_str}. One moment sir."
    )

    flights = _get_schedules(dep_iata, arr_iata)

    if not flights:
        url = _build_mmt_url(dep_iata, arr_iata, travel_date)
        _speak(
            f"No direct flights found via AirLabs for {from_city.title()} to "
            f"{to_city.title()} on {date_str}. Opening MakeMyTrip for you sir."
        )
        _open_browser(url)
        return f"Opened MakeMyTrip for {from_city.title()} → {to_city.title()} on {date_str}."

    # Filter by date
    dated = [f for f in flights if _flight_on_date(f, travel_date)]
    results = (dated or flights)[:5]

    summary = (
        f"Found {len(results)} flight{'s' if len(results)!=1 else ''} "
        f"from {from_city.title()} to {to_city.title()} on {date_str} sir."
    )
    _speak(summary)

    details = []
    for i, f in enumerate(results[:3]):
        d = _format_flight(f)
        _speak(f"Option {i+1}: {d}.")
        details.append(f"  {i+1}. {d}")

    confirm = _ask("Shall I open MakeMyTrip to book one of these sir?", timeout=8)
    if confirm and any(w in confirm.lower() for w in ["yes","sure","open","book","go ahead","please","yeah"]):
        url = _build_mmt_url(dep_iata, arr_iata, travel_date)
        _open_browser(url)
        _speak(f"Opening MakeMyTrip for {from_city.title()} to {to_city.title()} on {date_str}.")
        return summary + "\n" + "\n".join(details) + "\n→ MakeMyTrip opened."
    else:
        _speak("Alright, let me know whenever you want to book sir.")
        return summary + "\n" + "\n".join(details)


def _flight_on_date(f: dict, d: datetime.date) -> bool:
    for key in ("dep_time", "dep_time_utc"):
        t_str = f.get(key, "")
        if t_str and len(t_str) >= 10:
            try:
                if datetime.date.fromisoformat(t_str[:10]) == d:
                    return True
            except Exception:
                pass
    return False


# ── Proactive calendar hook ───────────────────────────────────────
def check_calendar_for_travel(events: list):
    if not events: return
    for event in events:
        title = event.get("title", "").lower()
        day   = event.get("day", "")
        time_ = event.get("time", "")
        for city in CITY_IATA:
            if city in title and city.lower() != HOME_CITY.lower():
                def _proactive(c=city, d=day, t=time_, ev=event.get("title","")):
                    ans = _ask(
                        f"Sir, I noticed '{ev}' on {d} at {t}. "
                        f"It looks like it may be in {c.title()}. "
                        f"Shall I search for flights?"
                    )
                    if ans and any(w in ans.lower() for w in ["yes","sure","please","search"]):
                        _flight_flow(f"flight from {HOME_CITY} to {c} on {d}")
                threading.Thread(target=_proactive, daemon=True).start()
                return