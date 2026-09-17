from __future__ import annotations

from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _games() -> list[dict]:
    return [
        {
            "event_id": "1",
            "date": "2026-08-29",
            "opponent": "Opponent A",
            "location": "home",
            "result": "W",
            "score": "31-14",
            "opponent_record_pct": 0.600,
        },
        {
            "event_id": "2",
            "date": "2026-09-05",
            "opponent": "Opponent B",
            "location": "away",
            "result": "L",
            "score": "20-24",
            "opponent_record_pct": 0.500,
        },
    ]


def test_evidence_state_exposes_visible_summary_and_completed_games() -> None:
    from cfb_game_total_clean_page_v5 import _team_evidence_state

    profile = {
        "team": "Syracuse",
        "data_source": "ESPN exact-event/current-season reconciliation",
        "completed_games": _games(),
    }
    state = _team_evidence_state(profile, {"away_team": "Syracuse"}, "away")

    assert state["team"] == "Syracuse"
    assert state["record"] == "1-1"
    assert state["ppg"] == 25.5
    assert state["allowed_pg"] == 19.0
    assert state["point_diff_pg"] == 6.5
    assert state["recent_form"] == "WL"
    assert state["data_source"] == "ESPN exact-event/current-season reconciliation"
    assert len(state["completed_games"]) == 2


def test_evidence_center_contract_has_independent_team_expanders() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v5.py").read_text(encoding="utf-8")

    assert "def _render_evidence_center" in source
    assert 'f"{away_team} evidence"' in source
    assert 'f"{home_team} evidence"' in source
    assert "expanded=False" in source
    assert "Recent completed games" in source
    assert "DATA SOURCE" in source
    assert "SOS" in source
    assert "Split context" in source


def test_evidence_center_precedes_model_gate_and_deep_audit() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v5.py").read_text(encoding="utf-8")

    evidence = source.index("_render_evidence_center(")
    model_gate = source.index("_status_cards(", evidence)
    deep_audit = source.index('st.expander("📊 Deep model evidence', model_gate)

    assert evidence < model_gate < deep_audit


def test_v5_keeps_frozen_model_and_sportsbook_boundaries() -> None:
    source = (ROOT / "cfb_game_total_clean_page_v5.py").read_text(encoding="utf-8")

    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v4"' in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "selected_result = frozen_page.slate.analyze_game(game, selected_day)" in source
    assert "runtime_display.reconcile_display_bundle(" in source


_OFFICIAL_ROWS = {
    "pace": {"label": "Plays Per Game", "value": "72.1"},
    "explosive": {"label": "Yards Per Play", "value": "6.8"},
    "red_zone": {"label": "Red Zone Touchdown %", "value": "68%"},
    "third_down": {"label": "Third Down Conversion %", "value": "47%"},
    "turnovers": {"label": "Turnover Margin", "value": "+3"},
}


def _deterministic_snapshot() -> dict:
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
        "away": {"official_stats": deepcopy(_OFFICIAL_ROWS)},
        "home": {"official_stats": deepcopy(_OFFICIAL_ROWS)},
    }


def test_game_total_deterministic_snapshot_backfills_verified_deep_evidence(monkeypatch) -> None:
    import cfb_game_total_clean_page_v6 as page
    import cfb_game_total_runtime_display_v1 as runtime

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

    monkeypatch.setattr(runtime, "_find_game_total_snapshot", lambda *_: _deterministic_snapshot())
    calls: list[tuple[dict, str]] = []

    def fake_reconcile(matchup, day):
        calls.append((deepcopy(dict(matchup)), str(day)))
        return _verified_payload(), {"runtime_status": "GREEN"}

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
    assert away["official_stats"] == _OFFICIAL_ROWS
    assert home["official_stats"] == _OFFICIAL_ROWS
    assert diag["game_total_verified_backfill_used"] is True
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
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.MAY_MODIFY_PROJECTION is False


def test_game_total_verified_backfill_fails_closed_without_inventing_evidence(monkeypatch) -> None:
    import cfb_game_total_runtime_display_v1 as runtime

    game = {
        "espn_event_id": "401000001",
        "game_date": "2026-09-19",
        "away_team": "Away U",
        "home_team": "Home U",
    }
    monkeypatch.setattr(runtime, "_find_game_total_snapshot", lambda *_: _deterministic_snapshot())

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
