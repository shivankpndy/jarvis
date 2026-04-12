"""
JARVIS Coding Agent
Uses qwen2.5-coder:3b (via Ollama) or falls back to main LLM.
Saves generated code to D:\JARVIS\workspace\
"""
import os, re, datetime
from llm import chat_raw

WORKSPACE = r"D:\JARVIS\workspace"

_speak_fn = None
def set_speak(fn): global _speak_fn; _speak_fn = fn
def _speak(text):
    if _speak_fn: _speak_fn(text)
    else: print(f"[Coding] {text}")


def _coding_llm(prompt: str) -> str:
    """Try qwen2.5-coder first, fall back to main LLM."""
    try:
        import ollama
        resp = ollama.chat(
            model="qwen2.5-coder:3b",
            messages=[{"role": "user", "content": prompt}]
        )
        return resp["message"]["content"].strip()
    except Exception as e:
        print(f"[Coding] qwen fallback to main LLM: {e}")
        return chat_raw(prompt)


def _extract_code(text: str) -> str:
    """Pull code out of markdown fences if present."""
    m = re.search(r'```(?:\w+)?\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def _save_to_workspace(code: str, filename: str = "") -> str:
    """Save code to workspace folder, return path."""
    try:
        os.makedirs(WORKSPACE, exist_ok=True)
        if not filename:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"jarvis_code_{ts}.py"
        path = os.path.join(WORKSPACE, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"[Coding] Saved to {path}")
        return path
    except Exception as e:
        print(f"[Coding] Save error: {e}")
        return ""


def run(user_text: str) -> str:
    """Main entry point — called by agent_router as coding_agent.run()"""
    print(f"[Coding] Request: '{user_text}'")

    prompt = (
        f"You are an expert Python programmer. "
        f"Write clean, working code for the following request.\n"
        f"Include helpful comments. Use standard Python 3 only.\n"
        f"Return ONLY the code — no explanation before or after.\n\n"
        f"Request: {user_text}"
    )

    _speak("Writing the code now sir.")
    raw = _coding_llm(prompt)
    code = _extract_code(raw)

    if not code:
        return "I wasn't able to generate code for that sir. Please try rephrasing."

    # Save to workspace
    path = _save_to_workspace(code)

    # Build spoken summary — first line of code or function name
    first_line = code.split('\n')[0][:80]
    save_msg = f" Saved to workspace." if path else ""

    print(f"[Coding] Generated:\n{code[:300]}...")
    _speak(f"Done sir. Here is the code.{save_msg}")

    # Return full code for display in terminal/dashboard
    return f"```python\n{code}\n```\n\n📁 Saved to: {path}" if path else f"```python\n{code}\n```"


# Allow direct test: python coding_agent.py
if __name__ == "__main__":
    result = run("write a function to sort a list")
    print(result)