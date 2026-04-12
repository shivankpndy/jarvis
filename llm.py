"""
JARVIS LLM Wrapper
==================
Single place to switch between Ollama (local) and Cohere API.

Set in .env:
    LLM_PROVIDER=cohere          # or: ollama
    COHERE_API_KEY=your_key_here

Cohere free tier: 1000 calls/day, no credit card needed.
Sign up at: https://dashboard.cohere.com

Usage in any JARVIS file:
    from llm import chat, chat_raw

    reply = chat("What is the capital of France?")
    reply = chat([{"role":"user","content":"hello"}])  # full history
"""

import os
from dotenv import load_dotenv
load_dotenv(r"D:\JARVIS\.env")

# ── Config ────────────────────────────────────────────────────────────────────
PROVIDER     = os.getenv("LLM_PROVIDER", "cohere").lower()   # "cohere" or "ollama"
COHERE_KEY   = os.getenv("COHERE_API_KEY", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL",  "llama3.2:3b")
COHERE_MODEL = os.getenv("COHERE_MODEL",  "command-r")

print(f"[LLM] Provider: Ollama 3.2  |")


# ── Cohere client (lazy init) ─────────────────────────────────────────────────
_cohere_client = None

def _get_cohere():
    global _cohere_client
    if _cohere_client is None:
        import cohere
        _cohere_client = cohere.Client(COHERE_KEY)
    return _cohere_client


# ── Core chat function ────────────────────────────────────────────────────────
def chat(messages, system: str = "", temperature: float = 0.7) -> str:
    """
    Send messages to configured LLM, return response string.

    Args:
        messages:    Either a string prompt, or a list of
                     {"role": "user"/"assistant"/"system", "content": "..."}
        system:      Optional system prompt override
        temperature: 0.0–1.0

    Returns:
        str: The model's response text
    """
    # Normalise to list format
    if isinstance(messages, str):
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": messages})
    else:
        msgs = list(messages)

    if PROVIDER == "cohere":
        return _cohere_chat(msgs, temperature)
    else:
        return _ollama_chat(msgs)


def chat_raw(prompt: str, system: str = "", temperature: float = 0.7) -> str:
    """Convenience: send a single string prompt, get string back."""
    return chat(prompt, system=system, temperature=temperature)


# ── Cohere backend ────────────────────────────────────────────────────────────
def _cohere_chat(msgs: list, temperature: float) -> str:
    try:
        co = _get_cohere()

        system_prompt = ""
        chat_history  = []
        user_msg      = ""

        for m in msgs:
            role    = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_prompt = content
            elif role == "assistant":
                chat_history.append({"role": "CHATBOT", "message": content})
            elif role == "user":
                if user_msg:
                    chat_history.append({"role": "USER", "message": user_msg})
                user_msg = content

        if not user_msg:
            return ""

        kwargs = {
            "model":       COHERE_MODEL,
            "message":     user_msg,
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["preamble"] = system_prompt
        if chat_history:
            kwargs["chat_history"] = chat_history

        resp = co.chat(**kwargs)
        return resp.text.strip()

    except Exception as e:
        print(f"[LLM] Cohere error: {e} — falling back to Ollama")
        return _ollama_chat(msgs)


# ── Ollama backend ────────────────────────────────────────────────────────────
def _ollama_chat(msgs: list) -> str:
    try:
        import ollama
        response = ollama.chat(model=OLLAMA_MODEL, messages=msgs)
        return response["message"]["content"].strip()
    except Exception as e:
        print(f"[LLM] Ollama error: {e}")
        return "I'm having trouble thinking right now sir. Please try again."
