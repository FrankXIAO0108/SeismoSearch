"""
Run an unattended retrieval evaluation matrix for SeismoSearch.

The script runs:

1. pytest
2. keyword + raw
3. keyword + planner
4. bm25 + raw
5. bm25 + planner
6. dense + raw
7. dense + planner
8. hybrid + raw
9. hybrid + planner
10. hybrid_rerank + raw
11. hybrid_rerank + planner

All outputs are written to a timestamped directory under:

eval/results/overnight/

The script does not modify runtime documents and does not commit Git changes.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


# 项目根目录。
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Python 源码目录。
SRC_DIR = PROJECT_ROOT / "src"

# 检索评测脚本。
RETRIEVAL_EVAL_SCRIPT = (
    PROJECT_ROOT
    / "scripts"
    / "run_retrieval_eval.py"
)

# 默认评测集。
DEFAULT_EVAL_FILE = (
    PROJECT_ROOT
    / "eval"
    / "retrieval_eval_60.jsonl"
)

# 夜间实验结果根目录。
OVERNIGHT_ROOT = (
    PROJECT_ROOT
    / "eval"
    / "results"
    / "overnight"
)


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description=(
            "Run the full SeismoSearch retrieval evaluation matrix."
        )
    )

    parser.add_argument(
        "--eval-file",
        type=Path,
        default=DEFAULT_EVAL_FILE,
        help="Retrieval evaluation JSONL file.",
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

    parser.add_argument(
        "--skip-reranker",
        action="store_true",
        help="Skip hybrid_rerank runs.",
    )

    return parser.parse_args()


def build_env() -> dict[str, str]:
    """
    构建子进程环境变量。
    """
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

    # 强制 Python 使用 UTF-8 输出。
    env["PYTHONUTF8"] = "1"

    return env


def run_command(
    command: list[str],
    log_path: Path,
) -> tuple[int, float]:
    """
    执行一个命令，并将 stdout/stderr 同时写入日志。
    """
    start_time = datetime.now()

    print()
    print("=" * 100)
    print("RUN")
    print("=" * 100)
    print(" ".join(command))
    print(f"Log: {log_path.relative_to(PROJECT_ROOT)}")

    log_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    env = build_env()

    with log_path.open(
        "w",
        encoding="utf-8",
    ) as log_file:
        process = subprocess.Popen(
            command,
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        assert process.stdout is not None

        for line in process.stdout:
            print(
                line,
                end="",
            )

            log_file.write(
                line
            )

            log_file.flush()

        return_code = process.wait()

    end_time = datetime.now()

    duration_seconds = (
        end_time - start_time
    ).total_seconds()

    print()
    print(
        f"[DONE] exit_code={return_code} "
        f"duration={duration_seconds:.2f}s"
    )

    return (
        return_code,
        duration_seconds,
    )


def load_result_summary(
    result_path: Path,
) -> dict[str, Any] | None:
    """
    从 retrieval eval 输出 JSON 中读取 summary。
    """
    if not result_path.exists():
        return None

    try:
        data = json.loads(
            result_path.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError:
        return None

    summary = data.get(
        "summary"
    )

    if not isinstance(
        summary,
        dict,
    ):
        return None

    return summary


def run_pytest(
    output_dir: Path,
) -> dict[str, Any]:
    """
    运行 pytest。
    """
    log_path = (
        output_dir
        / "pytest.log"
    )

    return_code, duration_seconds = run_command(
        command=[
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "-q",
        ],
        log_path=log_path,
    )

    return {
        "name": "pytest",
        "success": (
            return_code == 0
        ),
        "exit_code": return_code,
        "duration_seconds": (
            duration_seconds
        ),
        "log_path": (
            log_path
            .relative_to(PROJECT_ROOT)
            .as_posix()
        ),
    }


def run_retrieval_eval(
    eval_file: Path,
    output_dir: Path,
    retriever: str,
    query_mode: str,
    top_k: int,
) -> dict[str, Any]:
    """
    运行一组 retrieval eval。
    """
    run_name = (
        f"{retriever}_"
        f"{query_mode}_"
        f"top{top_k}"
    )

    result_path = (
        output_dir
        / f"{run_name}.json"
    )

    log_path = (
        output_dir
        / f"{run_name}.log"
    )

    command = [
        sys.executable,
        str(
            RETRIEVAL_EVAL_SCRIPT
        ),
        "--eval-file",
        str(
            eval_file
        ),
        "--output-file",
        str(
            result_path
        ),
        "--query-mode",
        query_mode,
        "--retriever",
        retriever,
        "--top-k",
        str(
            top_k
        ),
    ]

    return_code, duration_seconds = run_command(
        command=command,
        log_path=log_path,
    )

    summary = load_result_summary(
        result_path
    )

    return {
        "name": run_name,
        "retriever": retriever,
        "query_mode": query_mode,
        "top_k": top_k,
        "success": (
            return_code == 0
        ),
        "exit_code": return_code,
        "duration_seconds": (
            duration_seconds
        ),
        "result_path": (
            result_path
            .relative_to(PROJECT_ROOT)
            .as_posix()
        ),
        "log_path": (
            log_path
            .relative_to(PROJECT_ROOT)
            .as_posix()
        ),
        "summary": summary,
    }


def print_final_table(
    runs: list[dict[str, Any]],
) -> None:
    """
    输出最终汇总。
    """
    print()
    print("=" * 120)
    print("OVERNIGHT RETRIEVAL MATRIX SUMMARY")
    print("=" * 120)

    for run in runs:
        if run["name"] == "pytest":
            print(
                f"{run['name']:<35} "
                f"success={run['success']} "
                f"duration={run['duration_seconds']:.2f}s"
            )

            continue

        summary = (
            run.get("summary")
            or {}
        )

        print(
            f"{run['name']:<35} "
            f"success={run['success']} "
            f"requirement_hit="
            f"{summary.get('requirement_hit_rate')} "
            f"mrr="
            f"{summary.get('mrr')} "
            f"failed="
            f"{summary.get('failed_count')} "
            f"duration="
            f"{run['duration_seconds']:.2f}s"
        )


def print_git_status(
    output_dir: Path,
) -> None:
    """
    保存当前 git status。
    """
    log_path = (
        output_dir
        / "git_status.log"
    )

    run_command(
        command=[
            "git",
            "status",
            "--short",
        ],
        log_path=log_path,
    )


def main() -> int:
    """
    主流程。
    """
    args = parse_args()

    eval_file = (
        args.eval_file
        if args.eval_file.is_absolute()
        else PROJECT_ROOT
        / args.eval_file
    ).resolve()

    if not eval_file.exists():
        print(
            f"[ERROR] Eval file not found: "
            f"{eval_file}"
        )

        return 2

    if args.top_k <= 0:
        print(
            "[ERROR] --top-k must be positive."
        )

        return 2

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_dir = (
        OVERNIGHT_ROOT
        / timestamp
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("=" * 100)
    print(
        "SEISMOSEARCH OVERNIGHT RETRIEVAL MATRIX"
    )
    print("=" * 100)

    print(
        f"Eval file: "
        f"{eval_file.relative_to(PROJECT_ROOT)}"
    )

    print(
        f"Output dir: "
        f"{output_dir.relative_to(PROJECT_ROOT)}"
    )

    print(
        f"Top-K: "
        f"{args.top_k}"
    )

    runs: list[dict[str, Any]] = []

    if not args.skip_pytest:
        runs.append(
            run_pytest(
                output_dir=output_dir
            )
        )

    retrievers = [
        "keyword",
        "bm25",
        "dense",
        "hybrid",
    ]

    if not args.skip_reranker:
        retrievers.append(
            "hybrid_rerank"
        )

    query_modes = [
        "raw",
        "planner",
    ]

    for retriever in retrievers:
        for query_mode in query_modes:
            run_result = run_retrieval_eval(
                eval_file=eval_file,
                output_dir=output_dir,
                retriever=retriever,
                query_mode=query_mode,
                top_k=args.top_k,
            )

            runs.append(
                run_result
            )

    print_git_status(
        output_dir=output_dir
    )

    summary_path = (
        output_dir
        / "summary.json"
    )

    summary_payload = {
        "started_at_directory": timestamp,
        "eval_file": (
            eval_file
            .relative_to(PROJECT_ROOT)
            .as_posix()
        ),
        "top_k": args.top_k,
        "runs": runs,
    }

    summary_path.write_text(
        json.dumps(
            summary_payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print_final_table(
        runs
    )

    print()
    print(
        f"Summary saved to: "
        f"{summary_path.relative_to(PROJECT_ROOT)}"
    )

    failed_runs = [
        run
        for run in runs
        if not run["success"]
    ]

    if failed_runs:
        print()
        print(
            f"[WARNING] "
            f"{len(failed_runs)} run(s) failed."
        )

        return 1

    print()
    print(
        "[PASS] All overnight runs completed."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )