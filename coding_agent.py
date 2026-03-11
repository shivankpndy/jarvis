import os
import re
import ollama

CODER_MODEL = "qwen2.5-coder:3b"
WORKSPACE   = r"D:\JARVIS\workspace"

CODER_PERSONA = """You are an expert coding assistant embedded inside JARVIS.
When given a coding task:
1. Write clean, well commented code
2. Always wrap code in proper markdown code blocks like ```python
3. After the code, give a brief 1-2 sentence explanation
4. Address the user as sir
5. Be concise - no unnecessary filler text"""


def extract_code_blocks(text):
    pattern = r'```(?:python|js|javascript|bash|html|css|json)?\n(.*?)```'
    return re.findall(pattern, text, re.DOTALL)


def generate_filename(task, index, code):
    if "def " in code or "import " in code or "print(" in code: ext = ".py"
    elif "function " in code or "const " in code: ext = ".js"
    elif "<html" in code: ext = ".html"
    else: ext = ".py"
    words = re.sub(r'[^a-z0-9 ]', '', task.lower()).split()[:4]
    name  = "_".join(words) if words else "jarvis_code"
    suffix = f"_{index + 1}" if index > 0 else ""
    return f"{name}{suffix}{ext}"


def save_code(filename, code):
    os.makedirs(WORKSPACE, exist_ok=True)
    filepath = os.path.join(WORKSPACE, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code.strip())
    return filepath


def run(task: str) -> str:
    print(f"💻 Coding agent: {task[:60]}")
    try:
        response = ollama.chat(
            model=CODER_MODEL,
            messages=[
                {"role": "system", "content": CODER_PERSONA},
                {"role": "user",   "content": task}
            ]
        )
        reply = response["message"]["content"].strip()
        code_blocks = extract_code_blocks(reply)
        saved_files = []
        for i, code in enumerate(code_blocks):
            filename = generate_filename(task, i, code)
            filepath = save_code(filename, code)
            saved_files.append(filepath)
            print(f"💾 Saved: {filepath}")
        if saved_files:
            paths = "\n".join(saved_files)
            reply += f"\n\nCode saved to:\n{paths}"
        return reply
    except Exception as e:
        return f"Coding agent encountered an error sir: {str(e)}"
