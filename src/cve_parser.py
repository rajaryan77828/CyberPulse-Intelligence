"""
CyberPulse Intelligence - CVE Extraction and Linker
Validates CVE identifiers strictly against the CVE pattern and produces official NVD links.
"""

import re
from typing import List, Set

# Standard CVE regex pattern: CVE-YYYY-NNNN+
CVE_PATTERN = re.compile(r'\bCVE-(1999|20\d{2})-(\d{4,7})\b', re.IGNORECASE)

def extract_cves(text: str) -> List[str]:
    """Finds all distinct, valid CVE identifiers in text."""
    if not text:
        return []
    matches = CVE_PATTERN.findall(text)
    # Reconstruct canonical upper-case identifiers
    cves: Set[str] = set()
    for year, number in matches:
        cve_id = f"CVE-{year}-{number}".upper()
        cves.add(cve_id)
    return sorted(list(cves))

def get_nvd_url(cve_id: str) -> str:
    """Returns official NIST NVD vulnerability link."""
    return f"https://nvd.nist.gov/vuln/detail/{cve_id.upper()}"
