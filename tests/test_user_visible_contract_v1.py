from __future__ import annotations

import pytest

from devsystem.user_visible_contract_v1 import (
    QUERY_POLICY_REQUIRED,
    QUERY_POLICY_TELEMETRY,
    RESPONSIVE_VIEWPORTS,
    UserVisibleContract,
    UserVisibleContractFailure,
    certify_responsive_suite,
    evaluate_user_visible_evidence,
)


def _contract(*, query_policy=QUERY_POLICY_TELEMETRY):
    return UserVisibleContract(
        name="demo",
        required_selectors=("[data-testid='root']",),
        required_text=("Visible Title",),
        required_markets=("Moneyline", "Over/Under", "Game Total", "Top Picks"),
        required_query=(("route", "Top Picks"),),
        query_policy=query_policy,
    )


def _evidence(*, query=None, body_scroll=390, doc_scroll=390, viewport=390):
    return {
        "selector_counts": {"[data-testid='root']": 1},
        "selector_visible": {"[data-testid='root']": True},
        "body_text": "Visible Title",
        "observed_markets": ["Moneyline", "Over/Under", "Game Total", "Top Picks"],
        "dimensions": {
            "bodyScroll": body_scroll,
            "docScroll": doc_scroll,
            "viewport": viewport,
        },
        "query": query or {},
        "url": "https://example.test/",
        "width": viewport,
        "height": 844,
    }


def test_required_responsive_contract_is_390_768_1440():
    assert RESPONSIVE_VIEWPORTS == ((390, 844), (768, 1024), (1440, 1000))


def test_query_is_non_blocking_telemetry_by_default():
    result = evaluate_user_visible_evidence(
        _contract(),
        _evidence(query={"route": ["wrong"]}),
    )
    assert result["status"] == "GREEN"
    assert result["query_policy"] == QUERY_POLICY_TELEMETRY
    assert result["query_matches"] == {"route": False}


def test_query_can_be_explicitly_promoted_to_required():
    with pytest.raises(UserVisibleContractFailure, match="required_query"):
        evaluate_user_visible_evidence(
            _contract(query_policy=QUERY_POLICY_REQUIRED),
            _evidence(query={"route": ["wrong"]}),
        )


@pytest.mark.parametrize(
    "mutation,token",
    [
        ({"selector_counts": {"[data-testid='root']": 0}}, "selector_count"),
        ({"selector_visible": {"[data-testid='root']": False}}, "selector_not_visible"),
        ({"body_text": "wrong"}, "missing_text"),
        ({"observed_markets": ["Moneyline", "Over/Under", "Game Total"]}, "market_count"),
        (
            {"dimensions": {"bodyScroll": 401, "docScroll": 390, "viewport": 390}},
            "horizontal_overflow",
        ),
    ],
)
def test_required_user_visible_behavior_fails_closed(mutation, token):
    evidence = _evidence()
    evidence.update(mutation)
    with pytest.raises(UserVisibleContractFailure, match=token):
        evaluate_user_visible_evidence(_contract(), evidence)


def test_responsive_suite_requires_all_three_widths():
    contract = _contract()
    results = [
        {"status": "GREEN", "width": 390, "height": 844},
        {"status": "GREEN", "width": 768, "height": 1024},
        {"status": "GREEN", "width": 1440, "height": 1000},
    ]
    result = certify_responsive_suite(contract, results)
    assert result["status"] == "GREEN"
    assert result["user_behavior_blocking"] is True
    assert result["telemetry_blocking"] is False

    with pytest.raises(UserVisibleContractFailure, match="missing viewports"):
        certify_responsive_suite(contract, results[:-1])
