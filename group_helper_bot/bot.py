"""Standalone Telegram polling worker for NOVA Help."""
import html
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import requests

from group_helper_bot.store import GroupStore
from group_helper_bot.ui import WELCOME, GUIDE, GROUP_GUIDE, home_keyboard, admin_keyboard

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("nova-help")
TOKEN = os.getenv("HELP_TELEGRAM_BOT_TOKEN", "").strip()
DB_PATH = os.getenv("HELP_DB_PATH", "/data/group-helper.sqlite3")
API = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
ADMIN_IDS = {x.strip() for x in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",") if x.strip()}
HTTP = requests.Session()
HTTP.headers.update({"User-Agent": "NOVA-Help/1.0"})
STORE = GroupStore(DB_PATH) if TOKEN else None
AWAITING_REPORT = set()
BOT_ID = None


def telegram(method, payload=None, params=None):
    response = HTTP.post(f"{API}/{method}", json=payload or {}, params=params, timeout=35)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API {method} returned ok=false")
    return data.get("result")


def send(chat_id, text, reply_markup=None, reply_to=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    return telegram("sendMessage", payload)


def is_admin(chat_id, user_id):
    member = telegram("getChatMember", {"chat_id": chat_id, "user_id": user_id})
    return member.get("status") in ("creator", "administrator")


def private_assistant_answer(prompt):
    if not OPENAI_KEY:
        return ("🧠 <b>دستیار NOVA</b>\n"
                "اتصال هوش مصنوعی هنوز تنظیم نشده است. فعلاً می‌توانم راهنمای منو و دستورهای ربات را ارائه کنم.\n"
                "برای پاسخ هوشمند، مدیر سامانه باید OPENAI_API_KEY را در متغیرهای Railway همین سرویس ثبت کند.")
    try:
        response = HTTP.post(
            f"{OPENAI_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_KEY}"},
            json={
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": "You are NOVA Help, a concise and practical Persian-speaking assistant. Give safe, actionable help. Never claim to perform actions you cannot perform."},
                    {"role": "user", "content": prompt[:6000]},
                ],
                "temperature": 0.4,
            },
            timeout=45,
        )
        if response.status_code in (401, 403):
            log.error("AI authentication/permission failed (HTTP %s); returning fallback", response.status_code)
            return "⚠️ اتصال هوش مصنوعی به مشکل احراز هویت یا مجوز خورده است. درخواستت ثبت نشد؛ مدیر باید کلید و دسترسی API را بررسی کند."
        response.raise_for_status()
        data = response.json()
        return html.escape(data["choices"][0]["message"]["content"][:3900])
    except (requests.RequestException, KeyError, ValueError):
        log.exception("AI request failed; prompt omitted from logs")
        return "⚠️ در حال حاضر پاسخ هوشمند در دسترس نیست. کمی بعد دوباره امتحان کن یا از بخش گزارش مشکل استفاده کن."


def target_user(message):
    reply = message.get("reply_to_message") or {}
    return reply.get("from") if reply.get("from", {}).get("id") else None


def admin_required(chat_id, user_id):
    try:
        return is_admin(chat_id, user_id)
    except Exception:
        log.exception("Admin permission check failed")
        return False


def moderate(message, command, args):
    chat = message.get("chat", {})
    sender = message.get("from", {})
    chat_id, actor_id = chat.get("id"), sender.get("id")
    if chat.get("type") not in ("group", "supergroup"):
        return send(chat_id, "این دستور فقط داخل گروه قابل استفاده است.")
    if not admin_required(chat_id, actor_id):
        return send(chat_id, "⛔ این عملیات فقط برای مدیران گروه فعال است.")
    target = target_user(message)
    if command in ("/rules", "/id", "/setrules"):
        pass
    elif command == "/unban":
        if not args or not args[0].isdigit():
            return send(chat_id, "قالب: <code>/unban USER_ID</code>")
        telegram("unbanChatMember", {"chat_id": chat_id, "user_id": int(args[0]), "only_if_banned": True})
        return send(chat_id, "✅ مسدودیت کاربر رفع شد.")
    elif not target:
        return send(chat_id, "برای این دستور، روی پیام کاربر موردنظر پاسخ بده و دستور را بفرست.")
    target_id = target["id"]
    if command == "/warn":
        count = STORE.add_warning(chat_id, target_id)
        return send(chat_id, f"⚠️ اخطار شماره <b>{count}</b> برای کاربر ثبت شد.", reply_to=message.get("message_id"))
    if command == "/mute":
        minutes = 10
        if args and args[0].isdigit():
            minutes = max(1, min(int(args[0]), 10080))
        until = int((datetime.now(timezone.utc) + timedelta(minutes=minutes)).timestamp())
        telegram("restrictChatMember", {
            "chat_id": chat_id, "user_id": target_id, "until_date": until,
            "permissions": {"can_send_messages": False, "can_send_audios": False,
                            "can_send_documents": False, "can_send_photos": False,
                            "can_send_videos": False, "can_send_video_notes": False,
                            "can_send_voice_notes": False, "can_send_polls": False,
                            "can_send_other_messages": False, "can_add_web_page_previews": False},
        })
        return send(chat_id, f"🔇 کاربر برای {minutes} دقیقه محدود شد.")
    if command == "/unmute":
        telegram("restrictChatMember", {
            "chat_id": chat_id, "user_id": target_id,
            "permissions": {"can_send_messages": True, "can_send_audios": True,
                            "can_send_documents": True, "can_send_photos": True,
                            "can_send_videos": True, "can_send_video_notes": True,
                            "can_send_voice_notes": True, "can_send_polls": True,
                            "can_send_other_messages": True, "can_add_web_page_previews": True},
        })
        return send(chat_id, "🔊 محدودیت ارسال پیام کاربر برداشته شد.")
    if command == "/ban":
        telegram("banChatMember", {"chat_id": chat_id, "user_id": target_id})
        return send(chat_id, "🚫 کاربر از گروه مسدود شد.")
    return send(chat_id, "دستور مدیریتی ناشناخته است.")


def handle_callback(callback):
    query_id = callback.get("id")
    message = callback.get("message", {})
    chat = message.get("chat", {})
    user = callback.get("from", {})
    data = callback.get("data", "")
    if query_id:
        try:
            telegram("answerCallbackQuery", {"callback_query_id": query_id})
        except Exception:
            log.exception("Callback acknowledgement failed")
    chat_id = chat.get("id")
    if not chat_id:
        return
    if data == "home":
        return send(chat_id, WELCOME, home_keyboard())
    if data == "assistant":
        return send(chat_id, "🧠 <b>دستیار هوشمند</b>\nسؤالت را در همین گفت‌وگوی خصوصی بنویس. برای حفظ حریم خصوصی، اطلاعات حساس و رمزها را ارسال نکن.")
    if data == "group":
        return send(chat_id, GROUP_GUIDE, admin_keyboard())
    if data == "guide":
        return send(chat_id, GUIDE, home_keyboard())
    if data == "rules":
        rules = STORE.get_rules(chat_id) if chat.get("type") in ("group", "supergroup") else None
        return send(chat_id, "📜 <b>قوانین گروه</b>\n" + html.escape(rules or "هنوز قانونی برای این گروه ثبت نشده است. مدیر گروه می‌تواند /setrules متن قوانین را اجرا کند."))
    if data == "moderation":
        return send(chat_id, GROUP_GUIDE)
    if data == "report":
        AWAITING_REPORT.add(str(user.get("id")))
        return send(chat_id, "📨 مشکل یا پیشنهادت را در پیام بعدی بنویس. پیام برای مدیران سامانه ارسال می‌شود.")
    if data == "status":
        return send(chat_id, "🟢 <b>وضعیت NOVA Help</b>\nربات در حال پاسخ‌گویی است. برای ابزارهای مدیریتی، آن را در گروه مدیر کن و دسترسی‌های لازم را بده.")
    return send(chat_id, "این گزینه هنوز تعریف نشده است. /menu را بزن.")


def handle_web_app_data(message):
    raw = (message.get("web_app_data") or {}).get("data")
    if not raw:
        return False
    chat_id = message.get("chat", {}).get("id")
    user_id = message.get("from", {}).get("id")
    if not chat_id or not user_id:
        return True
    try:
        action = json.loads(raw).get("action", "")
    except (TypeError, ValueError):
        send(chat_id, "⚠️ داده داشبورد قابل‌خواندن نبود. /menu را دوباره بزن.")
        return True
    if action == "assistant":
        send(chat_id, "🧠 <b>دستیار هوشمند</b>\nسؤالت را همین‌جا بنویس تا بررسی کنم.")
    elif action == "group":
        send(chat_id, GROUP_GUIDE, admin_keyboard())
    elif action == "guide":
        send(chat_id, GUIDE, home_keyboard())
    elif action == "report":
        AWAITING_REPORT.add(str(user_id))
        send(chat_id, "📨 مشکل یا پیشنهادت را در پیام بعدی بنویس.")
    elif action == "status":
        send(chat_id, "🟢 <b>وضعیت NOVA Help</b>\nربات پاسخ‌گوست. فعال بودن AI به اعتبار کلید API وابسته است.")
    elif action == "commands":
        send(chat_id, GROUP_GUIDE)
    else:
        send(chat_id, "این ابزار هنوز فعال نشده است.")
    return True

def handle_message(message):
    chat = message.get("chat", {})
    user = message.get("from", {})
    chat_id, user_id = chat.get("id"), user.get("id")
    if not chat_id or not user_id:
        return
    if handle_web_app_data(message):
        return
    text = (message.get("text") or "").strip()
    if message.get("new_chat_members"):
        if BOT_ID and any(member.get("id") == BOT_ID for member in message["new_chat_members"]):
            send(chat_id, "✨ سلام! من NOVA Help هستم. برای مدیریت گروه، دسترسی مدیر لازم دارم. /help")
        return
    if not text:
        return
    parts = text.split()
    command = parts[0].split("@", 1)[0].lower() if parts[0].startswith("/") else ""
    args = parts[1:]
    if command in ("/start", "/menu"):
        if chat.get("type") == "private":
            send(chat_id, WELCOME, home_keyboard())
        else:
            send(chat_id, "✨ NOVA Help به گروه اضافه شد. /help برای دیدن دستورها؛ /rules برای قوانین.")
        return
    if command in ("/help",):
        send(chat_id, GUIDE if chat.get("type") == "private" else GROUP_GUIDE)
        return
    if command == "/rules":
        rules = STORE.get_rules(chat_id)
        send(chat_id, "📜 <b>قوانین گروه</b>\n" + html.escape(rules or "هنوز قانونی ثبت نشده است."))
        return
    if command == "/id":
        target = target_user(message)
        send(chat_id, f"🆔 شناسه گروه: <code>{chat_id}</code>\nشناسه شما: <code>{user_id}</code>" +
             (f"\nشناسه کاربر پاسخ‌داده‌شده: <code>{target['id']}</code>" if target else ""))
        return
    if command == "/setrules":
        if chat.get("type") not in ("group", "supergroup") or not admin_required(chat_id, user_id):
            return send(chat_id, "⛔ فقط مدیر گروه می‌تواند قوانین را تغییر دهد.")
        rules = text.partition(" ")[2].strip()
        if not rules:
            return send(chat_id, "قالب: <code>/setrules متن قوانین گروه</code>")
        STORE.set_rules(chat_id, rules, user_id)
        return send(chat_id, "✅ قوانین گروه ذخیره شد.")
    if command in ("/warn", "/mute", "/unmute", "/ban", "/unban"):
        try:
            moderate(message, command, args)
        except Exception:
            log.exception("Moderation action failed; message content omitted")
            send(chat_id, "⚠️ عملیات انجام نشد. دسترسی مدیر ربات و مجوزهای حذف/محدودسازی اعضا را بررسی کن.")
        return
    if chat.get("type") == "private":
        if str(user_id) in AWAITING_REPORT:
            AWAITING_REPORT.discard(str(user_id))
            report_id = STORE.add_report(user_id, user.get("username"), text)
            delivered = 0
            for admin_id in ADMIN_IDS:
                try:
                    send(int(admin_id), f"📨 <b>گزارش جدید #{report_id}</b>\nکاربر: <code>{user_id}</code>\n{html.escape(text[:1800])}")
                    delivered += 1
                except Exception:
                    log.exception("Support report delivery failed")
            if delivered:
                return send(chat_id, "✅ گزارش ثبت و برای مدیر سامانه ارسال شد.")
            return send(chat_id, "✅ گزارش ذخیره شد؛ اما فهرست مدیران گیرنده هنوز تنظیم نشده است.")
        send(chat_id, private_assistant_answer(text))


def main():
    global BOT_ID
    if not TOKEN:
        raise RuntimeError("HELP_TELEGRAM_BOT_TOKEN is required")
    me = telegram("getMe")
    BOT_ID = me.get("id")
    log.info("NOVA Help started as @%s", me.get("username", "unknown"))
    telegram("setMyCommands", {"commands": [
        {"command": "start", "description": "شروع و نمایش منوی اصلی"},
        {"command": "menu", "description": "نمایش منوی اصلی"},
        {"command": "help", "description": "راهنما و امکانات"},
        {"command": "rules", "description": "مشاهده قوانین گروه"},
        {"command": "id", "description": "نمایش شناسه گروه و کاربر"},
        {"command": "warn", "description": "اخطار به کاربر (با پاسخ به پیام)"},
        {"command": "mute", "description": "محدودسازی کاربر (با پاسخ به پیام)"},
        {"command": "unmute", "description": "رفع محدودیت کاربر (با پاسخ به پیام)"},
        {"command": "ban", "description": "مسدودسازی کاربر (با پاسخ به پیام)"},
        {"command": "unban", "description": "رفع مسدودیت با شناسه کاربر"},
        {"command": "setrules", "description": "تنظیم قوانین گروه"},
    ]})
    offset = None
    while True:
        try:
            params = {"timeout": 45, "allowed_updates": ["message", "callback_query"]}
            if offset is not None:
                params["offset"] = offset
            response = HTTP.get(f"{API}/getUpdates", params=params, timeout=55)
            response.raise_for_status()
            payload = response.json()
            if not payload.get("ok"):
                raise RuntimeError("Telegram getUpdates returned ok=false")
            for update in payload.get("result", []):
                offset = update["update_id"] + 1
                try:
                    if "callback_query" in update:
                        handle_callback(update["callback_query"])
                    else:
                        handle_message(update.get("message", {}))
                except Exception:
                    log.exception("Update handling failed; user content omitted from logs")
        except requests.RequestException:
            log.exception("Telegram polling transport error; verify network and webhook/polling exclusivity")
            time.sleep(7)
        except RuntimeError:
            log.exception("Telegram polling failed; retrying after delay")
            time.sleep(7)


if __name__ == "__main__":
    main()
