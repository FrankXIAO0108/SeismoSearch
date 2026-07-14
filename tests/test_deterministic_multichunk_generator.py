"""
Tests for deterministic multi-chunk document evidence selection.
"""

from __future__ import annotations

from seismosearch.generator import generate_answer


def make_doc(
    evidence_id: str,
    rank: int,
    heading: str,
    text: str,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "evidence_type": "document_chunk",
        "rank": rank,
        "chunk_id": f"chunk_{rank}",
        "source_path": (
            "data/processed/docs/"
            "quality_and_uncertainty_fields.md"
        ),
        "source_type": "markdown",
        "doc_title": "USGS Quality and Uncertainty Fields",
        "heading": heading,
        "text": text,
    }


def make_pack(
    query: str,
    docs: list[dict],
    query_type: str = "concept",
) -> dict:
    return {
        "query_id": "deterministic_multichunk_test",
        "query_type": query_type,
        "user_query": query,
        "doc_evidence": docs,
        "event_evidence": [],
        "computed_evidence": [],
        "warnings": [],
        "answer_constraints": {
            "must_use_evidence_pack": True,
            "must_not_predict_future_earthquakes": False,
            "must_cite_doc_evidence_when_using_document_facts": True,
            "response_mode": "concept_answer",
        },
    }


def test_multi_field_query_selects_one_chunk_per_field() -> None:
    docs = [
        make_doc(
            "doc_001",
            1,
            "地震深度",
            "这是与问题无关的普通地震深度说明。",
        ),
        make_doc(
            "doc_002",
            2,
            "horizontalError",
            (
                "horizontalError 表示事件水平位置估计的"
                "不确定性。"
            ),
        ),
        make_doc(
            "doc_003",
            3,
            "Overview",
            "字段包括 horizontalError 和 depthError。",
        ),
        make_doc(
            "doc_004",
            4,
            "depthError",
            "depthError 表示震源深度估计的不确定性。",
        ),
    ]
    pack = make_pack(
        "horizontalError 和 depthError 有什么不同？",
        docs,
    )

    result = generate_answer(pack)
    answer = result["answer"]

    assert "事件水平位置估计的不确定性" in answer
    assert "震源深度估计的不确定性" in answer
    assert "普通地震深度说明" not in answer
    assert "[doc_002]" in answer
    assert "[doc_004]" in answer
    assert "[doc_001]" not in answer
    assert "[doc_003]" not in answer
    assert result["used_evidence_ids"] == [
        "doc_002",
        "doc_004",
    ]


def test_heading_match_beats_overview_body_match() -> None:
    docs = [
        make_doc(
            "doc_001",
            1,
            "Overview",
            "字段列表包含 magSource 和 magType。",
        ),
        make_doc(
            "doc_002",
            2,
            "magSource",
            "magSource 表示震级结果来自哪个数据源。",
        ),
        make_doc(
            "doc_003",
            3,
            "magType",
            "magType 表示使用的震级类型。",
        ),
    ]
    pack = make_pack(
        "magSource 和 magType 分别表示什么？",
        docs,
    )

    result = generate_answer(pack)

    assert result["used_evidence_ids"] == [
        "doc_002",
        "doc_003",
    ]
    assert "字段列表包含" not in result["answer"]


def test_single_field_query_does_not_cite_candidates() -> None:
    docs = [
        make_doc(
            "doc_001",
            1,
            "gap",
            "gap 表示台站方位角空缺。",
        ),
        make_doc(
            "doc_002",
            2,
            "nst",
            "nst 表示参与定位的台站数量。",
        ),
    ]
    pack = make_pack(
        "gap 变小就能证明定位一定更准吗？",
        docs,
    )

    result = generate_answer(pack)

    assert result["used_evidence_ids"] == ["doc_001"]
    assert "[doc_002]" not in result["answer"]
    assert "其他候选文档证据" not in result["answer"]


def test_chinese_only_query_preserves_top_one_fallback() -> None:
    docs = [
        make_doc(
            "doc_001",
            1,
            "震级和烈度的区别",
            "震级描述震源大小，烈度描述地点震动影响。",
        ),
        make_doc(
            "doc_002",
            2,
            "其他概念",
            "其他候选说明。",
        ),
    ]
    pack = make_pack(
        "震级和烈度有什么区别？",
        docs,
    )

    result = generate_answer(pack)

    assert result["used_evidence_ids"] == ["doc_001"]
    assert "震级描述震源大小" in result["answer"]
    assert "[doc_002]" not in result["answer"]
