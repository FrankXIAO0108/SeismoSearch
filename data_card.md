# SeismoSearch Data Card

## Purpose

SeismoSearch uses public earthquake catalog data and seismology reference documents to answer questions about recorded events, catalog fields, historical statistics, and safety-bounded risk communication.

It does not predict future earthquakes, estimate a user's personal risk, or replace official monitoring and emergency guidance.

## Data sources

### Event catalog

- Default runtime sample: `data/processed/events_sample_1000.jsonl`.
- Reproducible expansion: USGS FDSN Event Web Service, 2021-01-01 through 2025-12-31, global M4.5+ events filtered to `eventtype=earthquake`.
- Expansion manifest: `data/processed/events_catalog_2021_2025_m45.manifest.json`.
- Normalized storage: DuckDB table `events`, schema defined in `schemas/events_schema.sql`.
- Raw records are retained in the normalized record for audit and future schema extensions.

### Knowledge documents

- Runtime corpus: `data/processed/docs/`.
- Optional versioned expansion: `data/processed/docs_expansion_v1/`.
- Corpus registry: `data/processed/doc_corpus_manifest_v1.json`.
- Documents are paraphrased or summarized from public USGS and FEMA materials; each expansion document contains its source references.

## Normalized fields

The event schema preserves event identity, source URLs, occurrence and update time, coordinates, depth, place, region, country, magnitude and magnitude type, review status, quality fields, alert and tsunami flags, and the original source record.

The field mapping and data-quality notes are defined in `schemas/events_schema.sql` and `docs/event_field_mapping.md`.

## Processing pipeline

```text
USGS GeoJSON
    -> normalize and validate
    -> deduplicate by event_id
    -> JSONL snapshot with manifest
    -> DuckDB events table
    -> structured event tools
```

The snapshot builder uses bounded time windows and fails when a window reaches the upstream request limit, preventing silent truncation. The database builder validates required fields and duplicate IDs before bulk insertion.

## Known limitations

- The default runtime database is a local sample, not a complete global catalog.
- Event records and document summaries inherit the scope and revision policy of their public sources.
- The expansion corpus is opt-in and has not been validated by an independent blind holdout.
- Derived geography fields should not be treated as primary source facts for offshore events.

## Reproducibility

Use `scripts/build_event_catalog_snapshot.py` to rebuild the expansion snapshot and `scripts/build_event_db.py` to create a DuckDB runtime file. The manifest records query parameters, source windows, counts, quality checks, file size, and SHA-256.
