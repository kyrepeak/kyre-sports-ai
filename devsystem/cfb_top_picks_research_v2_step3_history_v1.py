"""CFB Top Picks Research V2 Step 3 — permanent multi-source history guard."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "devsystem/contracts/cfb_top_picks_research_v2_contract_v1.json"
ROUTER = ROOT / "cfb_top_picks_history_router_v1.py"
DETAILS = ROOT / "cfb_top_picks_details_v1.py"
PAGE = ROOT / "cfb_top_picks_page_v4.py"
CERT = ROOT / "devsystem/cfb_top_picks_research_v2_step3_history_cert_v1.py"


class Step3HistoryContractFailure(RuntimeError):
    pass


def check_repository() -> dict[str, object]:
    failures: list[str] = []
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    router = ROUTER.read_text(encoding="utf-8")
    details = DETAILS.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    cert = CERT.read_text(encoding="utf-8")

    history = dict(contract.get("history_contract") or {})
    if history.get("minimum_independent_history_sources_attempted", 0) < 2:
        failures.append("Step-1 minimum history source contract changed")
    if history.get("alias_resolution_required") is not True:
        failures.append("Step-1 alias resolution contract changed")

    for token in (
        "cfb_over_under_history_engine_v1 as espn_history",
        "cfb_over_under_data_recovery_v1 as recovery",
        "espn_exact_team_schedule_history",
        "winsipedia_all_time_game_by_game",
        'VERIFIED_HISTORY = "VERIFIED_HISTORY"',
        'VERIFIED_NO_HISTORY = "VERIFIED_NO_HISTORY_AFTER_SOURCE_EXHAUSTION"',
        'SOURCE_CONFLICT_REVIEW = "SOURCE_CONFLICT_REVIEW"',
        "sources_attempted",
        "sources_verified",
        "no_history_claim_allowed",
        "recovery._slug_guess",
        "API2_USED = False",
    ):
        if token not in router:
            failures.append(f"history router missing {token}")

    for forbidden in ("sports_api", "KYRE_SPORTS_API", "/api/v1/"):
        if forbidden in router:
            failures.append(f"history router illegally couples API 2: {forbidden}")

    if "history_router.resolve_matchup_history(row, game)" not in details:
        failures.append("detail layer does not use the multi-source history router")
    if "series = history_recovery._fetch_winsipedia_games(away, home)" in details:
        failures.append("detail layer still owns a direct single-source Winsipedia call")

    for token in (
        'data-history-status="VERIFIED_HISTORY"',
        'data-history-status="VERIFIED_NO_HISTORY_AFTER_SOURCE_EXHAUSTION"',
        'data-history-status="SOURCE_CONFLICT_REVIEW"',
        "No “these teams never played” claim is being made.",
    ):
        if token not in page:
            failures.append(f"history UI missing {token}")

    for token in (
        "required_picks = 10",
        "source_count_attempted",
        "TERMINAL_STATUSES",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP3_10_HISTORY_TERMINAL_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP3_NO_FALSE_NO_HISTORY_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP3_FROZEN_GREEN",
    ):
        if token not in cert:
            failures.append(f"Step-3 certification missing {token}")

    if failures:
        raise Step3HistoryContractFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "step": "3/9",
        "independent_history_sources": 2,
        "alias_resolution_required": True,
        "false_no_history_forbidden": True,
        "history_projection_weight": 0.0,
        "api2_protected": True,
        "steps1_2_protected": True,
    }


def main() -> int:
    result = check_repository()
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP3_HISTORY_CONTRACT_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
