"""
CyberPulse Intelligence - Concurrent Feed Ingestion Engine
Fetches feeds concurrently with timeouts, response size limits, per-source cooldowns,
robust date parsing, canonical deduplication, and transactional storage.
"""

import urllib.request
import feedparser
import time
import concurrent.futures
from datetime import datetime, timezone
import dateutil.parser
from typing import Dict, Any, List, Optional

from src.database import Database
from src.security import sanitize_text, validate_feed_url
from src.deduplication import canonicalize_url, compute_title_fingerprint, compute_content_hash
from src.cve_parser import extract_cves
from src.ioc_parser import extract_iocs
from src.categorizer import classify_article

DEFAULT_USER_AGENT = "CyberPulse-Intelligence/1.0 (+https://github.com/cyberpulse; threat-intel-bot)"

def parse_published_date(entry: Any) -> Optional[str]:
    """Extracts and normalizes timestamp to ISO 8601 UTC string."""
    date_candidates = [
        getattr(entry, 'published', None),
        getattr(entry, 'updated', None),
        getattr(entry, 'created', None),
        getattr(entry, 'pubDate', None)
    ]
    
    # Try parsed structs first
    struct_time = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
    if struct_time:
        try:
            dt = datetime(*struct_time[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass

    for raw in date_candidates:
        if raw and isinstance(raw, str):
            try:
                dt = dateutil.parser.parse(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                return dt.isoformat()
            except Exception:
                continue

    return None

class FeedCollector:
    def __init__(self, db: Database, user_agent: str = DEFAULT_USER_AGENT, timeout: int = 12, max_bytes: int = 2097152):
        self.db = db
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_bytes = max_bytes

    def fetch_single_feed(self, source: Dict[str, Any]) -> Dict[str, Any]:
        """Fetches and parses a single RSS/Atom feed safely."""
        source_id = source["id"]
        feed_url = source["feed_url"]
        source_name = source["name"]
        default_cat = source.get("category", "Global News")
        
        if not validate_feed_url(feed_url):
            err = "Invalid or disallowed feed URL scheme/host"
            self.db.record_source_error(source_id, feed_url, err, datetime.now(timezone.utc).isoformat())
            return {"source_id": source_id, "status": "error", "error": err, "entries": []}

        try:
            req = urllib.request.Request(
                feed_url,
                headers={"User-Agent": self.user_agent, "Accept": "application/rss+xml, application/atom+xml, text/xml, application/xml;q=0.9, */*;q=0.8"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status_code = resp.getcode()
                if status_code != 200:
                    err = f"HTTP {status_code}"
                    self.db.record_source_error(source_id, feed_url, err, datetime.now(timezone.utc).isoformat())
                    return {"source_id": source_id, "status": "error", "error": err, "entries": []}
                
                content = resp.read(self.max_bytes)
                parsed = feedparser.parse(content)

                if parsed.bozo and not parsed.entries:
                    err = f"Bozo XML parse error: {parsed.bozo_exception}"
                    self.db.record_source_error(source_id, feed_url, err, datetime.now(timezone.utc).isoformat())
                    return {"source_id": source_id, "status": "error", "error": err, "entries": []}

                parsed_articles = []
                now_utc = datetime.now(timezone.utc).isoformat()

                for entry in parsed.entries:
                    raw_title = getattr(entry, 'title', '')
                    title = sanitize_text(raw_title, max_length=500)
                    if not title:
                        continue

                    raw_link = getattr(entry, 'link', '')
                    canonical_url = canonicalize_url(raw_link)
                    if not canonical_url:
                        continue

                    # Summary or description
                    raw_summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                    clean_summary = sanitize_text(raw_summary, max_length=2000)

                    # Published date
                    published_at = parse_published_date(entry)

                    # Deduplication tokens
                    fingerprint = compute_title_fingerprint(title)
                    content_hash = compute_content_hash(title, clean_summary, canonical_url)

                    # Automatic security classification
                    category, _ = classify_article(title, clean_summary, default_cat)

                    # Security intelligence
                    combined_text = f"{title} {clean_summary}"
                    cves = extract_cves(combined_text)
                    iocs = extract_iocs(clean_summary)
                    ioc_flat = iocs["ips"] + iocs["hashes"]

                    author = sanitize_text(getattr(entry, 'author', ''), max_length=150)

                    # Extract image URL if available
                    image_url = ""
                    # 1. Enclosures
                    enclosures = getattr(entry, 'enclosures', []) or []
                    for enc in enclosures:
                        href = enc.get('href', '') or enc.get('url', '')
                        if href and any(href.lower().endswith(ext) or ext in href.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', 'image']):
                            image_url = href
                            break
                    # 2. Media content
                    if not image_url:
                        media_contents = getattr(entry, 'media_content', []) or []
                        for m in media_contents:
                            m_url = m.get('url', '')
                            if m_url:
                                image_url = m_url
                                break
                    # 3. Links rel=enclosure
                    if not image_url:
                        links = getattr(entry, 'links', []) or []
                        for lk in links:
                            if lk.get('rel') == 'enclosure' and 'image' in lk.get('type', ''):
                                image_url = lk.get('href', '')
                                break

                    parsed_articles.append({
                        "canonical_url": canonical_url,
                        "title_fingerprint": fingerprint,
                        "title": title,
                        "source_id": source_id,
                        "source_name": source_name,
                        "published_at": published_at,
                        "first_seen_at": now_utc,
                        "collected_at": now_utc,
                        "summary": clean_summary,
                        "category": category,
                        "author": author,
                        "content_hash": content_hash,
                        "cve_list": cves,
                        "ioc_list": ioc_flat,
                        "image_url": image_url
                    })

                self.db.record_source_success(source_id, now_utc)
                return {"source_id": source_id, "status": "success", "entries": parsed_articles}

        except Exception as e:
            err = f"{type(e).__name__}: {str(e)}"
            self.db.record_source_error(source_id, feed_url, err, datetime.now(timezone.utc).isoformat())
            return {"source_id": source_id, "status": "error", "error": err, "entries": []}

    def run_collection_cycle(self, max_workers: int = 10) -> Dict[str, Any]:
        """Runs a concurrent sweep across all enabled sources."""
        start_time = datetime.now(timezone.utc)
        sources = [s for s in self.db.get_sources_inventory() if s["enabled"]]
        
        sources_polled = len(sources)
        sources_succeeded = 0
        sources_failed = 0
        entries_processed = 0
        new_inserted = 0
        duplicates_skipped = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_source = {executor.submit(self.fetch_single_feed, s): s for s in sources}
            for future in concurrent.futures.as_completed(future_to_source):
                res = future.result()
                if res["status"] == "success":
                    sources_succeeded += 1
                    for article in res["entries"]:
                        entries_processed += 1
                        inserted, _ = self.db.insert_article(article)
                        if inserted:
                            new_inserted += 1
                        else:
                            duplicates_skipped += 1
                else:
                    sources_failed += 1

        end_time = datetime.now(timezone.utc)
        dur = (end_time - start_time).total_seconds()

        run_stats = {
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat(),
            "sources_polled": sources_polled,
            "sources_succeeded": sources_succeeded,
            "sources_failed": sources_failed,
            "entries_processed": entries_processed,
            "new_articles_inserted": new_inserted,
            "duplicates_skipped": duplicates_skipped,
            "duration_seconds": round(dur, 2),
            "status": "completed" if sources_failed == 0 else f"completed_with_{sources_failed}_failures"
        }

        self.db.record_collection_run(run_stats)
        return run_stats
