"""Tests for native DuckDB JSONL bulk loading."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from scripts.build_event_db import (
    execute_schema,
    insert_records_from_jsonl,
    validate_table_name,
)


def make_record(event_id: str) -> dict:
    return {
        "event_id": event_id,
        "source": "USGS",
        "event_time_utc": "2025-01-01T00:00:00Z",
        "longitude": 120.0,
        "latitude": 30.0,
        "ingest_time_utc": "2025-01-02T00:00:00Z",
        "raw_format": "geojson",
        "raw_record_json": {"id": event_id},
    }


def test_bulk_loader_preserves_rows_and_raw_json(tmp_path: Path) -> None:
    input_path = tmp_path / "events.jsonl"
    input_path.write_text(
        "\n".join(
            json.dumps(make_record(event_id))
            for event_id in ["event-a", "event-b"]
        )
        + "\n",
        encoding="utf-8",
    )
    connection = duckdb.connect(":memory:")
    execute_schema(connection, Path("schemas/events_schema.sql"))

    inserted = insert_records_from_jsonl(
        connection,
        "events",
        input_path,
    )

    assert inserted == 2
    assert connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 2
    assert connection.execute(
        "SELECT json_extract_string(raw_record_json, '$.id') "
        "FROM events ORDER BY event_id LIMIT 1"
    ).fetchone()[0] == "event-a"
    connection.close()


def test_table_name_validation_rejects_sql_syntax() -> None:
    try:
        validate_table_name("events; DROP TABLE events")
    except ValueError:
        return
    raise AssertionError("unsafe table name should be rejected")
