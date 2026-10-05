"""NFL Rushing + Receiving live-game repair — Step 3/5 Rushing live cert.

Step 2 already separated live render-time identity from the closed live prop-market
gate. Step 3 proves the currently routed Rushing Yards V16 path consumes that
bridge correctly. This module is proof-only: it does not modify page, router,
projection, probability, ranking, sportsbook, staking, wagering, or API 2.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

MISSION_STEP = "3/5"
MODEL_VERSION = "NFL LIVE GAME REPAIR STEP 3 • RUSHING LIVE CERT V1"
RUSHING_OWNER = "nfl_rushing_yards_hub_v16.py"
RECEIVING_OWNER = "nfl_receiving_yards_hub_v17.py"
ROUTER_PATH = Path("streamlit_memory_lazy_router_v187.py")
RUSHING_PATH = Path(RUSHING_OWNER)
RECEIVING_PATH = Path(RECEIVING_OWNER)
BASE_RUSHING_PATH = Path("nfl_rushing_yards_hub_v1.py")
CONTEXT_API_PATH = Path("nfl_rushing_yards_context_api_v1.py")
SHARED_GATE_PATH = Path("nfl_prop_app_eligibility_v1.py")

MAY_MODIFY_RUSHING_PAGE = False
MAY_MODIFY_RECEIVING_PAGE = False
MAY_MODIFY_ROUTER = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SPORTSBOOK = False
API2_USED = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_EXPECTED_RUSHING_BLOB = "bce79ae1dafda1af1864efa7fa2d860e16c93a5d"
_EXPECTED_RECEIVING_BLOB = "10d5eb4db39a70648b8f20887408d50df773b391"
_EXPECTED_SHARED_GATE_BLOB = "01d8b0039e270b03d5f96fa4ac17f542f360a610"
_EVENT_ID = "401000001"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _blob(path: str) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", f"HEAD:{path}"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(f"NFL_LIVE_GAME_STEP3_BLOB_UNRESOLVED:{path}")
    return completed.stdout.strip().lower()


def verify_repository_contract() -> dict[str, Any]:
    router = _read(ROUTER_PATH)
    rushing = _read(RUSHING_PATH)
    _read(RECEIVING_PATH)
    base = _read(BASE_RUSHING_PATH)
    context_api = _read(CONTEXT_API_PATH)
    shared = _read(SHARED_GATE_PATH)

    checks = {
        "router_owner_exact": '"Rushing Yards": "nfl_rushing_yards_hub_v16"' in router,
        "shared_guard_called": (
            "from nfl_prop_app_eligibility_v1 import guard_context_payload" in rushing
            and "return guard_context_payload(" in rushing
            and "_ORIGINAL_LOAD = base_page._load_rushing_context" in rushing
        ),
        "context_api_state_agnostic": (
            "def fetch_event_context(" in context_api
            and "identity_state" not in context_api
            and "prop_gate_open" not in context_api
            and 'state in {"in", "post"}' not in context_api
        ),
        "base_renderer_consumes_ready_data": (
            "context = _load_rushing_context(selected_event_id)" in base
            and 'if not context.get("ready")' in base
            and 'if not context.get("data_available")' in base
        ),
        "step2_live_bridge_present": (
            'identity_state == "LIVE"' in shared
            and 'snapshot.get("identity_gate_open") is True' in shared
            and 'snapshot.get("prop_gate_open") is not True' in shared
        ),
        "rushing_blob_frozen": _blob(RUSHING_OWNER) == _EXPECTED_RUSHING_BLOB,
        "receiving_untouched": _blob(RECEIVING_OWNER) == _EXPECTED_RECEIVING_BLOB,
        "shared_gate_step2_exact": _blob(str(SHARED_GATE_PATH)) == _EXPECTED_SHARED_GATE_BLOB,
    }
    failed = [name for name, value in checks.items() if value is not True]
    if failed:
        raise AssertionError("NFL_LIVE_GAME_STEP3_REPOSITORY_DRIFT:" + ",".join(failed))
    return {
        "status": "GREEN",
        "mission_step": MISSION_STEP,
        "router_owner": "nfl_rushing_yards_hub_v16",
        **checks,
        "product_mutation": False,
        "receiving_untouched": True,
        "api2_used": False,
    }


def _context() -> dict[str, Any]:
    return {
        "ready": True,
        "data_available": True,
        "official_event_id": _EVENT_ID,
        "market_enabled": False,
        "sportsbook_influence": 0.0,
        "teams": [
            {
                "official_team_id": "1",
                "team_abbreviation": "ATL",
                "players": [
                    {
                        "official_athlete_id": "101",
                        "official_team_id": "1",
                        "position": "RB",
                        "player_name": "Current ATL Runner",
                    }
                ],
            },
            {
                "official_team_id": "29",
                "team_abbreviation": "CAR",
                "players": [
                    {
                        "official_athlete_id": "201",
                        "official_team_id": "29",
                        "position": "RB",
                        "player_name": "Current CAR Runner",
                    }
                ],
            },
        ],
    }


def _live_snapshot() -> dict[str, Any]:
    return {
        "ready": True,
        "state": "CLOSED",
        "identity_state": "LIVE",
        "identity_gate_open": True,
        "prop_gate_open": False,
        "reason": "pregame player-prop identity closed after kickoff",
        "team_by_id": {"1": "ATL", "29": "CAR"},
    }


def _final_snapshot() -> dict[str, Any]:
    return {
        "ready": True,
        "state": "CLOSED",
        "prop_gate_open": False,
        "reason": "pregame player-prop identity closed after kickoff",
        "team_by_id": {"1": "ATL", "29": "CAR"},
    }


def _roster_loader(abbr: str):
    rows = {"ATL": {"101"}, "CAR": {"201"}}
    return rows.get(abbr, set()), {"ok": True, "http": 200}


def _run_wrapper(snapshot: dict[str, Any], *, stale_roster: bool = False) -> dict[str, Any]:
    import nfl_prop_app_eligibility_v1 as gate
    import nfl_rushing_yards_hub_v16 as rushing

    original_load = rushing._ORIGINAL_LOAD
    original_snapshot = gate._load_event_snapshot
    original_roster = gate._eligible_ids_for_team

    def roster(abbr: str):
        if stale_roster and abbr == "ATL":
            return {"999"}, {"ok": True, "http": 200}
        return _roster_loader(abbr)

    rushing._ORIGINAL_LOAD = lambda _event: _context()
    gate._load_event_snapshot = lambda _event: dict(snapshot)
    gate._eligible_ids_for_team = roster
    try:
        return rushing._load_rushing_context_step7(_EVENT_ID)
    finally:
        rushing._ORIGINAL_LOAD = original_load
        gate._load_event_snapshot = original_snapshot
        gate._eligible_ids_for_team = original_roster


def certify_synthetic_live_rushing() -> dict[str, Any]:
    result = _run_wrapper(_live_snapshot())
    players = [
        player
        for team in (result.get("teams") or [])
        for player in (team.get("players") or [])
    ]
    assert result.get("ready") is True
    assert result.get("data_available") is True
    assert result.get("step7_app_identity_verified") is True
    assert result.get("step7_app_identity_state") == "LIVE"
    assert result.get("step7_app_live_identity_verified") is True
    assert result.get("step7_app_final_inactives_verified") is False
    assert result.get("market_enabled") is False
    assert float(result.get("sportsbook_influence") or 0.0) == 0.0
    assert len(result.get("teams") or []) == 2
    assert len(players) >= 2
    assert all(player.get("step7_app_identity_verified") is True for player in players)
    return {
        "status": "GREEN",
        "ready": True,
        "data_available": True,
        "identity_state": "LIVE",
        "live_identity_verified": True,
        "prop_market_open": False,
        "team_count": 2,
        "player_count": len(players),
    }


def certify_synthetic_final_rushing() -> dict[str, Any]:
    result = _run_wrapper(_final_snapshot())
    assert result.get("ready") is False
    assert result.get("teams") == []
    assert result.get("step7_app_identity_verified") is False
    return {
        "status": "GREEN",
        "ready": False,
        "team_count": 0,
    }


def certify_synthetic_stale_roster_rushing() -> dict[str, Any]:
    result = _run_wrapper(_live_snapshot(), stale_roster=True)
    assert result.get("ready") is False
    assert result.get("teams") == []
    assert result.get("step7_app_identity_verified") is False
    return {
        "status": "GREEN",
        "ready": False,
        "identity_verified": False,
    }


def discover_current_live_nfl_event() -> dict[str, Any] | None:
    eastern = datetime.now(ZoneInfo("America/New_York"))
    response = requests.get(
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        params={"dates": eastern.strftime("%Y%m%d"), "limit": 100},
        timeout=15,
        headers={"Accept": "application/json", "User-Agent": "KyreSportsAI-Step3/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    for event in payload.get("events") or []:
        if not isinstance(event, dict):
            continue
        state = str((((event.get("status") or {}).get("type") or {}).get("state") or "")).strip().lower()
        event_id = str(event.get("id") or "").strip()
        if state == "in" and event_id.isdigit():
            return {
                "event_id": event_id,
                "name": str(event.get("shortName") or event.get("name") or "NFL live event"),
                "state": state,
            }
    return None


def certify_current_live_rushing(*, attempts: int = 3) -> dict[str, Any]:
    live = discover_current_live_nfl_event()
    if not live:
        raise AssertionError("NFL_LIVE_GAME_STEP3_NO_ACTIVE_NFL_EVENT")

    import nfl_rushing_yards_hub_v16 as rushing

    result: dict[str, Any] = {}
    for attempt in range(1, max(1, attempts) + 1):
        result = rushing._load_rushing_context_step7(live["event_id"])
        if (
            result.get("ready") is True
            and result.get("data_available") is True
            and result.get("step7_app_identity_state") == "LIVE"
            and result.get("step7_app_live_identity_verified") is True
        ):
            break
        if attempt < attempts:
            time.sleep(5)

    teams = result.get("teams") or []
    players = [
        player
        for team in teams
        if isinstance(team, dict)
        for player in (team.get("players") or [])
        if isinstance(player, dict)
    ]
    assert result.get("ready") is True, result.get("reason")
    assert result.get("data_available") is True, result.get("reason")
    assert result.get("step7_app_identity_verified") is True
    assert result.get("step7_app_identity_state") == "LIVE"
    assert result.get("step7_app_live_identity_verified") is True
    assert result.get("step7_app_final_inactives_verified") is False
    assert result.get("market_enabled") is False
    assert float(result.get("sportsbook_influence") or 0.0) == 0.0
    assert len(teams) == 2
    assert len(players) >= 2
    assert all(player.get("step7_app_identity_verified") is True for player in players)

    return {
        "status": "GREEN",
        "event_id": live["event_id"],
        "event": live["name"],
        "event_state": "in",
        "identity_state": "LIVE",
        "live_identity_verified": True,
        "prop_market_open": False,
        "team_count": len(teams),
        "player_count": len(players),
        "sportsbook_projection_influence": 0.0,
        "api2_used": False,
    }


def run(*, require_live: bool = False, artifact_dir: str | Path = "artifacts/nfl-live-game-repair-step3-rushing-live") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "GREEN",
        "mission_step": MISSION_STEP,
        "repository": verify_repository_contract(),
        "synthetic_live": certify_synthetic_live_rushing(),
        "synthetic_final": certify_synthetic_final_rushing(),
        "synthetic_stale_roster": certify_synthetic_stale_roster_rushing(),
        "product_mutation": False,
        "receiving_untouched": True,
        "api2_used": False,
    }
    if require_live:
        payload["current_live"] = certify_current_live_rushing()
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "step3_rushing_live.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("NFL_LIVE_GAME_REPAIR_STEP3_RUSHING_LIVE_GREEN")
    if require_live:
        print("NFL_LIVE_GAME_REPAIR_STEP3_CURRENT_LIVE_RUSHING_GREEN")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-live", action="store_true")
    parser.add_argument("--artifact-dir", default="artifacts/nfl-live-game-repair-step3-rushing-live")
    args = parser.parse_args()
    run(require_live=args.require_live, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
