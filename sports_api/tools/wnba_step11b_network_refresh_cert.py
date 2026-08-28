"""Offline deterministic certification for WNBA Step 11B network orchestration."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step11_draftkings_provider as s11a
from sports_api import wnba_step11_network_refresh_orchestrator as s11b

UTC = timezone.utc
BRANCH = "wnba-step11b-network-refresh-orchestrator-20260828"
CERT_MARKER = "STEP11B_NETWORK_REFRESH_ORCHESTRATOR_CERTIFIED"
OUTPUT_PATH = Path("step11b-network-refresh-cert.json")
GAME_ID = "1022600291"
PLAYER_ID = 1642301
HOME_TEAM_ID = 1611661330
AWAY_TEAM_ID = 1611661329


def _env() -> dict[str, str]:
    return {
        "WNBA_STEP11A_DRAFTKINGS_PROVIDER_ENABLED": "true",
        "WNBA_STEP11B_NETWORK_REFRESH_ENABLED": "true",
        "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
        "WNBA_STEP10B_MARKET_ADAPTER_ENABLED": "true",
        "WNBA_STEP10C_MARKET_SNAPSHOT_ENABLED": "true",
        "WNBA_STEP10D_REFRESH_CONTROLLER_ENABLED": "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
        "WNBA_STEP6J_CANARY_ENABLED": "false",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED": "false",
    }


def _schedule() -> dict:
    return {
        "leagueSchedule": {
            "seasonYear": "2026",
            "gameDates": [{
                "gameDate": "2026-08-28",
                "games": [{
                    "gameId": GAME_ID,
                    "gameDateTimeUTC": "2026-08-28T23:00:00Z",
                    "homeTeam": {
                        "teamId": str(HOME_TEAM_ID),
                        "teamCity": "Atlanta",
                        "teamName": "Dream",
                        "teamTricode": "ATL",
                    },
                    "awayTeam": {
                        "teamId": str(AWAY_TEAM_ID),
                        "teamCity": "Portland",
                        "teamName": "Fire",
                        "teamTricode": "POR",
                    },
                }],
            }],
        }
    }


def _market_name(stat: str) -> str:
    return {
        "points": "Player Points",
        "rebounds": "Player Rebounds",
        "assists": "Player Assists",
        "pra": "Player Points + Rebounds + Assists",
    }[stat]


def _document(stat: str, line: float, over: int, under: int) -> dict:
    market_id = f"cert-market-{stat}"
    return {
        "events": [{
            "id": "cert-dk-event",
            "startEventDate": "2026-08-28T23:00:00Z",
            "participants": [{"name": "Atlanta Dream"}, {"name": "Portland Fire"}],
        }],
        "markets": [{
            "id": market_id,
            "eventId": "cert-dk-event",
            "name": _market_name(stat),
        }],
        "selections": [
            {
                "id": f"{market_id}-over",
                "marketId": market_id,
                "label": "Over",
                "points": line,
                "playerName": "Certification Player",
                "oddsAmerican": over,
            },
            {
                "id": f"{market_id}-under",
                "marketId": market_id,
                "label": "Under",
                "points": line,
                "playerName": "Certification Player",
                "oddsAmerican": under,
            },
        ],
    }


class _Response:
    def __init__(self, document: dict, status_code: int = 200):
        self._document = deepcopy(document)
        self.status_code = status_code
        self.content = b"{}"

    def json(self):
        return deepcopy(self._document)


def main() -> None:
    documents = {
        s11a.OFFICIAL_SCHEDULE_URL: _schedule(),
        s11a.FROZEN_DRAFTKINGS_ENDPOINTS[0]: _document("points", 20.5, -105, -115),
        s11a.FROZEN_DRAFTKINGS_ENDPOINTS[1]: _document("rebounds", 10.5, -110, -110),
        s11a.FROZEN_DRAFTKINGS_ENDPOINTS[2]: _document("assists", 4.5, 105, -125),
        s11a.FROZEN_DRAFTKINGS_ENDPOINTS[3]: _document("pra", 35.5, -108, -112),
    }
    request_state = {"schedule_calls": 0, "total_calls": 0}

    def requester(url, *, headers, timeout):
        request_state["total_calls"] += 1
        if url == s11a.OFFICIAL_SCHEDULE_URL:
            request_state["schedule_calls"] += 1
            if request_state["schedule_calls"] == 1:
                return _Response({}, status_code=503)
        return _Response(documents[url])

    evaluated = datetime.now(UTC)
    result = s11b.run_step11b_network_refresh_cycle(
        season=2026,
        slate_date="2026-08-28",
        evaluated_at=evaluated,
        provider_attempts=3,
        provider_requester=requester,
        roster_loader=lambda season: {
            "players": [{
                "player_id": PLAYER_ID,
                "full_name": "Certification Player",
                "team_id": HOME_TEAM_ID,
                "team_key": "atlanta-dream",
            }],
            "team_source_urls": {},
        },
        env=_env(),
    )

    assert request_state["schedule_calls"] == 2
    assert request_state["total_calls"] == 6
    assert result["network_refresh"]["attempts_executed"] == 2
    assert result["network_refresh"]["retryable_failures"] == 1
    assert result["network_refresh"]["succeeded"] is True
    assert result["network_refresh"]["sleep_performed"] is False
    assert result["network_refresh"]["scheduler_invoked"] is False
    assert result["provider_refresh"]["attempts"][0]["ok"] is False
    assert result["provider_refresh"]["attempts"][1]["ok"] is True

    cycle = result["step10d_cycle"]
    assert cycle["status"] == "ready"
    assert cycle["snapshot_source"] == "current_refresh"
    assert cycle["refresh"]["provider_count"] == 1
    assert cycle["refresh"]["successful_provider_count"] == 1
    assert cycle["refresh"]["total_attempts_consumed"] == 2
    assert cycle["providers"][0]["retries_planned"] == 1
    assert cycle["refresh"]["retry_policy"]["sleep_executed"] is False
    assert cycle["market_snapshot"]["snapshot"]["eligible_record_count"] == 4
    records = cycle["market_snapshot"]["records"]
    assert {row["game_id"] for row in records} == {GAME_ID}
    assert {row["player_id"] for row in records} == {PLAYER_ID}
    assert {row["stat"] for row in records} == {"points", "rebounds", "assists", "pra"}

    guards = result["guardrails"]
    assert guards["sportsbook_network_fetch_attempted"] is True
    assert guards["sportsbook_network_fetch_performed"] is True
    assert guards["sportsbook_http_methods"] == ["GET"]
    for key in (
        "authentication_used",
        "cookies_used",
        "wager_action_performed",
        "paid_odds_vendor_used",
        "retry_sleep_performed",
        "scheduler_started",
        "step9_called",
        "basketball_projection_changed",
        "step8_distribution_changed",
        "supabase_mutated",
        "persistence_mutated",
        "production_runtime_enabled",
        "production_activation_allowed",
    ):
        assert guards[key] is False, key

    evidence = {
        "data_type": "wnba_step11b_network_refresh_cert_v1",
        "certification_result": CERT_MARKER,
        "branch": BRANCH,
        "github_head_sha": os.environ.get("GITHUB_SHA"),
        "release_id": s11b.RELEASE_ID,
        "schema_version": s11b.SCHEMA_VERSION,
        "model_version": s11b.MODEL_VERSION,
        "frozen_step11a_sha": s11b.STEP11A_FROZEN_HEAD_SHA,
        "frozen_step10_sha": s11b.STEP10_FROZEN_HEAD_SHA,
        "certified_refresh": {
            "network_attempts_executed": result["network_refresh"]["attempts_executed"],
            "retryable_failures": result["network_refresh"]["retryable_failures"],
            "sleep_performed": result["network_refresh"]["sleep_performed"],
            "step10d_status": cycle["status"],
            "snapshot_source": cycle["snapshot_source"],
            "eligible_record_count": cycle["market_snapshot"]["snapshot"]["eligible_record_count"],
            "refresh_cycle_id": cycle["refresh_cycle_id"],
            "refresh_cycle_content_sha256": cycle["refresh_cycle_content_sha256"],
            "step10c_snapshot_content_sha256": cycle["market_snapshot"]["snapshot_content_sha256"],
            "step11a_provider_bridge_content_sha256": result["network_refresh"]["step11a_provider_bridge_content_sha256"],
            "orchestration_content_sha256": result["orchestration_content_sha256"],
        },
        "safety": guards,
    }
    OUTPUT_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(CERT_MARKER)


if __name__ == "__main__":
    main()
