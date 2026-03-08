"""Delete messages listed in a JSON file using your user account.

Usage:
  python purge_user.py <filename.json>

The JSON file is produced by dump_ids.py.
Requires the user_session.session created by dump_ids.py.
"""

import os
import sys
import asyncio
import json
from telethon import TelegramClient
from telethon.errors import ChatAdminRequiredError, ChatWriteForbiddenError, FloodWaitError
from tqdm import tqdm

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

BATCH = 100


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    chat_id = data["chat_id"]
    ids = data["message_ids"]

    client = TelegramClient("user_session", API_ID, API_HASH)
    await client.start()

    try:
        entity = await client.get_entity(chat_id)
        chat_name = getattr(entity, "title", None) or getattr(entity, "username", str(chat_id))
    except Exception:
        chat_name = str(chat_id)

    print(f"\nAbout to delete {len(ids)} messages from '{chat_name}' (id: {chat_id})")
    try:
        input("Press Enter to confirm, Ctrl+C to abort: ")
    except KeyboardInterrupt:
        print("\nAborted.")
        await client.disconnect()
        return

    deleted = failed = 0
    batches = [ids[i:i + BATCH] for i in range(0, len(ids), BATCH)]

    with tqdm(total=len(ids), unit="msg") as bar:
        for batch in batches:
            try:
                await client.delete_messages(chat_id, batch)
                deleted += len(batch)
            except FloodWaitError as e:
                tqdm.write(f"Rate limited — waiting {e.seconds}s...")
                await asyncio.sleep(e.seconds)
                try:
                    await client.delete_messages(chat_id, batch)
                    deleted += len(batch)
                except Exception as e2:
                    tqdm.write(f"Retry failed: {e2}")
                    failed += len(batch)
            except (ChatAdminRequiredError, ChatWriteForbiddenError) as e:
                print(f"\nPermission error: {e}\nMake sure your account is an admin with Delete Messages permission.")
                await client.disconnect()
                return
            except Exception as e:
                tqdm.write(f"Error on batch at id {batch[0]}: {e}")
                failed += len(batch)
            bar.update(len(batch))

    print(f"Done. Deleted {deleted}, failed {failed}.")
    await client.disconnect()


asyncio.run(main())
