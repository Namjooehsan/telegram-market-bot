import os
import hmac
import logging
from datetime import datetime, timezone
from threading import Lock

import requests
from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("market-bot")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
limiter = Limiter(get_remote_address, app=app, default_limits=["120 per hour"])
draft_lock = Lock()
DRAFTS = {}

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = [x.strip() for x in os.getenv("TELEGRAM_CHAT_IDS", os.getenv("TELEGRAM_CHAT_ID", "")).split(",") if x.strip()]
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
ADMIN_IDS = {x.strip() for x in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",") if x.strip()}
BINANCE_BASE = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")


def binance_get(path, params=None):
    response = requests.get(BINANCE_BASE + path, params=params, timeout=12)
    response.raise_for_status()
    return response.json()


def market_snapshot(symbol="BTCUSDT"):
    ticker = binance_get("/api/v3/ticker/24hr", {"symbol": symbol})
    candles = binance_get("/api/v3/klines", {"symbol": symbol, "interval": "1h", "limit": 30})
    closes = [float(c[4]) for c in candles]
    volumes = [float(c[5]) for c in candles]
    last = closes[-1]
    sma20 = sum(closes[-20:]) / min(20, len(closes))
    change = float(ticker["priceChangePercent"])
    return {
        "symbol": symbol,
        "price": float(ticker["lastPrice"]),
        "change_24h_pct": change,
        "volume_24h_base": float(ticker["volume"]),
        "quote_volume_24h": float(ticker["quoteVolume"]),
        "hourly_volume_latest": volumes[-1],
        "sma20_1h": sma20,
        "trend_1h": "بالای میانگین ۲۰ ساعته" if last >= sma20 else "پایین میانگین ۲۰ ساعته",
        "candles": [{"time": int(c[0]), "open": float(c[1]), "high": float(c[2]),
                     "low": float(c[3]), "close": float(c[4]), "volume": float(c[5])}
                    for c in candles[-24:]],
        "source": "Binance Spot public market data",
        "as_of": datetime.now(timezone.utc).isoformat()
    }


def make_report():
    symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]
    rows = []
    for symbol in symbols:
        try:
            rows.append(market_snapshot(symbol))
        except Exception as exc:
            log.warning("Could not fetch %s: %s", symbol, exc)
    if not rows:
        raise RuntimeError("No market data could be retrieved")
    lines = ["گزارش پایش بازار رمزارز", "منبع: بازار اسپات بایننس | داده‌ها تقریبی و لحظه‌ای"]
    for row in rows:
        lines.append(
            f'{row["symbol"]}: {row["price"]:,.4f} USDT | '
            f'تغییر ۲۴ساعته: {row["change_24h_pct"]:+.2f}% | '
            f'حجم مظنه ۲۴ساعته: {row["quote_volume_24h"]:,.0f} USDT | '
            f'وضعیت: {row["trend_1h"]}'
        )
    lines += ["", "این گزارش اطلاعاتی است و توصیه قطعی خرید یا فروش نیست.",
              "حجم خرید و فروش تفکیک‌شده از داده عمومی تیکر قابل استنتاج قطعی نیست."]
    return "\n".join(lines), rows


def telegram_call(method, payload):
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}",
        json=payload, timeout=15
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error: {data}")
    return data["result"]


def send_telegram(text, reply_markup=None, skip_chat_ids=None):
    """Send to every configured destination; report partial failures without hiding them."""
    if not TELEGRAM_CHAT_IDS:
        raise RuntimeError("TELEGRAM_CHAT_IDS is not configured")
    skipped = set(skip_chat_ids or [])
    result = {"sent": [], "failed": []}
    for chat_id in TELEGRAM_CHAT_IDS:
        if chat_id in skipped:
            continue
        payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            telegram_call("sendMessage", payload)
            result["sent"].append(chat_id)
        except Exception as exc:
            log.exception("Telegram delivery failed for destination %s", chat_id)
            result["failed"].append({"chat_id": chat_id, "error": str(exc)[:300]})
    return result


def is_admin(user_id):
    return str(user_id) in ADMIN_IDS


def create_draft():
    body, data = make_report()
    draft_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    with draft_lock:
        DRAFTS[draft_id] = {"text": body, "data": data, "created": datetime.now(timezone.utc).isoformat()}
    return draft_id, body


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def index():
    return jsonify({"service": "telegram-market-bot", "status": "running", "mode": "approval-required"})


@app.get("/health")
@limiter.exempt
def health():
    return jsonify({"ok": True, "time": datetime.now(timezone.utc).isoformat()})


@app.get("/api/market/<symbol>")
@limiter.limit("30 per minute")
def market(symbol):
    symbol = symbol.upper()
    if not symbol.endswith("USDT") or len(symbol) > 20:
        return jsonify({"error": "Use a valid USDT symbol, e.g. BTCUSDT"}), 400
    try:
        return jsonify(market_snapshot(symbol))
    except requests.RequestException:
        log.exception("Market data request failed")
        return jsonify({"error": "Market data provider unavailable"}), 502
    except Exception:
        log.exception("Market snapshot failed")
        return jsonify({"error": "Unable to build market snapshot"}), 500


@app.post("/telegram/webhook")
@limiter.limit("60 per minute")
def telegram_webhook():
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not TELEGRAM_WEBHOOK_SECRET or not hmac.compare_digest(supplied, TELEGRAM_WEBHOOK_SECRET):
        return jsonify({"error": "unauthorized"}), 401
    update = request.get_json(silent=True) or {}
    if update.get("callback_query"):
        return telegram_callback()
    message = update.get("message") or {}
    user = message.get("from") or {}
    user_id = user.get("id")
    chat_id = str((message.get("chat") or {}).get("id", ""))
    command = (message.get("text") or "").strip().split()[0].lower() if message.get("text") else ""
    if not is_admin(user_id):
        return jsonify({"ok": True})
    try:
        if command == "/draft":
            draft_id, body = create_draft()
            keyboard = {"inline_keyboard": [[
                {"text": "تأیید و انتشار", "callback_data": f"approve:{draft_id}"},
                {"text": "رد گزارش", "callback_data": f"reject:{draft_id}"}
            ]]}
            telegram_call("sendMessage", {"chat_id": chat_id, "text": f"پیش‌نویس {draft_id}\n\n{body}",
                                           "reply_markup": keyboard})
        elif command == "/help":
            telegram_call("sendMessage", {"chat_id": chat_id,
                "text": "دستورها:\n/draft ساخت پیش‌نویس گزارش\n/help راهنما\n\nانتشار فقط پس از تأیید مدیر انجام می‌شود."})
    except Exception:
        log.exception("Telegram command failed")
    return jsonify({"ok": True})


@app.post("/telegram/callback")
@limiter.limit("60 per minute")
def telegram_callback():
    supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not TELEGRAM_WEBHOOK_SECRET or not hmac.compare_digest(supplied, TELEGRAM_WEBHOOK_SECRET):
        return jsonify({"error": "unauthorized"}), 401
    update = request.get_json(silent=True) or {}
    callback = update.get("callback_query") or {}
    user_id = (callback.get("from") or {}).get("id")
    data = callback.get("data", "")
    callback_id = callback.get("id")
    try:
        if not is_admin(user_id):
            telegram_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "دسترسی غیرمجاز"})
            return jsonify({"ok": True})
        action, _, draft_id = data.partition(":")
        with draft_lock:
            draft = DRAFTS.get(draft_id)
        if not draft:
            telegram_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "پیش‌نویس منقضی یا ناموجود است"})
        elif action == "approve":
            delivery = send_telegram(
                "گزارش تأییدشده\n\n" + draft["text"],
                skip_chat_ids=draft.get("sent_to", [])
            )
            with draft_lock:
                draft["sent_to"] = list(set(draft.get("sent_to", []) + delivery["sent"]))
            if delivery["failed"]:
                telegram_call("answerCallbackQuery", {
                    "callback_query_id": callback_id,
                    "text": f"ارسال ناقص: {len(delivery['sent'])} مقصد موفق، {len(delivery['failed'])} مقصد ناموفق؛ برای تلاش مجدد دوباره تأیید کنید"
                })
            else:
                telegram_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": f"گزارش به {len(delivery['sent'])} مقصد ارسال شد"})
                with draft_lock:
                    DRAFTS.pop(draft_id, None)
        elif action == "reject":
            telegram_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "گزارش رد شد"})
            with draft_lock:
                DRAFTS.pop(draft_id, None)
    except Exception:
        log.exception("Callback processing failed")
        if callback_id:
            try:
                telegram_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "خطا در پردازش"})
            except Exception:
                pass
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
