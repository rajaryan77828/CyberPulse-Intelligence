"""
CyberPulse Intelligence - Deduplication & Fingerprinting Engine
Uses URL canonicalization, title normalization, and SHA-256 content hashes.
"""

import re
import hashlib
from urllib.parse import urlparse, parse_qsl, urlunparse, urlencode

# Common tracking query params to strip for canonical URL
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'fbclid', 'gclid', 'ref', 'source', 'rss', 'feed', 'feedname'
}

def canonicalize_url(url: str) -> str:
    """Cleans URLs by removing session tokens, UTM params, trailing slashes, fragments."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        clean_scheme = parsed.scheme.lower()
        clean_netloc = parsed.netloc.lower()
        if clean_netloc.startswith("www."):
            clean_netloc = clean_netloc[4:]
        
        # Filter tracking query parameters
        query_pairs = parse_qsl(parsed.query, keep_blank_values=False)
        filtered_pairs = [
            (k, v) for k, v in query_pairs 
            if k.lower() not in TRACKING_PARAMS
        ]
        clean_query = urlencode(sorted(filtered_pairs))
        
        # Clean path: strip trailing slash unless root
        clean_path = parsed.path.rstrip('/')
        if not clean_path:
            clean_path = '/'
            
        return urlunparse((clean_scheme, clean_netloc, clean_path, '', clean_query, ''))
    except Exception:
        return url.strip()

def compute_title_fingerprint(title: str) -> str:
    """Normalizes title into an alphanumeric lowercase fingerprint."""
    if not title:
        return ""
    # Lowercase and strip punctuation
    clean = re.sub(r'[^\w\s]', '', title.lower())
    # Collapse multiple whitespaces
    tokens = clean.split()
    # Strip common fluff words if title is long
    fluff = {'a', 'an', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'with', 'by'}
    meaningful = [t for t in tokens if t not in fluff] or tokens
    return " ".join(meaningful)

def compute_content_hash(title: str, summary: str, url: str) -> str:
    """Computes SHA-256 fingerprint for article payload."""
    payload = f"{title.strip().lower()}|{summary.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(payload.encode('utf-8', errors='ignore')).hexdigest()
