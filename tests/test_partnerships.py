from partnerships.research import PartnerResearcher, KNOWN_PARTNER_CANDIDATES


def test_partner_directory_is_seeded_and_marks_candidates_not_verified(tmp_path):
    researcher = PartnerResearcher(tmp_path / "partners.sqlite3")
    leads = researcher.latest(50)
    assert len(leads) >= len(KNOWN_PARTNER_CANDIDATES)
    assert any(item["title"] == "Google AdMob" for item in leads)
    assert all(item["status"] == "directory_candidate" for item in leads)


def test_refresh_persists_deduplicates_and_records_errors(tmp_path, monkeypatch):
    researcher = PartnerResearcher(tmp_path / "partners.sqlite3")
    sample = [{
        "title": "Rewarded video publisher monetization",
        "url": "https://example.org/rewarded-video",
        "source": "Test RSS",
        "summary": "Publisher terms and payout details.",
    }]
    monkeypatch.setattr(researcher, "_fetch_rss", lambda query: sample)
    first = researcher.refresh(["query one", "query two"])
    second = researcher.refresh(["query one"])
    assert first["fetched"] == 1
    assert first["new_count"] == 1
    assert second["new_count"] == 0
    assert researcher.latest_run()["finished_at"]


def test_ai_review_only_updates_discovered_leads(tmp_path):
    researcher = PartnerResearcher(tmp_path / "partners.sqlite3")
    lead = next(x for x in researcher.latest(50) if x["title"] == "Google AdMob")
    assert researcher.save_ai_review(lead["lead_id"], 91, "rewarded video", "terms unknown", "draft only")
    reviewed = next(x for x in researcher.latest(50) if x["lead_id"] == lead["lead_id"])
    assert reviewed["priority_score"] == 91
    assert reviewed["status"] == "ai_reviewed"
    assert not researcher.save_ai_review(lead["lead_id"], 99, "changed", "x", "y")


def test_referral_attribution_is_unique_and_blocks_self_referrals(tmp_path):
    researcher = PartnerResearcher(tmp_path / "partners.sqlite3")
    assert researcher.record_referral("200", "100") is True
    assert researcher.record_referral("200", "300") is False
    assert researcher.record_referral("100", "100") is False
    stats = researcher.referral_summary()
    assert stats["total_users"] == 2
    assert stats["referrals_since"] == 1
    assert stats["top_inviters"][0]["inviter_id"] == "100"


def test_referral_link_without_inviter_does_not_create_referral(tmp_path):
    researcher = PartnerResearcher(tmp_path / "partners.sqlite3")
    assert researcher.record_referral("200") is False
    stats = researcher.referral_summary()
    assert stats["total_users"] == 1
    assert stats["referrals_since"] == 0
