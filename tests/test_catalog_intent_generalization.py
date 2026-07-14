"""
Regression tests for catalog-intent paraphrase generalization.

These cases verify that catalog routing depends on catalog scope, event object,
and selection intent rather than one exact phrase.
"""

from __future__ import annotations

import pytest

from seismosearch.planner import plan_query


@pytest.mark.parametrize(
    "query",
    (
        "本地样本中震级最大的事件有哪些？",
        "样本里震级最高的几条记录是什么？",
        "当前样例数据中最大的地震事件有哪些？",
        "帮我看看本地样本有哪些强震记录。",
        "找出震级最大的事件。",
    ),
)
def test_catalog_paraphrases_route_to_event_tools(
    query: str,
) -> None:
    plan = plan_query(query)

    assert plan["query_type"] == "catalog"
    assert plan["event_search_params"] is not None
    assert plan["event_statistics_params"] is not None
    assert plan["doc_retrieval_queries"] == []


@pytest.mark.parametrize(
    "query",
    (
        "本地样本中震级最大的事件有哪些？",
        "样本里震级最高的几条记录是什么？",
        "当前样例数据中最大的地震事件有哪些？",
        "找出震级最大的事件。",
    ),
)
def test_catalog_superlatives_order_by_magnitude(
    query: str,
) -> None:
    plan = plan_query(query)

    assert (
        plan["event_search_params"]["order_by"]
        == "magnitude"
    )
    assert (
        plan["event_search_params"]["descending"]
        is True
    )


@pytest.mark.parametrize(
    "query",
    (
        "震级最大的事件是什么意思？",
        "样本数据是什么意思？",
        "如何定义地震事件？",
    ),
)
def test_explanation_queries_do_not_become_catalog(
    query: str,
) -> None:
    plan = plan_query(query)

    assert plan["query_type"] == "concept"
    assert plan["event_search_params"] is None
    assert plan["event_statistics_params"] is None
    assert plan["doc_retrieval_queries"] != []
