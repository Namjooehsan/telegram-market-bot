# NOVA Wallet — non-custodial address book MVP

This service is deliberately **read-only**. It stores public wallet addresses for later explorer access. It does not create wallets, hold funds, sign transactions, or send payments.

## Supported address formats
BTC, BCH, XRP, ADA. Validation is format-level only; it is not a full network checksum verification.

## Required Railway variables
- `WALLET_TELEGRAM_BOT_TOKEN`: token for the dedicated wallet bot.
- `WALLET_DATA_KEY`: Fernet key used to encrypt addresses and labels at rest.
- `WALLET_DB_PATH`: persistent volume path, recommended `/data/wallet-addresses.sqlite3`.

Generate a key locally with:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Put the output directly into Railway Variables. Do not send it in chat or commit it to GitHub. Back it up securely: losing it makes stored addresses unreadable. Replacing it without migrating the database has the same effect.

## Telegram commands
- `/start`, `/help`
- `/add BTC <public-address> [label]`
- `/list`
- `/remove <id>`
- `/security`

The bot only accepts messages in private chats. Each user's entries are isolated by Telegram user ID. Addresses and labels are encrypted with Fernet before storage. Never send a seed phrase, private key, password, or login code.

## Deployment
Run as a separate Railway worker service from this repository with start command:
```bash
python -m wallet_bot.bot
```
Attach a persistent volume at `/data`. Set the required variables above. Ensure this bot token is not used by another polling process. If a webhook is already configured for this bot, disable it intentionally before enabling polling.

## Explicitly not implemented
Live on-chain balances, transaction notifications, wallet creation/import, transaction signing, swaps, deposits, withdrawals, and fiat payments. These require separately reviewed providers, threat modelling, and explicit product decisions.
