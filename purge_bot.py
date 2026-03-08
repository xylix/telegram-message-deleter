"""Telegram bot that purges messages by ID from a JSON file via /purge command.

Usage:
  1. First run dump_ids.py to generate a message_ids_<chat_id>.json file
  2. Set API_ID, API_HASH, and BOT_TOKEN below (or as env vars)
  3. Add the bot as admin to the chat (needs Delete Messages permission)
  4. pip install telethon tqdm
  5. Run this script, then send /purge <filename.json> to the bot

Flags:
  --resume  Scan forward to the first surviving message and continue from there.
            Use this after an interrupted run (with or without a .progress file).
  --fresh   Ignore any saved progress and start from the beginning.
"""

import os
import json
import asyncio
from telethon import TelegramClient, events
from telethon.errors import (
    ChatAdminRequiredError,
    MessageDeleteForbiddenError,
    ChatWriteForbiddenError,
    FloodWaitError,
    UserAdminInvalidError,
)
from tqdm import tqdm

FATAL_ERRORS = (
    ChatAdminRequiredError,
    ChatWriteForbiddenError,
    UserAdminInvalidError,
)

BATCH = 100
BAR_WIDTH = 20

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

bot = TelegramClient("purge_bot", API_ID, API_HASH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_bar(done, total):
    filled = int(BAR_WIDTH * done / total) if total else BAR_WIDTH
    pct = int(100 * done / total) if total else 100
    return f"[{'█' * filled}{'░' * (BAR_WIDTH - filled)}] {pct}% ({done}/{total})"


def progress_path(filename):
    return filename + ".progress"


def load_progress(filename):
    path = progress_path(filename)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)["processed"]
    return None


def save_progress(filename, processed):
    with open(progress_path(filename), "w") as f:
        json.dump({"processed": processed}, f)


def clear_progress(filename):
    path = progress_path(filename)
    if os.path.exists(path):
        os.remove(path)


async def find_resume_index(chat_id, ids, status_msg):
    """Scan batches from the start; return the index of the first batch that
    still has at least one surviving message."""
    await status_msg.edit("Scanning for first surviving message...")
    for i in range(0, len(ids), BATCH):
        batch = ids[i:i + BATCH]
        msgs = await bot.get_messages(chat_id, ids=batch)
        if any(m is not None for m in msgs):
            return i
    return len(ids)  # everything is already gone


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

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
    parts = event.pattern_match.group(1).strip().split()
    flags = {p for p in parts if p.startswith("--")}
    filename = next((p for p in parts if not p.startswith("--")), None)

    if not filename:
        await event.respond(
            "Usage: /purge <filename.json> [--resume|--fresh]\n\n"
            "--resume  skip already-deleted messages and continue\n"
            "--fresh   ignore saved progress, start from the beginning"
        )
        return

    try:
        with open(filename) as f:
            data = json.load(f)
    except FileNotFoundError:
        await event.respond(f"File not found: {filename}")
        return

    chat_id = data["chat_id"]
    ids = data["message_ids"]
    total = len(ids)

    # --fresh: wipe saved state and proceed from 0
    if "--fresh" in flags:
        clear_progress(filename)
        start = 0
    else:
        saved = load_progress(filename)

        if saved is not None and "--resume" not in flags:
            # Saved progress exists but user hasn't confirmed — ask
            await event.respond(
                f"A previous run was interrupted after {saved}/{total} messages.\n"
                f"• `/purge {filename} --resume` — continue from where it stopped\n"
                f"• `/purge {filename} --fresh` — start over from the beginning"
            )
            return

        if saved is not None and "--resume" in flags:
            # Resume from saved checkpoint
            start = saved
        elif "--resume" in flags:
            # No progress file — scan the chat to find the resume point
            probe_msg = await event.respond("No saved progress found. Scanning...")
            start = await find_resume_index(chat_id, ids, probe_msg)
            await probe_msg.delete()
        else:
            # Normal fresh start: peek at the first batch to detect a prior
            # interrupted run that didn't use this bot
            msgs = await bot.get_messages(chat_id, ids=ids[:BATCH])
            already_gone = sum(1 for m in msgs if m is None)
            if already_gone == len(msgs):
                await event.respond(
                    f"The first {len(msgs)} messages are already deleted — looks like "
                    f"a previous run was interrupted.\n"
                    f"• `/purge {filename} --resume` — scan and skip ahead\n"
                    f"• `/purge {filename} --fresh` — attempt deletion from the beginning anyway"
                )
                return
            start = 0

    remaining = ids[start:]
    if not remaining:
        clear_progress(filename)
        await event.respond("Nothing left to delete — all messages are already gone.")
        return

    skipped_note = f" (skipping first {start} already-deleted)" if start else ""
    status = await event.respond(
        f"Deleting {len(remaining)} messages{skipped_note}...\n{make_bar(start, total)}"
    )

    deleted = 0
    failed = 0
    batches = [remaining[i:i + BATCH] for i in range(0, len(remaining), BATCH)]

    with tqdm(total=len(remaining), unit="msg", desc="Deleting") as bar:
        for batch in batches:
            try:
                await bot.delete_messages(chat_id, batch)
                deleted += len(batch)
            except FATAL_ERRORS as e:
                # Permission problem — no point continuing
                await status.edit(
                    f"Aborted: {type(e).__name__}\n\n"
                    f"The bot lacks permission to delete messages in this chat.\n"
                    f"Make sure the bot is an admin with Delete Messages permission.\n\n"
                    f"Note: basic groups do not support bot admin permissions — "
                    f"convert the group to a supergroup first (Group Settings → Advanced → Convert to Supergroup)."
                )
                print(f"Fatal error: {e}")
                return
            except FloodWaitError as e:
                wait_note = f"Rate limited by Telegram — waiting {e.seconds}s..."
                print(wait_note)
                await status.edit(
                    f"Deleting {len(remaining)} messages{skipped_note}...\n"
                    f"{make_bar(start + deleted + failed, total)}\n{wait_note}"
                )
                await asyncio.sleep(e.seconds)
                # Retry the same batch after the wait
                try:
                    await bot.delete_messages(chat_id, batch)
                    deleted += len(batch)
                except Exception as e2:
                    failed += len(batch)
                    print(f"Retry failed for batch at id {batch[0]}: {e2}")
            except MessageDeleteForbiddenError as e:
                failed += len(batch)
                print(f"Cannot delete batch starting at id {batch[0]}: {e}")
            except Exception as e:
                failed += len(batch)
                print(f"Unexpected error on batch starting at id {batch[0]}: {e}")
            bar.update(len(batch))
            processed_so_far = start + deleted + failed
            save_progress(filename, processed_so_far)
            await status.edit(
                f"Deleting {len(remaining)} messages{skipped_note}...\n"
                f"{make_bar(processed_so_far, total)}"
            )

    clear_progress(filename)
    summary = f"Done. Deleted {deleted}, failed {failed}."
    if start:
        summary += f" ({start} were already gone and skipped.)"
    await status.edit(summary)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    await bot.start(bot_token=BOT_TOKEN)
    print("Bot running. Send /purge <filename.json> to trigger.")
    await bot.run_until_disconnected()


asyncio.run(main())
