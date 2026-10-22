from __future__ import annotations

from datetime import datetime, timezone

import pytest

import sports_api.api.cfb_game_total_page1_v1 as api


def _game(game_id: str, away: str, home: str, kickoff: str = "2026-10-24T19:30:00+00:00") -> dict:
    return {
        "game_id": game_id,
        "identity_key": game_id,
        "away_team": away,
        "home_team": home,
        "kickoff_iso": kickoff,
        "identity_verified": True,
        "date_matches_query": True,
    }


def _quote(book: str, event: str, market_id: str, away: str, home: str, total: float) -> dict:
    return {
        "sportsbook": book,
        "provider_event_id": event,
        "provider_market_id": market_id,
        "away_team": away,
        "home_team": home,
        "total_line": total,
        "over_price": -112,
        "under_price": -108,
        "away_spread": 14.5,
        "away_spread_price": -106,
        "home_spread": -14.5,
        "home_spread_price": -114,
        "away_moneyline": 520,
        "home_moneyline": -750,
        "observed_at_utc": "2026-10-22T07:30:00+00:00",
        "line_status": "open",
    }


def test_payload_uses_ncaa_game_id_once_and_preserves_exact_book_quote(monkeypatch):
    games = [
        _game("ncaa-1", "Michigan State", "UCLA"),
        _game("ncaa-1", "Michigan State", "UCLA"),
    ]
    monkeypatch.setattr(api, "_resolve_slate_date", lambda **_: ("2026-10-24", games))
    monkeypatch.setattr(
        api,
        "collect_primary_market_rows",
        lambda: [_quote("FanDuel", "fd-1", "fd-market-1", "Michigan State", "UCLA", 43.5)],
    )
    monkeypatch.setattr(api, "collect_secondary_market_rows", lambda: [])

    payload = api.build_page1_payload(
        game_date="2026-10-24",
        now_provider=lambda: datetime(2026, 10, 22, 7, 40, tzinfo=timezone.utc),
    )

    assert payload["service"] == "Kyre Sports API"
    assert payload["routing"]["application_gateway"] == "Kyre Sports API"
    assert payload["routing"]["schedule_primary"] == "NCAA"
    assert payload["routing"]["market_primary"] == "FanDuel"
    assert payload["routing"]["consensus_averaging"] is False
    assert payload["routing"]["null_to_zero"] is False
    assert payload["routing"]["fabrication"] is False
    assert payload["routing"]["forbidden_providers"] == ["SGO", "ESPN", "ESPN BET"]

    assert len(payload["games"]) == 1
    game = payload["games"][0]
    assert game["game_id"] == "ncaa-1"
    assert len(game["market_quotes"]) == 1
    quote = game["market_quotes"][0]
    assert quote["sportsbook"] == "FanDuel"
    assert quote["provider_event_id"] == "fd-1"
    assert quote["provider_market_id"] == "fd-market-1"
    assert quote["total_line"] == 43.5
    assert quote["over_price"] == -112
    assert quote["under_price"] == -108
    assert quote["away_moneyline"] == 520
    assert quote["home_moneyline"] == -750
    assert quote["observed_at_utc"] == "2026-10-22T07:30:00+00:00"


def test_secondary_is_called_only_for_games_missing_primary_quotes(monkeypatch):
    games = [
        _game("g1", "Michigan State", "UCLA"),
        _game("g2", "Texas A&M", "Alabama", "2026-10-24T19:30:00+00:00"),
    ]
    monkeypatch.setattr(api, "_resolve_slate_date", lambda **_: ("2026-10-24", games))
    monkeypatch.setattr(
        api,
        "collect_primary_market_rows",
        lambda: [_quote("FanDuel", "fd-1", "fd-m1", "Michigan State", "UCLA", 43.5)],
    )
    seen: list[list[str]] = []

    def secondary(missing_games):
        seen.append([row["game_id"] for row in missing_games])
        return [_quote("DraftKings", "dk-2", "dk-m2", "Texas A&M", "Alabama", 49.5)]

    monkeypatch.setattr(api, "collect_secondary_market_rows", secondary)
    payload = api.build_page1_payload(game_date="2026-10-24")

    assert seen == [["g2"]]
    quotes = {row["game_id"]: row["market_quotes"] for row in payload["games"]}
    assert [q["sportsbook"] for q in quotes["g1"]] == ["FanDuel"]
    assert [q["sportsbook"] for q in quotes["g2"]] == ["DraftKings"]


def test_conflicting_books_remain_separate_and_missing_values_are_not_zero(monkeypatch):
    games = [_game("g1", "Ole Miss", "Texas")]
    monkeypatch.setattr(api, "_resolve_slate_date", lambda **_: ("2026-10-24", games))
    fd = _quote("FanDuel", "fd", "fd-total", "Ole Miss", "Texas", 54.5)
    dk = _quote("DraftKings", "dk", "dk-total", "Ole Miss", "Texas", 55.0)
    dk["away_moneyline"] = None
    monkeypatch.setattr(api, "collect_primary_market_rows", lambda: [fd])
    monkeypatch.setattr(api, "collect_secondary_market_rows", lambda _missing: [dk])

    payload = api.build_page1_payload(game_date="2026-10-24")
    quotes = payload["games"][0]["market_quotes"]

    # Primary coverage is complete, so the secondary source is not consulted and
    # no consensus/average line can be manufactured.
    assert len(quotes) == 1
    assert quotes[0]["total_line"] == 54.5
    assert quotes[0]["away_moneyline"] == 520
    assert all(q.get("away_moneyline") != 0 for q in quotes)


def test_invalid_game_date_fails_closed(monkeypatch):
    with pytest.raises(ValueError):
        api.build_page1_payload(game_date="10/24/2026")
