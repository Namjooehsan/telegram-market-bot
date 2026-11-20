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
- `HELP_MINIAPP_URL`: optional public HTTPS URL of the companion dashboard. When set, `/start` adds a Mini App launch button.

Optional variables:
- `OPENAI_API_KEY`: AI assistant access.
- `OPENAI_BASE_URL`: defaults to `https://api.openai.com/v1`.
- `OPENAI_MODEL`: defaults to `gpt-4o-mini`.
- `TELEGRAM_ADMIN_IDS`: comma-separated owner/admin Telegram IDs for support notifications.
- `LOG_LEVEL`: defaults to `INFO`.

Attach a persistent Railway volume at `/data`. Do not reuse the market bot's Telegram token. If the dedicated bot has a webhook configured, intentionally remove that webhook in BotFather/Telegram API administration before starting polling; this worker does not silently delete webhooks.

## Colorful dashboard
The companion dashboard is in `group_helper_bot/miniapp/`. Deploy a second Railway web service from this repository with start command `python -m group_helper_bot.miniapp.server`, expose its HTTPS domain, then set that full URL as `HELP_MINIAPP_URL` on the bot worker. The Mini App sends section selections back to the bot through Telegram WebApp data; it does not claim group permissions or AI are active before the worker is configured.

## Permissions in groups
Add the bot to the group and promote it to administrator with only the permissions needed for moderation (delete messages, restrict members, ban users). Telegram group permissions and privacy mode may affect which messages it receives.

## Important limitations
- Telegram's native inline keyboard does not support custom button colours. The companion Mini App provides the colourful dashboard; it must be separately hosted and its HTTPS URL configured as `HELP_MINIAPP_URL`.
- Automatic spam deletion is not enabled by default.
- This is a moderation/assistant tool, not an unrestricted group owner. It checks admin status before sensitive actions.
- Never send bot tokens, passwords, or API keys in chat or commit them to Git.
