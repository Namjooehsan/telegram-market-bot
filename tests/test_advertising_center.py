import sqlite3
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from advertising.center import AdvertisingCenter


def make_center(tmp_path, cap=1):
    center = AdvertisingCenter(tmp_path / "ads.sqlite3", max_daily_drafts=cap)
    with center.connect() as conn:
        conn.executescript("""
        CREATE TABLE stars_orders (
            payload TEXT PRIMARY KEY, user_id TEXT, product_code TEXT,
            stars_amount INTEGER, status TEXT, created_at TEXT, paid_at TEXT
        );
        CREATE TABLE donation_requests (
            donation_id TEXT PRIMARY KEY, user_id TEXT, asset TEXT, network TEXT,
            amount TEXT, status TEXT, created_at TEXT, reviewed_at TEXT
        );
        CREATE TABLE payment_requests (
            invoice_id TEXT PRIMARY KEY, user_id TEXT, asset TEXT, network TEXT,
            amount TEXT, status TEXT, created_at TEXT, reviewed_at TEXT
        );
        """)
    return center


def test_default_campaign_and_daily_cap(tmp_path):
    center = make_center(tmp_path, cap=1)
    campaign = center.ensure_default_campaign()
    first, state = center.create_daily_creative(campaign, "FA copy\nEN copy", now=datetime(2026, 11, 19, 9, tzinfo=timezone.utc))
    second, state2 = center.create_daily_creative(campaign, "second", now=datetime(2026, 11, 19, 10, tzinfo=timezone.utc))
    assert campaign == "brand-launch"
    assert first is not None and state == "created"
    assert second is None and state2 == "daily_cap_reached"


def test_approval_and_publish_idempotency(tmp_path):
    center = make_center(tmp_path)
    campaign = center.ensure_default_campaign()
    creative_id, _ = center.create_daily_creative(campaign, "approved copy")
    assert center.review_creative(creative_id, True)["status"] == "approved"
    assert center.review_creative(creative_id, True) is None
    assert center.mark_published(creative_id, [{"destination": "-1001", "status": "sent", "message_id": 123}])
    assert center.get_creative(creative_id)["status"] == "published"
    assert not center.mark_published(creative_id, [{"destination": "-1001", "status": "sent"}])


def test_attribution_and_paid_stars_reporting(tmp_path):
    center = make_center(tmp_path)
    center.ensure_default_campaign()
    assert center.record_start_attribution(77, "ad_brand-launch")
    assert not center.record_start_attribution(78, "ad_unknown-campaign")
    local_now = datetime.now(ZoneInfo("Asia/Tehran"))
    now = local_now.astimezone(timezone.utc).isoformat()
    with center.connect() as conn:
        conn.execute(
            "INSERT INTO stars_orders VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("payload-1", "77", "premium_30d", 120, "paid", now, now),
        )
    assert center.bind_order_to_user(77, "payload-1") == "brand-launch"
    report = center.revenue_report(local_now)
    assert report["stars"][0]["stars_total"] == 120
    assert report["attributed_stars"][0]["campaign_id"] == "brand-launch"
