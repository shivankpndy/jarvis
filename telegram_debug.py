import os
import sys
sys.path.insert(0, r"D:\JARVIS")

from dotenv import load_dotenv
load_dotenv(r"D:\JARVIS\.env")

from telethon import TelegramClient, events
import asyncio

API_ID   = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION  = r"D:\JARVIS\jarvis_telegram"

client = TelegramClient(SESSION, API_ID, API_HASH)


@client.on(events.NewMessage)
async def handle_message(event):
    msg = event.message
    print(f"\n[NewMessage] From: {event.sender_id} | Text: {msg.message} | Action: {type(msg.action).__name__}")


@client.on(events.Raw)
async def handle_raw(update):
    """Catch ALL raw updates from Telegram — including calls."""
    update_type = type(update).__name__
    # Only print call-related or unknown updates, skip noise
    if any(x in update_type.lower() for x in ['call', 'phone', 'action']):
        print(f"\n[RAW - CALL RELATED] {update_type}: {update}")
    else:
        print(f"[RAW] {update_type}")


async def main():
    print("Telegram DEBUG mode - catching ALL events including calls...")
    await client.start()
    me = await client.get_me()
    print(f"Logged in as: {me.first_name}")
    print("Have someone Telegram call you now and don't pick up.\n")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())