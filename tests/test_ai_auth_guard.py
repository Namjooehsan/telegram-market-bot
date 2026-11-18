from types import SimpleNamespace

import requests

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
