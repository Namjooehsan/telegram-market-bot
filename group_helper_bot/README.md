# NOVA Help — Group Assistant MVP

A dedicated Telegram worker for private assistance and practical group administration.

## Included
- Persian inline home menu with assistant, group management, guide, support report and status sections.
- Private-chat assistant using the configured OpenAI-compatible Chat Completions API, with a useful fallback if AI credentials are unavailable.
- Admin-only group commands: `/rules`, `/setrules`, `/id`, `/warn`, `/mute`, `/unmute`, `/ban`, and `/unban`.
- SQLite persistence for group rules, warnings and support reports.
- Admin permission checks before moderation actions.
- Polling worker with bounded request timeouts and safe logs.

## Railway setup
Create a **separate worker service** from this repository. Start command:

```bash
python -m group_helper_bot.bot
```

Required variables:
- `HELP_TELEGRAM_BOT_TOKEN`: dedicated token for `@helptelegramgroup01_bot`.
- `HELP_DB_PATH`: recommended `/data/group-helper.sqlite3` on a persistent volume.

Optional variables:
- `OPENAI_API_KEY`: AI assistant access.
- `OPENAI_BASE_URL`: defaults to `https://api.openai.com/v1`.
- `OPENAI_MODEL`: defaults to `gpt-4o-mini`.
- `TELEGRAM_ADMIN_IDS`: comma-separated owner/admin Telegram IDs for support notifications.
- `LOG_LEVEL`: defaults to `INFO`.

Attach a persistent Railway volume at `/data`. Do not reuse the market bot's Telegram token. If the dedicated bot has a webhook configured, intentionally remove that webhook in BotFather/Telegram API administration before starting polling; this worker does not silently delete webhooks.

## Permissions in groups
Add the bot to the group and promote it to administrator with only the permissions needed for moderation (delete messages, restrict members, ban users). Telegram group permissions and privacy mode may affect which messages it receives.

## Important limitations
- Telegram's native inline keyboard does not support custom button colours. This MVP uses an emoji-rich menu and formatted layout. A truly colourful dashboard requires a Telegram Mini App/web app, which can be added as a companion UI.
- Automatic spam deletion is not enabled by default.
- This is a moderation/assistant tool, not an unrestricted group owner. It checks admin status before sensitive actions.
- Never send bot tokens, passwords, or API keys in chat or commit them to Git.
