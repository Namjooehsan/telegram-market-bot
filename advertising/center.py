"""Persistent campaign, creative, consent-aware delivery and revenue attribution."""
import json
import re
import sqlite3
import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

TEHRAN = ZoneInfo("Asia/Tehran")

LANGUAGES = {
    "ar": "العربية", "bn": "বাংলা", "cs": "Čeština", "da": "Dansk",
    "de": "Deutsch", "el": "Ελληνικά", "en": "English", "es": "Español",
    "fa": "فارسی", "fi": "Suomi", "fil": "Filipino", "fr": "Français",
    "gu": "ગુજરાતી", "he": "עברית", "hi": "हिन्दी", "hu": "Magyar",
    "id": "Bahasa Indonesia", "it": "Italiano", "ja": "日本語", "jv": "Basa Jawa",
    "ko": "한국어", "ms": "Bahasa Melayu", "mr": "मराठी", "nl": "Nederlands",
    "no": "Norsk", "pa": "ਪੰਜਾਬੀ", "pl": "Polski", "pt": "Português",
    "ro": "Română", "ru": "Русский", "sv": "Svenska", "sw": "Kiswahili",
    "ta": "தமிழ்", "te": "తెలుగు", "th": "ไทย", "tr": "Türkçe",
    "uk": "Українська", "ur": "اردو", "vi": "Tiếng Việt", "zh": "中文",
}

PLATFORMS = [
    {"id": "telegram", "name": "Telegram", "status": "available", "note": "فقط مقصدهای مجاز ثبت‌شده در تنظیمات ربات"},
    {"id": "instagram", "name": "Instagram", "status": "needs_connection", "note": "نیازمند حساب حرفه‌ای و مجوز رسمی انتشار"},
    {"id": "facebook", "name": "Facebook", "status": "needs_connection", "note": "نیازمند اتصال رسمی Meta"},
    {"id": "youtube", "name": "YouTube", "status": "needs_connection", "note": "نیازمند کانال و OAuth رسمی"},
    {"id": "tiktok", "name": "TikTok", "status": "needs_connection", "note": "نیازمند دسترسی مجاز API و بررسی کشور"},
    {"id": "x", "name": "X", "status": "needs_connection", "note": "نیازمند دسترسی رسمی API"},
    {"id": "linkedin", "name": "LinkedIn", "status": "needs_connection", "note": "نیازمند مجوز انتشار حساب/صفحه"},
    {"id": "email", "name": "Email", "status": "needs_connection", "note": "فقط فهرست مخاطبان دارای رضایت و لغو عضویت"},
    {"id": "google_ads", "name": "Google Ads", "status": "needs_connection", "note": "نیازمند حساب تبلیغاتی، بودجه و تأیید مستقل"},
    {"id": "seo", "name": "SEO / Website", "status": "planning", "note": "انتشار محتوای سایت؛ نیازمند وب‌سایت و Search Console"},
]

class AdvertisingCenter:
    def __init__(self, db_path, max_daily_drafts=1):
        self.db_path = str(db_path)
        self.max_daily_drafts = max(1, min(int(max_daily_drafts), 5))

    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def ensure_schema(self, conn=None):
        own = conn is None
        conn = conn or self.connect()
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS ad_campaigns (
            campaign_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            objective TEXT NOT NULL,
            audience TEXT NOT NULL,
            regions_json TEXT NOT NULL,
            languages_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ad_creatives (
            creative_id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            body TEXT NOT NULL,
            languages_json TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'telegram',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            reviewed_at TEXT,
            published_at TEXT,
            local_day TEXT NOT NULL,
            FOREIGN KEY(campaign_id) REFERENCES ad_campaigns(campaign_id)
        );
        CREATE TABLE IF NOT EXISTS ad_deliveries (
            delivery_id TEXT PRIMARY KEY,
            creative_id TEXT NOT NULL,
            destination TEXT NOT NULL,
            status TEXT NOT NULL,
            message_id TEXT,
            error TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ad_user_attribution (
            user_id TEXT PRIMARY KEY,
            first_campaign_id TEXT NOT NULL,
            last_campaign_id TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS ad_order_attribution (
            payload TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)
        if own:
            conn.commit()
            conn.close()

    def ensure_default_campaign(self):
        with self.connect() as conn:
            self.ensure_schema(conn)
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("""
                INSERT OR IGNORE INTO ad_campaigns
                (campaign_id, name, objective, audience, regions_json, languages_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
            """, (
                "brand-launch",
                "معرفی برند آزمایشگاه هوشمندی بازار",
                "جذب مخاطب علاقه‌مند به داده بازار و فرصت‌های کسب‌وکار از مسیر داوطلبانه و شفاف",
                "افرادی که خودشان برای دریافت تحلیل و محتوای آموزشی عضو می‌شوند",
                json.dumps(["global-opt-in"], ensure_ascii=False),
                json.dumps(["fa", "en"], ensure_ascii=False),
                now,
            ))
        return "brand-launch"

    def create_daily_creative(self, campaign_id, body, languages=("fa", "en"), now=None):
        now = now or datetime.now(timezone.utc)
        local_day = now.astimezone(TEHRAN).date().isoformat()
        with self.connect() as conn:
            self.ensure_schema(conn)
            campaign = conn.execute(
                "SELECT status FROM ad_campaigns WHERE campaign_id = ?", (campaign_id,)
            ).fetchone()
            if not campaign or campaign["status"] != "active":
                return None, "campaign_inactive"
            count = conn.execute(
                "SELECT COUNT(*) FROM ad_creatives WHERE campaign_id = ? AND local_day = ?",
                (campaign_id, local_day),
            ).fetchone()[0]
            if count >= self.max_daily_drafts:
                return None, "daily_cap_reached"
            creative_id = uuid.uuid4().hex[:12]
            conn.execute("""
                INSERT INTO ad_creatives
                (creative_id, campaign_id, body, languages_json, channel, status, created_at, local_day)
                VALUES (?, ?, ?, ?, 'telegram', 'pending', ?, ?)
            """, (
                creative_id, campaign_id, body,
                json.dumps(list(languages), ensure_ascii=False),
                now.astimezone(timezone.utc).isoformat(), local_day,
            ))
        return creative_id, "created"

    def get_creative(self, creative_id):
        with self.connect() as conn:
            self.ensure_schema(conn)
            row = conn.execute("SELECT * FROM ad_creatives WHERE creative_id = ?", (creative_id,)).fetchone()
        return dict(row) if row else None

    def latest_creative(self, campaign_id="brand-launch"):
        with self.connect() as conn:
            self.ensure_schema(conn)
            row = conn.execute(
                "SELECT * FROM ad_creatives WHERE campaign_id = ? ORDER BY created_at DESC LIMIT 1",
                (campaign_id,),
            ).fetchone()
        return dict(row) if row else None

    def review_creative(self, creative_id, approved):
        status = "approved" if approved else "rejected"
        with self.connect() as conn:
            self.ensure_schema(conn)
            cur = conn.execute("""
                UPDATE ad_creatives SET status = ?, reviewed_at = ?
                WHERE creative_id = ? AND status = 'pending'
            """, (status, datetime.now(timezone.utc).isoformat(), creative_id))
            if cur.rowcount != 1:
                row = conn.execute("SELECT * FROM ad_creatives WHERE creative_id = ?", (creative_id,)).fetchone()
                if not approved or not row or row["status"] != "approved":
                    return None
            else:
                row = conn.execute("SELECT * FROM ad_creatives WHERE creative_id = ?", (creative_id,)).fetchone()
        return dict(row) if row else None

    def delivered_destinations(self, creative_id):
        with self.connect() as conn:
            self.ensure_schema(conn)
            rows = conn.execute(
                "SELECT destination FROM ad_deliveries WHERE creative_id = ? AND status = 'sent'",
                (creative_id,),
            ).fetchall()
        return {row["destination"] for row in rows}

    def mark_published(self, creative_id, deliveries):
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            self.ensure_schema(conn)
            row = conn.execute(
                "SELECT status FROM ad_creatives WHERE creative_id = ?", (creative_id,)
            ).fetchone()
            # Only approved-but-not-yet-published creatives can add delivery rows.
            # A published creative is terminal and cannot be published twice.
            if not row or row["status"] != "approved":
                return False
            for item in deliveries:
                conn.execute("""
                    INSERT INTO ad_deliveries
                    (delivery_id, creative_id, destination, status, message_id, error, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    uuid.uuid4().hex, creative_id, str(item.get("destination", "")),
                    item.get("status", "unknown"), str(item.get("message_id") or ""),
                    str(item.get("error") or "")[:300], now,
                ))
            failed = any(x.get("status") != "sent" for x in deliveries)
            if deliveries and not failed:
                conn.execute(
                    "UPDATE ad_creatives SET status = 'published', published_at = ? WHERE creative_id = ?",
                    (now, creative_id),
                )
            return bool(deliveries) and not failed

    def record_start_attribution(self, user_id, start_parameter):
        match = re.fullmatch(r"ad_([a-zA-Z0-9-]{3,40})", str(start_parameter or "").strip())
        if not match:
            return False
        campaign_id = match.group(1)
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as conn:
            self.ensure_schema(conn)
            campaign = conn.execute(
                "SELECT status FROM ad_campaigns WHERE campaign_id = ?", (campaign_id,)
            ).fetchone()
            if not campaign or campaign["status"] != "active":
                return False
            conn.execute("""
                INSERT INTO ad_user_attribution
                (user_id, first_campaign_id, last_campaign_id, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                last_campaign_id = excluded.last_campaign_id,
                last_seen_at = excluded.last_seen_at
            """, (str(user_id), campaign_id, campaign_id, now, now))
        return True

    def bind_order_to_user(self, user_id, payload):
        with self.connect() as conn:
            self.ensure_schema(conn)
            row = conn.execute(
                "SELECT last_campaign_id FROM ad_user_attribution WHERE user_id = ?",
                (str(user_id),),
            ).fetchone()
            if not row:
                return None
            campaign_id = row["last_campaign_id"]
            conn.execute("""
                INSERT OR REPLACE INTO ad_order_attribution (payload, campaign_id, created_at)
                VALUES (?, ?, ?)
            """, (payload, campaign_id, datetime.now(timezone.utc).isoformat()))
        return campaign_id

    def campaigns_summary(self):
        with self.connect() as conn:
            self.ensure_schema(conn)
            rows = conn.execute("""
                SELECT c.campaign_id, c.name, c.status,
                       COUNT(DISTINCT x.creative_id) AS creatives,
                       SUM(CASE WHEN x.status = 'published' THEN 1 ELSE 0 END) AS published,
                       (SELECT COUNT(DISTINCT a.user_id) FROM ad_user_attribution a
                        WHERE a.last_campaign_id = c.campaign_id) AS attributed_users,
                       (SELECT COUNT(*) FROM ad_deliveries d
                        JOIN ad_creatives cx ON cx.creative_id = d.creative_id
                        WHERE cx.campaign_id = c.campaign_id AND d.status = 'sent') AS successful_deliveries
                FROM ad_campaigns c
                LEFT JOIN ad_creatives x ON x.campaign_id = c.campaign_id
                GROUP BY c.campaign_id ORDER BY c.created_at DESC LIMIT 10
            """).fetchall()
        return [dict(row) for row in rows]

    def revenue_report(self, now=None):
        now = now or datetime.now(TEHRAN)
        local_now = now.astimezone(TEHRAN)
        local_start = datetime.combine(local_now.date(), time.min, tzinfo=TEHRAN)
        local_end = local_start + timedelta(days=1)
        start_utc = local_start.astimezone(timezone.utc).isoformat()
        end_utc = local_end.astimezone(timezone.utc).isoformat()
        with self.connect() as conn:
            self.ensure_schema(conn)
            stars = conn.execute("""
                SELECT product_code, COUNT(*) AS order_count, SUM(stars_amount) AS stars_total
                FROM stars_orders
                WHERE status = 'paid' AND paid_at >= ? AND paid_at < ?
                GROUP BY product_code ORDER BY product_code
            """, (start_utc, end_utc)).fetchall()
            attributed = conn.execute("""
                SELECT a.campaign_id, COUNT(*) AS order_count, SUM(o.stars_amount) AS stars_total
                FROM stars_orders o JOIN ad_order_attribution a ON a.payload = o.payload
                WHERE o.status = 'paid' AND o.paid_at >= ? AND o.paid_at < ?
                GROUP BY a.campaign_id
            """, (start_utc, end_utc)).fetchall()
            donations = conn.execute("""
                SELECT asset, COUNT(*) AS item_count, SUM(CAST(amount AS REAL)) AS amount_total
                FROM donation_requests
                WHERE status = 'approved' AND reviewed_at >= ? AND reviewed_at < ?
                GROUP BY asset ORDER BY asset
            """, (start_utc, end_utc)).fetchall()
            external = conn.execute("""
                SELECT asset, COUNT(*) AS item_count, SUM(CAST(amount AS REAL)) AS amount_total
                FROM payment_requests
                WHERE status = 'approved' AND reviewed_at >= ? AND reviewed_at < ?
                GROUP BY asset ORDER BY asset
            """, (start_utc, end_utc)).fetchall()
            submitted = conn.execute("""
                SELECT COUNT(*) FROM donation_requests
                WHERE status = 'submitted' AND created_at >= ? AND created_at < ?
            """, (start_utc, end_utc)).fetchone()[0]
            campaign_starts = conn.execute("""
                SELECT last_campaign_id AS campaign_id, COUNT(DISTINCT user_id) AS user_count
                FROM ad_user_attribution
                WHERE last_seen_at >= ? AND last_seen_at < ?
                GROUP BY last_campaign_id ORDER BY user_count DESC
            """, (start_utc, end_utc)).fetchall()
        return {
            "date": local_now.date().isoformat(),
            "stars": [dict(x) for x in stars],
            "attributed_stars": [dict(x) for x in attributed],
            "approved_donations": [dict(x) for x in donations],
            "approved_external": [dict(x) for x in external],
            "campaign_starts": [dict(x) for x in campaign_starts],
            "unverified_submissions": int(submitted),
        }

    def format_revenue_report(self, now=None):
        report = self.revenue_report(now)
        lines = [f"گزارش وجوه ثبت‌شده و تأییدشده | {report['date']} | منطقه زمانی تهران"]
        lines.append("Telegram Stars (پرداخت موفق تلگرام):")
        if report["stars"]:
            for row in report["stars"]:
                lines.append(f"- {row['product_code']}: {row['order_count']} سفارش، {row['stars_total'] or 0} Stars")
        else:
            lines.append("- امروز پرداخت موفقی ثبت نشده است.")
        lines.append("کاربران یکتای ورودی از لینک کمپین (شروع ربات، نه بازدید پست):")
        if report["campaign_starts"]:
            for row in report["campaign_starts"]:
                lines.append(f"- {row['campaign_id']}: {row['user_count']} کاربر یکتا")
        else:
            lines.append("- امروز ورودی منتسب‌شده‌ای ثبت نشده است.")
        lines.append("فروش منتسب به لینک کمپین:")
        if report["attributed_stars"]:
            for row in report["attributed_stars"]:
                lines.append(f"- {row['campaign_id']}: {row['order_count']} سفارش، {row['stars_total'] or 0} Stars")
        else:
            lines.append("- فروش منتسب‌شده‌ای ثبت نشده است.")
        lines.append("حمایت رمزارزی تأییدشده توسط مدیر:")
        if report["approved_donations"]:
            for row in report["approved_donations"]:
                lines.append(f"- {row['asset']}: {row['item_count']} مورد، {row['amount_total'] or 0:g}")
        else:
            lines.append("- مورد تأییدشده‌ای ثبت نشده است.")
        lines.append("پرداخت خارجیِ تأییدشده توسط مدیر:")
        if report["approved_external"]:
            for row in report["approved_external"]:
                lines.append(f"- {row['asset']}: {row['item_count']} مورد، {row['amount_total'] or 0:g}")
        else:
            lines.append("- مورد تأییدشده‌ای ثبت نشده است.")
        lines.append(f"رسیدهای رمزارزی بررسی‌نشده: {report['unverified_submissions']} (در درآمد منظور نشده)")
        lines.append("توجه: Stars معادل وجه نقد قابل‌برداشت نیست؛ تبدیل و تسویه به شرایط رسمی تلگرام وابسته است. این گزارش ناخالص است و هزینه تبلیغات/کارمزد/مالیات را کسر نمی‌کند.")
        return "\n".join(lines)

    @staticmethod
    def campaign_link(bot_username, campaign_id="brand-launch"):
        username = str(bot_username or "").strip().lstrip("@")
        return f"https://t.me/{username}?start=ad_{campaign_id}" if username else ""
