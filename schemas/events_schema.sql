-- SeismoSearch events table schema
-- Purpose:
--   Store structured public earthquake catalog records for SQL-based event lookup,
--   filtering, sorting, aggregation, and evidence citation.
--
-- Design principles:
--   1. Keep original source identity for traceability.
--   2. Normalize time, location, magnitude, depth, alert, and quality fields.
--   3. Preserve raw JSON for audit and future schema extension.
--   4. Do not use this table for earthquake prediction.

CREATE TABLE IF NOT EXISTS events (
    -- Primary identity.
    -- event_id is the stable internal event identifier used by SeismoSearch.
    event_id                VARCHAR PRIMARY KEY,

    -- Data source, for example: USGS, ISC, EMSC.
    source                  VARCHAR NOT NULL,

    -- Original event ID from the upstream catalog.
    source_event_id          VARCHAR,

    -- Source-level URL or API endpoint.
    source_url               VARCHAR,

    -- Event detail page URL, used for evidence citation.
    detail_url               VARCHAR,

    -- Event classification, for example: earthquake, quarry blast, explosion.
    event_type               VARCHAR,

    -- Review status, for example: reviewed, automatic.
    status                   VARCHAR,

    -- Event occurrence time in UTC.
    event_time_utc           TIMESTAMP NOT NULL,

    -- Last update time from the source catalog.
    updated_time_utc         TIMESTAMP,

    -- Date extracted from event_time_utc, useful for grouping and aggregation.
    event_date_utc           DATE,

    -- Longitude in decimal degrees.
    longitude                DOUBLE NOT NULL,

    -- Latitude in decimal degrees.
    latitude                 DOUBLE NOT NULL,

    -- Hypocentral depth in kilometers.
    depth_km                 DOUBLE,

    -- Human-readable location description from the source.
    place                    VARCHAR,

    -- Derived or source-provided region name.
    region                   VARCHAR,

    -- Derived country name.
    -- This should not be treated as a primary source fact, especially for offshore events.
    country                  VARCHAR,

    -- Earthquake magnitude value.
    magnitude                DOUBLE,

    -- Magnitude type, for example: mw, mww, mb, ml.
    magnitude_type           VARCHAR,

    -- Magnitude uncertainty if available.
    magnitude_error          DOUBLE,

    -- Number of stations used for magnitude calculation if available.
    magnitude_nst            INTEGER,

    -- Source agency for magnitude.
    magnitude_source         VARCHAR,

    -- Horizontal location error in kilometers.
    horizontal_error_km      DOUBLE,

    -- Depth error in kilometers.
    depth_error_km           DOUBLE,

    -- Number of seismic stations used for location.
    nst                      INTEGER,

    -- Largest azimuthal gap in degrees.
    gap_deg                  DOUBLE,

    -- Distance to nearest station in degrees.
    dmin_deg                 DOUBLE,

    -- Root mean square travel-time residual in seconds.
    rms_sec                  DOUBLE,

    -- Source agency for location.
    location_source          VARCHAR,

    -- Number of felt reports if available.
    felt                     INTEGER,

    -- Community Decimal Intensity if available.
    cdi                      DOUBLE,

    -- Modified Mercalli Intensity if available.
    mmi                      DOUBLE,

    -- Alert level, for example: green, yellow, orange, red.
    alert                    VARCHAR,

    -- Tsunami flag.
    -- Usually 0 or 1, depending on source convention.
    tsunami                  INTEGER,

    -- Source-provided event significance score.
    significance             INTEGER,

    -- Network identifier from the source catalog.
    net                      VARCHAR,

    -- Event code from the source catalog.
    code                     VARCHAR,

    -- Comma-separated related event IDs from source, if available.
    ids                      VARCHAR,

    -- Comma-separated contributing sources, if available.
    sources                  VARCHAR,

    -- Comma-separated product types, if available.
    product_types            VARCHAR,

    -- Time when this record is ingested into SeismoSearch.
    ingest_time_utc          TIMESTAMP NOT NULL,

    -- Raw data format, for example: geojson, csv, json.
    raw_format               VARCHAR,

    -- Original raw event record preserved for audit and future parsing.
    raw_record_json          JSON,

    -- Whether the event has been reviewed by a source agency.
    is_reviewed              BOOLEAN,

    -- Whether this record is suspected to duplicate another event.
    is_duplicate_candidate   BOOLEAN DEFAULT FALSE,

    -- Free-text note for data quality issues.
    data_quality_note        VARCHAR
);