"""
CyberPulse Intelligence - Comprehensive Test Suite
Validates database persistence, deduplication, safe URL validation,
XSS/CSV injection mitigation, CVE extraction, IOC defanging, and data exports.
"""

import os
import sys
import unittest
import tempfile
import gc

# Ensure project root is in sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.database import Database
from src.security import sanitize_text, validate_feed_url, sanitize_csv_cell, defang_ioc
from src.deduplication import canonicalize_url, compute_title_fingerprint, compute_content_hash
from src.cve_parser import extract_cves, get_nvd_url
from src.ioc_parser import extract_iocs
from src.categorizer import classify_article
from src.export_service import ExportService

class TestCyberPulseIntelligence(unittest.TestCase):
    def setUp(self):
        self.temp_db_path = os.path.join(tempfile.gettempdir(), f"cp_test_{os.getpid()}_{id(self)}.db")
        self.db = Database(db_path=self.temp_db_path)
        # Register dummy source to satisfy foreign key constraints
        self.db.sync_sources_from_config([{
            "id": "test_src",
            "name": "Test Source",
            "feed_url": "https://example.com/feed.xml",
            "site_url": "https://example.com",
            "category": "Vulnerabilities",
            "enabled": True,
            "priority": 1
        }])

    def tearDown(self):
        del self.db
        gc.collect()
        try:
            if os.path.exists(self.temp_db_path):
                os.remove(self.temp_db_path)
        except Exception:
            pass

    def test_database_persistence_and_schema(self):
        """Verifies tables and schema version initialized properly."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = {row[0] for row in cursor.fetchall()}
            self.assertIn("articles", tables)
            self.assertIn("sources", tables)
            self.assertIn("collection_runs", tables)
            self.assertIn("schema_version", tables)

    def test_deduplication_canonical_url_and_fingerprint(self):
        """Ensures duplicate URLs and normalized title fingerprints are skipped."""
        art1 = {
            "canonical_url": "https://example.com/advisory-1?utm_source=twitter",
            "title_fingerprint": "critical zero day vulnerability in apache",
            "title": "Critical Zero-Day Vulnerability in Apache",
            "source_id": "test_src",
            "source_name": "Test Source",
            "published_at": "2026-10-13T10:00:00Z",
            "first_seen_at": "2026-10-13T10:05:00Z",
            "collected_at": "2026-10-13T10:05:00Z",
            "summary": "Apache released patch for RCE flaw.",
            "category": "Vulnerabilities",
            "author": "Security Team",
            "content_hash": "hash123",
            "cve_list": ["CVE-2026-1234"],
            "ioc_list": []
        }
        
        art1["canonical_url"] = canonicalize_url(art1["canonical_url"])
        inserted, reason = self.db.insert_article(art1)
        self.assertTrue(inserted)
        self.assertEqual(reason, "inserted")

        # Duplicate canonical URL attempt
        art2 = art1.copy()
        art2["canonical_url"] = "https://example.com/advisory-1?utm_medium=email"
        art2["canonical_url"] = canonicalize_url(art2["canonical_url"])
        inserted2, reason2 = self.db.insert_article(art2)
        self.assertFalse(inserted2)
        self.assertEqual(reason2, "duplicate_url")

        # Duplicate fingerprint attempt with different URL
        art3 = art1.copy()
        art3["canonical_url"] = "https://example.com/advisory-2"
        inserted3, reason3 = self.db.insert_article(art3)
        self.assertFalse(inserted3)
        self.assertEqual(reason3, "duplicate_title_fingerprint")

    def test_cve_extraction_and_nvd_link(self):
        """Tests standard CVE extraction and NVD formatting."""
        text = "Security researchers discovered CVE-2026-45678 and CVE-2025-0012 affecting Linux kernel."
        cves = extract_cves(text)
        self.assertEqual(cves, ["CVE-2025-0012", "CVE-2026-45678"])
        self.assertEqual(get_nvd_url("CVE-2026-45678"), "https://nvd.nist.gov/vuln/detail/CVE-2026-45678")

    def test_security_sanitization_and_injection_mitigation(self):
        """Verifies HTML strip, SSRF check, CSV injection escaping."""
        dirty_html = "<script>alert('pwned')</script><b>Malicious Payload</b> <iframe src='evil.com'></iframe>"
        clean = sanitize_text(dirty_html)
        self.assertNotIn("<script>", clean)
        self.assertNotIn("<iframe>", clean)
        self.assertEqual(clean, "Malicious Payload")

        malicious_formula = "=CMD|' /C calc'!A0"
        safe_cell = sanitize_csv_cell(malicious_formula)
        self.assertTrue(safe_cell.startswith("'"))

        self.assertFalse(validate_feed_url("http://127.0.0.1/admin/feed.xml"))
        self.assertFalse(validate_feed_url("http://localhost:8080/rss"))
        self.assertFalse(validate_feed_url("ftp://example.com/feed.xml"))
        self.assertTrue(validate_feed_url("https://www.bleepingcomputer.com/feed/"))

    def test_ioc_defanging(self):
        """Ensures indicators of compromise are defanged safely."""
        self.assertEqual(defang_ioc("http://malware-drop.com/payload.exe"), "hxxp://malware-drop[.]com/payload[.]exe")
        self.assertEqual(defang_ioc("198.51.100.14"), "198[.]51[.]100[.]14")

    def test_topic_classification(self):
        """Checks transparent security keyword heuristic categorizer."""
        cat, inferred = classify_article("LockBit Ransomware Demands $5M Extortion", "Victim network encrypted")
        self.assertEqual(cat, "Ransomware")
        self.assertTrue(inferred)

        cat2, _ = classify_article("Lumma Stealer Distributed Via Phishing Mail", "New trojan malware variant")
        self.assertEqual(cat2, "Malware")

    def test_export_service_csv_json(self):
        """Tests clean export to CSV and JSON without leaking internal paths."""
        articles = [{
            "id": 1,
            "title": "Critical Patch Released",
            "source_name": "Vendor Bulletin",
            "category": "Vendor Advisories",
            "published_at": "2026-10-13T12:00:00Z",
            "first_seen_at": "2026-10-13T12:05:00Z",
            "canonical_url": "https://example.com/patch",
            "author": "Advisory Team",
            "cve_list": "CVE-2026-9999",
            "summary": "Fixes remote bug"
        }]
        csv_data = ExportService.export_to_csv(articles)
        self.assertIn("Critical Patch Released", csv_data)
        self.assertIn("CVE-2026-9999", csv_data)

        json_data = ExportService.export_to_json(articles)
        self.assertIn('"title": "Critical Patch Released"', json_data)
        self.assertNotIn("cyberpulse.db", json_data)

if __name__ == "__main__":
    unittest.main()
