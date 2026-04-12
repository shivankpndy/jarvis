"""
JARVIS Travel Agent — Amadeus API (real flight data, no bot blocking)

FREE API setup (2 minutes):
  1. Go to https://developers.amadeus.com
  2. Sign up free → Create App
  3. Copy API Key and API Secret
  4. Add to .env:
       AMADEUS_API_KEY=your_key
       AMADEUS_API_SECRET=your_secret

Install: pip install amadeus
"""

import os
import re
import threading
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(r"D:\JARVIS\.env")

AMADEUS_KEY    = os.getenv("AMADEUS_API_KEY", "")
AMADEUS_SECRET = os.getenv("AMADEUS_API_SECRET", "")

# Common Indian city → IATA code map
CITY_CODES = {
    "delhi": "DEL", "new delhi": "DEL",
    "mumbai": "BOM", "bombay": "BOM",
    "bangalore": "BLR", "bengaluru": "BLR",
    "hyderabad": "HYD",
    "chennai": "MAA", "madras": "MAA",
    "kolkata": "CCU", "calcutta": "CCU",
    "lucknow": "LKO",
    "ahmedabad": "AMD",
    "pune": "PNQ",
    "goa": "GOI",
    "jaipur": "JAI",
    "kochi": "COK", "cochin": "COK",
    "varanasi": "VNS",
    "patna": "PAT",
    "bhopal": "BHO",
    "indore": "IDR",
    "nagpur": "NAG",
    "srinagar": "SXR",
    "leh": "IXL",
    "amritsar": "ATQ",
    "chandigarh": "IXC",
    "dehradun": "DED",
    "agra": "AGR",
    "jodhpur": "JDH",
    "udaipur": "UDR",
    "coimbatore": "CJB",
    "vizag": "VTZ", "visakhapatnam": "VTZ",
    "bhubaneswar": "BBI",
    "guwahati": "GAU",
    "port blair": "IXZ",
    "ranchi": "IXR",
    "raipur": "RPR",
    "aurangabad": "IXU",
    "mangalore": "IXE",
    "tirupati": "TIR",
    "madurai": "IXM",
    "trichy": "TRZ", "tiruchirappalli": "TRZ",
}

_speak_fn  = None
_listen_fn = None
_notify_fn = None
_amadeus   = None

def set_speak(fn):  global _speak_fn;  _speak_fn  = fn
def set_listen(fn): global _listen_fn; _listen_fn = fn
def set_notify(fn): global _notify_fn; _notify_fn = fn

def _speak(text):
    if _speak_fn: _speak_fn(text)
    else: print(f"[Travel] {text}")

def _listen(timeout=15):
    if _listen_fn: return _listen_fn(timeout=timeout) or ""
    return ""


# ── Amadeus client ────────────────────────────────────────────────
def _get_client():
    global _amadeus
    if _amadeus: return _amadeus
    try:
        from amadeus import Client
        _amadeus = Client(
            client_id=AMADEUS_KEY,
            client_secret=AMADEUS_SECRET,
        )
        return _amadeus
    except ImportError:
        print("[Travel] amadeus not installed — run: pip install amadeus")
        return None
    except Exception as e:
        print(f"[Travel] Amadeus init error: {e}")
        return None


def is_configured():
    return bool(AMADEUS_KEY and AMADEUS_SECRET)


# ── Helpers ───────────────────────────────────────────────────────
def _city_to_iata(city: str) -> str:
    """Convert city name to IATA code."""
    c = city.lower().strip()
    if c in CITY_CODES:
        return CITY_CODES[c]
    # Try partial match
    for key, code in CITY_CODES.items():
        if c in key or key in c:
            return code
    # If already looks like IATA code (3 uppercase letters)
    if re.match(r'^[A-Z]{3}$', city.upper()):
        return city.upper()
    return city.upper()[:3]


def _parse_date(text: str) -> tuple[str, str]:
    """Returns (YYYY-MM-DD for API, spoken date string)."""
    today = datetime.today()
    t     = text.lower()

    if "tomorrow" in t:
        d = today + timedelta(days=1)
    elif "day after" in t:
        d = today + timedelta(days=2)
    elif "next week" in t:
        d = today + timedelta(days=7)
    elif "this weekend" in t or "saturday" in t:
        days = 5 - today.weekday()
        if days <= 0: days += 7
        d = today + timedelta(days=days)
    elif "sunday" in t:
        days = 6 - today.weekday()
        if days <= 0: days += 7
        d = today + timedelta(days=days)
    elif "friday" in t:
        days = 4 - today.weekday()
        if days <= 0: days += 7
        d = today + timedelta(days=days)
    elif "monday" in t:
        days = 0 - today.weekday()
        if days <= 0: days += 7
        d = today + timedelta(days=days)
    elif "tuesday" in t:
        days = 1 - today.weekday()
        if days <= 0: days += 7
        d = today + timedelta(days=days)
    elif "wednesday" in t:
        days = 2 - today.weekday()
        if days <= 0: days += 7
        d = today + timedelta(days=days)
    elif "thursday" in t:
        days = 3 - today.weekday()
        if days <= 0: days += 7
        d = today + timedelta(days=days)
    else:
        # try to find a date pattern like "15 march" or "march 15"
        m = re.search(r'(\d{1,2})\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', t)
        if m:
            months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
                      "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
            day_num = int(m.group(1))
            mon_num = months[m.group(2)]
            year    = today.year if mon_num >= today.month else today.year + 1
            d = today.replace(year=year, month=mon_num, day=day_num)
        else:
            d = today + timedelta(days=1)

    return d.strftime("%Y-%m-%d"), d.strftime("%A %B %d")


def _extract_city(text: str, keywords: list) -> str:
    t = text.lower()
    for kw in keywords:
        m = re.search(
            rf'\b{kw}\s+([a-z ]+?)(?:\s+(?:on|for|next|this|tomorrow|to\b|at\b|\d)|$)',
            t
        )
        if m:
            city = m.group(1).strip().title()
            if len(city) > 1:
                return city
    return ""


def _format_duration(iso: str) -> str:
    """Convert PT2H30M to '2 hours 30 minutes'."""
    h = re.search(r'(\d+)H', iso)
    m = re.search(r'(\d+)M', iso)
    parts = []
    if h: parts.append(f"{h.group(1)} hour{'s' if int(h.group(1))>1 else ''}")
    if m: parts.append(f"{m.group(1)} minutes")
    return " ".join(parts) if parts else iso


def _format_price(offer: dict) -> str:
    try:
        price = offer["price"]["grandTotal"]
        curr  = offer["price"]["currency"]
        if curr == "INR":
            return f"{float(price):,.0f} rupees"
        return f"{curr} {price}"
    except Exception:
        return ""


def _format_flight(offer: dict, idx: int) -> str:
    try:
        itinerary = offer["itineraries"][0]
        segments  = itinerary["segments"]
        first_seg = segments[0]
        last_seg  = segments[-1]

        airline   = first_seg["carrierCode"]
        dep_time  = first_seg["departure"]["at"][11:16]   # HH:MM
        arr_time  = last_seg["arrival"]["at"][11:16]
        duration  = _format_duration(itinerary["duration"])
        stops     = len(segments) - 1
        stop_str  = "non-stop" if stops == 0 else f"{stops} stop{'s' if stops>1 else ''}"
        price     = _format_price(offer)

        return (
            f"Option {idx}: {airline}, departs {dep_time}, arrives {arr_time}, "
            f"{duration}, {stop_str}"
            + (f", {price}" if price else "")
        )
    except Exception as e:
        return f"Option {idx}: flight details unavailable"


# ── Flight search ─────────────────────────────────────────────────
def search_flights(origin: str, destination: str, date: str,
                   adults: int = 1, max_results: int = 5) -> list:
    client = _get_client()
    if not client:
        return []
    try:
        origin_code = _city_to_iata(origin)
        dest_code   = _city_to_iata(destination)
        print(f"[Travel] Searching {origin_code}→{dest_code} on {date}")

        response = client.shopping.flight_offers_search.get(
            originLocationCode=origin_code,
            destinationLocationCode=dest_code,
            departureDate=date,
            adults=adults,
            max=max_results,
            currencyCode="INR",
        )
        return response.data
    except Exception as e:
        print(f"[Travel] Flight search error: {e}")
        return []


# ── Voice flow ────────────────────────────────────────────────────
def _flight_flow(user_text: str):
    if not is_configured():
        _speak(
            "Amadeus API is not configured Shivank. "
            "Please add your Amadeus API key and secret to the dot env file. "
            "Sign up free at developers dot amadeus dot com."
        )
        return

    t = user_text.lower()

    origin      = _extract_city(t, ["from"])
    destination = _extract_city(t, ["to", "for"])
    date_api, date_spoken = _parse_date(t)

    if not origin:
        _speak("Which city are you flying from Shivank?")
        origin = _listen()
        if not origin:
            _speak("Flight search cancelled.")
            return
        origin = origin.strip()

    if not destination:
        _speak("And where are you flying to?")
        destination = _listen()
        if not destination:
            _speak("Flight search cancelled.")
            return
        destination = destination.strip()

    origin_code = _city_to_iata(origin)
    dest_code   = _city_to_iata(destination)

    _speak(
        f"Searching flights from {origin} to {destination} "
        f"on {date_spoken}. One moment."
    )

    offers = search_flights(origin, destination, date_api)

    if not offers:
        _speak(
            f"No flights found from {origin} to {destination} on {date_spoken} Shivank. "
            f"Try a different date or check MakeMyTrip directly."
        )
        return

    _speak(f"Found {len(offers)} flights. Here are the top options.")
    for i, offer in enumerate(offers[:3]):
        _speak(_format_flight(offer, i + 1))

    # Cheapest
    try:
        cheapest = min(offers, key=lambda x: float(x["price"]["grandTotal"]))
        price    = _format_price(cheapest)
        _speak(f"The cheapest option is {price}.")
    except Exception:
        pass

    _speak(
        "Would you like me to open MakeMyTrip to book any of these Shivank? "
        "Say yes or tell me the option number."
    )
    choice = _listen()
    if not choice:
        return

    if any(w in choice.lower() for w in ["yes", "sure", "okay", "go ahead"]) or \
       re.search(r'\b[1-3]\b', choice):
        import webbrowser
        url = (
            f"https://www.makemytrip.com/flights/cheap-flights-from-"
            f"{origin_code.lower()}-to-{dest_code.lower()}.html"
        )
        webbrowser.open(url)
        _speak(
            f"Opened MakeMyTrip in your browser for "
            f"{origin} to {destination} flights Shivank."
        )
        if _notify_fn:
            _notify_fn(
                f"Travel: {origin}→{destination} on {date_spoken} — "
                f"{len(offers)} flights found"
            )


def handle(user_text: str) -> str:
    threading.Thread(
        target=lambda: _flight_flow(user_text),
        daemon=True
    ).start()
    return ""


# ── Called from calendar agent when travel event detected ─────────
def check_upcoming_travel(event_title: str, event_dt: datetime) -> str | None:
    """
    Called by calendar_agent when an event looks like travel.
    Returns a suggestion string if flights should be booked, else None.
    """
    travel_keywords = [
        "travel", "trip", "flight", "fly", "visit", "tour",
        "vacation", "holiday", "go to", "conference", "meet"
    ]
    title_lower = event_title.lower()
    if not any(k in title_lower for k in travel_keywords):
        return None

    days_until = (event_dt.date() - datetime.today().date()).days
    if days_until < 0:
        return None

    if days_until <= 2:
        return (
            f"Sir, your event '{event_title}' is in {days_until} day{'s' if days_until != 1 else ''}. "
            f"Would you like me to search for flights?"
        )
    elif days_until <= 7:
        return (
            f"Sir, you have '{event_title}' coming up in {days_until} days. "
            f"Shall I search for flights?"
        )
    return None