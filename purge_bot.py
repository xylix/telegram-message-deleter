"""Telegram bot that purges messages by ID from a JSON file via /purge command.

Usage:
  1. First run dump_ids.py to generate a message_ids_<chat_id>.json file
  2. Set API_ID, API_HASH, and BOT_TOKEN below (or as env vars)
  3. Add the bot as admin to the chat (needs Delete Messages permission)
  4. pip install telethon
  5. Run this script, then send /purge to the bot (auto-finds the JSON file)
"""

import os
import json
import asyncio
from telethon import TelegramClient, events

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

bot = TelegramClient("purge_bot", API_ID, API_HASH)


@bot.on(events.ChatAction)
async def on_added(event):
    if event.user_added or event.user_joined:
        me = await bot.get_me()
        if event.user_id == me.id:
            chat = await event.get_chat()
            title = getattr(chat, "title", "DM")
            print(f"Added to: {title} | Chat ID: {event.chat_id}")
            await event.respond(f"Chat ID: {event.chat_id}")


@bot.on(events.NewMessage(pattern=r"/purge\s*(.*)"))
async def purge(event):
    arg = event.pattern_match.group(1).strip()
    if not arg:
        await event.respond("Usage: /purge <filename.json>")
        return

    try:
        with open(arg) as f:
            data = json.load(f)
    except FileNotFoundError:
        await event.respond(f"File not found: {arg}")
        return

    chat_id = data["chat_id"]
    ids = data["message_ids"]

    await event.respond(f"Deleting {len(ids)} messages from chat {chat_id}...")

    deleted = 0
    failed = 0
    for mid in ids:
        try:
            await bot.delete_messages(chat_id, mid)
            deleted += 1
        except Exception:
            failed += 1
        if (deleted + failed) % 30 == 0:
            await asyncio.sleep(1)
        if deleted % 100 == 0 and deleted > 0:
            print(f"  deleted {deleted}/{len(ids)}...")

    await event.respond(f"Done. Deleted {deleted}, failed {failed}.")


async def main():
    await bot.start(bot_token=BOT_TOKEN)
    print("Bot running. Send /purge to trigger.")
    await bot.run_until_disconnected()


asyncio.run(main())
