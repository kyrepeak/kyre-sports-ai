from __future__ import annotations

from copy import deepcopy

import cfb_game_total_clean_page_v6 as page
import cfb_game_total_runtime_display_v1 as runtime


OFFICIAL_ROWS = {
    "pace": {"label": "Plays Per Game", "value": "72.1"},
    "explosive": {"label": "Yards Per Play", "value": "6.8"},
    "red_zone": {"label": "Red Zone Touchdown %", "value": "68%"},
    "third_down": {"label": "Third Down Conversion %", "value": "47%"},
    "turnovers": {"label": "Turnover Margin", "value": "+3"},
}


def _snapshot() -> dict:
    return {
        "event_id": "401000001",
        "game_date": "2026-09-19",
        "away_team": "Away U",
        "home_team": "Home U",
        "venue": "Snapshot Stadium",
        "broadcast": "ESPN",
        "away": {
            "team_id": "1",
            "record_text": "2-0",
            "completed_games": [{"result": "W", "score": "35-14"}],
        },
        "home": {
            "team_id": "2",
            "record_text": "2-0",
            "completed_games": [{"result": "W", "score": "31-17"}],
        },
    }


def _verified_payload() -> dict:
    return {
        "game": {
            "weather": {"summary": "Clear", "temperature": 78, "wind_mph": 7},
            "series_history": [{"season": 2025, "winner": "Home U", "score": "28-24"}],
        },
        "away": {"official_stats": deepcopy(OFFICIAL_ROWS)},
        "home": {"official_stats": deepcopy(OFFICIAL_ROWS)},
    }


def test_deterministic_snapshot_backfills_only_verified_deep_evidence(monkeypatch) -> None:
    game = {
        "espn_event_id": "401000001",
        "game_date": "2026-09-19",
        "away_team": "Away U",
        "home_team": "Home U",
    }
    frozen_away = {"team": "Away U", "frozen_marker": "away"}
    frozen_home = {"team": "Home U", "frozen_marker": "home"}
    original_game = deepcopy(game)
    original_away = deepcopy(frozen_away)
    original_home = deepcopy(frozen_home)

    monkeypatch.setattr(runtime, "_find_game_total_snapshot", lambda *_: _snapshot())
    calls: list[tuple[dict, str]] = []

    def fake_reconcile(matchup, day):
        calls.append((deepcopy(dict(matchup)), str(day)))
        return _verified_payload(), {"runtime_status": "GREEN"}

    # Step 2 contract: deterministic display reliability remains primary, but
    # missing evidence may be backfilled from the existing verified deep source.
    monkeypatch.setattr(runtime.verified_runtime, "reconcile_matchup", fake_reconcile)

    display_game, away, home, diag = runtime.reconcile_display_bundle(
        game,
        "2026-09-19",
        frozen_away,
        frozen_home,
    )

    assert len(calls) == 1
    assert display_game["venue"] == "Snapshot Stadium"
    assert display_game["broadcast"] == "ESPN"
    assert display_game["weather"]["summary"] == "Clear"
    assert display_game["series_history"][0]["season"] == 2025
    assert away["official_stats"] == OFFICIAL_ROWS
    assert home["official_stats"] == OFFICIAL_ROWS
    assert diag["game_total_verified_backfill_used"] is True

    # Display enrichment must never mutate the frozen model inputs.
    assert game == original_game
    assert frozen_away == original_away
    assert frozen_home == original_home

    statuses = page._existing_step_status(
        {"away": {"exact_identity": True}, "home": {"exact_identity": True}},
        {**away, "sample_games": 1, "ppg": 30.0, "allowed_pg": 20.0},
        {**home, "sample_games": 1, "ppg": 28.0, "allowed_pg": 21.0},
        display_game,
    )
    assert all(statuses[step] == "READY" for step in range(4, 11))


def test_verified_backfill_fails_closed_without_inventing_evidence(monkeypatch) -> None:
    game = {
        "espn_event_id": "401000001",
        "game_date": "2026-09-19",
        "away_team": "Away U",
        "home_team": "Home U",
    }
    monkeypatch.setattr(runtime, "_find_game_total_snapshot", lambda *_: _snapshot())

    def unavailable(*_args, **_kwargs):
        raise RuntimeError("verified provider unavailable")

    monkeypatch.setattr(runtime.verified_runtime, "reconcile_matchup", unavailable)

    display_game, away, home, diag = runtime.reconcile_display_bundle(
        game,
        "2026-09-19",
        {"team": "Away U"},
        {"team": "Home U"},
    )

    assert not away.get("official_stats")
    assert not home.get("official_stats")
    assert not display_game.get("weather")
    assert not display_game.get("series_history")
    assert diag["game_total_verified_backfill_used"] is False
    assert "RuntimeError" in diag["game_total_verified_backfill_error"]


def test_step2_preserves_frozen_game_total_contract() -> None:
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False
