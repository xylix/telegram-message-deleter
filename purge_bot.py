"""Telegram bot that purges all messages from a channel via /purge command.

Usage:
  1. Get api_id and api_hash from https://my.telegram.org
  2. Create a bot via @BotFather, grab the token
  3. Add the bot as an admin to your channel (needs Delete Messages permission)
     — the bot will print the chat ID to the console and reply with it
  4. Set API_ID, API_HASH, BOT_TOKEN, and CHANNEL_ID below (or as env vars)
  5. pip install telethon
  6. Run this script, then send /purge to the bot
"""

import os
from telethon import TelegramClient, events
from telethon.tl.types import ChatMemberStatusAdministrator

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))  # e.g. -1001234567890

bot = TelegramClient("purge_bot", API_ID, API_HASH).start(bot_token=BOT_TOKEN)


@bot.on(events.ChatAction)
async def on_added(event):
    if event.user_added or event.user_joined:
        me = await bot.get_me()
        if event.user_id == me.id:
            chat = await event.get_chat()
            title = getattr(chat, "title", "DM")
            print(f"Added to: {title} | Chat ID: {event.chat_id}")
            await event.respond(f"Chat ID: {event.chat_id}")


@bot.on(events.NewMessage(pattern="/purge"))
async def purge(event):
    deleted = 0
    async for msg in bot.iter_messages(CHANNEL_ID):
        await msg.delete()
        deleted += 1
        if deleted % 100 == 0:
            print(f"  deleted {deleted} messages...")

    await event.respond(f"Done. Deleted {deleted} messages from the target channel.")


print("Bot running. Send /purge to trigger.")
bot.run_until_disconnected()
