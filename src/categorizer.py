"""
CyberPulse Intelligence - Transparent Cybersecurity Topic Categorizer
Categorizes articles using transparent, editable keyword rules.
Clearly labels inferred categories as automatic heuristic classifications.
"""

from typing import Tuple, List

KEYWORD_RULES = {
    "Ransomware": [
        "ransomware", "lockbit", "blackcat", "alphv", "akira", "clop", "play ransomware",
        "ransom demand", "decryptor", "extortion", "double extortion"
    ],
    "Malware": [
        "malware", "trojan", "stealer", "rat", "backdoor", "rootkit", "spyware",
        "keylogger", "loader", "infostealer", "lumma", "redline", "agent tesla", "botnet"
    ],
    "Data Breaches": [
        "data breach", "leak", "leaked", "records exposed", "compromised database",
        "unauthorized access", "exfiltration", "data theft", "stolen credentials", "pwned"
    ],
    "Exploits & PoC": [
        "proof of concept", "poc", "exploit", "0-day", "zero-day", "remote code execution",
        "rce", "privilege escalation", "heap overflow", "buffer overflow", "command injection"
    ],
    "Cloud Security": [
        "aws", "azure", "google cloud", "gcp", "s3 bucket", "iam misconfiguration",
        "cloud security", "kubernetes", "k8s", "docker container", "serverless", "cloud breach"
    ],
    "AI Security": [
        "llm", "prompt injection", "adversarial attack", "jailbreak", "ai safety",
        "artificial intelligence", "machine learning", "deepfake", "chatgpt", "openai model"
    ],
    "Phishing & Social Engineering": [
        "phishing", "spear phishing", "smishing", "vishing", "social engineering",
        "credential harvesting", "evilginx", "aitm", "bec", "business email compromise"
    ],
    "Privacy & Compliance": [
        "gdpr", "hipaa", "privacy fine", "surveillance", "data protection", "ftc",
        "sec enforcement", "compliance", "encryption mandate"
    ],
    "Network Security": [
        "ddos", "firewall", "router", "vpn vulnerability", "bgp hijack", "dns poisoning",
        "packet storm", "botnet flood", "lateral movement", "tls intercept"
    ],
    "Application Security": [
        "sql injection", "xss", "cross-site scripting", "csrf", "ssrf", "api security",
        "dependency vulnerability", "npm supply chain", "pypi package", "software supply chain"
    ],
    "Vendor Advisories": [
        "security update", "patch tuesday", "advisory", "security bulletin", "cisco advisory",
        "microsoft advisory", "fortinet patch", "firmware update"
    ],
    "Vulnerabilities": [
        "vulnerability", "cve-", "flaw", "security bug", "critical severity", "cvss"
    ],
    "Threat Intelligence": [
        "threat actor", "apt", "apt28", "apt29", "lazarus", "cyber espionage", "campaign",
        "indicators of compromise", "mitre att&ck", "tactics", "techniques"
    ]
}

def classify_article(title: str, summary: str, default_category: str = "Global News") -> Tuple[str, bool]:
    """
    Returns (category_name, is_heuristic_inferred)
    Matches highest frequency of specific security domain keywords.
    """
    combined = f"{title.lower()} {summary.lower()}"
    
    # Priority order matching
    match_scores = {}
    for cat, keywords in KEYWORD_RULES.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            match_scores[cat] = score

    if match_scores:
        top_cat = max(match_scores.items(), key=lambda x: x[1])[0]
        return top_cat, True
    
    return default_category, False
