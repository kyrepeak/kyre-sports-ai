"""CFB Top Picks Research + Completeness V2 — Step 1 frozen data contract."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "devsystem/contracts/cfb_top_picks_research_v2_contract_v1.json"
DETAILS = ROOT / "cfb_top_picks_details_v1.py"
CARDS = ROOT / "cfb_top_picks_page_v2.py"
ENGINE = ROOT / "cfb_top_picks_engine_v1.py"


class TopPicksResearchContractFailure(RuntimeError):
    pass


def _load() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def check_repository() -> dict[str, object]:
    contract = _load()
    failures: list[str] = []

    scope = dict(contract.get("scope") or {})
    if scope.get("ranked_pick_count") != 10:
        failures.append("contract must cover exactly 10 ranked picks")
    if scope.get("api2_separate_and_protected") is not True:
        failures.append("API 2 separation is not frozen")
    if scope.get("may_modify_api2") is not False:
        failures.append("API 2 modification must remain prohibited")
    if scope.get("probability_why_preserved") is not True:
        failures.append("existing probability Why contract must be preserved")

    card_fields = set(contract.get("required_pick_card_fields") or [])
    for field in (
        "event_id","away_team","home_team","away_team_id","home_team_id",
        "away_logo_url","home_logo_url","market","pick","probability","reliability",
    ):
        if field not in card_fields:
            failures.append(f"required pick-card field missing: {field}")

    sections = set(contract.get("required_detail_sections") or [])
    for section in (
        "why_this_pick","reasoning_research","scoring_profile","pace_and_style",
        "defensive_matchup","recent_form","actual_matchup_history","benefits","risks",
        "sources_and_freshness",
    ):
        if section not in sections:
            failures.append(f"required detail section missing: {section}")

    market_contract = dict(contract.get("market_reasoning_contract") or {})
    for market in ("OVER/UNDER","SPREAD","MONEYLINE"):
        if not (dict(market_contract.get(market) or {}).get("required")):
            failures.append(f"market-aware reasoning missing for {market}")

    history = dict(contract.get("history_contract") or {})
    if history.get("minimum_independent_history_sources_attempted", 0) < 2:
        failures.append("history exhaustion requires at least two independent sources")
    if history.get("no_history_claim_requires_source_exhaustion") is not True:
        failures.append("no-history claims must require source exhaustion")
    if history.get("alias_resolution_required") is not True:
        failures.append("history alias resolution is not required")

    provenance = dict(contract.get("provenance_contract") or {})
    if provenance.get("unit_of_work") != "DATA_FIELD":
        failures.append("data router unit of work must be DATA_FIELD")
    for key in (
        "no_source_loyalty","every_material_fact_requires_source",
        "every_material_fact_requires_observed_at",
        "source_conflicts_must_be_recorded",
        "unsupported_values_must_not_be_invented",
        "fallback_to_other_sources_before_unavailable",
    ):
        if provenance.get(key) is not True:
            failures.append(f"provenance contract missing {key}")

    complete = dict(contract.get("completeness_gate") or {})
    if complete.get("required_ranked_picks") != 10:
        failures.append("10/10 completeness gate missing")
    for key in (
        "every_pick_must_pass_card_contract",
        "every_expanded_pick_must_pass_detail_contract",
        "real_team_logos_required",
        "benefits_must_have_verified_evidence",
        "risks_must_have_verified_evidence",
        "history_status_must_be_terminal",
        "zero_placeholder_logo_text",
        "zero_unexplained_missing_required_fields",
    ):
        if complete.get(key) is not True:
            failures.append(f"completeness gate missing {key}")

    # Baseline audit proof: these are historical findings frozen at Step 1.
    # Later steps are expected to close the gaps, so the permanent guard checks
    # the immutable audit record rather than requiring production to stay broken.
    baseline = dict(contract.get("current_baseline_audit") or {})
    expected_baseline = {
        "logo_state": "ABBREVIATION_PLACEHOLDERS",
        "history_state": "SINGLE_DIRECT_WINSIPEDIA_PATH",
        "benefits_state": "HISTORY_ONLY",
        "why_state": "MODEL_PROBABILITY_AND_RELIABILITY_ONLY",
        "reasoning_research_state": "MISSING",
        "risks_state": "MISSING",
        "ten_of_ten_completeness_gate": "MISSING",
    }
    for key, expected in expected_baseline.items():
        if baseline.get(key) != expected:
            failures.append(
                f"frozen Step-1 baseline record changed: {key}={baseline.get(key)!r}"
            )

    if failures:
        raise TopPicksResearchContractFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "step": "1/9",
        "audit_complete": True,
        "contract_frozen": True,
        "ranked_picks_covered": 10,
        "history_min_sources": int(history["minimum_independent_history_sources_attempted"]),
        "api2_protected": True,
        "product_fixes_applied": False,
        "known_gaps": [
            "real_team_logos",
            "multi_source_history",
            "football_reasoning_research",
            "non_history_benefits",
            "risks",
            "ten_of_ten_completeness_certification",
        ],
    }


def main() -> int:
    result = check_repository()
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP1_AUDIT_GREEN")
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP1_CONTRACT_FROZEN_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
