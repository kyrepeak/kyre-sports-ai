import pandas as pd

import nfl_spread_matchup_history_v1 as history


def _frame():
    return pd.DataFrame([
        {"game_id":"2025_10_HOU_JAX","gameday":"2025-11-09","away_team":"HOU","home_team":"JAX","away_score":23,"home_score":20,"spread_line":-2.5},
        {"game_id":"2025_03_JAX_HOU","gameday":"2025-09-21","away_team":"JAX","home_team":"HOU","away_score":17,"home_score":24,"spread_line":-3.0},
        {"game_id":"2024_13_HOU_JAX","gameday":"2024-12-01","away_team":"HOU","home_team":"JAX","away_score":23,"home_score":20,"spread_line":-3.5},
        {"game_id":"future","gameday":"2027-01-01","away_team":"HOU","home_team":"JAX","away_score":None,"home_score":None,"spread_line":None},
        {"game_id":"other","gameday":"2025-01-01","away_team":"BUF","home_team":"JAX","away_score":10,"home_score":20,"spread_line":1.5},
    ])


def test_history_filters_exact_matchup_completed_games_and_is_descriptive_only(monkeypatch):
    monkeypatch.setattr(history.nflverse, "_load_games_csv", lambda: _frame())
    out = history.load_matchup_history({"away_abbr":"HOU","home_abbr":"JAX"}, limit=5)
    assert out["ready"] is True
    assert out["display_only"] is True
    assert out["model_influence"] == 0.0
    assert out["source"] == "nflverse"
    assert out["games"] == 3
    assert len(out["meetings"]) == 3
    assert all({r["away_abbr"], r["home_abbr"]} == {"HOU","JAX"} for r in out["meetings"])


def test_history_reports_series_margin_and_ats_only_when_verified_lines_exist(monkeypatch):
    monkeypatch.setattr(history.nflverse, "_load_games_csv", lambda: _frame())
    out = history.load_matchup_history({"away_abbr":"HOU","home_abbr":"JAX"}, limit=5)
    assert out["series_summary"] == "Texans lead 3-0"
    assert out["average_margin"] == 4.3
    assert out["ats_games"] == 3
    assert out["ats_summary"] != "—"
    assert out["meetings"][0]["date"] == "Nov 9, 2025"
    assert out["meetings"][0]["score"] == "HOU 23 • JAX 20"


def test_history_falls_back_cleanly_when_primary_unavailable(monkeypatch):
    def boom():
        raise RuntimeError("offline")
    monkeypatch.setattr(history.nflverse, "_load_games_csv", boom)
    monkeypatch.setattr(history, "_load_espn_fallback", lambda away, home, limit: [{
        "date":"Sep 1, 2024","away_abbr":"HOU","home_abbr":"JAX","away_score":20,"home_score":17,
        "score":"HOU 20 • JAX 17","winner_abbr":"HOU","margin":3.0,"spread_line":None,"ats_winner":None,
    }])
    out = history.load_matchup_history({"away_abbr":"HOU","home_abbr":"JAX"}, limit=5)
    assert out["ready"] is True
    assert out["source"] == "espn"
    assert out["ats_games"] == 0
    assert out["ats_summary"] == "—"
