# telegram-bulk-deleter

Bulk-delete all messages from a Telegram group or channel — without deleting and re-creating the chat. Useful when you want to clear history but keep the group, its members, links, and settings intact.

**Why two scripts?** The Telegram Bot API has no method for listing message history, and brute-forcing sequential IDs doesn't work for basic groups (IDs come from a shared global sequence). So we have to use a user account session. We run it in two stages to have more steps of confirmation: dump the history message ids first, then delete everything from the resulting list.

**Why is there no hosted version?** This tool touches your personal Telegram account and accesses your group history. You should run it yourself so your data stays with you and doesn't pass through anyone else's server.

## Before you run this

`dump_ids.py` and `purge_user.py` use a **user account session** — meaning they act as you on Telegram. Before running any code from a stranger on the internet that does this, you should read through those two files and satisfy yourself that they:

- only read/delete from the `chat_id` in the JSON file and nowhere else
- do not exfiltrate message content, contact lists, or session credentials anywhere

The code is short. It is worth the five minutes.

## Setup

1. Get `API_ID` and `API_HASH` from https://my.telegram.org
2. Install dependencies:
   ```
   pip install telethon tqdm
   ```
3. Export env vars:
   ```
   export API_ID=...
   export API_HASH=...
   ```

## Usage

### Step 1 — Dump message IDs

```
python dump_ids.py <chat_id>
```

First run will prompt for your phone number and a login code. Writes `message_ids_<chat_id>.json`.

To find a chat ID: temporarily add [@userinfobot](https://t.me/userinfobot) to the group — it will report the chat ID. Remove it after.

### Step 2 — Delete messages

```
python purge_user.py message_ids_<chat_id>.json
```

Shows the chat name and message count, asks for confirmation, then deletes in batches with a progress bar. Your account must be an admin with Delete Messages permission in the chat.

If interrupted, just re-run — deleting already-deleted messages is a no-op.
