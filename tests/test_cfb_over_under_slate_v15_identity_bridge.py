"""Regressions for the additive CFB O/U downstream identity bridge V15."""
from __future__ import annotations

from datetime import date

import cfb_over_under_slate_v15_identity_bridge as bridge


def _norfolk_official_row():
    return {
        "event_id": "401858220",
        "game_date": "2026-09-11",
        "away_team": "Norfolk State",
        "home_team": "Virginia",
        "away_team_id": "2450",
        "home_team_id": "258",
        "venue": "Scott Stadium",
        "broadcast": "ACCNX",
        "status": "Scheduled",
        "_official_snapshot_kind": "market_identity_v1",
    }


def test_bridge_recovers_terminal_st_alias_with_official_ids(monkeypatch):
    monkeypatch.setattr(
        bridge.schedule_v7,
        "_official_rows_for_date",
        lambda day: [_norfolk_official_row()],
    )
    game = {
        "game_date": "2026-09-11",
        "away_team": "Norfolk St.",
        "home_team": "Virginia",
        "venue": "Venue unavailable",
        "broadcast": "Broadcast unavailable",
    }

    hydrated, diag = bridge.hydrate_game_identity(game, date(2026, 9, 11))

    assert game.get("espn_event_id") is None
    assert hydrated["espn_event_id"] == "401858220"
    assert hydrated["away_espn_team_id"] == "2450"
    assert hydrated["home_espn_team_id"] == "258"
    assert hydrated["venue"] == "Scott Stadium"
    assert hydrated["broadcast"] == "ACCNX"
    assert hydrated["identity_verified"] is True
    assert diag["matched"] is True
    assert diag["match_method"] == "deterministic_alias"
    assert diag["fuzzy_matching"] is False
    assert diag["synthetic_ids"] is False
    assert diag["sportsbook_projection_weight"] == 0.0
    assert diag["projection_math"] == "frozen_v14_unchanged"


def test_bridge_collision_fails_closed_without_synthetic_identity(monkeypatch):
    rows = [_norfolk_official_row(), dict(_norfolk_official_row(), event_id="401858999")]
    monkeypatch.setattr(
        bridge.schedule_v7,
        "_official_rows_for_date",
        lambda day: rows,
    )
    game = {
        "game_date": "2026-09-11",
        "away_team": "Norfolk St.",
        "home_team": "Virginia",
    }

    hydrated, diag = bridge.hydrate_game_identity(game, "2026-09-11")

    assert hydrated == game
    assert "espn_event_id" not in hydrated
    assert diag["matched"] is False
    assert diag["match_method"] == "collision"
    assert diag["fuzzy_matching"] is False
    assert diag["synthetic_ids"] is False


def test_bridge_source_failure_fails_closed(monkeypatch):
    def unavailable(day):
        raise RuntimeError("source unavailable")

    monkeypatch.setattr(bridge.schedule_v7, "_official_rows_for_date", unavailable)
    game = {
        "game_date": "2026-09-11",
        "away_team": "Norfolk St.",
        "home_team": "Virginia",
    }

    hydrated, diag = bridge.hydrate_game_identity(game, "2026-09-11")

    assert hydrated == game
    assert diag["matched"] is False
    assert diag["match_method"] == "official_identity_unavailable"
    assert diag["error_type"] == "RuntimeError"


def test_analyze_game_hydrates_then_delegates_to_frozen_v14(monkeypatch):
    monkeypatch.setattr(
        bridge.schedule_v7,
        "_official_rows_for_date",
        lambda day: [_norfolk_official_row()],
    )
    seen = {}

    def frozen_analyze(game, as_of_day, analysis_line):
        seen["game"] = dict(game)
        seen["day"] = as_of_day
        seen["line"] = analysis_line
        return {"delegated": True}

    monkeypatch.setattr(bridge.frozen, "analyze_game", frozen_analyze)

    result = bridge.analyze_game(
        {
            "game_date": "2026-09-11",
            "away_team": "Norfolk St.",
            "home_team": "Virginia",
        },
        date(2026, 9, 11),
        51.5,
    )

    assert result == {"delegated": True}
    assert seen["game"]["espn_event_id"] == "401858220"
    assert seen["game"]["away_espn_team_id"] == "2450"
    assert seen["game"]["home_espn_team_id"] == "258"
    assert seen["day"] == date(2026, 9, 11)
    assert seen["line"] == 51.5
    assert bridge.MARKET_PROJECTION_WEIGHT == 0.0


def test_scan_slate_hydrates_every_game_then_delegates_unchanged(monkeypatch):
    games = [
        {
            "identity_key": "norfolk-st-at-virginia",
            "game_date": "2026-09-11",
            "away_team": "Norfolk St.",
            "home_team": "Virginia",
            "identity_verified": True,
            "date_matches_query": True,
        },
        {
            "identity_key": "richmond-at-nc-state",
            "game_date": "2026-09-11",
            "away_team": "Richmond",
            "home_team": "NC State",
            "identity_verified": True,
            "date_matches_query": True,
        },
    ]
    analysis_lines = {
        "norfolk-st-at-virginia": 48.5,
        "richmond-at-nc-state": 51.0,
    }
    hydrate_calls = []
    seen = {}

    def fake_hydrate(game, as_of_day):
        hydrate_calls.append((dict(game), as_of_day))
        hydrated = dict(game)
        hydrated["espn_event_id"] = (
            "401858220" if game["away_team"] == "Norfolk St." else "401858222"
        )
        return hydrated, {"matched": True}

    def frozen_scan(games_arg, day_arg, lines_arg, workers=bridge.MAX_WORKERS):
        seen["games"] = [dict(game) for game in games_arg]
        seen["day"] = day_arg
        seen["lines"] = lines_arg
        seen["workers"] = workers
        return [{"frozen_row": True}], {"version": "frozen-v14", "games_analyzed": 2}

    monkeypatch.setattr(bridge, "hydrate_game_identity", fake_hydrate)
    monkeypatch.setattr(bridge.frozen, "scan_slate", frozen_scan)

    rows, diag = bridge.scan_slate(
        games,
        date(2026, 9, 11),
        analysis_lines,
        workers=1,
    )

    assert len(hydrate_calls) == 2
    assert seen["games"][0]["espn_event_id"] == "401858220"
    assert seen["games"][1]["espn_event_id"] == "401858222"
    assert seen["games"][0]["identity_key"] == "norfolk-st-at-virginia"
    assert seen["games"][1]["identity_key"] == "richmond-at-nc-state"
    assert seen["day"] == "2026-09-11"
    assert seen["lines"] is analysis_lines
    assert seen["workers"] == 1
    assert rows == [{"frozen_row": True}]
    assert diag == {"version": "frozen-v14", "games_analyzed": 2}
    assert bridge.MARKET_PROJECTION_WEIGHT == 0.0


def test_scan_slate_preserves_original_game_when_bridge_fails_closed(monkeypatch):
    game = {
        "identity_key": "collision-game",
        "game_date": "2026-09-11",
        "away_team": "Example St.",
        "home_team": "Example",
        "identity_verified": True,
        "date_matches_query": True,
    }
    seen = {}

    monkeypatch.setattr(
        bridge,
        "hydrate_game_identity",
        lambda original, day: (dict(original), {"matched": False, "match_method": "collision"}),
    )

    def frozen_scan(games_arg, day_arg, lines_arg, workers=bridge.MAX_WORKERS):
        seen["games"] = [dict(value) for value in games_arg]
        return [], {"errors": []}

    monkeypatch.setattr(bridge.frozen, "scan_slate", frozen_scan)

    rows, diag = bridge.scan_slate(
        [game],
        "2026-09-11",
        {"collision-game": 50.0},
    )

    assert seen["games"] == [game]
    assert rows == []
    assert diag == {"errors": []}
    assert "espn_event_id" not in seen["games"][0]


def test_clear_scan_cache_delegates_to_frozen_v14(monkeypatch):
    seen = []
    monkeypatch.setattr(bridge.frozen, "clear_scan_cache", lambda: seen.append(True))

    bridge.clear_scan_cache()

    assert seen == [True]
    assert bridge.MAX_WORKERS == bridge.frozen.MAX_WORKERS
