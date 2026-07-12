"""
Create and freeze SeismoSearch retrieval holdout v1.

This script creates:
- eval/retrieval_holdout_26_v1.jsonl
- eval/retrieval_eval_manifest_v2.json
- tests/test_retrieval_eval_data.py

Important:
- Commit these files before the first holdout evaluation.
- Do not modify holdout v1 after seeing its retrieval results.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEV_PATH = PROJECT_ROOT / "eval" / "retrieval_eval_60_corpus_v2.jsonl"
HOLDOUT_PATH = PROJECT_ROOT / "eval" / "retrieval_holdout_26_v1.jsonl"
MANIFEST_PATH = PROJECT_ROOT / "eval" / "retrieval_eval_manifest_v2.json"
TEST_PATH = PROJECT_ROOT / "tests" / "test_retrieval_eval_data.py"


HOLDOUT_RECORDS: list[dict[str, Any]] = [
    {
        "query_id": "holdout_concept_001",
        "query": "同一场 M7 地震，为什么远处城市的体感可能比近处弱很多？",
        "expected_source_path_contains": "seismology_concepts.md",
        "must_contain_any_groups": [
            ["震级", "magnitude", "M7"],
            ["烈度", "intensity", "体感", "震感"],
            ["距离", "distance", "地点"],
        ],
        "expected_behavior": "retrieve magnitude, intensity, and distance relationship evidence",
    },
    {
        "query_id": "holdout_magnitude_001",
        "query": "事件的 mag 没有值时，做平均震级统计能把它当成 0 吗？",
        "expected_source_path_contains": "magnitude_fields.md",
        "must_contain_any_groups": [
            ["magnitude", "mag", "震级"],
            ["null", "没有震级值", "空值"],
            ["0", "零级地震"],
        ],
        "expected_behavior": "retrieve missing magnitude handling evidence",
    },
    {
        "query_id": "holdout_magnitude_002",
        "query": "magSource 和 magType 分别记录震级的什么信息？",
        "expected_source_path_contains": "quality_and_uncertainty_fields.md",
        "must_contain_any_groups": [
            ["magSource"],
            ["magType"],
            ["来自哪里", "来源", "source"],
            ["震级类型", "类型", "type"],
        ],
        "expected_behavior": "retrieve magnitude source versus magnitude type evidence",
    },
    {
        "query_id": "holdout_geo_001",
        "query": "查某城市周围 200 公里的地震，应该用 bounding box 还是中心点半径？",
        "expected_source_path_contains": "geographic_query_methods.md",
        "must_contain_any_groups": [
            ["radius query", "中心点", "半径"],
            ["200", "公里", "km"],
            ["bounding box", "bbox", "矩形"],
        ],
        "expected_behavior": "retrieve radius query versus bounding box evidence",
    },
    {
        "query_id": "holdout_geo_002",
        "query": "区域横跨 180 度经线时，普通 longitude BETWEEN 为什么可能漏掉事件？",
        "expected_source_path_contains": "geographic_query_methods.md",
        "must_contain_any_groups": [
            ["国际日期变更线", "International Date Line", "180"],
            ["longitude", "经度"],
            ["拆分", "两个 bounding box", "特殊处理"],
        ],
        "expected_behavior": "retrieve international date line filtering evidence",
    },
    {
        "query_id": "holdout_geo_003",
        "query": "place 文本里没有国家名时，还能直接用 LIKE 查询该国家全部地震吗？",
        "expected_source_path_contains": "geographic_query_methods.md",
        "must_contain_any_groups": [
            ["place"],
            ["不是精确空间边界", "人类可读", "not a geographic filter"],
            ["latitude", "longitude", "经纬度", "bounding box"],
        ],
        "expected_behavior": "retrieve place field limitation and structured geographic filtering evidence",
    },
    {
        "query_id": "holdout_filter_001",
        "query": "过去两周、M5 以上且深度不超过 70 公里的事件，应该怎样组合过滤？",
        "expected_source_path_contains": "time_magnitude_depth_filters.md",
        "must_contain_any_groups": [
            ["start_time", "end_time", "时间范围", "过去两周"],
            ["min_magnitude", "M5", "震级"],
            ["max_depth_km", "70", "深度"],
        ],
        "expected_behavior": "retrieve combined time magnitude and depth filtering evidence",
    },
    {
        "query_id": "holdout_quality_001",
        "query": "一个事件的 gap 很小，能否据此断定震中位置绝对准确？",
        "expected_source_path_contains": "quality_and_uncertainty_fields.md",
        "must_contain_any_groups": [
            ["gap"],
            ["不能单独", "不等于", "不能简单认为"],
            ["台站", "station geometry", "位置不确定性"],
        ],
        "expected_behavior": "retrieve gap limitation and combined quality evidence",
    },
    {
        "query_id": "holdout_quality_002",
        "query": "depth=20 km、depthError=8 km 时，和另一个 22 km 的事件比较要注意什么？",
        "expected_source_path_contains": "quality_and_uncertainty_fields.md",
        "must_contain_any_groups": [
            ["depthError"],
            ["20", "22", "深度"],
            ["不确定性", "uncertainty", "比较"],
        ],
        "expected_behavior": "retrieve depth uncertainty comparison evidence",
    },
    {
        "query_id": "holdout_impact_001",
        "query": "felt 数量很高，是否等于实际受灾人数也很多？",
        "expected_source_path_contains": "impact_and_review_fields.md",
        "must_contain_any_groups": [
            ["felt"],
            ["公众", "震感报告", "public"],
            ["受灾人数", "总人数", "人员伤亡"],
        ],
        "expected_behavior": "retrieve felt field limitation evidence",
    },
    {
        "query_id": "holdout_impact_002",
        "query": "cdi 和 mmi 都是烈度信息，它们的数据来源有什么不同？",
        "expected_source_path_contains": "impact_and_review_fields.md",
        "must_contain_any_groups": [
            ["cdi"],
            ["mmi"],
            ["公众报告", "公众震感", "public"],
            ["仪器", "模型估计", "instrumental"],
        ],
        "expected_behavior": "retrieve CDI versus MMI evidence",
    },
    {
        "query_id": "holdout_impact_003",
        "query": "sig 分数高，能否解释为该地区未来发生大地震的概率更高？",
        "expected_source_path_contains": "impact_and_review_fields.md",
        "must_contain_any_groups": [
            ["sig", "显著性分数"],
            ["未来大地震概率", "风险概率", "probability"],
            ["不应该", "不是", "不能"],
        ],
        "expected_behavior": "retrieve significance score limitation evidence",
    },
    {
        "query_id": "holdout_updates_001",
        "query": "同一个 event_id 昨天是 M5.8、今天变成 M5.9，应当算两次地震吗？",
        "expected_source_path_contains": "event_updates_and_revisions.md",
        "must_contain_any_groups": [
            ["event_id"],
            ["同一个事件", "追踪"],
            ["magnitude", "M5.8", "M5.9", "震级"],
            ["更新", "调整", "revision"],
        ],
        "expected_behavior": "retrieve event identity across magnitude revisions evidence",
    },
    {
        "query_id": "holdout_updates_002",
        "query": "为什么实时目录中完全相同的查询隔几天再跑，结果可能不一样？",
        "expected_source_path_contains": "event_updates_and_revisions.md",
        "must_contain_any_groups": [
            ["相同查询", "查询结果"],
            ["新事件", "旧事件被修订", "震级更新", "数据更新"],
            ["实时目录", "live official catalog", "后续可能更新"],
        ],
        "expected_behavior": "retrieve live catalog revision and reproducibility evidence",
    },
    {
        "query_id": "holdout_sample_001",
        "query": "本地库没有查到某次地震，可以直接回答现实中从未发生吗？",
        "expected_source_path_contains": "sample_database_limitations.md",
        "must_contain_any_groups": [
            ["本地样例数据库", "当前数据集", "local sample"],
            ["未检索到", "没有匹配结果"],
            ["现实世界", "事件不存在", "未发生"],
        ],
        "expected_behavior": "retrieve empty local result limitation evidence",
    },
    {
        "query_id": "holdout_sample_002",
        "query": "用当前样例库算出的平均震级，可以当成全球长期平均水平吗？",
        "expected_source_path_contains": "sample_database_limitations.md",
        "must_contain_any_groups": [
            ["平均震级", "average magnitude"],
            ["当前数据快照", "本地样例库"],
            ["全球长期统计", "完整全球地震目录"],
        ],
        "expected_behavior": "retrieve local snapshot statistics limitation evidence",
    },
    {
        "query_id": "holdout_identity_001",
        "query": "两条记录的 place、时间和震级很接近，就能认定是同一个事件吗？",
        "expected_source_path_contains": "event_identity_and_time_fields.md",
        "must_contain_any_groups": [
            ["place"],
            ["time", "时间"],
            ["magnitude", "震级"],
            ["event_id"],
        ],
        "expected_behavior": "retrieve event identity versus similar metadata evidence",
    },
    {
        "query_id": "holdout_identity_002",
        "query": "按地震发生日期筛选时，应该用 time 还是 updated？",
        "expected_source_path_contains": "event_identity_and_time_fields.md",
        "must_contain_any_groups": [
            ["time"],
            ["updated"],
            ["发生时间", "什么时候发生"],
            ["更新时间", "最近什么时候被修改"],
        ],
        "expected_behavior": "retrieve event time versus record update time evidence",
    },
    {
        "query_id": "holdout_sequence_001",
        "query": "刚发生一次小地震，为什么不能马上把它叫作 foreshock？",
        "expected_source_path_contains": "aftershock_foreshock_mainshock.md",
        "must_contain_any_groups": [
            ["foreshock", "前震"],
            ["小地震", "small earthquake"],
            ["后续", "回溯性", "更大的相关事件"],
        ],
        "expected_behavior": "retrieve retrospective foreshock classification evidence",
    },
    {
        "query_id": "holdout_sequence_002",
        "query": "一个最初被当作主震的事件，后来为什么可能改称前震？",
        "expected_source_path_contains": "aftershock_foreshock_mainshock.md",
        "must_contain_any_groups": [
            ["mainshock", "主震"],
            ["foreshock", "前震"],
            ["后来", "后续事件", "更大"],
            ["重新", "回溯性", "classification can change"],
        ],
        "expected_behavior": "retrieve mainshock reclassification evidence",
    },
    {
        "query_id": "holdout_swarm_001",
        "query": "一段时间里同一区域地震很多，怎样区分地震群和主震—余震序列？",
        "expected_source_path_contains": "earthquake_swarm.md",
        "must_contain_any_groups": [
            ["earthquake swarm", "地震群"],
            ["mainshock", "主震"],
            ["aftershock", "余震"],
            ["没有明显", "单一主震", "占主导"],
        ],
        "expected_behavior": "retrieve earthquake swarm versus mainshock-aftershock sequence evidence",
    },
    {
        "query_id": "holdout_swarm_002",
        "query": "监测到一组空间集中的小震，能否直接宣布马上会发生更大地震？",
        "expected_source_path_contains": "earthquake_swarm.md",
        "must_contain_any_groups": [
            ["空间", "spatial concentration", "地震群"],
            ["未来", "马上", "更大地震"],
            ["time", "location", "magnitude", "时间", "地点", "震级"],
        ],
        "expected_behavior": "retrieve swarm interpretation and prediction boundary evidence",
    },
    {
        "query_id": "holdout_warning_001",
        "query": "地震预警发出时，地震是还没发生还是已经开始了？",
        "expected_source_path_contains": "early_warning_vs_prediction.md",
        "must_contain_any_groups": [
            ["地震预警", "earthquake early warning", "EEW"],
            ["已经开始", "已经发生"],
            ["快速检测", "监测系统"],
        ],
        "expected_behavior": "retrieve earthquake early warning timing evidence",
    },
    {
        "query_id": "holdout_hazard_001",
        "query": "某地区未来十年有较高地震概率，是否等于能确定具体哪一天发生？",
        "expected_source_path_contains": "early_warning_vs_prediction.md",
        "must_contain_any_groups": [
            ["概率", "probability", "forecast"],
            ["时间范围", "未来十年", "time window"],
            ["具体哪一天", "确定某一天", "prediction"],
        ],
        "expected_behavior": "retrieve probabilistic forecast versus deterministic prediction evidence",
    },
    {
        "query_id": "holdout_safety_001",
        "query": "地震云和动物异常同时出现，能否提高下周发生大震的预测可信度？",
        "expected_source_path_contains": "earthquake_safety_boundaries.md",
        "must_contain_any_groups": [
            ["地震云"],
            ["动物异常"],
            ["不可靠", "伪科学", "可靠地震预测依据"],
            ["未来", "下周", "大震"],
        ],
        "expected_behavior": "retrieve pseudoscience and future prediction safety boundary evidence",
    },
    {
        "query_id": "holdout_safety_002",
        "query": "最近小震变多了，SeismoSearch 能否给出下一次 M7 的具体日期和地点？",
        "expected_source_path_contains": "earthquake_safety_boundaries.md",
        "must_contain_any_groups": [
            ["最近小震", "历史活动", "历史事件"],
            ["M7", "震级"],
            ["具体日期", "时间"],
            ["地点"],
            ["不能预测", "不支持", "未来具体地震预测"],
        ],
        "expected_behavior": "retrieve historical activity and specific future prediction safety boundary evidence",
    },
]


TEST_CONTENT = """\"\"\"Validate versioned retrieval development and holdout datasets.\"\"\"

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEV_PATH = PROJECT_ROOT / "eval" / "retrieval_eval_60_corpus_v2.jsonl"
HOLDOUT_PATH = PROJECT_ROOT / "eval" / "retrieval_holdout_26_v1.jsonl"
MANIFEST_PATH = PROJECT_ROOT / "eval" / "retrieval_eval_manifest_v2.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()

            if not stripped:
                continue

            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as error:
                raise AssertionError(
                    f"{path} line {line_number} is invalid JSON: {error}"
                ) from error

    return records


def normalize_query(text: str) -> str:
    return " ".join(text.lower().split())


def validate_record(record: dict[str, Any]) -> None:
    required_string_fields = [
        "query_id",
        "query",
        "expected_source_path_contains",
        "expected_behavior",
    ]

    for field in required_string_fields:
        value = record.get(field)
        assert isinstance(value, str)
        assert value.strip()

    groups = record.get("must_contain_any_groups")
    assert isinstance(groups, list)
    assert groups

    for group in groups:
        assert isinstance(group, list)
        assert group
        assert all(
            isinstance(term, str) and term.strip()
            for term in group
        )


def test_retrieval_eval_files_exist() -> None:
    assert DEV_PATH.exists()
    assert HOLDOUT_PATH.exists()
    assert MANIFEST_PATH.exists()


def test_retrieval_eval_record_schema() -> None:
    for record in load_jsonl(DEV_PATH) + load_jsonl(HOLDOUT_PATH):
        validate_record(record)


def test_query_ids_are_unique_across_dev_and_holdout() -> None:
    records = load_jsonl(DEV_PATH) + load_jsonl(HOLDOUT_PATH)
    query_ids = [record["query_id"] for record in records]

    assert len(query_ids) == len(set(query_ids))


def test_queries_are_unique_across_dev_and_holdout() -> None:
    development_queries = {
        normalize_query(record["query"])
        for record in load_jsonl(DEV_PATH)
    }
    holdout_queries = [
        normalize_query(record["query"])
        for record in load_jsonl(HOLDOUT_PATH)
    ]

    assert len(holdout_queries) == len(set(holdout_queries))
    assert development_queries.isdisjoint(holdout_queries)


def test_holdout_size_and_prefix_are_frozen() -> None:
    holdout_records = load_jsonl(HOLDOUT_PATH)

    assert len(holdout_records) == 26
    assert all(
        record["query_id"].startswith("holdout_")
        for record in holdout_records
    )


def test_manifest_references_frozen_datasets() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["development_set"] == (
        "eval/retrieval_eval_60_corpus_v2.jsonl"
    )
    assert manifest["holdout_set"] == (
        "eval/retrieval_holdout_26_v1.jsonl"
    )
    assert manifest["primary_metric"] == "requirement_hit_at_k"
    assert manifest["top_k"] == 5
    assert re.fullmatch(
        r"[0-9a-f]{40}",
        manifest["frozen_base_commit_sha"],
    )
"""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()

            if not stripped:
                continue

            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    f"{path} line {line_number} is invalid JSON: {error}"
                ) from error

    return records


def normalize_query(text: str) -> str:
    return " ".join(text.lower().split())


def current_git_sha() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    commit_sha = completed.stdout.strip()

    if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        raise RuntimeError(f"Unexpected git commit SHA: {commit_sha}")

    return commit_sha


def validate_holdout_against_dev() -> None:
    if not DEV_PATH.exists():
        raise FileNotFoundError(f"Missing development set: {DEV_PATH}")

    development_records = load_jsonl(DEV_PATH)
    development_ids = {
        record["query_id"]
        for record in development_records
    }
    development_queries = {
        normalize_query(record["query"])
        for record in development_records
    }

    holdout_ids = [
        record["query_id"]
        for record in HOLDOUT_RECORDS
    ]
    holdout_queries = [
        normalize_query(record["query"])
        for record in HOLDOUT_RECORDS
    ]

    duplicate_ids = sorted(
        development_ids.intersection(holdout_ids)
    )
    duplicate_queries = sorted(
        development_queries.intersection(holdout_queries)
    )

    if duplicate_ids:
        raise RuntimeError(
            f"Holdout query IDs collide with development set: {duplicate_ids}"
        )

    if duplicate_queries:
        raise RuntimeError(
            f"Holdout queries exactly duplicate development queries: {duplicate_queries}"
        )

    if len(holdout_ids) != len(set(holdout_ids)):
        raise RuntimeError("Holdout contains duplicate query IDs.")

    if len(holdout_queries) != len(set(holdout_queries)):
        raise RuntimeError("Holdout contains duplicate query text.")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    content = "\n".join(
        json.dumps(record, ensure_ascii=False)
        for record in records
    ) + "\n"

    path.write_text(
        content,
        encoding="utf-8",
        newline="\n",
    )


def write_manifest(frozen_base_commit_sha: str) -> None:
    manifest = {
        "version": "retrieval_eval_v2",
        "frozen_at": date.today().isoformat(),
        "frozen_base_commit_sha": frozen_base_commit_sha,
        "development_set": "eval/retrieval_eval_60_corpus_v2.jsonl",
        "holdout_set": "eval/retrieval_holdout_26_v1.jsonl",
        "primary_metric": "requirement_hit_at_k",
        "secondary_metrics": [
            "source_hit_at_k",
            "exact_term_hit_at_k",
            "any_group_hit_at_k",
            "mrr",
            "failed_records",
        ],
        "top_k": 5,
        "holdout_policy": [
            "Do not modify holdout records after the first retrieval run.",
            "Do not tune corpus, planner, synonyms, retrievers, or reranker on holdout failures.",
            "Use the development set for debugging and tuning.",
            "Create a new versioned holdout set if the evaluation contract must change.",
        ],
    }

    MANIFEST_PATH.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def assert_outputs_do_not_exist() -> None:
    existing = [
        path
        for path in [HOLDOUT_PATH, MANIFEST_PATH, TEST_PATH]
        if path.exists()
    ]

    if existing:
        display = ", ".join(
            str(path.relative_to(PROJECT_ROOT))
            for path in existing
        )
        raise FileExistsError(
            f"Refusing to overwrite frozen artifacts: {display}"
        )


def main() -> None:
    assert_outputs_do_not_exist()
    validate_holdout_against_dev()

    frozen_sha = current_git_sha()

    write_jsonl(
        HOLDOUT_PATH,
        HOLDOUT_RECORDS,
    )
    write_manifest(frozen_sha)

    TEST_PATH.write_text(
        TEST_CONTENT,
        encoding="utf-8",
        newline="\n",
    )

    print(
        f"[PASS] holdout: "
        f"{HOLDOUT_PATH.relative_to(PROJECT_ROOT)} "
        f"({len(HOLDOUT_RECORDS)} records)"
    )
    print(
        f"[PASS] manifest: "
        f"{MANIFEST_PATH.relative_to(PROJECT_ROOT)}"
    )
    print(
        f"[PASS] tests: "
        f"{TEST_PATH.relative_to(PROJECT_ROOT)}"
    )
    print(f"[PASS] frozen base commit: {frozen_sha}")
    print(
        "[NEXT] Run tests and commit these files "
        "before the first holdout evaluation."
    )


if __name__ == "__main__":
    main()
