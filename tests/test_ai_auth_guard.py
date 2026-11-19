import os
from pathlib import Path
import sys
from types import SimpleNamespace

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "test-secret")
os.environ.setdefault("TELEGRAM_ADMIN_IDS", "12345")

import app


def test_openai_text_pauses_retries_after_unauthorized(monkeypatch):
    monkeypatch.setattr(app, "OPENAI_API_KEY", "invalid-test-key")
    monkeypatch.setattr(app, "OPENAI_AUTH_FAILED", False)
    monkeypatch.setattr(app, "consume_ai_quota", lambda: True)

    calls = []

    def unauthorized(*args, **kwargs):
        calls.append(True)
        error = requests.HTTPError("unauthorized")
        error.response = SimpleNamespace(status_code=401)
        raise error

    monkeypatch.setattr(app.requests, "post", unauthorized)

    assert app.openai_text("test prompt", "test system prompt") is None
    assert app.OPENAI_AUTH_FAILED is True
    assert app.openai_text("test prompt", "test system prompt") is None
    assert len(calls) == 1


def test_ai_status_reports_auth_failure_and_last_success(monkeypatch):
    monkeypatch.setattr(app, "OPENAI_API_KEY", "configured-test-key")
    monkeypatch.setattr(app, "OPENAI_AUTH_FAILED", True)
    monkeypatch.setattr(app, "OPENAI_LAST_SUCCESS", False)
    assert "401/403" in app.ai_status_text()

    monkeypatch.setattr(app, "OPENAI_AUTH_FAILED", False)
    monkeypatch.setattr(app, "OPENAI_LAST_SUCCESS", True)
    assert "تأیید شده" in app.ai_status_text()
