import requests
import feedparser
import sys

urls = [
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/"),
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews"),
    ("Krebs on Security", "https://krebsonsecurity.com/feed/"),
    ("SecurityWeek", "https://www.securityweek.com/feed/"),
    ("Dark Reading", "https://www.darkreading.com/rss.xml"),
    ("CISA Advisories", "https://www.cisa.gov/cybersecurity-advisories/all.xml"),
    ("Packet Storm", "https://packetstormsecurity.com/feeds/news/"),
    ("Naked Security Sophos", "https://nakedsecurity.sophos.com/feed/"),
    ("Kaspersky Securelist", "https://securelist.com/feed/"),
    ("Unit 42 Palo Alto", "https://unit42.paloaltonetworks.com/feed/"),
    ("Cisco Talos", "https://blog.talosintelligence.com/rss/"),
    ("Google Project Zero", "https://googleprojectzero.blogspot.com/feeds/posts/default?alt=rss"),
    ("Microsoft Security Blog", "https://www.microsoft.com/en-us/security/blog/feed/"),
    ("SANS Internet Storm Center", "https://isc.sans.edu/rssfeed.xml"),
    ("Trend Micro Research", "https://feeds.trendmicro.com/TrendMicroResearch"),
    ("Schneier on Security", "https://www.schneier.com/feed/atom/"),
    ("CERT-EU", "https://cert.europa.eu/feed/blog"),
    ("NVD Recent CVEs", "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml"),
    ("ZDI Zero Day Initiative", "https://www.zerodayinitiative.com/blog?format=rss"),
    ("Qualys Security Blog", "https://blog.qualys.com/feed")
]

headers = {
    'User-Agent': 'CyberPulse-Intelligence/1.0 (+https://github.com/cyberpulse; news-aggregator; bot)'
}

print(f"Testing {len(urls)} feeds...\n")
working = 0
for name, url in urls:
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            parsed = feedparser.parse(resp.content)
            entries = len(parsed.entries)
            print(f"[OK] {name:<28} | HTTP {resp.status_code} | Entries: {entries}")
            if entries > 0:
                working += 1
        else:
            print(f"[WARN] {name:<26} | HTTP {resp.status_code}")
    except Exception as e:
        print(f"[FAIL] {name:<26} | Error: {type(e).__name__} - {e}")

print(f"\nWorking feeds with entries: {working}/{len(urls)}")
