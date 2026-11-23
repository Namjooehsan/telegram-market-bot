import concurrent.futures
import hashlib
import html
import json
import logging
import math
import re
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

log = logging.getLogger("opportunity-research")
MARKET_FILE = Path(__file__).with_name("market_universe.json")

SEARCH_QUERIES = [
    "AI automation small business demand",
    "AI integration AI agents business workflow adoption",
    "AI video generation editing UGC advertising services demand",
    "AI data center infrastructure semiconductors networking cooling power demand",
    "ecommerce management retail logistics trends",
    "micro SaaS productivity software startup",
    "creator economy paid memberships digital products",
    "cybersecurity small business privacy backup fraud prevention",
    "post quantum cryptography quantum safe security enterprise adoption",
    "robotics industrial automation warehouse humanoid robotics investment",
    "renewable energy battery storage grid infrastructure data center power",
    "critical minerals copper lithium rare earths supply chain",
    "food agriculture supply chain technology",
    "crypto payments blockchain institutional adoption regulation",
    "tokenized real world assets RWA tokenized funds equities adoption",
    "stablecoin payment rails cross border settlement merchant payments",
    "decentralized AI compute DePIN GPU inference marketplace",
    "Bitcoin ecosystem BTCFi layer 2 institutional custody",
    "gold oil forex macroeconomic markets business",
    "real estate property management services",
    "pet services home repair local businesses",
]
HN_QUERIES = [
    "AI automation agents",
    "AI video tools",
    "micro SaaS",
    "creator economy",
    "ecommerce",
    "stablecoin payments",
    "tokenized real world assets",
    "decentralized compute DePIN",
    "post quantum cryptography",
    "robotics automation",
]
DEMAND_TERMS = (
    "demand", "growth", "adoption", "search", "hiring", "jobs", "business",
    "market", "trend", "launch", "funding", "revenue", "automation",
    "freelance", "subscription", "تقاضا", "رشد", "کسب‌وکار", "بازار", "فروش",
)
BLOCKED_PHRASES = (
    "sell illegal drugs", "weapon sales", "explosive sales", "counterfeit goods",
    "stolen credentials", "phishing kit", "ransomware service", "fake reviews",
    "buy stolen data", "sanctions evasion", "casino affiliate", "sports betting",
    "pirated software",
)
BENCHMARK_SOURCES = [
    ("Upwork In-Demand Skills 2026", "https://www.upwork.com/press/releases/upworks-in-demand-skills-2026-demand-for-top-ai-skills-more-than-doubles-as-ai-is-embedded-into-everyday-work"),
    ("Fiverr Business Trends 2026", "https://www.fiverr.com/resources/guides/reports/business-trends-index-june-2026/"),
]


def get_market_universe():
    try:
        return json.loads(MARKET_FILE.read_text(encoding="utf-8")).get("markets", [])
    except (OSError, ValueError, TypeError):
        log.exception("Could not read market_universe.json")
        return []


def _clean(value, limit=500):
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()[:limit]


def _parse_date(value):
    parsed = None
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(str(value))
            except (TypeError, ValueError, OverflowError):
                parsed = None
    if parsed is None:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def classify_market(text, markets=None):
    text = str(text or "").casefold()
    markets = markets if markets is not None else get_market_universe()
    best, best_score = None, 0
    for market in markets:
        score = sum(1 for word in market.get("keywords", []) if str(word).casefold() in text)
        if score > best_score:
            best, best_score = market, score
    return best or next((m for m in markets if m.get("id") == "business-services"), None)


def format_market_universe(markets=None):
    markets = markets if markets is not None else get_market_universe()
    grouped = {}
    for item in markets:
        grouped.setdefault(item.get("segment", "سایر"), []).append(item.get("name", ""))
    lines = [
        "نقشه بازارهای مجاز برای رصد و ایده‌یابی",
        "فهرست پژوهشی/کسب‌وکاری است؛ نه به معنی قیمت زنده برای همه دارایی‌ها.",
        "",
    ]
    for segment in sorted(grouped):
        names = [name for name in grouped[segment] if name]
        if names:
            lines.extend([segment + ":", "، ".join(names), ""])
    lines.extend([
        "جستجوی زنده: /marketsearch عبارت",
        "برخی حوزه‌ها نیازمند مجوزند؛ فعالیت‌های ممنوع و غیرقانونی یا فریبکارانه پیشنهاد نمی‌شوند.",
    ])
    return "\n".join(lines)


class OpportunityResearcher:
    """Collect public demand signals and persist ranked, source-linked results."""

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.markets = get_market_universe()
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS opportunity_signals (
                    url TEXT PRIMARY KEY, title TEXT NOT NULL, source TEXT NOT NULL,
                    published_at TEXT NOT NULL, market_id TEXT NOT NULL, market_name TEXT NOT NULL,
                    summary TEXT NOT NULL, revenue_angle TEXT NOT NULL,
                    validation_test TEXT NOT NULL, score REAL NOT NULL,
                    first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS opportunity_ideas (
                    idea_id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    source_urls_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS market_daily_snapshots (
                    snapshot_date TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    market_name TEXT NOT NULL,
                    signal_count INTEGER NOT NULL,
                    avg_score REAL NOT NULL,
                    max_score REAL NOT NULL,
                    captured_at TEXT NOT NULL,
                    PRIMARY KEY (snapshot_date, market_id)
                )
            """)

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path), timeout=20)
        conn.row_factory = sqlite3.Row
        return conn

    def _fetch_google_news(self, query):
        response = requests.get(
            "https://news.google.com/rss/search",
            params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
            headers={"User-Agent": "MarketOpportunityResearch/1.0"},
            timeout=9,
        )
        response.raise_for_status()
        root = ET.fromstring(response.content)
        items = []
        for item in root.findall(".//item")[:12]:
            title, link = _clean(item.findtext("title"), 250), _clean(item.findtext("link"), 500)
            if not title or not link:
                continue
            source = item.find("source")
            items.append({
                "title": title, "url": link,
                "source": _clean(source.text if source is not None else "Google News", 100),
                "published_at": item.findtext("pubDate"),
                "summary": _clean(item.findtext("description"), 420), "points": 0,
            })
        return items

    def _fetch_hacker_news(self, query):
        response = requests.get(
            "https://hn.algolia.com/api/v1/search_by_date",
            params={"query": query, "tags": "story", "hitsPerPage": 12},
            headers={"User-Agent": "MarketOpportunityResearch/1.0"},
            timeout=9,
        )
        response.raise_for_status()
        items = []
        for hit in response.json().get("hits", []):
            title = _clean(hit.get("title") or hit.get("story_title"), 250)
            object_id = str(hit.get("objectID") or "")
            url = hit.get("url") or (f"https://news.ycombinator.com/item?id={object_id}" if object_id else "")
            if title and url:
                items.append({
                    "title": title, "url": _clean(url, 500), "source": "Hacker News",
                    "published_at": hit.get("created_at"), "summary": _clean(hit.get("story_text"), 420),
                    "points": int(hit.get("points") or 0) + int(hit.get("num_comments") or 0),
                })
        return items

    def _build_signal(self, raw):
        title, summary, url = _clean(raw.get("title"), 250), _clean(raw.get("summary"), 420), _clean(raw.get("url"), 500)
        if not title or not url or urlparse(url).scheme not in ("http", "https"):
            return None
        combined = (title + " " + summary).casefold()
        if any(term in combined for term in BLOCKED_PHRASES):
            return None
        published = _parse_date(raw.get("published_at"))
        age_days = max(0, (datetime.now(timezone.utc) - published).total_seconds() / 86400)
        if age_days > 90:
            return None
        market = classify_market(combined, self.markets) or {}
        hits = sum(1 for term in DEMAND_TERMS if term.casefold() in combined)
        score = 1 + min(3, hits * 0.55) + (2.5 if age_days <= 7 else 1.2 if age_days <= 30 else 0.2)
        score += min(1.5, math.log1p(max(0, int(raw.get("points") or 0))) / 4)
        models = market.get("revenue_models") or ["خدمت تخصصی و قرارداد پروژه‌ای"]
        test = market.get("validation_test") or "با ۱۰ مشتری بالقوه مصاحبه و یک نمونه آزمایشی اجرا کن."
        return {
            "title": title, "url": url, "source": _clean(raw.get("source") or "منبع عمومی", 100),
            "published_at": published.isoformat(), "market_id": market.get("id", "business-services"),
            "market_name": market.get("name", "خدمات کسب‌وکار"), "summary": summary,
            "revenue_angle": _clean(models[0], 180), "validation_test": _clean(test, 220),
            "score": round(score, 3),
        }

    def _save(self, signals):
        now = datetime.now(timezone.utc).isoformat()
        added = 0
        with self._connect() as conn:
            for item in signals:
                if not conn.execute("SELECT 1 FROM opportunity_signals WHERE url=?", (item["url"],)).fetchone():
                    added += 1
                conn.execute("""
                    INSERT INTO opportunity_signals
                    (url,title,source,published_at,market_id,market_name,summary,revenue_angle,
                     validation_test,score,first_seen_at,last_seen_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(url) DO UPDATE SET
                      title=excluded.title, source=excluded.source, published_at=excluded.published_at,
                      market_id=excluded.market_id, market_name=excluded.market_name,
                      summary=excluded.summary, revenue_angle=excluded.revenue_angle,
                      validation_test=excluded.validation_test, score=excluded.score,
                      last_seen_at=excluded.last_seen_at
                """, (
                    item["url"], item["title"], item["source"], item["published_at"],
                    item["market_id"], item["market_name"], item["summary"],
                    item["revenue_angle"], item["validation_test"], item["score"], now, now,
                ))
            cutoff = (datetime.now(timezone.utc).replace(day=1)).isoformat()[:10] + "T00:00:00+00:00"
            conn.execute("DELETE FROM opportunity_signals WHERE published_at < ?", (cutoff,))
        return added

    def latest_signals(self, limit=10):
        limit = min(30, max(1, int(limit)))
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT title,url,source,published_at,market_id,market_name,summary,
                       revenue_angle,validation_test,score,first_seen_at,last_seen_at
                FROM opportunity_signals ORDER BY score DESC,published_at DESC LIMIT ?
            """, (limit,)).fetchall()
        return [dict(row) for row in rows]

    def save_ai_ideas(self, content, source_urls=None):
        content = str(content or "").strip()[:8000]
        if not content:
            return False
        source_urls = [str(url)[:500] for url in (source_urls or []) if str(url).startswith(("https://", "http://"))][:10]
        idea_id = hashlib.sha256(content.encode("utf-8")).hexdigest()
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute("""
                INSERT OR IGNORE INTO opportunity_ideas
                (idea_id, content, source_urls_json, created_at)
                VALUES (?, ?, ?, ?)
            """, (idea_id, content, json.dumps(source_urls, ensure_ascii=False), created_at))
        return cursor.rowcount == 1

    def latest_ai_ideas(self, limit=3):
        limit = min(10, max(1, int(limit)))
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT idea_id, content, source_urls_json, created_at
                FROM opportunity_ideas
                ORDER BY created_at DESC LIMIT ?
            """, (limit,)).fetchall()
        return [{
            "idea_id": row["idea_id"],
            "content": row["content"],
            "source_urls": json.loads(row["source_urls_json"]),
            "created_at": row["created_at"],
        } for row in rows]

    def _run_queries(self, query_jobs):
        raw, errors = [], []
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(fetcher, query): (source, query) for source, query, fetcher in query_jobs}
            for future in concurrent.futures.as_completed(futures):
                source, query = futures[future]
                try:
                    raw.extend(future.result())
                except Exception as exc:
                    errors.append({"source": source, "query": query, "error": str(exc)[:180]})
        signals, seen = [], set()
        for item in raw:
            signal = self._build_signal(item)
            if signal and signal["url"] not in seen:
                seen.add(signal["url"])
                signals.append(signal)
        new_count = self._save(signals) if signals else 0
        return raw, signals, errors, new_count

    def save_daily_market_snapshot(self, signals, snapshot_date=None):
        """Persist one comparable daily snapshot per market and return day-over-day changes."""
        today = snapshot_date or datetime.now(ZoneInfo("Asia/Tehran")).date().isoformat()
        previous_day = (datetime.fromisoformat(today).date() - timedelta(days=1)).isoformat()
        captured_at = datetime.now(timezone.utc).isoformat()
        grouped = {}
        for item in signals or []:
            market_id = item.get("market_id", "other")
            grouped.setdefault(market_id, []).append(float(item.get("score") or 0))
        current = {}
        with self._connect() as conn:
            for market in self.markets:
                market_id = market.get("id", "other")
                scores = grouped.get(market_id, [])
                row = {
                    "market_id": market_id,
                    "market_name": market.get("name", market_id),
                    "signal_count": len(scores),
                    "avg_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
                    "max_score": round(max(scores), 3) if scores else 0.0,
                }
                current[market_id] = row
                conn.execute("""
                    INSERT INTO market_daily_snapshots
                    (snapshot_date, market_id, market_name, signal_count, avg_score, max_score, captured_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(snapshot_date, market_id) DO UPDATE SET
                      market_name=excluded.market_name,
                      signal_count=excluded.signal_count,
                      avg_score=excluded.avg_score,
                      max_score=excluded.max_score,
                      captured_at=excluded.captured_at
                """, (
                    today, row["market_id"], row["market_name"], row["signal_count"],
                    row["avg_score"], row["max_score"], captured_at,
                ))
            previous_rows = conn.execute(
                """SELECT market_id, market_name, signal_count, avg_score
                   FROM market_daily_snapshots WHERE snapshot_date = ?""",
                (previous_day,),
            ).fetchall()
        previous = {row["market_id"]: dict(row) for row in previous_rows}
        changes = []
        for market_id, row in current.items():
            prior = previous.get(market_id, {})
            prior_count = int(prior.get("signal_count", 0) or 0)
            delta = row["signal_count"] - prior_count
            if row["signal_count"] or prior_count:
                changes.append({
                    **row,
                    "previous_signal_count": prior_count,
                    "delta_signal_count": delta,
                    "previous_avg_score": round(float(prior.get("avg_score", 0) or 0), 3),
                    "snapshot_date": today,
                    "comparison_date": previous_day,
                })
        changes.sort(
            key=lambda item: (
                item["delta_signal_count"] > 0,
                abs(item["delta_signal_count"]),
                item["signal_count"],
                item["avg_score"],
            ),
            reverse=True,
        )
        return changes[:12]

    def latest_market_changes(self, limit=12):
        limit = min(20, max(1, int(limit)))
        with self._connect() as conn:
            row = conn.execute("SELECT MAX(snapshot_date) AS d FROM market_daily_snapshots").fetchone()
            latest = row["d"] if row else None
        if not latest:
            return []
        rows = self.save_daily_market_snapshot([], snapshot_date=latest)
        return rows[:limit]

    def refresh(self):
        jobs = [("Google News", q, self._fetch_google_news) for q in SEARCH_QUERIES]
        jobs += [("Hacker News", q, self._fetch_hacker_news) for q in HN_QUERIES]
        raw, signals, errors, new_count = self._run_queries(jobs)
        market_changes = self.save_daily_market_snapshot(signals)
        return {
            "fetched": len(raw), "new_count": new_count,
            "errors": errors[:12], "signals": self.latest_signals(12),
            "market_changes": market_changes,
        }

    def search_custom(self, query, limit=6):
        query = re.sub(r"[\x00-\x1f]", " ", str(query or "")).strip()
        if not query or len(query) > 120:
            return []
        raw, signals, _, _ = self._run_queries([
            ("Google News", query, self._fetch_google_news),
            ("Hacker News", query, self._fetch_hacker_news),
        ])
        return sorted(signals, key=lambda item: (item["score"], item["published_at"]), reverse=True)[:limit]


def format_market_changes(changes, limit=8):
    changes = list(changes or [])[:max(1, min(12, int(limit)))]
    if not changes:
        return "برای این نوبت سیگنال قابل‌مقایسه‌ای ثبت نشده است."
    lines = [
        "مقایسه روزانه بازارها بر اساس خبرها و سیگنال‌های عمومی",
        "این اعداد حجم جستجوی کاربران یا تقاضای قطعی خرید نیستند؛ تعداد سیگنال‌های جمع‌آوری‌شده‌اند.",
        "",
    ]
    for item in changes:
        delta = int(item.get("delta_signal_count", 0) or 0)
        direction = "افزایش" if delta > 0 else "کاهش" if delta < 0 else "بدون تغییر"
        lines.append(
            f"- {item.get('market_name', 'بازار نامشخص')}: امروز {item.get('signal_count', 0)} "
            f"| روز قبل {item.get('previous_signal_count', 0)} | {direction} {abs(delta)} "
            f"| امتیاز میانگین {item.get('avg_score', 0)}"
        )
    return "\n".join(lines)


def format_opportunity_digest(signals, limit=5):
    signals = list(signals or [])[:max(1, min(8, int(limit)))]
    if not signals:
        return "هنوز فرصت تازه‌ای در حافظه پژوهش ثبت نشده است."
    lines = [
        "فرصت‌های درآمدی و سیگنال‌های بازار",
        "این موارد سرنخ پژوهشی‌اند؛ نه آمار قطعی حجم جستجو، تضمین فروش یا توصیه سرمایه‌گذاری.",
        "",
    ]
    for index, item in enumerate(signals, 1):
        lines.extend([
            f"{index}) {item.get('title', 'بدون عنوان')}",
            f"بازار: {item.get('market_name', 'سایر')} | منبع: {item.get('source', 'منبع عمومی')}",
            f"مسیر درآمد احتمالی: {item.get('revenue_angle', 'خدمت تخصصی')}",
            f"آزمایش کم‌هزینه: {item.get('validation_test', 'با مشتریان بالقوه اعتبارسنجی کن.')}",
            f"منبع: {item.get('url', '')}", "",
        ])
    lines.extend([
        "بنچمارک‌های مرجع:",
        "Upwork 2026: " + BENCHMARK_SOURCES[0][1],
        "Fiverr 2026: " + BENCHMARK_SOURCES[1][1],
    ])
    return "\n".join(lines)
