"""
Ingest USGS earthquake events for SeismoSearch.

This script implements the first real data path:

raw USGS GeoJSON
-> raw file under data/raw/events/
-> normalized JSONL records under data/processed/events_sample_1000.jsonl

The script does NOT perform earthquake prediction.
It only collects and normalizes already recorded earthquake catalog events.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


USGS_EVENT_API = "https://earthquake.usgs.gov/fdsnws/event/1/query"


def utc_now_iso() -> str:
    """Return current UTC time in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ms_to_utc_iso(value: Any) -> str | None:
    """Convert Unix milliseconds to UTC ISO-8601 string."""
    if value is None:
        return None

    try:
        timestamp_ms = float(value)
    except (TypeError, ValueError):
        return None

    timestamp_sec = timestamp_ms / 1000.0
    return datetime.fromtimestamp(timestamp_sec, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def event_date_from_iso(value: str | None) -> str | None:
    """Extract UTC date string from an ISO-8601 timestamp."""
    if not value:
        return None

    return value[:10]


def safe_float(value: Any) -> float | None:
    """Convert value to float; return None if conversion fails."""
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int | None:
    """Convert value to int; return None if conversion fails."""
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_usgs_query_url(
    starttime: str,
    endtime: str,
    min_magnitude: float,
    limit: int,
    event_type: str | None = None,
) -> str:
    """Build a USGS Event API query URL."""
    params = {
        "format": "geojson",
        "starttime": starttime,
        "endtime": endtime,
        "minmagnitude": min_magnitude,
        "limit": limit,
        "orderby": "time",
    }

    if event_type:
        params["eventtype"] = event_type

    query_string = urllib.parse.urlencode(params)
    return f"{USGS_EVENT_API}?{query_string}"


def download_json(
    url: str,
    max_attempts: int = 4,
) -> dict[str, Any]:
    """Download JSON with bounded retries for transient network failures."""
    if max_attempts <= 0:
        raise ValueError("max_attempts must be positive")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "SeismoSearch/0.1.0 educational project",
            "Accept": "application/geo+json, application/json",
        },
    )

    raw_bytes: bytes | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw_bytes = response.read()
            break
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"USGS request failed with HTTP {exc.code}: {exc.reason}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt >= max_attempts:
                raise RuntimeError(
                    "Failed to download USGS data after "
                    f"{max_attempts} attempts: {exc}"
                ) from exc

            delay_seconds = 2 ** (attempt - 1)
            print(
                f"[WARN] Transient download failure; retrying in "
                f"{delay_seconds}s ({attempt}/{max_attempts}): {exc}",
                file=sys.stderr,
            )
            time.sleep(delay_seconds)

    if raw_bytes is None:
        raise RuntimeError("USGS download did not return a response body")

    try:
        return json.loads(raw_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse downloaded JSON: {exc}") from exc


def load_json_file(path: Path) -> dict[str, Any]:
    """Load a local JSON or GeoJSON file."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_raw_geojson(payload: dict[str, Any], output_dir: Path) -> Path:
    """Save raw USGS GeoJSON under data/raw/events/."""
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"usgs_events_raw_{timestamp}.geojson"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    return output_path


def normalize_feature(feature: dict[str, Any], ingest_time_utc: str) -> dict[str, Any] | None:
    """Normalize one USGS GeoJSON feature into SeismoSearch event schema."""
    properties = feature.get("properties") or {}
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates") or []

    source_event_id = feature.get("id")

    longitude = safe_float(coordinates[0]) if len(coordinates) > 0 else None
    latitude = safe_float(coordinates[1]) if len(coordinates) > 1 else None
    depth_km = safe_float(coordinates[2]) if len(coordinates) > 2 else None

    event_time_utc = ms_to_utc_iso(properties.get("time"))
    updated_time_utc = ms_to_utc_iso(properties.get("updated"))

    data_quality_notes: list[str] = []

    if not source_event_id:
        data_quality_notes.append("missing_source_event_id")

    if not event_time_utc:
        data_quality_notes.append("missing_event_time_utc")

    if longitude is None:
        data_quality_notes.append("missing_longitude")

    if latitude is None:
        data_quality_notes.append("missing_latitude")

    if source_event_id is None or event_time_utc is None or longitude is None or latitude is None:
        return None

    magnitude = safe_float(properties.get("mag"))

    if magnitude is None:
        data_quality_notes.append("missing_magnitude")

    if depth_km is None:
        data_quality_notes.append("missing_depth_km")

    status = properties.get("status")
    is_reviewed = True if status == "reviewed" else False if status else None

    normalized = {
        "event_id": f"usgs_{source_event_id}",
        "source": "USGS",
        "source_event_id": str(source_event_id),
        "source_url": properties.get("url"),
        "detail_url": properties.get("detail"),
        "event_type": properties.get("type"),
        "status": status,
        "event_time_utc": event_time_utc,
        "updated_time_utc": updated_time_utc,
        "event_date_utc": event_date_from_iso(event_time_utc),
        "longitude": longitude,
        "latitude": latitude,
        "depth_km": depth_km,
        "place": properties.get("place"),
        "region": None,
        "country": None,
        "magnitude": magnitude,
        "magnitude_type": properties.get("magType"),
        "magnitude_error": safe_float(properties.get("magError")),
        "magnitude_nst": safe_int(properties.get("magNst")),
        "magnitude_source": properties.get("magSource"),
        "horizontal_error_km": safe_float(properties.get("horizontalError")),
        "depth_error_km": safe_float(properties.get("depthError")),
        "nst": safe_int(properties.get("nst")),
        "gap_deg": safe_float(properties.get("gap")),
        "dmin_deg": safe_float(properties.get("dmin")),
        "rms_sec": safe_float(properties.get("rms")),
        "location_source": properties.get("locationSource"),
        "felt": safe_int(properties.get("felt")),
        "cdi": safe_float(properties.get("cdi")),
        "mmi": safe_float(properties.get("mmi")),
        "alert": properties.get("alert"),
        "tsunami": safe_int(properties.get("tsunami")),
        "significance": safe_int(properties.get("sig")),
        "net": properties.get("net"),
        "code": properties.get("code"),
        "ids": properties.get("ids"),
        "sources": properties.get("sources"),
        "product_types": properties.get("types"),
        "ingest_time_utc": ingest_time_utc,
        "raw_format": "geojson",
        "raw_record_json": feature,
        "is_reviewed": is_reviewed,
        "is_duplicate_candidate": False,
        "data_quality_note": ";".join(data_quality_notes) if data_quality_notes else None,
    }

    return normalized


def normalize_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize all features in a USGS GeoJSON payload."""
    features = payload.get("features")

    if not isinstance(features, list):
        raise ValueError("Invalid USGS GeoJSON: missing features list.")

    ingest_time_utc = utc_now_iso()
    normalized_records: list[dict[str, Any]] = []

    for feature in features:
        if not isinstance(feature, dict):
            continue

        normalized = normalize_feature(feature, ingest_time_utc=ingest_time_utc)

        if normalized is not None:
            normalized_records.append(normalized)

    return normalized_records


def write_jsonl(records: list[dict[str, Any]], output_path: Path) -> None:
    """Write normalized event records as JSONL."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            file.write("\n")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Download and normalize USGS earthquake events for SeismoSearch."
    )

    parser.add_argument(
        "--starttime",
        default="2024-01-01",
        help="USGS query start date or datetime, for example 2024-01-01.",
    )

    parser.add_argument(
        "--endtime",
        default="2025-12-31",
        help="USGS query end date or datetime, for example 2025-12-31.",
    )

    parser.add_argument(
        "--min-magnitude",
        type=float,
        default=4.5,
        help="Minimum magnitude for USGS query.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum number of events to request.",
    )

    parser.add_argument(
        "--event-type",
        default="earthquake",
        help=(
            "USGS event type filter. Use an empty value to include all "
            "catalog event types."
        ),
    )

    parser.add_argument(
        "--raw-input",
        type=Path,
        default=None,
        help="Optional local raw GeoJSON file. If provided, download is skipped.",
    )

    parser.add_argument(
        "--raw-output-dir",
        type=Path,
        default=Path("data/raw/events"),
        help="Directory for saving raw USGS GeoJSON.",
    )

    parser.add_argument(
        "--processed-output",
        type=Path,
        default=Path("data/processed/events_sample_1000.jsonl"),
        help="Output JSONL path for normalized records.",
    )

    return parser.parse_args()


def main() -> int:
    """Run event ingestion."""
    args = parse_args()

    if args.limit <= 0:
        print("ERROR: --limit must be positive.", file=sys.stderr)
        return 1

    if args.raw_input:
        print(f"Loading local raw GeoJSON: {args.raw_input}")
        payload = load_json_file(args.raw_input)
        raw_path = args.raw_input
    else:
        url = build_usgs_query_url(
            starttime=args.starttime,
            endtime=args.endtime,
            min_magnitude=args.min_magnitude,
            limit=args.limit,
            event_type=args.event_type or None,
        )
        print(f"Downloading USGS events from: {url}")
        payload = download_json(url)
        raw_path = save_raw_geojson(payload, args.raw_output_dir)
        print(f"Saved raw GeoJSON to: {raw_path}")

    records = normalize_payload(payload)
    write_jsonl(records, args.processed_output)

    print(f"Normalized records: {len(records)}")
    print(f"Processed JSONL saved to: {args.processed_output}")

    if len(records) == 0:
        print("WARNING: No normalized records were produced.", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
