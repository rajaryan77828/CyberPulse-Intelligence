import urllib.request
import feedparser
import concurrent.futures
import time

feeds = [
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews", "Global News"),
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/", "Global News"),
    ("Krebs on Security", "https://krebsonsecurity.com/feed/", "Threat Intelligence"),
    ("Dark Reading", "https://www.darkreading.com/rss.xml", "Global News"),
    ("SecurityWeek", "https://www.securityweek.com/feed/", "Global News"),
    ("Schneier on Security", "https://www.schneier.com/feed/atom/", "Privacy & Compliance"),
    ("SANS ISC", "https://isc.sans.edu/rssfeed.xml", "Threat Intelligence"),
    ("CISA Advisories", "https://www.cisa.gov/cybersecurity-advisories/all.xml", "Vulnerabilities"),
    ("Packet Storm News", "https://packetstormsecurity.com/feeds/news/", "Exploits & PoC"),
    ("Packet Storm Files", "https://packetstormsecurity.com/feeds/files/", "Exploits & PoC"),
    ("Google Security Blog", "https://feeds.feedburner.com/GoogleOnlineSecurityBlog", "Cloud Security"),
    ("Google Project Zero", "https://googleprojectzero.blogspot.com/feeds/posts/default?alt=rss", "Vulnerabilities"),
    ("Microsoft Security", "https://www.microsoft.com/en-us/security/blog/feed/", "Vendor Advisories"),
    ("Cisco Talos", "https://blog.talosintelligence.com/rss/", "Threat Intelligence"),
    ("Kaspersky Securelist", "https://securelist.com/feed/", "Malware"),
    ("Unit 42 Palo Alto", "https://unit42.paloaltonetworks.com/feed/", "Threat Intelligence"),
    ("Trend Micro Research", "https://feeds.trendmicro.com/TrendMicroResearch", "Threat Intelligence"),
    ("Qualys Security Blog", "https://blog.qualys.com/feed", "Vulnerabilities"),
    ("ZDI Blog", "https://www.zerodayinitiative.com/blog?format=rss", "Vulnerabilities"),
    ("WeLiveSecurity ESET", "https://www.welivesecurity.com/en/rss/feed/", "Malware"),
    ("Naked Security", "https://nakedsecurity.sophos.com/feed/", "Global News"),
    ("Malwarebytes Labs", "https://www.malwarebytes.com/blog/feed/index.xml", "Malware"),
    ("Rapid7 Blog", "https://www.rapid7.com/blog/feed/", "Threat Intelligence"),
    ("Tripwire State of Security", "https://www.tripwire.com/state-of-security/feed", "Global News"),
    ("CERT-EU", "https://cert.europa.eu/feed/blog", "Vulnerabilities"),
    ("NCSC UK", "https://www.ncsc.gov.uk/api/1/services/v1/report-rss-feed.xml", "Threat Intelligence"),
    ("SentinelOne Labs", "https://www.sentinelone.com/labs/feed/", "Threat Intelligence"),
    ("Red Canary Blog", "https://redcanary.com/blog/feed/", "Threat Intelligence"),
    ("Mandiant Threat Research", "https://cloud.google.com/feeds/mandiant-threat-research.xml", "Threat Intelligence"),
    ("CrowdStrike Blog", "https://www.crowdstrike.com/blog/feed/", "Threat Intelligence")
]

headers = {
    'User-Agent': 'CyberPulse-Intelligence/1.0 (+https://github.com/cyberpulse; news-aggregator; bot)'
}

def test_feed(item):
    name, url, cat = item
    start = time.time()
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            code = response.getcode()
            content = response.read(1024 * 512) # 512KB max
            parsed = feedparser.parse(content)
            entries = len(parsed.entries)
            dur = time.time() - start
            return {"name": name, "url": url, "cat": cat, "status": code, "entries": entries, "time": round(dur, 2), "ok": entries > 0}
    except Exception as e:
        dur = time.time() - start
        return {"name": name, "url": url, "cat": cat, "status": 0, "entries": 0, "time": round(dur, 2), "error": str(e), "ok": False}

if __name__ == "__main__":
    print(f"Testing {len(feeds)} candidate feeds with concurrent pool...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        for res in executor.map(test_feed, feeds):
            status_str = f"HTTP {res.get('status', 'ERR')}"
            entries_str = f"{res.get('entries', 0)} entries"
            err_str = f" - {res.get('error')}" if 'error' in res else ""
            print(f"[{'PASS' if res['ok'] else 'FAIL'}] {res['name']:<28} | {status_str:<9} | {entries_str:<12} | {res['time']}s{err_str}")
            results.append(res)
    
    total_working = sum(1 for r in results if r["ok"])
    total_entries = sum(r["entries"] for r in results if r["ok"])
    print(f"\nSummary: {total_working}/{len(feeds)} feeds verified working! Total initial entries available: {total_entries}")
