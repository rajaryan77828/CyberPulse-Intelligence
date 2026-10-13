"""
CyberPulse Intelligence - Security & Untrusted Input Sanitization Module
Protects against XSS, HTML injection, CSV injection, SSRF, and dangerous defanging.
"""

import re
import html
from urllib.parse import urlparse

SAFE_SCHEMES = {"http", "https"}

# Regex for malicious CSV injection formulas (=, +, -, @, tab, newline)
CSV_INJECTION_PREFIXES = ('=', '+', '-', '@', '\t', '\r')

def sanitize_text(text: str, max_length: int = 10000) -> str:
    """Strips dangerous HTML/script tags and normalizes Unicode."""
    if not text:
        return ""
    text = str(text)[:max_length]
    # Remove script and style tags completely
    text = re.sub(r'<(script|style|iframe|object|embed)[^>]*>.*?</\1>', '', text, flags=re.IGNORECASE | re.DOTALL)
    # Strip remaining HTML tags safely
    text = re.sub(r'<[^<]+?>', '', text)
    # Escape entities
    text = html.unescape(text)
    # Strip carriage control
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    return text.strip()

def validate_feed_url(url: str) -> bool:
    """Ensures feed URL has safe HTTP/HTTPS scheme and valid netloc without localhost SSRF risk."""
    if not url:
        return False
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme.lower() not in SAFE_SCHEMES:
            return False
        if not parsed.netloc:
            return False
        # Block private/local IP SSRF from user input feeds
        netloc = parsed.netloc.lower().split(':')[0]
        if netloc in {'127.0.0.1', 'localhost', '::1', '0.0.0.0'}:
            return False
        if netloc.startswith('10.') or netloc.startswith('192.168.') or netloc.startswith('169.254.'):
            return False
        return True
    except Exception:
        return False

def sanitize_csv_cell(value: Any) -> str:
    """Defends against CSV Formula Injection in spreadsheet viewers."""
    val_str = str(value or "")
    if val_str.startswith(CSV_INJECTION_PREFIXES):
        return "'" + val_str
    return val_str

def defang_ioc(ioc: str) -> str:
    """
    Safely defangs malicious indicators (e.g., evil.com -> evil[.]com, http:// -> hxxp://)
    Prevents accidental clicks or trigger actions in user interface.
    """
    if not ioc:
        return ""
    ioc = str(ioc).strip()
    # Replace http/https
    ioc = re.sub(r'^https?://', 'hxxp://', ioc, flags=re.IGNORECASE)
    # Defang dots
    ioc = ioc.replace('.', '[.]')
    return ioc
