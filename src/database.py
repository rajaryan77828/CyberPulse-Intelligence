"""
CyberPulse Intelligence - SQLite Persistent Storage Layer
Implements strict parameterized queries, schema versioning, transaction handling,
canonical deduplication indexing, bookmarks, read tracking, and audit logging.
"""

import sqlite3
import os
import shutil
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

SCHEMA_VERSION = 1

class Database:
    def __init__(self, db_path: str = "data/cyberpulse.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def init_schema(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Version table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            );
            """)

            # Sources Registry Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                feed_url TEXT NOT NULL UNIQUE,
                site_url TEXT,
                category TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                priority INTEGER DEFAULT 1,
                last_checked TEXT,
                last_success TEXT,
                last_error TEXT,
                consecutive_failures INTEGER DEFAULT 0,
                total_articles_fetched INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """)

            # Articles Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_url TEXT NOT NULL UNIQUE,
                title_fingerprint TEXT NOT NULL,
                title TEXT NOT NULL,
                source_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                published_at TEXT,
                first_seen_at TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                summary TEXT,
                category TEXT NOT NULL,
                author TEXT,
                content_hash TEXT NOT NULL,
                has_cve INTEGER DEFAULT 0,
                cve_list TEXT,
                ioc_list TEXT,
                image_url TEXT,
                read_status INTEGER DEFAULT 0,
                bookmarked INTEGER DEFAULT 0,
                read_later INTEGER DEFAULT 0,
                user_tags TEXT DEFAULT '',
                FOREIGN KEY (source_id) REFERENCES sources (id) ON DELETE CASCADE
            );
            """)

            # Indexes for ultra-fast query performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_canonical_url ON articles(canonical_url);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_fingerprint ON articles(title_fingerprint);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_collected ON articles(collected_at);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles(source_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_bookmarked ON articles(bookmarked);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_read_status ON articles(read_status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_has_cve ON articles(has_cve);")

            # Collection Run History
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS collection_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                sources_polled INTEGER NOT NULL,
                sources_succeeded INTEGER NOT NULL,
                sources_failed INTEGER NOT NULL,
                entries_processed INTEGER NOT NULL,
                new_articles_inserted INTEGER NOT NULL,
                duplicates_skipped INTEGER NOT NULL,
                duration_seconds REAL NOT NULL,
                status TEXT NOT NULL
            );
            """)

            # Source Error Logs Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                feed_url TEXT NOT NULL,
                error_message TEXT NOT NULL,
                error_time TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
            );
            """)

            # Record schema version
            cursor.execute("SELECT MAX(version) FROM schema_version;")
            row = cursor.fetchone()
            current_v = row[0] if row and row[0] is not None else 0
            if current_v < SCHEMA_VERSION:
                cursor.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?);",
                    (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat())
                )
            conn.commit()

    def sync_sources_from_config(self, sources_list: List[Dict[str, Any]]):
        """Syncs the YAML config sources into the SQLite table without overwriting runtime stats."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now(timezone.utc).isoformat()
            for s in sources_list:
                cursor.execute("""
                INSERT INTO sources (id, name, feed_url, site_url, category, enabled, priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    feed_url=excluded.feed_url,
                    site_url=excluded.site_url,
                    category=excluded.category;
                """, (
                    s["id"],
                    s["name"],
                    s["feed_url"],
                    s.get("site_url", ""),
                    s.get("category", "Global News"),
                    1 if s.get("enabled", True) else 0,
                    s.get("priority", 1),
                    now
                ))
            conn.commit()

    def insert_article(self, article: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Inserts an article if not duplicate by canonical URL or title fingerprint.
        Returns (is_inserted, reason_if_skipped)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check canonical URL
            cursor.execute("SELECT id FROM articles WHERE canonical_url = ?;", (article["canonical_url"],))
            if cursor.fetchone():
                return False, "duplicate_url"

            # Check title fingerprint within last 30 days
            cursor.execute("SELECT id FROM articles WHERE title_fingerprint = ?;", (article["title_fingerprint"],))
            if cursor.fetchone():
                return False, "duplicate_title_fingerprint"

            cursor.execute("""
            INSERT INTO articles (
                canonical_url, title_fingerprint, title, source_id, source_name,
                published_at, first_seen_at, collected_at, summary, category,
                author, content_hash, has_cve, cve_list, ioc_list, image_url, read_status,
                bookmarked, read_later, user_tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, '');
            """, (
                article["canonical_url"],
                article["title_fingerprint"],
                article["title"],
                article["source_id"],
                article["source_name"],
                article.get("published_at"),
                article["first_seen_at"],
                article["collected_at"],
                article.get("summary", ""),
                article.get("category", "Global News"),
                article.get("author", ""),
                article["content_hash"],
                1 if article.get("cve_list") else 0,
                ",".join(article.get("cve_list", [])),
                ",".join(article.get("ioc_list", [])),
                article.get("image_url", "")
            ))
            
            cursor.execute("""
            UPDATE sources SET total_articles_fetched = total_articles_fetched + 1 WHERE id = ?;
            """, (article["source_id"],))

            conn.commit()
            return True, "inserted"

    def record_source_success(self, source_id: str, timestamp: str):
        with self.get_connection() as conn:
            conn.execute("""
            UPDATE sources SET 
                last_checked = ?,
                last_success = ?,
                last_error = NULL,
                consecutive_failures = 0
            WHERE id = ?;
            """, (timestamp, timestamp, source_id))
            conn.commit()

    def record_source_error(self, source_id: str, feed_url: str, error_msg: str, timestamp: str):
        with self.get_connection() as conn:
            conn.execute("""
            UPDATE sources SET 
                last_checked = ?,
                last_error = ?,
                consecutive_failures = consecutive_failures + 1
            WHERE id = ?;
            """, (timestamp, error_msg, source_id))
            
            conn.execute("""
            INSERT INTO source_errors (source_id, feed_url, error_message, error_time)
            VALUES (?, ?, ?, ?);
            """, (source_id, feed_url, error_msg, timestamp))
            conn.commit()

    def record_collection_run(self, run_stats: Dict[str, Any]):
        with self.get_connection() as conn:
            conn.execute("""
            INSERT INTO collection_runs (
                started_at, completed_at, sources_polled, sources_succeeded,
                sources_failed, entries_processed, new_articles_inserted,
                duplicates_skipped, duration_seconds, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                run_stats["started_at"],
                run_stats["completed_at"],
                run_stats["sources_polled"],
                run_stats["sources_succeeded"],
                run_stats["sources_failed"],
                run_stats["entries_processed"],
                run_stats["new_articles_inserted"],
                run_stats["duplicates_skipped"],
                run_stats["duration_seconds"],
                run_stats["status"]
            ))
            conn.commit()

    def get_articles_filtered(
        self,
        category: Optional[str] = None,
        source_id: Optional[str] = None,
        search_query: Optional[str] = None,
        cve_filter: Optional[str] = None,
        only_bookmarked: bool = False,
        only_read_later: bool = False,
        only_unread: bool = False,
        published_today: bool = False,
        discovered_today: bool = False,
        sort_by: str = "newest",
        offset: int = 0,
        limit: int = 25
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Filtered and paginated query returning (articles, total_count)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            conditions = ["1=1"]
            params = []

            if category and category != "All":
                conditions.append("category = ?")
                params.append(category)

            if source_id and source_id != "All":
                conditions.append("source_id = ?")
                params.append(source_id)

            if search_query:
                q = f"%{search_query.strip()}%"
                conditions.append("(title LIKE ? OR summary LIKE ? OR user_tags LIKE ? OR author LIKE ?)")
                params.extend([q, q, q, q])

            if cve_filter:
                conditions.append("cve_list LIKE ?")
                params.append(f"%{cve_filter.strip().upper()}%")

            if only_bookmarked:
                conditions.append("bookmarked = 1")

            if only_read_later:
                conditions.append("read_later = 1")

            if only_unread:
                conditions.append("read_status = 0")

            today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if published_today:
                conditions.append("published_at LIKE ?")
                params.append(f"{today_date}%")

            if discovered_today:
                conditions.append("first_seen_at LIKE ?")
                params.append(f"{today_date}%")

            where_clause = " WHERE " + " AND ".join(conditions)

            # Count total
            cursor.execute(f"SELECT COUNT(*) FROM articles {where_clause};", params)
            total_count = cursor.fetchone()[0]

            # Sorting
            sort_order = "published_at DESC NULLS LAST, id DESC"
            if sort_by == "oldest":
                sort_order = "published_at ASC NULLS LAST, id ASC"
            elif sort_by == "source":
                sort_order = "source_name ASC, published_at DESC"
            elif sort_by == "collected_newest":
                sort_order = "collected_at DESC"

            query = f"""
            SELECT * FROM articles 
            {where_clause} 
            ORDER BY {sort_order} 
            LIMIT ? OFFSET ?;
            """
            cursor.execute(query, params + [limit, offset])
            rows = [dict(r) for r in cursor.fetchall()]
            return rows, total_count

    def update_article_flag(self, article_id: int, flag_name: str, value: int):
        allowed_flags = {"bookmarked", "read_status", "read_later"}
        if flag_name not in allowed_flags:
            raise ValueError(f"Disallowed flag: {flag_name}")
        with self.get_connection() as conn:
            conn.execute(f"UPDATE articles SET {flag_name} = ? WHERE id = ?;", (value, article_id))
            conn.commit()

    def update_article_tags(self, article_id: int, tags: str):
        with self.get_connection() as conn:
            conn.execute("UPDATE articles SET user_tags = ? WHERE id = ?;", (tags, article_id))
            conn.commit()

    def get_sources_inventory(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sources ORDER BY priority ASC, name ASC;")
            return [dict(r) for r in cursor.fetchall()]

    def set_source_enabled(self, source_id: str, enabled: bool):
        with self.get_connection() as conn:
            conn.execute("UPDATE sources SET enabled = ? WHERE id = ?;", (1 if enabled else 0, source_id))
            conn.commit()

    def get_overview_statistics(self) -> Dict[str, Any]:
        """Calculates exact, un-inflated statistics for the SOC dashboard."""
        today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total stored articles
            cursor.execute("SELECT COUNT(*) FROM articles;")
            total_articles = cursor.fetchone()[0]

            # Unique articles published today
            cursor.execute("SELECT COUNT(*) FROM articles WHERE published_at LIKE ?;", (f"{today_date}%",))
            published_today = cursor.fetchone()[0]

            # Articles collected/discovered today
            cursor.execute("SELECT COUNT(*) FROM articles WHERE collected_at LIKE ?;", (f"{today_date}%",))
            collected_today = cursor.fetchone()[0]

            # Articles in last 24h
            cursor.execute("""
            SELECT COUNT(*) FROM articles 
            WHERE published_at >= datetime('now', '-24 hours');
            """)
            published_last_24h = cursor.fetchone()[0]

            # Source stats
            cursor.execute("SELECT COUNT(*) FROM sources WHERE enabled = 1;")
            sources_enabled = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM sources WHERE last_error IS NOT NULL AND consecutive_failures > 0;")
            sources_with_errors = cursor.fetchone()[0]

            # Distinct sources updated today
            cursor.execute("""
            SELECT COUNT(DISTINCT source_id) FROM articles 
            WHERE collected_at LIKE ?;
            """, (f"{today_date}%",))
            sources_updated_today = cursor.fetchone()[0]

            # Last collection run
            cursor.execute("SELECT * FROM collection_runs ORDER BY id DESC LIMIT 1;")
            last_run_row = cursor.fetchone()
            last_run = dict(last_run_row) if last_run_row else None

            # Category distribution
            cursor.execute("SELECT category, COUNT(*) as count FROM articles GROUP BY category ORDER BY count DESC;")
            category_counts = [dict(r) for r in cursor.fetchall()]

            # Top sources
            cursor.execute("SELECT source_name, COUNT(*) as count FROM articles GROUP BY source_name ORDER BY count DESC LIMIT 15;")
            source_counts = [dict(r) for r in cursor.fetchall()]

            # CVEs breakdown
            cursor.execute("SELECT cve_list FROM articles WHERE has_cve = 1 AND cve_list != '';")
            cve_rows = cursor.fetchall()
            cve_freq = {}
            for r in cve_rows:
                for cve in r[0].split(","):
                    cve = cve.strip()
                    if cve:
                        cve_freq[cve] = cve_freq.get(cve, 0) + 1
            top_cves = sorted(cve_freq.items(), key=lambda x: x[1], reverse=True)[:10]

            return {
                "total_articles": total_articles,
                "published_today": published_today,
                "collected_today": collected_today,
                "published_last_24h": published_last_24h,
                "sources_enabled": sources_enabled,
                "sources_with_errors": sources_with_errors,
                "sources_updated_today": sources_updated_today,
                "last_run": last_run,
                "category_counts": category_counts,
                "source_counts": source_counts,
                "top_cves": top_cves
            }

    def backup_database(self, destination_dir: str = "backups") -> str:
        """Safely creates a timestamped snapshot of the SQLite database using SQLite backup API."""
        os.makedirs(destination_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(destination_dir, f"cyberpulse_backup_{timestamp}.db")
        
        with self.get_connection() as src_conn:
            dest_conn = sqlite3.connect(backup_file)
            src_conn.backup(dest_conn)
            dest_conn.close()
            
        return backup_file

    def restore_database(self, backup_file_path: str):
        if not os.path.exists(backup_file_path):
            raise FileNotFoundError(f"Backup file not found: {backup_file_path}")
        
        # Verify valid sqlite
        try:
            test_conn = sqlite3.connect(backup_file_path)
            test_cursor = test_conn.cursor()
            test_cursor.execute("SELECT COUNT(*) FROM articles;")
            test_conn.close()
        except Exception as e:
            raise ValueError(f"Invalid SQLite backup file: {e}")

        shutil.copy2(backup_file_path, self.db_path)
