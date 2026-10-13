# 🛡️ CyberPulse Intelligence

> **Production-Quality Local Cybersecurity News Aggregation & Threat Intelligence Platform**  
> *100% Free Public Feeds • Zero API Keys • Zero Fabricated Metrics • Persistent SQLite Storage*

---

## 🌟 Overview

**CyberPulse Intelligence** aggregates, normalizes, deduplicates, and visualizes real-world cybersecurity threat intelligence from legitimate public RSS/Atom feeds and government security bulletins.

Built for security researchers, SOC analysts, and cyber journalists who require transparent, unadulterated intelligence data without relying on paid commercial APIs or vendor lock-in.

---

## 🏗️ Architecture & Features

- **Concurrent Feed Ingestion:** High-throughput async/threaded collection across 49+ pre-verified cybersecurity RSS/Atom feeds.
- **Canonical Deduplication:** Combines query-param stripping, URL canonicalization, and normalized title fingerprints to prevent duplicate stories across multiple syndication networks.
- **Persistent SQLite Storage:** Strict parameterized queries, indexes on canonical URLs, categories, timestamps, and bookmarks.
- **Threat Intelligence Extraction:**
  - Automated detection and linking of **CVE Identifiers** (`CVE-YYYY-NNNN+`) to official NIST NVD advisories.
  - Safe extraction and **IOC defanging** (`hxxp://` and `[.]`) for public IPv4s and file hashes.
- **Enterprise Dark SOC Dashboard:** Built with Streamlit and Plotly, delivering dark-themed metrics, category breakdowns, publisher trends, and search filters.
- **No Fabricated Data:** Reports actual unique articles published today vs. real articles collected today, with a clear shortfall indicator when publishers haven't released 1,000+ new stories in a single 24-hour cycle.
- **Windows Automation:** Pre-configured batch files for zero-friction setup, dashboard launch, automated Task Scheduler ingestion, and database backups.

---

## 📁 Project Structure

```text
D:\CyberPulse-Intelligence\
├── app.py                      # Main Streamlit SOC Dashboard
├── run_collector.py            # CLI feed ingestion runner
├── config.yaml                 # Central catalog of 49 verified public feeds
├── requirements.txt            # Python dependencies
├── README.md                   # System documentation
├── .gitignore                  # Git configuration
├── setup.bat                   # 1-click Windows environment setup
├── run.bat                     # Launch SOC dashboard locally
├── update_news.bat             # Background update script for Task Scheduler
├── backup.bat                  # Physical SQLite database backup utility
├── src\
│   ├── database.py             # SQLite persistence layer, migrations, WAL mode
│   ├── feed_collector.py       # Concurrent safe feed fetcher & parser
│   ├── security.py             # HTML/XSS sanitization, SSRF protection, CSV escaping
│   ├── deduplication.py        # URL canonicalizer & title fingerprinting
│   ├── cve_parser.py           # CVE regex extractor and NIST NVD linker
│   ├── ioc_parser.py           # IPv4 and file hash extractor with defanging
│   ├── categorizer.py          # Security domain classifier
│   └── export_service.py       # Safe CSV & JSON exporter
├── data\
│   └── cyberpulse.db           # Persistent SQLite database (WAL enabled)
├── logs\                       # Collection & update logs
├── backups\                    # Timestamped SQLite database snapshots
└── tests\
    └── test_cyberpulse.py      # Automated unit test suite
```

---

## 🚀 Quick Start (Windows)

### 1. Initial Setup
Double-click `setup.bat` or run:
```cmd
setup.bat
```
This verifies your Python 3.11+ environment, installs dependencies, initializes the database schema, and performs an initial collection cycle.

### 2. Launch SOC Dashboard
Double-click `run.bat` or execute:
```cmd
run.bat
```
Open your browser at `http://127.0.0.1:8501`.

---

## ⏰ Scheduling Automated Updates (Windows Task Scheduler)

To periodically refresh feeds throughout the day:

1. Open **Windows Task Scheduler** (`taskschd.msc`).
2. Click **Create Basic Task**.
3. Name it: `CyberPulse Intelligence Sync`.
4. Trigger: Choose **Daily**, set to repeat every **2 hours** (or preferred frequency).
5. Action: **Start a program**.
6. Program/script: `D:\CyberPulse-Intelligence\update_news.bat`.
7. Start in: `D:\CyberPulse-Intelligence\`.
8. Click **Finish**.

---

## 🧪 Running Automated Tests

Run the comprehensive unit test suite:
```cmd
python -m unittest discover -s tests -p "test_*.py" -v
```

All 7 core modules (database persistence, deduplication, CVE extraction, HTML sanitization, SSRF filters, IOC defanging, and data exports) are strictly verified.

---

## 🔒 Security & Privacy Notice

- Binds to `127.0.0.1` by default for local research.
- Untrusted feed content is stripped of scripts and HTML tags before rendering.
- Extracted IOCs are defanged to prevent accidental browser execution or drive-by navigation.
- No personal user credentials, API keys, or external accounts are stored or required.

---

## 👨‍💻 Author & Credits

- **Creator:** **RAJ ARYAN**
- **Website:** [rajaryan.neocities.org](https://rajaryan.neocities.org)
- **License:** MIT License (see [LICENSE](LICENSE))

