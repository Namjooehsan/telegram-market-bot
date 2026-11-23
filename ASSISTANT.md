# NOVA Doer — «هر ورودی را به یک کار کامل تبدیل کن»

NOVA Doer is a standalone, Telegram-authenticated Mini App MVP for task completion, not an open-ended chat. It is in this repo branch at `assistant_service.py` and `assistant/index.html`.

## Features in this MVP

- A task-first Persian RTL home screen: assistant / do-it, file analysis & study, web research, voice transcription, image & OCR, writing, summary, translation and multi-file comparison.
- Upload PDF, UTF-8 text/Markdown/CSV, PNG/JPEG/WebP, and common audio files. Up to 5 files and 10 MB combined per operation. Inputs are passed to the configured AI provider and not intentionally retained by the application.
- A strong “do it” workflow prompt for compound user requests (e.g. summarize a PDF, create questions/flashcards, and make a 7-day study plan).
- Telegram `initData` verification on every account/credit API; no client-supplied user IDs are trusted.
- Atomic free-operation metering (10 per UTC month by default; configurable), refund on provider failure, bounded upload sizes and request rate limits.
- Web search can be enabled for the answer operation using the OpenAI Responses `web_search` tool.
- Outputs are displayed in the Mini App and are not persisted by this MVP.

## Run as a separate Railway web service

The existing bot `/` is its JSON health endpoint and the existing `/miniapp` is NOVA Hub. This assistant is deliberately a separate service to avoid changing those production routes. Create a second web service from this repository and use:

```sh
gunicorn --workers 1 --bind 0.0.0.0:$PORT assistant_service:app
```

Configure:

- `TELEGRAM_BOT_TOKEN`: same bot token used to verify Telegram Mini App `initData` (store in Railway Variables only).
- `OPENAI_API_KEY`: provider key, stored only as a Railway secret.
- `ASSISTANT_DB_PATH=/data/assistant.sqlite3` and attach a persistent volume at `/data` (stores monthly operation counts only).
- `ASSISTANT_FREE_MONTHLY_CREDITS=10` (0–100) and optionally `ASSISTANT_OPENAI_MODEL`.
- `ASSISTANT_WEB_SEARCH_ENABLED=true` to enable the Responses `web_search` tool for the answer action; provider support, model access and pricing apply.
- Optional `ASSISTANT_TRANSCRIPTION_MODEL` (defaults to `gpt-4o-mini-transcribe`).

Set the public HTTPS assistant service URL as the Telegram Mini App URL in BotFather. The main bot's existing `/apps` button still targets NOVA Hub; configuring a new BotFather menu button is an explicit Telegram/BotFather step, not performed by this code. Do not add a Telegram bot token to a URL or frontend.

## Monetization status — not live until deliberately configured

The application currently provides only free monthly credits. It does **not** implement Pro/Power account entitlements, charge cards, PayPal, Stars invoices, recurring subscriptions, refunds, or affiliate commissions. Do not advertise paid plans or take money through a manual screenshot. Telegram digital-service billing should be implemented through Telegram Stars with verified payment webhooks, idempotent fulfillment, plan entitlements and refund handling; the existing project's Stars flow is separate and does not grant NOVA Doer plans. PayPal requires an eligible merchant account, official checkout integration, server-verified webhooks, order/refund/chargeback handling, and regional availability. A PayPal email by itself is not a payment integration.

Before launch, test with a Telegram test account and a provider sandbox/low-cost account; review provider retention, privacy notices, copyright, and data-processing/legal requirements. AI output can be wrong and must be checked. Never upload secrets, credentials or sensitive personal information. Files and complete outputs are sent to the configured AI provider; this service does not store them, but the provider's handling/retention terms still apply.

## API

- `GET /health` — health check.
- `GET /api/assistant/status` — verified Telegram user credit status.
- `POST /api/assistant/jobs` — multipart form: `task`, `instructions`, `language`, and repeated `files` fields.

Accepted task IDs: `do_it`, `study`, `answer`, `transcribe`, `ocr`, `rewrite`, `summarize`, `translate`, `compare`.
