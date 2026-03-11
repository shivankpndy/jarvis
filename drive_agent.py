"""
JARVIS Google Drive Agent
Uses rclone CLI — handles OAuth silently after one-time setup.

One-time setup (do this once):
  1. Open PowerShell and run:  winget install Rclone.Rclone
  2. Then run:                  rclone config
     - Type: n  (new remote)
     - Name: jarvis_drive
     - Storage type: drive
     - Client ID: leave blank → Enter
     - Client Secret: leave blank → Enter
     - Scope: 1  (full access)
     - Browser opens → sign in with your Google account → Allow
     - Done. rclone saves token permanently.
"""
import os
import re
import subprocess
import threading
import time
import schedule

RCLONE_REMOTE = "jarvis_drive"         # name you gave during rclone config
DRIVE_FOLDER  = "JARVIS"               # root folder created in your Drive
SNAPSHOTS_DIR = r"D:\JARVIS\snapshots"
MEMORY_DIR    = r"D:\JARVIS\memory"
DOWNLOAD_DIR  = r"D:\JARVIS\downloads"

_speak_fn  = None
_listen_fn = None
_notify_fn = None


def set_speak(fn):  global _speak_fn;  _speak_fn  = fn
def set_listen(fn): global _listen_fn; _listen_fn = fn
def set_notify(fn): global _notify_fn; _notify_fn = fn


def _speak(text):
    if _speak_fn: _speak_fn(text)
    else: print(f"[Drive] {text}")


def _listen(timeout=12) -> str:
    if _listen_fn: return _listen_fn(timeout=timeout) or ""
    return ""


# ── rclone wrapper ───────────────────────────────────────────────────────────────
def _rclone(args: list, timeout: int = 60) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["rclone"] + args,
            capture_output=True, text=True, timeout=timeout
        )
        ok  = result.returncode == 0
        out = (result.stdout + result.stderr).strip()
        return ok, out
    except subprocess.TimeoutExpired:
        return False, "Timed out"
    except FileNotFoundError:
        return False, "rclone not installed. Run: winget install Rclone.Rclone"
    except Exception as e:
        return False, str(e)


def _remote(subfolder: str = "") -> str:
    base = f"{RCLONE_REMOTE}:{DRIVE_FOLDER}"
    return f"{base}/{subfolder}" if subfolder else base


def _rclone_available() -> bool:
    ok, _ = _rclone(["version"], timeout=5)
    return ok


# ── Core Drive operations ────────────────────────────────────────────────────────
def upload_file(local_path: str, subfolder: str = "") -> bool:
    if not os.path.exists(local_path):
        print(f"[Drive] File not found: {local_path}")
        return False
    ok, out = _rclone(["copy", local_path, _remote(subfolder), "--progress"])
    if ok:
        print(f"[Drive] Uploaded: {os.path.basename(local_path)}")
    else:
        print(f"[Drive] Upload failed: {out}")
    return ok


def list_files(subfolder: str = "") -> list[str]:
    ok, out = _rclone(["ls", _remote(subfolder)])
    if not ok or not out.strip():
        return []
    files = []
    for line in out.strip().split("\n"):
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            files.append(parts[1])
    return files


def search_files(query: str) -> list[str]:
    all_files = list_files()
    q = query.lower()
    return [f for f in all_files if q in f.lower()]


def download_file(filename: str) -> bool:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    remote = f"{RCLONE_REMOTE}:{DRIVE_FOLDER}/{filename}"
    ok, out = _rclone(["copy", remote, DOWNLOAD_DIR])
    if ok:
        print(f"[Drive] Downloaded: {filename} → {DOWNLOAD_DIR}")
    else:
        print(f"[Drive] Download failed: {out}")
    return ok


def backup_memory() -> bool:
    ok, _ = _rclone(["copy", MEMORY_DIR, _remote("memory")])
    if ok:
        print("[Drive] Memory backed up to Drive")
        if _notify_fn:
            _notify_fn("JARVIS memory backup complete Shivank.")
    return ok


def backup_snapshots() -> bool:
    ok, _ = _rclone(["copy", SNAPSHOTS_DIR, _remote("snapshots")])
    if ok:
        print("[Drive] Snapshots backed up to Drive")
    return ok


# ── Voice handler ────────────────────────────────────────────────────────────────
def handle(user_text: str) -> str:
    t = user_text.lower()

    # Upload a file
    if any(k in t for k in ["upload", "save to drive", "backup to drive",
                             "put on drive", "send to drive"]):
        threading.Thread(target=_upload_flow, args=(user_text,), daemon=True).start()
        return ""

    # List files
    if any(k in t for k in ["list drive", "show drive", "what's on drive",
                             "drive files", "what do i have on drive"]):
        files = list_files()
        if not files:
            return "Your JARVIS Drive folder is empty Shivank."
        total   = len(files)
        preview = ", ".join(files[:4])
        suffix  = " and more." if total > 4 else "."
        return f"You have {total} file{'s' if total != 1 else ''} on Drive Shivank. Including {preview}{suffix}"

    # Search files
    if any(k in t for k in ["find on drive", "search drive",
                             "look for on drive", "find file on drive"]):
        m = re.search(r'(?:find|search|look for)\s+(?:on\s+drive\s+)?(.+)', t)
        if m:
            q       = m.group(1).strip()
            matches = search_files(q)
            if matches:
                return (
                    f"Found {len(matches)} file{'s' if len(matches) != 1 else ''} "
                    f"matching '{q}' Shivank: {', '.join(matches[:3])}."
                )
            return f"No files matching '{q}' on Drive Shivank."
        return "What should I search for on Drive Shivank?"

    # Download
    if any(k in t for k in ["download from drive", "get from drive",
                             "fetch from drive", "download file"]):
        threading.Thread(target=_download_flow, daemon=True).start()
        return ""

    # Backup memory
    if any(k in t for k in ["backup memory", "save memory to drive", "backup jarvis"]):
        ok = backup_memory()
        return ("Memory backed up to Drive Shivank."
                if ok else "Backup failed. Check your rclone setup Shivank.")

    # Backup snapshots
    if any(k in t for k in ["backup snapshots", "upload snapshots", "save snapshots"]):
        ok = backup_snapshots()
        return ("Snapshots uploaded to Drive Shivank."
                if ok else "Upload failed. Check your rclone setup Shivank.")

    return ""


def _upload_flow(user_text: str):
    """Conversational upload flow."""
    # Try to extract path hint from the command
    m = re.search(
        r'(?:upload|save|put|send)\s+(?:the\s+)?(.+?)(?:\s+to\s+(?:drive|google\s+drive))?$',
        user_text, re.IGNORECASE
    )
    hint = m.group(1).strip() if m else None

    if hint and os.path.exists(hint):
        local_path = hint
    else:
        _speak("What's the full file path you want to upload Shivank?")
        raw = _listen()
        if not raw:
            _speak("Upload cancelled.")
            return
        local_path = raw.strip().strip('"').strip("'")

    # Try common locations if it's just a filename
    if not os.path.exists(local_path):
        for base in [
            r"D:\JARVIS",
            os.path.expanduser("~\\Desktop"),
            os.path.expanduser("~\\Documents"),
            os.path.expanduser("~\\Downloads"),
        ]:
            candidate = os.path.join(base, local_path)
            if os.path.exists(candidate):
                local_path = candidate
                break
        else:
            _speak(
                f"I couldn't find that file Shivank. "
                f"Please give me the full path like D colon backslash folder backslash filename."
            )
            return

    filename = os.path.basename(local_path)
    _speak(f"Uploading {filename} to Google Drive.")
    ok = upload_file(local_path)
    if ok:
        _speak(f"{filename} has been uploaded to Drive Shivank.")
    else:
        _speak(
            "Upload failed Shivank. Make sure rclone is installed and configured. "
            "Run rclone config if you haven't already."
        )


def _download_flow():
    """Conversational download flow."""
    _speak("What file should I download from Drive Shivank?")
    query = _listen()
    if not query:
        _speak("Download cancelled.")
        return

    matches = search_files(query.strip())
    if not matches:
        _speak(f"No files matching '{query}' found on Drive Shivank.")
        return

    if len(matches) == 1:
        filename = matches[0]
    else:
        names = ", ".join(matches[:3])
        _speak(f"I found {len(matches)} matches: {names}. Which one Shivank?")
        choice = _listen()
        if not choice:
            _speak("Download cancelled.")
            return
        # Find closest match
        filename = matches[0]
        for mf in matches:
            if choice.lower() in mf.lower():
                filename = mf
                break

    _speak(f"Downloading {filename}.")
    ok = download_file(filename)
    if ok:
        _speak(
            f"Done. {filename} has been saved to "
            f"D backslash JARVIS backslash downloads Shivank."
        )
    else:
        _speak("Download failed Shivank.")


# ── Auto backup scheduler ────────────────────────────────────────────────────────
def start_auto_backup():
    if not _rclone_available():
        print("[Drive] rclone not found — skipping auto backup")
        print("[Drive] To install: winget install Rclone.Rclone")
        print("[Drive] To configure: rclone config")
        return

    schedule.every().day.at("00:00").do(backup_memory)
    schedule.every().day.at("00:05").do(backup_snapshots)

    def _run():
        print("[Drive] Auto-backup scheduled — memory at 00:00, snapshots at 00:05")
        while True:
            schedule.run_pending()
            time.sleep(60)

    threading.Thread(target=_run, daemon=True).start()