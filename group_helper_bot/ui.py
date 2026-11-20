"""Telegram menu presentation helpers for NOVA Group Helper."""

MAIN_MENU = {
    "inline_keyboard": [
        [{"text": "🧠 دستیار هوشمند", "callback_data": "assistant"},
         {"text": "🛡 مدیریت گروه", "callback_data": "group"}],
        [{"text": "📚 راهنما و آموزش", "callback_data": "guide"},
         {"text": "📨 گزارش مشکل", "callback_data": "report"}],
        [{"text": "⚙️ وضعیت و تنظیمات", "callback_data": "status"}],
    ]
}

ADMIN_MENU = {
    "inline_keyboard": [
        [{"text": "📜 قوانین گروه", "callback_data": "rules"},
         {"text": "👮 راهنمای مدیر", "callback_data": "moderation"}],
        [{"text": "🔙 بازگشت به خانه", "callback_data": "home"}],
    ]
}

WELCOME = (
    "✨ <b>به NOVA Help خوش آمدی</b>\n"
    "<i>دستیار هوشمند و مرکز مدیریت گروه‌های تلگرام</i>\n\n"
    "از اینجا می‌توانی راهنمایی بگیری، گروهت را مدیریت کنی و مشکل‌ها را گزارش بدهی.\n"
    "برای فعال شدن ابزارهای مدیریتی، ربات باید در گروه عضو و مدیر باشد."
)

GUIDE = (
    "📚 <b>راهنمای سریع</b>\n\n"
    "• در گفت‌وگوی خصوصی، سؤال خود را مستقیم برای دستیار بنویس.\n"
    "• برای دیدن منوی اصلی /menu را بفرست.\n"
    "• در گروه، /rules و /id برای مشاهده قوانین و شناسه‌هاست.\n"
    "• مدیران می‌توانند روی پیام کاربر پاسخ دهند و /warn، /mute یا /ban را اجرا کنند.\n"
    "• برای کنترل گروه، ربات باید دسترسی‌های لازم را داشته باشد."
)

GROUP_GUIDE = (
    "🛡 <b>مرکز مدیریت گروه</b>\n\n"
    "ربات را به گروه اضافه کن و از بخش تنظیمات گروه، دسترسی مدیر بده.\n"
    "دستورها فقط برای مدیران گروه اجرا می‌شوند:\n"
    "<code>/warn</code> — ثبت اخطار روی پیام پاسخ‌داده‌شده\n"
    "<code>/mute 10</code> — محدودیت ارسال پیام برای ۱۰ دقیقه\n"
    "<code>/unmute</code> — رفع محدودیت ارسال پیام\n"
    "<code>/ban</code> — مسدود کردن کاربر\n"
    "<code>/unban USER_ID</code> — رفع مسدودیت با شناسه عددی\n"
    "<code>/setrules متن قوانین</code> — ثبت قوانین گروه\n"
    "<code>/rules</code> — نمایش قوانین\n"
    "<code>/id</code> — نمایش شناسه گروه و کاربر"
)

def home_keyboard():
    return MAIN_MENU

def admin_keyboard():
    return ADMIN_MENU
