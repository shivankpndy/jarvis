"""
vscode_faker.py
───────────────
Simulates realistic VS Code activity: opens random files, types random
edits, undoes them, and saves — leaving every file completely unchanged.

Requirements:
    pip install pyautogui pygetwindow keyboard

Usage:
    1. Open VS Code and load a folder/workspace.
    2. Run this script: python vscode_faker.py
    3. Press Ctrl+Shift+Q at any time to stop cleanly.

Notes:
    • Works on Windows. For macOS change CMD_KEY to 'command'.
    • VS Code must be open with a folder/workspace so Ctrl+P finds files.
"""

import random
import time
import sys
import threading
import pyautogui
import pygetwindow as gw
import keyboard

# ─── Config ───────────────────────────────────────────────────────────────────

CMD_KEY      = "ctrl"           # "command" on macOS
STEP_DELAY   = (1.2, 2.8)       # seconds between actions
CYCLE_DELAY  = (10, 20)         # seconds between full file-cycles
TYPING_SPEED = (0.06, 0.12)     # seconds per character
STOP_HOTKEY  = "ctrl+shift+q"

# Pyautogui global pause between every call (keeps things stable)
pyautogui.PAUSE = 0.15
pyautogui.FAILSAFE = True       # move mouse to top-left corner to abort

FAKE_EDITS = [
    "// TODO: refactor this later",
    "console.log('debug');",
    "# placeholder",
    "/* review needed */",
    "var temp = null;",
    "print('check')",
    "// WIP",
    "let x = 0;",
    "// FIXME: clean up",
    "# stub implementation",
]

# ─── Stop flag ────────────────────────────────────────────────────────────────

_stop = threading.Event()
keyboard.add_hotkey(STOP_HOTKEY, lambda: (_stop.set(),
                                          print("\n[STOP] Hotkey triggered.")))

# ─── Utilities ────────────────────────────────────────────────────────────────

def wait(bounds=STEP_DELAY):
    """Sleep a random amount; honour stop flag."""
    end = time.time() + random.uniform(*bounds)
    while time.time() < end:
        if _stop.is_set():
            raise SystemExit
        time.sleep(0.1)


def hotkey(*keys):
    pyautogui.hotkey(*keys)
    time.sleep(0.25)


def focus_vscode():
    wins = [w for w in gw.getAllWindows() if "Visual Studio Code" in w.title]
    if not wins:
        print("[WARN] VS Code window not found.")
        return False
    win = wins[0]
    try:
        win.restore()
        time.sleep(0.3)
        win.activate()
    except Exception:
        pass
    time.sleep(0.7)
    return True


# ─── Actions ──────────────────────────────────────────────────────────────────

def open_random_file():
    hotkey(CMD_KEY, "p")
    time.sleep(0.6)

    letters = random.choices("abcdefghijklmnoprstwy", k=random.randint(1, 3))
    pyautogui.typewrite("".join(letters), interval=random.uniform(*TYPING_SPEED))
    time.sleep(0.9)

    for _ in range(random.randint(0, 4)):
        pyautogui.press("down")
        time.sleep(0.1)

    pyautogui.press("enter")
    time.sleep(1.3)
    print(f"  -> Opened file (searched: {''.join(letters)})")


def scroll_around():
    direction = random.choice(["up", "down"])
    steps = random.randint(3, 10)
    for _ in range(steps):
        pyautogui.scroll(3 if direction == "up" else -3)
        time.sleep(0.08)
    time.sleep(0.3)
    print(f"  -> Scrolled {direction} {steps}x")


def move_cursor():
    line = str(random.randint(1, 180))
    hotkey(CMD_KEY, "g")          # Go to Line
    time.sleep(0.4)
    pyautogui.typewrite(line, interval=0.08)
    pyautogui.press("enter")
    time.sleep(0.4)
    hotkey("end")
    print(f"  -> Jumped to line {line}")


def fake_edit_and_undo():
    """
    Insert a snippet on a new line, then undo everything in small batches
    with pauses so VS Code doesn't miss any undo steps.
    """
    snippet = random.choice(FAKE_EDITS)

    # Move to a random line
    line = str(random.randint(1, 150))
    hotkey(CMD_KEY, "g")
    time.sleep(0.4)
    pyautogui.typewrite(line, interval=0.08)
    pyautogui.press("enter")
    time.sleep(0.3)
    hotkey("end")
    time.sleep(0.2)

    # Insert newline then type the snippet
    pyautogui.press("enter")      # counts as 1 undo step
    time.sleep(0.2)
    for ch in snippet:
        pyautogui.typewrite(ch, interval=random.uniform(*TYPING_SPEED))

    print(f"  -> Typed: '{snippet}'")
    wait((0.6, 1.4))

    # Undo in batches of 5 with a short pause between batches
    total_undos = len(snippet) + 1
    print(f"  -> Undoing {total_undos} steps ", end="", flush=True)

    done = 0
    while done < total_undos:
        chunk = min(5, total_undos - done)
        for _ in range(chunk):
            hotkey(CMD_KEY, "z")
        done += chunk
        time.sleep(0.35)
        print(".", end="", flush=True)

    print(" done")
    time.sleep(0.4)

    # Save to confirm no net change
    hotkey(CMD_KEY, "s")
    time.sleep(0.5)
    print("  -> Saved (file unchanged)")


# ─── Main cycle ───────────────────────────────────────────────────────────────

def run_cycle():
    if not focus_vscode():
        return

    print("\n[CYCLE START]")

    wait()
    open_random_file()

    wait()
    scroll_around()

    if random.random() > 0.35:
        wait()
        move_cursor()

    wait()
    fake_edit_and_undo()

    if random.random() > 0.5:
        wait()
        scroll_around()

    print("[CYCLE END]")


def main():
    print("=" * 55)
    print("  VS Code Faker  |  Ctrl+Shift+Q to stop")
    print("=" * 55)
    print(f"  Cycle delay : {CYCLE_DELAY[0]}-{CYCLE_DELAY[1]}s")
    print(f"  Step  delay : {STEP_DELAY[0]}-{STEP_DELAY[1]}s")
    print("  Files are NEVER permanently changed.\n")
    print("  Starting in 3 seconds — switch to VS Code now...")
    time.sleep(3)

    while not _stop.is_set():
        try:
            run_cycle()
        except SystemExit:
            break
        except Exception as e:
            print(f"[ERROR] {e} — retrying next cycle")

        delay = random.uniform(*CYCLE_DELAY)
        print(f"\n  Next cycle in {delay:.0f}s...")
        try:
            wait((delay, delay))
        except SystemExit:
            break

    print("\n[DONE] Stopped cleanly.")
    sys.exit(0)


if __name__ == "__main__":
    main()