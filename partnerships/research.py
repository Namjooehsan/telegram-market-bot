"""Research and referral utilities for NOVA Partnerships.

Discovery is read-only. The module never signs agreements, sends outreach,
or treats an advertised CPM/eCPM as guaranteed publisher revenue.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests

PARTNER_SEARCHES = [
    "rewarded video advertising network publisher monetization eCPM 2026",
    "in-app rewarded ads publisher network minimum payout revenue share",
    "Telegram Mini App monetization advertising network publisher",
    "affiliate network partner program SaaS recurring commission publisher",
    "creator sponsorship marketplace brand partnership application",
    "video monetization network publisher requirements payout countries",
    "performance marketing affiliate program publisher rates terms",
]

# Candidate discovery directory, not endorsements or claims of current eligibility.
KNOWN_PARTNER_CANDIDATES = [
    {"name": "Google Ad Manager / AdSense", "type": "display and video ads", "url": "https://ads.google.com/", "priority": "high"},
    {"name": "Google AdMob", "type": "in-app rewarded video", "url": "https://admob.google.com/", "priority": "high"},
    {"name": "Unity Ads", "type": "in-app rewarded video", "url": "https://unity.com/products/grow/monetization", "priority": "high"},
    {"name": "AppLovin", "type": "in-app monetization", "url": "https://www.applovin.com/", "priority": "high"},
    {"name": "Digital Turbine", "type": "mobile advertising", "url": "https://www.digitalturbine.com/", "priority": "medium"},
    {"name": "InMobi", "type": "mobile advertising", "url": "https://www.inmobi.com/", "priority": "medium"},
    {"name": "ironSource / LevelPlay", "type": "in-app mediation", "url": "https://www.is.com/", "priority": "high"},
    {"name": "Amazon Associates", "type": "affiliate", "url": "https://affiliate-program.amazon.com/", "priority": "medium"},
    {"name": "Awin", "type": "affiliate network", "url": "https://www.awin.com/", "priority": "medium"},
    {"name": "CJ Affiliate", "type": "affiliate network", "url": "https://www.cj.com/", "priority": "medium"},
    {"name": "Impact", "type": "partnership management", "url": "https://impact.com/", "priority": "medium"},
    {"name": "PartnerStack", "type": "B2B SaaS affiliate", "url": "https://partnerstack.com/", "priority": "medium"},
    {"name": "Raptive", "type": "publisher advertising", "url": "https://raptive.com/", "priority": "medium"},
    {"name": "Mediavine", "type": "publisher advertising", "url": "https://www.mediavine.com/", "priority": "medium"},
    {"name": "Monetag", "type": "web advertising", "url": "https://monetag.com/", "priority": "medium"},
    {"name": "Adsterra", "type": "web advertising", "url": "https://adsterra.com/", "priority": "medium"},
]

def _now():
    return datetime.now(timezone.utc).isoformat()

class PartnerResearcher:
    def __init__(self, db_path, timeout=12):
        self.db_path = str(db_path)
        self.timeout = timeout
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS partner_leads (
                lead_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                source TEXT NOT NULL,
                summary TEXT NOT NULL,
                partner_type TEXT NOT NULL DEFAULT 'unknown',
                priority_score INTEGER NOT NULL DEFAULT 0,
                ai_assessment TEXT,
                outreach_draft TEXT,
                status TEXT NOT NULL DEFAULT 'discovered',
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                UNIQUE(url)
            );
            CREATE TABLE IF NOT EXISTS partner_research_runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                fetched INTEGER NOT NULL DEFAULT 0,
                new_count INTEGER NOT NULL DEFAULT 0,
                errors_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS referral_users (
                user_id TEXT PRIMARY KEY,
                inviter_id TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                consented_at TEXT,
                blocked_at TEXT
            );
            CREATE TABLE IF NOT EXISTS referral_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                inviter_id TEXT NOT NULL,
                invitee_id TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL DEFAULT 'telegram_start',
                created_at TEXT NOT NULL
            );
            """)
            for item in KNOWN_PARTNER_CANDIDATES:
                lead_id = hashlib.sha256(item["url"].encode()).hexdigest()[:20]
                conn.execute("""
                    INSERT OR IGNORE INTO partner_leads
                    (lead_id,title,url,source,summary,partner_type,priority_score,status,first_seen_at,last_seen_at)
                    VALUES (?,?,?,?,?,?,?,'directory_candidate',?,?)
                """, (lead_id,item["name"],item["url"],"curated_candidate_directory",
                      "Candidate only. Verify publisher eligibility, country availability, policy, payment terms and actual net eCPM before applying.",
                      item["type"], 50 if item["priority"]=="high" else 30,_now(),_now()))

    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=15000")
        return conn

    def _fetch_rss(self, query):
        url = "https://news.google.com/rss/search?q=" + quote_plus(query) + "&hl=en-US&gl=US&ceid=US:en"
        response = requests.get(url, timeout=self.timeout, headers={"User-Agent":"NOVA-Partnership-Research/1.0"})
        response.raise_for_status()
        root = ET.fromstring(response.content)
        items = []
        for node in root.findall(".//item")[:12]:
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            summary = re.sub(r"<[^>]+>", " ", node.findtext("description") or "")
            summary = re.sub(r"\s+", " ", summary).strip()[:1200]
            if title and link.startswith("http"):
                items.append({"title":title[:300],"url":link,"source":"Google News RSS","summary":summary})
        return items

    def refresh(self, queries=None):
        queries = queries or PARTNER_SEARCHES
        started = _now()
        fetched, errors, new_count = [], [], 0
        with self.connect() as conn:
            cursor = conn.execute("INSERT INTO partner_research_runs(started_at) VALUES (?)", (started,))
            run_id = cursor.lastrowid
        for query in queries:
            try:
                fetched.extend(self._fetch_rss(query))
            except Exception as exc:
                errors.append({"query":query,"error":str(exc)[:220]})
        seen = set()
        with self.connect() as conn:
            for item in fetched:
                if item["url"] in seen:
                    continue
                seen.add(item["url"])
                lead_id = hashlib.sha256(item["url"].encode()).hexdigest()[:20]
                cur = conn.execute("""
                    INSERT OR IGNORE INTO partner_leads
                    (lead_id,title,url,source,summary,partner_type,status,first_seen_at,last_seen_at)
                    VALUES (?,?,?,?,?,'research_signal','discovered',?,?)
                """, (lead_id,item["title"],item["url"],item["source"],item["summary"],_now(),_now()))
                new_count += cur.rowcount
                conn.execute("UPDATE partner_leads SET last_seen_at=? WHERE url=?",(_now(),item["url"]))
            conn.execute("""
                UPDATE partner_research_runs SET finished_at=?,fetched=?,new_count=?,errors_json=?
                WHERE run_id=?
            """,(_now(),len(seen),new_count,json.dumps(errors,ensure_ascii=False),run_id))
        return {"run_id":run_id,"fetched":len(seen),"new_count":new_count,"errors":errors}

    def latest(self, limit=25):
        with self.connect() as conn:
            rows=conn.execute("""
                SELECT lead_id,title,url,source,summary,partner_type,priority_score,
                       ai_assessment,outreach_draft,status,last_seen_at
                FROM partner_leads ORDER BY priority_score DESC,last_seen_at DESC LIMIT ?
            """,(max(1,min(100,int(limit))),)).fetchall()
        return [dict(row) for row in rows]

    def save_ai_review(self, lead_id, score, partner_type, assessment, outreach):
        score=max(0,min(100,int(score)))
        with self.connect() as conn:
            cur=conn.execute("""
                UPDATE partner_leads SET priority_score=?,partner_type=?,ai_assessment=?,
                outreach_draft=?,status='ai_reviewed',last_seen_at=?
                WHERE lead_id=? AND status NOT IN ('rejected','applied','approved')
            """,(score,str(partner_type)[:80],str(assessment)[:2500],str(outreach)[:3500],_now(),lead_id))
            return cur.rowcount==1

    def record_referral(self, user_id, inviter_id=None, consented=False):
        uid=str(user_id)
        inviter=str(inviter_id) if inviter_id and str(inviter_id).isdigit() else None
        if inviter==uid: inviter=None
        now=_now()
        with self.connect() as conn:
            prior=conn.execute("SELECT inviter_id FROM referral_users WHERE user_id=?",(uid,)).fetchone()
            conn.execute("""
                INSERT INTO referral_users(user_id,inviter_id,first_seen_at,last_seen_at,consented_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET last_seen_at=excluded.last_seen_at,
                consented_at=COALESCE(referral_users.consented_at,excluded.consented_at)
            """,(uid,inviter,now,now,now if consented else None))
            if inviter and not prior:
                conn.execute("""
                    INSERT OR IGNORE INTO referral_events(inviter_id,invitee_id,created_at)
                    VALUES(?,?,?)
                """,(inviter,uid,now))
        return bool(inviter and not prior)

    def referral_summary(self, since=None):
        since=since or datetime.now(timezone.utc).date().isoformat()
        with self.connect() as conn:
            total=conn.execute("SELECT COUNT(*) FROM referral_users").fetchone()[0]
            new_today=conn.execute("SELECT COUNT(*) FROM referral_users WHERE first_seen_at >= ?",(since,)).fetchone()[0]
            events=conn.execute("SELECT COUNT(*) FROM referral_events WHERE created_at >= ?",(since,)).fetchone()[0]
            top=conn.execute("""
                SELECT inviter_id,COUNT(*) AS invites FROM referral_events
                GROUP BY inviter_id ORDER BY invites DESC LIMIT 5
            """).fetchall()
        return {"total_users":total,"new_users_since":new_today,"referrals_since":events,
                "top_inviters":[dict(x) for x in top]}

    def latest_run(self):
        with self.connect() as conn:
            row=conn.execute("SELECT * FROM partner_research_runs ORDER BY run_id DESC LIMIT 1").fetchone()
        return dict(row) if row else None
