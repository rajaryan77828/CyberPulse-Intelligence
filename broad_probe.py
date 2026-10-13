import urllib.request
import feedparser
import concurrent.futures
import time

more_feeds = [
    # General & News
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews", "Global News"),
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/", "Global News"),
    ("Krebs on Security", "https://krebsonsecurity.com/feed/", "Threat Intelligence"),
    ("Dark Reading", "https://www.darkreading.com/rss.xml", "Global News"),
    ("SecurityWeek", "https://www.securityweek.com/feed/", "Global News"),
    ("Schneier on Security", "https://www.schneier.com/feed/atom/", "Privacy & Compliance"),
    ("SANS ISC", "https://isc.sans.edu/rssfeed.xml", "Threat Intelligence"),
    ("CISA Advisories", "https://www.cisa.gov/cybersecurity-advisories/all.xml", "Vulnerabilities"),
    ("Google Security Blog", "https://feeds.feedburner.com/GoogleOnlineSecurityBlog", "Cloud Security"),
    ("Google Project Zero", "https://googleprojectzero.blogspot.com/feeds/posts/default?alt=rss", "Vulnerabilities"),
    ("Microsoft Security", "https://www.microsoft.com/en-us/security/blog/feed/", "Vendor Advisories"),
    ("Cisco Talos", "https://blog.talosintelligence.com/rss/", "Threat Intelligence"),
    ("Kaspersky Securelist", "https://securelist.com/feed/", "Malware"),
    ("Unit 42 Palo Alto", "https://unit42.paloaltonetworks.com/feed/", "Threat Intelligence"),
    ("ZDI Blog", "https://www.zerodayinitiative.com/blog?format=rss", "Vulnerabilities"),
    ("WeLiveSecurity ESET", "https://www.welivesecurity.com/en/rss/feed/", "Malware"),
    ("Malwarebytes Labs", "https://www.malwarebytes.com/blog/feed/index.xml", "Malware"),
    ("Tripwire State of Security", "https://www.tripwire.com/state-of-security/feed", "Global News"),
    ("NCSC UK", "https://www.ncsc.gov.uk/api/1/services/v1/report-rss-feed.xml", "Threat Intelligence"),
    ("SentinelOne Labs", "https://www.sentinelone.com/labs/feed/", "Threat Intelligence"),
    ("Red Canary Blog", "https://redcanary.com/blog/feed/", "Threat Intelligence"),
    ("CrowdStrike Blog", "https://www.crowdstrike.com/blog/feed/", "Threat Intelligence"),
    
    # Additional high-volume & specialized public security feeds
    ("The Register Security", "https://www.theregister.com/security/headlines.atom", "Global News"),
    ("Threatpost Archive/Feed", "https://threatpost.com/feed/", "Threat Intelligence"),
    ("Help Net Security", "https://www.helpnetsecurity.com/feed/", "Global News"),
    ("Security Affairs", "https://securityaffairs.com/feed", "Global News"),
    ("Troy Hunt Blog", "https://www.troyhunt.com/rss/", "Data Breaches"),
    ("Graham Cluley", "https://grahamcluley.com/feed/", "Global News"),
    ("NVD Recent Vulnerabilities", "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml", "CVE & NVD"),
    ("NVD Analyzed Vulnerabilities", "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss-analyzed.xml", "CVE & NVD"),
    ("AlienVault OTX Pulse", "https://otx.alienvault.com/api/v1/pulses/subscribed?format=rss", "Threat Intelligence"),
    ("Exploit-DB RSS", "https://www.exploit-db.com/rss.xml", "Exploits & PoC"),
    ("Packet Storm Security", "https://rss.packetstormsecurity.com/news/", "Exploits & PoC"),
    ("Packet Storm Files RSS", "https://rss.packetstormsecurity.com/files/", "Exploits & PoC"),
    ("Full Disclosure List", "https://seclists.org/rss/fulldisclosure.rss", "Vulnerabilities"),
    ("Bugtraq SecLists", "https://seclists.org/rss/bugtraq.rss", "Vulnerabilities"),
    ("OSS Security SecLists", "https://seclists.org/rss/oss-sec.rss", "Application Security"),
    ("Nmap Announcements", "https://seclists.org/rss/nmap-announce.rss", "Network Security"),
    ("CERT Coordination Center", "https://www.kb.cert.org/vuls/atom/feed.xml", "Vulnerabilities"),
    ("US-CERT Current Activity", "https://www.cisa.gov/uscert/ncas/current-activity.xml", "Threat Intelligence"),
    ("CISA ICS Advisories", "https://www.cisa.gov/cybersecurity-advisories/ics-advisories.xml", "Vulnerabilities"),
    ("CISA ICS Medical", "https://www.cisa.gov/cybersecurity-advisories/ics-medical-advisories.xml", "Vulnerabilities"),
    ("BleepingComputer Ransomware", "https://www.bleepingcomputer.com/feed/ransomware/", "Ransomware"),
    ("BleepingComputer Malware", "https://www.bleepingcomputer.com/feed/malware/", "Malware"),
    ("BleepingComputer Security", "https://www.bleepingcomputer.com/feed/security/", "Global News"),
    ("Naked Security Sophos Atom", "https://news.sophos.com/en-us/category/serious-security/feed/", "Threat Intelligence"),
    ("SophosLabs Uncut", "https://news.sophos.com/en-us/category/threat-research/feed/", "Malware"),
    ("BlackBerry Threat Vector", "https://blogs.blackberry.com/en/rss", "Threat Intelligence"),
    ("Tenable Blog", "https://www.tenable.com/blog/feed", "Vulnerabilities"),
    ("Rapid7 Research", "https://www.rapid7.com/blog/categories/vulnerabilities-threats/feed/", "Vulnerabilities"),
    ("Check Point Research", "https://research.checkpoint.com/feed/", "Threat Intelligence"),
    ("Recorded Future News", "https://therecord.media/feed", "Data Breaches"),
    ("Infosecurity Magazine", "https://www.infosecurity-magazine.com/rss/news/", "Global News"),
    ("Hacker Combat", "https://hackercombat.com/feed/", "Global News"),
    ("GBHackers on Security", "https://gbhackers.com/feed/", "Vulnerabilities"),
    ("Cyber Defense Magazine", "https://www.cyberdefensemagazine.com/feed/", "Global News"),
    ("CyberScoop", "https://cyberscoop.com/feed/", "Global News"),
    ("The Cyberwire", "https://thecyberwire.com/feeds/rss.xml", "Threat Intelligence"),
    ("Cybercrime Magazine", "https://cybersecurityventures.com/feed/", "Threat Intelligence"),
    ("Darknet", "https://www.darknet.org.uk/feed/", "Exploits & PoC"),
    ("ZeroDay Lab", "https://www.zerodaylab.com/feed/", "Vulnerabilities"),
    ("Bitdefender Labs", "https://www.bitdefender.com/blog/api/rss/labs/", "Threat Intelligence"),
    ("Cloudflare Security Blog", "https://blog.cloudflare.com/tag/security/rss/", "Cloud Security"),
    ("AWS Security Blog", "https://aws.amazon.com/blogs/security/feed/", "Cloud Security"),
    ("GitHub Security Blog", "https://github.blog/tag/security/feed/", "Application Security"),
    ("Fortinet FortiGuard Labs", "https://www.fortinet.com/blog/threat-research/rss", "Threat Intelligence"),
    ("Symantec Enterprise Blogs", "https://symantec-enterprise-blogs.security.com/blogs/threat-intelligence/rss", "Threat Intelligence"),
    ("F-Secure / WithSecure", "https://labs.withsecure.com/publications.rss", "Threat Intelligence")
]

headers = {
    'User-Agent': 'CyberPulse-Intelligence/1.0 (Windows NT 10.0; Win64; x64; +https://github.com/cyberpulse)'
}

def probe(item):
    name, url, cat = item
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            code = response.getcode()
            body = response.read(1024 * 1024) # up to 1MB
            parsed = feedparser.parse(body)
            num = len(parsed.entries)
            dt = round(time.time() - t0, 2)
            return {"name": name, "url": url, "cat": cat, "code": code, "entries": num, "dt": dt, "ok": num > 0}
    except Exception as e:
        dt = round(time.time() - t0, 2)
        return {"name": name, "url": url, "cat": cat, "code": 0, "entries": 0, "dt": dt, "err": str(e), "ok": False}

if __name__ == "__main__":
    print(f"Testing {len(more_feeds)} candidate feeds with 12 workers...")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        for r in executor.map(probe, more_feeds):
            res_str = f"PASS ({r['entries']} entries)" if r['ok'] else f"FAIL ({r.get('err', '0 entries')[:35]})"
            print(f"{r['name']:<30} | {res_str:<38} | {r['dt']}s")
            results.append(r)
    
    valid = [r for r in results if r["ok"]]
    total_entries = sum(r["entries"] for r in valid)
    print(f"\n==========================================")
    print(f"Valid Sources: {len(valid)} / {len(more_feeds)}")
    print(f"Total Available Entries in valid feeds: {total_entries}")
    print(f"==========================================")
