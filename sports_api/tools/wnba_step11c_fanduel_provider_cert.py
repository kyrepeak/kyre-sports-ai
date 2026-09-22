"""Offline certification for WNBA Step 11C FanDuel provider bridge."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step11_fanduel_provider as s11c

UTC = timezone.utc
BRANCH = "wnba-step11c-fanduel-provider-20260828"
CERT_MARKER = "STEP11C_FANDUEL_PROVIDER_BRIDGE_CERTIFIED"
OUTPUT_PATH = Path("step11c-fanduel-provider-cert.json")
GAME_ID = "1022600291"
PLAYER_ID = 1642301
HOME_TEAM_ID = 1611661330
AWAY_TEAM_ID = 1611661329
EVENT_ID = "35990001"


def _env() -> dict[str, str]:
    return {
        "WNBA_STEP11C_FANDUEL_PROVIDER_ENABLED": "true",
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
    return {"leagueSchedule": {"seasonYear": "2026", "gameDates": [{"gameDate": "2026-08-28", "games": [{
        "gameId": GAME_ID,
        "gameDateTimeUTC": "2026-08-28T23:00:00Z",
        "homeTeam": {"teamId": str(HOME_TEAM_ID), "teamCity": "Atlanta", "teamName": "Dream", "teamTricode": "ATL"},
        "awayTeam": {"teamId": str(AWAY_TEAM_ID), "teamCity": "Portland", "teamName": "Fire", "teamTricode": "POR"},
    }]}]}}


def _odds(price: int) -> dict:
    return {"americanDisplayOdds": {"americanOdds": price}, "trueOdds": {"decimalOdds": {"decimalOdds": 1.91}}}


def _market(stat: str, line: float, over: int, under: int) -> dict:
    labels = {
        "points": "Certification Player - Player Points",
        "rebounds": "Certification Player - Player Rebounds",
        "assists": "Certification Player - Player Assists",
        "pra": "Certification Player - Player Points + Rebounds + Assists",
    }
    mid = f"cert-fd-{stat}"
    return {
        "marketId": mid,
        "marketName": labels[stat],
        "marketStatus": "OPEN",
        "runners": [
            {"selectionId": f"{mid}-over", "runnerName": f"Over {line}", "runnerStatus": "ACTIVE", "winRunnerOdds": _odds(over)},
            {"selectionId": f"{mid}-under", "runnerName": f"Under {line}", "runnerStatus": "ACTIVE", "winRunnerOdds": _odds(under)},
        ],
    }


def main() -> None:
    event = {
        "eventId": EVENT_ID,
        "name": "Portland Fire @ Atlanta Dream",
        "openDate": "2026-08-28T23:00:00Z",
        "homeTeam": {"name": "Atlanta Dream"},
        "awayTeam": {"name": "Portland Fire"},
    }
    specs = [
        ("points", 20.5, -108, -112),
        ("rebounds", 10.5, -110, -110),
        ("assists", 4.5, 102, -122),
        ("pra", 35.5, -105, -115),
    ]
    markets = {f"cert-fd-{stat}": _market(stat, line, over, under) for stat, line, over, under in specs}
    document = {"attachments": {"events": {EVENT_ID: event}, "markets": markets}}

    result = s11c.build_step11c_fanduel_provider_bridge(
        event_page_documents=[{
            "event_id": EVENT_ID,
            "captured_at_utc": "2026-08-28T06:07:45+00:00",
            "document": document,
        }],
        official_schedule_document=_schedule(),
        official_roster_players=[{
            "player_id": PLAYER_ID,
            "full_name": "Certification Player",
            "team_id": HOME_TEAM_ID,
            "team_key": "atlanta-dream",
        }],
        slate_date="2026-08-28",
        evaluated_at=datetime(2026, 8, 28, 6, 8, 0, tzinfo=UTC),
        env=_env(),
    )

    records = result["provider_refresh"]["attempts"][0]["payload"]["records"]
    assert result["identity"]["reconciled_event_count"] == 1
    assert result["identity"]["two_way_record_count"] == 4
    assert result["step10_validation"]["record_count"] == 4
    assert {row["game_id"] for row in records} == {GAME_ID}
    assert {row["player_id"] for row in records} == {PLAYER_ID}
    assert [row["stat"] for row in records] == ["assists", "points", "pra", "rebounds"]
    assert result["provider_refresh"]["provider"] == "FanDuel"
    assert result["provider_refresh"]["adapter_type"] == "flat_two_way_v1"
    assert result["lineage"]["step11b_frozen_git_sha"] == s11c.STEP11B_FROZEN_HEAD_SHA
    assert result["lineage"]["step10_frozen_git_sha"] == s11c.STEP10_FROZEN_HEAD_SHA

    guards = result["guardrails"]
    for key in (
        "sportsbook_network_fetch_performed", "official_wnba_network_fetch_performed",
        "authentication_used", "cookies_used", "wager_action_performed", "paid_odds_vendor_used",
        "basketball_projection_changed", "step8_distribution_changed", "step9_called",
        "supabase_mutated", "persistence_mutated", "scheduler_started",
        "production_runtime_enabled", "production_activation_allowed",
    ):
        assert guards[key] is False, key

    evidence = {
        "data_type": "wnba_step11c_fanduel_provider_cert_v1",
        "certification_result": CERT_MARKER,
        "branch": BRANCH,
        "github_head_sha": os.environ.get("GITHUB_SHA"),
        "release_id": s11c.RELEASE_ID,
        "model_version": s11c.MODEL_VERSION,
        "schema_version": s11c.SCHEMA_VERSION,
        "frozen_step11b_sha": s11c.STEP11B_FROZEN_HEAD_SHA,
        "frozen_step11a_sha": s11c.STEP11A_FROZEN_HEAD_SHA,
        "frozen_step10_sha": s11c.STEP10_FROZEN_HEAD_SHA,
        "provider": s11c.PROVIDER,
        "public_surface": {
            "host": "api.sportsbook.fanduel.com",
            "content_page": s11c.CONTENT_PAGE_PATH,
            "event_page": s11c.EVENT_PAGE_PATH,
            "region": s11c.FANDUEL_REGION,
            "static_public_web_key": True,
            "authentication_required": False,
        },
        "certified_bridge": {
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
