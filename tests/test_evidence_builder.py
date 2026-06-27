"""
Tests for SeismoSearch Evidence Builder.

These tests verify that build_evidence_pack correctly organizes planner outputs
and tool outputs into controlled context for the future answer generator.

The key behaviors are:
- catalog questions should produce event evidence and computed evidence;
- safety questions should not trigger event search or event statistics;
- concept questions should not fabricate document evidence before doc retrieval exists;
- Evidence Builder should use planner.py automatically when manual params are not provided.
"""

from __future__ import annotations

from seismosearch.evidence_builder import build_evidence_pack


def test_catalog_evidence_pack_contains_event_and_computed_evidence() -> None:
    """Catalog queries should include event evidence and computed statistics."""
    pack = build_evidence_pack(
        user_query="最近 M6.5 以上地震有哪些？",
        query_type="catalog",
        event_search_params={
            "min_magnitude": 6.5,
            "order_by": "magnitude",
            "limit": 2,
        },
        event_statistics_params={
            "min_magnitude": 6.5,
        },
    )

    # The Evidence Pack itself should be classified as a catalog query.
    assert pack["query_type"] == "catalog"

    # Catalog queries should call:
    # 1. safety_check;
    # 2. event_search;
    # 3. event_statistics.
    tool_names = [tool_call["tool_name"] for tool_call in pack["tool_calls"]]

    assert tool_names == [
        "safety_check",
        "event_search",
        "event_statistics",
    ]

    # All tool calls should succeed.
    tool_statuses = [tool_call["status"] for tool_call in pack["tool_calls"]]
    assert tool_statuses == ["ok", "ok", "ok"]

    # event_search_params limit=2, so the pack should contain 2 event evidence items.
    event_evidence = pack["event_evidence"]
    assert len(event_evidence) == 2

    # Event evidence should have stable evidence IDs for later citation.
    assert event_evidence[0]["evidence_id"] == "event_001"
    assert event_evidence[1]["evidence_id"] == "event_002"

    # The events should satisfy the M6.5+ condition.
    assert event_evidence[0]["magnitude"] >= 6.5
    assert event_evidence[1]["magnitude"] >= 6.5

    # The events are requested in magnitude-descending order.
    assert event_evidence[0]["magnitude"] >= event_evidence[1]["magnitude"]

    # Catalog queries should include one computed evidence item.
    computed_evidence = pack["computed_evidence"]
    assert len(computed_evidence) == 1

    statistics = computed_evidence[0]["statistics"]
    magnitude_summary = statistics["magnitude_summary"]

    # Count and magnitude summary must use the same filter.
    assert statistics["event_count_matching_filters"] == magnitude_summary["event_count"]

    # The statistics should be based on M6.5+ events.
    assert magnitude_summary["min_magnitude"] >= 6.5

    # The current local sample should still be explicitly bounded.
    assert statistics["database_time_range"]["event_count"] == 1000

    # Catalog answers must cite event evidence and state sample limitations.
    constraints = pack["answer_constraints"]
    assert constraints["must_use_evidence_pack"] is True
    assert constraints["must_cite_event_evidence_when_using_event_facts"] is True
    assert constraints["should_state_sample_limitations"] is True
    assert constraints["should_not_claim_full_global_coverage"] is True
    assert constraints["response_mode"] == "catalog_answer"


def test_safety_evidence_pack_does_not_call_event_tools() -> None:
    """Safety queries should not call event search or event statistics."""
    pack = build_evidence_pack(
        user_query="明天东京会不会发生大地震？",
    )

    # The planner should classify this as a safety query.
    assert pack["query_type"] == "safety"

    # Safety queries should only call safety_check.
    tool_names = [tool_call["tool_name"] for tool_call in pack["tool_calls"]]
    assert tool_names == ["safety_check"]

    # No historical event evidence should be produced for future prediction.
    assert pack["event_evidence"] == []

    # No computed earthquake statistics should be produced either.
    assert pack["computed_evidence"] == []

    # The safety label should detect prediction inducement.
    safety_labels = pack["safety_evidence"]["safety_labels"]
    assert safety_labels["prediction_inducement"] is True
    assert "会不会发生" in safety_labels["matched_keywords"]

    # The future generator must not answer as if it can predict earthquakes.
    constraints = pack["answer_constraints"]
    assert constraints["must_use_evidence_pack"] is True
    assert constraints["must_not_predict_future_earthquakes"] is True
    assert constraints["should_offer_safe_alternatives"] is True
    assert constraints["must_cite_event_evidence_when_using_event_facts"] is False
    assert constraints["response_mode"] == "safe_refusal_with_alternatives"


def test_concept_evidence_pack_marks_doc_retrieval_as_not_implemented() -> None:
    """Concept queries should not fabricate document evidence before retrieval exists."""
    pack = build_evidence_pack(
        user_query="震级和烈度有什么区别？",
        query_type="concept",
    )

    # Concept queries are routed to concept mode.
    assert pack["query_type"] == "concept"

    # At this stage only safety_check is available for concept questions.
    tool_names = [tool_call["tool_name"] for tool_call in pack["tool_calls"]]
    assert tool_names == ["safety_check"]

    # Since doc_retriever.py is not implemented yet, doc evidence must be empty.
    assert pack["doc_evidence"] == []

    # The pack should explicitly warn that document retrieval is not ready.
    assert "doc_retrieval_not_implemented_yet" in pack["warnings"]

    # Planner-generated retrieval rewrites should be visible for future doc retrieval.
    assert "震级和烈度有什么区别？" in pack["doc_retrieval_queries"]
    assert "震级 烈度 区别" in pack["doc_retrieval_queries"]
    assert "seismic magnitude vs intensity" in pack["doc_retrieval_queries"]

    # Concept mode should not require event citations.
    constraints = pack["answer_constraints"]
    assert constraints["must_cite_event_evidence_when_using_event_facts"] is False
    assert constraints["must_cite_doc_evidence_when_using_document_facts"] is False
    assert constraints["response_mode"] == "concept_answer"


def test_evidence_builder_uses_planner_for_catalog_query() -> None:
    """Evidence Builder should use planner output when params are not manually provided."""
    pack = build_evidence_pack(
        user_query="最近 M6.5 以上地震有哪些？",
    )

    assert pack["query_type"] == "catalog"

    planner_output = pack["router_output"]["planner_output"]

    assert planner_output["query_type"] == "catalog"
    assert planner_output["event_search_params"]["min_magnitude"] == 6.5
    assert planner_output["event_search_params"]["order_by"] == "event_time_utc"
    assert planner_output["event_search_params"]["descending"] is True

    tool_names = [tool_call["tool_name"] for tool_call in pack["tool_calls"]]

    assert tool_names == [
        "safety_check",
        "event_search",
        "event_statistics",
    ]

    # Current local sample has 7 M6.5+ events.
    assert len(pack["event_evidence"]) == 7
    assert len(pack["computed_evidence"]) == 1

    statistics = pack["computed_evidence"][0]["statistics"]
    magnitude_summary = statistics["magnitude_summary"]

    assert statistics["event_count_matching_filters"] == 7
    assert magnitude_summary["event_count"] == 7
    assert magnitude_summary["min_magnitude"] >= 6.5

    constraints = pack["answer_constraints"]

    assert constraints["must_use_evidence_pack"] is True
    assert constraints["must_cite_event_evidence_when_using_event_facts"] is True
    assert constraints["should_state_sample_limitations"] is True
    assert constraints["response_mode"] == "catalog_answer"


def test_evidence_builder_uses_planner_for_safety_query() -> None:
    """Evidence Builder should not call event tools for planner-classified safety queries."""
    pack = build_evidence_pack(
        user_query="明天东京会不会发生大地震？",
    )

    assert pack["query_type"] == "safety"

    planner_output = pack["router_output"]["planner_output"]

    assert planner_output["query_type"] == "safety"
    assert planner_output["safety_intent"] == "future_specific_earthquake_prediction"
    assert planner_output["event_search_params"] is None
    assert planner_output["event_statistics_params"] is None

    tool_names = [tool_call["tool_name"] for tool_call in pack["tool_calls"]]

    assert tool_names == ["safety_check"]

    assert pack["event_evidence"] == []
    assert pack["computed_evidence"] == []

    constraints = pack["answer_constraints"]

    assert constraints["must_not_predict_future_earthquakes"] is True
    assert constraints["should_offer_safe_alternatives"] is True
    assert constraints["response_mode"] == "safe_refusal_with_alternatives"