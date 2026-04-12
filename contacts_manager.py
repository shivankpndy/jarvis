"""
JARVIS Contacts Manager
Stores contacts locally in D:\JARVIS\contacts.json
JARVIS checks here before sending emails/messages.
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


def _ask(prompt: str, timeout: int = 12) -> str:
    """Speak prompt, listen, fall back to terminal input if voice fails."""
    _speak(prompt)
    result = _listen(timeout=timeout)
    if result:
        return result.strip()
    # Voice failed — fall back to typed input
    _speak("I didn't catch that. Please type it below.")
    print(f"\n>>> {prompt}")
    try:
        return input("You: ").strip()
    except Exception:
        return ""


# ── Storage ───────────────────────────────────────────────────────
# Format: { "name_lowercase": {"name": str, "email": str, "phone": str} }

def _load() -> dict:
    try:
        if os.path.exists(CONTACTS_FILE):
            with open(CONTACTS_FILE, "r") as f:
                data = json.load(f)
            # ── Migrate old list format → dict ────────────────────
            if isinstance(data, list):
                migrated = {}
                for item in data:
                    if isinstance(item, dict) and "name" in item:
                        key = item["name"].lower().strip()
                        migrated[key] = {
                            "name":  item.get("name", "").strip(),
                            "email": item.get("email", "").strip().lower(),
                            "phone": item.get("phone", "").strip(),
                        }
                print(f"[Contacts] Migrated {len(migrated)} contacts from old list format")
                _save_raw(migrated)
                return migrated
            return data
    except Exception as e:
        print(f"[Contacts] Load error: {e}")
    return {}


def _save_raw(contacts: dict):
    """Write dict to file — call inside _lock."""
    try:
        os.makedirs(os.path.dirname(CONTACTS_FILE), exist_ok=True)
        with open(CONTACTS_FILE, "w") as f:
            json.dump(contacts, f, indent=2)
    except Exception as e:
        print(f"[Contacts] Save error: {e}")


def _save(contacts: dict):
    _save_raw(contacts)


# ── Email normalizer (handles Google SR spoken email) ─────────────
def _clean_email(raw: str) -> str:
    """
    Convert spoken email dictation to a proper email address.
      "shivank p&d at the rate gmail dot com"  → "shivankpndy@gmail.com"
      "john dot smith at gmail dot com"         → "john.smith@gmail.com"
      "info at rate yahoo dot co dot in"        → "info@yahoo.co.in"
    """
    t = raw.strip().lower()

    # "at the rate" / "at rate" → @
    t = re.sub(r'\bat\s+the\s+rate\s+of\b', '@', t)
    t = re.sub(r'\bat\s+the\s+rate\b',      '@', t)
    t = re.sub(r'\bat\s+rate\b',            '@', t)
    # "word at word" → @  (plain "at" between non-space tokens)
    t = re.sub(r'(?<=\w)\s+at\s+(?=\w)',    '@', t)

    # "dot" → .
    t = re.sub(r'\s*\bdot\b\s*', '.', t)

    # Google SR often collapses letters: "p&d" → "pndy", stray "&" → "n"
    t = t.replace('p&d', 'pndy')
    t = t.replace(' & ', 'n')
    t = t.replace('&',   'n')

    # Collapse spaces inside the address
    if '@' in t:
        m = re.search(r'([\w.\-]+)\s*@\s*([\w.\-\s]+)', t)
        if m:
            local  = re.sub(r'\s+', '', m.group(1))
            domain = re.sub(r'\s+', '', m.group(2))
            t = t[:m.start()] + f"{local}@{domain}" + t[m.end():]

    # Legacy simple replacements as final safety net
    t = t.replace(' at ', '@').replace(' dot ', '.').replace(' ', '')
    return t.strip()


# ── Public API ────────────────────────────────────────────────────

def get_all() -> dict:
    with _lock:
        return _load()


def find(name: str) -> str | None:
    """
    Look up a contact by name. Returns email or None.
    Case-insensitive, partial match supported.
    """
    contacts = _load()
    name_lower = name.lower().strip()

    # Exact match
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
        key = name.lower().strip()
        contacts[key] = {
            "name":  name.strip(),
            "email": email.strip().lower(),
            "phone": phone.strip(),
        }
        _save(contacts)
    print(f"[Contacts] Saved: {name} → {email}  phone={phone or 'none'}")
    return True


def remove(name: str) -> bool:
    with _lock:
        contacts = _load()
        key = name.lower().strip()
        if key in contacts:
            del contacts[key]
            _save(contacts)
            return True
        # Partial match fallback
        for k in list(contacts.keys()):
            if name.lower() in k:
                del contacts[k]
                _save(contacts)
                return True
    return False


def list_contacts() -> list:
    """Return list of contact dicts."""
    contacts = _load()
    return [
        {
            "name":  v["name"],
            "email": v["email"],
            "phone": v.get("phone", ""),
        }
        for v in contacts.values()
    ]


# ── Resolve helpers (used by email_sender etc.) ───────────────────

def resolve_by_name(name: str) -> str:
    """Return email for a contact name, or '' if not found."""
    email = find(name)
    return email or ""


def add_contact(name: str, email: str, phone: str = "") -> bool:
    """Alias for add() — used by email_sender."""
    return add(name, email, phone)


def resolve_or_ask(name_or_email: str) -> str | None:
    """
    Resolve name → email.
    If it's already an email, offer to save it.
    If not found, ask user if they want to add it.
    """
    if "@" in name_or_email:
        threading.Thread(
            target=_offer_to_save_email,
            args=(name_or_email,),
            daemon=True,
        ).start()
        return name_or_email

    email = find(name_or_email)
    if email:
        return email

    _speak(
        f"I don't have {name_or_email} in your contacts Shivank. "
        f"Should I add them?"
    )
    response = _listen(timeout=10)
    if not response:
        return None

    if any(w in response.lower() for w in ["yes", "yeah", "sure", "add", "save"]):
        email_raw = _ask(f"What is {name_or_email}'s email address?", timeout=15)
        if not email_raw:
            _speak("Nothing provided. Skipping.")
            return None

        email_clean = _clean_email(email_raw)
        if "@" not in email_clean:
            _speak("That doesn't look like a valid email. Skipping.")
            return None

        phone_raw = _ask(
            f"Got it — {email_clean}. Phone number for {name_or_email}? Say skip to skip.",
            timeout=10
        )
        phone = ""
        if phone_raw and not any(w in phone_raw.lower() for w in ["skip", "no"]):
            phone = re.sub(r'[^0-9+]', '', phone_raw)

        add(name_or_email, email_clean, phone)
        _speak(f"{name_or_email} saved to your contacts Shivank.")
        return email_clean

    _speak("Okay, skipping.")
    return None


def _offer_to_save_email(email: str):
    """If user provided a raw email, offer to save it with a name."""
    import time
    time.sleep(2)
    contacts = _load()
    for v in contacts.values():
        if v["email"].lower() == email.lower():
            return   # already saved
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


# ── Voice command handler ─────────────────────────────────────────

def handle(user_text: str) -> str:
    t = user_text.lower()

    if any(k in t for k in ["show contacts", "list contacts",
                              "my contacts", "who are my contacts"]):
        contacts = list_contacts()
        if not contacts:
            return "You have no saved contacts yet Shivank."
        names = ", ".join([c["name"] for c in contacts[:5]])
        total = len(contacts)
        suffix = " and more." if total > 5 else "."
        return (f"You have {total} contact{'s' if total != 1 else ''} Shivank. "
                f"Including {names}{suffix}")

    if any(k in t for k in ["add contact", "save contact", "new contact"]):
        threading.Thread(target=_add_contact_flow, daemon=True).start()
        return ""

    if any(k in t for k in ["delete contact", "remove contact"]):
        threading.Thread(
            target=_remove_contact_flow, args=(user_text,), daemon=True
        ).start()
        return ""

    return ""


def _add_contact_flow():
    """Full guided add-contact voice flow."""
    # Step 1 — Name
    name = _ask("What's the name of the contact?", timeout=10)
    if not name:
        _speak("Didn't catch a name. Cancelled.")
        return

    # Step 2 — Email
    email_raw = _ask(f"What's {name}'s email address?", timeout=15)
    if not email_raw:
        _speak("Didn't catch an email. Cancelled.")
        return

    email = _clean_email(email_raw)
    if "@" not in email:
        _speak(f"Sorry, that doesn't look like a valid email address.")
        return

    # Step 3 — Phone (optional)
    phone_raw = _ask(
        f"Got it — {email}. Phone number for {name}? Say skip to skip.",
        timeout=10
    )
    phone = ""
    if phone_raw and not any(w in phone_raw.lower() for w in ["skip", "no"]):
        phone = re.sub(r'[^0-9+]', '', phone_raw)

    add(name, email, phone)
    _speak(f"{name} has been added to your contacts Shivank.")


def _remove_contact_flow(user_text: str):
    match = re.search(
        r'(?:delete|remove)\s+contact\s+(.+)', user_text, re.IGNORECASE
    )
    name = match.group(1).strip() if match else None

    if not name:
        name = _ask("Which contact should I remove?", timeout=8)
    if not name:
        return

    ok = remove(name)
    if ok:
        _speak(f"{name} has been removed from your contacts Shivank.")
    else:
        _speak(f"I couldn't find {name} in your contacts.")