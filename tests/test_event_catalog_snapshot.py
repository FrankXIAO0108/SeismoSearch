"""Tests for scalable, reproducible event catalog snapshot construction."""

from __future__ import annotations

from datetime import date

import pytest

from scripts.build_event_catalog_snapshot import (
    TimeWindow,
    build_time_windows,
    collect_catalog_records,
)


def make_feature(event_id: str, time_ms: int, updated_ms: int) -> dict:
    return {
        "type": "Feature",
        "id": event_id,
        "properties": {
            "time": time_ms,
            "updated": updated_ms,
            "mag": 5.0,
            "type": "earthquake",
            "status": "reviewed",
            "url": f"https://example.test/{event_id}",
            "detail": f"https://example.test/{event_id}.geojson",
        },
        "geometry": {
            "type": "Point",
            "coordinates": [120.0, 30.0, 10.0],
        },
    }


def test_build_time_windows_covers_range_without_gaps() -> None:
    windows = build_time_windows(
        date(2025, 1, 1),
        date(2025, 1, 11),
        window_days=4,
    )
    assert windows == [
        TimeWindow(date(2025, 1, 1), date(2025, 1, 5)),
        TimeWindow(date(2025, 1, 5), date(2025, 1, 9)),
        TimeWindow(date(2025, 1, 9), date(2025, 1, 11)),
    ]


def test_collect_catalog_records_deduplicates_boundary_event() -> None:
    windows = [
        TimeWindow(date(2025, 1, 1), date(2025, 1, 2)),
        TimeWindow(date(2025, 1, 2), date(2025, 1, 3)),
    ]
    responses = iter(
        [
            {
                "features": [
                    make_feature("shared", 1_735_776_000_000, 1000),
                    make_feature("first", 1_735_732_800_000, 1000),
                ]
            },
            {
                "features": [
                    make_feature("shared", 1_735_776_000_000, 2000),
                    make_feature("second", 1_735_862_400_000, 1000),
                ]
            },
        ]
    )

    records, stats = collect_catalog_records(
        windows=windows,
        min_magnitude=4.5,
        request_limit=20_000,
        event_type="earthquake",
        raw_output_dir=None,
        fetcher=lambda _url: next(responses),
    )

    assert [record["event_id"] for record in records] == [
        "usgs_first",
        "usgs_shared",
        "usgs_second",
    ]
    assert stats["raw_feature_count"] == 4
    assert stats["normalized_count"] == 3
    assert stats["duplicate_count"] == 1
    shared = next(record for record in records if record["event_id"] == "usgs_shared")
    assert shared["updated_time_utc"].endswith("02Z")


def test_collect_catalog_records_rejects_possible_truncation() -> None:
    window = TimeWindow(date(2025, 1, 1), date(2025, 1, 2))
    payload = {
        "features": [
            make_feature(f"event-{index}", 1_735_732_800_000 + index, 1000)
            for index in range(2)
        ]
    }

    with pytest.raises(RuntimeError, match="may be truncated"):
        collect_catalog_records(
            windows=[window],
            min_magnitude=4.5,
            request_limit=2,
            event_type="earthquake",
            raw_output_dir=None,
            fetcher=lambda _url: payload,
        )
