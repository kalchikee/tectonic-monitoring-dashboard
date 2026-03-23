# Automated Tectonic Monitoring Dashboard

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32-red)](https://streamlit.io/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-blue)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Live Demo](https://img.shields.io/badge/Live-Demo-brightgreen)](https://tectonic-monitor.onrender.com)

A fully automated, web-deployable geoscience monitoring platform that ingests real-time earthquake data and GNSS velocities from USGS and UNAVCO, detects anomalous seismicity swarms using statistical process control, and serves results through a FastAPI backend and interactive Streamlit dashboard — updated every 24 hours via automated pipeline.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Data Sources (External)                      │
│  USGS FDSN API  │  UNAVCO GNSS API  │  USGS Quaternary Faults  │
└─────────┬───────┴──────────┬────────┴──────────────────────────┘
          │                  │
          ▼                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Python Ingestion Pipeline                      │
│  earthquake_ingestion.py  │  gnss_ingestion.py  │  scheduler.py │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PostgreSQL + PostGIS                           │
│  earthquakes  │  gnss_stations  │  gnss_velocities  │  anomalies│
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                              │
│  /seismicity/events  │  /seismicity/anomalies  │  /gnss/vectors │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Streamlit Dashboard                            │
│  Real-time Map  │  Time Series  │  GNSS Velocities  │  Alerts  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Features

- **Real-time seismicity map** — Interactive Plotly/Folium map of M1.0+ earthquakes updated every 24 hours, colored by depth and scaled by magnitude
- **Omori decay fitting** — Automated aftershock sequence detection and decay parameter estimation
- **Anomaly detection** — Z-score based flagging of regions with anomalously elevated seismicity rates vs. 1-year baseline
- **GNSS velocity vectors** — Current plate motion vectors from UNAVCO GAGE network
- **FastAPI REST backend** — Programmatic access to all data with full OpenAPI documentation at `/docs`
- **Containerized deployment** — One-command Docker Compose launch for reproducible, portable infrastructure
- **Auto-refresh** — Dashboard auto-updates every 300 seconds; pipeline runs on 24-hour cron schedule

---

## Repository Structure

```
04-tectonic-monitoring-dashboard/
├── app/
│   ├── main.py                  # Streamlit entry point
│   ├── pages/
│   │   ├── seismicity_map.py    # Interactive earthquake map
│   │   ├── time_series.py       # Event rate and Omori decay panel
│   │   ├── gnss_velocities.py   # GNSS vector map
│   │   └── hazard_summary.py    # Regional hazard context
│   └── components/
│       ├── map_components.py    # Reusable Plotly/Folium helpers
│       └── chart_components.py  # Time-series chart helpers
├── pipeline/
│   ├── earthquake_ingestion.py  # USGS FDSN → PostGIS upsert
│   ├── gnss_ingestion.py        # UNAVCO API → PostGIS
│   ├── anomaly_detection.py     # Statistical swarm detection
│   └── scheduler.py             # APScheduler cron jobs
├── api/
│   ├── main.py                  # FastAPI application
│   ├── routers/
│   │   ├── seismicity.py        # /seismicity/* endpoints
│   │   ├── gnss.py              # /gnss/* endpoints
│   │   └── hazard.py            # /hazard/* endpoints
│   └── models/
│       └── schemas.py           # Pydantic response models
├── database/
│   ├── connection.py            # SQLAlchemy engine
│   ├── models.py                # ORM table definitions
│   └── migrations/
│       └── 001_initial_schema.sql
├── docker-compose.yml
├── Dockerfile
└── config/
    └── config.yaml
```

---

## Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/kalchikee/tectonic-monitoring-dashboard.git
cd tectonic-monitoring-dashboard
cp .env.example .env
docker-compose up -d
```

Services will start at:
- **Dashboard:** http://localhost:8501
- **API docs:** http://localhost:8000/docs
- **Database:** localhost:5432

### Manual Installation

```bash
# Requires PostgreSQL with PostGIS extension
pip install -r requirements.txt
python scripts/initialize_db.py
python scripts/backfill_data.py  # Load 30 days of historical data
uvicorn api.main:app --port 8000 &
streamlit run app/main.py
```

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Service health check |
| `/seismicity/events` | GET | Paginated earthquake list (filter by mag, depth, time, bbox) |
| `/seismicity/summary` | GET | Aggregated stats (counts, max magnitude, active regions) |
| `/seismicity/anomalies` | GET | Current anomaly flags with z-scores |
| `/seismicity/timeseries` | GET | Event counts binned by hour/day/week |
| `/gnss/stations` | GET | GNSS station metadata |
| `/gnss/velocities` | GET | Current velocity vectors |
| `/hazard/region` | GET | Seismicity rate for user-defined region |

Full interactive documentation at `/docs` (Swagger UI) and `/redoc`.

---

## Data Sources

| Dataset | Update Frequency | API |
|---------|-----------------|-----|
| Earthquake catalog | Real-time (24hr pull) | `earthquake.usgs.gov/fdsnws/event/1/query` |
| GNSS velocities | Weekly | `gage-data.unavco.org/ws/metadata/site` |
| Fault traces | Static | USGS Quaternary Fault Database |

---

## Deployment

### Render (Free Tier)

```bash
# Connect GitHub repo to Render
# Set environment variables:
DATABASE_URL=postgresql://...
# Render will auto-deploy on push
```

### Railway

```bash
railway login
railway init
railway up
```

---

## Anomaly Detection Method

Seismicity rates are computed in 1°×1° grid cells at weekly resolution. A baseline rate μ and standard deviation σ are estimated from the prior 52 weeks. A cell is flagged as anomalous when:

```
z = (rate_current_week - μ) / σ > 3.0
```

False positive rate: ~0.1% per cell per week under the null hypothesis of stationary Poisson seismicity.

---

## License

MIT License. See [LICENSE](LICENSE).

---

## References

- USGS Earthquake Hazards Program: https://earthquake.usgs.gov
- UNAVCO GAGE Geodetic Infrastructure: https://www.unavco.org
- Shakecast / ShakeMap infrastructure: https://earthquake.usgs.gov/data/shakecast/
