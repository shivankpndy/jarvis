"""
JARVIS Contacts Manager
Stores contacts locally in D:\JARVIS\contacts.json
JARVIS checks here before sending emails/messages.
If contact not found, asks to save it.
"""
import json
import os
import re
import threading

CONTACTS_FILE = r"D:\JARVIS\contacts.json"
_lock         = threading.Lock()
_speak_fn     = None
_listen_fn    = None


def set_speak(fn):  global _speak_fn;  _speak_fn  = fn
def set_listen(fn): global _listen_fn; _listen_fn = fn


def _speak(text):
    if _speak_fn: _speak_fn(text)
    else: print(f"[Contacts] {text}")

def _listen(timeout=10) -> str:
    if _listen_fn: return _listen_fn(timeout=timeout) or ""
    return ""


def _ask(prompt: str, timeout: int = 10) -> str:
    """Speak prompt, listen, fall back to terminal typing if voice fails."""
    _speak(prompt)
    result = _listen(timeout=timeout)
    if result:
        return result.strip()
    _speak("I didn't catch that. Please type it below.")
    print(f"\n>>> {prompt}")
    try:
        typed = input("You: ").strip()
        return typed
    except Exception:
        return ""


def _load() -> dict:
    try:
        if os.path.exists(CONTACTS_FILE):
            with open(CONTACTS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"[Contacts] Load error: {e}")
    return {}


def _save(contacts: dict):
    try:
        os.makedirs(os.path.dirname(CONTACTS_FILE), exist_ok=True)
        with open(CONTACTS_FILE, "w") as f:
            json.dump(contacts, f, indent=2)
    except Exception as e:
        print(f"[Contacts] Save error: {e}")


def get_all() -> dict:
    with _lock:
        return _load()


def find(name: str) -> str | None:
    """
    Look up contact by name.
    Returns email string if found, None if not.
    Case-insensitive, partial match supported.
    """
    contacts = _load()
    name_lower = name.lower().strip()

    # Exact match first
    if name_lower in contacts:
        return contacts[name_lower]["email"]

    # Partial match
    for key, val in contacts.items():
        if name_lower in key or key in name_lower:
            return val["email"]

    return None


def add(name: str, email: str, phone: str = "") -> bool:
    """Add or update a contact."""
    with _lock:
        contacts = _load()
        contacts[name.lower().strip()] = {
            "name":  name.strip(),
            "email": email.strip().lower(),
            "phone": phone.strip(),
        }
        _save(contacts)
    print(f"[Contacts] Saved: {name} → {email}")
    return True


def remove(name: str) -> bool:
    with _lock:
        contacts = _load()
        key = name.lower().strip()
        if key in contacts:
            del contacts[key]
            _save(contacts)
            return True
    return False


def list_contacts() -> list:
    """Return list of contact dicts for voice readout."""
    contacts = _load()
    return [
        {"name": v["name"], "email": v["email"], "phone": v.get("phone", "")}
        for v in contacts.values()
    ]


def resolve_or_ask(name_or_email: str) -> str | None:
    """
    Try to resolve a name to email.
    If not found, ask user if they want to add it.
    Returns email string or None if cancelled.
    """
    # Already an email address
    if "@" in name_or_email:
        # Offer to save it
        threading.Thread(
            target=_offer_to_save_email,
            args=(name_or_email,),
            daemon=True
        ).start()
        return name_or_email

    # Try contacts lookup
    email = find(name_or_email)
    if email:
        return email

    # Not found — ask to add
    _speak(
        f"I don't have {name_or_email} in your contacts Shivank. "
        f"Should I add them? Say yes and give me their email, or say no to skip."
    )
    response = _listen(timeout=15)
    if not response:
        return None

    r = response.lower()
    if any(w in r for w in ["yes", "yeah", "sure", "add", "save"]):
        # Ask for email
        email_raw = _ask(f"What is {name_or_email}'s email address?", timeout=15)
        if not email_raw:
            _speak("Nothing provided. Skipping.")
            return None

        # Clean up spoken email — "shivank at gmail dot com" → "shivank@gmail.com"
        email_clean = (email_raw.strip()
                       .replace(" at ", "@")
                       .replace(" dot ", ".")
                       .replace(" ", "")
                       .lower())

        if "@" not in email_clean:
            _speak(f"That doesn't look like a valid email. Skipping.")
            return None

        # Ask for phone optionally
        phone_raw = _ask(f"Got it — {email_clean}. Should I also save a phone number for {name_or_email}? Say the number or say skip.", timeout=10)
        phone = ""
        if phone_raw and "skip" not in phone_raw.lower() and "no" not in phone_raw.lower():
            phone = re.sub(r'[^0-9+]', '', phone_raw)

        add(name_or_email, email_clean, phone)
        _speak(f"{name_or_email} saved to your contacts Shivank.")
        return email_clean

    else:
        _speak("Okay, skipping.")
        return None


def _offer_to_save_email(email: str):
    """If user typed a raw email, offer to save it with a name."""
    import time
    time.sleep(2)  # wait for email to send first
    contacts = _load()
    # Check if already saved
    for v in contacts.values():
        if v["email"].lower() == email.lower():
            return
    _speak(
        f"Should I save {email} to your contacts for next time? "
        f"Say yes and tell me their name, or say no."
    )
    response = _listen(timeout=10)
    if not response:
        return
    if any(w in response.lower() for w in ["yes", "yeah", "sure", "save"]):
        _speak("What name should I save them as?")
        name = _listen(timeout=8)
        if name:
            add(name.strip(), email)
            _speak(f"Saved as {name.strip()} Shivank.")


def handle(user_text: str) -> str:
    """Voice command handler for contacts queries."""
    t = user_text.lower()

    if any(k in t for k in ["show contacts", "list contacts", "my contacts", "who are my contacts"]):
        contacts = list_contacts()
        if not contacts:
            return "You have no saved contacts yet Shivank."
        names = ", ".join([c["name"] for c in contacts[:5]])
        total = len(contacts)
        return f"You have {total} contact{'s' if total != 1 else ''} Shivank. Including {names}{'and more.' if total > 5 else '.'}"

    if any(k in t for k in ["add contact", "save contact", "new contact"]):
        threading.Thread(target=_add_contact_flow, daemon=True).start()
        return ""

    if any(k in t for k in ["delete contact", "remove contact"]):
        threading.Thread(target=_remove_contact_flow, args=(user_text,), daemon=True).start()
        return ""

    return ""


def _add_contact_flow():
    _speak("What's the name of the contact?")
    name = _listen(timeout=10)
    if not name:
        _speak("Didn't catch that.")
        return
    _speak(f"What's {name}'s email?")
    email_raw = _listen(timeout=12)
    if not email_raw:
        _speak("Didn't catch that.")
        return
    email = (email_raw.strip()
             .replace(" at ", "@")
             .replace(" dot ", ".")
             .replace(" ", "")
             .lower())
    if "@" not in email:
        _speak("That doesn't look like a valid email.")
        return
    _speak(f"Phone number for {name}? Say skip to skip.")
    phone_raw = _listen(timeout=10)
    phone = ""
    if phone_raw and "skip" not in phone_raw.lower():
        phone = re.sub(r'[^0-9+]', '', phone_raw)
    add(name, email, phone)
    _speak(f"{name} added to your contacts Shivank.")


def _remove_contact_flow(user_text: str):
    # Try to extract name from command
    match = re.search(r'(?:delete|remove)\s+contact\s+(.+)', user_text, re.IGNORECASE)
    name = match.group(1).strip() if match else None
    if not name:
        _speak("Which contact should I remove?")
        name = _listen(timeout=8)
    if not name:
        return
    ok = remove(name)
    if ok:
        _speak(f"{name} removed from contacts Shivank.")
    else:
        _speak(f"I couldn't find {name} in your contacts.")


# ── Extra helpers used by email_sender ───────────────────────────
def resolve_by_name(name: str) -> str:
    """Return email for a contact name, or empty string if not found."""
    contacts = _load()
    name_l   = name.lower().strip()
    for c in contacts:
        if c.get("name", "").lower() == name_l:
            return c.get("email", "")
        # Partial match — first name
        if name_l in c.get("name", "").lower():
            return c.get("email", "")
    return ""


def add_contact(name: str, email: str, phone: str = "") -> bool:
    """Add a contact programmatically (used by email_sender)."""
    contacts = _load()
    # Update if exists
    for c in contacts:
        if c.get("name", "").lower() == name.lower():
            c["email"] = email
            if phone: c["phone"] = phone
            return _save(contacts)
    contacts.append({"name": name.strip(), "email": email.strip(), "phone": phone})
    return _save(contacts)