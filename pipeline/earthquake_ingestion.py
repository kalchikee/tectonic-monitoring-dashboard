"""
earthquake_ingestion.py
-----------------------
Ingests real-time earthquake data from the USGS FDSN web service into PostGIS.

Runs on a 24-hour schedule. Uses upsert logic (INSERT ... ON CONFLICT DO UPDATE)
to handle duplicate events and catalog revisions. Supports both initial backfill
and incremental daily updates.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import geopandas as gpd
import pandas as pd
import psycopg2
import requests
from psycopg2.extras import execute_values
from shapely.geometry import Point

log = logging.getLogger(__name__)

USGS_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def get_db_connection(database_url: Optional[str] = None):
    """Return a psycopg2 connection using DATABASE_URL env var."""
    url = database_url or os.environ.get(
        "DATABASE_URL",
        "postgresql://tectonic:tectonic@localhost:5432/tectonic_monitor"
    )
    return psycopg2.connect(url)


def fetch_earthquakes(
    starttime: str,
    endtime: str,
    minmagnitude: float = 1.0,
    minlatitude: float = -90,
    maxlatitude: float = 90,
    minlongitude: float = -180,
    maxlongitude: float = 180,
) -> list[dict]:
    """
    Query USGS FDSN API and return list of event dicts.

    Parameters
    ----------
    starttime, endtime : ISO 8601 date strings
    minmagnitude : Magnitude threshold
    lat/lon bounds : Optional spatial filter

    Returns
    -------
    list of event dicts with keys: event_id, time, magnitude, depth_km, lat, lon, place
    """
    params = {
        "format": "geojson",
        "starttime": starttime,
        "endtime": endtime,
        "minmagnitude": minmagnitude,
        "minlatitude": minlatitude,
        "maxlatitude": maxlatitude,
        "minlongitude": minlongitude,
        "maxlongitude": maxlongitude,
        "orderby": "time",
        "limit": 20000,
    }

    resp = requests.get(USGS_API, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    events = []
    for feat in data["features"]:
        p = feat["properties"]
        c = feat["geometry"]["coordinates"]
        events.append({
            "event_id": feat["id"],
            "time": datetime.fromtimestamp(p["time"] / 1000, tz=timezone.utc),
            "magnitude": p.get("mag"),
            "mag_type": p.get("magType", ""),
            "depth_km": c[2],
            "latitude": c[1],
            "longitude": c[0],
            "place": p.get("place", ""),
            "status": p.get("status", ""),
            "net": p.get("net", ""),
            "n_stations": p.get("nst"),
            "rms": p.get("rms"),
        })

    log.info(f"Fetched {len(events)} events ({starttime} → {endtime})")
    return events


def upsert_earthquakes(events: list[dict], conn) -> int:
    """
    Insert or update earthquake records in PostGIS database.

    Returns number of rows affected.
    """
    if not events:
        return 0

    sql = """
    INSERT INTO earthquakes (
        event_id, time, magnitude, mag_type, depth_km,
        latitude, longitude, place, status, net, n_stations, rms,
        geom, ingested_at
    ) VALUES %s
    ON CONFLICT (event_id) DO UPDATE SET
        magnitude = EXCLUDED.magnitude,
        status = EXCLUDED.status,
        n_stations = EXCLUDED.n_stations,
        rms = EXCLUDED.rms,
        ingested_at = EXCLUDED.ingested_at
    """

    rows = [
        (
            e["event_id"],
            e["time"],
            e["magnitude"],
            e["mag_type"],
            e["depth_km"],
            e["latitude"],
            e["longitude"],
            e["place"],
            e["status"],
            e["net"],
            e["n_stations"],
            e["rms"],
            f"SRID=4326;POINT({e['longitude']} {e['latitude']})",
            datetime.now(timezone.utc),
        )
        for e in events
    ]

    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
        count = cur.rowcount
    conn.commit()

    log.info(f"Upserted {count} rows into earthquakes table")
    return count


def run_daily_ingestion(
    lookback_hours: int = 25,
    minmagnitude: float = 1.0,
    database_url: Optional[str] = None,
) -> dict:
    """
    Main ingestion function: fetch last N hours of earthquakes and upsert.

    Called by scheduler every 24 hours.

    Returns
    -------
    dict with ingestion statistics
    """
    now = datetime.now(timezone.utc)
    starttime = (now - timedelta(hours=lookback_hours)).strftime("%Y-%m-%dT%H:%M:%S")
    endtime = now.strftime("%Y-%m-%dT%H:%M:%S")

    log.info(f"Daily ingestion: {starttime} → {endtime}")

    try:
        events = fetch_earthquakes(
            starttime=starttime,
            endtime=endtime,
            minmagnitude=minmagnitude,
        )

        conn = get_db_connection(database_url)
        n_upserted = upsert_earthquakes(events, conn)
        conn.close()

        stats = {
            "status": "success",
            "starttime": starttime,
            "endtime": endtime,
            "events_fetched": len(events),
            "rows_upserted": n_upserted,
            "run_at": now.isoformat(),
        }

    except Exception as exc:
        log.error(f"Ingestion failed: {exc}", exc_info=True)
        stats = {
            "status": "error",
            "error": str(exc),
            "run_at": now.isoformat(),
        }

    return stats


def backfill(
    days: int = 30,
    minmagnitude: float = 1.0,
    database_url: Optional[str] = None,
) -> None:
    """
    Backfill historical earthquake data for initial database load.

    Fetches data in daily chunks to avoid API limits.
    """
    log.info(f"Starting {days}-day backfill (M≥{minmagnitude})")
    conn = get_db_connection(database_url)
    now = datetime.now(timezone.utc)
    total_upserted = 0

    for d in range(days, 0, -1):
        start = (now - timedelta(days=d)).strftime("%Y-%m-%dT00:00:00")
        end = (now - timedelta(days=d - 1)).strftime("%Y-%m-%dT00:00:00")
        try:
            events = fetch_earthquakes(start, end, minmagnitude=minmagnitude)
            n = upsert_earthquakes(events, conn)
            total_upserted += n
        except Exception as exc:
            log.warning(f"  Day {d} failed: {exc}")

    conn.close()
    log.info(f"Backfill complete: {total_upserted} rows loaded")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        backfill(days=days)
    else:
        stats = run_daily_ingestion()
        print(stats)
