"""
JARVIS Agent Router
Detects intent from voice command and routes to the correct agent.
"""
import sys
import os
import re
sys.path.insert(0, r"D:\JARVIS")
from dotenv import load_dotenv
load_dotenv(r"D:\JARVIS\.env")
from llm import chat, chat_raw


# ── Intent Keywords ──────────────────────────────────────────────────────────────

TIMER_KEYWORDS = [
    "set a timer", "set timer", "timer for", "timer of",
    "remind me in", "set an alarm", "set alarm", "alarm at",
    "alarm for", "wake me at", "wake me up", "remind me at",
    "in 1 minute", "in 2 minutes", "in 5 minutes", "in 10 minutes",
    "in 15 minutes", "in 30 minutes", "in an hour", "in 1 hour",
    "after 5 minutes", "after 10 minutes",
]

IOT_KEYWORDS = [
    "turn on the lights", "turn off the lights",
    "turn on the light", "turn off the light",
    "lights on", "lights off", "light on", "light off",
    "room lights on", "room lights off",
    "switch on the light", "switch off the light",
    "white led", "turn on the room", "turn off the room",
    "make tea", "tea time", "brew tea", "start tea", "prepare tea", "chai",
    "tea off", "cancel tea", "green led",
    "intruder", "trigger alert", "alert on", "red alert",
    "clear alert", "cancel alert", "alert off", "red led",
    "all off", "everything off", "turn off everything", "all lights off",
]

GMAIL_KEYWORDS = [
    "check email", "check my email", "any emails", "new emails",
    "unread emails", "my inbox", "check mail", "any mail",
    "read my email", "read emails", "what emails",
]

SLACK_KEYWORDS = [
    "check slack", "slack messages", "any slack", "slack updates",
    "slack dms", "my slack", "slack notifications", "check my slack",
]

EMAIL_SEND_KEYWORDS = [
    "send email", "send an email", "write email", "write an email",
    "compose email", "email to", "send mail", "shoot an email",
    "draft email", "email rahul", "email mom", "email dad",
]

CALENDAR_KEYWORDS = [
    "calendar", "my schedule", "my day", "today's events",
    "what's on my calendar", "this week", "upcoming events",
    "add meeting", "schedule meeting", "add event", "create event",
    "set a meeting", "book meeting", "new meeting", "new event",
    "set a reminder", "when is my", "do i have anything",
    # natural scheduling phrases
    "schedule a", "schedule an", "schedule call", "schedule team",
    "add a call", "add call", "book a call", "set up a call",
    "add appointment", "create appointment", "book appointment",
    "remind me", "set reminder", "add reminder",
    "put on my calendar", "add to calendar", "add to my calendar",
    "block time", "block off",
]

DRIVE_KEYWORDS = [
    "google drive", "drive files", "upload to drive", "save to drive",
    "backup to drive", "put on drive", "list drive", "show drive",
    "find on drive", "search drive", "download from drive",
    "get from drive", "backup memory", "backup snapshots",
    "what's on drive", "what do i have on drive",
]

CONTACTS_KEYWORDS = [
    "show contacts", "list contacts", "my contacts",
    "add contact", "save contact", "new contact",
    "delete contact", "remove contact",
    "who are my contacts",
]

SENSOR_KEYWORDS = [
    "temperature", "room temp", "how hot", "how warm", "degrees",
    "humidity", "how humid", "moisture",
    "flame", "fire detected", "smoke",
    "is there fire", "any fire", "sensor reading",
]

BRIEFING_KEYWORDS = [
    "morning briefing", "good morning jarvis", "good morning",
    "daily briefing", "brief me", "morning update",
    "what's happening today", "morning report", "start my day",
    "what's my day look like", "today's briefing",
]

SEARCH_KEYWORDS = [
    "search for", "search the web", "look up", "look it up",
    "google", "find out", "search online", "browse for",
    "latest news", "current news", "news about", "what happened",
    "recent", "right now", "currently", "live score",
    "weather in", "price of",
]

CAMERA_KEYWORDS = [
    "start camera", "stop camera", "camera on", "camera off",
    "enable camera", "disable camera", "start monitoring",
    "stop monitoring", "security on", "security off",
    "watch for intruder", "camera status", "is camera on",
]

FINANCE_KEYWORDS = [
    "stock price", "share price", "stock market", "share market",
    "nifty", "sensex", "bank nifty", "banknifty", "nse", "bse",
    "bitcoin", "ethereum", "crypto", "btc", "eth", "solana", "dogecoin",
    "gold price", "silver price", "crude oil", "oil price",
    "usd to inr", "dollar rate", "rupee", "forex",
    "mutual fund", "market today", "trading at", "price of",
    "how is nifty", "how is sensex", "how is reliance", "how is tcs",
    "what is tcs", "what is sbi", "what is reliance", "what is hdfc",
    "reliance stock", "tcs stock", "infosys stock", "sbi stock",
    "how much is", "current price", "live price", "market price",
    "portfolio", "watchlist", "nifty 50", "my stocks",
    "apple stock", "tesla stock", "nvidia stock", "bitcoin price",
    "yahoo finance", "yfinance", "market update", "market snapshot",
    "how is apple", "how is tesla", "how is nvidia", "how is amazon",
    "xrp", "bnb", "ada", "cardano", "shib",
]

CODING_KEYWORDS = [
    # write + code/script/function/class/program
    "write code", "write a script", "write a function", "write a program",
    "write a python", "write a javascript", "write a class", "write a module",
    "write me code", "write me a script", "write me a function",
    "write me a program", "write me a python", "write me a class",
    # create/build/make
    "create a script", "create a program", "create a function",
    "build a function", "build a script", "build a program",
    "make a script", "make a function", "make a program",
    # code/script/function for
    "code for", "script for", "function to", "function that",
    "code that", "code to", "program to", "program that",
    # debug/fix
    "debug this", "fix this code", "fix the bug", "there is a bug",
    "whats wrong with this code", "why is this code",
    # implement/generate
    "implement", "generate code", "code snippet",
    # language specific
    "python code", "javascript code", "python script", "js code",
    "python function", "python class", "python program",
]

PROJECT_KEYWORDS = [
    "new project", "start project", "create project",
    "new task", "start a project", "scaffold",
]


FLIGHT_KEYWORDS = [
    "search flights", "find flights", "book flight", "flight to",
    "flight from", "flights to", "fly to", "fly from",
    "book a flight", "check flights", "makemytrip",
    "cheapest flight", "next flight", "one way flight", "round trip",
    "flights between", "flight between", "check flights between",
    "flights from", "any flights", "show flights",
]

TRAVEL_KEYWORDS = [
    "travel plan", "travel planning", "plan my trip",
    "trip plan", "itinerary", "plan travel",
]

ZOMATO_KEYWORDS = [
    "zomato", "order from zomato", "order on zomato",
    "order food", "get me food", "i want to order", "food delivery",
    "order biryani", "order pizza", "order burger", "order chinese",
    "order something to eat", "hungry", "order chicken",
    "order indian food", "order from",
]

ZEPTO_KEYWORDS = [
    "zepto", "zepto cafe", "zepto cafe", "order from zepto",
    "order on zepto", "zepto order",
]

SWIGGY_KEYWORDS = [
    "order from swiggy", "swiggy",
]

FOUNDER_GREETING_KEYWORDS = [
    "greet the founder of hack club",
    "greet founder of hack club",
    "message for hack club founder",
    "hack club founder is watching",
    "zach latta is watching",
    "greet zach latta",
    "special message for zach",
]

DESKTOP_KEYWORDS = [
    "open browser", "go to website", "open youtube", "open google",
    "organize files", "move file", "find file", "open folder",
    "open notepad", "open calculator", "screenshot",
]

# These force brain even if coding keywords match
BRAIN_OVERRIDE = [
    "essay", "poem", "story", "letter", "paragraph",
    "article", "blog post", "speech", "write about",
    "explain", "describe", "summarize", "what is",
    "who is", "how does", "why is", "tell me about",
    "difference between", "give me an example", "define",
]

JARVIS_PERSONA = """You are JARVIS, a highly intelligent personal AI assistant.
You are helpful, efficient, and slightly formal — like a British butler who is
also a genius engineer. Keep responses concise. Address the user as Shivank or sir."""


def craft_hack_club_founder_greeting() -> str:
    return (
        "Mr. Zach Latta, founder of Hack Club, it is an honor to have you here. "
        "Your work empowers young builders to create boldly and ship real projects. "
        "This JARVIS is built in that same spirit. Thank you for inspiring a generation of makers."
    )


def is_founder_greeting_request(text: str) -> bool:
    """Robust matcher for founder greeting prompts with punctuation/noise removed."""
    normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    normalized = " ".join(normalized.split())

    if any(k in normalized for k in FOUNDER_GREETING_KEYWORDS):
        return True

    mentions_hack_club = "hack club" in normalized or "hackclub" in normalized
    asks_to_greet = any(word in normalized for word in ["greet", "message", "wish", "welcome", "say hi"])
    mentions_founder = "founder" in normalized or "zach" in normalized or "zach latta" in normalized

    return mentions_hack_club and (asks_to_greet or mentions_founder)


# ── Intent Detection ─────────────────────────────────────────────────────────────

def detect_intent(text: str) -> str:
    t = text.lower().strip()

    # Priority order matters — most specific first
    if is_founder_greeting_request(t):          return "founder_greeting"
    if any(k in t for k in TIMER_KEYWORDS):    return "timer"
    if any(k in t for k in IOT_KEYWORDS):      return "iot"
    if any(k in t for k in GMAIL_KEYWORDS):    return "gmail"
    if any(k in t for k in SLACK_KEYWORDS):    return "slack"
    if any(k in t for k in EMAIL_SEND_KEYWORDS): return "email_send"
    if any(k in t for k in BRIEFING_KEYWORDS): return "briefing"
    if any(k in t for k in CALENDAR_KEYWORDS): return "calendar"
    if any(k in t for k in DRIVE_KEYWORDS):    return "drive"
    if any(k in t for k in CONTACTS_KEYWORDS): return "contacts"
    if any(k in t for k in SENSOR_KEYWORDS):   return "sensor"
    if any(k in t for k in SEARCH_KEYWORDS):   return "search"
    if any(k in t for k in CAMERA_KEYWORDS):   return "camera"
    if any(k in t for k in FINANCE_KEYWORDS):  return "finance"
    if any(k in t for k in TRAVEL_KEYWORDS):   return "flight"
    if any(k in t for k in FLIGHT_KEYWORDS):   return "flight"
    if any(k in t for k in ZEPTO_KEYWORDS):    return "zepto"
    if any(k in t for k in ZOMATO_KEYWORDS):   return "zomato"
    if any(k in t for k in SWIGGY_KEYWORDS):   return "swiggy"
    if any(k in t for k in PROJECT_KEYWORDS):  return "project"
    if any(k in t for k in CODING_KEYWORDS):   return "coding"
    if any(k in t for k in BRAIN_OVERRIDE):    return "brain"
    if any(k in t for k in DESKTOP_KEYWORDS):  return "desktop"
    return "brain"


# ── Brain ─────────────────────────────────────────────────────────────────────────

def brain_think(user_text: str, history: list) -> str:
    history.append({"role": "user", "content": user_text})
    reply = ""
    try:
        reply = chat(history).strip()
        if not reply:
            reply = "I'm not sure how to respond to that sir."
    except Exception as e:
        print(f"[Brain] LLM error: {e}")
        reply = f"I'm sorry sir, I encountered an error: {e}"
    if reply:
        history.append({"role": "assistant", "content": reply})
    return reply


# ── Main Router ───────────────────────────────────────────────────────────────────

def route(user_text: str, history: list) -> tuple:
    if is_founder_greeting_request(user_text):
        return "founder_greeting", craft_hack_club_founder_greeting()

    intent = detect_intent(user_text)
    print(f"[Router] intent='{intent}' | text='{user_text[:60]}'")

    if intent == "founder_greeting":
        return "founder_greeting", craft_hack_club_founder_greeting()

    # Timer
    if intent == "timer":
        try:
            from timer_agent import handle as h
            reply = h(user_text)
            if reply: return "timer", reply
        except Exception as e: print(f"Timer error: {e}")
        return "brain", brain_think(user_text, history)

    # IoT
    if intent == "iot":
        try:
            from iot_agent import handle as h
            reply = h(user_text)
            if reply: return "iot", reply
        except Exception as e: print(f"IoT error: {e}")
        return "brain", brain_think(user_text, history)

    # Gmail read
    if intent == "gmail":
        try:
            from gmail_agent import handle as h
            reply = h(user_text)
            if reply: return "gmail", reply
        except Exception as e: print(f"Gmail error: {e}")
        return "brain", brain_think(user_text, history)

    # Slack
    if intent == "slack":
        try:
            from slack_agent import handle as h
            reply = h(user_text)
            if reply: return "slack", reply
        except Exception as e: print(f"Slack error: {e}")
        return "brain", brain_think(user_text, history)

    # Email send
    if intent == "email_send":
        try:
            from email_sender import handle as h
            h(user_text)
            return "email_send", ""
        except Exception as e: print(f"Email sender error: {e}")
        return "brain", brain_think(user_text, history)

    # Morning briefing
    if intent == "briefing":
        try:
            from morning_briefing import handle as h
            h(user_text)
            return "briefing", ""
        except Exception as e: print(f"Briefing error: {e}")
        return "brain", brain_think(user_text, history)

    # Google Calendar
    if intent == "calendar":
        try:
            from calendar_agent import handle as h
            reply = h(user_text)
            if reply: return "calendar", reply
            return "calendar", ""    # flow speaks itself
        except Exception as e: print(f"Calendar error: {e}")
        return "brain", brain_think(user_text, history)

    # Google Drive
    if intent == "drive":
        try:
            from drive_agent import handle as h
            reply = h(user_text)
            if reply: return "drive", reply
            return "drive", ""       # flow speaks itself
        except Exception as e: print(f"Drive error: {e}")
        return "brain", brain_think(user_text, history)

    # Contacts
    if intent == "contacts":
        try:
            from contacts_manager import handle as h
            reply = h(user_text)
            if reply: return "contacts", reply
            return "contacts", ""
        except Exception as e: print(f"Contacts error: {e}")
        return "brain", brain_think(user_text, history)

    # Sensor (DHT11 + Flame)
    if intent == "sensor":
        try:
            from sensor_agent import handle as h
            reply = h(user_text)
            if reply: return "sensor", reply
        except Exception as e: print(f"Sensor error: {e}")
        return "brain", brain_think(user_text, history)

    # Web search
    if intent == "search":
        try:
            from search_agent import handle as h
            reply = h(user_text)
            if reply: return "search", reply
        except Exception as e: print(f"Search error: {e}")
        return "brain", brain_think(user_text, history)

    # Camera
    if intent == "camera":
        try:
            from camera_agent import handle as h
            reply = h(user_text)
            if reply: return "camera", reply
            return "camera", ""
        except Exception as e: print(f"Camera error: {e}")
        return "brain", brain_think(user_text, history)

    # Finance
    if intent == "finance":
        try:
            from finance_agent import handle as h
            reply = h(user_text)
            if reply: return "finance", reply
        except Exception as e: print(f"Finance error: {e}")
        return "brain", brain_think(user_text, history)

    # Travel — Amadeus flight search
    if intent == "travel":
        try:
            from travel_agent import handle as travel_handle
            reply = travel_handle(user_text)
            return "travel", reply or ""
        except Exception as e:
            print(f"Travel error: {e}")
        return "brain", brain_think(user_text, history)

    # Flight search
    if intent == "flight":
        try:
            from flight_agent import handle as flight_handle
            reply = flight_handle(user_text)
            return "flight", reply or ""
        except Exception as e:
            print(f"Flight error: {e}")
        return "brain", brain_think(user_text, history)

    # Zepto Café ordering
    if intent == "zepto":
        try:
            from zomato_agent import handle as zepto_handle, is_logged_in
            if not is_logged_in():
                return "zepto", (
                    "Zepto is not set up yet Shivank. "
                    "Run python zepto_agent.py --login in your terminal first."
                )
            reply = zepto_handle(user_text)
            return "zepto", reply or ""
        except Exception as e:
            print(f"Zepto error: {e}")
        return "brain", brain_think(user_text, history)

    # Zomato food ordering (official MCP)
    if intent == "zomato":
        try:
            from zomato_agent import handle as zomato_handle, is_available
            if not is_available():
                return "zomato", (
                    "Node.js is not installed sir. "
                    "Please install it from nodejs.org to use Zomato ordering."
                )
            reply = zomato_handle(user_text)
            return "zomato", reply or ""
        except Exception as e:
            print(f"Zomato error: {e}")
        return "brain", brain_think(user_text, history)

    # Swiggy food ordering
    if intent == "swiggy":
        try:
            from swiggy_agent import handle as swiggy_handle, is_logged_in
            if not is_logged_in():
                return "swiggy", (
                    "Swiggy is not set up yet Shivank. "
                    "Please run python swiggy underscore agent dot py dash dash login "
                    "in your terminal first."
                )
            reply = swiggy_handle(user_text)
            return "swiggy", reply or ""
        except Exception as e:
            print(f"Swiggy error: {e}")
        return "brain", brain_think(user_text, history)

    # Coding
    if intent == "coding":
        try:
            from coding_agent import run as h
            reply = h(user_text)
            return "coding", reply
        except Exception as e: print(f"Coding error: {e}")
        return "brain", brain_think(user_text, history)

    # Project scaffold
    if intent == "project":
        try:
            from coding_agent import run as h
            reply = h(
                f"Create a project scaffold for: {user_text}. "
                f"Make a main.py with basic structure and comments."
            )
            return "project", reply
        except Exception as e: print(f"Project error: {e}")
        return "brain", brain_think(user_text, history)

    # Desktop automation
    if intent == "desktop":
        try:
            from crew_orchestrator import route_to_crew
            reply = route_to_crew("desktop", user_text)
            return "desktop", reply
        except Exception as e: print(f"Desktop error: {e}")
        return "brain", brain_think(user_text, history)

    # Default brain — with auto search fallback
    reply = brain_think(user_text, history)
    try:
        from search_agent import should_search, search_and_summarize
        if should_search(user_text, reply):
            print("[Router] Brain uncertain — falling back to web search")
            search_reply = search_and_summarize(user_text, user_text)
            if search_reply:
                return "search", search_reply
    except Exception:
        pass
    return "brain", reply