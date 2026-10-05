"""NFL Rushing + Receiving live-game repair — Step 4/5 Receiving live cert.

Step 4 proves the currently routed Receiving Yards V17 path can remain useful
while an NFL game is in progress without opening the prop-market gate. The only
product mutation is a LIVE-only exact-ID stale-roster reconciliation in V17;
the frozen shared identity guard remains the final authority.
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

MISSION_STEP = "4/5"
MODEL_VERSION = "NFL LIVE GAME REPAIR STEP 4 • RECEIVING LIVE CERT V1"
RECEIVING_OWNER = "nfl_receiving_yards_hub_v17.py"
RUSHING_OWNER = "nfl_rushing_yards_hub_v16.py"
RECEIVING_MUTATION_SCOPE = "LIVE_STALE_API_PLAYER_FILTER_ONLY"
ROUTER_PATH = Path("streamlit_memory_lazy_router_v187.py")
RECEIVING_PATH = Path(RECEIVING_OWNER)
RUSHING_PATH = Path(RUSHING_OWNER)
BASE_RECEIVING_PATH = Path("nfl_receiving_yards_hub_v2.py")
CONTEXT_API_PATH = Path("nfl_receiving_yards_context_api_v1.py")
SHARED_GATE_PATH = Path("nfl_prop_app_eligibility_v1.py")

MAY_MODIFY_RECEIVING_PAGE = True
MAY_MODIFY_RUSHING_PAGE = False
MAY_MODIFY_ROUTER = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SPORTSBOOK = False
API2_USED = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0

_EXPECTED_RECEIVING_BLOB = "d69990d75666db414839470db20f68958c284b9e"
_EXPECTED_RUSHING_BLOB = "2a81e3130882b579a8d1e52bca0ef1f4e94c988c"
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
        raise AssertionError(f"NFL_LIVE_GAME_STEP4_BLOB_UNRESOLVED:{path}")
    return completed.stdout.strip().lower()


def verify_repository_contract() -> dict[str, Any]:
    router = _read(ROUTER_PATH)
    receiving = _read(RECEIVING_PATH)
    _read(RUSHING_PATH)
    base = _read(BASE_RECEIVING_PATH)
    context_api = _read(CONTEXT_API_PATH)
    shared = _read(SHARED_GATE_PATH)

    checks = {
        "router_owner_exact": '"Receiving Yards": "nfl_receiving_yards_hub_v17"' in router,
        "shared_guard_called": (
            "from nfl_prop_app_eligibility_v1 import guard_context_payload" in receiving
            and "guard_context_payload(" in receiving
            and "_ORIGINAL_LOAD = base_page._load_receiving_context" in receiving
        ),
        "context_api_state_agnostic": (
            "def fetch_event_context(" in context_api
            and "identity_state" not in context_api
            and "prop_gate_open" not in context_api
        ),
        "base_renderer_consumes_ready_data": (
            "context = _load_receiving_context(selected_event_id)" in base
            and 'context.get("ready") is not True' in base
        ),
        "step2_live_bridge_present": (
            'identity_state == "LIVE"' in shared
            and 'snapshot.get("identity_gate_open") is True' in shared
            and 'snapshot.get("prop_gate_open") is not True' in shared
        ),
        "live_roster_reconciliation_present": (
            "def _reconcile_live_roster_payload(" in receiving
            and "athlete_id not in current_ids" in receiving
            and "roster_loader=load_roster" in receiving
            and 'result["step4_live_roster_filtered_count"] = filtered_count' in receiving
        ),
        "receiving_blob_step4_exact": _blob(RECEIVING_OWNER) == _EXPECTED_RECEIVING_BLOB,
        "rushing_step3_frozen_exact": _blob(RUSHING_OWNER) == _EXPECTED_RUSHING_BLOB,
        "shared_gate_step2_frozen_exact": _blob(str(SHARED_GATE_PATH)) == _EXPECTED_SHARED_GATE_BLOB,
    }
    failed = [name for name, value in checks.items() if value is not True]
    if failed:
        raise AssertionError("NFL_LIVE_GAME_STEP4_REPOSITORY_DRIFT:" + ",".join(failed))
    return {
        "status": "GREEN",
        "mission_step": MISSION_STEP,
        "router_owner": "nfl_receiving_yards_hub_v17",
        **checks,
        "product_mutation": True,
        "receiving_mutation_scope": RECEIVING_MUTATION_SCOPE,
        "rushing_untouched": True,
        "api2_used": False,
    }


def _context(*, malformed: bool = False) -> dict[str, Any]:
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
                        "official_athlete_id": "not-an-id" if malformed else "101",
                        "official_team_id": "1",
                        "position": "WR",
                        "player_name": "ATL Receiver",
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
                        "position": "TE",
                        "player_name": "CAR Receiver",
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


def _run_wrapper(
    snapshot: dict[str, Any],
    *,
    stale_roster: bool = False,
    malformed: bool = False,
) -> dict[str, Any]:
    import nfl_prop_app_eligibility_v1 as gate
    import nfl_receiving_yards_hub_v17 as receiving

    original_load = receiving._ORIGINAL_LOAD
    original_snapshot = gate._load_event_snapshot
    original_roster = gate._eligible_ids_for_team

    def roster(abbr: str):
        if stale_roster and abbr == "ATL":
            return {"999"}, {"ok": True, "http": 200}
        return _roster_loader(abbr)

    receiving._ORIGINAL_LOAD = lambda _event: _context(malformed=malformed)
    gate._load_event_snapshot = lambda _event: dict(snapshot)
    gate._eligible_ids_for_team = roster
    try:
        return receiving._load_receiving_context_step7(_EVENT_ID)
    finally:
        receiving._ORIGINAL_LOAD = original_load
        gate._load_event_snapshot = original_snapshot
        gate._eligible_ids_for_team = original_roster


def certify_synthetic_live_receiving() -> dict[str, Any]:
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


def certify_synthetic_final_receiving() -> dict[str, Any]:
    result = _run_wrapper(_final_snapshot())
    assert result.get("ready") is False
    assert result.get("teams") == []
    assert result.get("step7_app_identity_verified") is False
    return {"status": "GREEN", "ready": False, "team_count": 0}


def certify_synthetic_stale_roster_receiving() -> dict[str, Any]:
    result = _run_wrapper(_live_snapshot(), stale_roster=True)
    players = [
        player
        for team in (result.get("teams") or [])
        for player in (team.get("players") or [])
    ]
    assert result.get("ready") is True
    assert result.get("step7_app_identity_verified") is True
    assert result.get("step7_app_live_identity_verified") is True
    assert result.get("step4_live_roster_filtered_count") == 1
    assert len(players) == 1
    return {
        "status": "GREEN",
        "ready": True,
        "identity_verified": True,
        "filtered_count": 1,
        "player_count": len(players),
    }


def certify_synthetic_malformed_receiving() -> dict[str, Any]:
    result = _run_wrapper(_live_snapshot(), malformed=True)
    assert result.get("ready") is False
    assert result.get("teams") == []
    assert result.get("step7_app_identity_verified") is False
    return {"status": "GREEN", "ready": False, "fail_closed": True}


def discover_current_live_nfl_event() -> dict[str, Any] | None:
    eastern = datetime.now(ZoneInfo("America/New_York"))
    response = requests.get(
        "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
        params={"dates": eastern.strftime("%Y%m%d"), "limit": 100},
        timeout=15,
        headers={"Accept": "application/json", "User-Agent": "KyreSportsAI-Step4/1.0"},
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


def certify_current_live_receiving(*, attempts: int = 3) -> dict[str, Any]:
    live = discover_current_live_nfl_event()
    if not live:
        raise AssertionError("NFL_LIVE_GAME_STEP4_NO_ACTIVE_NFL_EVENT")

    import nfl_receiving_yards_hub_v17 as receiving

    result: dict[str, Any] = {}
    for attempt in range(1, max(1, attempts) + 1):
        result = receiving._load_receiving_context_step7(live["event_id"])
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
    assert len(players) >= 1
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
        "filtered_count": int(result.get("step4_live_roster_filtered_count") or 0),
        "sportsbook_projection_influence": 0.0,
        "api2_used": False,
    }


def run(
    *,
    require_live: bool = False,
    artifact_dir: str | Path = "artifacts/nfl-live-game-repair-step4-receiving-live",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "GREEN",
        "mission_step": MISSION_STEP,
        "repository": verify_repository_contract(),
        "synthetic_live": certify_synthetic_live_receiving(),
        "synthetic_final": certify_synthetic_final_receiving(),
        "synthetic_stale_roster": certify_synthetic_stale_roster_receiving(),
        "synthetic_malformed": certify_synthetic_malformed_receiving(),
        "product_mutation": True,
        "receiving_mutation_scope": RECEIVING_MUTATION_SCOPE,
        "rushing_untouched": True,
        "api2_used": False,
    }
    if require_live:
        payload["current_live"] = certify_current_live_receiving()
    artifacts = Path(artifact_dir)
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "step4_receiving_live.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("NFL_LIVE_GAME_REPAIR_STEP4_RECEIVING_LIVE_GREEN")
    if require_live:
        print("NFL_LIVE_GAME_REPAIR_STEP4_CURRENT_LIVE_RECEIVING_GREEN")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-live", action="store_true")
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/nfl-live-game-repair-step4-receiving-live",
    )
    args = parser.parse_args()
    run(require_live=args.require_live, artifact_dir=args.artifact_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
