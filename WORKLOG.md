# Worklog

## Goal

Bulk-delete all messages from a Telegram basic group.

---

## Attempt 1: python-telegram-bot, brute-force ID iteration

Started with `python-telegram-bot` (Bot API). The plan was to iterate message IDs downward from the latest known ID and call `deleteMessage` on each one.

This failed for two reasons:

1. **Bot API has no history enumeration.** There is no `getHistory` or equivalent — the bot can only see messages it receives in real time, not past ones.

2. **Basic groups use a global shared message ID sequence.** Message IDs in basic groups are not per-chat sequential integers starting from 1. They come from a global counter shared across all chats on the account, so the gaps between consecutive messages in one group can be enormous. A bail-out threshold of 100 consecutive misses would trigger after deleting only 2–3 real messages. Raising the threshold arbitrarily wouldn't help — the gaps are just too large to brute-force.

## Attempt 2: Telethon bot with iter_messages

Switched to Telethon (MTProto API) to get access to `iter_messages` / `GetHistoryRequest`, which actually enumerates message history.

Hit `BotMethodInvalidError`: bots cannot call `GetHistoryRequest`. History access is restricted to user accounts.

## Attempt 3: User account does everything

User-account automation via Telethon can call `iter_messages`. The obvious next step was to also run the deletions from the user account.

Rejected for two reasons:

- **TOS risk.** Automating writes on a personal account is in a greyer area than read-only access.
- **Accident risk.** A user session has full write access to every chat the account is in. A bug or wrong argument could silently delete messages from the wrong chat with no permission barrier stopping it.

## Final design: two-script split

`dump_ids.py` — user account, read-only
- Logs in via Telethon user session.
- Calls `iter_messages` to enumerate all message IDs in the target chat.
- Writes `message_ids_<chat_id>.json` containing the chat ID and list of message IDs.
- Never deletes anything.

`purge_bot.py` — bot account, deletes only from a named file
- Reads a specified JSON file (explicit bot command: `/purge <filename.json>`).
- Deletes only the message IDs listed in that file, in the chat ID listed in that file.
- The bot also replies with its chat ID when added to a group, so you don't need to use a third-party metadata bot to find it.

This contains the blast radius: the user session only ever reads, and the bot only ever deletes a known, explicit list of IDs from a specific chat.

### API credentials

Both scripts require `API_ID` and `API_HASH` from https://my.telegram.org. The registration form there is notoriously unreliable — no underscores allowed in the app name, Firefox has issues with it, and it rate-limits aggressively. The server configs and public keys shown on that page are not needed; Telethon handles the MTProto protocol details internally.

---

## Later additions

### purge_user.py — fallback for basic groups

`purge_bot.py` assumes the bot can be made admin with Delete Messages permission. This works in supergroups and channels, but **basic groups do not support per-permission admin roles for bots at all** — only the group creator can delete any message there. Since the target chat was a basic group that couldn't be converted to a supergroup, a third script was added:

`purge_user.py` — user account, deletes from JSON file
- Same JSON format as `purge_bot.py`.
- Uses the existing `user_session.session` from `dump_ids.py`.
- Runs from the command line rather than via bot commands.
- Includes a confirmation prompt that resolves the chat ID to a human-readable name before any deletion begins, to guard against passing the wrong file.

### Progress tracking and resume

Both deletion scripts save a `.progress` sidecar file (e.g. `message_ids_<chat_id>.json.progress`) after each batch. If the process is interrupted, re-running detects the saved state and prompts to `--resume` (continue from checkpoint) or `--fresh` (start over).

`--resume` without a progress file triggers a scan using `get_messages` to find the first batch that still has surviving messages, allowing recovery from runs interrupted before this feature existed or deleted externally.

### Rate limiting

The scripts no longer use a hardcoded sleep between batches. Instead they catch Telethon's `FloodWaitError`, which carries the exact number of seconds Telegram requires waiting, sleep that long, and retry the failed batch. This is strictly correct — a hardcoded delay is a guess; the flood wait response is authoritative.

### In-chat progress bar

`purge_bot.py` sends an initial status message when a `/purge` command is received and edits it after each batch with a Unicode block progress bar (`[████░░░░░░░░░░░░░░░░] 20% (200/1000)`). Both scripts also display a `tqdm` progress bar on the console.
