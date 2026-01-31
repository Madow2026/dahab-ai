"""Sidebar navigation with per-page NEW badges.

Streamlit default multipage nav does not support dynamic badges, so we hide it
and render our own links.

Pages should:
1) Compute `new_since_last_visit` using db.get_page_new_count(page_key)
2) Call db.mark_page_seen(page_key) to reset that page's badge
3) Call render_sidebar(db, current_page_key)
"""

from __future__ import annotations

from typing import Dict, Optional

import streamlit as st


_PAGES: Dict[str, Dict[str, str]] = {
    "dashboard": {
        "label": "📈 Markets Dashboard",
        "path": "pages/1_📈_Markets_Dashboard.py",
    },
    "news": {
        "label": "📰 News",
        "path": "pages/2_📰_News.py",
    },
    "outlook": {
        "label": "🎯 AI Market Outlook",
        "path": "pages/3_🎯_AI_Market_Outlook.py",
    },
    "accuracy": {
        "label": "📊 Accuracy Performance",
        "path": "pages/4_📊_Accuracy_Performance.py",
    },
    "portfolio": {
        "label": "💼 Paper Portfolio",
        "path": "pages/5_💼_Paper_Portfolio.py",
    },
}


def _hide_default_sidebar_nav() -> None:
    # Hide Streamlit's built-in multipage nav so we can show badges.
    st.markdown(
        """
        <style>
          [data-testid="stSidebarNav"] { display: none; }
          .dahab-nav-title { color:#D4AF37; font-weight:700; margin: 0.25rem 0 0.5rem 0; }
          .dahab-nav-caption { color:#9AA0AA; font-size: 0.85rem; margin-bottom: 0.75rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(db, current_page_key: str) -> None:
    """Render sidebar nav with NEW-count badges.

    `current_page_key` must be one of: dashboard/news/outlook/accuracy/portfolio.
    """
    _hide_default_sidebar_nav()

    with st.sidebar:
        st.markdown("<div class='dahab-nav-title'>DAHAB AI</div>", unsafe_allow_html=True)
        st.markdown(
            "<div class='dahab-nav-caption'>Live badges reset when you open a page.</div>",
            unsafe_allow_html=True,
        )

        try:
            badges = db.get_sidebar_badges() or {}
        except Exception:
            badges = {}

        # Streamlit version compatibility: page_link exists on newer versions.
        page_link = getattr(st.sidebar, "page_link", None) or getattr(st, "page_link", None)

        for key, meta in _PAGES.items():
            # For News: show total recent-news volume (always visible).
            # For other pages: show NEW-since-last-visit badges (only when > 0).
            if key == 'news':
                try:
                    count = int(db.get_recent_news_count(hours=168) or 0)
                except Exception:
                    count = int(badges.get(key, 0) or 0)
                suffix = f" ({count})"
            else:
                count = int(badges.get(key, 0) or 0)
                suffix = f" ({count})" if count > 0 else ""
            label = f"{meta['label']}{suffix}"

            if page_link:
                try:
                    page_link(meta["path"], label=label)
                    continue
                except Exception:
                    # Fall through to markdown if page_link fails.
                    pass

            # Fallback: show label only (no navigation).
            st.markdown(label)

        st.markdown("---")
        st.caption("Tip: keep the worker running for continuous updates.")
