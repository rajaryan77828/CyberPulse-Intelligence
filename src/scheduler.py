"""
CyberPulse Intelligence - Background Auto-Fetch Scheduler
Runs a singleton background thread that periodically sweeps all enabled feeds.
Designed for Streamlit Community Cloud compatibility via @st.cache_resource.

Features:
- Global threading.Lock prevents overlapping collection cycles
- Per-source cooldown tracking (minimum seconds between re-fetches)
- Configurable interval (default 300s / 5 min)
- Exponential backoff on repeated source failures (capped at 5 min)
- Stale-cache detection and warning flags
- Thread-safe status reporting for the UI
- Graceful start/stop with daemon thread

Created by RAJ ARYAN — rajaryan.neocities.org
"""

import threading
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

logger = logging.getLogger("cyberpulse.scheduler")
logger.setLevel(logging.INFO)


class SchedulerStatus:
    """Thread-safe container for scheduler runtime state, readable by the UI."""

    def __init__(self):
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {
            "running": False,
            "interval_seconds": 300,
            "last_cycle_started": None,
            "last_cycle_completed": None,
            "next_scheduled": None,
            "last_cycle_stats": None,
            "total_cycles_run": 0,
            "total_articles_ingested": 0,
            "consecutive_empty_cycles": 0,
            "is_fetching_now": False,
            "source_backoff": {},       # source_id -> {failures, next_retry_after}
            "source_cooldowns": {},     # source_id -> last_fetched_utc_iso
            "error": None,
        }

    def get(self, key: str, default=None):
        with self._lock:
            return self._data.get(key, default)

    def get_snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def update(self, **kwargs):
        with self._lock:
            self._data.update(kwargs)

    def record_source_cooldown(self, source_id: str):
        with self._lock:
            self._data["source_cooldowns"][source_id] = datetime.now(timezone.utc).isoformat()

    def get_source_cooldown(self, source_id: str) -> Optional[str]:
        with self._lock:
            return self._data["source_cooldowns"].get(source_id)

    def record_source_backoff(self, source_id: str, failures: int, next_retry_after: str):
        with self._lock:
            self._data["source_backoff"][source_id] = {
                "failures": failures,
                "next_retry_after": next_retry_after,
            }

    def clear_source_backoff(self, source_id: str):
        with self._lock:
            self._data["source_backoff"].pop(source_id, None)

    def get_source_backoff(self, source_id: str) -> Optional[Dict]:
        with self._lock:
            return self._data["source_backoff"].get(source_id)


class BackgroundScheduler:
    """
    Singleton-style background scheduler that runs feed collection on a timer.

    Usage (in Streamlit via @st.cache_resource):
        scheduler = BackgroundScheduler(db, config)
        scheduler.start()
    """

    _fetch_lock = threading.Lock()  # Global lock — one collection at a time, ever

    def __init__(self, db, config: Dict[str, Any]):
        self.db = db
        self.config = config

        sched_cfg = config.get("scheduler", {})
        self.interval = sched_cfg.get("interval_seconds", 300)
        self.source_cooldown_seconds = sched_cfg.get("source_cooldown_seconds", 120)
        self.max_backoff_seconds = sched_cfg.get("max_backoff_seconds", 300)
        self.max_retries_per_source = sched_cfg.get("max_retries_per_source", 3)

        self.status = SchedulerStatus()
        self.status.update(interval_seconds=self.interval)

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self):
        """Start the background scheduler thread (idempotent)."""
        if self._thread is not None and self._thread.is_alive():
            logger.info("Scheduler already running — ignoring duplicate start()")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="CyberPulse-Scheduler",
            daemon=True,
        )
        self._thread.start()
        self.status.update(running=True)
        logger.info(f"Background scheduler started (interval={self.interval}s)")

    def stop(self):
        """Signal the scheduler to stop after current cycle."""
        self._stop_event.set()
        self.status.update(running=False)
        logger.info("Scheduler stop requested")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run_loop(self):
        """Main loop: sleep → fetch → repeat until stopped."""
        while not self._stop_event.is_set():
            next_run = datetime.now(timezone.utc) + timedelta(seconds=self.interval)
            self.status.update(next_scheduled=next_run.isoformat())

            # Sleep in small increments so we can respond to stop quickly
            slept = 0
            while slept < self.interval and not self._stop_event.is_set():
                chunk = min(2.0, self.interval - slept)
                time.sleep(chunk)
                slept += chunk

            if self._stop_event.is_set():
                break

            self._execute_cycle()

        self.status.update(running=False, next_scheduled=None)
        logger.info("Scheduler loop exited cleanly")

    def run_immediate(self) -> Optional[Dict[str, Any]]:
        """
        Manual one-shot fetch (from the sidebar button).
        Uses the same global lock so it can't overlap with a scheduled run.
        Returns cycle stats or None if another fetch is already running.
        """
        return self._execute_cycle()

    def _execute_cycle(self) -> Optional[Dict[str, Any]]:
        """Run one complete collection cycle under the global lock."""
        if not self._fetch_lock.acquire(blocking=False):
            logger.warning("Skipping cycle — another fetch is already in progress")
            return None

        try:
            self.status.update(is_fetching_now=True, last_cycle_started=datetime.now(timezone.utc).isoformat())
            logger.info("Starting collection cycle")

            from src.feed_collector import FeedCollector

            collector = FeedCollector(
                db=self.db,
                user_agent=self.config.get("app", {}).get("user_agent", "CyberPulse-Intelligence/1.0"),
                timeout=self.config.get("app", {}).get("request_timeout_seconds", 12),
                scheduler_status=self.status,
                source_cooldown_seconds=self.source_cooldown_seconds,
                max_backoff_seconds=self.max_backoff_seconds,
                max_retries=self.max_retries_per_source,
            )

            run_stats = collector.run_collection_cycle(
                max_workers=self.config.get("app", {}).get("max_concurrent_workers", 10)
            )

            now = datetime.now(timezone.utc).isoformat()
            total_ingested = self.status.get("total_articles_ingested", 0) + run_stats.get("new_articles_inserted", 0)
            total_cycles = self.status.get("total_cycles_run", 0) + 1
            consecutive_empty = self.status.get("consecutive_empty_cycles", 0)
            if run_stats.get("new_articles_inserted", 0) == 0:
                consecutive_empty += 1
            else:
                consecutive_empty = 0

            self.status.update(
                last_cycle_completed=now,
                last_cycle_stats=run_stats,
                total_cycles_run=total_cycles,
                total_articles_ingested=total_ingested,
                consecutive_empty_cycles=consecutive_empty,
                is_fetching_now=False,
                error=None,
            )
            logger.info(
                f"Cycle #{total_cycles} done: {run_stats.get('new_articles_inserted', 0)} new, "
                f"{run_stats.get('duplicates_skipped', 0)} dupes, "
                f"{run_stats.get('sources_failed', 0)} failures"
            )
            return run_stats

        except Exception as e:
            err_msg = f"{type(e).__name__}: {e}"
            logger.error(f"Cycle failed: {err_msg}")
            self.status.update(is_fetching_now=False, error=err_msg)
            return None

        finally:
            self._fetch_lock.release()

    def is_stale(self) -> bool:
        """Returns True if last successful cycle is older than 2× the interval."""
        last = self.status.get("last_cycle_completed")
        if not last:
            return True
        try:
            from dateutil.parser import parse as dtparse
            last_dt = dtparse(last)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            threshold = datetime.now(timezone.utc) - timedelta(seconds=self.interval * 2)
            return last_dt < threshold
        except Exception:
            return True

    def get_time_until_next(self) -> Optional[int]:
        """Returns seconds until next scheduled fetch, or None."""
        nxt = self.status.get("next_scheduled")
        if not nxt:
            return None
        try:
            from dateutil.parser import parse as dtparse
            nxt_dt = dtparse(nxt)
            if nxt_dt.tzinfo is None:
                nxt_dt = nxt_dt.replace(tzinfo=timezone.utc)
            delta = (nxt_dt - datetime.now(timezone.utc)).total_seconds()
            return max(0, int(delta))
        except Exception:
            return None
