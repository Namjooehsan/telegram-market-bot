"""Mini App catalogue, Telegram initData verification and paid-product prompts."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from urllib.parse import parse_qsl

from advertising import LANGUAGES

FREE_APPS = [
    {"id": "market_prices", "category": "بازار و رمزارز", "title": "تابلوی قیمت زنده", "title_en": "Live Market Board", "description": "قیمت و تغییر روزانه دارایی‌های منتخب را از Binance ببین", "icon": "📈"},
    {"id": "pnl_calculator", "category": "بازار و رمزارز", "title": "ماشین‌حساب سود و زیان", "title_en": "P/L Calculator", "description": "بازده تقریبی موقعیت را با قیمت ورود و مقدار محاسبه کن", "icon": "🧮"},
    {"id": "margin_calculator", "category": "کسب‌وکار و فروش", "title": "محاسبه‌گر حاشیه سود", "title_en": "Profit Margin", "description": "قیمت تمام‌شده، قیمت فروش و حاشیه سود را بسنج", "icon": "💹"},
    {"id": "break_even", "category": "کسب‌وکار و فروش", "title": "نقطه سربه‌سر", "title_en": "Break-even", "description": "تعداد فروش لازم برای پوشش هزینه‌های ثابت را محاسبه کن", "icon": "🎯"},
    {"id": "caption_studio", "category": "تولید محتوا", "title": "استودیوی کپشن", "title_en": "Caption Studio", "description": "برای محصول و شبکه اجتماعی کپشن اولیه بساز", "icon": "✍️"},
    {"id": "hashtag_helper", "category": "تولید محتوا", "title": "پیشنهاد هشتگ", "title_en": "Hashtag Helper", "description": "از موضوع و زبان دلخواه، هشتگ‌های مرتبط بگیر", "icon": "#️⃣"},
    {"id": "daily_planner", "category": "بهره‌وری و مدیریت", "title": "برنامه‌ریز روزانه", "title_en": "Daily Planner", "description": "کارها را ثبت و روی همین دستگاه پیگیری کن", "icon": "🗓️"},
    {"id": "focus_timer", "category": "بهره‌وری و مدیریت", "title": "تایمر تمرکز", "title_en": "Focus Timer", "description": "چرخه تمرکز و استراحت را مدیریت کن", "icon": "⏱️"},
    {"id": "flashcards", "category": "آموزش و یادگیری", "title": "فلش‌کارت واژگان", "title_en": "Vocabulary Cards", "description": "واژه‌های پرکاربرد انگلیسی و فارسی را تمرین کن", "icon": "🧠"},
    {"id": "market_quiz", "category": "آموزش و یادگیری", "title": "آزمون سواد بازار", "title_en": "Market Quiz", "description": "دانش پایه بازار و مدیریت ریسک را بسنج", "icon": "🎓"},
    {"id": "daily_trivia", "category": "بازی و سرگرمی", "title": "دانستنی روز", "title_en": "Daily Trivia", "description": "با پرسش‌های کوتاه اطلاعات عمومی بازی کن", "icon": "🎲"},
    {"id": "word_scramble", "category": "بازی و سرگرمی", "title": "بازی کلمه‌سازی", "title_en": "Word Puzzle", "description": "حروف به‌هم‌ریخته را مرتب کن و امتیاز بگیر", "icon": "🔤"},
]

PAID_PRODUCTS = [
    {
        "code": "miniapp_ad_campaign",
        "rank": 1,
        "title": "کارخانه کمپین چندزبانه",
        "title_en": "Multilingual Campaign Factory",
        "description": "بسته تبلیغاتی بومی‌سازی‌شده برای کشور، منطقه و مخاطب هدف",
        "price_env": "MINIAPP_AD_CAMPAIGN_STARS",
        "default_price": 0,
        "icon": "🌍",
        "prompt_key": "ad_campaign",
    },
    {
        "code": "miniapp_business_plan",
        "rank": 2,
        "title": "طراح طرح کسب‌وکار",
        "title_en": "Business Plan Builder",
        "description": "طرح اجرایی، مشتری هدف، مدل درآمد و برنامه اعتبارسنجی",
        "price_env": "MINIAPP_BUSINESS_PLAN_STARS",
        "default_price": 0,
        "icon": "🚀",
        "prompt_key": "business_plan",
    },
    {
        "code": "miniapp_content_calendar",
        "rank": 3,
        "title": "تقویم محتوایی حرفه‌ای",
        "title_en": "Creator Content Calendar",
        "description": "تقویم ۱۴روزه محتوا، ایده ویدئو، کپشن و دعوت به اقدام",
        "price_env": "MINIAPP_CONTENT_CALENDAR_STARS",
        "default_price": 0,
        "icon": "🎬",
        "prompt_key": "content_calendar",
    },
    {
        "code": "miniapp_automation_blueprint",
        "rank": 4,
        "title": "طراح اتوماسیون کسب‌وکار",
        "title_en": "Automation Blueprint",
        "description": "نقشه گردش‌کار، گره‌های n8n، خطاگیری و شاخص سنجش",
        "price_env": "MINIAPP_AUTOMATION_BLUEPRINT_STARS",
        "default_price": 0,
        "icon": "⚙️",
        "prompt_key": "automation_blueprint",
    },
    {
        "code": "miniapp_market_brief",
        "rank": 5,
        "title": "گزارش‌ساز هوشمند بازار",
        "title_en": "Market Intelligence Brief",
        "description": "خلاصه داده‌محور دارایی‌های منتخب و سناریوهای ریسک",
        "price_env": "MINIAPP_MARKET_BRIEF_STARS",
        "default_price": 0,
        "icon": "📊",
        "prompt_key": "market_brief",
    },
]

FREE_CATEGORIES = [
    "بازار و رمزارز",
    "کسب‌وکار و فروش",
    "تولید محتوا",
    "بهره‌وری و مدیریت",
    "آموزش و یادگیری",
    "بازی و سرگرمی",
]


def paid_products_with_prices(prices: dict[str, int], purchased: set[str] | None = None):
    purchased = purchased or set()
    result = []
    for product in PAID_PRODUCTS:
        item = dict(product)
        item["price"] = max(0, int(prices.get(item["code"], 0) or 0))
        item["active"] = 1 <= item["price"] <= 25000
        item["purchased"] = item["code"] in purchased
        item.pop("price_env", None)
        item.pop("default_price", None)
        item.pop("prompt_key", None)
        result.append(item)
    return result


def verify_init_data(
    init_data: str,
    bot_token: str,
    *,
    now: int | None = None,
    max_age_seconds: int = 86400,
):
    """Verify Telegram Mini App initData using Telegram's HMAC-SHA-256 scheme."""
    if not init_data or not bot_token or len(init_data) > 8192:
        return None
    try:
        pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=True)
    except ValueError:
        return None
    data = {}
    for key, value in pairs:
        if key in data:
            return None
        data[key] = value
    received_hash = data.pop("hash", "")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", received_hash):
        return None
    auth_date_raw = data.get("auth_date", "")
    try:
        auth_date = int(auth_date_raw)
    except (TypeError, ValueError):
        return None
    current = int(time.time()) if now is None else int(now)
    if auth_date <= 0 or auth_date > current + 300 or current - auth_date > max_age_seconds:
        return None
    try:
        user = json.loads(data.get("user", ""))
    except (TypeError, json.JSONDecodeError):
        return None
    if not isinstance(user, dict) or not isinstance(user.get("id"), int) or user["id"] <= 0:
        return None
    check_string = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected = hmac.new(secret_key, check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash.lower()):
        return None
    return {
        "id": str(user["id"]),
        "first_name": str(user.get("first_name", ""))[:64],
        "username": str(user.get("username", ""))[:64],
        "language_code": str(user.get("language_code", ""))[:16],
    }


def build_paid_prompt(product_code: str, form: dict, market_data: list[dict] | None = None):
    """Return a source-grounded prompt for one purchased Mini App product."""
    product = next((x for x in PAID_PRODUCTS if x["code"] == product_code), None)
    if not product:
        raise ValueError("Unknown Mini App product")
    language = str(form.get("language", "fa")).lower()
    if language not in LANGUAGES:
        language = "fa"
    region = str(form.get("region", "")).strip()[:100]
    dialect = str(form.get("dialect", "")).strip()[:120]
    topic = str(form.get("topic", "")).strip()[:1600]
    audience = str(form.get("audience", "")).strip()[:500]
    offer = str(form.get("offer", "")).strip()[:400]
    platform = str(form.get("platform", "")).strip()[:80]
    budget = str(form.get("budget", "")).strip()[:100]

    common = (
        f"Write the complete result in {LANGUAGES[language]} (language code: {language}). "
        f"Target region/country: {region or 'not specified'}. "
        f"Local dialect or regional-language preference: {dialect or 'use the selected standard language'}. "
        "Respect local language, culture, units and legal constraints. "
        "Do not invent facts, customer testimonials, market statistics, legal approvals or guaranteed outcomes. "
        "Separate assumptions from verified inputs. Never promise income, investment profit or guaranteed growth. "
        "Use lawful, consent-based marketing only; do not recommend spam, scraping private data or unsolicited mass messaging. "
        "Be actionable, structured and specific. End with a short validation checklist."
    )

    if product["prompt_key"] == "ad_campaign":
        prompt = (
            "Create a localized campaign kit for a legitimate small business or digital product. "
            f"Offer/product: {topic}. Target audience: {audience}. Offer details: {offer}. "
            f"Platforms: {platform or 'Telegram, Instagram and website'}. "
            "Include: positioning, 5 headline options, 3 short ad variants, 1 longer post, CTA, "
            "local cultural/language adaptation notes, a seven-day test plan and consent-aware distribution guidance. "
            "Avoid false urgency and unsupported superiority claims."
        )
    elif product["prompt_key"] == "business_plan":
        prompt = (
            "Build a practical lean business plan. "
            f"Idea/product: {topic}. Customer: {audience}. Region: {region}. "
            f"Available budget: {budget or 'not specified'}. "
            "Include customer problem, value proposition, competitor-research checklist, revenue model, "
            "cost categories, minimum viable product, first 10 customer acquisition experiments, "
            "30-day milestones, key metrics, risks, licenses to investigate and stop/go criteria. "
            "Do not fabricate market size or guarantee profit."
        )
    elif product["prompt_key"] == "content_calendar":
        prompt = (
            "Create a 14-day content calendar for a creator or business. "
            f"Niche/product: {topic}. Audience: {audience}. Platforms: {platform or 'short video and social posts'}. "
            "For each day provide format, hook, outline, caption, CTA, visual concept and one metric to monitor. "
            "Do not reuse copyrighted scripts, lyrics or another creator's distinctive copy."
        )
    elif product["prompt_key"] == "automation_blueprint":
        prompt = (
            "Design an implementable workflow automation blueprint for a legitimate business. "
            f"Process to automate: {topic}. Team/users: {audience}. Existing tools: {platform}. "
            "Include trigger, nodes/steps, data schema, validation, retries, error queue, notifications, "
            "human approval checkpoints, privacy/security controls, estimated implementation stages and test cases. "
            "Never bypass user consent, platform protections or access controls."
        )
    else:
        safe_market_data = market_data or []
        prompt = (
            "Prepare an educational market intelligence brief using ONLY the live snapshot JSON below. "
            f"Assets/request: {topic or 'tracked crypto assets'}. "
            "Report observed prices, 24h change, quote volume, 1h trend and volume anomaly ratios. "
            "Explain uncertainty and alternative scenarios; do not issue personal buy/sell recommendations. "
            "Never invent order-book, on-chain or whale-identity data. Data JSON: "
            + json.dumps(safe_market_data, ensure_ascii=False)[:10000]
        )
    return common + "\n\n" + prompt
