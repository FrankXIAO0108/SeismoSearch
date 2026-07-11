"""
Corpus workflow for SeismoSearch.

Example:

python scripts/run_corpus_workflow.py `
    --doc data/processed/docs/earthquake_swarm.md `
    --query "earthquake swarm 和 mainshock-aftershock sequence 有什么区别？" `
    --probe-query "最近很多小地震是不是说明马上会发生大地震？"

Rules:
- --query:
  The target document must appear in top-k.
- --probe-query:
  Only print retrieval results. It does not affect workflow PASS/FAIL.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


# 项目根目录。
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Python 源代码目录。
SRC_DIR = PROJECT_ROOT / "src"


def normalize_repo_path(path: Path) -> str:
    """
    将绝对路径转换为仓库内相对路径。
    """
    return path.resolve().relative_to(
        PROJECT_ROOT.resolve()
    ).as_posix()


def resolve_document_path(raw_path: str) -> Path:
    """
    解析文档路径。
    """
    path = Path(raw_path)

    if not path.is_absolute():
        path = PROJECT_ROOT / path

    return path.resolve()


def validate_document(document_path: Path) -> None:
    """
    检查文档基本格式。
    """
    if not document_path.exists():
        raise FileNotFoundError(
            f"Document does not exist: {document_path}"
        )

    if not document_path.is_file():
        raise ValueError(
            f"Document path is not a file: {document_path}"
        )

    if document_path.suffix.lower() != ".md":
        raise ValueError(
            f"Runtime corpus document must be Markdown: {document_path}"
        )

    text = document_path.read_text(
        encoding="utf-8"
    )

    if not text.strip():
        raise ValueError(
            f"Document is empty: {document_path}"
        )

    if not text.lstrip().startswith("# "):
        raise ValueError(
            f"Document should start with an H1 title: {document_path}"
        )

    # 检查容易产生检索噪声的 section。
    noisy_headings = [
        "## Example Queries",
        "## 示例问题",
    ]

    for heading in noisy_headings:
        if heading in text:
            print(
                f"[WARNING] Potential retrieval-noise heading: "
                f"{heading}"
            )


def load_hybrid_retriever():
    """
    导入 Hybrid Retriever。
    """
    src_path = str(SRC_DIR)

    if src_path not in sys.path:
        sys.path.insert(
            0,
            src_path,
        )

    from seismosearch.hybrid_retriever import (
        retrieve_docs_hybrid,
    )

    return retrieve_docs_hybrid


def retrieve(
    query: str,
    top_k: int,
) -> list[dict[str, Any]]:
    """
    执行 Hybrid Retrieval。
    """
    retrieve_docs_hybrid = (
        load_hybrid_retriever()
    )

    result = retrieve_docs_hybrid(
        query,
        top_k=top_k,
    )

    return result.get(
        "chunks",
        [],
    )


def print_results(
    query: str,
    chunks: list[dict[str, Any]],
) -> None:
    """
    打印检索结果。
    """
    print()
    print("=" * 88)
    print(f"QUERY: {query}")
    print("=" * 88)

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):
        source_path = str(
            chunk.get(
                "source_path",
                "",
            )
        )

        heading = str(
            chunk.get(
                "heading",
                "",
            )
        )

        print(
            f"{index}. "
            f"{source_path} | "
            f"{heading}"
        )


def run_required_query(
    document_repo_path: str,
    query: str,
    top_k: int,
) -> bool:
    """
    必须命中目标文档的检索测试。
    """
    chunks = retrieve(
        query=query,
        top_k=top_k,
    )

    print_results(
        query=query,
        chunks=chunks,
    )

    target_rank: int | None = None

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):
        source_path = str(
            chunk.get(
                "source_path",
                "",
            )
        ).replace(
            "\\",
            "/",
        )

        if (
            target_rank is None
            and source_path == document_repo_path
        ):
            target_rank = index

    print("-" * 88)

    if target_rank is None:
        print(
            f"[FAIL] Target document not found "
            f"in top-{top_k}: "
            f"{document_repo_path}"
        )

        return False

    print(
        f"[PASS] Target document found "
        f"at rank {target_rank}: "
        f"{document_repo_path}"
    )

    return True


def run_probe_query(
    query: str,
    top_k: int,
) -> None:
    """
    只观察检索结果，不参与 PASS/FAIL。
    """
    chunks = retrieve(
        query=query,
        top_k=top_k,
    )

    print_results(
        query=query,
        chunks=chunks,
    )

    print("-" * 88)

    print(
        "[PROBE] Diagnostic query only. "
        "This result does not affect workflow status."
    )


def run_pytest() -> bool:
    """
    运行 pytest。
    """
    print()
    print("=" * 88)
    print("RUNNING PYTEST")
    print("=" * 88)

    env = os.environ.copy()

    existing_pythonpath = env.get(
        "PYTHONPATH",
        "",
    )

    if existing_pythonpath:
        env["PYTHONPATH"] = (
            f"{SRC_DIR}"
            f"{os.pathsep}"
            f"{existing_pythonpath}"
        )
    else:
        env["PYTHONPATH"] = str(
            SRC_DIR
        )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "-q",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
    )

    if completed.returncode == 0:
        print(
            "[PASS] pytest passed"
        )

        return True

    print(
        "[FAIL] pytest failed "
        f"with exit code "
        f"{completed.returncode}"
    )

    return False


def print_git_status() -> None:
    """
    输出 git status --short。
    """
    print()
    print("=" * 88)
    print("GIT STATUS")
    print("=" * 88)

    subprocess.run(
        [
            "git",
            "status",
            "--short",
        ],
        cwd=PROJECT_ROOT,
        check=False,
    )


def parse_args() -> argparse.Namespace:
    """
    解析命令行参数。
    """
    parser = argparse.ArgumentParser(
        description=(
            "Run SeismoSearch corpus workflow."
        )
    )

    parser.add_argument(
        "--doc",
        required=True,
        help=(
            "Target runtime Markdown document."
        ),
    )

    parser.add_argument(
        "--query",
        action="append",
        default=[],
        help=(
            "Required query. "
            "Target document must appear in top-k."
        ),
    )

    parser.add_argument(
        "--probe-query",
        action="append",
        default=[],
        help=(
            "Diagnostic query. "
            "Only print retrieval results."
        ),
    )

    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Retrieval top-k.",
    )

    parser.add_argument(
        "--skip-pytest",
        action="store_true",
        help="Skip pytest.",
    )

    return parser.parse_args()


def main() -> int:
    """
    主流程。
    """
    args = parse_args()

    if args.top_k <= 0:
        print(
            "[ERROR] --top-k must be positive."
        )

        return 2

    if (
        not args.query
        and not args.probe_query
    ):
        print(
            "[ERROR] At least one "
            "--query or --probe-query is required."
        )

        return 2

    try:
        document_path = (
            resolve_document_path(
                args.doc
            )
        )

        validate_document(
            document_path
        )

    except (
        FileNotFoundError,
        ValueError,
    ) as error:
        print(
            f"[ERROR] {error}"
        )

        return 2

    document_repo_path = (
        normalize_repo_path(
            document_path
        )
    )

    print("=" * 88)
    print(
        "SEISMOSEARCH CORPUS WORKFLOW"
    )
    print("=" * 88)

    print(
        f"Document:        "
        f"{document_repo_path}"
    )

    print(
        f"Required Query:  "
        f"{len(args.query)}"
    )

    print(
        f"Probe Query:     "
        f"{len(args.probe_query)}"
    )

    print(
        f"Top-K:           "
        f"{args.top_k}"
    )

    required_results: list[bool] = []

    for query in args.query:
        passed = run_required_query(
            document_repo_path=(
                document_repo_path
            ),
            query=query,
            top_k=args.top_k,
        )

        required_results.append(
            passed
        )

    for query in args.probe_query:
        run_probe_query(
            query=query,
            top_k=args.top_k,
        )

    if required_results:
        retrieval_passed = all(
            required_results
        )
    else:
        retrieval_passed = True

    if args.skip_pytest:
        pytest_passed = True

        print()
        print(
            "[SKIP] pytest skipped"
        )
    else:
        pytest_passed = run_pytest()

    print_git_status()

    print()
    print("=" * 88)
    print("WORKFLOW SUMMARY")
    print("=" * 88)

    print(
        "Required Retrieval: "
        f"{'PASS' if retrieval_passed else 'FAIL'}"
    )

    print(
        "Pytest:             "
        f"{'PASS' if pytest_passed else 'FAIL'}"
    )

    if (
        retrieval_passed
        and pytest_passed
    ):
        print()
        print(
            "[PASS] Corpus workflow "
            "completed successfully."
        )

        return 0

    print()
    print(
        "[FAIL] Corpus workflow "
        "has failures."
    )

    return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )