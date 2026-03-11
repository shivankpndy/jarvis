import json
import os
import datetime
import ollama

MEMORY_FILE = r"D:\JARVIS\memory\jarvis_memory.json"
LOG_FILE    = r"D:\JARVIS\memory\conversation_log.json"
OLLAMA_MODEL = "llama3.2:3b"

os.makedirs(r"D:\JARVIS\memory", exist_ok=True)


def _load(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _save(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Memory save error: {e}")


# ── Core memory store ──────────────────────────────────────────────
def load_memory() -> dict:
    return _load(MEMORY_FILE, {
        "facts":    {},       # key facts about sir: name, preferences etc
        "summaries": [],      # daily conversation summaries
        "last_seen": None,
    })


def save_memory(memory: dict):
    _save(MEMORY_FILE, memory)


# ── Conversation log ───────────────────────────────────────────────
def load_log() -> list:
    return _load(LOG_FILE, [])


def save_log(log: list):
    _save(LOG_FILE, log)


def log_exchange(user_text: str, jarvis_reply: str):
    """Save every conversation turn to log."""
    log = load_log()
    log.append({
        "time":  datetime.datetime.now().isoformat(),
        "user":  user_text,
        "jarvis": jarvis_reply
    })
    # Keep last 200 turns only
    if len(log) > 200:
        log = log[-200:]
    save_log(log)


# ── Extract facts from conversation ───────────────────────────────
def extract_facts(user_text: str, memory: dict):
    """Use Ollama to extract any facts worth remembering."""
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content":
                f"""Extract any personal facts worth remembering from this message.
Return ONLY a JSON object like {{"key": "value"}} or {{}} if nothing important.
Examples: {{"name": "Shivank"}}, {{"prefers": "short answers"}}, {{"project": "JARVIS hackathon"}}
Message: "{user_text}"
JSON only, no other text:"""}]
        )
        text = response["message"]["content"].strip()
        # Clean JSON
        if "{" in text and "}" in text:
            text = text[text.index("{"):text.rindex("}")+1]
            facts = json.loads(text)
            if facts:
                memory["facts"].update(facts)
                print(f"Memory: learned {facts}")
    except Exception:
        pass


# ── Summarize yesterday's conversation ────────────────────────────
def summarize_recent(memory: dict):
    """Summarize last session's conversation and store it."""
    log = load_log()
    if not log:
        return

    # Get last 20 turns
    recent = log[-20:]
    conv_text = "\n".join([
        f"Sir: {turn['user']}\nJARVIS: {turn['jarvis']}"
        for turn in recent
    ])

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content":
                f"""Summarize this JARVIS conversation in 2-3 sentences.
Focus on what was discussed, decisions made, tasks completed.
Be concise.

{conv_text}

Summary:"""}]
        )
        summary = response["message"]["content"].strip()
        memory["summaries"].append({
            "date": datetime.date.today().isoformat(),
            "summary": summary
        })
        # Keep last 30 daily summaries
        if len(memory["summaries"]) > 30:
            memory["summaries"] = memory["summaries"][-30:]
        print(f"Memory: session summarized")
    except Exception as e:
        print(f"Memory summarize error: {e}")


# ── Build context string for JARVIS ───────────────────────────────
def build_memory_context(memory: dict) -> str:
    """Build a context string to inject into JARVIS persona."""
    lines = []

    # Facts about sir
    if memory["facts"]:
        facts_str = ", ".join([f"{k}: {v}" for k, v in memory["facts"].items()])
        lines.append(f"Known facts about sir: {facts_str}")

    # Last seen
    if memory["last_seen"]:
        lines.append(f"Last conversation: {memory['last_seen']}")

    # Recent summaries
    if memory["summaries"]:
        recent = memory["summaries"][-3:]  # last 3 days
        for s in recent:
            lines.append(f"Previous session ({s['date']}): {s['summary']}")

    if not lines:
        return ""

    return "MEMORY CONTEXT:\n" + "\n".join(lines)


# ── Session start / end ────────────────────────────────────────────
def on_session_start() -> str:
    """Call when JARVIS starts. Returns greeting context."""
    memory = load_memory()

    # Summarize previous session if there's a log
    log = load_log()
    if log:
        last_entry = log[-1]
        last_time  = datetime.datetime.fromisoformat(last_entry["time"])
        now        = datetime.datetime.now()
        hours_ago  = (now - last_time).total_seconds() / 3600

        # If last session was more than 1 hour ago, summarize it
        if hours_ago > 1:
            summarize_recent(memory)

    memory["last_seen"] = datetime.datetime.now().strftime("%B %d at %I:%M %p")
    save_memory(memory)

    context = build_memory_context(memory)
    return context


def on_session_end():
    """Call when JARVIS goes to standby."""
    memory = load_memory()
    summarize_recent(memory)
    save_memory(memory)
    print("Memory: session saved")


def remember(user_text: str, jarvis_reply: str):
    """Call after every exchange — logs and extracts facts."""
    log_exchange(user_text, jarvis_reply)
    memory = load_memory()
    extract_facts(user_text, memory)
    save_memory(memory)


def get_memory_summary() -> str:
    """Get a quick summary of what JARVIS knows."""
    memory = load_memory()
    lines  = [f"Facts: {memory['facts']}",
              f"Sessions remembered: {len(memory['summaries'])}",
              f"Last seen: {memory['last_seen']}"]
    return "\n".join(lines)