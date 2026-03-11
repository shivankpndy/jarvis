import os
import sys
sys.path.insert(0, r"D:\JARVIS")

from dotenv import load_dotenv
load_dotenv(r"D:\JARVIS\.env")

from telethon import TelegramClient, events
from telethon.tl.types import (
    UpdatePhoneCall,
    PhoneCallDiscarded,
    PhoneCallDiscardReasonMissed,
    DocumentAttributeAudio
)
from datetime import datetime
import ollama
import asyncio
import subprocess
import tempfile
import threading

API_ID   = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION  = r"D:\JARVIS\jarvis_telegram"

OLLAMA_MODEL = "llama3.2:3b"
PIPER_EXE    = r"D:\JARVIS\piper_extracted\piper\piper.exe"
VOICE_MODEL  = r"D:\JARVIS\voices\en_GB-alan-medium.onnx"

client        = TelegramClient(SESSION, API_ID, API_HASH)
pending_calls = {}

# Track active JARVIS conversations with callers
# user_id -> {"name": str, "messages": [...], "state": "waiting_for_message"}
active_conversations = {}


def speak_notification(text):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        tmp_wav = f.name
    try:
        subprocess.run(
            [PIPER_EXE, "--model", VOICE_MODEL, "--output_file", tmp_wav],
            input=text.encode(), capture_output=True)
        subprocess.run(
            ["powershell", "-c", f'(New-Object Media.SoundPlayer "{tmp_wav}").PlaySync()'])
    finally:
        if os.path.exists(tmp_wav):
            try: os.unlink(tmp_wav)
            except: pass


def notify_sir(text):
    """Post notification to JARVIS main loop or speak directly."""
    try:
        import jarvis
        jarvis.post_notification(text)
    except Exception:
        threading.Thread(target=speak_notification, args=(text,), daemon=True).start()


async def get_caller_name(user_id):
    try:
        entity = await client.get_entity(user_id)
        name   = getattr(entity, 'first_name', 'Unknown')
        if getattr(entity, 'last_name', None):
            name += f" {entity.last_name}"
        return name
    except Exception:
        return f"User {user_id}"


async def summarize_missed_call(caller_name, call_time):
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content":
            f"You are JARVIS. Write ONE short sentence notifying sir of a missed Telegram call from {caller_name} at {call_time}. One sentence only."}]
    )
    return response["message"]["content"].strip()


async def generate_jarvis_reply(caller_name, user_message, conversation_history):
    """Generate JARVIS reply to the caller on behalf of Shivank."""
    history = conversation_history + [
        {"role": "user", "content": user_message}
    ]
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": f"""You are JARVIS, AI assistant of Shivank Pandey.
You are having a Telegram conversation with {caller_name} on Shivank's behalf.
Shivank is currently unavailable.
Your job is to:
1. Understand what {caller_name} needs
2. Collect their message/request
3. Tell them Shivank will get back to them
4. Be polite, brief, and professional
Do NOT pretend to be Shivank. You are his AI assistant."""},
            *history
        ]
    )
    return response["message"]["content"].strip()


async def summarize_conversation(caller_name, messages):
    """Summarize the conversation for Shivank."""
    conversation_text = "\n".join([f"{'Caller' if m['role']=='user' else 'JARVIS'}: {m['content']}" for m in messages])
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[{"role": "user", "content":
            f"""You are JARVIS. Summarize this conversation with {caller_name} for sir in 2 sentences.
Focus on what they need or want to communicate.

Conversation:
{conversation_text}

Summary for sir:"""}]
    )
    return response["message"]["content"].strip()


@client.on(events.Raw(UpdatePhoneCall))
async def handle_phone_call(update):
    call = update.phone_call

    if hasattr(call, 'admin_id'):
        pending_calls[call.id] = call.admin_id
        print(f"\nIncoming Telegram call from id={call.admin_id}")

    if isinstance(call, PhoneCallDiscarded):
        if isinstance(getattr(call, 'reason', None), PhoneCallDiscardReasonMissed):
            caller_id   = pending_calls.pop(call.id, None)
            call_time   = datetime.now().strftime("%I:%M %p")
            caller_name = await get_caller_name(caller_id) if caller_id else "Unknown"
            print(f"Missed call from: {caller_name} at {call_time}")

            # Brief sir
            brief = await summarize_missed_call(caller_name, call_time)
            notify_sir(brief)

            # Send brief to saved messages
            me = await client.get_me()
            await client.send_message(me.id, f"🤖 JARVIS: {brief}")

            # Send automated reply to caller
            if caller_id:
                auto_reply = (
                    f"Hello {caller_name}! 👋\n\n"
                    f"I'm JARVIS, Shivank's AI assistant. He's currently unavailable and missed your call.\n\n"
                    f"Please tell me what you need or what message you'd like me to pass on to him, "
                    f"and I'll make sure he gets it right away! 🤖"
                )
                await client.send_message(caller_id, auto_reply)

                # Start tracking conversation
                active_conversations[caller_id] = {
                    "name":     caller_name,
                    "messages": [],
                    "state":    "waiting_for_message"
                }
                print(f"Automated reply sent to {caller_name}. Waiting for their response.")


@client.on(events.NewMessage(incoming=True))
async def handle_incoming_message(event):
    """Handle replies from callers in active JARVIS conversations."""
    try:
        sender_id = event.sender_id
        me        = await client.get_me()

        # Ignore messages from yourself
        if sender_id == me.id:
            return

        # Only handle if we have an active conversation with this person
        if sender_id not in active_conversations:
            return

        conv        = active_conversations[sender_id]
        caller_name = conv["name"]
        user_message = event.message.message

        if not user_message:
            return

        print(f"Message from {caller_name}: {user_message}")

        # Add to conversation history
        conv["messages"].append({"role": "user", "content": user_message})

        # Generate JARVIS reply
        reply = await generate_jarvis_reply(caller_name, user_message, conv["messages"][:-1])
        conv["messages"].append({"role": "assistant", "content": reply})

        # Reply to caller
        await client.send_message(sender_id, reply)
        print(f"JARVIS replied to {caller_name}: {reply}")

        # After first message received — summarize and brief sir
        if len(conv["messages"]) >= 2:
            summary = await summarize_conversation(caller_name, conv["messages"])
            brief   = f"Sir, {caller_name} replied on Telegram. {summary}"
            notify_sir(brief)

            # Send full conversation summary to saved messages
            me = await client.get_me()
            conv_text = "\n".join([
                f"{'📨 ' + caller_name if m['role']=='user' else '🤖 JARVIS'}: {m['content']}"
                for m in conv["messages"]
            ])
            await client.send_message(
                me.id,
                f"💬 Conversation with {caller_name}:\n\n{conv_text}\n\n📝 Summary: {summary}"
            )

    except Exception as e:
        print(f"Message handler error: {e}")


async def main():
    print("JARVIS Telegram watcher starting...")
    await client.start()
    me = await client.get_me()
    print(f"Logged in as: {me.first_name}")
    print("Watching for missed calls and messages...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())