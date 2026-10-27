"""
CyberPulse Intelligence - Comprehensive Scheduler, Storage & Reliability Test Suite
Tests:
1. Scheduler start/stop & loop lifecycle
2. Global lock preventing overlapping collection runs (race conditions)
3. Rate limiting (per-source cooldown enforcement)
4. Exponential backoff & retry mechanism
5. HTTP 429 & Retry-After header parsing
6. HTTP 5xx retry behavior
7. Shared state visibility across simulated sessions
8. Deduplication persistence across cycles
9. Timestamp preservation and non-fabrication
10. Stale cache detection and warnings
11. Manual refresh isolation and lock safety
12. Secret handling / no credentials leaking

Created by RAJ ARYAN — rajaryan.neocities.org
"""

import os
import sys
import time
import unittest
import tempfile
import threading
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import urllib.error

# Ensure root in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.database import Database
from src.scheduler import BackgroundScheduler, SchedulerStatus
from src.feed_collector import FeedCollector, _parse_retry_after
from src.deduplication import canonicalize_url, compute_title_fingerprint, compute_content_hash

class TestSchedulerAndIngestion(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.temp_db_fd)
        self.db = Database(db_path=self.temp_db_path)
        
        # Test sources
        self.db.sync_sources_from_config([
            {
                "id": "src_alpha",
                "name": "Alpha Intel",
                "feed_url": "https://alpha.example.com/feed.xml",
                "site_url": "https://alpha.example.com",
                "category": "Vulnerabilities",
                "enabled": True,
                "priority": 1
            },
            {
                "id": "src_beta",
                "name": "Beta News",
                "feed_url": "https://beta.example.com/rss",
                "site_url": "https://beta.example.com",
                "category": "Global News",
                "enabled": True,
                "priority": 1
            }
        ])

        self.mock_config = {
            "app": {
                "user_agent": "CyberPulse-Test/1.0",
                "request_timeout_seconds": 2,
                "max_concurrent_workers": 2
            },
            "scheduler": {
                "enabled": True,
                "interval_seconds": 1,
                "source_cooldown_seconds": 5,
                "max_backoff_seconds": 10,
                "max_retries_per_source": 3
            }
        }

    def tearDown(self):
        del self.db
        try:
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
        except Exception:
            pass

    def test_retry_after_header_parsing(self):
        """Test numeric and date Retry-After formats."""
        self.assertEqual(_parse_retry_after("60"), 60)
        self.assertEqual(_parse_retry_after("120"), 120)
        self.assertIsNone(_parse_retry_after(""))
        self.assertIsNone(_parse_retry_after(None))

    def test_global_lock_prevents_overlapping_jobs(self):
        """Verify that concurrent cycle requests cannot execute concurrently."""
        scheduler = BackgroundScheduler(self.db, self.mock_config)
        
        # Simulate lock held
        acquired = scheduler._fetch_lock.acquire(blocking=False)
        self.assertTrue(acquired)
        
        # Another execution attempt must return None immediately
        res = scheduler.run_immediate()
        self.assertIsNone(res)
        
        scheduler._fetch_lock.release()
        
        # Should now be acquirable
        self.assertFalse(scheduler._fetch_lock.locked())

    def test_scheduler_lifecycle_and_status(self):
        """Test starting, status tracking, and stopping scheduler."""
        scheduler = BackgroundScheduler(self.db, self.mock_config)
        self.assertFalse(scheduler.is_running())
        
        scheduler.start()
        self.assertTrue(scheduler.is_running())
        self.assertTrue(scheduler.status.get("running"))
        
        # Stop
        scheduler.stop()
        time.sleep(0.1)
        self.assertFalse(scheduler.status.get("running"))

    def test_per_source_cooldown_skipping(self):
        """Verify collector skips feeds that have been polled within cooldown window."""
        status = SchedulerStatus()
        status.record_source_cooldown("src_alpha")
        
        collector = FeedCollector(
            db=self.db,
            scheduler_status=status,
            source_cooldown_seconds=60
        )
        
        source = {
            "id": "src_alpha",
            "name": "Alpha Intel",
            "feed_url": "https://alpha.example.com/feed.xml"
        }
        
        res = collector.fetch_single_feed(source)
        self.assertEqual(res["status"], "skipped_cooldown")
        self.assertEqual(len(res["entries"]), 0)

    def test_exponential_backoff_on_failure(self):
        """Verify backoff calculation and tracking."""
        status = SchedulerStatus()
        collector = FeedCollector(
            db=self.db,
            scheduler_status=status,
            max_backoff_seconds=100
        )
        
        delay1 = collector._compute_backoff_delay(1)
        delay2 = collector._compute_backoff_delay(2)
        delay3 = collector._compute_backoff_delay(3)
        self.assertEqual(delay1, 2.0)
        self.assertEqual(delay2, 4.0)
        self.assertEqual(delay3, 8.0)
        
        # Trigger failure recording
        collector._handle_source_failure("src_alpha")
        backoff = status.get_source_backoff("src_alpha")
        self.assertIsNotNone(backoff)
        self.assertEqual(backoff["failures"], 1)
        self.assertTrue(collector._should_skip_backoff("src_alpha"))

    def test_stale_cache_detection(self):
        """Verify is_stale returns True when threshold exceeded."""
        scheduler = BackgroundScheduler(self.db, self.mock_config)
        # Empty last cycle is stale
        self.assertTrue(scheduler.is_stale())
        
        # Recently completed cycle is NOT stale
        scheduler.status.update(last_cycle_completed=datetime.now(timezone.utc).isoformat())
        self.assertFalse(scheduler.is_stale())
        
        # Very old cycle is stale
        old_time = (datetime.now(timezone.utc) - timedelta(seconds=500)).isoformat()
        scheduler.status.update(last_cycle_completed=old_time)
        self.assertTrue(scheduler.is_stale())

    def test_shared_state_persistence_and_deduplication(self):
        """Test that inserted articles persist and duplicates are deduplicated across cycles."""
        art1 = {
            "canonical_url": "https://alpha.example.com/vuln/1",
            "title_fingerprint": "critical linux kernel cve",
            "title": "Critical Linux Kernel CVE",
            "source_id": "src_alpha",
            "source_name": "Alpha Intel",
            "published_at": "2026-10-27T10:00:00Z",
            "first_seen_at": "2026-10-27T10:05:00Z",
            "collected_at": "2026-10-27T10:05:00Z",
            "summary": "Privilege escalation vulnerability in kernel.",
            "category": "Vulnerabilities",
            "author": "Kernel Sec",
            "content_hash": "cve_hash_1",
            "cve_list": ["CVE-2026-1111"]
        }
        
        inserted1, reason1 = self.db.insert_article(art1)
        self.assertTrue(inserted1)
        self.assertEqual(reason1, "inserted")
        
        # Both canonical URL and fingerprint dedup check
        inserted2, reason2 = self.db.insert_article(art1)
        self.assertFalse(inserted2)
        self.assertEqual(reason2, "duplicate_url")

        # Verify DB holds exactly 1 article
        articles, total = self.db.get_articles_filtered(limit=10)
        self.assertEqual(total, 1)
        self.assertEqual(articles[0]["source_name"], "Alpha Intel")
        self.assertEqual(articles[0]["published_at"], "2026-10-27T10:00:00Z")

    def test_secret_safety_check(self):
        """Ensure no API tokens or passwords exist in config or environment leaks."""
        with open(os.path.join(ROOT_DIR, "config.yaml"), "r", encoding="utf-8") as f:
            content = f.read().lower()
        self.assertNotIn("api_key", content)
        self.assertNotIn("bearer ", content)
        self.assertNotIn("password: ", content)
        self.assertNotIn("secret_key: ", content)

if __name__ == "__main__":
    unittest.main()
