import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import assistant_service as service


def signed_init_data(token, user_id=1234, now=None):
    now = int(time.time()) if now is None else int(now)
    values = {
        "auth_date": str(now),
        "query_id": "test-query",
        "user": json.dumps({"id": user_id, "first_name": "Test"}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={values[k]}" for k in sorted(values))
    key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    values["hash"] = hmac.new(key, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(values)


def test_assistant_home_and_health_routes():
    client = service.app.test_client()
    assert client.get("/").status_code == 200
    assert b"NOVA Doer" in client.get("/").data
    assert client.get("/health").json["ok"] is True


def test_status_requires_telegram_auth(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "BOT_TOKEN", "test-token")
    monkeypatch.setattr(service, "DB_PATH", str(tmp_path / "usage.sqlite3"))
    client = service.app.test_client()
    assert client.get("/api/assistant/status").status_code == 401
    response = client.get("/api/assistant/status", headers={
        "X-Telegram-Init-Data": signed_init_data("test-token")
    })
    assert response.status_code == 200
    assert response.json["remaining"] == service.FREE_MONTHLY_CREDITS


def test_text_job_uses_verified_user_and_returns_metered_result(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "BOT_TOKEN", "test-token")
    monkeypatch.setattr(service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(service, "DB_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr(service, "_respond", lambda items, task: "انجام شد")
    client = service.app.test_client()
    response = client.post("/api/assistant/jobs", headers={
        "X-Telegram-Init-Data": signed_init_data("test-token")
    }, data={"task": "do_it", "instructions": "لطفاً خلاصه و برنامه بساز"})
    assert response.status_code == 200
    assert response.json["result"] == "انجام شد"
    assert response.json["usage"]["remaining"] == service.FREE_MONTHLY_CREDITS - 1
    assert response.json["stored"] is False


def test_credit_is_refunded_after_provider_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "BOT_TOKEN", "test-token")
    monkeypatch.setattr(service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(service, "DB_PATH", str(tmp_path / "usage.sqlite3"))
    def fail(*args):
        raise RuntimeError("provider unavailable")
    monkeypatch.setattr(service, "_respond", fail)
    client = service.app.test_client()
    response = client.post("/api/assistant/jobs", headers={
        "X-Telegram-Init-Data": signed_init_data("test-token")
    }, data={"task": "summarize", "instructions": "لطفاً خلاصه کن"})
    assert response.status_code == 503
    assert response.json["credit_restored"] is True
    assert service._usage("1234")["remaining"] == service.FREE_MONTHLY_CREDITS


def test_unsupported_upload_type_is_rejected_without_using_credit(tmp_path, monkeypatch):
    from io import BytesIO
    monkeypatch.setattr(service, "BOT_TOKEN", "test-token")
    monkeypatch.setattr(service, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(service, "DB_PATH", str(tmp_path / "usage.sqlite3"))
    client = service.app.test_client()
    response = client.post("/api/assistant/jobs", headers={
        "X-Telegram-Init-Data": signed_init_data("test-token")
    }, data={"task": "do_it", "files": (BytesIO(b"bad"), "virus.exe", "application/octet-stream")})
    assert response.status_code == 400
    assert service._usage("1234")["used"] == 0


def test_free_monthly_limit_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "DB_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setattr(service, "FREE_MONTHLY_CREDITS", 1)
    assert service._reserve_credit("42") is True
    assert service._reserve_credit("42") is False
