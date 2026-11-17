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
