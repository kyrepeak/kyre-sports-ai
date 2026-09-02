"""Offline certification for WNBA Step 11A DraftKings provider bridge."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step11_draftkings_provider as s11

UTC = timezone.utc
BRANCH = "wnba-step11a-draftkings-provider-20260828"
CERT_MARKER = "STEP11A_DRAFTKINGS_PROVIDER_BRIDGE_CERTIFIED"
OUTPUT_PATH = Path("step11a-draftkings-provider-cert.json")
GAME_ID = "1022600291"
PLAYER_ID = 1642301
HOME_TEAM_ID = 1611661330
AWAY_TEAM_ID = 1611661329


def _env() -> dict[str, str]:
    return {
        "WNBA_STEP11A_DRAFTKINGS_PROVIDER_ENABLED": "true",
        "WNBA_STEP10A_LIVE_MARKET_INPUT_ENABLED": "true",
        "WNBA_STEP10B_MARKET_ADAPTER_ENABLED": "true",
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
            "participants": [
                {"name": "Atlanta Dream"},
                {"name": "Portland Fire"},
            ],
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


def main() -> None:
    stats = [
        ("points", 20.5, -105, -115),
        ("rebounds", 10.5, -110, -110),
        ("assists", 4.5, 105, -125),
        ("pra", 35.5, -108, -112),
    ]
    documents = []
    for index, (url, spec) in enumerate(zip(s11.FROZEN_DRAFTKINGS_ENDPOINTS, stats, strict=True)):
        stat, line, over, under = spec
        documents.append({
            "url": url,
            "captured_at_utc": f"2026-08-28T05:49:{20 + index:02d}+00:00",
            "document": _document(stat, line, over, under),
        })

    result = s11.build_step11a_draftkings_provider_bridge(
        draftkings_documents=documents,
        official_schedule_document=_schedule(),
        official_roster_players=[{
            "player_id": PLAYER_ID,
            "full_name": "Certification Player",
            "team_id": HOME_TEAM_ID,
            "team_key": "atlanta-dream",
        }],
        slate_date="2026-08-28",
        evaluated_at=datetime(2026, 8, 28, 5, 50, 0, tzinfo=UTC),
        env=_env(),
    )

    assert result["identity"]["normalized_offer_count"] == 8
    assert result["identity"]["draftkings_event_count"] == 1
    assert result["identity"]["reconciled_event_count"] == 1
    assert result["identity"]["two_way_record_count"] == 4
    refresh = result["provider_refresh"]
    assert refresh["provider"] == "DraftKings"
    assert refresh["adapter_type"] == "flat_two_way_v1"
    assert refresh["attempts"][0]["ok"] is True
    records = refresh["attempts"][0]["payload"]["records"]
    assert [row["stat"] for row in records] == ["assists", "points", "pra", "rebounds"]
    assert {row["game_id"] for row in records} == {GAME_ID}
    assert {row["player_id"] for row in records} == {PLAYER_ID}
    assert result["step10_validation"]["record_count"] == 4
    assert result["lineage"]["step10_frozen_git_sha"] == s11.STEP10_FROZEN_SHA

    guards = result["guardrails"]
    for key in (
        "sportsbook_network_fetch_performed",
        "official_wnba_network_fetch_performed",
        "authentication_used",
        "cookies_used",
        "wager_action_performed",
        "paid_odds_vendor_used",
        "basketball_projection_changed",
        "step8_distribution_changed",
        "supabase_mutated",
        "persistence_mutated",
        "scheduler_started",
        "production_runtime_enabled",
        "production_activation_allowed",
    ):
        assert guards[key] is False, key

    evidence = {
        "data_type": "wnba_step11a_draftkings_provider_cert_v1",
        "certification_result": CERT_MARKER,
        "branch": BRANCH,
        "github_head_sha": os.environ.get("GITHUB_SHA"),
        "release_id": s11.RELEASE_ID,
        "model_version": s11.MODEL_VERSION,
        "schema_version": s11.SCHEMA_VERSION,
        "frozen_step10_sha": s11.STEP10_FROZEN_SHA,
        "frozen_draftkings_endpoint_count": len(s11.FROZEN_DRAFTKINGS_ENDPOINTS),
        "certified_bridge": {
            "normalized_offer_count": result["identity"]["normalized_offer_count"],
            "reconciled_event_count": result["identity"]["reconciled_event_count"],
            "two_way_record_count": result["identity"]["two_way_record_count"],
            "official_game_id": GAME_ID,
            "official_player_id": PLAYER_ID,
            "stats": [row["stat"] for row in records],
            "step10b_adapter_content_sha256": result["step10_validation"]["adapter_content_sha256"],
            "step10a_snapshot_content_sha256": result["step10_validation"]["step10a_snapshot_content_sha256"],
            "provider_bridge_content_sha256": result["provider_bridge_content_sha256"],
        },
        "safety": guards,
    }
    OUTPUT_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))
    print(CERT_MARKER)


if __name__ == "__main__":
    main()
