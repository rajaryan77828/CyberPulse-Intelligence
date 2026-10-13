"""
CyberPulse Intelligence - Data Export & Backup Service
Safely exports filtered articles to CSV/JSON defending against CSV injection attacks.
"""

import json
import csv
import io
import os
from typing import List, Dict, Any
from src.security import sanitize_csv_cell

class ExportService:
    @staticmethod
    def export_to_csv(articles: List[Dict[str, Any]]) -> str:
        """Converts article records into CSV string with formula sanitization."""
        if not articles:
            return ""
        
        output = io.StringIO()
        fieldnames = [
            "id", "title", "source_name", "category", "published_at", 
            "first_seen_at", "canonical_url", "author", "cve_list", "summary"
        ]
        
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore', quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        
        for art in articles:
            row = {k: sanitize_csv_cell(art.get(k, "")) for k in fieldnames}
            writer.writerow(row)
            
        return output.getvalue()

    @staticmethod
    def export_to_json(articles: List[Dict[str, Any]]) -> str:
        """Exports articles into pretty formatted JSON without internal filesystem paths."""
        clean_records = []
        for a in articles:
            record = {
                "id": a.get("id"),
                "title": a.get("title"),
                "source": a.get("source_name"),
                "category": a.get("category"),
                "published_at": a.get("published_at"),
                "first_seen_at": a.get("first_seen_at"),
                "url": a.get("canonical_url"),
                "author": a.get("author"),
                "cve_list": a.get("cve_list", "").split(",") if a.get("cve_list") else [],
                "summary": a.get("summary")
            }
            clean_records.append(record)
        return json.dumps(clean_records, indent=2, ensure_ascii=False)
