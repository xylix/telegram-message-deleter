# telegram-bulk-deleter

Two-script tool for bulk-deleting Telegram messages using your user account to list them and a bot to delete them.

**Why two scripts?** The Telegram Bot API has no method for listing message history, and brute-forcing sequential IDs doesn't work for basic groups (IDs come from a shared global sequence). So a user account session reads the history, and a bot with admin permissions does the deleting.

## Setup

1. Get `API_ID` and `API_HASH` from https://my.telegram.org
2. Create a bot via [@BotFather](https://t.me/BotFather) and get its `BOT_TOKEN`
3. Install dependencies:
   ```
   pip install telethon tqdm
   ```
4. Export env vars:
   ```
   export API_ID=...
   export API_HASH=...
   export BOT_TOKEN=...
   ```

## Usage

### Step 1 — Dump message IDs

```
python dump_ids.py <chat_id>
```

First run will prompt for your phone number and a login code. Writes `message_ids_<chat_id>.json`.

To find a chat ID: add the bot to the group — it will print and reply with the chat ID on join.

### Step 2 — Delete messages

There are two deletion scripts. Use the one that matches your chat type:

| Chat type | Script |
|-----------|--------|
| Supergroup or channel | `purge_bot.py` (bot with admin permissions) |
| Basic group | `purge_user.py` (your user account, must be group creator or admin) |

**Basic groups** do not support bot admin permissions at all — only the group creator can delete any message there. If you can convert the group to a supergroup (Group Settings → Advanced → Convert to Supergroup) the bot approach works and is preferred.

#### purge_bot.py (supergroups / channels)

Add the bot to the chat as admin with **Delete Messages** permission, then send:

```
/purge message_ids_<chat_id>.json
```

The bot replies with a live in-chat progress bar and the console shows a `tqdm` bar.

#### purge_user.py (basic groups)

```
python purge_user.py message_ids_<chat_id>.json
```

Reuses the `user_session.session` from Step 1. No bot required.

#### Resuming an interrupted run

Both scripts save a `.progress` sidecar file (e.g. `message_ids_<chat_id>.json.progress`) after each batch. If interrupted, re-run the same command — it will detect the saved state and prompt you:

```
# bot:
/purge message_ids_<chat_id>.json --resume   # continue from checkpoint
/purge message_ids_<chat_id>.json --fresh    # start over

# user script:
python purge_user.py message_ids_<chat_id>.json --resume
python purge_user.py message_ids_<chat_id>.json --fresh
```

If there is no `.progress` file but the first batch is already gone (deleted externally), both scripts detect this and suggest `--resume`, which scans forward to find the first surviving message.
