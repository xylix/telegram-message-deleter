"""Telegram bot that purges all messages from a channel via /purge command.

Usage:
  1. Create a bot via @BotFather, grab the token
  2. Set BOT_TOKEN below (or as env var)
  3. pip install python-telegram-bot
  4. Run this script
  5. Add the bot as admin to a channel (needs Delete Messages permission)
     — the bot will print the channel ID to the console
  6. Send /purge <channel_id> to the bot
"""

import os
import asyncio
from telegram import Update
from telegram.ext import Application, ChatMemberHandler, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")


async def track_added(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    new = result.new_chat_member
    if new.user.id == ctx.bot.id and new.status in ("administrator", "member"):
        chat = result.chat
        print(f"Bot added to: {chat.title!r}  ID: {chat.id}")


async def on_added(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg and msg.new_chat_members:
        for member in msg.new_chat_members:
            if member.id == ctx.bot.id:
                print(f"Added to: {msg.chat.title} | Chat ID: {msg.chat.id}")
                await msg.reply_text(f"Chat ID: {msg.chat.id}")
                return


async def purge(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /purge <channel_id>")
        return
    try:
        channel_id = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("Channel ID must be a number, e.g. -1001234567890")
        return

    bot = ctx.bot
    msg = await bot.send_message(channel_id, "Purging...")
    top = msg.message_id
    await msg.delete()

    deleted = 0
    misses = 0
    for mid in range(top - 1, 0, -1):
        try:
            await bot.delete_message(channel_id, mid)
            deleted += 1
            misses = 0
        except Exception:
            misses += 1
            if misses > 100:
                break
        if deleted % 30 == 0:
            await asyncio.sleep(1)  # respect rate limits

    await update.message.reply_text(f"Done. Deleted {deleted} messages from the target channel.")


if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(ChatMemberHandler(track_added, ChatMemberHandler.MY_CHAT_MEMBER))
    from telegram.ext import MessageHandler, filters
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_added))
    app.add_handler(CommandHandler("purge", purge))
    print("Bot running. Send /purge to trigger.")
    app.run_polling()
