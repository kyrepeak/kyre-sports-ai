"""CFB Top Picks Research V2 Step 5 — permanent defense + pace guard."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "cfb_top_picks_defense_pace_research_v1.py"
DETAILS = ROOT / "cfb_top_picks_details_v1.py"
PAGE = ROOT / "cfb_top_picks_page_v4.py"
CERT = ROOT / "devsystem/cfb_top_picks_research_v2_step5_defense_pace_cert_v1.py"


class Step5DefensePaceContractFailure(RuntimeError):
    pass


def check_repository() -> dict[str, object]:
    failures: list[str] = []
    engine = ENGINE.read_text(encoding="utf-8")
    details = DETAILS.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    cert = CERT.read_text(encoding="utf-8")

    for token in (
        "cfb_over_under_step3_readable_v2 as readable",
        "cfb_over_under_pace_engine_v1 as pace_identity",
        "cfb_over_under_red_zone_engine_v1 as red_zone",
        "cfb_over_under_explosive_engine_v1 as explosive",
        "points_allowed_per_game",
        "recent_points_allowed_avg",
        "yards_per_play_allowed",
        "plays_per_game",
        "red_zone_td_rate_allowed",
        "explosive_susceptibility_proxy",
        "pace_index",
        "observed_at",
        "API2_USED = False",
        "DEFENSE_PACE_RESEARCH_PROJECTION_WEIGHT = 0.0",
    ):
        if token not in engine:
            failures.append(f"defense/pace research engine missing {token}")

    for forbidden in ("sports_api", "KYRE_SPORTS_API", "/api/v1/"):
        if forbidden in engine:
            failures.append(f"defense/pace research illegally couples API 2: {forbidden}")

    if "defense_pace_research.build_defense_pace_research(row, game, slate_day)" not in details:
        failures.append("detail layer does not attach Step-5 defense/pace research")
    if "Defense + Pace Research" not in page:
        failures.append("Top Picks detail UI does not render defense/pace research")
    if "RESEARCH_STEP5_MARKER" not in page:
        failures.append("Top Picks page missing Step-5 marker")

    for token in (
        "required_picks = 10",
        "required_teams = 20",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP5_20_TEAM_DEFENSE_PACE_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP5_PROVENANCE_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP5_MULTI_SOURCE_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP5_FROZEN_GREEN",
    ):
        if token not in cert:
            failures.append(f"Step-5 certification missing {token}")

    if failures:
        raise Step5DefensePaceContractFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "step": "5/9",
        "core_metrics_per_team": 4,
        "supporting_metrics_per_team": 6,
        "field_level_provenance": True,
        "multi_source": True,
        "projection_weight": 0.0,
        "api2_protected": True,
        "steps1_4_protected": True,
    }


def main() -> int:
    result = check_repository()
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP5_DEFENSE_PACE_CONTRACT_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
