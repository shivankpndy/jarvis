import os
import time
import threading
from dotenv import load_dotenv
import ollama

load_dotenv(r"D:\JARVIS\.env")

SLACK_TOKEN    = os.getenv("SLACK_TOKEN")
CHECK_INTERVAL = 30   # check every 30 seconds
BRAIN_MODEL    = "llama3.2:3b"

_notify_fn      = None
_last_ts        = {}   # channel_id → last timestamp seen


def set_notify(fn):
    global _notify_fn
    _notify_fn = fn


def _headers():
    return {
        "Authorization": f"Bearer {SLACK_TOKEN}",
        "Content-Type":  "application/json"
    }


def _get(url, params=None):
    import urllib.request
    import urllib.parse
    import json
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=_headers())
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _summarize_message(user: str, text: str, channel: str) -> str:
    """Summarize a Slack message for voice."""
    try:
        prompt = f"""Summarize this Slack message in one sentence for a voice assistant.
Address the user as sir. Be very concise.

From: {user}
Channel: {channel}
Message: {text[:400]}

Summary:"""
        response = ollama.chat(
            model=BRAIN_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        return response["message"]["content"].strip()
    except Exception:
        return f"Slack message from {user} in {channel}."


def _get_dm_channels():
    """Get all DM channels."""
    try:
        data = _get("https://slack.com/api/conversations.list",
                    {"types": "im", "limit": "50"})
        if data.get("ok"):
            return data.get("channels", [])
    except Exception as e:
        print(f"Slack DM list error: {e}")
    return []


def _get_username(user_id: str) -> str:
    """Resolve user ID to display name."""
    try:
        data = _get("https://slack.com/api/users.info", {"user": user_id})
        if data.get("ok"):
            profile = data["user"].get("profile", {})
            return profile.get("display_name") or profile.get("real_name", user_id)
    except Exception:
        pass
    return user_id


def check_slack():
    """Check DMs and mentions for new messages."""
    global _last_ts
    try:
        notifications = []

        # Check DM channels
        dm_channels = _get_dm_channels()
        for ch in dm_channels:
            ch_id  = ch["id"]
            oldest = _last_ts.get(ch_id, str(time.time() - 300))  # last 5 min on first run

            data = _get("https://slack.com/api/conversations.history", {
                "channel": ch_id,
                "oldest":  oldest,
                "limit":   "5"
            })

            if not data.get("ok"):
                continue

            messages = data.get("messages", [])
            if not messages:
                continue

            # Update last seen timestamp
            _last_ts[ch_id] = messages[0]["ts"]

            for msg in reversed(messages):
                # Skip bot messages
                if msg.get("bot_id") or msg.get("subtype"):
                    continue

                user    = _get_username(msg.get("user", "Unknown"))
                text    = msg.get("text", "")
                summary = _summarize_message(user, text, "Direct Message")
                notifications.append(summary)
                print(f"Slack DM from {user}: {text[:60]}")

        # Notify JARVIS
        if notifications and _notify_fn:
            for note in notifications[:3]:  # max 3 at a time
                _notify_fn(f"Sir, you have a Slack message. {note}")

    except Exception as e:
        print(f"Slack check error: {e}")


def get_recent_messages(count=3) -> str:
    """Called when user asks 'check my Slack'."""
    try:
        dm_channels = _get_dm_channels()
        if not dm_channels:
            return "No recent Slack messages sir."

        all_messages = []
        for ch in dm_channels[:5]:
            ch_id = ch["id"]
            data  = _get("https://slack.com/api/conversations.history", {
                "channel": ch_id,
                "limit":   "3"
            })
            if not data.get("ok"):
                continue
            for msg in data.get("messages", []):
                if msg.get("bot_id") or msg.get("subtype"):
                    continue
                user = _get_username(msg.get("user", "Unknown"))
                text = msg.get("text", "")
                all_messages.append(f"{user}: {text[:100]}")

        if not all_messages:
            return "No recent Slack direct messages sir."

        result = f"You have {len(all_messages)} recent Slack messages sir. "
        result += ". ".join(all_messages[:count])
        return result

    except Exception as e:
        return f"Could not check Slack sir. Error: {e}"


def handle(user_text: str) -> str:
    """Called by agent_router when user asks about Slack."""
    text = user_text.lower()
    if any(k in text for k in ["check slack", "slack messages", "any slack",
                                "slack updates", "slack dms", "my slack"]):
        return get_recent_messages()
    return ""


def start_slack_watcher():
    """Background thread — checks Slack every 30 seconds."""
    def _run():
        print(f"Slack watcher started — checking every {CHECK_INTERVAL}s")
        # Seed timestamps so we don't notify old messages on startup
        try:
            dm_channels = _get_dm_channels()
            for ch in dm_channels:
                ch_id = ch["id"]
                data  = _get("https://slack.com/api/conversations.history", {
                    "channel": ch_id,
                    "limit":   "1"
                })
                if data.get("ok") and data.get("messages"):
                    _last_ts[ch_id] = data["messages"][0]["ts"]
            print(f"Slack: seeded {len(_last_ts)} channels")
        except Exception as e:
            print(f"Slack seed error: {e}")

        while True:
            time.sleep(CHECK_INTERVAL)
            check_slack()

    threading.Thread(target=_run, daemon=True).start()


# ── Helper for morning briefing ───────────────────────────────────
def get_unread_count() -> int:
    """Return number of unread Slack DMs since last check."""
    try:
        return len(_unseen_messages) if '_unseen_messages' in globals() else 0
    except Exception:
        return 0