"""Minimal Telegram polling bot for encrypted, read-only public-address tracking."""
import logging
import os
import time
from pathlib import Path

import requests

from wallet_bot.store import WalletStore
from wallet_bot.validation import validate_public_address, explorer_url

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("nova-wallet-bot")
TOKEN = os.getenv("WALLET_TELEGRAM_BOT_TOKEN", "").strip()
DB_PATH = os.getenv("WALLET_DB_PATH", "/data/wallet-addresses.sqlite3")
API = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "NOVA-ReadOnly-Wallet/1.0"})
STORE = WalletStore(DB_PATH) if TOKEN else None


def send(chat_id, text):
    response = HTTP.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True}, timeout=20)
    response.raise_for_status()


def handle(message):
    chat = message.get("chat", {})
    user = message.get("from", {})
    chat_id, user_id = chat.get("id"), user.get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not user_id or not text:
        return
    if chat.get("type") != "private":
        send(chat_id, "برای حفظ حریم خصوصی، ربات کیف پول فقط در گفت‌وگوی خصوصی کار می‌کند.")
        return
    parts = text.split(maxsplit=3)
    command = parts[0].split("@", 1)[0].lower()
    if command in ("/start", "/help"):
        send(chat_id, "NOVA Wallet — نسخه فقط‌خواندنی و غیرامانی\n\n"
             "/add BTC آدرس [برچسب] — افزودن آدرس عمومی\n"
             "/list — فهرست آدرس‌های ذخیره‌شده\n"
             "/remove شناسه — حذف آدرس\n"
             "/security — توضیح امنیت\n\n"
             "هرگز عبارت بازیابی، کلید خصوصی، رمز یا کد ورود را ارسال نکن. این ربات تراکنش امضا یا برداشت انجام نمی‌دهد.")
    elif command == "/add":
        if len(parts) < 3:
            send(chat_id, "قالب: /add BTC آدرس [برچسب]\nشبکه‌های پشتیبانی‌شده: BTC, BCH, XRP, ADA")
            return
        network, address = parts[1].upper(), parts[2].strip()
        label = parts[3].strip()[:80] if len(parts) > 3 else ""
        if not validate_public_address(network, address):
            send(chat_id, "قالب آدرس با شبکه انتخاب‌شده تطبیق ندارد. این بررسی فقط قالبی است و صحت checksum را تضمین نمی‌کند.")
            return
        try:
            entry_id = STORE.add(user_id, network, address, label)
        except ValueError:
            send(chat_id, "حداکثر ۳۰ آدرس برای هر حساب مجاز است. ابتدا یک آدرس را با /remove حذف کن.")
            return
        send(chat_id, f"آدرس عمومی با شناسه {entry_id} ذخیره شد.\n{explorer_url(network, address)}\nموجودی زنده و تراکنش‌ها در این نسخه هنوز واکشی نمی‌شوند.")
    elif command == "/list":
        entries = STORE.list_for_user(user_id)
        if not entries:
            send(chat_id, "هنوز آدرسی ذخیره نکرده‌ای. برای افزودن: /add BTC آدرس [برچسب]")
            return
        lines = ["آدرس‌های عمومی ذخیره‌شده:"]
        for item in entries[:30]:
            label = f" — {item['label']}" if item["label"] else ""
            lines.append(f"#{item['id']} {item['network']}{label}\n{item['address']}\n{explorer_url(item['network'], item['address'])}")
        send(chat_id, "\n\n".join(lines))
    elif command == "/remove":
        if len(parts) != 2 or not parts[1].isdigit():
            send(chat_id, "قالب: /remove شناسه")
            return
        removed = STORE.remove(user_id, int(parts[1]))
        send(chat_id, "آدرس حذف شد." if removed else "شناسه متعلق به حساب شما نیست یا وجود ندارد.")
    elif command == "/security":
        send(chat_id, "امنیت NOVA Wallet:\n• فقط آدرس عمومی دریافت می‌شود.\n• آدرس و برچسب در SQLite با Fernet رمزنگاری می‌شوند.\n• کلید رمزنگاری فقط در متغیر محرمانه WALLET_DATA_KEY نگهداری می‌شود.\n• کلید خصوصی، seed phrase، رمز و اختیار برداشت هرگز دریافت یا ذخیره نمی‌شود.\n• این نسخه فقط دفترچه آدرس است؛ موجودی زنده، امضای تراکنش و انتقال وجه هنوز فعال نیست.")
    else:
        send(chat_id, "فرمان ناشناخته است. /help را بفرست.")


def main():
    if not TOKEN:
        raise RuntimeError("WALLET_TELEGRAM_BOT_TOKEN is required")
    # Do not silently remove an existing webhook; it may belong to another deployment.
    webhook_response = HTTP.get(f"{API}/getWebhookInfo", timeout=20)
    webhook_response.raise_for_status()
    webhook_payload = webhook_response.json()
    if not webhook_payload.get("ok"):
        raise RuntimeError("Telegram getWebhookInfo returned ok=false")
    if webhook_payload.get("result", {}).get("url"):
        raise RuntimeError("A Telegram webhook is already configured; disable it deliberately before starting polling")

    offset = None
    while True:
        try:
            params = {"timeout": 50, "allowed_updates": ["message"]}
            if offset is not None:
                params["offset"] = offset
            response = HTTP.get(f"{API}/getUpdates", params=params, timeout=60)
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok"):
                raise RuntimeError("Telegram getUpdates returned ok=false")
            for update in payload.get("result", []):
                offset = update["update_id"] + 1
                try:
                    handle(update.get("message", {}))
                except Exception:
                    log.exception("Wallet update failed; user content omitted from logs")
        except requests.RequestException:
            log.exception("Telegram transport error")
            time.sleep(5)


if __name__ == "__main__":
    main()
