"""Delete messages from a basic group using your user account session.

Use this instead of purge_bot.py when the chat is a basic group (not a
supergroup), where bots cannot be given admin permissions.

Usage:
  python purge_user.py <filename.json> [--resume|--fresh]

Flags:
  --resume  Scan forward to the first surviving message and continue from there.
  --fresh   Ignore any saved progress and start from the beginning.

Requires the same user_session.session created by dump_ids.py.
"""

import os
import sys
import json
import asyncio
from telethon import TelegramClient
from telethon.errors import (
    ChatAdminRequiredError,
    MessageDeleteForbiddenError,
    ChatWriteForbiddenError,
)
from tqdm import tqdm

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")

BATCH = 100
BAR_WIDTH = 20

FATAL_ERRORS = (ChatAdminRequiredError, ChatWriteForbiddenError)


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


async def find_resume_index(client, chat_id, ids):
    print("Scanning for first surviving message...")
    for i in range(0, len(ids), BATCH):
        batch = ids[i:i + BATCH]
        msgs = await client.get_messages(chat_id, ids=batch)
        if any(m is not None for m in msgs):
            return i
    return len(ids)


async def main():
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not args:
        print(__doc__)
        sys.exit(1)

    filename = args[0]

    try:
        with open(filename) as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {filename}")
        sys.exit(1)

    chat_id = data["chat_id"]
    ids = data["message_ids"]
    total = len(ids)

    # Determine start index
    if "--fresh" in flags:
        clear_progress(filename)
        start = 0
    else:
        saved = load_progress(filename)

        if saved is not None and "--resume" not in flags:
            print(
                f"Previous run was interrupted after {saved}/{total} messages.\n"
                f"  --resume   continue from where it stopped\n"
                f"  --fresh    start over from the beginning"
            )
            sys.exit(0)

        if saved is not None and "--resume" in flags:
            start = saved
            print(f"Resuming from saved checkpoint: {start}/{total}")
        elif "--resume" in flags:
            client = TelegramClient("user_session", API_ID, API_HASH)
            await client.start()
            start = await find_resume_index(client, chat_id, ids)
            await client.disconnect()
            if start > 0:
                print(f"Detected {start} already-deleted messages. Resuming from index {start}.")
            else:
                print("No already-deleted messages found. Starting from the beginning.")
        else:
            # Peek at the first batch to detect an externally interrupted run
            client = TelegramClient("user_session", API_ID, API_HASH)
            await client.start()
            msgs = await client.get_messages(chat_id, ids=ids[:BATCH])
            await client.disconnect()
            already_gone = sum(1 for m in msgs if m is None)
            if already_gone == len(msgs):
                print(
                    f"The first {len(msgs)} messages are already deleted — looks like a previous interrupted run.\n"
                    f"  --resume   scan and skip ahead to first surviving message\n"
                    f"  --fresh    attempt deletion from the beginning anyway"
                )
                sys.exit(0)
            start = 0

    remaining = ids[start:]
    if not remaining:
        clear_progress(filename)
        print("Nothing left to delete — all messages are already gone.")
        return

    client = TelegramClient("user_session", API_ID, API_HASH)
    await client.start()

    deleted = 0
    failed = 0
    batches = [remaining[i:i + BATCH] for i in range(0, len(remaining), BATCH)]
    skipped_note = f" (skipping first {start} already-deleted)" if start else ""

    print(f"Deleting {len(remaining)} messages{skipped_note}...")

    with tqdm(total=len(remaining), unit="msg", desc="Deleting") as bar:
        for batch in batches:
            try:
                await client.delete_messages(chat_id, batch)
                deleted += len(batch)
            except FATAL_ERRORS as e:
                print(
                    f"\nFatal error: {type(e).__name__}: {e}\n"
                    "You need to be an admin (or the group creator) to delete messages."
                )
                await client.disconnect()
                return
            except MessageDeleteForbiddenError as e:
                failed += len(batch)
                print(f"\nCannot delete batch at id {batch[0]}: {e}")
            except Exception as e:
                failed += len(batch)
                print(f"\nUnexpected error on batch at id {batch[0]}: {e}")
            bar.update(len(batch))
            save_progress(filename, start + deleted + failed)
            await asyncio.sleep(1)

    clear_progress(filename)
    summary = f"Done. Deleted {deleted}, failed {failed}."
    if start:
        summary += f" ({start} were already gone and skipped.)"
    print(summary)
    await client.disconnect()


asyncio.run(main())
