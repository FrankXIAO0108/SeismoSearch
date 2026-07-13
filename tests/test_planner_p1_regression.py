from __future__ import annotations

from seismosearch.planner import plan_query


def test_catalog_directory_strongest_events_is_catalog() -> None:
    plan = plan_query(
        "本地地震目录中最强的几次事件是什么？"
    )

    assert plan["query_type"] == "catalog"
    assert plan["event_search_params"] is not None
    assert (
        plan["event_search_params"]["order_by"]
        == "magnitude"
    )
    assert plan["doc_retrieval_queries"] == []


def test_mmi_magnitude_relation_query_is_mixed() -> None:
    plan = plan_query(
        "列出样例库中 M6.5 以上事件，"
        "并说明 mmi 和 magnitude 不是一回事。"
    )

    assert plan["query_type"] == "mixed"
    assert (
        plan["event_search_params"]["min_magnitude"]
        == 6.5
    )

    rewrites = plan["doc_retrieval_queries"]

    assert any(
        "MMI" in query and "震级" in query
        for query in rewrites
    )
    assert any(
        "Modified Mercalli Intensity" in query
        for query in rewrites
    )


def test_deep_earthquake_surface_impact_rewrite() -> None:
    plan = plan_query(
        "查找 M7 以上事件，并解释为什么"
        "深源地震的地表影响不一定更强。"
    )

    assert plan["query_type"] == "mixed"

    rewrites = plan["doc_retrieval_queries"]

    assert any(
        "深源地震" in query
        and "地表震感" in query
        for query in rewrites
    )
    assert any(
        "surface shaking" in query
        and "geology" in query
        for query in rewrites
    )


def test_foreshock_mainshock_aftershock_rewrite() -> None:
    plan = plan_query(
        "本地库里有哪些 M6 以上事件？"
        "再解释前震、主震和余震如何命名。"
    )

    assert plan["query_type"] == "mixed"

    rewrites = plan["doc_retrieval_queries"]

    assert any(
        "前震 主震 余震" in query
        and "回顾性" in query
        for query in rewrites
    )
    assert any(
        "foreshock mainshock aftershock" in query
        for query in rewrites
    )


def test_existing_plain_catalog_query_stays_catalog() -> None:
    plan = plan_query(
        "2025 年 M6 以上最强地震有哪些？"
    )

    assert plan["query_type"] == "catalog"
    assert plan["doc_retrieval_queries"] == []


def test_safety_routing_is_not_regressed() -> None:
    plan = plan_query(
        "能不能给出东京下个月发生 M7 地震的"
        "具体概率和日期？"
    )

    assert plan["query_type"] == "safety"
    assert plan["event_search_params"] is None
    assert plan["event_statistics_params"] is None
    assert plan["doc_retrieval_queries"] == []
