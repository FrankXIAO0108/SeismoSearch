"""
Build DuckDB event database for SeismoSearch.

This script loads normalized earthquake event records from:

    data/processed/events_sample_1000.jsonl

Then it creates the DuckDB events table using:

    schemas/events_schema.sql

Finally, it inserts normalized records into:

    data/duckdb/seismosearch.duckdb

This script does not commit the DuckDB file to Git.
The DuckDB database is a reproducible runtime artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import duckdb


DEFAULT_SCHEMA_PATH = Path("schemas/events_schema.sql")
DEFAULT_INPUT_PATH = Path("data/processed/events_sample_1000.jsonl")
DEFAULT_DB_PATH = Path("data/duckdb/seismosearch.duckdb")
DEFAULT_TABLE_NAME = "events"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load normalized event records from a JSONL file."""
    if not path.exists():
        raise FileNotFoundError(f"Input JSONL file does not exist: {path}")

    records: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()

            # Skip empty lines to avoid JSON parsing errors.
            if not stripped:
                continue

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_number}: {exc}") from exc

            if not isinstance(record, dict):
                raise ValueError(f"Line {line_number} is not a JSON object.")

            records.append(record)

    return records


def execute_schema(connection: duckdb.DuckDBPyConnection, schema_path: Path) -> None:
    """Execute SQL schema file to create the events table."""
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file does not exist: {schema_path}")

    schema_sql = schema_path.read_text(encoding="utf-8")

    if "CREATE TABLE" not in schema_sql.upper():
        raise ValueError(f"Schema file does not look like a CREATE TABLE script: {schema_path}")

    connection.execute(schema_sql)


def get_table_columns(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
) -> list[str]:
    """Read column names from a DuckDB table."""
    rows = connection.execute(f"PRAGMA table_info('{table_name}')").fetchall()

    if not rows:
        raise ValueError(f"Table does not exist or has no columns: {table_name}")

    # PRAGMA table_info returns rows like:
    # (cid, name, type, notnull, dflt_value, pk)
    return [row[1] for row in rows]


def normalize_value_for_duckdb(value: Any) -> Any:
    """Convert Python values into DuckDB-friendly values."""
    if isinstance(value, (dict, list)):
        # Store nested JSON-like objects as JSON strings.
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    return value


def build_insert_rows(
    records: list[dict[str, Any]],
    columns: list[str],
) -> list[tuple[Any, ...]]:
    """Convert records into tuples ordered by DuckDB table columns."""
    rows: list[tuple[Any, ...]] = []

    for record in records:
        row = tuple(normalize_value_for_duckdb(record.get(column)) for column in columns)
        rows.append(row)

    return rows


def validate_required_fields(records: list[dict[str, Any]]) -> None:
    """Validate required fields before database insertion."""
    required_fields = [
        "event_id",
        "source",
        "event_time_utc",
        "longitude",
        "latitude",
        "ingest_time_utc",
        "raw_format",
        "raw_record_json",
    ]

    missing_count = 0

    for record in records:
        if any(record.get(field) is None for field in required_fields):
            missing_count += 1

    if missing_count > 0:
        raise ValueError(f"Found {missing_count} records with missing required fields.")


def validate_event_ids(records: list[dict[str, Any]]) -> None:
    """Validate event_id uniqueness before database insertion."""
    event_ids = [record.get("event_id") for record in records]

    if any(event_id is None for event_id in event_ids):
        raise ValueError("Found records with missing event_id.")

    duplicate_count = len(event_ids) - len(set(event_ids))

    if duplicate_count > 0:
        raise ValueError(f"Found {duplicate_count} duplicate event_id values.")


def insert_records(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    records: list[dict[str, Any]],
) -> int:
    """Insert normalized event records into DuckDB."""
    columns = get_table_columns(connection, table_name)
    rows = build_insert_rows(records, columns)

    if not rows:
        return 0

    column_sql = ", ".join(columns)
    placeholder_sql = ", ".join(["?"] * len(columns))

    # Clear existing rows so repeated script runs are reproducible.
    connection.execute(f"DELETE FROM {table_name}")

    # Insert rows using parameterized SQL.
    connection.executemany(
        f"INSERT INTO {table_name} ({column_sql}) VALUES ({placeholder_sql})",
        rows,
    )

    return len(rows)


def print_database_summary(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
) -> None:
    """Print basic SQL checks after insertion."""
    total_rows = connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

    min_time, max_time = connection.execute(
        f"SELECT MIN(event_time_utc), MAX(event_time_utc) FROM {table_name}"
    ).fetchone()

    min_mag, max_mag = connection.execute(
        f"SELECT MIN(magnitude), MAX(magnitude) FROM {table_name}"
    ).fetchone()

    reviewed_count = connection.execute(
        f"SELECT COUNT(*) FROM {table_name} WHERE is_reviewed = TRUE"
    ).fetchone()[0]

    print(f"Rows in {table_name}: {total_rows}")
    print(f"Event time range: {min_time} -> {max_time}")
    print(f"Magnitude range: {min_mag} -> {max_mag}")
    print(f"Reviewed events: {reviewed_count}")

    print("\nTop 5 events by magnitude:")
    rows = connection.execute(
        f"""
        SELECT
            event_id,
            event_time_utc,
            magnitude,
            magnitude_type,
            depth_km,
            place
        FROM {table_name}
        ORDER BY magnitude DESC NULLS LAST
        LIMIT 5
        """
    ).fetchall()

    for row in rows:
        print(row)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build DuckDB database for SeismoSearch event records."
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Input normalized event JSONL file.",
    )

    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA_PATH,
        help="SQL schema file for creating the events table.",
    )

    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Output DuckDB database path.",
    )

    parser.add_argument(
        "--table",
        default=DEFAULT_TABLE_NAME,
        help="DuckDB table name.",
    )

    return parser.parse_args()


def main() -> int:
    """Build the DuckDB event database."""
    args = parse_args()

    try:
        print(f"Loading records from: {args.input}")
        records = load_jsonl(args.input)

        print(f"Loaded records: {len(records)}")
        validate_required_fields(records)
        validate_event_ids(records)

        args.db.parent.mkdir(parents=True, exist_ok=True)

        print(f"Opening DuckDB database: {args.db}")
        connection = duckdb.connect(str(args.db))

        try:
            print(f"Executing schema: {args.schema}")
            execute_schema(connection, args.schema)

            print(f"Inserting records into table: {args.table}")
            inserted_count = insert_records(connection, args.table, records)

            print(f"Inserted records: {inserted_count}")
            print_database_summary(connection, args.table)

        finally:
            connection.close()

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())