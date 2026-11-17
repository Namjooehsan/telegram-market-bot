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
    assert response.status_code == 400


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
