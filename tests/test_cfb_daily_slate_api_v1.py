from __future__ import annotations

from datetime import date, datetime, timezone
from importlib import import_module
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "sports_api" / "api" / "cfb_daily_slate_v1.py"
HEALTH_PATH = ROOT / "sports_api" / "api" / "health.py"


def _module():
    assert MODULE_PATH.exists(), "Daily Slate API owner is not implemented yet"
    return import_module("sports_api.api.cfb_daily_slate_v1")


def _team(team_id: str, name: str, *, rank: int | None = None, record: str = "0-0") -> dict:
    team = {
        "id": team_id,
        "displayName": name,
        "shortDisplayName": name,
        "logo": f"https://a.espncdn.com/i/teamlogos/ncaa/500/{team_id}.png",
    }
    competitor = {
        "team": team,
        "records": [{"summary": record}],
        "score": "0",
    }
    if rank is not None:
        competitor["curatedRank"] = {"current": rank}
    return competitor


def _event(
    event_id: str,
    kickoff_utc: str,
    *,
    away_id: str = "1",
    away_name: str = "Away",
    home_id: str = "2",
    home_name: str = "Home",
    status: str = "Scheduled",
    provider_id: str | None = None,
    total: float | None = None,
) -> dict:
    away = _team(away_id, away_name, rank=8, record="5-1")
    away["homeAway"] = "away"
    home = _team(home_id, home_name, rank=21, record="4-2")
    home["homeAway"] = "home"
    competition = {
        "date": kickoff_utc,
        "competitors": [away, home],
        "venue": {
            "fullName": "Example Stadium",
            "address": {"city": "Tempe", "state": "AZ"},
            "indoor": False,
        },
        "broadcasts": [{"names": ["ESPN"]}],
        "status": {
            "type": {"description": status, "detail": status, "completed": status == "Final"}
        },
        "weather": {
            "displayValue": "Clear",
            "temperature": 82,
            "windSpeed": 8,
            "windDirection": "SW",
            "precipitation": 10,
        },
    }
    if provider_id and total is not None:
        competition["odds"] = [
            {
                "provider": {"id": provider_id, "name": provider_id},
                "overUnder": total,
                "details": "HOME -2.5",
                "spread": -2.5,
                "awayTeamOdds": {"moneyLine": 115},
                "homeTeamOdds": {"moneyLine": -135},
            }
        ]
    return {
        "id": event_id,
        "date": kickoff_utc,
        "status": {"type": {"description": status, "detail": status, "completed": status == "Final"}},
        "competitions": [competition],
    }


def test_phoenix_day_bounds_and_upstream_dates_cover_midnight_boundary() -> None:
    mod = _module()
    start, end = mod.phoenix_day_utc_bounds(date(2026, 10, 17))
    assert start.isoformat() == "2026-10-17T07:00:00+00:00"
    assert end.isoformat() == "2026-10-18T07:00:00+00:00"
    assert mod.upstream_scoreboard_dates_for_phoenix_day(date(2026, 10, 17)) == (
        "2026-10-17",
        "2026-10-18",
    )


def test_merge_scoreboard_games_keeps_all_fbs_fcs_games_on_selected_phoenix_day() -> None:
    mod = _module()
    rows = [
        {**mod.normalize_scoreboard_event(_event("fbs", "2026-10-17T18:00:00Z"), subdivision="FBS")},
        {**mod.normalize_scoreboard_event(_event("fcs", "2026-10-18T03:30:00Z"), subdivision="FCS")},
        {**mod.normalize_scoreboard_event(_event("outside", "2026-10-18T08:00:00Z"), subdivision="FCS")},
    ]
    games = mod.merge_scoreboard_games(rows, selected_day=date(2026, 10, 17))
    assert [game["event_id"] for game in games] == ["fbs", "fcs"]
    assert [game["kickoff_phoenix"] for game in games] == [
        "2026-10-17T11:00:00-07:00",
        "2026-10-17T20:30:00-07:00",
    ]


def test_cross_division_duplicate_is_one_game_with_both_subdivision_tags() -> None:
    mod = _module()
    event = _event("cross", "2026-10-17T19:00:00Z", away_name="FCS School", home_name="FBS School")
    rows = [
        mod.normalize_scoreboard_event(event, subdivision="FBS"),
        mod.normalize_scoreboard_event(event, subdivision="FCS"),
    ]
    games = mod.merge_scoreboard_games(rows, selected_day=date(2026, 10, 17))
    assert len(games) == 1
    assert games[0]["event_id"] == "cross"
    assert games[0]["subdivisions"] == ["FBS", "FCS"]


def test_normalized_game_exposes_logistics_status_weather_and_provenance() -> None:
    mod = _module()
    game = mod.normalize_scoreboard_event(
        _event("401", "2026-10-17T19:00:00Z", away_id="9", away_name="Away U", home_id="10", home_name="Home U"),
        subdivision="FBS",
    )
    assert game is not None
    assert game["event_id"] == "401"
    assert game["away"]["name"] == "Away U"
    assert game["home"]["name"] == "Home U"
    assert game["away"]["record"] == "5-1"
    assert game["home"]["rank"] == 21
    assert game["venue"] == "Example Stadium"
    assert game["city"] == "Tempe, AZ"
    assert game["broadcast"] == "ESPN"
    assert game["weather"]["temperature_f"] == 82
    assert game["fabrication"] is False
    assert game["provenance"]["schedule"]


def test_missing_logistics_do_not_drop_verified_game() -> None:
    mod = _module()
    event = _event("partial", "2026-10-17T19:00:00Z")
    comp = event["competitions"][0]
    comp.pop("venue")
    comp.pop("broadcasts")
    comp.pop("weather")
    game = mod.normalize_scoreboard_event(event, subdivision="FBS")
    assert game is not None
    assert game["event_id"] == "partial"
    assert game["venue"] is None
    assert game["broadcast"] is None
    assert game["weather"] is None


def test_event_without_authoritative_event_id_fails_closed() -> None:
    mod = _module()
    event = _event("missing", "2026-10-17T19:00:00Z")
    event["id"] = ""
    assert mod.normalize_scoreboard_event(event, subdivision="FBS") is None


def test_scoreboard_market_observations_preserve_actual_book_identity() -> None:
    mod = _module()
    event = _event("market", "2026-10-17T19:00:00Z", provider_id="ESPN BET", total=55.5)
    observations = mod.scoreboard_market_observations(event)
    assert observations
    assert {row["sportsbook"] for row in observations} == {"ESPN BET"}
    assert all(row["game_id"] == "market" for row in observations)
    assert all(row["identity_verified"] is True for row in observations)
    assert any(row["market_type"] == "game_total" and row["value"] == 55.5 for row in observations)


def test_payload_dedupes_same_provider_across_transports_and_keeps_independent_book() -> None:
    mod = _module()
    selected = date(2026, 10, 17)
    fanduel_event = _event("g1", "2026-10-17T19:00:00Z", provider_id="FanDuel", total=56.0)
    payloads = {
        ("2026-10-17", 80): {"events": [fanduel_event]},
        ("2026-10-17", 81): {"events": []},
        ("2026-10-18", 80): {"events": []},
        ("2026-10-18", 81): {"events": []},
    }
    market_rows = [
        {
            "game_id": "g1",
            "sportsbook": "FanDuel",
            "market_type": "game_total",
            "total": 56.0,
            "line_status": "active",
            "line_updated_at_utc": "2026-10-17T16:00:00+00:00",
            "identity_verified": True,
        },
        {
            "game_id": "g1",
            "sportsbook": "Book B",
            "market_type": "game_total",
            "total": 55.5,
            "line_status": "active",
            "line_updated_at_utc": "2026-10-17T16:01:00+00:00",
            "identity_verified": True,
        },
    ]
    payload = mod.build_daily_slate_payload(
        selected,
        now_utc=datetime(2026, 10, 17, 16, tzinfo=timezone.utc),
        scoreboard_payloads=payloads,
        market_rows=market_rows,
    )
    assert payload["requested_phoenix_date"] == "2026-10-17"
    assert payload["game_count"] == 1
    books = [row["sportsbook"] for row in payload["games"][0]["market_observations"]]
    assert books.count("FanDuel") == 1
    assert "Book B" in books
    assert payload["fabrication"] is False
    assert payload["page_wide_source_authority"] is False


def test_daily_slate_route_is_registered_in_shared_health_router() -> None:
    source = HEALTH_PATH.read_text(encoding="utf-8")
    assert "cfb_daily_slate_v1" in source
    assert "cfb_daily_slate_router.routes" in source
