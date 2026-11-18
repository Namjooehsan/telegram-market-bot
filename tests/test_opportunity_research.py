from opportunity_research import (
    OpportunityResearcher,
    classify_market,
    format_market_universe,
    get_market_universe,
)


def test_market_universe_is_broad_and_has_compliance_limits():
    markets = get_market_universe()
    assert len(markets) >= 30
    assert any("رمزارز" in item["name"] for item in markets)
    assert any("کشاورزی" in item["name"] for item in markets)
    assert "فعالیت‌های ممنوع" in format_market_universe(markets)


def test_market_classification_finds_ai_automation():
    market = classify_market("AI automation workflow for small business demand")
    assert market["id"] == "ai-automation"


def test_refresh_persists_and_deduplicates_public_signals(tmp_path, monkeypatch):
    researcher = OpportunityResearcher(tmp_path / "research.sqlite3")
    sample = [{
        "title": "AI workflow automation demand is rising",
        "url": "https://example.com/ai-workflow",
        "source": "Test Source",
        "published_at": "2026-11-18T10:00:00+00:00",
        "summary": "Small businesses are adopting automation tools.",
        "points": 10,
    }]
    monkeypatch.setattr(researcher, "_fetch_google_news", lambda query: sample)
    monkeypatch.setattr(researcher, "_fetch_hacker_news", lambda query: [])
    first = researcher.refresh()
    second = researcher.refresh()
    assert first["fetched"] > 0
    assert first["new_count"] == 1
    assert second["new_count"] == 0
    assert len(researcher.latest_signals(5)) == 1


def test_ai_ideas_are_persisted_and_deduplicated(tmp_path):
    researcher = OpportunityResearcher(tmp_path / "research.sqlite3")
    idea_text = "ایده آزمایشی: ابزار خودکارسازی پاسخ مشتری برای فروشگاه‌های کوچک"
    sources = ["https://example.com/source"]
    assert researcher.save_ai_ideas(idea_text, sources) is True
    assert researcher.save_ai_ideas(idea_text, sources) is False
    saved = researcher.latest_ai_ideas(2)
    assert len(saved) == 1
    assert saved[0]["content"] == idea_text
    assert saved[0]["source_urls"] == sources
