import os
import sys
from pathlib import Path

# Ensure the repository root is importable in GitHub Actions and local pytest runs.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("TELEGRAM_ADMIN_IDS", "12345")

import app as market_app


def test_health_endpoint():
    response = market_app.app.test_client().get("/health")
    assert response.status_code == 200
    assert response.json["ok"] is True


def test_webhook_rejects_invalid_secret():
    response = market_app.app.test_client().post("/telegram/webhook", json={})
    assert response.status_code == 401


def test_market_endpoint_rejects_non_usdt_symbol():
    response = market_app.app.test_client().get("/api/market/BTC")
    assert response.status_code == 400


def test_market_endpoint_rejects_invalid_symbol_characters():
    response = market_app.app.test_client().get("/api/market/BTC%2FUSDT")
    assert response.status_code == 404


def test_send_telegram_delivers_to_all_configured_channels(monkeypatch):
    sent = []
    monkeypatch.setattr(market_app, "TELEGRAM_CHAT_IDS", ["@BTCanalizor", "@thebesttimetobuybtc"])
    monkeypatch.setattr(
        market_app, "telegram_call",
        lambda method, payload: sent.append((method, payload["chat_id"], payload["text"])) or {"ok": True}
    )

    result = market_app.send_telegram("test report")

    assert len(result) == 2
    assert [item[1] for item in sent] == ["@BTCanalizor", "@thebesttimetobuybtc"]
    assert all(item[2] == "test report" for item in sent)


def test_draft_command_requires_valid_webhook_secret(monkeypatch):
    client = market_app.app.test_client()
    sent = []
    monkeypatch.setattr(market_app, "create_draft", lambda: ("draft-1", "sample report"))
    monkeypatch.setattr(
        market_app, "telegram_call",
        lambda method, payload: sent.append(payload) or {"message_id": 1}
    )

    response = client.post(
        "/telegram/webhook",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-secret"},
        json={
            "message": {
                "from": {"id": 12345},
                "chat": {"id": 12345},
                "text": "/draft"
            }
        }
    )

    assert response.status_code == 200
    assert len(sent) == 1
    assert "sample report" in sent[0]["text"]
    assert sent[0]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "approve:draft-1"


def test_drafts_persist_in_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "drafts.sqlite3"
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(db_path))
    monkeypatch.setattr(market_app, "make_report", lambda: ("persistent report", [{"symbol": "BTCUSDT"}]))

    draft_id, body = market_app.create_draft()
    stored = market_app.get_draft(draft_id)

    assert body == "persistent report"
    assert stored["text"] == "persistent report"
    assert stored["data"] == [{"symbol": "BTCUSDT"}]
    assert stored["status"] == "pending"

    market_app.delete_draft(draft_id)
    assert market_app.get_draft(draft_id) is None



def test_openai_is_optional_without_api_key(monkeypatch):
    monkeypatch.setattr(market_app, "OPENAI_API_KEY", "")
    assert market_app.openai_text("hello", "system") is None


def test_payment_setup_is_disabled_by_default(monkeypatch):
    monkeypatch.setattr(market_app, "PAYMENTS_ENABLED", False)
    monkeypatch.setattr(market_app, "PAYMENT_ASSET", "BTC")
    monkeypatch.setattr(market_app, "PAYMENT_NETWORK", "BTC")
    monkeypatch.setattr(market_app, "PAYMENT_RECEIVE_ADDRESS", "public-address")
    monkeypatch.setattr(market_app, "PREMIUM_PRICE", "10")
    assert market_app.payment_setup_ready() is False


def test_manual_payment_approval_grants_premium(tmp_path, monkeypatch):
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(tmp_path / "bot.sqlite3"))
    monkeypatch.setattr(market_app, "PAYMENTS_ENABLED", True)
    monkeypatch.setattr(market_app, "PAYMENT_ASSET", "USDT")
    monkeypatch.setattr(market_app, "PAYMENT_NETWORK", "TEST-NET")
    monkeypatch.setattr(market_app, "PAYMENT_RECEIVE_ADDRESS", "test-receive-address")
    monkeypatch.setattr(market_app, "PREMIUM_PRICE", "5")
    monkeypatch.setattr(market_app, "PREMIUM_DURATION_DAYS", 30)
    monkeypatch.setattr(market_app, "ADMIN_IDS", {"12345"})

    invoice_id = market_app.create_payment_invoice("67890")
    assert invoice_id
    assert market_app.submit_payment(invoice_id, "67890", "a" * 64)
    approved = market_app.approve_payment(invoice_id)

    assert approved is not None
    assert approved[0] == "67890"
    assert market_app.is_premium_user("67890")


def test_payment_invoice_cannot_be_submitted_by_another_user(tmp_path, monkeypatch):
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(tmp_path / "bot.sqlite3"))
    monkeypatch.setattr(market_app, "PAYMENTS_ENABLED", True)
    monkeypatch.setattr(market_app, "PAYMENT_ASSET", "BTC")
    monkeypatch.setattr(market_app, "PAYMENT_NETWORK", "BTC")
    monkeypatch.setattr(market_app, "PAYMENT_RECEIVE_ADDRESS", "test-receive-address")
    monkeypatch.setattr(market_app, "PREMIUM_PRICE", "0.001")
    invoice_id = market_app.create_payment_invoice("67890")
    assert market_app.submit_payment(invoice_id, "99999", "b" * 64) is False


def test_ai_daily_quota_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(tmp_path / "bot.sqlite3"))
    monkeypatch.setattr(market_app, "AI_DAILY_REQUEST_LIMIT", 2)
    assert market_app.consume_ai_quota() is True
    assert market_app.consume_ai_quota() is True
    assert market_app.consume_ai_quota() is False


def test_stars_order_is_bound_to_user_and_exact_amount(tmp_path, monkeypatch):
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(tmp_path / "stars.sqlite3"))
    monkeypatch.setattr(market_app, "STARS_PREMIUM_PRICE", 77)
    order = market_app.create_stars_order("67890", "premium_30d")
    assert order
    payload, product = order
    assert product["price"] == 77
    valid = {
        "invoice_payload": payload,
        "from": {"id": 67890},
        "currency": "XTR",
        "total_amount": 77,
    }
    assert market_app.stars_pre_checkout_is_valid(valid) is True
    assert market_app.stars_pre_checkout_is_valid({**valid, "from": {"id": 99999}}) is False
    assert market_app.stars_pre_checkout_is_valid({**valid, "total_amount": 76}) is False


def test_successful_stars_payment_grants_premium_once(tmp_path, monkeypatch):
    monkeypatch.setattr(market_app, "DRAFT_DB_PATH", str(tmp_path / "stars.sqlite3"))
    monkeypatch.setattr(market_app, "STARS_PREMIUM_PRICE", 77)
    monkeypatch.setattr(market_app, "PREMIUM_DURATION_DAYS", 30)
    order = market_app.create_stars_order("67890", "premium_30d")
    payload, _ = order
    payment = {
        "invoice_payload": payload,
        "currency": "XTR",
        "total_amount": 77,
        "telegram_payment_charge_id": "charge-test-0001",
    }
    assert market_app.complete_stars_payment("67890", payment) == "premium_30d"
    assert market_app.is_premium_user("67890") is True
    assert market_app.complete_stars_payment("67890", payment) is None


def test_zero_stars_price_keeps_product_disabled(monkeypatch):
    monkeypatch.setattr(market_app, "STARS_IDEA_PRICE", 0)
    assert market_app.stars_product("business_idea") is None


def test_support_wallets_show_xrp_destination_tag(monkeypatch):
    monkeypatch.setattr(market_app, "SUPPORT_XRP_ADDRESS", "rTestAddress")
    monkeypatch.setattr(market_app, "SUPPORT_XRP_TAG", "123456")
    support_text = market_app.support_wallet_text()
    assert "rTestAddress" in support_text
    assert "123456" in support_text
    assert "حمایت اختیاری" in support_text


def test_fun_pack_requires_configured_stars_price(monkeypatch):
    monkeypatch.setattr(market_app, "STARS_FUNPACK_PRICE", 0)
    assert market_app.stars_product("fun_pack") is None
    monkeypatch.setattr(market_app, "STARS_FUNPACK_PRICE", 45)
    product = market_app.stars_product("fun_pack")
    assert product["price"] == 45
