import os
import hmac
import logging
import json
import random
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

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
DRAFT_DB_PATH = os.getenv("DRAFT_DB_PATH", "./data/drafts.sqlite3")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_IDS = [x.strip() for x in os.getenv("TELEGRAM_CHAT_IDS", TELEGRAM_CHAT_ID).split(",") if x.strip()]
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
ADMIN_IDS = {x.strip() for x in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",") if x.strip()}
BINANCE_BASE = os.getenv("BINANCE_BASE_URL", "https://api.binance.com")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-6-luna")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
TRACKED_SYMBOLS = [x.strip().upper() for x in os.getenv(
    "TRACKED_SYMBOLS", "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT"
).split(",") if x.strip()]
PAYMENTS_ENABLED = os.getenv("PAYMENTS_ENABLED", "false").lower() == "true"
PAYMENT_ASSET = os.getenv("PAYMENT_ASSET", "")
PAYMENT_NETWORK = os.getenv("PAYMENT_NETWORK", "")
PAYMENT_RECEIVE_ADDRESS = os.getenv("PAYMENT_RECEIVE_ADDRESS", "")
PREMIUM_PRICE = os.getenv("PREMIUM_PRICE", "")
PREMIUM_DURATION_DAYS = int(os.getenv("PREMIUM_DURATION_DAYS", "30"))
AI_DAILY_REQUEST_LIMIT = max(0, int(os.getenv("AI_DAILY_REQUEST_LIMIT", "12")))
STARS_PREMIUM_PRICE = max(0, int(os.getenv("STARS_PREMIUM_PRICE", "0")))
STARS_IDEA_PRICE = max(0, int(os.getenv("STARS_IDEA_PRICE", "0")))
WALLET_BOT_USERNAME = os.getenv("TELEGRAM_WALLET_BOT_USERNAME", "EhsanWallet_bot").strip().lstrip("@")
SUPPORT_BTC_ADDRESS = os.getenv("SUPPORT_BTC_ADDRESS", "")
SUPPORT_BCH_ADDRESS = os.getenv("SUPPORT_BCH_ADDRESS", "")
SUPPORT_XRP_ADDRESS = os.getenv("SUPPORT_XRP_ADDRESS", "")
SUPPORT_XRP_TAG = os.getenv("SUPPORT_XRP_TAG", "")
SUPPORT_ADA_ADDRESS = os.getenv("SUPPORT_ADA_ADDRESS", "")

QUIZ_BANK = [
    {"q": "بیت‌کوین در چه سالی راه‌اندازی شد؟", "choices": ["A) ۲۰۰۸", "B) ۲۰۰۹", "C) ۲۰۱۱"], "answer": "b", "why": "شبکه بیت‌کوین در ژانویه ۲۰۰۹ فعال شد."},
    {"q": "کدام شاخص حجم معاملات بر حسب USDT را نشان می‌دهد؟", "choices": ["A) quoteVolume", "B) openTime", "C) highPrice"], "answer": "a", "why": "quoteVolume ارزش مظنه‌شده معاملات را نشان می‌دهد."},
    {"q": "آیا جهش حجم به‌تنهایی ورود نهنگ را ثابت می‌کند؟", "choices": ["A) بله", "B) خیر", "C) همیشه"], "answer": "b", "why": "جهش حجم فقط یک نشانه آماری است و به داده‌های تکمیلی نیاز دارد."},
]
RIDDLE_BANK = [
    ("آن چیست که هرچه بیشتر از آن برداری، بزرگ‌تر می‌شود؟", "چاله"),
    ("بی‌صدا بالا و پایین می‌رود و قیمت‌ها را نشان می‌دهد؛ چیست؟", "نمودار"),
    ("کلید دارد اما در را باز نمی‌کند؛ در دنیای رمزارز هم مهم است؛ چیست؟", "کلید خصوصی"),
]
JOKES = [
    "معامله‌گر گفت: حد ضرر گذاشتم. بازار پرسید: کجا؟ گفت: روی امیدم!",
    "چرا بلاک‌چین هیچ‌وقت تنها نیست؟ چون همیشه چند نود دوروبرش هستند!",
    "به ربات گفتم آینده را پیش‌بینی کن؛ گفت: اول لطفاً داده‌های گذشته را دست‌کاری نکن!",
]
ACTIVE_QUIZZES = {}


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
    baseline_volumes = volumes[-25:-1]
    baseline_volume = sum(baseline_volumes) / len(baseline_volumes) if baseline_volumes else 0.0
    volume_spike_ratio = volumes[-1] / baseline_volume if baseline_volume else 0.0
    return {
        "symbol": symbol,
        "price": float(ticker["lastPrice"]),
        "change_24h_pct": change,
        "volume_24h_base": float(ticker["volume"]),
        "quote_volume_24h": float(ticker["quoteVolume"]),
        "hourly_volume_latest": volumes[-1],
        "hourly_volume_avg_previous_24": baseline_volume,
        "volume_spike_ratio": volume_spike_ratio,
        "volume_signal": "جهش حجم؛ نیازمند بررسی" if volume_spike_ratio >= 2.5 else "عادی",
        "sma20_1h": sma20,
        "trend_1h": "بالای میانگین ۲۰ ساعته" if last >= sma20 else "پایین میانگین ۲۰ ساعته",
        "candles": [{"time": int(c[0]), "open": float(c[1]), "high": float(c[2]),
                     "low": float(c[3]), "close": float(c[4]), "volume": float(c[5])}
                    for c in candles[-24:]],
        "source": "Binance Spot public market data",
        "as_of": datetime.now(timezone.utc).isoformat()
    }


def openai_text(prompt, system_prompt, max_output_tokens=650):
    """Call the OpenAI Responses API; skip cleanly until a private key is configured."""
    if not OPENAI_API_KEY:
        return None
    if not consume_ai_quota():
        log.warning("Daily AI request limit reached; skipping this AI response")
        return None
    try:
        response = requests.post(
            f"{OPENAI_BASE_URL}/responses",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": OPENAI_MODEL,
                "store": False,
                "max_output_tokens": max_output_tokens,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
                    {"role": "user", "content": [{"type": "input_text", "text": prompt}]}
                ]
            },
            timeout=45
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("output_text"):
            return payload["output_text"].strip()
        chunks = []
        for item in payload.get("output", []):
            for part in item.get("content", []):
                if part.get("type") == "output_text" and part.get("text"):
                    chunks.append(part["text"])
        return "\n".join(chunks).strip() or None
    except Exception:
        log.exception("OpenAI analysis request failed")
        return None


def ai_market_commentary(rows):
    concise_rows = [{
        "symbol": row["symbol"],
        "price_usd": row["price"],
        "change_24h_pct": row["change_24h_pct"],
        "quote_volume_24h_usd": row["quote_volume_24h"],
        "trend_1h": row["trend_1h"],
        "volume_spike_ratio": round(row["volume_spike_ratio"], 2)
    } for row in rows]
    system_prompt = (
        "You are a cautious Persian-language digital-asset market analyst. "
        "Use only the supplied live snapshot. Never invent news, on-chain flows, order-book data, "
        "buy/sell volume, whale identities, or support/resistance levels not present in the data. "
        "Explain uncertainty. Do not give personalized financial advice or guaranteed predictions. "
        "Write concise, practical Persian in 4-6 bullets."
    )
    prompt = (
        "بر اساس داده‌های زیر جمع‌بندی کوتاه تهیه کن: وضعیت کلی، قدرت نسبی دارایی‌ها، "
        "ریسک‌ها و داده‌های لازم برای تأیید سیگنال. جهش حجم به‌تنهایی اثبات ورود نهنگ نیست. "
        "داده‌ها:\n" + json.dumps(concise_rows, ensure_ascii=False)
    )
    return openai_text(prompt, system_prompt, max_output_tokens=650)


def ai_answer(question):
    snapshots = []
    for symbol in TRACKED_SYMBOLS[:8]:
        try:
            snapshots.append(market_snapshot(symbol))
        except Exception as exc:
            log.warning("Could not refresh %s for AI question: %s", symbol, exc)
    if not snapshots:
        return "فعلاً دریافت داده زنده بازار ممکن نشد؛ کمی بعد دوباره امتحان کن."
    compact = [{
        "symbol": row["symbol"], "price": row["price"],
        "change_24h_pct": row["change_24h_pct"],
        "quote_volume_24h": row["quote_volume_24h"],
        "trend_1h": row["trend_1h"],
        "volume_spike_ratio": round(row["volume_spike_ratio"], 2)
    } for row in snapshots]
    return openai_text(
        "پرسش کاربر: " + question + "\n\nداده زنده بازار (JSON): " +
        json.dumps(compact, ensure_ascii=False),
        "به فارسی پاسخ بده. پاسخ باید مبتنی بر داده ارسالی باشد، کمبود داده را صریح بگو، "
        "میان واقعیت و برداشت تحلیلی تفکیک کن، خبر یا قیمت ساختگی نده و توصیه قطعی خرید/فروش نکن.",
        max_output_tokens=700
    )


def make_report():
    symbols = TRACKED_SYMBOLS
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
            f'وضعیت: {row["trend_1h"]} | '
            f'نسبت حجم یک‌ساعته به میانگین ۲۴ ساعت قبل: {row["volume_spike_ratio"]:.2f}x'
        )
    ai_notes = ai_market_commentary(rows)
    if ai_notes:
        lines += ["", "تحلیل هوش مصنوعی:", ai_notes]
    else:
        lines += ["", "تحلیل هوش مصنوعی پس از ثبت کلید API فعال می‌شود."]
    lines += [
        "",
        "جهش حجم فقط هشدار آماری است و فعالیت نهنگ را ثابت نمی‌کند.",
        "حجم خرید و فروش تفکیک‌شده از تیکر عمومی قابل استنتاج قطعی نیست.",
        "این گزارش اطلاعاتی است و توصیه قطعی خرید یا فروش نیست."
    ]
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


def telegram_safe_text(text, limit=4000):
    text = str(text)
    if len(text) <= limit:
        return text
    suffix = "\n… ادامه گزارش برای محدودیت تلگرام کوتاه شد."
    return text[:max(0, limit - len(suffix))] + suffix


def send_telegram(text, reply_markup=None):
    if not TELEGRAM_CHAT_IDS:
        raise RuntimeError("TELEGRAM_CHAT_IDS or TELEGRAM_CHAT_ID is not configured")
    text = telegram_safe_text(text)
    results = []
    errors = []
    for chat_id in TELEGRAM_CHAT_IDS:
        payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            results.append(telegram_call("sendMessage", payload))
        except Exception as exc:
            log.exception("Telegram delivery failed for a configured destination")
            errors.append(str(exc))
    if errors:
        raise RuntimeError(f"Telegram delivery failed for {len(errors)} destination(s)")
    return results


def is_admin(user_id):
    return str(user_id) in ADMIN_IDS


def draft_db():
    db_path = Path(DRAFT_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(db_path), timeout=10)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            draft_id TEXT PRIMARY KEY,
            body TEXT NOT NULL,
            data_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS premium_members (
            user_id TEXT PRIMARY KEY,
            expires_at TEXT NOT NULL,
            granted_at TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS payment_requests (
            invoice_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            asset TEXT NOT NULL,
            network TEXT NOT NULL,
            amount TEXT NOT NULL,
            address TEXT NOT NULL,
            tx_hash TEXT,
            status TEXT NOT NULL DEFAULT 'awaiting_tx',
            created_at TEXT NOT NULL,
            reviewed_at TEXT
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS ai_usage (
            usage_date TEXT PRIMARY KEY,
            request_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS stars_orders (
            payload TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            product_code TEXT NOT NULL,
            stars_amount INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            telegram_charge_id TEXT UNIQUE,
            created_at TEXT NOT NULL,
            paid_at TEXT
        )
    """)
    return connection


def get_draft(draft_id):
    with draft_db() as connection:
        row = connection.execute(
            "SELECT body, data_json, created_at, status FROM drafts WHERE draft_id = ?",
            (draft_id,)
        ).fetchone()
    if not row:
        return None
    return {"text": row[0], "data": json.loads(row[1]), "created": row[2], "status": row[3]}


def delete_draft(draft_id):
    with draft_db() as connection:
        connection.execute("DELETE FROM drafts WHERE draft_id = ?", (draft_id,))


def consume_ai_quota():
    """Atomically enforce a global daily cap on AI API requests."""
    if AI_DAILY_REQUEST_LIMIT <= 0:
        return False
    today = datetime.now(timezone.utc).date().isoformat()
    with draft_db() as connection:
        row = connection.execute(
            "SELECT request_count FROM ai_usage WHERE usage_date = ?", (today,)
        ).fetchone()
        if row and row[0] >= AI_DAILY_REQUEST_LIMIT:
            return False
        connection.execute(
            """INSERT INTO ai_usage (usage_date, request_count) VALUES (?, 1)
            ON CONFLICT(usage_date) DO UPDATE SET request_count = request_count + 1""",
            (today,)
        )
    return True


def payment_setup_ready():
    return bool(
        PAYMENTS_ENABLED and PAYMENT_ASSET and PAYMENT_NETWORK
        and PAYMENT_RECEIVE_ADDRESS and PREMIUM_PRICE
    )


def stars_product(product_code):
    products = {
        "premium_30d": {
            "title": "اشتراک پریمیوم ۳۰ روزه",
            "description": "دسترسی ۳۰ روزه به تحلیل تعاملی و امکانات ویژه ربات",
            "price": STARS_PREMIUM_PRICE,
        },
        "business_idea": {
            "title": "ایده کسب‌وکار اختصاصی با هوش مصنوعی",
            "description": "یک ایده کاربردی همراه با مشتری هدف، هزینه شروع و روش اعتبارسنجی",
            "price": STARS_IDEA_PRICE,
        },
    }
    product = products.get(product_code)
    return product if product and 1 <= product["price"] <= 25000 else None


def create_stars_order(user_id, product_code):
    product = stars_product(product_code)
    if not product:
        return None
    payload = "S" + uuid.uuid4().hex
    with draft_db() as connection:
        connection.execute(
            """INSERT INTO stars_orders
            (payload, user_id, product_code, stars_amount, created_at)
            VALUES (?, ?, ?, ?, ?)""",
            (payload, str(user_id), product_code, product["price"],
             datetime.now(timezone.utc).isoformat())
        )
    return payload, product


def get_stars_order(payload):
    with draft_db() as connection:
        row = connection.execute(
            """SELECT user_id, product_code, stars_amount, status
            FROM stars_orders WHERE payload = ?""", (payload,)
        ).fetchone()
    if not row:
        return None
    return {"user_id": row[0], "product_code": row[1],
            "stars_amount": row[2], "status": row[3]}


def send_stars_invoice(chat_id, user_id, product_code):
    order = create_stars_order(user_id, product_code)
    if not order:
        return False
    payload, product = order
    telegram_call("sendInvoice", {
        "chat_id": chat_id,
        "title": product["title"],
        "description": product["description"],
        "payload": payload,
        "currency": "XTR",
        "prices": [{"label": product["title"], "amount": product["price"]}],
    })
    return True


def stars_pre_checkout_is_valid(query):
    order = get_stars_order(query.get("invoice_payload", ""))
    sender_id = str((query.get("from") or {}).get("id", ""))
    return bool(
        order and order["status"] == "pending"
        and order["user_id"] == sender_id
        and query.get("currency") == "XTR"
        and query.get("total_amount") == order["stars_amount"]
    )


def complete_stars_payment(user_id, payment):
    payload = payment.get("invoice_payload", "")
    charge_id = payment.get("telegram_payment_charge_id", "")
    if payment.get("currency") != "XTR" or not charge_id:
        return None
    now = datetime.now(timezone.utc)
    with draft_db() as connection:
        row = connection.execute(
            """SELECT user_id, product_code, stars_amount, status
            FROM stars_orders WHERE payload = ?""", (payload,)
        ).fetchone()
        if (not row or row[0] != str(user_id) or row[3] != "pending"
                or row[2] != payment.get("total_amount")):
            return None
        cursor = connection.execute(
            """UPDATE stars_orders SET status = 'paid',
            telegram_charge_id = ?, paid_at = ?
            WHERE payload = ? AND status = 'pending'""",
            (charge_id, now.isoformat(), payload)
        )
        if cursor.rowcount != 1:
            return None
        if row[1] == "premium_30d":
            current = connection.execute(
                "SELECT expires_at FROM premium_members WHERE user_id = ?",
                (str(user_id),)
            ).fetchone()
            base = datetime.fromisoformat(current[0]) if current and datetime.fromisoformat(current[0]) > now else now
            expires_at = (base + timedelta(days=PREMIUM_DURATION_DAYS)).isoformat()
            connection.execute(
                """INSERT INTO premium_members (user_id, expires_at, granted_at)
                VALUES (?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET
                expires_at = excluded.expires_at, granted_at = excluded.granted_at""",
                (str(user_id), expires_at, now.isoformat())
            )
    return row[1]


def support_wallet_text():
    lines = ["آدرس‌های حمایت اختیاری (بدون فعال‌سازی اشتراک یا خدمت دیجیتال):"]
    if SUPPORT_BTC_ADDRESS:
        lines.append(f"Bitcoin | شبکه BTC:\n{SUPPORT_BTC_ADDRESS}")
    if SUPPORT_BCH_ADDRESS:
        lines.append(f"Bitcoin Cash | شبکه BCH:\n{SUPPORT_BCH_ADDRESS}")
    if SUPPORT_XRP_ADDRESS:
        lines.append(f"XRP | شبکه XRP:\n{SUPPORT_XRP_ADDRESS}")
        if SUPPORT_XRP_TAG:
            lines.append(f"Destination Tag الزامی: {SUPPORT_XRP_TAG}")
    if SUPPORT_ADA_ADDRESS:
        lines.append(f"Cardano | شبکه Cardano:\n{SUPPORT_ADA_ADDRESS}")
    if len(lines) == 1:
        lines.append("آدرس حمایتی هنوز روی سرور پیکربندی نشده است.")
    lines += [
        "قبل از انتقال، نام رمزارز و شبکه را دقیق تطبیق بده.",
        "این آدرس‌ها صرفاً برای حمایت اختیاری‌اند؛ خرید خدمات دیجیتال داخل تلگرام با Telegram Stars انجام می‌شود.",
        "هیچ‌وقت عبارت بازیابی یا کلید خصوصی را برای ربات ارسال نکن."
    ]
    return "\n".join(lines)


def is_premium_user(user_id):
    if is_admin(user_id):
        return True
    with draft_db() as connection:
        row = connection.execute(
            "SELECT expires_at FROM premium_members WHERE user_id = ?",
            (str(user_id),)
        ).fetchone()
    return bool(row and row[0] > datetime.now(timezone.utc).isoformat())


def create_payment_invoice(user_id):
    if not payment_setup_ready():
        return None
    invoice_id = "P" + uuid.uuid4().hex[:10].upper()
    created_at = datetime.now(timezone.utc).isoformat()
    with draft_db() as connection:
        connection.execute(
            """INSERT INTO payment_requests
            (invoice_id, user_id, asset, network, amount, address, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (invoice_id, str(user_id), PAYMENT_ASSET, PAYMENT_NETWORK,
             PREMIUM_PRICE, PAYMENT_RECEIVE_ADDRESS, created_at)
        )
    return invoice_id


def submit_payment(invoice_id, user_id, tx_hash):
    with draft_db() as connection:
        cursor = connection.execute(
            """UPDATE payment_requests SET tx_hash = ?, status = 'submitted'
            WHERE invoice_id = ? AND user_id = ? AND status = 'awaiting_tx'""",
            (tx_hash[:180], invoice_id.upper(), str(user_id))
        )
        return cursor.rowcount == 1


def pending_payments(limit=10):
    with draft_db() as connection:
        return connection.execute(
            """SELECT invoice_id, user_id, asset, network, amount, tx_hash
            FROM payment_requests WHERE status = 'submitted'
            ORDER BY created_at ASC LIMIT ?""",
            (limit,)
        ).fetchall()


def approve_payment(invoice_id):
    now = datetime.now(timezone.utc)
    with draft_db() as connection:
        row = connection.execute(
            "SELECT user_id, status FROM payment_requests WHERE invoice_id = ?",
            (invoice_id.upper(),)
        ).fetchone()
        if not row or row[1] != "submitted":
            return None
        user_id = row[0]
        current = connection.execute(
            "SELECT expires_at FROM premium_members WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        base = datetime.fromisoformat(current[0]) if current and datetime.fromisoformat(current[0]) > now else now
        expires_at = (base + timedelta(days=PREMIUM_DURATION_DAYS)).isoformat()
        connection.execute(
            """INSERT INTO premium_members (user_id, expires_at, granted_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET expires_at = excluded.expires_at,
                granted_at = excluded.granted_at""",
            (user_id, expires_at, now.isoformat())
        )
        connection.execute(
            "UPDATE payment_requests SET status = 'approved', reviewed_at = ? WHERE invoice_id = ?",
            (now.isoformat(), invoice_id.upper())
        )
    return user_id, expires_at


def reject_payment(invoice_id):
    with draft_db() as connection:
        cursor = connection.execute(
            """UPDATE payment_requests SET status = 'rejected', reviewed_at = ?
            WHERE invoice_id = ? AND status = 'submitted'""",
            (datetime.now(timezone.utc).isoformat(), invoice_id.upper())
        )
        return cursor.rowcount == 1


def scheduled_draft():
    """Create a private approval draft for the configured Telegram admin."""
    if not TELEGRAM_TOKEN or not TELEGRAM_WEBHOOK_SECRET or not ADMIN_IDS:
        log.warning("Scheduled draft skipped: Telegram token, webhook secret, or admin ID is missing")
        return
    draft_id, body = create_draft()
    keyboard = {"inline_keyboard": [[
        {"text": "تأیید و انتشار در کانال و گروه", "callback_data": f"approve:{draft_id}"},
        {"text": "رد گزارش", "callback_data": f"reject:{draft_id}"}
    ]]}
    for admin_id in ADMIN_IDS:
        telegram_call("sendMessage", {
            "chat_id": admin_id,
            "text": telegram_safe_text(f"پیش‌نویس زمان‌بندی‌شده {draft_id}\n\n{body}"),
            "reply_markup": keyboard
        })


def start_scheduler():
    if os.getenv("ENABLE_SCHEDULER", "false").lower() != "true":
        log.info("Scheduled report jobs are disabled")
        return None
    scheduler = BackgroundScheduler(timezone=ZoneInfo("Asia/Tehran"))
    for hour in (8, 12, 16, 21):
        scheduler.add_job(
            scheduled_draft,
            "cron",
            hour=hour,
            minute=0,
            id=f"market-draft-{hour:02d}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=3600
        )
    scheduler.start()
    log.info("Tehran schedule enabled: 08:00, 12:00, 16:00, 21:00")
    return scheduler


def configure_telegram_webhook():
    public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    if not (TELEGRAM_TOKEN and TELEGRAM_WEBHOOK_SECRET and public_domain):
        log.warning("Telegram webhook not configured: token, secret, or public domain missing")
        return
    try:
        telegram_call("setWebhook", {
            "url": f"https://{public_domain}/telegram/webhook",
            "secret_token": TELEGRAM_WEBHOOK_SECRET,
            "allowed_updates": ["message", "callback_query"],
            "drop_pending_updates": False
        })
        log.info("Telegram webhook configured")
    except Exception:
        log.exception("Could not configure Telegram webhook")


def create_draft():
    body, data = make_report()
    draft_id = uuid.uuid4().hex[:16]
    created_at = datetime.now(timezone.utc).isoformat()
    with draft_db() as connection:
        connection.execute(
            "INSERT INTO drafts (draft_id, body, data_json, created_at, status) VALUES (?, ?, ?, ?, 'pending')",
            (draft_id, body, json.dumps(data, ensure_ascii=False), created_at)
        )
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
    raw_text = (message.get("text") or "").strip()
    parts = raw_text.split(maxsplit=1)
    command = parts[0].split("@", 1)[0].lower() if parts else ""
    argument = parts[1].strip() if len(parts) > 1 else ""
    admin = is_admin(user_id)
    try:
        if command in ("/start", "/help"):
            telegram_call("sendMessage", {
                "chat_id": chat_id,
                "text": (
                    "ربات پایش بازار رمزارز\n"
                    "/plans پلن‌ها\n/pay فاکتور اشتراک (پس از فعال‌سازی پرداخت)\n"
                    "/paid شناسه‌فاکتور هش‌تراکنش\n"
                    "/ask پرسش تحلیلی ویژه مدیر و اعضای پریمیوم\n"
                    "/whales بررسی جهش‌های حجم\n"
                    "/draft ساخت پیش‌نویس (مدیر)\n/status وضعیت سرویس (مدیر)\n"
                    "انتشار فقط پس از تأیید مدیر انجام می‌شود."
                )
            })
        elif command == "/plans":
            status_text = (
                f"پلن پریمیوم: {PREMIUM_DURATION_DAYS} روز | مبلغ: {PREMIUM_PRICE} {PAYMENT_ASSET}"
                if payment_setup_ready()
                else "پلن پریمیوم در حال آماده‌سازی است؛ پرداخت هنوز فعال نشده است."
            )
            telegram_call("sendMessage", {"chat_id": chat_id, "text": status_text})
        elif command == "/pay":
            invoice_id = create_payment_invoice(user_id)
            if not invoice_id:
                telegram_call("sendMessage", {
                    "chat_id": chat_id,
                    "text": "پرداخت هنوز فعال نشده است. تا تعیین دارایی، شبکه، مبلغ و آدرس دریافت، واریز انجام نده."
                })
            else:
                telegram_call("sendMessage", {
                    "chat_id": chat_id,
                    "text": (
                        f"فاکتور: {invoice_id}\nمبلغ: {PREMIUM_PRICE} {PAYMENT_ASSET}\n"
                        f"شبکه: {PAYMENT_NETWORK}\nآدرس دریافت: {PAYMENT_RECEIVE_ADDRESS}\n"
                        "پس از انتقال دستور زیر را بفرست:\n"
                        f"/paid {invoice_id} TXID"
                    )
                })
        elif command == "/paid":
            fields = argument.split(maxsplit=1)
            if len(fields) != 2 or len(fields[1]) < 12:
                telegram_call("sendMessage", {
                    "chat_id": chat_id, "text": "فرمت درست: /paid شناسه‌فاکتور هش‌تراکنش"
                })
            elif submit_payment(fields[0], user_id, fields[1]):
                telegram_call("sendMessage", {
                    "chat_id": chat_id,
                    "text": "درخواست ثبت شد؛ پس از بررسی دستی تراکنش توسط مدیر، اشتراک فعال می‌شود."
                })
                for admin_id in ADMIN_IDS:
                    telegram_call("sendMessage", {
                        "chat_id": admin_id,
                        "text": f"پرداخت برای بررسی: {fields[0]}\nکاربر: {user_id}\nTXID: {fields[1]}"
                    })
            else:
                telegram_call("sendMessage", {
                    "chat_id": chat_id, "text": "فاکتور معتبر و در انتظار پرداخت برای این حساب پیدا نشد."
                })
        elif command == "/ask":
            if not is_premium_user(user_id):
                telegram_call("sendMessage", {
                    "chat_id": chat_id,
                    "text": "تحلیل تعاملی ویژه مدیر و اعضای پریمیوم است. برای اطلاعات پلن /plans را بفرست."
                })
            elif not OPENAI_API_KEY:
                telegram_call("sendMessage", {
                    "chat_id": chat_id, "text": "کلید سرویس هوش مصنوعی هنوز روی سرور ثبت نشده است."
                })
            elif not argument:
                telegram_call("sendMessage", {
                    "chat_id": chat_id, "text": "نمونه: /ask وضعیت بیت‌کوین چیست؟"
                })
            else:
                answer = ai_answer(argument) or "پاسخ هوش مصنوعی فعلاً در دسترس نیست."
                telegram_call("sendMessage", {
                    "chat_id": chat_id, "text": telegram_safe_text(answer), "disable_web_page_preview": True
                })
        elif command == "/whales":
            signals = []
            for symbol in TRACKED_SYMBOLS[:8]:
                try:
                    row = market_snapshot(symbol)
                    if row["volume_spike_ratio"] >= 2.0:
                        signals.append(
                            f'{symbol}: حجم یک‌ساعته {row["volume_spike_ratio"]:.2f} برابر میانگین ۲۴ ساعت قبل'
                        )
                except Exception as exc:
                    log.warning("Volume scan failed for %s: %s", symbol, exc)
            body = "\n".join(signals) if signals else "جهش حجم بالاتر از آستانه ۲ برابر مشاهده نشد."
            telegram_call("sendMessage", {
                "chat_id": chat_id,
                "text": "هشدار جهش حجم (نه اثبات فعالیت نهنگ):\n" + body
            })
        elif command == "/status" and admin:
            schedule = "فعال" if scheduler and scheduler.running else "غیرفعال"
            telegram_call("sendMessage", {
                "chat_id": chat_id,
                "text": (
                    f"سرویس: فعال\nهوش مصنوعی: {'کلید ثبت شده' if OPENAI_API_KEY else 'منتظر کلید'}"
                    f"\nمدل: {OPENAI_MODEL}\nزمان‌بندی تهران: {schedule}"
                    f"\nپرداخت: {'آماده تنظیم' if payment_setup_ready() else 'غیرفعال'}"
                    f"\nدارایی‌های تحت پایش: {', '.join(TRACKED_SYMBOLS)}"
                    f"\nمقصدهای انتشار: {len(TELEGRAM_CHAT_IDS)}"
                )
            })
        elif command == "/payments" and admin:
            rows = pending_payments()
            body = "\n".join(
                f"{row[0]} | user={row[1]} | {row[4]} {row[2]} / {row[3]} | TXID={row[5]}"
                for row in rows
            ) or "پرداخت در انتظار بررسی وجود ندارد."
            telegram_call("sendMessage", {"chat_id": chat_id, "text": body[:3900]})
        elif command == "/approvepay" and admin:
            approved = approve_payment(argument)
            telegram_call("sendMessage", {
                "chat_id": chat_id,
                "text": f"اشتراک کاربر {approved[0]} تا {approved[1]} فعال شد."
                if approved else "فاکتور در وضعیت قابل تأیید نیست."
            })
        elif command == "/rejectpay" and admin:
            rejected = reject_payment(argument)
            telegram_call("sendMessage", {
                "chat_id": chat_id, "text": "درخواست رد شد." if rejected else "درخواست قابل رد پیدا نشد."
            })
        elif not admin and command not in ("/start", "/help", "/plans", "/pay", "/paid", "/ask", "/whales"):
            return jsonify({"ok": True})
        elif command == "/draft" and admin:
            draft_id, body = create_draft()
            keyboard = {"inline_keyboard": [[
                {"text": "تأیید و انتشار", "callback_data": f"approve:{draft_id}"},
                {"text": "رد گزارش", "callback_data": f"reject:{draft_id}"}
            ]]}
            telegram_call("sendMessage", {"chat_id": chat_id,
                                           "text": telegram_safe_text(f"پیش‌نویس {draft_id}\n\n{body}"),
                                           "reply_markup": keyboard})
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
        draft = get_draft(draft_id)
        if not draft:
            telegram_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "پیش‌نویس منقضی یا ناموجود است"})
        elif action == "approve":
            send_telegram("گزارش تأییدشده\n\n" + draft["text"])
            telegram_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "گزارش منتشر شد"})
            delete_draft(draft_id)
        elif action == "reject":
            telegram_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "گزارش رد شد"})
            delete_draft(draft_id)
    except Exception:
        log.exception("Callback processing failed")
        if callback_id:
            try:
                telegram_call("answerCallbackQuery", {"callback_query_id": callback_id, "text": "خطا در پردازش"})
            except Exception:
                pass
    return jsonify({"ok": True})


# Railway runs a single Gunicorn worker for this service; enable jobs explicitly in production.
scheduler = start_scheduler()
configure_telegram_webhook()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
