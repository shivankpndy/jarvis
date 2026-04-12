"""
JARVIS Gmail Agent — reads REAL email content, no hallucination
"""
import imaplib
import email
import os
import re
import time
import threading
from email.header import decode_header
from dotenv import load_dotenv
from llm import chat, chat_raw

load_dotenv(r"D:\JARVIS\.env")

GMAIL_EMAIL    = os.getenv("GMAIL_EMAIL")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
IMAP_SERVER    = "imap.gmail.com"
IMAP_PORT      = 993
CHECK_INTERVAL = 60

_notify_fn     = None
_last_seen_ids = set()


def set_notify(fn):
    global _notify_fn
    _notify_fn = fn


def _connect():
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
    mail.login(GMAIL_EMAIL, GMAIL_PASSWORD)
    return mail


def _decode_str(value) -> str:
    if not value:
        return ""
    parts = decode_header(value)
    result = ""
    for decoded, enc in parts:
        if isinstance(decoded, bytes):
            result += decoded.decode(enc or "utf-8", errors="ignore")
        else:
            result += str(decoded)
    return result.strip()


def _clean_sender(sender: str) -> str:
    """Extract just the name or email from sender string."""
    # Try to get name from "Name <email>" format
    match = re.match(r'^"?([^"<]+)"?\s*<', sender)
    if match:
        name = match.group(1).strip()
        if name:
            return name
    # Fall back to email address
    match = re.search(r'<(.+?)>', sender)
    if match:
        return match.group(1)
    return sender


def _get_body(msg) -> str:
    """Extract plain text body — real content only."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if ct == "text/plain" and "attachment" not in cd:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="ignore")
                    break
                except Exception:
                    pass
        # If no plain text, try HTML and strip tags
        if not body:
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    try:
                        charset = part.get_content_charset() or "utf-8"
                        html = part.get_payload(decode=True).decode(charset, errors="ignore")
                        body = re.sub(r'<[^>]+>', ' ', html)
                        body = re.sub(r'\s+', ' ', body).strip()
                        break
                    except Exception:
                        pass
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="ignore")
        except Exception:
            pass

    # Clean up whitespace
    body = re.sub(r'\s+', ' ', body).strip()
    return body[:1500]  # max 1500 chars for Ollama


def _fetch_email(mail, eid) -> dict:
    """Fetch one email and return dict with real content."""
    try:
        _, msg_data = mail.fetch(eid, "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        subject = _decode_str(msg.get("Subject", "No Subject"))
        sender  = _clean_sender(_decode_str(msg.get("From", "Unknown")))
        date    = _decode_str(msg.get("Date", ""))
        body    = _get_body(msg)
        return {
            "subject": subject,
            "sender":  sender,
            "date":    date,
            "body":    body,
        }
    except Exception as e:
        print(f"[Gmail] Fetch error: {e}")
        return {}


def _summarize_for_voice(email_data: dict) -> str:
    """Summarize REAL email content for voice — no hallucination possible."""
    subject = email_data.get("subject", "")
    sender  = email_data.get("sender", "")
    body    = email_data.get("body", "")

    if not body:
        return f"Email from {sender} with subject: {subject}."

    try:
        prompt = (
            f"Summarize this real email in 2 sentences for voice readout. "
            f"Be concise. Address the user as sir. "
            f"Do NOT make up any details — only use what's in the email below.\n\n"
            f"From: {sender}\n"
            f"Subject: {subject}\n"
            f"Body: {body}\n\n"
            f"Summary:"
        )
        response = chat([{"role": "user", "content": prompt}]) 
        return response.strip()
    except Exception:
        # Safe fallback — no hallucination
        preview = body[:120].strip()
        return f"Email from {sender}. Subject: {subject}. {preview}"


def _is_important(email_data: dict) -> bool:
    """Check if email is important using real content."""
    subject = email_data.get("subject", "")
    body    = email_data.get("body", "")
    sender  = email_data.get("sender", "")
    text    = (subject + " " + body).lower()

    # Keyword fast-path — no Ollama needed
    urgent_words = [
        "urgent", "important", "asap", "immediately", "critical",
        "deadline", "offer", "interview", "payment", "invoice",
        "alert", "verify", "action required", "hackathon",
        "selected", "otp", "password", "security", "transaction",
        "bank", "account", "due", "overdue", "reminder",
    ]
    if any(w in text for w in urgent_words):
        return True

    # Ollama fallback for borderline cases
    try:
        prompt = (
            f"Is this email important enough to interrupt someone? "
            f"Answer only YES or NO.\n\n"
            f"From: {sender}\nSubject: {subject}\n"
            f"Body: {body[:200]}\n\nAnswer:"
        )
        response = chat([{"role": "user", "content": prompt}]) 
        return "YES" in response.upper()
    except Exception:
        return False


# ── Voice command handler ──────────────────────────────────────────
def handle(user_text: str) -> str:
    """Called when user says 'check my emails'."""
    try:
        mail = _connect()
        mail.select("INBOX")

        # Get unread emails
        _, data = mail.search(None, "UNSEEN")
        email_ids = data[0].split()

        if not email_ids:
            mail.logout()
            return "You have no unread emails sir."

        # Read last 5 max
        recent = email_ids[-5:]
        emails = []
        for eid in reversed(recent):
            ed = _fetch_email(mail, eid)
            if ed:
                emails.append(ed)

        mail.logout()

        if not emails:
            return "I couldn't read your emails sir. Please check your connection."

        count = len(email_ids)

        # Build natural spoken response from REAL data
        lines = [f"You have {count} unread email{'s' if count != 1 else ''} sir."]

        for i, ed in enumerate(emails[:3], 1):
            subject = ed.get("subject", "No subject")
            sender  = ed.get("sender", "Unknown")
            lines.append(f"Email {i} from {sender}: {subject}.")

        if count > 3:
            lines.append(f"And {count - 3} more emails.")

        # Summarize the most recent one with real body
        if emails:
            top = emails[0]
            summary = _summarize_for_voice(top)
            lines.append(f"The latest email: {summary}")

        return " ".join(lines)

    except Exception as e:
        print(f"[Gmail] handle error: {e}")
        return f"Could not check emails sir. Error: {str(e)[:80]}"


# ── Background watcher ─────────────────────────────────────────────
def check_emails():
    global _last_seen_ids
    try:
        mail = _connect()
        mail.select("INBOX")
        _, data = mail.search(None, "UNSEEN")
        email_ids = data[0].split()

        if not email_ids:
            mail.logout()
            return

        new_ids = set(email_ids) - _last_seen_ids
        _last_seen_ids = set(email_ids)

        for eid in new_ids:
            ed = _fetch_email(mail, eid)
            if not ed:
                continue
            print(f"[Gmail] New email — {ed['subject']} from {ed['sender']}")
            if _is_important(ed) and _notify_fn:
                summary = _summarize_for_voice(ed)
                _notify_fn(f"Sir, important email from {ed['sender']}. {summary}")

        mail.logout()
    except Exception as e:
        print(f"[Gmail] check_emails error: {e}")


def start_email_watcher():
    def _run():
        global _last_seen_ids
        print(f"[Gmail] Watcher started — checking every {CHECK_INTERVAL}s")
        try:
            mail = _connect()
            mail.select("INBOX")
            _, data = mail.search(None, "UNSEEN")
            _last_seen_ids = set(data[0].split())
            mail.logout()
            print(f"[Gmail] Seeded {len(_last_seen_ids)} existing unread emails")
        except Exception as e:
            print(f"[Gmail] Seed error: {e}")
        while True:
            time.sleep(CHECK_INTERVAL)
            check_emails()
    threading.Thread(target=_run, daemon=True).start()


# ── Morning briefing helpers ───────────────────────────────────────
def get_unread_count() -> int:
    try:
        mail = _connect()
        mail.select("inbox")
        _, data = mail.search(None, "UNSEEN")
        mail.logout()
        return len(data[0].split())
    except Exception as e:
        print(f"[Gmail] get_unread_count error: {e}")
        return 0


def get_top_subjects(n=3) -> list:
    try:
        mail = _connect()
        mail.select("inbox")
        _, data = mail.search(None, "UNSEEN")
        ids = data[0].split()[-n:]
        subjects = []
        for eid in reversed(ids):
            ed = _fetch_email(mail, eid)
            if ed:
                subjects.append(ed["subject"][:60])
        mail.logout()
        return subjects
    except Exception as e:
        print(f"[Gmail] get_top_subjects error: {e}")
        return []
