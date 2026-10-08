"""NFL RB/WR render repair Step 3 — exact data-binding certification.

Verification-only. This module does not mutate NFL runtime. It certifies that the
active Rushing/Receiving routes, identity gates, market joins, projections,
headshots, logos, and opponent ownership remain exact-ID and fail-closed after
the Step-2 presentation-transport repair.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VERSION = "NFL_RB_WR_RENDER_REPAIR_STEP3_DATA_BINDING_V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PRODUCT_RUNTIME_MUTATIONS = 0


def _source(root: Path, path: str) -> str:
    return (root / path).read_text(encoding="utf-8")


def _require(source: str, *markers: str, label: str) -> dict[str, Any]:
    missing = [marker for marker in markers if marker not in source]
    if missing:
        raise RuntimeError(f"{label}: missing binding markers: {missing}")
    return {"name": label, "status": "GREEN", "marker_count": len(markers)}


def _certify_static_bindings(root: Path) -> list[dict[str, Any]]:
    router = _source(root, "streamlit_memory_lazy_router_v187.py")
    rushing_owner = _source(root, "nfl_rushing_yards_hub_v16.py")
    rushing_cards = _source(root, "nfl_rushing_yards_hub_v4.py")
    receiving_owner = _source(root, "nfl_receiving_yards_hub_v17.py")
    receiving_cards = _source(root, "nfl_receiving_yards_hub_v13.py")
    eligibility = _source(root, "nfl_prop_app_eligibility_v1.py")
    rushing_context = _source(root, "nfl_rushing_yards_context_api_v1.py")
    receiving_context = _source(root, "nfl_receiving_yards_context_api_v1.py")
    receiving_market = _source(root, "nfl_receiving_yards_market_api_v1.py")

    checks = [
        _require(
            router,
            '"Rushing Yards": "nfl_rushing_yards_hub_v16"',
            '"Receiving Yards": "nfl_receiving_yards_hub_v17"',
            'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0',
            label="ACTIVE_ROUTER_OWNERS",
        ),
        _require(
            rushing_owner,
            'FROZEN_PRIOR = "nfl_rushing_yards_hub_v15"',
            "guard_context_payload(",
            'raw_player.get("official_athlete_id")',
            'raw_player.get("official_team_id")',
            'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0',
            label="RUSHING_RENDER_IDENTITY_GATE",
        ),
        _require(
            receiving_owner,
            'FROZEN_PRIOR = "nfl_receiving_yards_hub_v16"',
            "guard_context_payload(",
            'raw_player.get("official_athlete_id")',
            'raw_player.get("official_team_id")',
            'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0',
            label="RECEIVING_RENDER_IDENTITY_GATE",
        ),
        _require(
            rushing_cards,
            "prior.market_api.market_for_athlete(",
            '_safe(row.get("official_athlete_id"), "")',
            "team_id,",
            "headshot = _headshot_url(athlete_id)",
            "logo = _team_logo_url(team_abbr)",
            "compact_slot.html(board)",
            "st.html(_COMPACT_CSS)",
            label="RUSHING_CARD_BINDING",
        ),
        _require(
            receiving_cards,
            "projection_yards_for_athlete(",
            "context,\n                team,\n                athlete_id,",
            "face = headshot_url(athlete_id)",
            "logo = team_logo_url(team_abbr)",
            'row.get("line")',
            'row.get("over_odds")',
            'row.get("under_odds")',
            "st.html(_STEP13_CSS)",
            label="RECEIVING_CARD_BINDING",
        ),
        _require(
            eligibility,
            'official_event_id',
            'official_team_id',
            'official_athlete_id',
            'SPORTSBOOK_PROJECTION_INFLUENCE = 0.0',
            label="SHARED_APP_IDENTITY_GATE",
        ),
        _require(
            rushing_context,
            'official_event_id',
            'official_team_id',
            'official_athlete_id',
            'opponent_official_team_id',
            'projection_weight',
            label="RUSHING_CONTEXT_IDENTITY",
        ),
        _require(
            receiving_context,
            'official_event_id',
            'official_team_id',
            'official_athlete_id',
            'opponent_official_team_id',
            'projection_weight',
            label="RECEIVING_CONTEXT_IDENTITY",
        ),
        _require(
            receiving_market,
            'if _safe((row or {}).get("official_athlete_id")) == athlete_id',
            'and (not team_id or _safe((row or {}).get("official_team_id")) == team_id)',
            '"projection_weight": 0.0',
            'identity.get("player_name_matching") is not False',
            'identity.get("fuzzy_matching") is not False',
            label="RECEIVING_MARKET_EXACT_JOIN",
        ),
    ]
    return checks


def _exact_market_join_checks() -> list[dict[str, Any]]:
    import nfl_receiving_yards_market_api_v1 as receiving_market
    import nfl_rushing_yards_market_api_v1 as rushing_market

    event_market = {
        "ready": True,
        "official_event_id": "401000001",
        "http": 200,
        "props": [
            {
                "official_event_id": "401000001",
                "official_athlete_id": "4596448",
                "official_team_id": "27",
                "line": 52.5,
                "over_odds": -113,
                "under_odds": -113,
            }
        ],
    }
    checks: list[dict[str, Any]] = []
    for name, module in (
        ("RUSHING_MARKET_EXACT_JOIN", rushing_market),
        ("RECEIVING_MARKET_EXACT_JOIN_BEHAVIOR", receiving_market),
    ):
        exact = module.market_for_athlete(event_market, "4596448", "27")
        wrong_team = module.market_for_athlete(event_market, "4596448", "99")
        wrong_athlete = module.market_for_athlete(event_market, "9999999", "27")
        if exact.get("ready") is not True:
            raise RuntimeError(f"{name}: exact athlete/team row did not bind")
        if wrong_team.get("ready") is not False:
            raise RuntimeError(f"{name}: wrong team did not fail closed")
        if wrong_athlete.get("ready") is not False:
            raise RuntimeError(f"{name}: wrong athlete did not fail closed")
        checks.append({"name": name, "status": "GREEN", "exact_id_fail_closed": True})
    return checks


def certify(root: Path | None = None) -> dict[str, Any]:
    repo_root = Path(root) if root is not None else ROOT
    checks = _certify_static_bindings(repo_root) + _exact_market_join_checks()
    return {
        "status": "GREEN",
        "decision": "NFL_RB_WR_STEP3_DATA_BINDING_CERTIFIED",
        "version": VERSION,
        "check_count": len(checks),
        "checks": checks,
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "product_runtime_mutations": PRODUCT_RUNTIME_MUTATIONS,
        "identity_authority": "EXACT_ESPN_EVENT_TEAM_ATHLETE_IDS",
        "names_are_identity_keys": False,
        "fuzzy_identity_matching": False,
    }


def main() -> int:
    report = certify()
    print(
        "NFL_RB_WR_RENDER_REPAIR_STEP3_DATA_BINDING_GREEN="
        + json.dumps(report, sort_keys=True),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
