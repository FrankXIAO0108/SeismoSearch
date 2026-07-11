"""
Download one reference source and register it in source_registry.jsonl.

Example:

python scripts/register_reference_source.py `
    --source-id usgs_aftershock_glossary `
    --title "USGS Earthquake Glossary - Aftershock" `
    --url "https://earthquake.usgs.gov/learn/glossary/?term=aftershock" `
    --raw-filename "usgs_aftershock_glossary.html" `
    --source-type official_glossary `
    --topic aftershock `
    --topic earthquake_sequence
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any


# 项目根目录。
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 原始参考资料目录。
RAW_REFERENCE_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "reference_docs"
    / "usgs"
)

# 原始资料登记表。
REGISTRY_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "reference_docs"
    / "source_registry.jsonl"
)


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description=(
            "Download and register a SeismoSearch reference source."
        )
    )

    parser.add_argument(
        "--source-id",
        required=True,
        help="Unique source identifier.",
    )

    parser.add_argument(
        "--title",
        required=True,
        help="Source title.",
    )

    parser.add_argument(
        "--url",
        required=True,
        help="Original source URL.",
    )

    parser.add_argument(
        "--raw-filename",
        required=True,
        help="Raw HTML filename.",
    )

    parser.add_argument(
        "--source-type",
        required=True,
        help="Source type, for example official_glossary.",
    )

    parser.add_argument(
        "--topic",
        action="append",
        default=[],
        help="Topic. Repeat --topic for multiple topics.",
    )

    parser.add_argument(
        "--organization",
        default="U.S. Geological Survey",
        help="Source organization.",
    )

    parser.add_argument(
        "--language",
        default="en",
        help="Source language.",
    )

    parser.add_argument(
        "--status",
        default="active",
        choices=[
            "active",
            "draft",
            "deprecated",
            "archived",
        ],
        help="Registry status.",
    )

    return parser.parse_args()


def validate_raw_filename(raw_filename: str) -> None:
    """检查 raw filename，避免写到目标目录之外。"""
    filename_path = Path(raw_filename)

    if filename_path.name != raw_filename:
        raise ValueError(
            "--raw-filename must be a filename, not a path."
        )

    if filename_path.suffix.lower() not in {
        ".html",
        ".htm",
        ".txt",
        ".md",
    }:
        raise ValueError(
            "Supported raw file suffixes: "
            ".html, .htm, .txt, .md"
        )


def download_source(
    url: str,
    output_path: Path,
) -> None:
    """下载原始资料。"""
    RAW_REFERENCE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "SeismoSearch-Reference-Collector/1.0"
            ),
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            content = response.read()

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Download failed: {error}"
        ) from error

    output_path.write_bytes(content)

    print(
        f"[PASS] Downloaded: "
        f"{output_path.relative_to(PROJECT_ROOT).as_posix()}"
    )

    print(
        f"[INFO] Raw size: "
        f"{output_path.stat().st_size} bytes"
    )


def load_registry() -> list[dict[str, Any]]:
    """读取现有 source_registry.jsonl。"""
    if not REGISTRY_PATH.exists():
        return []

    records: list[dict[str, Any]] = []

    for line_number, raw_line in enumerate(
        REGISTRY_PATH.read_text(
            encoding="utf-8"
        ).splitlines(),
        start=1,
    ):
        line = raw_line.strip()

        if not line:
            continue

        try:
            record = json.loads(line)

        except json.JSONDecodeError as error:
            raise ValueError(
                "Invalid JSONL at "
                f"line {line_number}: {error}"
            ) from error

        records.append(record)

    return records


def write_registry(
    records: list[dict[str, Any]],
) -> None:
    """完整重写 JSONL，保证每条记录占一行。"""
    REGISTRY_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    content = "\n".join(
        json.dumps(
            record,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for record in records
    )

    if content:
        content += "\n"

    REGISTRY_PATH.write_text(
        content,
        encoding="utf-8",
    )


def upsert_registry_record(
    new_record: dict[str, Any],
) -> None:
    """按 source_id 新增或更新登记记录。"""
    records = load_registry()

    updated = False

    for index, record in enumerate(records):
        if (
            record.get("source_id")
            == new_record["source_id"]
        ):
            records[index] = new_record
            updated = True
            break

    if not updated:
        records.append(new_record)

    write_registry(records)

    action = (
        "Updated"
        if updated
        else "Added"
    )

    print(
        f"[PASS] {action} registry record: "
        f"{new_record['source_id']}"
    )


def main() -> int:
    """主流程。"""
    args = parse_args()

    try:
        validate_raw_filename(
            args.raw_filename
        )

        raw_path = (
            RAW_REFERENCE_DIR
            / args.raw_filename
        )

        download_source(
            url=args.url,
            output_path=raw_path,
        )

        raw_repo_path = (
            raw_path
            .relative_to(PROJECT_ROOT)
            .as_posix()
        )

        record = {
            "source_id": args.source_id,
            "title": args.title,
            "source_organization": (
                args.organization
            ),
            "source_type": (
                args.source_type
            ),
            "source_language": (
                args.language
            ),
            "source_url": args.url,
            "retrieved_at": (
                date.today().isoformat()
            ),
            "raw_path": raw_repo_path,
            "topics": args.topic,
            "status": args.status,
        }

        upsert_registry_record(
            record
        )

    except (
        ValueError,
        RuntimeError,
    ) as error:
        print(
            f"[ERROR] {error}"
        )

        return 1

    print()
    print(
        "[PASS] Reference source workflow completed."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )