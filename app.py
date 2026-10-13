"""
CyberPulse Intelligence - Enterprise Cybersecurity News & Threat Intelligence Platform
Modern, high-impact news portal styling inspired by top global news publications (The Verge, Reuters, BleepingComputer, DarkReading).
Features:
- Breaking News Ticker with smooth animations
- Hero / Featured Top Stories Grid with editorial imagery
- Multi-column card layout with hover animations and category badges
- CVE & NVD intelligence chips linking directly to NIST
- Fast filtering, multi-category routing, bookmarks, read later
- Feed health diagnostics and CSV/JSON exports
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import sys
import yaml
from datetime import datetime, timezone

# Ensure project root is in python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.database import Database
from src.feed_collector import FeedCollector
from src.export_service import ExportService
from src.cve_parser import get_nvd_url
from src.security import defang_ioc

# Page Configuration
st.set_page_config(
    page_title="CyberPulse Intelligence | Threat News Network",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom High-End News Magazine Styling with Animations
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .stApp {
        background-color: #07090e;
        color: #f1f5f9;
    }

    /* Top Breaking News Banner */
    .ticker-wrap {
        background: linear-gradient(90deg, #1e1b4b 0%, #0f172a 100%);
        border: 1px solid #312e81;
        border-radius: 8px;
        padding: 10px 16px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);
    }
    .ticker-badge {
        background-color: #ef4444;
        color: #ffffff;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.1em;
        padding: 4px 10px;
        border-radius: 4px;
        text-transform: uppercase;
        margin-right: 14px;
        animation: pulse 2s infinite;
        white-space: nowrap;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.85; transform: scale(0.98); }
    }
    .ticker-text {
        font-size: 13.5px;
        color: #cbd5e1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Hero / Featured Card */
    .hero-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 12px;
        overflow: hidden;
        margin-bottom: 28px;
        transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.3s ease, box-shadow 0.3s ease;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
    }
    .hero-card:hover {
        transform: translateY(-4px);
        border-color: #38bdf8;
        box-shadow: 0 20px 35px -10px rgba(56, 189, 248, 0.2);
    }
    .hero-img-wrap {
        height: 340px;
        width: 100%;
        overflow: hidden;
        position: relative;
        background-color: #1e293b;
    }
    .hero-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        transition: transform 0.5s ease;
    }
    .hero-card:hover .hero-img {
        transform: scale(1.03);
    }
    .hero-content {
        padding: 24px 28px;
    }
    .hero-title {
        font-size: 24px;
        font-weight: 800;
        line-height: 1.3;
        color: #f8fafc;
        margin-bottom: 12px;
        text-decoration: none;
        display: block;
    }
    .hero-title:hover {
        color: #38bdf8;
    }

    /* Magazine Grid Cards */
    .news-card {
        background-color: #0d131f;
        border: 1px solid #1e293b;
        border-radius: 10px;
        overflow: hidden;
        height: 100%;
        display: flex;
        flex-direction: column;
        transition: all 0.28s ease;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        margin-bottom: 20px;
    }
    .news-card:hover {
        transform: translateY(-5px);
        border-color: #0ea5e9;
        box-shadow: 0 12px 28px -5px rgba(14, 165, 233, 0.25);
    }
    .card-thumb-wrap {
        height: 180px;
        width: 100%;
        overflow: hidden;
        background-color: #1a2234;
        position: relative;
    }
    .card-thumb {
        width: 100%;
        height: 100%;
        object-fit: cover;
        transition: transform 0.4s ease;
    }
    .news-card:hover .card-thumb {
        transform: scale(1.05);
    }
    .card-body {
        padding: 16px 18px;
        display: flex;
        flex-direction: column;
        flex-grow: 1;
    }
    .card-title {
        font-size: 16px;
        font-weight: 700;
        line-height: 1.4;
        color: #f1f5f9;
        text-decoration: none;
        margin-bottom: 10px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .card-title:hover {
        color: #38bdf8;
    }
    .card-excerpt {
        color: #94a3b8;
        font-size: 13px;
        line-height: 1.5;
        margin-bottom: 14px;
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;
        flex-grow: 1;
    }
    .card-meta {
        font-size: 11.5px;
        color: #64748b;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* Badges */
    .badge-category {
        background: rgba(14, 165, 233, 0.15);
        color: #38bdf8;
        border: 1px solid rgba(14, 165, 233, 0.3);
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 10.5px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .badge-source {
        background: #1e293b;
        color: #cbd5e1;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 500;
    }
    .badge-cve {
        background: rgba(239, 68, 68, 0.2);
        color: #fca5a5;
        border: 1px solid rgba(239, 68, 68, 0.4);
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        text-decoration: none;
        margin-right: 4px;
        display: inline-block;
    }
    .badge-cve:hover {
        background: rgba(239, 68, 68, 0.4);
        color: #ffffff;
    }

    /* Stat Cards */
    .stat-box {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 16px 20px;
        text-align: left;
        position: relative;
        overflow: hidden;
    }
    .stat-box::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #0ea5e9, #6366f1);
    }
    .stat-num {
        font-size: 30px;
        font-weight: 800;
        color: #f8fafc;
        line-height: 1;
        margin-bottom: 4px;
    }
    .stat-lbl {
        font-size: 12px;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Load Database and Configuration
@st.cache_resource
def get_db():
    config_path = os.path.join(ROOT_DIR, "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    db_path = os.path.join(ROOT_DIR, config.get("app", {}).get("db_path", "data/cyberpulse.db"))
    return Database(db_path=db_path), config

db, config = get_db()
stats = db.get_overview_statistics()
DAILY_TARGET = config.get("app", {}).get("daily_target", 1000)

# Sidebar
st.sidebar.markdown("""
<div style="text-align: center; padding-bottom: 15px;">
    <div style="font-size: 26px; font-weight: 800; color: #38bdf8; letter-spacing: -0.02em;">CYBERPULSE</div>
    <div style="font-size: 11px; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.12em;">Threat News Network</div>
    <div style="margin-top: 8px; font-size: 12px; color: #cbd5e1;">
        Created by <b style="color: #f8fafc;">RAJ ARYAN</b><br>
        <a href="https://rajaryan.neocities.org" target="_blank" style="color: #38bdf8; text-decoration: none; font-size: 11.5px; font-weight: 600;">rajaryan.neocities.org ↗</a>
    </div>
</div>
""", unsafe_allow_html=True)

NAV_SECTIONS = [
    "🔥 Top Stories",
    "📰 All News Wire",
    "⚠️ Vulnerabilities",
    "🛡️ CVE & NVD Intel",
    "💀 Ransomware",
    "🦠 Malware",
    "🔓 Data Breaches",
    "🎯 Threat Intelligence",
    "⚡ Exploits & PoC",
    "☁️ Cloud Security",
    "💻 Application Security",
    "🌐 Network Security",
    "🤖 AI Security",
    "🎣 Phishing & Social Engineering",
    "⚖️ Privacy & Compliance",
    "📦 Vendor Advisories",
    "⭐ Saved Bookmarks",
    "📌 Read Later Queue",
    "📡 Sources & Feed Health",
    "📊 Newsroom Analytics",
    "💾 Data Exports",
    "⚙️ Portal Settings"
]

selected_nav = st.sidebar.radio("Browse Channels", NAV_SECTIONS, index=0)

# Local System Time
now_local = datetime.now()
st.sidebar.markdown("---")
st.sidebar.markdown(f"**Local Newsroom Time:**  \n`{now_local.strftime('%A, %b %d, %Y - %H:%M:%S')}`")

# Sync Button in Sidebar
if st.sidebar.button("⚡ Fetch Latest Wire Feeds", use_container_width=True):
    with st.sidebar.status("Refreshing live threat feeds...", expanded=True) as status:
        collector = FeedCollector(
            db=db,
            user_agent=config.get("app", {}).get("user_agent", "CyberPulse-Intelligence/1.0"),
            timeout=config.get("app", {}).get("request_timeout_seconds", 12)
        )
        run_stats = collector.run_collection_cycle(max_workers=config.get("app", {}).get("max_concurrent_workers", 10))
        status.update(label=f"Done! Ingested {run_stats['new_articles_inserted']} fresh stories.", state="complete", expanded=False)
    st.sidebar.success(f"Polled {run_stats['sources_polled']} feeds in {run_stats['duration_seconds']}s")
    st.rerun()

# Breaking Ticker Bar
latest_ticker_items, _ = db.get_articles_filtered(limit=5, sort_by="newest")
if latest_ticker_items:
    ticker_text = " • ".join([f"<b>[{item['source_name']}]</b> {item['title']}" for item in latest_ticker_items])
    st.markdown(f"""
    <div class="ticker-wrap">
        <span class="ticker-badge">LIVE INTEL WIRE</span>
        <div class="ticker-text">{ticker_text}</div>
    </div>
    """, unsafe_allow_html=True)

# Helper to render a card
def render_news_card(art):
    img = art.get('image_url') or "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=600&auto=format&fit=crop&q=80"
    pub_display = (art.get('published_at') or "Recent").split("T")[0]
    
    cve_chips = ""
    if art.get("cve_list"):
        for cve in art["cve_list"].split(",")[:2]:
            if cve:
                cve_chips += f'<a class="badge-cve" href="{get_nvd_url(cve)}" target="_blank">{cve}</a>'
    
    st.markdown(f"""
    <div class="news-card">
        <div class="card-thumb-wrap">
            <img class="card-thumb" src="{img}" alt="{art['title']}" loading="lazy" onerror="this.src='https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=600&auto=format&fit=crop&q=80';"/>
        </div>
        <div class="card-body">
            <div class="card-meta">
                <span class="badge-category">{art['category']}</span>
                <span style="color: #94a3b8; font-size: 11px;">{pub_display}</span>
            </div>
            <a class="card-title" href="{art['canonical_url']}" target="_blank">{art['title']}</a>
            <div class="card-excerpt">{art['summary']}</div>
            <div style="margin-top: auto; display: flex; justify-content: space-between; align-items: center; padding-top: 8px; border-top: 1px solid #1e293b;">
                <span class="badge-source">{art['source_name']}</span>
                <div>{cve_chips}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Action buttons
    ac1, ac2, ac3 = st.columns([1, 1, 1])
    with ac1:
        lbl_bm = "⭐" if art["bookmarked"] else "☆ Save"
        if st.button(lbl_bm, key=f"bm_{art['id']}"):
            db.update_article_flag(art["id"], "bookmarked", 0 if art["bookmarked"] else 1)
            st.rerun()
    with ac2:
        lbl_rl = "🔖" if art["read_later"] else "📌 Queue"
        if st.button(lbl_rl, key=f"rl_{art['id']}"):
            db.update_article_flag(art["id"], "read_later", 0 if art["read_later"] else 1)
            st.rerun()
    with ac3:
        st.markdown(f"<a href='{art['canonical_url']}' target='_blank' style='color: #38bdf8; font-size: 12px; font-weight: 600; text-decoration: none; display: inline-block; padding-top: 4px;'>Read ↗</a>", unsafe_allow_html=True)

# ==========================================================
# PAGE ROUTING
# ==========================================================

if selected_nav == "🔥 Top Stories":
    # Hero Section - Top Lead Story
    top_lead, _ = db.get_articles_filtered(limit=1, sort_by="newest")
    if top_lead:
        lead = top_lead[0]
        lead_img = lead.get("image_url") or "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=1200&auto=format&fit=crop&q=80"
        lead_cves = ""
        if lead.get("cve_list"):
            for cve in lead["cve_list"].split(",")[:3]:
                if cve:
                    lead_cves += f'<a class="badge-cve" href="{get_nvd_url(cve)}" target="_blank">{cve}</a> '

        st.markdown(f"""
        <div class="hero-card">
            <div class="hero-img-wrap">
                <img class="hero-img" src="{lead_img}" alt="{lead['title']}"/>
                <div style="position: absolute; bottom: 16px; left: 24px; background: rgba(0, 0, 0, 0.7); backdrop-filter: blur(8px); padding: 6px 14px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.1);">
                    <span class="badge-category">{lead['category']}</span>
                    <span style="color: #f1f5f9; font-size: 12px; font-weight: 600; margin-left: 10px;">{lead['source_name']}</span>
                </div>
            </div>
            <div class="hero-content">
                <a class="hero-title" href="{lead['canonical_url']}" target="_blank">{lead['title']}</a>
                <div style="color: #94a3b8; font-size: 15px; line-height: 1.6; margin-bottom: 14px;">
                    {lead['summary'][:320]}...
                </div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>{lead_cves}</div>
                    <a href="{lead['canonical_url']}" target="_blank" style="background: #0284c7; color: white; padding: 8px 18px; border-radius: 6px; text-decoration: none; font-size: 13px; font-weight: 700;">Full Coverage ↗</a>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Key Statistics Header Row
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-num">{stats['total_articles']:,}</div>
            <div class="stat-lbl">Stored Intelligence Records</div>
        </div>
        """, unsafe_allow_html=True)
    with s2:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-num" style="color: #38bdf8;">{stats['published_last_24h']:,}</div>
            <div class="stat-lbl">Disclosed in Last 24h</div>
        </div>
        """, unsafe_allow_html=True)
    with s3:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-num" style="color: #a855f7;">{stats['sources_enabled']}</div>
            <div class="stat-lbl">Active News Desks</div>
        </div>
        """, unsafe_allow_html=True)
    with s4:
        st.markdown(f"""
        <div class="stat-box">
            <div class="stat-num" style="color: #10b981;">{stats['published_today']:,} / {DAILY_TARGET:,}</div>
            <div class="stat-lbl">Today's Unique Releases</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 25px;'></div>", unsafe_allow_html=True)

    # Magazine Multi-Column Grid
    st.markdown("### ⚡ Latest Dispatches & Vulnerability Bulletins")
    articles, _ = db.get_articles_filtered(limit=18, offset=1, sort_by="newest")

    # Render in 3-column newspaper grid
    for i in range(0, len(articles), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(articles):
                with cols[j]:
                    render_news_card(articles[i + j])

elif selected_nav in [
    "📰 All News Wire", "⚠️ Vulnerabilities", "🛡️ CVE & NVD Intel", "💀 Ransomware",
    "🦠 Malware", "🔓 Data Breaches", "🎯 Threat Intelligence", "⚡ Exploits & PoC",
    "☁️ Cloud Security", "💻 Application Security", "🌐 Network Security", "🤖 AI Security",
    "🎣 Phishing & Social Engineering", "⚖️ Privacy & Compliance", "📦 Vendor Advisories",
    "⭐ Saved Bookmarks", "📌 Read Later Queue"
]:
    # Determine channel filters
    is_bookmarks = (selected_nav == "⭐ Saved Bookmarks")
    is_read_later = (selected_nav == "📌 Read Later Queue")
    
    cat_mapping = {
        "⚠️ Vulnerabilities": "Vulnerabilities",
        "🛡️ CVE & NVD Intel": "CVE & NVD",
        "💀 Ransomware": "Ransomware",
        "🦠 Malware": "Malware",
        "🔓 Data Breaches": "Data Breaches",
        "🎯 Threat Intelligence": "Threat Intelligence",
        "⚡ Exploits & PoC": "Exploits & PoC",
        "☁️ Cloud Security": "Cloud Security",
        "💻 Application Security": "Application Security",
        "🌐 Network Security": "Network Security",
        "🤖 AI Security": "AI Security",
        "🎣 Phishing & Social Engineering": "Phishing & Social Engineering",
        "⚖️ Privacy & Compliance": "Privacy & Compliance",
        "📦 Vendor Advisories": "Vendor Advisories"
    }
    category_filter = cat_mapping.get(selected_nav)

    # Header
    st.markdown(f"<h1 style='font-size: 28px; font-weight: 800; margin-bottom: 4px;'>{selected_nav}</h1>", unsafe_allow_html=True)
    st.caption("Curated, verified cybersecurity intelligence stream from authorized public publishers.")

    # Search & Filtering Bar
    f1, f2, f3 = st.columns([3, 2, 2])
    with f1:
        search_term = st.text_input("🔍 Search headlines & summaries...", placeholder="Search keywords, CVEs, malware families...")
    with f2:
        sources_avail = ["All Publications"] + [s["name"] for s in db.get_sources_inventory()]
        sel_source = st.selectbox("Filter Source", sources_avail)
        sel_src_id = None
        if sel_source != "All Publications":
            for s in db.get_sources_inventory():
                if s["name"] == sel_source:
                    sel_src_id = s["id"]
                    break
    with f3:
        sort_mode = st.selectbox("Sort By", ["Newest Published", "Oldest Published", "Newest Ingested", "Publication Name"])
        sort_map = {
            "Newest Published": "newest",
            "Oldest Published": "oldest",
            "Newest Ingested": "collected_newest",
            "Publication Name": "source"
        }

    # Advanced filter expander
    with st.expander("⚙️ Refine Feed Parameters", expanded=False):
        cve_filter = st.text_input("Target CVE Identifier", placeholder="e.g. CVE-2026-")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            filter_today = st.checkbox("Published Today Only", value=False)
        with col_c2:
            filter_unread = st.checkbox("Unread Only", value=False)

    # Pagination
    PAGE_SIZE = 12
    if "wire_page" not in st.session_state:
        st.session_state.wire_page = 1

    records, total_count = db.get_articles_filtered(
        category=category_filter,
        source_id=sel_src_id,
        search_query=search_term,
        cve_filter=cve_filter if 'cve_filter' in locals() and cve_filter else None,
        only_bookmarked=is_bookmarks,
        only_read_later=is_read_later,
        only_unread=filter_unread if 'filter_unread' in locals() else False,
        published_today=filter_today if 'filter_today' in locals() else False,
        sort_by=sort_map[sort_mode],
        offset=(st.session_state.wire_page - 1) * PAGE_SIZE,
        limit=PAGE_SIZE
    )

    total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    st.markdown(f"<div style='color: #94a3b8; font-size: 13px; margin-bottom: 20px;'>Found <b>{total_count:,}</b> articles • Page <b>{st.session_state.wire_page}</b> of <b>{total_pages}</b></div>", unsafe_allow_html=True)

    if not records:
        st.info("No intelligence articles matched your active search or filter criteria.")
    else:
        for i in range(0, len(records), 3):
            cols = st.columns(3)
            for j in range(3):
                if i + j < len(records):
                    with cols[j]:
                        render_news_card(records[i + j])

    # Pagination buttons
    if total_pages > 1:
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
        p1, p2, p3 = st.columns([1, 2, 1])
        with p1:
            if st.button("⬅ Previous Page", disabled=(st.session_state.wire_page <= 1), use_container_width=True):
                st.session_state.wire_page -= 1
                st.rerun()
        with p2:
            st.markdown(f"<div style='text-align: center; color: #94a3b8; padding-top: 8px;'>Page {st.session_state.wire_page} of {total_pages}</div>", unsafe_allow_html=True)
        with p3:
            if st.button("Next Page ➡", disabled=(st.session_state.wire_page >= total_pages), use_container_width=True):
                st.session_state.wire_page += 1
                st.rerun()

elif selected_nav == "📡 Sources & Feed Health":
    st.markdown("<h1 style='font-size: 28px; font-weight: 800;'>📡 Source Registry & Live Health Monitor</h1>", unsafe_allow_html=True)
    st.markdown("Real-time feed verification, latency tracking, and error logs across all authorized security endpoints.")

    sources = db.get_sources_inventory()
    h1, h2, h3 = st.columns(3)
    with h1:
        st.metric("Total Configured Sources", len(sources))
    with h2:
        active = sum(1 for s in sources if s['enabled'])
        st.metric("Active Live Endpoints", active)
    with h3:
        failing = sum(1 for s in sources if s['consecutive_failures'] > 0)
        st.metric("Endpoints with Errors", failing)

    st.markdown("### Source Roster")
    for s in sources:
        with st.expander(f"🌐 {s['name']} — {s['category']} ({'Active' if s['enabled'] else 'Paused'})"):
            st.write(f"**Feed Endpoint:** `{s['feed_url']}`")
            st.write(f"**Official Website:** [{s['site_url']}]({s['site_url']})")
            st.write(f"**Last Sync Success:** `{s['last_success'] or 'Never'}`")
            if s["last_error"]:
                st.error(f"Error Alert: {s['last_error']}")
            
            tgl_btn = "Pause Source" if s["enabled"] else "Activate Source"
            if st.button(tgl_btn, key=f"tgl_{s['id']}"):
                db.set_source_enabled(s["id"], not s["enabled"])
                st.rerun()

elif selected_nav == "📊 Newsroom Analytics":
    st.markdown("<h1 style='font-size: 28px; font-weight: 800;'>📊 Newsroom Analytics & Trend Intelligence</h1>", unsafe_allow_html=True)
    
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.subheader("Category Distribution")
        if stats["category_counts"]:
            df_cat = pd.DataFrame(stats["category_counts"])
            fig_cat = px.pie(df_cat, names="category", values="count", hole=0.5, color_discrete_sequence=px.colors.sequential.Tealgrn)
            fig_cat.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#cbd5e1"))
            st.plotly_chart(fig_cat, use_container_width=True)

    with col_a2:
        st.subheader("Top Contributing Publishers")
        if stats["source_counts"]:
            df_src = pd.DataFrame(stats["source_counts"][:10])
            fig_src = px.bar(df_src, x="count", y="source_name", orientation="h", color="count", color_continuous_scale="Viridis")
            fig_src.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#cbd5e1"), yaxis=dict(autorange="reversed"), coloraxis_showscale=False)
            st.plotly_chart(fig_src, use_container_width=True)

elif selected_nav == "💾 Data Exports":
    st.markdown("<h1 style='font-size: 28px; font-weight: 800;'>💾 Intelligence Exports & Snapshots</h1>", unsafe_allow_html=True)
    st.markdown("Generate sanitized data exports for SIEM ingestion or offline threat hunting.")

    ec1, ec2 = st.columns(2)
    with ec1:
        st.subheader("Export News Records")
        records_to_export, _ = db.get_articles_filtered(limit=5000)
        csv_bytes = ExportService.export_to_csv(records_to_export)
        st.download_button("📥 Download Sanitized CSV", data=csv_bytes, file_name="cyberpulse_intel_feed.csv", mime="text/csv", use_container_width=True)

        json_bytes = ExportService.export_to_json(records_to_export)
        st.download_button("📥 Download Clean JSON", data=json_bytes, file_name="cyberpulse_intel_feed.json", mime="application/json", use_container_width=True)

    with ec2:
        st.subheader("Database Backup")
        st.markdown("Take a physical, timestamped snapshot of the live SQLite database without taking down the server.")
        if st.button("📦 Create Database Snapshot Now", use_container_width=True):
            bk_path = db.backup_database()
            st.success(f"Backup created safely at: `{bk_path}`")

elif selected_nav == "⚙️ Portal Settings":
    st.markdown("<h1 style='font-size: 28px; font-weight: 800;'>⚙️ Portal Architecture & Configuration</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div style="background: #1e1b4b; border: 1px solid #4338ca; border-radius: 8px; padding: 18px 22px; margin-bottom: 24px;">
        <div style="font-size: 16px; font-weight: 700; color: #a5b4fc;">Created by RAJ ARYAN</div>
        <div style="color: #cbd5e1; font-size: 13.5px; margin-top: 4px;">
            Official Portfolio & Intelligence Portal: <a href="https://rajaryan.neocities.org" target="_blank" style="color: #38bdf8; font-weight: 600;">rajaryan.neocities.org ↗</a>
        </div>
        <div style="color: #94a3b8; font-size: 12px; margin-top: 6px;">Released under the MIT License • Built for local cybersecurity research</div>
    </div>
    """, unsafe_allow_html=True)
    st.write(f"**Lead Architect & Developer:** `RAJ ARYAN` ([rajaryan.neocities.org](https://rajaryan.neocities.org))")
    st.write(f"**Database Store:** `{os.path.abspath(db.db_path)}`")
    st.write(f"**Host Binding:** `{config.get('app', {}).get('bind_address', '127.0.0.1')}:8501` (Restricted to Localhost)")
    st.write(f"**Feed Timeout:** `{config.get('app', {}).get('request_timeout_seconds', 12)}s`")
    st.write(f"**Concurrent Fetch Workers:** `{config.get('app', {}).get('max_concurrent_workers', 10)}`")
    st.info("🔒 CyberPulse Intelligence enforces local-only loopback binding and zero external data leaks.")
