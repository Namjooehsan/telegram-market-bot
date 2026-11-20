import hashlib
import hmac
import json
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlencode
import time

import app as market_app
from miniapps.core import (
    FREE_APPS,
    FREE_CATEGORIES,
    PAID_PRODUCTS,
    build_paid_prompt,
    paid_products_with_prices,
    verify_init_data,
)


def signed_init_data(bot_token="test-bot-token", user_id=12345, now=None):
    now = int(time.time()) if now is None else int(now)
    values = {
        "auth_date": str(now),
        "query_id": "AAE-test-query",
        "user": json.dumps(
            {"id": user_id, "first_name": "Test", "username": "test_user", "language_code": "fa"},
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    }
    data_check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_free_apps_provide_two_tools_in_each_of_six_categories():
    counts = Counter(item["category"] for item in FREE_APPS)
    assert len(FREE_CATEGORIES) == 6
    assert len(FREE_APPS) == 12
    assert all(counts[category] == 2 for category in FREE_CATEGORIES)


def test_paid_product_catalogue_stays_disabled_until_prices_are_set():
    products = paid_products_with_prices({}, set())
    assert len(products) == 5
    assert [item["rank"] for item in products] == [1, 2, 3, 4, 5]
    assert all(item["active"] is False for item in products)
    assert all(item["price"] == 0 for item in products)


def test_paid_product_catalogue_enables_only_valid_stars_prices():
    products = paid_products_with_prices(
        {"miniapp_ad_campaign": 99, "miniapp_business_plan": 0, "miniapp_market_brief": 25001}
    )
    assert products[0]["active"] is True
    assert products[0]["price"] == 99
    assert products[1]["active"] is False
    assert products[4]["active"] is False


def test_telegram_init_data_signature_and_freshness():
    token = "test-bot-token"
    data = signed_init_data(token, now=1_800_000_000)
    verified = verify_init_data(data, token, now=1_800_000_010)
    assert verified["id"] == "12345"
    assert verified["language_code"] == "fa"
    assert verify_init_data(data, "another-token", now=1_800_000_010) is None
    assert verify_init_data(data, token, now=1_800_000_000 + 86401) is None


def test_telegram_init_data_rejects_tampering_duplicates_and_malformed_queries():
    token = "test-bot-token"
    valid = signed_init_data(token)
    tampered = valid.replace("test_user", "other_user")
    duplicate = valid + "&auth_date=1800000000"
    assert verify_init_data(tampered, token, now=1_800_000_000) is None
    assert verify_init_data(duplicate, token, now=1_800_000_000) is None
    assert verify_init_data("not-valid-query", token, now=1_800_000_000) is None


def test_paid_prompts_are_localized_and_do_not_promise_profit():
    prompt = build_paid_prompt(
        "miniapp_ad_campaign",
        {"topic": "local coffee shop", "region": "Istanbul, Türkiye", "dialect": "Istanbul Turkish", "language": "tr"},
    )
    assert "Türkçe" in prompt
    assert "Istanbul, Türkiye" in prompt
    assert "Istanbul Turkish" in prompt
    assert "consent-based" in prompt
    assert "Never promise income" in prompt


def test_unknown_paid_prompt_is_rejected():
    try:
        build_paid_prompt("miniapp_unknown", {"topic": "test"})
    except ValueError:
        pass
    else:
        raise AssertionError("Unknown product must not generate a prompt")


def test_miniapp_page_is_served_without_changing_health_route():
    client = market_app.app.test_client()
    page = client.get("/miniapp")
    health = client.get("/health")
    assert page.status_code == 200
    assert b"NOVA Hub" in page.data
    assert b"telegram-web-app.js" in page.data
    assert health.status_code == 200
    assert health.json["ok"] is True


def test_catalog_requires_a_verified_telegram_session(tmp_path, monkeypatch):
    token = "test-bot-token"
    monkeypatch.setattr(market_app, "TELEGRAM_TOKEN", token)
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(tmp_path / "miniapps.sqlite3"))
    client = market_app.app.test_client()
    assert client.get("/api/miniapp/catalog").status_code == 401
    response = client.get(
        "/api/miniapp/catalog",
        headers={"X-Telegram-Init-Data": signed_init_data(token)},
    )
    assert response.status_code == 200
    assert len(response.json["free_apps"]) == 12
    assert len(response.json["paid_products"]) == 5
    assert all(item["active"] is False for item in response.json["paid_products"])


def test_invoice_is_disabled_at_zero_price_and_without_ai_key(tmp_path, monkeypatch):
    token = "test-bot-token"
    monkeypatch.setattr(market_app, "TELEGRAM_TOKEN", token)
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(tmp_path / "miniapps.sqlite3"))
    monkeypatch.setattr(market_app, "MINIAPP_AD_CAMPAIGN_STARS", 0)
    monkeypatch.setattr(market_app, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(market_app, "OPENAI_AUTH_FAILED", False)
    client = market_app.app.test_client()
    headers = {"X-Telegram-Init-Data": signed_init_data(token)}
    disabled = client.post(
        "/api/miniapp/invoice", headers=headers,
        json={"product_code": "miniapp_ad_campaign"},
    )
    assert disabled.status_code == 409
    monkeypatch.setattr(market_app, "MINIAPP_AD_CAMPAIGN_STARS", 99)
    monkeypatch.setattr(market_app, "OPENAI_API_KEY", "")
    no_ai = client.post(
        "/api/miniapp/invoice", headers=headers,
        json={"product_code": "miniapp_ad_campaign"},
    )
    assert no_ai.status_code == 503


def test_invoice_link_uses_stars_without_provider_token(tmp_path, monkeypatch):
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(tmp_path / "invoice.sqlite3"))
    monkeypatch.setattr(market_app, "MINIAPP_AD_CAMPAIGN_STARS", 99)
    calls = []
    def fake_telegram(method, payload, timeout=15):
        calls.append((method, payload, timeout))
        return "https://t.me/$test-invoice"
    monkeypatch.setattr(market_app, "telegram_call", fake_telegram)
    result = market_app.create_miniapp_invoice_link("12345", "miniapp_ad_campaign")
    assert result["invoice_url"] == "https://t.me/$test-invoice"
    assert calls[0][0] == "createInvoiceLink"
    assert calls[0][1]["currency"] == "XTR"
    assert calls[0][1]["prices"][0]["amount"] == 99
    assert "provider_token" not in calls[0][1]


def test_miniapp_precheckout_reserves_order_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(tmp_path / "precheckout.sqlite3"))
    monkeypatch.setattr(market_app, "MINIAPP_AD_CAMPAIGN_STARS", 99)
    payload, _ = market_app.create_stars_order("12345", "miniapp_ad_campaign")
    query = {
        "id": "precheckout-1",
        "invoice_payload": payload,
        "from": {"id": 12345},
        "currency": "XTR",
        "total_amount": 99,
    }

    assert market_app.stars_pre_checkout_is_valid(query) is True
    assert market_app.stars_pre_checkout_is_valid(query) is True
    order = market_app.get_stars_order(payload)
    assert order["status"] == "checkout_approved"


def test_miniapp_precheckout_allows_only_one_active_checkout(tmp_path, monkeypatch):
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(tmp_path / "single-checkout.sqlite3"))
    monkeypatch.setattr(market_app, "MINIAPP_AD_CAMPAIGN_STARS", 99)
    first_payload, _ = market_app.create_stars_order("12345", "miniapp_ad_campaign")
    second_payload, _ = market_app.create_stars_order("12345", "miniapp_ad_campaign")

    def query(payload):
        return {
            "invoice_payload": payload,
            "from": {"id": 12345},
            "currency": "XTR",
            "total_amount": 99,
        }

    assert market_app.stars_pre_checkout_is_valid(query(first_payload)) is True
    assert market_app.stars_pre_checkout_is_valid(query(second_payload)) is False
    assert market_app.get_stars_order(first_payload)["status"] == "checkout_approved"
    assert market_app.get_stars_order(second_payload)["status"] == "pending"


def test_miniapp_precheckout_rejects_wrong_owner_and_amount(tmp_path, monkeypatch):
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(tmp_path / "invalid-precheckout.sqlite3"))
    monkeypatch.setattr(market_app, "MINIAPP_AD_CAMPAIGN_STARS", 99)
    payload, _ = market_app.create_stars_order("12345", "miniapp_ad_campaign")
    wrong_owner = {
        "invoice_payload": payload, "from": {"id": 54321},
        "currency": "XTR", "total_amount": 99,
    }
    wrong_amount = {
        "invoice_payload": payload, "from": {"id": 12345},
        "currency": "XTR", "total_amount": 1,
    }

    assert market_app.stars_pre_checkout_is_valid(wrong_owner) is False
    assert market_app.stars_pre_checkout_is_valid(wrong_amount) is False
    assert market_app.get_stars_order(payload)["status"] == "pending"


def test_successful_miniapp_stars_payment_creates_one_entitlement(tmp_path, monkeypatch):
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(tmp_path / "purchase.sqlite3"))
    monkeypatch.setattr(market_app, "MINIAPP_AD_CAMPAIGN_STARS", 99)
    order = market_app.create_stars_order("12345", "miniapp_ad_campaign")
    payload, _ = order
    payment = {
        "invoice_payload": payload,
        "currency": "XTR",
        "total_amount": 99,
        "telegram_payment_charge_id": "miniapp-charge-once",
    }
    assert market_app.complete_stars_payment("12345", payment) == "miniapp_ad_campaign"
    purchase = market_app.miniapp_purchase_for_user("12345", "miniapp_ad_campaign")
    assert purchase["status"] == "purchased"
    assert purchase["stars_amount"] == 99
    assert market_app.complete_stars_payment("12345", payment) is None


def test_miniapp_generation_requires_purchase(tmp_path, monkeypatch):
    token = "test-bot-token"
    monkeypatch.setattr(market_app, "TELEGRAM_TOKEN", token)
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(tmp_path / "generation.sqlite3"))
    client = market_app.app.test_client()
    response = client.post(
        "/api/miniapp/generate",
        headers={"X-Telegram-Init-Data": signed_init_data(token)},
        json={"product_code": "miniapp_business_plan", "topic": "A local delivery app"},
    )
    assert response.status_code == 403
