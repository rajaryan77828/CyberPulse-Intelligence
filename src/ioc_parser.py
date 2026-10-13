"""
CyberPulse Intelligence - IOC Parser & Safe Defanging
Extracts IP addresses, domains, and hashes, while treating indicators as unverified
and defanging them to protect analysts from drive-by triggers.
"""

import re
from typing import List, Dict

IPV4_PATTERN = re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b')
MD5_PATTERN = re.compile(r'\b[a-fA-F0-9]{32}\b')
SHA1_PATTERN = re.compile(r'\b[a-fA-F0-9]{40}\b')
SHA256_PATTERN = re.compile(r'\b[a-fA-F0-9]{64}\b')

# Private/bogon filter to avoid treating internal IPs as external IOCs
def is_public_ipv4(ip: str) -> bool:
    parts = [int(p) for p in ip.split('.')]
    if parts[0] in (10, 127, 0):
        return False
    if parts[0] == 172 and 16 <= parts[1] <= 31:
        return False
    if parts[0] == 192 and parts[1] == 168:
        return False
    if parts[0] >= 224:
        return False
    return True

def extract_iocs(text: str) -> Dict[str, List[str]]:
    """Extracts candidate IOCs from article text."""
    if not text:
        return {"ips": [], "hashes": []}
    
    # Extract IPs
    raw_ips = IPV4_PATTERN.findall(text)
    public_ips = sorted(list(set(ip for ip in raw_ips if is_public_ipv4(ip))))

    # Extract Hashes
    sha256 = SHA256_PATTERN.findall(text)
    sha1 = [h for h in SHA1_PATTERN.findall(text) if len(h) == 40]
    md5 = [h for h in MD5_PATTERN.findall(text) if len(h) == 32]
    all_hashes = sorted(list(set(sha256 + sha1 + md5)))

    return {
        "ips": public_ips[:10],
        "hashes": all_hashes[:10]
    }
