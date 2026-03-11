"""
JARVIS Email Sender
- Each step (recipient, subject, content) is asked separately
- If voice fails → immediately offers terminal text input
- Prints full SMTP debug so you can see exactly why send fails
"""
import os, re, smtplib, threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import ollama

load_dotenv(r"D:\JARVIS\.env")

GMAIL_EMAIL    = os.getenv("GMAIL_EMAIL", "")
GMAIL_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
BRAIN_MODEL    = "llama3.2:3b"

_speak_fn     = None
_listen_fn    = None
_notify_fn    = None

def set_speak(fn):     global _speak_fn;  _speak_fn  = fn
def set_listen(fn):    global _listen_fn; _listen_fn = fn
def set_notify(fn):    global _notify_fn; _notify_fn = fn

def _speak(text: str):
    if _speak_fn: _speak_fn(text)
    else: print(f"[Email] {text}")

def _listen(timeout=10) -> str:
    if _listen_fn: return _listen_fn(timeout=timeout) or ""
    return ""


# ── Core helper: ask by voice, fall back to typing ───────────────────────────
def _ask(prompt: str, timeout: int = 12, allow_long: bool = False) -> str:
    """
    Speak prompt → listen → if nothing heard, ask user to type in terminal.
    Returns the response string, or "" if user gives nothing.
    """
    _speak(prompt)
    result = _listen(timeout=timeout if not allow_long else 20)
    if result:
        return result.strip()

    # Voice failed — switch to typing
    _speak("I didn't catch that. Please type your response below.")
    print(f"\n>>> {prompt}")
    print(">>> (Type below and press Enter — leave blank to cancel)")
    try:
        typed = input("You: ").strip()
        return typed
    except Exception:
        return ""


# ── Contacts lookup ───────────────────────────────────────────────────────────
def _resolve_email(name_or_email: str) -> str:
    if "@" in name_or_email:
        return name_or_email.strip()
    try:
        from contacts_manager import resolve_by_name
        return resolve_by_name(name_or_email) or ""
    except Exception:
        return ""


# ── Draft with Ollama ─────────────────────────────────────────────────────────
def _draft_body(to: str, subject: str, notes: str) -> str:
    try:
        resp = ollama.chat(
            model=BRAIN_MODEL,
            messages=[{"role": "user", "content":
                f"Draft a short professional email.\n"
                f"To: {to}\nSubject: {subject}\nKey points: {notes}\n"
                f"Return ONLY the email body — no subject, no To:, no signature. "
                f"3-5 sentences max. Plain text only."
            }]
        )
        return resp["message"]["content"].strip()
    except Exception as e:
        print(f"[Email] Draft error: {e}")
        return notes


# ── Send via Gmail SMTP ───────────────────────────────────────────────────────
def _send(to_email: str, subject: str, body: str) -> tuple[bool, str]:
    """Returns (success, error_message)."""
    if not GMAIL_EMAIL:
        return False, "GMAIL_EMAIL not set in .env"
    if not GMAIL_PASSWORD:
        return False, "GMAIL_APP_PASSWORD not set in .env"
    if "@" not in to_email:
        return False, f"Invalid recipient email: {to_email}"

    print(f"\n[Email] Sending to: {to_email}")
    print(f"[Email] Subject:    {subject}")
    print(f"[Email] From:       {GMAIL_EMAIL}")
    print(f"[Email] Body:\n{body}\n")

    try:
        msg            = MIMEMultipart("alternative")
        msg["From"]    = GMAIL_EMAIL
        msg["To"]      = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        print("[Email] Connecting to smtp.gmail.com:465...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.set_debuglevel(1)          # prints SMTP conversation to console
            print("[Email] Logging in...")
            server.login(GMAIL_EMAIL, GMAIL_PASSWORD)
            print("[Email] Sending message...")
            server.sendmail(GMAIL_EMAIL, to_email, msg.as_string())
            print("[Email] ✓ Message accepted by Gmail")
        return True, ""

    except smtplib.SMTPAuthenticationError:
        return False, (
            "Gmail authentication failed. "
            "Make sure GMAIL_APP_PASSWORD in your .env is a 16-character App Password, "
            "not your regular Gmail password. "
            "Go to Google Account → Security → 2-Step Verification → App Passwords."
        )
    except smtplib.SMTPRecipientsRefused:
        return False, f"Recipient {to_email} was refused by Gmail."
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {e}"
    except Exception as e:
        return False, f"Send error: {e}"


# ── Main email flow ───────────────────────────────────────────────────────────
def handle(user_text: str):
    threading.Thread(target=_email_flow, args=(user_text,), daemon=True).start()


def _email_flow(user_text: str):
    t = user_text.lower().strip()

    # ── STEP 1: Recipient ─────────────────────────────────────────────────────
    recipient_raw = ""

    # Try to extract from command: "email to Rahul", "send email to mom"
    for pat in [
        r'(?:email|send|write)(?:\s+an?)?\s+(?:email\s+)?to\s+([a-zA-Z\s]+?)(?:\s+about|\s+saying|\s+regarding|\s*$)',
        r'(?:email)\s+([a-zA-Z]+)',
    ]:
        m = re.search(pat, t)
        if m:
            recipient_raw = m.group(1).strip()
            break

    if not recipient_raw:
        recipient_raw = _ask("Who should I send this email to Shivank?")
        if not recipient_raw:
            _speak("Email cancelled.")
            return

    to_email = _resolve_email(recipient_raw)

    if not to_email:
        to_email = _ask(
            f"I don't have an email address for {recipient_raw}. "
            f"What is their email address?",
            timeout=12
        )
        if not to_email or "@" not in to_email:
            _speak("I need a valid email address to continue. Email cancelled.")
            return

        # Offer to save to contacts
        _speak(f"Should I save {to_email} for {recipient_raw} in your contacts?")
        save_resp = _listen(timeout=7)
        if save_resp and any(w in save_resp.lower() for w in ["yes", "sure", "save", "yeah"]):
            try:
                from contacts_manager import add_contact
                add_contact(recipient_raw, to_email)
                _speak(f"Saved {recipient_raw} to your contacts.")
            except Exception as e:
                print(f"[Email] Contact save error: {e}")

    _speak(f"Got it. Sending to {to_email}.")
    print(f"[Email] Recipient resolved: {to_email}")

    # ── STEP 2: Subject ───────────────────────────────────────────────────────
    subject = ""

    # Try to extract from command
    for pat in [
        r'about\s+(.+?)(?:\s+saying|\s+that|\s*$)',
        r'regarding\s+(.+?)(?:\s*$)',
    ]:
        m = re.search(pat, t)
        if m:
            subject = m.group(1).strip().capitalize()
            break

    if not subject:
        subject = _ask("What is the subject of the email?")
        if not subject:
            _speak("No subject — email cancelled.")
            return

    _speak(f"Subject: {subject}.")
    print(f"[Email] Subject: {subject}")

    # ── STEP 3: Email content / key points ───────────────────────────────────
    content_notes = _ask(
        "What should the email say? "
        "Give me the key points and I will write it up.",
        allow_long=True,
        timeout=20
    )
    if not content_notes:
        _speak("No content provided — email cancelled.")
        return

    print(f"[Email] Notes: {content_notes}")

    # ── STEP 4: Draft ─────────────────────────────────────────────────────────
    _speak("Writing the email now.")
    body = _draft_body(recipient_raw or to_email, subject, content_notes)
    print(f"[Email] Draft:\n{body}")

    _speak(f"Here is the draft: {body}")

    # ── STEP 5: Confirm ───────────────────────────────────────────────────────
    confirm = _ask("Say send it to send, edit to make changes, or cancel to stop.")

    if not confirm:
        _speak("No response — email cancelled.")
        return

    c = confirm.lower()

    if any(w in c for w in ["send", "yes", "do it", "go ahead", "confirm", "ok"]):
        ok, err = _send(to_email, subject, body)
        if ok:
            _speak(f"Email sent to {to_email} successfully Shivank.")
            if _notify_fn: _notify_fn(f"Email sent → {to_email}: {subject}")
        else:
            _speak(f"Email failed to send. {err}")
            print(f"[Email] SEND FAILED: {err}")

    elif any(w in c for w in ["edit", "change", "modify", "rewrite", "update"]):
        new_notes = _ask("What changes should I make?", allow_long=True)
        if not new_notes:
            _speak("No changes provided — email cancelled.")
            return
        body = _draft_body(recipient_raw or to_email, subject, new_notes)
        _speak(f"Updated draft: {body}")
        confirm2 = _ask("Shall I send this version? Say send it or cancel.")
        if confirm2 and any(w in confirm2.lower() for w in ["send", "yes", "do it"]):
            ok, err = _send(to_email, subject, body)
            if ok:
                _speak(f"Email sent to {to_email} Shivank.")
                if _notify_fn: _notify_fn(f"Email sent → {to_email}: {subject}")
            else:
                _speak(f"Email failed. {err}")
                print(f"[Email] SEND FAILED: {err}")
        else:
            _speak("Email cancelled.")
    else:
        _speak("Email cancelled.")