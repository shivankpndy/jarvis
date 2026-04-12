"""
JARVIS Email Sender
- Each step (recipient, subject, content) is asked separately
- Voice → falls back to terminal typing if nothing heard
- Runs synchronously so terminal input works correctly
"""
CONTACTS = {
    "Macbeth":    "shivankpndy.hq@gmail.com",       # replace with real emails
    "Roman":    "shivankpndy.sf@gmail.com",
    "Rose":  "shivankpndy.studio@gmail.com",
}
import os, re, smtplib, threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from llm import chat, chat_raw

load_dotenv(r"D:\JARVIS\.env")

GMAIL_EMAIL    = os.getenv("GMAIL_EMAIL", "")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

_speak_fn  = None
_listen_fn = None
_notify_fn = None

def set_speak(fn):  global _speak_fn;  _speak_fn  = fn
def set_listen(fn): global _listen_fn; _listen_fn = fn
def set_notify(fn): global _notify_fn; _notify_fn = fn

def _speak(text: str):
    if _speak_fn: _speak_fn(text)
    else: print(f"[Email] {text}")

def _listen(timeout=10) -> str:
    if _listen_fn: return _listen_fn(timeout=timeout) or ""
    return ""


# ── Ask: voice first, then terminal typing ────────────────────────
def _ask(prompt: str, timeout: int = 12, allow_long: bool = False) -> str:
    _speak(prompt)
    result = _listen(timeout=timeout if not allow_long else 20)
    if result and len(result.strip()) > 1:
        return result.strip()
    # Voice got nothing — go straight to terminal
    print(f"\n[Email] {prompt}")
    print("[Email] Type your answer (or press Enter to cancel):")
    try:
        typed = input(">>> ").strip()
        return typed
    except Exception:
        return ""


# ── Resolve name → email ──────────────────────────────────────────
def _resolve_email(name_or_email: str) -> str:
    """If it looks like an email return it directly, else contacts lookup."""
    s = name_or_email.strip()
    if "@" in s:
        return s
    try:
        from contacts_manager import resolve_by_name
        return resolve_by_name(s) or ""
    except Exception:
        return ""


# ── Extract recipient from command text ──────────────────────────
def _extract_recipient(text: str) -> str:
    """
    Pull recipient from phrases like:
      'send an email to rahul'
      'send an email to shivankpndy@gmail.com'
      'email mom about the meeting'
    Returns raw name/email string or "".
    """
    patterns = [
        # email address directly
        r'to\s+([\w.\-+]+@[\w.\-]+\.[a-zA-Z]{2,})',
        # 'to <name>' before 'about/saying/regarding' or end
        r'(?:send|write|compose)(?:\s+an?)?\s+(?:email|mail)\s+to\s+([\w\s]+?)(?:\s+about|\s+saying|\s+regarding|\s*$)',
        # 'email <name>' shorthand
        r'\bemail\s+([\w\s]+?)(?:\s+about|\s+saying|\s+regarding|\s*$)',
    ]
    t = text.lower().strip()
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            result = m.group(1).strip()
            # Strip stray words
            for noise in ["an", "a", "the", "please", "now"]:
                result = re.sub(rf'\b{noise}\b', '', result).strip()
            if result:
                return result
    return ""


# ── Draft body via LLM ────────────────────────────────────────────
def _draft_body(to: str, subject: str, notes: str) -> str:
    try:
        prompt = (
            f"Draft a short professional email.\n"
            f"To: {to}\nSubject: {subject}\nKey points: {notes}\n"
            f"Return ONLY the email body — no subject line, no To:, no signature. "
            f"3-5 sentences max. Plain text."
        )
        return chat_raw(prompt).strip()
    except Exception as e:
        print(f"[Email] Draft error: {e}")
        return notes


# ── SMTP send ─────────────────────────────────────────────────────
def _send(to_email: str, subject: str, body: str) -> tuple[bool, str]:
    if not GMAIL_EMAIL:    return False, "GMAIL_EMAIL not set in .env"
    if not GMAIL_PASSWORD: return False, "GMAIL_APP_PASSWORD not set in .env"
    if "@" not in to_email: return False, f"Invalid recipient: {to_email}"

    print(f"[Email] → {to_email}  |  Subject: {subject}")
    try:
        msg            = MIMEMultipart("alternative")
        msg["From"]    = GMAIL_EMAIL
        msg["To"]      = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.set_debuglevel(1)
            server.login(GMAIL_EMAIL, GMAIL_PASSWORD)
            server.sendmail(GMAIL_EMAIL, to_email, msg.as_string())
            print("[Email] ✓ Sent")
        return True, ""

    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail authentication failed — use a 16-char App Password, "
            "not your regular password. "
            "Google Account → Security → 2-Step Verification → App Passwords."
        )
    except smtplib.SMTPRecipientsRefused:
        return False, f"Recipient {to_email} refused by Gmail."
    except Exception as e:
        return False, f"Send error: {e}"


# ── Main entry — called by agent_router ──────────────────────────
def handle(user_text: str):
    """
    Runs synchronously in the calling thread.
    (No background thread — avoids input() race condition.)
    """
    _email_flow(user_text)


def _email_flow(user_text: str):
    t = user_text.lower().strip()

    # ── Step 1: Recipient ─────────────────────────────────────────
    recipient_raw = _extract_recipient(t)

    if not recipient_raw:
        recipient_raw = _ask("Who should I send this email to?")
        if not recipient_raw:
            _speak("Email cancelled.")
            return

    print(f"[Email] Recipient raw: '{recipient_raw}'")
    to_email = _resolve_email(recipient_raw)

    if not to_email:
        to_email = _ask(
            f"I don't have an email for {recipient_raw}. "
            f"What is their email address?"
        )

    # Clean up whatever was typed/spoken — extract just the email
    if to_email:
        m = re.search(r'[\w.\-+]+@[\w.\-]+\.[a-zA-Z]{2,}', to_email)
        if m:
            to_email = m.group(0)

    if not to_email or "@" not in to_email:
        _speak("I need a valid email address. Email cancelled.")
        return

    print(f"[Email] Sending to: {to_email}")

    # Offer to save unknown names to contacts
    if "@" not in recipient_raw:
        save_resp = _ask(
            f"Should I save {to_email} as {recipient_raw} in your contacts?",
            timeout=6
        )
        if save_resp and any(w in save_resp.lower() for w in ["yes","sure","save","yeah","yep"]):
            try:
                from contacts_manager import add_contact
                add_contact(recipient_raw, to_email)
                _speak(f"Saved {recipient_raw} to contacts.")
            except Exception as e:
                print(f"[Email] Contact save error: {e}")

    # ── Step 2: Subject ───────────────────────────────────────────
    subject = ""
    for pat in [r'about\s+(.+?)(?:\s+saying|\s+that|\s*$)',
                r'regarding\s+(.+?)(?:\s*$)']:
        m = re.search(pat, t)
        if m:
            subject = m.group(1).strip().capitalize()
            break

    if not subject:
        subject = _ask("What is the subject?")
        if not subject:
            _speak("No subject — email cancelled.")
            return

    print(f"[Email] Subject: {subject}")

    # ── Step 3: Content ───────────────────────────────────────────
    notes = _ask(
        "What should the email say? Give me the key points.",
        allow_long=True, timeout=20
    )
    if not notes:
        _speak("No content — email cancelled.")
        return

    # ── Step 4: Draft ─────────────────────────────────────────────
    _speak("Writing the email now.")
    body = _draft_body(recipient_raw or to_email, subject, notes)
    print(f"[Email] Draft:\n{body}")
    _speak(f"Here is the draft: {body}")

    # ── Step 5: Confirm ───────────────────────────────────────────
    confirm = _ask("Say send it to send, edit to change, or cancel.")
    if not confirm:
        _speak("No response — email cancelled.")
        return

    c = confirm.lower()

    if any(w in c for w in ["send","yes","do it","go ahead","confirm","ok"]):
        ok, err = _send(to_email, subject, body)
        if ok:
            _speak(f"Email sent to {to_email} successfully sir.")
            if _notify_fn: _notify_fn(f"Email sent → {to_email}: {subject}")
        else:
            _speak(f"Email failed. {err}")
            print(f"[Email] FAILED: {err}")

    elif any(w in c for w in ["edit","change","modify","rewrite","update"]):
        new_notes = _ask("What changes should I make?", allow_long=True)
        if not new_notes:
            _speak("No changes — email cancelled.")
            return
        body = _draft_body(recipient_raw or to_email, subject, new_notes)
        _speak(f"Updated: {body}")
        confirm2 = _ask("Send this version? Say send it or cancel.")
        if confirm2 and any(w in confirm2.lower() for w in ["send","yes","do it"]):
            ok, err = _send(to_email, subject, body)
            if ok:
                _speak(f"Email sent to {to_email} sir.")
                if _notify_fn: _notify_fn(f"Email sent → {to_email}: {subject}")
            else:
                _speak(f"Email failed. {err}")
        else:
            _speak("Email cancelled.")
    else:
        _speak("Email cancelled.")