"""
Regression tests for magnitude-update and revision query rewrites.

These tests lock the failure family exposed by End-to-End Holdout V2 without
rerunning or modifying the frozen evaluation result.
"""

from __future__ import annotations

from seismosearch.planner import plan_query


def test_magnitude_update_query_gets_revision_rewrites() -> None:
    plan = plan_query(
        "为什么同一个事件的 magnitude 之后还可能改动？"
    )

    assert plan["query_type"] == "concept"
    assert plan["event_search_params"] is None
    assert plan["event_statistics_params"] is None

    rewrites = plan["doc_retrieval_queries"]

    assert any(
        "地震事件更新" in query
        and "震级变化" in query
        and "人工复核" in query
        for query in rewrites
    )
    assert any(
        "Earthquake Event Updates and Revisions" in query
        and "magnitude revision" in query
        for query in rewrites
    )
    assert any(
        "reviewed" in query.lower()
        and "magnitude" in query.lower()
        and "change" in query.lower()
        for query in rewrites
    )

    assert "地震 震级 magnitude 定义" not in rewrites
    assert "earthquake magnitude definition" not in rewrites


def test_chinese_magnitude_revision_paraphrase_is_supported() -> None:
    plan = plan_query(
        "同一个地震事件的震级后来为什么会调整？"
    )

    rewrites = plan["doc_retrieval_queries"]

    assert plan["query_type"] == "concept"
    assert any(
        "新增台站数据" in query
        and "波形重新处理" in query
        and "数据源合并" in query
        for query in rewrites
    )


def test_reviewed_magnitude_update_query_combines_rewrites() -> None:
    plan = plan_query(
        "status=reviewed 后 magnitude 还会更新吗？"
    )

    rewrites = plan["doc_retrieval_queries"]

    assert plan["query_type"] == "concept"
    assert any(
        "reviewed automatic" in query
        for query in rewrites
    )
    assert any(
        "Earthquake Event Updates and Revisions" in query
        for query in rewrites
    )


def test_mixed_magnitude_update_query_keeps_event_tools() -> None:
    plan = plan_query(
        "列出 M6.5 以上事件，并解释震级为什么还可能更新。"
    )

    rewrites = plan["doc_retrieval_queries"]

    assert plan["query_type"] == "mixed"
    assert (
        plan["event_search_params"]["min_magnitude"]
        == 6.5
    )
    assert any(
        "震级变化" in query
        and "事件更新" in query
        for query in rewrites
    )


def test_plain_magnitude_definition_keeps_definition_rewrites() -> None:
    plan = plan_query("地震 magnitude 是什么意思？")

    rewrites = plan["doc_retrieval_queries"]

    assert plan["query_type"] == "concept"
    assert "地震 震级 magnitude 定义" in rewrites
    assert "earthquake magnitude definition" in rewrites
    assert not any(
        "Earthquake Event Updates and Revisions" in query
        for query in rewrites
    )


def test_same_magnitude_impact_query_does_not_trigger_revision() -> None:
    plan = plan_query(
        "为什么相同震级的地震影响可能不同？"
    )

    rewrites = plan["doc_retrieval_queries"]

    assert not any(
        "Earthquake Event Updates and Revisions" in query
        for query in rewrites
    )
