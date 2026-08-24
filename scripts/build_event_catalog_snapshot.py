"""Build a reproducible, multi-window USGS earthquake catalog snapshot.

The legacy ``ingest_events.py`` command intentionally keeps a small sample.
This command is the scalable companion used for larger local catalogs:

USGS Event API windows -> normalized records -> deduplication -> JSONL + manifest

Each API request is bounded below the USGS 20,000-result service limit.  A
window returning exactly the configured request limit is rejected rather than
silently accepting a potentially truncated catalog.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from scripts.ingest_events import (
        build_usgs_query_url,
        download_json,
        normalize_payload,
        write_jsonl,
    )
except ModuleNotFoundError:  # Direct execution: python scripts/<file>.py
    from ingest_events import (  # type: ignore[no-redef]
        build_usgs_query_url,
        download_json,
        normalize_payload,
        write_jsonl,
    )


USGS_MAX_RESULTS = 20_000
MANIFEST_SCHEMA_VERSION = "event_catalog_snapshot_v1"
USGS_API_DOCS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/"


@dataclass(frozen=True)
class TimeWindow:
    """One half-open UTC date window used for an API request."""

    start: date
    end: date

    @property
    def start_text(self) -> str:
        return self.start.isoformat()

    @property
    def end_text(self) -> str:
        return self.end.isoformat()


def parse_iso_date(value: str) -> date:
    """Parse an ISO date with a clear command-line validation error."""
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"Invalid ISO date: {value!r}") from error


def build_time_windows(
    start: date,
    end: date,
    window_days: int,
) -> list[TimeWindow]:
    """Split ``[start, end)`` into deterministic adjacent date windows."""
    if start >= end:
        raise ValueError("start date must be before end date")
    if window_days <= 0:
        raise ValueError("window_days must be positive")

    windows: list[TimeWindow] = []
    cursor = start
    step = timedelta(days=window_days)

    while cursor < end:
        next_cursor = min(cursor + step, end)
        windows.append(TimeWindow(start=cursor, end=next_cursor))
        cursor = next_cursor

    return windows


def save_raw_window(
    payload: dict[str, Any],
    output_dir: Path,
    window: TimeWindow,
) -> Path:
    """Save a raw response with a deterministic, collision-free filename."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / (
        f"usgs_{window.start_text}_{window.end_text}.geojson"
    )
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    return output_path


def prefer_newer_record(
    current: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Keep the most recently updated version of a duplicate USGS event."""
    current_updated = str(current.get("updated_time_utc") or "")
    candidate_updated = str(candidate.get("updated_time_utc") or "")
    if candidate_updated > current_updated:
        return candidate
    return current


def collect_catalog_records(
    *,
    windows: list[TimeWindow],
    min_magnitude: float,
    request_limit: int,
    event_type: str | None,
    raw_output_dir: Path | None,
    fetcher: Callable[[str], dict[str, Any]] = download_json,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Download, normalize, and deduplicate all configured windows."""
    if request_limit <= 0 or request_limit > USGS_MAX_RESULTS:
        raise ValueError(
            f"request_limit must be between 1 and {USGS_MAX_RESULTS}"
        )

    records_by_id: dict[str, dict[str, Any]] = {}
    raw_feature_count = 0
    normalized_before_dedup = 0
    window_summaries: list[dict[str, Any]] = []

    for index, window in enumerate(windows, start=1):
        url = build_usgs_query_url(
            starttime=window.start_text,
            endtime=window.end_text,
            min_magnitude=min_magnitude,
            limit=request_limit,
            event_type=event_type,
        )
        print(
            f"[{index}/{len(windows)}] "
            f"Downloading {window.start_text} -> {window.end_text}"
        )
        payload = fetcher(url)
        features = payload.get("features")
        if not isinstance(features, list):
            raise ValueError("Invalid USGS response: missing features list")

        feature_count = len(features)
        if feature_count >= request_limit:
            raise RuntimeError(
                "USGS result window reached the request limit and may be "
                f"truncated: {window.start_text} -> {window.end_text}, "
                f"count={feature_count}. Use a smaller --window-days value."
            )

        raw_path: str | None = None
        if raw_output_dir is not None:
            saved_path = save_raw_window(payload, raw_output_dir, window)
            raw_path = saved_path.as_posix()

        normalized_records = normalize_payload(payload)
        raw_feature_count += feature_count
        normalized_before_dedup += len(normalized_records)

        for record in normalized_records:
            event_id = str(record["event_id"])
            existing = records_by_id.get(event_id)
            if existing is None:
                records_by_id[event_id] = record
            else:
                records_by_id[event_id] = prefer_newer_record(
                    existing,
                    record,
                )

        window_summaries.append(
            {
                "start": window.start_text,
                "end": window.end_text,
                "raw_feature_count": feature_count,
                "normalized_count": len(normalized_records),
                "raw_path": raw_path,
            }
        )

    records = sorted(
        records_by_id.values(),
        key=lambda item: (
            str(item.get("event_time_utc") or ""),
            str(item.get("event_id") or ""),
        ),
    )
    collection_stats = {
        "raw_feature_count": raw_feature_count,
        "normalized_before_dedup": normalized_before_dedup,
        "duplicate_count": normalized_before_dedup - len(records),
        "normalized_count": len(records),
        "windows": window_summaries,
    }
    return records, collection_stats


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest for a generated artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(
    *,
    records: list[dict[str, Any]],
    collection_stats: dict[str, Any],
    output_path: Path,
    start: date,
    end: date,
    min_magnitude: float,
    window_days: int,
    request_limit: int,
    event_type: str | None,
) -> dict[str, Any]:
    """Build provenance and quality metadata for the normalized snapshot."""
    times = [str(record["event_time_utc"]) for record in records]
    magnitudes = [
        float(record["magnitude"])
        for record in records
        if record.get("magnitude") is not None
    ]
    reviewed_count = sum(
        1 for record in records if record.get("is_reviewed") is True
    )
    missing_magnitude_count = sum(
        1 for record in records if record.get("magnitude") is None
    )

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "source": {
            "organization": "U.S. Geological Survey",
            "service": "FDSN Event Web Service",
            "api_documentation": USGS_API_DOCS_URL,
        },
        "query": {
            "start": start.isoformat(),
            "end_exclusive": end.isoformat(),
            "min_magnitude": min_magnitude,
            "window_days": window_days,
            "request_limit": request_limit,
            "ordering": "time",
            "event_type": event_type,
        },
        "artifact": {
            "path": output_path.as_posix(),
            "sha256": sha256_file(output_path),
            "size_bytes": output_path.stat().st_size,
        },
        "quality": {
            "raw_feature_count": collection_stats["raw_feature_count"],
            "normalized_before_dedup": collection_stats[
                "normalized_before_dedup"
            ],
            "duplicate_count": collection_stats["duplicate_count"],
            "normalized_count": len(records),
            "dropped_invalid_count": (
                collection_stats["raw_feature_count"]
                - collection_stats["normalized_before_dedup"]
            ),
            "reviewed_count": reviewed_count,
            "missing_magnitude_count": missing_magnitude_count,
            "event_time_min": min(times) if times else None,
            "event_time_max": max(times) if times else None,
            "magnitude_min": min(magnitudes) if magnitudes else None,
            "magnitude_max": max(magnitudes) if magnitudes else None,
        },
        "windows": collection_stats["windows"],
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Build a reproducible multi-window USGS catalog snapshot."
    )
    parser.add_argument("--starttime", required=True)
    parser.add_argument("--endtime", required=True)
    parser.add_argument("--min-magnitude", type=float, default=4.5)
    parser.add_argument("--window-days", type=int, default=180)
    parser.add_argument("--request-limit", type=int, default=USGS_MAX_RESULTS)
    parser.add_argument("--event-type", default="earthquake")
    parser.add_argument("--processed-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    parser.add_argument(
        "--raw-output-dir",
        type=Path,
        default=Path("data/raw/events/catalog_snapshot"),
    )
    parser.add_argument(
        "--skip-raw",
        action="store_true",
        help="Do not retain raw per-window GeoJSON responses.",
    )
    return parser.parse_args()


def main() -> int:
    """Build the requested catalog snapshot and its manifest."""
    args = parse_args()
    try:
        start = parse_iso_date(args.starttime)
        end = parse_iso_date(args.endtime)
        windows = build_time_windows(start, end, args.window_days)
        raw_output_dir = None if args.skip_raw else args.raw_output_dir
        records, collection_stats = collect_catalog_records(
            windows=windows,
            min_magnitude=args.min_magnitude,
            request_limit=args.request_limit,
            event_type=args.event_type or None,
            raw_output_dir=raw_output_dir,
        )
        if not records:
            raise RuntimeError("USGS query produced no normalized records")

        write_jsonl(records, args.processed_output)
        manifest = build_manifest(
            records=records,
            collection_stats=collection_stats,
            output_path=args.processed_output,
            start=start,
            end=end,
            min_magnitude=args.min_magnitude,
            window_days=args.window_days,
            request_limit=args.request_limit,
            event_type=args.event_type or None,
        )
        args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
        args.manifest_output.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, RuntimeError, ValueError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1

    print(f"[PASS] Normalized events: {len(records)}")
    print(f"[PASS] JSONL: {args.processed_output}")
    print(f"[PASS] Manifest: {args.manifest_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
