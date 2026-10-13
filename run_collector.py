"""
CyberPulse Intelligence - Scheduled News Collector Runner
Invoked by update_news.bat or Windows Task Scheduler to run automated background syncs.
"""

import os
import sys
import yaml
from datetime import datetime, timezone

# Ensure project root is in python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.database import Database
from src.feed_collector import FeedCollector

def main():
    print("=" * 65)
    print(" CYBERPULSE INTELLIGENCE - AUTOMATED COLLECTION CYCLE")
    print(f" Timestamp: {datetime.now(timezone.utc).isoformat()} UTC")
    print("=" * 65)

    config_path = os.path.join(ROOT_DIR, "config.yaml")
    if not os.path.exists(config_path):
        print(f"[ERROR] Config file not found at {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    db_path = os.path.join(ROOT_DIR, config.get("app", {}).get("db_path", "data/cyberpulse.db"))
    db = Database(db_path=db_path)

    # Sync sources from config
    sources = config.get("sources", [])
    db.sync_sources_from_config(sources)
    print(f"[*] Loaded {len(sources)} source definitions from config.")

    user_agent = config.get("app", {}).get("user_agent", "CyberPulse-Intelligence/1.0")
    timeout = config.get("app", {}).get("request_timeout_seconds", 12)
    collector = FeedCollector(db=db, user_agent=user_agent, timeout=timeout)

    print("[*] Initiating concurrent feed ingestion cycle...")
    stats = collector.run_collection_cycle(max_workers=config.get("app", {}).get("max_concurrent_workers", 10))

    print("\n----------------- CYCLE SUMMARY -----------------")
    print(f" Duration:            {stats['duration_seconds']} seconds")
    print(f" Sources Polled:      {stats['sources_polled']}")
    print(f" Sources Succeeded:   {stats['sources_succeeded']}")
    print(f" Sources Failed:      {stats['sources_failed']}")
    print(f" Entries Processed:   {stats['entries_processed']}")
    print(f" New Articles Saved:  {stats['new_articles_inserted']}")
    print(f" Duplicates Skipped:  {stats['duplicates_skipped']}")
    print(f" Cycle Status:        {stats['status']}")
    print("-------------------------------------------------")

    overview = db.get_overview_statistics()
    print(f"\n[+] Total Persistent Articles in Database: {overview['total_articles']}")
    print(f"[+] Unique Articles Published Today:       {overview['published_today']}")
    print(f"[+] Unique Articles Collected Today:       {overview['collected_today']}")
    print(f"[+] Articles in Last 24 Hours:             {overview['published_last_24h']}")
    
    target = config.get("app", {}).get("daily_target", 1000)
    print(f"[+] Daily Target:                          {target}")
    if overview['published_today'] >= target:
        print("[+] DAILY TARGET ACHIEVED!")
    else:
        shortfall = target - overview['published_today']
        print(f"[!] Target not yet met. Measured shortfall: {shortfall} unique articles published today.")
        print("    (Note: Aggregator collects valid entries as publishers post them throughout the day)")

    print("\n[OK] Collection cycle completed safely.")

if __name__ == "__main__":
    main()
