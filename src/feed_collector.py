"""
CyberPulse Intelligence - Concurrent Feed Ingestion Engine
Fetches feeds concurrently with timeouts, response size limits, per-source cooldowns,
robust date parsing, canonical deduplication, and transactional storage.

v2: Added retry with exponential backoff, HTTP 429 Retry-After handling,
    5xx error retry, per-source cooldown enforcement, and scheduler integration.

Created by RAJ ARYAN — rajaryan.neocities.org
"""

import urllib.request
import urllib.error
import feedparser
import time
import concurrent.futures
import logging
from datetime import datetime, timezone, timedelta
import dateutil.parser
from typing import Dict, Any, List, Optional

from src.database import Database
from src.security import sanitize_text, validate_feed_url
from src.deduplication import canonicalize_url, compute_title_fingerprint, compute_content_hash
from src.cve_parser import extract_cves
from src.ioc_parser import extract_iocs
from src.categorizer import classify_article

logger = logging.getLogger("cyberpulse.collector")
logger.setLevel(logging.INFO)

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


def _parse_retry_after(header_value: str) -> Optional[int]:
    """Parse HTTP Retry-After header. Returns seconds to wait, or None."""
    if not header_value:
        return None
    # Try integer seconds first
    try:
        return max(1, int(header_value))
    except ValueError:
        pass
    # Try HTTP-date format
    try:
        retry_dt = dateutil.parser.parse(header_value)
        if retry_dt.tzinfo is None:
            retry_dt = retry_dt.replace(tzinfo=timezone.utc)
        delta = (retry_dt - datetime.now(timezone.utc)).total_seconds()
        return max(1, int(delta))
    except Exception:
        return None


class FeedCollector:
    def __init__(
        self,
        db: Database,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = 12,
        max_bytes: int = 2097152,
        scheduler_status=None,
        source_cooldown_seconds: int = 120,
        max_backoff_seconds: int = 300,
        max_retries: int = 3,
    ):
        self.db = db
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.scheduler_status = scheduler_status
        self.source_cooldown_seconds = source_cooldown_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.max_retries = max_retries

    def _should_skip_cooldown(self, source_id: str) -> bool:
        """Check if source was fetched too recently (per-source cooldown)."""
        if not self.scheduler_status:
            return False
        last_fetched = self.scheduler_status.get_source_cooldown(source_id)
        if not last_fetched:
            return False
        try:
            last_dt = dateutil.parser.parse(last_fetched)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            cooldown_threshold = datetime.now(timezone.utc) - timedelta(seconds=self.source_cooldown_seconds)
            return last_dt > cooldown_threshold
        except Exception:
            return False

    def _should_skip_backoff(self, source_id: str) -> bool:
        """Check if source is in exponential backoff period."""
        if not self.scheduler_status:
            return False
        backoff = self.scheduler_status.get_source_backoff(source_id)
        if not backoff:
            return False
        try:
            retry_after = dateutil.parser.parse(backoff["next_retry_after"])
            if retry_after.tzinfo is None:
                retry_after = retry_after.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) < retry_after
        except Exception:
            return False

    def _compute_backoff_delay(self, failures: int) -> float:
        """Exponential backoff: 2^failures seconds, capped at max_backoff_seconds."""
        delay = min(2 ** failures, self.max_backoff_seconds)
        return float(delay)

    def _fetch_with_retry(self, feed_url: str) -> bytes:
        """
        Fetches feed content with retry logic for transient errors.
        - HTTP 429: respects Retry-After header, retries after wait
        - HTTP 5xx: retries with exponential backoff
        - Network errors: retries with backoff
        Raises on permanent failure after exhausting retries.
        """
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                req = urllib.request.Request(
                    feed_url,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept": "application/rss+xml, application/atom+xml, text/xml, application/xml;q=0.9, */*;q=0.8",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    status_code = resp.getcode()
                    if status_code == 200:
                        return resp.read(self.max_bytes)
                    elif status_code == 429:
                        retry_after = _parse_retry_after(resp.getheader("Retry-After", ""))
                        wait = retry_after or (2 ** attempt)
                        wait = min(wait, self.max_backoff_seconds)
                        logger.warning(f"429 from {feed_url}, waiting {wait}s (attempt {attempt+1})")
                        time.sleep(wait)
                        continue
                    elif 500 <= status_code < 600:
                        wait = min(2 ** attempt, self.max_backoff_seconds)
                        logger.warning(f"HTTP {status_code} from {feed_url}, backoff {wait}s (attempt {attempt+1})")
                        time.sleep(wait)
                        continue
                    else:
                        raise urllib.error.HTTPError(
                            feed_url, status_code, f"HTTP {status_code}", {}, None
                        )

            except urllib.error.HTTPError as e:
                if e.code == 429:
                    retry_header = ""
                    if hasattr(e, 'headers') and e.headers:
                        retry_header = e.headers.get("Retry-After", "")
                    retry_after = _parse_retry_after(retry_header)
                    wait = retry_after or (2 ** attempt)
                    wait = min(wait, self.max_backoff_seconds)
                    logger.warning(f"429 error from {feed_url}, waiting {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                    last_exception = e
                    continue
                elif 500 <= e.code < 600:
                    wait = min(2 ** attempt, self.max_backoff_seconds)
                    logger.warning(f"HTTP {e.code} from {feed_url}, backoff {wait}s (attempt {attempt+1})")
                    time.sleep(wait)
                    last_exception = e
                    continue
                else:
                    raise
            except (urllib.error.URLError, TimeoutError, OSError, ConnectionError) as e:
                wait = min(2 ** attempt, self.max_backoff_seconds)
                logger.warning(f"Network error {type(e).__name__} for {feed_url}, backoff {wait}s (attempt {attempt+1})")
                time.sleep(wait)
                last_exception = e
                continue

        raise last_exception or Exception(f"Failed to fetch {feed_url} after {self.max_retries} attempts")

    def fetch_single_feed(self, source: Dict[str, Any]) -> Dict[str, Any]:
        """Fetches and parses a single RSS/Atom feed safely, with retry and backoff."""
        source_id = source["id"]
        feed_url = source["feed_url"]
        source_name = source["name"]
        default_cat = source.get("category", "Global News")
        
        # Check cooldown
        if self._should_skip_cooldown(source_id):
            return {"source_id": source_id, "status": "skipped_cooldown", "entries": []}

        # Check backoff
        if self._should_skip_backoff(source_id):
            return {"source_id": source_id, "status": "skipped_backoff", "entries": []}

        if not validate_feed_url(feed_url):
            err = "Invalid or disallowed feed URL scheme/host"
            self.db.record_source_error(source_id, feed_url, err, datetime.now(timezone.utc).isoformat())
            return {"source_id": source_id, "status": "error", "error": err, "entries": []}

        try:
            content = self._fetch_with_retry(feed_url)
            parsed = feedparser.parse(content)

            if parsed.bozo and not parsed.entries:
                err = f"Bozo XML parse error: {parsed.bozo_exception}"
                self.db.record_source_error(source_id, feed_url, err, datetime.now(timezone.utc).isoformat())
                self._handle_source_failure(source_id)
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

            # Record cooldown and clear backoff on success
            if self.scheduler_status:
                self.scheduler_status.record_source_cooldown(source_id)
                self.scheduler_status.clear_source_backoff(source_id)

            return {"source_id": source_id, "status": "success", "entries": parsed_articles}

        except Exception as e:
            err = f"{type(e).__name__}: {str(e)}"
            self.db.record_source_error(source_id, feed_url, err, datetime.now(timezone.utc).isoformat())
            self._handle_source_failure(source_id)
            return {"source_id": source_id, "status": "error", "error": err, "entries": []}

    def _handle_source_failure(self, source_id: str):
        """Update backoff state after a source failure."""
        if not self.scheduler_status:
            return
        existing = self.scheduler_status.get_source_backoff(source_id)
        failures = (existing["failures"] + 1) if existing else 1
        delay = self._compute_backoff_delay(failures)
        next_retry = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
        self.scheduler_status.record_source_backoff(source_id, failures, next_retry)
        logger.info(f"Source {source_id}: backoff #{failures}, next retry in {delay}s")

    def run_collection_cycle(self, max_workers: int = 10) -> Dict[str, Any]:
        """Runs a concurrent sweep across all enabled sources."""
        start_time = datetime.now(timezone.utc)
        sources = [s for s in self.db.get_sources_inventory() if s["enabled"]]
        
        sources_polled = len(sources)
        sources_succeeded = 0
        sources_failed = 0
        sources_skipped = 0
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
                elif res["status"].startswith("skipped"):
                    sources_skipped += 1
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
            "sources_skipped": sources_skipped,
            "entries_processed": entries_processed,
            "new_articles_inserted": new_inserted,
            "duplicates_skipped": duplicates_skipped,
            "duration_seconds": round(dur, 2),
            "status": "completed" if sources_failed == 0 else f"completed_with_{sources_failed}_failures"
        }

        self.db.record_collection_run(run_stats)
        return run_stats
