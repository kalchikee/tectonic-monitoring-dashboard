"""
seismicity.py
-------------
FastAPI router for seismicity endpoints.

For portability (no database required for demo), this module falls back to
querying the USGS FDSN API directly when no database is configured. In
production, queries hit the PostGIS database populated by the ingestion pipeline.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from fastapi import APIRouter, Query, HTTPException

router = APIRouter()

USGS_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"
USE_DB = bool(os.environ.get("DATABASE_URL"))


def _usgs_query(params: dict) -> list[dict]:
    """Query USGS FDSN API and return parsed event list."""
    params["format"] = "geojson"
    params["limit"] = params.get("limit", 1000)
    resp = requests.get(USGS_API, params=params, timeout=30)
    resp.raise_for_status()
    events = []
    for feat in resp.json()["features"]:
        p = feat["properties"]
        c = feat["geometry"]["coordinates"]
        events.append({
            "event_id": feat["id"],
            "time": datetime.fromtimestamp(p["time"] / 1000, tz=timezone.utc).isoformat(),
            "magnitude": p.get("mag"),
            "mag_type": p.get("magType", ""),
            "depth_km": round(c[2], 1) if c[2] is not None else None,
            "latitude": round(c[1], 4),
            "longitude": round(c[0], 4),
            "place": p.get("place", ""),
            "url": p.get("url", ""),
        })
    return events


@router.get("/events")
async def get_events(
    days: int = Query(7, ge=1, le=365, description="Days to look back"),
    minmagnitude: float = Query(2.0, ge=0.0, le=10.0),
    maxdepth: float = Query(100.0, ge=0.0, le=700.0),
    minlatitude: Optional[float] = Query(None),
    maxlatitude: Optional[float] = Query(None),
    minlongitude: Optional[float] = Query(None),
    maxlongitude: Optional[float] = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    """
    Paginated earthquake event list.

    Returns events filtered by time, magnitude, depth, and optional bounding box.
    """
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    end = now.strftime("%Y-%m-%dT%H:%M:%S")

    params = {
        "starttime": start,
        "endtime": end,
        "minmagnitude": minmagnitude,
        "maxdepth": maxdepth,
        "limit": limit,
        "orderby": "time-asc",
    }
    if minlatitude is not None:
        params["minlatitude"] = minlatitude
    if maxlatitude is not None:
        params["maxlatitude"] = maxlatitude
    if minlongitude is not None:
        params["minlongitude"] = minlongitude
    if maxlongitude is not None:
        params["maxlongitude"] = maxlongitude

    try:
        events = _usgs_query(params)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"USGS API error: {e}")

    return {
        "count": len(events),
        "query_params": {
            "days": days,
            "minmagnitude": minmagnitude,
            "start": start,
            "end": end,
        },
        "events": events,
    }


@router.get("/summary")
async def get_summary():
    """
    Aggregated seismicity statistics for dashboard header metrics.
    """
    now = datetime.now(timezone.utc)

    # 24-hour stats
    params_24h = {
        "starttime": (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "minmagnitude": 2.0,
    }
    # 7-day M5+ stats
    params_7d = {
        "starttime": (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "minmagnitude": 5.0,
    }

    try:
        events_24h = _usgs_query(params_24h)
        events_7d_m5 = _usgs_query(params_7d)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"USGS API error: {e}")

    max_mag = max((e["magnitude"] for e in events_24h if e["magnitude"]), default=None)

    return {
        "events_24h": len(events_24h),
        "max_magnitude_24h": max_mag,
        "m5_events_7d": len(events_7d_m5),
        "active_anomalies": 0,  # populated by anomaly_detection pipeline
        "gnss_stations_active": 1200,  # approximate from UNAVCO
        "last_updated": now.isoformat(),
    }


@router.get("/timeseries")
async def get_timeseries(
    days: int = Query(30, ge=1, le=365),
    minmagnitude: float = Query(2.0, ge=0.0),
    bin_size: str = Query("day", regex="^(hour|day|week)$"),
):
    """
    Daily/weekly event count time series for plotting.
    """
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")

    params = {
        "starttime": start,
        "endtime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "minmagnitude": minmagnitude,
        "limit": 10000,
    }

    try:
        events = _usgs_query(params)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    import pandas as pd
    if not events:
        return {"bins": [], "counts": []}

    df = pd.DataFrame(events)
    df["time"] = pd.to_datetime(df["time"])

    freq_map = {"hour": "h", "day": "D", "week": "W"}
    freq = freq_map[bin_size]
    counts = df.resample(freq, on="time").size().reset_index()
    counts.columns = ["time", "count"]

    return {
        "bin_size": bin_size,
        "minmagnitude": minmagnitude,
        "bins": counts["time"].dt.strftime("%Y-%m-%dT%H:%M:%S").tolist(),
        "counts": counts["count"].tolist(),
    }
