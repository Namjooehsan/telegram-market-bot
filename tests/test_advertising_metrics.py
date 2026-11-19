from datetime import datetime
from advertising.center import AdvertisingCenter, TEHRAN


def _create_reporting_tables(center):
    with center.connect() as conn:
        conn.execute("""
            CREATE TABLE stars_orders (
                product_code TEXT, stars_amount INTEGER, status TEXT,
                paid_at TEXT, payload TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE donation_requests (
                asset TEXT, amount TEXT, status TEXT, reviewed_at TEXT, created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE payment_requests (
                asset TEXT, amount TEXT, status TEXT, reviewed_at TEXT, created_at TEXT
            )
        """)


def test_campaign_summary_counts_unique_starts_and_successful_deliveries(tmp_path):
    center = AdvertisingCenter(tmp_path / "ads.sqlite3")
    center.ensure_default_campaign()
    assert center.record_start_attribution("101", "ad_brand-launch")
    assert center.record_start_attribution("102", "ad_brand-launch")

    creative_id, status = center.create_daily_creative("brand-launch", "Approved campaign copy")
    assert status == "created"
    assert center.review_creative(creative_id, True)
    assert center.mark_published(creative_id, [
        {"destination": "@channel", "status": "sent", "message_id": "11"},
        {"destination": "@group", "status": "sent", "message_id": "12"},
    ])

    campaign = center.campaigns_summary()[0]
    assert campaign["attributed_users"] == 2
    assert campaign["successful_deliveries"] == 2
    assert campaign["published"] == 1


def test_revenue_report_distinguishes_campaign_starts_from_post_views(tmp_path):
    center = AdvertisingCenter(tmp_path / "ads.sqlite3")
    center.ensure_default_campaign()
    _create_reporting_tables(center)
    center.record_start_attribution("201", "ad_brand-launch")
    center.record_start_attribution("202", "ad_brand-launch")

    report = center.revenue_report(now=datetime.now(TEHRAN))
    assert report["campaign_starts"] == [
        {"campaign_id": "brand-launch", "user_count": 2}
    ]
    assert "campaign_starts" in report
