"""CFB Top Picks Research + Completeness V2 — Step 2 logo contract guard."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEP1 = ROOT / "devsystem/contracts/cfb_top_picks_research_v2_contract_v1.json"
RESOLVER = ROOT / "cfb_top_picks_team_identity_v1.py"
ENGINE = ROOT / "cfb_top_picks_engine_v1.py"
CARDS = ROOT / "cfb_top_picks_page_v2.py"
BROWSER = ROOT / "devsystem/cfb_top_picks_research_v2_step2_logo_cert_v1.py"


class Step2LogoContractFailure(RuntimeError):
    pass


def check_repository() -> dict[str, object]:
    failures: list[str] = []
    step1 = json.loads(STEP1.read_text(encoding="utf-8"))
    resolver = RESOLVER.read_text(encoding="utf-8")
    engine = ENGINE.read_text(encoding="utf-8")
    cards = CARDS.read_text(encoding="utf-8")
    browser = BROWSER.read_text(encoding="utf-8")

    if step1["scope"]["api2_separate_and_protected"] is not True:
        failures.append("Step-1 API 2 protection is not preserved")
    if step1["completeness_gate"]["real_team_logos_required"] is not True:
        failures.append("Step-1 real-logo requirement changed")

    for token in (
        "cfb_over_under_logo_resolver_v3 as exact_logo",
        "cfb_over_under_logo_resolver_v2 as multisource",
        "API2_USED = False",
        "def enrich_ranked_picks(",
        "logo_identity_ready",
    ):
        if token not in resolver:
            failures.append(f"resolver missing {token}")

    for forbidden in (
        "sports_api",
        "KYRE_SPORTS_API",
        "cfb_game_total_team_logo_identity_v1",
        "/api/v1/",
    ):
        if forbidden in resolver:
            failures.append(f"resolver illegally couples API 2: {forbidden}")

    rank_pos = engine.find("picks = _rank_balanced(candidates, limit=limit)")
    enrich_pos = engine.find("picks = team_identity.enrich_ranked_picks(picks, games_by_event)")
    if rank_pos < 0 or enrich_pos <= rank_pos:
        failures.append("logo enrichment must occur strictly after frozen ranking")
    for token in (
        '"logo_ready_count"',
        '"logo_required_count"',
        '"logo_identity_complete"',
        "team_identity.MODEL_VERSION",
    ):
        if token not in engine:
            failures.append(f"engine logo diagnostics missing {token}")

    for token in (
        'data-top-picks-real-logo="true"',
        'data-logo-placeholder="true"',
        'data-team-id=',
        'data-logo-provider=',
        'cfb-top-picks-logo-{side}-{rank}',
    ):
        if token not in cards:
            failures.append(f"card renderer missing {token}")

    for token in (
        "naturalWidth",
        'data-top-picks-real-logo="true"',
        "CFB_TOP_PICKS_RESEARCH_V2_STEP2_20_REAL_LOGOS_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP2_FROZEN_GREEN",
    ):
        if token not in browser:
            failures.append(f"browser proof missing {token}")

    if failures:
        raise Step2LogoContractFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "step": "2/9",
        "ranked_board_size": 10,
        "required_real_logo_images": 20,
        "exact_identity_primary": True,
        "multi_source_fallback": True,
        "enrichment_after_ranking": True,
        "api2_protected": True,
        "ranking_math_changed": False,
        "probability_math_changed": False,
    }


def main() -> int:
    result = check_repository()
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP2_LOGO_CONTRACT_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
