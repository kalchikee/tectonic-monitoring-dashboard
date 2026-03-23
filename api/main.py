"""
FastAPI backend for the Tectonic Monitoring Dashboard.

Endpoints:
  GET /health                  - Service health check
  GET /seismicity/events       - Paginated earthquake list
  GET /seismicity/summary      - Aggregated statistics
  GET /seismicity/anomalies    - Current anomaly flags
  GET /seismicity/timeseries   - Event counts by time bin
  GET /gnss/stations           - GNSS station metadata
  GET /gnss/velocities         - Current velocity vectors
  GET /hazard/region           - Seismicity rate for bbox

Run:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import seismicity, gnss, hazard

app = FastAPI(
    title="Tectonic Monitoring API",
    description=(
        "Real-time tectonic monitoring backend serving earthquake, GNSS, "
        "and seismic hazard data from USGS and UNAVCO sources."
    ),
    version="1.0.0",
    contact={
        "name": "GitHub",
        "url": "https://github.com/kalchikee/tectonic-monitoring-dashboard",
    },
    license_info={"name": "MIT"},
)

# CORS — allow Streamlit dashboard and any other frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Include routers
app.include_router(seismicity.router, prefix="/seismicity", tags=["Seismicity"])
app.include_router(gnss.router, prefix="/gnss", tags=["GNSS"])
app.include_router(hazard.router, prefix="/hazard", tags=["Hazard"])


@app.get("/health", tags=["System"])
async def health_check():
    """Service health check — verifies API is running."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }


@app.get("/", tags=["System"])
async def root():
    """API root — returns documentation URL."""
    return {
        "message": "Tectonic Monitoring API",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }
