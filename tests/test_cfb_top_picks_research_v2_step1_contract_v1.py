from __future__ import annotations

import json
from pathlib import Path

from devsystem.cfb_top_picks_research_v2_step1_contract_v1 import check_repository

CONTRACT = Path("devsystem/contracts/cfb_top_picks_research_v2_contract_v1.json")


def test_step1_audit_and_contract_are_green_and_frozen():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["audit_complete"] is True
    assert result["contract_frozen"] is True
    assert result["ranked_picks_covered"] == 10
    assert result["history_min_sources"] >= 2
    assert result["api2_protected"] is True
    assert result["product_fixes_applied"] is False


def test_every_market_has_reasoning_research_contract():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    markets = contract["market_reasoning_contract"]
    assert set(markets) == {"OVER/UNDER", "SPREAD", "MONEYLINE"}
    assert "combined_scoring_environment" in markets["OVER/UNDER"]["required"]
    assert "projected_margin_context" in markets["SPREAD"]["required"]
    assert "win_strength_context" in markets["MONEYLINE"]["required"]


def test_history_cannot_claim_none_from_one_failed_website():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    history = contract["history_contract"]
    assert history["no_history_claim_requires_source_exhaustion"] is True
    assert history["minimum_independent_history_sources_attempted"] >= 2
    assert history["alias_resolution_required"] is True
    assert "VERIFIED_NO_HISTORY_AFTER_SOURCE_EXHAUSTION" in history["allowed_terminal_statuses"]


def test_all_ten_require_real_logos_benefits_risks_and_provenance():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    gate = contract["completeness_gate"]
    assert gate["required_ranked_picks"] == 10
    assert gate["real_team_logos_required"] is True
    assert gate["benefits_must_have_verified_evidence"] is True
    assert gate["risks_must_have_verified_evidence"] is True
    assert gate["zero_placeholder_logo_text"] is True
    provenance = contract["provenance_contract"]
    assert provenance["unit_of_work"] == "DATA_FIELD"
    assert provenance["no_source_loyalty"] is True


def test_api2_is_explicitly_outside_scope():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    scope = contract["scope"]
    assert scope["api2_separate_and_protected"] is True
    assert scope["may_modify_api2"] is False
