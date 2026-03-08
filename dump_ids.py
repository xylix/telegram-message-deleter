"""Dump all message IDs from a chat to a JSON file using your user account.

Usage:
  1. Set API_ID and API_HASH (from https://my.telegram.org)
  2. pip install telethon
  3. python dump_ids.py <chat_id>
  4. First run will ask for your phone number and a login code
"""

import os
import sys
import json
import asyncio
from telethon import TelegramClient

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python dump_ids.py <chat_id>")
        sys.exit(1)

    chat_id = int(sys.argv[1])
    client = TelegramClient("user_session", API_ID, API_HASH)
    await client.start()

    ids = []
    async for msg in client.iter_messages(chat_id):
        ids.append(msg.id)

    outfile = f"message_ids_{chat_id}.json"
    with open(outfile, "w") as f:
        json.dump(ids, f)

    print(f"Dumped {len(ids)} message IDs to {outfile}")
    await client.disconnect()


asyncio.run(main())
