from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from devsystem.semantic_ui_verifier_contract_v1 import (
    SemanticUIVerificationFailure,
    certify_semantic_contract,
    contract_self_test,
    load_cases,
    selector_fragility,
    validate_cases,
    validate_locator_strategy,
)

CASES = Path("devsystem/semantic_ui_verifier_cases_v1.json")


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["dom_reshuffle_semantics_green"] is True
    assert result["framework_internal_selector_blocked"] is True


def test_repository_cases_validate_real_historical_failure_shapes():
    payload = load_cases(CASES)
    assert len(payload["historical_basis"]) >= 2
    assert {item["failure_run"] for item in payload["historical_basis"]} >= {
        35675715862,
        35676052842,
    }


def test_dom_order_does_not_matter_when_semantics_match():
    contract = {
        "contract_id": "order-independent",
        "requirements": [
            {"capability_id": "date", "kind": "interactive", "role": "combobox", "accessible_name": "Slate Date"},
            {"capability_id": "matchup", "kind": "interactive", "role": "combobox", "accessible_name": "Matchup"},
        ],
    }
    observations = [
        {"role": "combobox", "accessible_name": "Matchup", "visible": True, "interactive": True, "wrapper_width": 200, "wrapper_height": 60, "interactive_width": 120, "interactive_height": 24},
        {"role": "combobox", "accessible_name": "Slate Date", "visible": True, "interactive": True, "wrapper_width": 200, "wrapper_height": 60, "interactive_width": 120, "interactive_height": 24},
    ]
    assert certify_semantic_contract(contract, observations)["status"] == "GREEN"


def test_real_25px_interactive_child_is_valid_when_wrapper_contract_is_green():
    result = certify_semantic_contract(
        {
            "contract_id": "historical-height-repair",
            "requirements": [
                {"capability_id": "date", "kind": "interactive", "role": "combobox", "accessible_name": "Slate Date", "min_wrapper_height": 40}
            ],
        },
        [
            {
                "role": "combobox",
                "accessible_name": "Slate Date",
                "visible": True,
                "interactive": True,
                "wrapper_width": 195.171875,
                "wrapper_height": 68,
                "interactive_width": 123,
                "interactive_height": 25.59375,
            }
        ],
    )
    assert result["status"] == "GREEN"


@pytest.mark.parametrize(
    "selector",
    [
        "[data-baseweb='input']",
        ".stDateInput > div > div:nth-child(2)",
        "div.css-18ni7ap.e8zbici2 > div:nth-of-type(3)",
    ],
)
def test_brittle_framework_selectors_are_rejected(selector):
    assert selector_fragility(selector)
    with pytest.raises(SemanticUIVerificationFailure):
        validate_locator_strategy(
            {"kind": "stable_wrapper", "semantic_key": "control", "selector": selector}
        )


def test_hidden_marker_cannot_substitute_for_interactive_control():
    result = certify_semantic_contract(
        {
            "contract_id": "marker-negative",
            "requirements": [
                {"capability_id": "sport", "kind": "interactive", "role": "combobox", "accessible_name": "Sport"}
            ],
        },
        [{"kind": "diagnostic_marker", "text": "SPORT_READY", "visible": False, "hidden": True}],
    )
    assert result["status"] == "BLOCKED"
    assert result["results"][0]["issues"] == ["SEMANTIC_CAPABILITY_MISSING"]


def test_duplicate_semantic_matches_fail_closed():
    observation = {"role": "button", "accessible_name": "Next", "visible": True, "interactive": True, "wrapper_width": 100, "wrapper_height": 44, "interactive_width": 100, "interactive_height": 44}
    result = certify_semantic_contract(
        {
            "contract_id": "ambiguous",
            "requirements": [
                {"capability_id": "next", "kind": "interactive", "role": "button", "accessible_name": "Next"}
            ],
        },
        [observation, deepcopy(observation)],
    )
    assert result["status"] == "BLOCKED"
    assert "AMBIGUOUS_SEMANTIC_MATCH" in result["results"][0]["issues"]


def test_cases_tamper_fails_closed():
    payload = load_cases(CASES)
    tampered = deepcopy(payload)
    tampered["historical_basis"][0]["lesson"] = "tampered"
    with pytest.raises(SemanticUIVerificationFailure):
        validate_cases(tampered)
