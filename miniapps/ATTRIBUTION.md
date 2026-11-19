# NOVA Hub — attribution and implementation notes

This repository's Mini App interface and Python integration are newly authored for this project. No application source files, UI assets, branding, or proprietary templates were copied from the repositories below. They were reviewed as technical references for ecosystem conventions and license comparison.

## Reviewed open-source references

| Project | License reported by GitHub | Stars observed during research | Use in this project |
|---|---:|---:|---|
| [Telegram-Mini-Apps/tma.js](https://github.com/Telegram-Mini-Apps/tma.js) | MIT | 1,216 | Reviewed as a maintained TypeScript SDK/reference; no source files imported |
| [Telegram-Mini-Apps/reactjs-template](https://github.com/Telegram-Mini-Apps/reactjs-template) | MIT | 430 | Reviewed as a React/Vite starter; not installed because the production service is Flask/Python |
| [telegram-mini-apps-dev/TelegramUI](https://github.com/telegram-mini-apps-dev/TelegramUI) | MIT | 874 | Reviewed for UI patterns; no components/assets copied |
| [telegram-mini-apps-dev/awesome-telegram-mini-apps](https://github.com/telegram-mini-apps-dev/awesome-telegram-mini-apps) | CC0-1.0 | 1,407 | Discovery/reference list only |

Star counts are observations from repository metadata when reviewed, not a ranking of customer popularity or evidence of revenue. Licenses may change; re-check the upstream repository's current LICENSE file before importing any code in the future.

## Official platform documentation

- Telegram Mini Apps: https://core.telegram.org/bots/webapps
- Telegram Bot API: https://core.telegram.org/bots/api
- Telegram Stars for digital goods: https://core.telegram.org/bots/payments-stars

## Implementation notes

- miniapps/index.html is a lightweight, responsive, self-contained web frontend that uses Telegram's official Web App JavaScript bridge. It adds no React/Node build chain to the production Flask container.
- miniapps/core.py contains the 12-item free catalogue, five paid product definitions, Telegram initData HMAC validation, and localized product prompts.
- app.py serves the Mini App, validates user sessions on private endpoints, creates Telegram Stars invoice links, and stores paid entitlements/results in the existing persistent SQLite database.
- Digital services inside Telegram use Telegram Stars (XTR). Never substitute crypto-wallet donations or unverified transfer receipts for Telegram's digital-goods payment flow.
