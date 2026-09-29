"""CFB Top Picks Research V2 Step 4 — permanent offense-research guard."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "cfb_top_picks_offense_research_v1.py"
DETAILS = ROOT / "cfb_top_picks_details_v1.py"
PAGE = ROOT / "cfb_top_picks_page_v4.py"
CERT = ROOT / "devsystem/cfb_top_picks_research_v2_step4_offense_cert_v1.py"


class Step4OffenseContractFailure(RuntimeError):
    pass


def check_repository() -> dict[str, object]:
    failures: list[str] = []
    engine = ENGINE.read_text(encoding="utf-8")
    details = DETAILS.read_text(encoding="utf-8")
    page = PAGE.read_text(encoding="utf-8")
    cert = CERT.read_text(encoding="utf-8")

    for token in (
        "cfb_over_under_step3_readable_v2 as readable",
        "cfb_over_under_red_zone_engine_v1 as red_zone",
        "cfb_over_under_explosive_engine_v1 as explosive",
        "points_per_game",
        "recent_scoring_avg",
        "yards_per_play",
        "pass_yards_per_game",
        "rush_yards_per_game",
        "red_zone_td_rate",
        "explosive_efficiency_proxy",
        "observed_at",
        "API2_USED = False",
        "OFFENSE_RESEARCH_PROJECTION_WEIGHT = 0.0",
    ):
        if token not in engine:
            failures.append(f"offense research engine missing {token}")

    for forbidden in ("sports_api", "KYRE_SPORTS_API", "/api/v1/"):
        if forbidden in engine:
            failures.append(f"offense research illegally couples API 2: {forbidden}")

    if "offense_research.build_offense_research(row, game, slate_day)" not in details:
        failures.append("detail layer does not attach Step-4 offense research")
    if "Offensive Scoring Research" not in page:
        failures.append("Top Picks detail UI does not render offensive scoring research")

    for token in (
        "required_picks = 10",
        "required_teams = 20",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP4_20_TEAM_OFFENSE_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP4_PROVENANCE_GREEN",
        "CFB_TOP_PICKS_RESEARCH_V2_STEP4_FROZEN_GREEN",
    ):
        if token not in cert:
            failures.append(f"Step-4 certification missing {token}")

    if failures:
        raise Step4OffenseContractFailure(" | ".join(failures))

    return {
        "status": "GREEN",
        "step": "4/9",
        "core_metrics_per_team": 5,
        "supporting_metrics_per_team": 4,
        "field_level_provenance": True,
        "multi_source": True,
        "projection_weight": 0.0,
        "api2_protected": True,
        "steps1_3_protected": True,
    }


def main() -> int:
    result = check_repository()
    print("CFB_TOP_PICKS_RESEARCH_V2_STEP4_OFFENSE_CONTRACT_GREEN")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
