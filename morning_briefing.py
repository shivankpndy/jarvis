"""
JARVIS Morning Briefing Agent
Fires automatically at 8:00 AM every day.
Briefs sir on: date, pending timers, unread emails, Slack DMs, memory reminders.
Can also be triggered manually: "Good morning JARVIS" / "Morning briefing"
"""
import schedule
import threading
import time
import datetime
from llm import chat, chat_raw

_notify_fn   = None
_speak_fn    = None


def set_notify(fn):
    global _notify_fn
    _notify_fn = fn


def set_speak(fn):
    """Pass in jarvis.py speak_raw so briefing uses voice directly."""
    global _speak_fn
    _speak_fn = fn


def _say(text):
    if _speak_fn:
        _speak_fn(text)
    elif _notify_fn:
        _notify_fn(text)
    else:
        print(f"[Briefing] {text}")


# ── Gather data from all agents ────────────────────────────────────
def _get_email_summary():
    try:
        from gmail_agent import get_unread_count, get_top_subjects
        count    = get_unread_count()
        subjects = get_top_subjects(3)
        if count == 0:
            return "No unread emails."
        lines = [f"{count} unread email{'s' if count != 1 else ''}."]
        if subjects:
            lines.append("Top subjects: " + ", ".join(subjects))
        return " ".join(lines)
    except Exception as e:
        print(f"[Briefing] Email error: {e}")
        return ""


def _get_slack_summary():
    try:
        from slack_agent import get_unread_count
        count = get_unread_count()
        if count == 0:
            return "No new Slack messages."
        return f"{count} unread Slack message{'s' if count != 1 else ''}."
    except Exception as e:
        print(f"[Briefing] Slack error: {e}")
        return ""


def _get_memory_reminders():
    try:
        from memory_agent import get_memory_summary
        summary = get_memory_summary()
        if summary:
            return summary[:300]
        return ""
    except Exception as e:
        print(f"[Briefing] Memory error: {e}")
        return ""


def _get_weather():
    """Search for weather using search agent."""
    try:
        from search_agent import search
        result = search("weather today Lucknow India")
        if result and len(result) > 20:
            # Trim to one sentence
            import re
            sentences = re.split(r'(?<=[.!?])\s+', result)
            return sentences[0] if sentences else ""
        return ""
    except Exception as e:
        print(f"[Briefing] Weather error: {e}")
        return ""


# ── Build briefing text with Ollama ───────────────────────────────
def _build_briefing(parts: dict) -> str:
    now  = datetime.datetime.now()
    date = now.strftime("%A, %B %d %Y")
    hour = now.hour

    if hour < 12:   greeting = "Good morning"
    elif hour < 17: greeting = "Good afternoon"
    else:           greeting = "Good evening"

    # Build raw data string
    data_lines = [f"Date: {date}"]
    if parts.get("weather"):
        data_lines.append(f"Weather: {parts['weather']}")
    if parts.get("emails"):
        data_lines.append(f"Emails: {parts['emails']}")
    if parts.get("slack"):
        data_lines.append(f"Slack: {parts['slack']}")
    if parts.get("memory"):
        data_lines.append(f"Context: {parts['memory']}")

    raw = "\n".join(data_lines)

    try:
        prompt = (
            f"You are JARVIS giving sir his morning briefing. "
            f"Today is {date}. Write a natural, concise spoken briefing "
            f"in 4-6 sentences. Start with '{greeting} sir.' "
            f"Address the user as sir. Be warm but efficient. "
            f"Include the date, then cover each data point naturally. "
            f"Do not use bullet points — speak in flowing sentences.\n\n"
            f"Data:\n{raw}\n\nBriefing:"
        )
        response = chat([{"role": "user", "content": prompt}]) 
        return response.strip()
    except Exception as e:
        print(f"[Briefing] Ollama error: {e}")
        # Fallback plain briefing
        lines = [f"{greeting} sir. Today is {date}."]
        if parts.get("emails"):
            lines.append(parts["emails"])
        if parts.get("slack"):
            lines.append(parts["slack"])
        return " ".join(lines)


# ── Deliver the briefing ───────────────────────────────────────────
def deliver_briefing(manual=False):
    print("[Briefing] Gathering data...")

    parts = {}

    # Collect all data (non-blocking with threads)
    results = {}

    def _collect(key, fn):
        try:
            results[key] = fn()
        except Exception:
            results[key] = ""

    threads = [
        threading.Thread(target=_collect, args=("weather", _get_weather),      daemon=True),
        threading.Thread(target=_collect, args=("emails",  _get_email_summary), daemon=True),
        threading.Thread(target=_collect, args=("slack",   _get_slack_summary), daemon=True),
        threading.Thread(target=_collect, args=("memory",  _get_memory_reminders), daemon=True),
    ]
    for t in threads: t.start()
    for t in threads: t.join(timeout=10)   # max 10s to collect all data

    parts = results
    print(f"[Briefing] Data: {parts}")

    briefing = _build_briefing(parts)
    print(f"[Briefing] Delivering: {briefing}")
    _say(briefing)


# ── Scheduler ─────────────────────────────────────────────────────
def start_briefing_scheduler(time_str="08:00"):
    def _run():
        schedule.every().day.at(time_str).do(deliver_briefing)
        print(f"[Briefing] Scheduled daily at {time_str}")
        while True:
            schedule.run_pending()
            time.sleep(30)

    threading.Thread(target=_run, daemon=True).start()


# ── Voice command handler ──────────────────────────────────────────
def handle(user_text: str) -> str:
    text = user_text.lower()

    if any(k in text for k in [
        "morning briefing", "good morning jarvis", "good morning",
        "daily briefing", "what's my briefing", "brief me",
        "morning update", "what's happening today", "morning report",
        "start my day",
    ]):
        # Deliver in background so voice pipeline doesn't block
        threading.Thread(target=deliver_briefing, args=(True,), daemon=True).start()
        return ""   # empty = briefing will speak itself via _say

    return ""
