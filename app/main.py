"""
main.py
-------
Streamlit dashboard entry point for the Tectonic Monitoring System.

Multi-page application with sidebar navigation. Auto-refreshes every 300 seconds.
Connects to the FastAPI backend for data.

Run:
    streamlit run app/main.py
"""

import time
from datetime import datetime, timedelta, timezone

import requests
import streamlit as st

# ── Page configuration ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Tectonic Monitor",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/kalchikee/tectonic-monitoring-dashboard",
        "Report a bug": "https://github.com/kalchikee/tectonic-monitoring-dashboard/issues",
        "About": "Automated tectonic monitoring dashboard — USGS ComCat + UNAVCO GNSS",
    },
)

# Custom CSS
st.markdown(
    """
    <style>
    .metric-card {
        background: linear-gradient(135deg, #1e3a5f, #0d1f3c);
        border-radius: 10px;
        padding: 1rem;
        border: 1px solid #2d5a9e;
        color: white;
    }
    .stMetric {
        background-color: #0d1f3c;
        border-radius: 8px;
        padding: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

API_BASE = "http://localhost:8000"
REFRESH_INTERVAL = 300  # seconds


def get_api_data(endpoint: str, params: dict | None = None) -> dict | None:
    """Fetch data from FastAPI backend with error handling."""
    try:
        resp = requests.get(f"{API_BASE}{endpoint}", params=params, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"API error ({endpoint}): {e}")
        return None


def render_header():
    """Render dashboard header with last-update timestamp."""
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("🌍 Tectonic Monitoring Dashboard")
        st.caption(
            "Real-time seismicity and GNSS monitoring | "
            "Data: USGS ComCat + UNAVCO GAGE | "
            f"Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        )
    with col2:
        if st.button("🔄 Refresh"):
            st.rerun()


def render_summary_metrics():
    """Render key metric cards at the top of the dashboard."""
    summary = get_api_data("/seismicity/summary")
    if not summary:
        return

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="M2+ Events (24h)",
            value=summary.get("events_24h", "—"),
            delta=summary.get("delta_24h"),
            delta_color="inverse",
        )
    with col2:
        st.metric(
            label="Largest Today",
            value=f"M{summary.get('max_magnitude_24h', '—')}",
        )
    with col3:
        st.metric(
            label="Active Anomalies",
            value=summary.get("active_anomalies", 0),
            delta=None,
        )
    with col4:
        st.metric(
            label="M5+ (7 days)",
            value=summary.get("m5_events_7d", "—"),
        )
    with col5:
        st.metric(
            label="GNSS Stations",
            value=summary.get("gnss_stations_active", "—"),
        )


def render_sidebar():
    """Render navigation sidebar."""
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "View",
        ["Seismicity Map", "Time Series", "GNSS Velocities", "Hazard Summary"],
        label_visibility="collapsed",
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Filters**")

    min_mag = st.sidebar.slider("Min Magnitude", 1.0, 5.0, 2.0, 0.5)
    days_back = st.sidebar.selectbox("Time Window", [1, 7, 30, 90], index=1)
    depth_max = st.sidebar.slider("Max Depth (km)", 10, 100, 50, 10)

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        "**Data Sources**\n"
        "- [USGS ComCat](https://earthquake.usgs.gov)\n"
        "- [UNAVCO GNSS](https://www.unavco.org)\n"
        "- [USGS Faults](https://www.usgs.gov)"
    )

    auto_refresh = st.sidebar.checkbox("Auto-refresh (5 min)", value=True)

    return page, min_mag, days_back, depth_max, auto_refresh


def main():
    render_header()
    st.markdown("---")
    render_summary_metrics()
    st.markdown("---")

    page, min_mag, days_back, depth_max, auto_refresh = render_sidebar()

    # Route to sub-pages
    if page == "Seismicity Map":
        from app.pages.seismicity_map import render as render_map
        render_map(min_magnitude=min_mag, days_back=days_back, max_depth=depth_max)
    elif page == "Time Series":
        from app.pages.time_series import render as render_ts
        render_ts(min_magnitude=min_mag, days_back=days_back)
    elif page == "GNSS Velocities":
        from app.pages.gnss_velocities import render as render_gnss
        render_gnss()
    elif page == "Hazard Summary":
        from app.pages.hazard_summary import render as render_hazard
        render_hazard()

    # Auto-refresh
    if auto_refresh:
        time.sleep(REFRESH_INTERVAL)
        st.rerun()


if __name__ == "__main__":
    main()
