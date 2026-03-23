-- Initial schema for the Tectonic Monitoring Database
-- Requires PostGIS extension

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- ── Earthquake Events ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS earthquakes (
    id              SERIAL PRIMARY KEY,
    event_id        VARCHAR(64) UNIQUE NOT NULL,
    time            TIMESTAMPTZ NOT NULL,
    magnitude       DECIMAL(4,2),
    mag_type        VARCHAR(10),
    depth_km        DECIMAL(8,3),
    latitude        DECIMAL(10,6) NOT NULL,
    longitude       DECIMAL(11,6) NOT NULL,
    place           VARCHAR(255),
    status          VARCHAR(20),
    net             VARCHAR(10),
    n_stations      INTEGER,
    rms             DECIMAL(6,4),
    geom            GEOMETRY(POINT, 4326) NOT NULL,
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Spatial index for bounding box queries
CREATE INDEX IF NOT EXISTS idx_earthquakes_geom
    ON earthquakes USING GIST (geom);

-- Temporal index for time-range queries
CREATE INDEX IF NOT EXISTS idx_earthquakes_time
    ON earthquakes (time DESC);

-- Magnitude index for filtering
CREATE INDEX IF NOT EXISTS idx_earthquakes_magnitude
    ON earthquakes (magnitude);

-- Composite index for common query pattern (time + magnitude)
CREATE INDEX IF NOT EXISTS idx_earthquakes_time_mag
    ON earthquakes (time DESC, magnitude);

-- ── GNSS Stations ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gnss_stations (
    id              SERIAL PRIMARY KEY,
    station_id      VARCHAR(16) UNIQUE NOT NULL,
    name            VARCHAR(128),
    network         VARCHAR(32),
    latitude        DECIMAL(10,6) NOT NULL,
    longitude       DECIMAL(11,6) NOT NULL,
    elevation_m     DECIMAL(8,2),
    geom            GEOMETRY(POINT, 4326) NOT NULL,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gnss_stations_geom
    ON gnss_stations USING GIST (geom);

-- ── GNSS Velocities ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gnss_velocities (
    id              SERIAL PRIMARY KEY,
    station_id      VARCHAR(16) REFERENCES gnss_stations(station_id),
    reference_frame VARCHAR(32) DEFAULT 'NA12',
    ve_mm_yr        DECIMAL(8,3),   -- East velocity (mm/yr)
    vn_mm_yr        DECIMAL(8,3),   -- North velocity (mm/yr)
    vu_mm_yr        DECIMAL(8,3),   -- Up velocity (mm/yr)
    se_mm_yr        DECIMAL(8,3),   -- East std error
    sn_mm_yr        DECIMAL(8,3),   -- North std error
    su_mm_yr        DECIMAL(8,3),   -- Up std error
    obs_start       DATE,
    obs_end         DATE,
    n_observations  INTEGER,
    ingested_at     TIMESTAMPTZ DEFAULT NOW()
);

-- ── Seismicity Anomalies ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS seismicity_anomalies (
    id              SERIAL PRIMARY KEY,
    detected_at     TIMESTAMPTZ DEFAULT NOW(),
    lat_center      DECIMAL(8,4) NOT NULL,
    lon_center      DECIMAL(9,4) NOT NULL,
    grid_cell       GEOMETRY(POLYGON, 4326),
    z_score         DECIMAL(6,3),
    current_rate    DECIMAL(10,4),
    baseline_rate   DECIMAL(10,4),
    baseline_std    DECIMAL(10,4),
    window_days     INTEGER,
    n_events        INTEGER,
    is_active       BOOLEAN DEFAULT TRUE,
    resolved_at     TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_anomalies_grid
    ON seismicity_anomalies USING GIST (grid_cell);

CREATE INDEX IF NOT EXISTS idx_anomalies_active
    ON seismicity_anomalies (is_active, detected_at DESC);

-- ── Updated_at trigger ────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER earthquakes_updated_at
    BEFORE UPDATE ON earthquakes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ── Summary view ──────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW seismicity_daily_summary AS
SELECT
    date_trunc('day', time) AS day,
    COUNT(*) AS event_count,
    MAX(magnitude) AS max_magnitude,
    AVG(magnitude) AS avg_magnitude,
    AVG(depth_km) AS avg_depth_km,
    COUNT(*) FILTER (WHERE magnitude >= 3.0) AS m3_plus,
    COUNT(*) FILTER (WHERE magnitude >= 5.0) AS m5_plus
FROM earthquakes
WHERE time >= NOW() - INTERVAL '365 days'
GROUP BY date_trunc('day', time)
ORDER BY day DESC;

COMMENT ON TABLE earthquakes IS 'USGS ComCat earthquake events, updated daily';
COMMENT ON TABLE gnss_stations IS 'UNAVCO GAGE GNSS station metadata';
COMMENT ON TABLE gnss_velocities IS 'GNSS station velocity components from UNAVCO';
COMMENT ON TABLE seismicity_anomalies IS 'Automated seismicity rate anomaly detections';
