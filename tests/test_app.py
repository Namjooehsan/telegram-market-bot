import os
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("TELEGRAM_ADMIN_IDS", "12345")

from app import app


def test_health_endpoint():
    response = app.test_client().get("/health")
    assert response.status_code == 200
    assert response.json["ok"] is True


def test_webhook_rejects_invalid_secret():
    response = app.test_client().post("/telegram/webhook", json={})
    assert response.status_code == 401


def test_market_endpoint_rejects_non_usdt_symbol():
    response = app.test_client().get("/api/market/BTC")
    assert response.status_code == 400


def test_multi_destination_delivery_skips_successful_targets(monkeypatch):
    import app as market_app
    monkeypatch.setattr(market_app, "TELEGRAM_CHAT_IDS", ["@channel_a", "@channel_b"])
    calls = []

    def fake_call(method, payload):
        calls.append(payload["chat_id"])
        if payload["chat_id"] == "@channel_b":
            raise RuntimeError("not an admin")

    monkeypatch.setattr(market_app, "telegram_call", fake_call)
    result = market_app.send_telegram("test")
    assert result["sent"] == ["@channel_a"]
    assert len(result["failed"]) == 1

    calls.clear()
    retry = market_app.send_telegram("test", skip_chat_ids=result["sent"])
    assert calls == ["@channel_b"]
    assert retry["sent"] == []
    assert len(retry["failed"]) == 1
