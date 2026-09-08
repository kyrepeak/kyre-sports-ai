"""Regression checks for Moneyline Step 5L live-game compatibility."""
import pandas as pd

import mlb_moneyline_hub_v171 as m


def _games():
    return pd.DataFrame([
        {
            "game_pk": 1001,
            "game_date": "2026-09-08",
            "away_team": "Away A",
            "home_team": "Home A",
            "away_team_id": 1,
            "home_team_id": 2,
            "verified": True,
            "status": "Scheduled",
        },
        {
            "game_pk": 1002,
            "game_date": "2026-09-08",
            "away_team": "Away B",
            "home_team": "Home B",
            "away_team_id": 3,
            "home_team_id": 4,
            "verified": True,
            "status": "Scheduled",
        },
    ])


def test_state_label_classifies_live_delayed_final_and_pregame():
    assert m._state_label("In Progress") == "LIVE"
    assert m._state_label("Manager Challenge") == "LIVE"
    assert m._state_label("Delayed") == "DELAYED"
    assert m._state_label("Suspended") == "DELAYED"
    assert m._state_label("Final") == "FINAL"
    assert m._state_label("Scheduled") == "PREGAME"


def test_official_status_snapshot_is_exact_gamepk_only(monkeypatch):
    payload = {
        "dates": [{
            "games": [
                {
                    "gamePk": 1001,
                    "status": {"detailedState": "In Progress"},
                    "teams": {"away": {"score": 2}, "home": {"score": 1}},
                    "linescore": {"currentInningOrdinal": "5th", "inningState": "Top"},
                },
                {
                    "gamePk": 9999,
                    "status": {"detailedState": "In Progress"},
                    "teams": {"away": {"score": 9}, "home": {"score": 9}},
                    "linescore": {"currentInningOrdinal": "9th", "inningState": "Bottom"},
                },
            ]
        }]
    }
    monkeypatch.setattr(m, "_json", lambda url: payload)
    m._official_status_snapshot.clear()

    out = m._official_status_snapshot("2026-09-08", (1001, 1002))

    assert set(out) == {1001}
    assert out[1001]["state"] == "LIVE"
    assert out[1001]["away_runs"] == 2
    assert out[1001]["inning"] == "5th"


def test_live_subset_includes_live_and_delayed_but_never_final():
    games = _games()
    snapshot = {
        1001: {"state": "LIVE", "status": "In Progress"},
        1002: {"state": "FINAL", "status": "Final"},
    }
    out = m._live_subset(games, snapshot)
    assert out["game_pk"].tolist() == [1001]
    assert out.iloc[0]["status"] == "In Progress"


def test_counts_tracks_all_phases():
    out = m._counts({
        1: {"state": "LIVE"},
        2: {"state": "DELAYED"},
        3: {"state": "PREGAME"},
        4: {"state": "FINAL"},
        5: {"state": "FINAL"},
    })
    assert out == {"LIVE": 1, "DELAYED": 1, "PREGAME": 1, "FINAL": 2}


def test_no_active_games_delegates_only_to_frozen_pregame(monkeypatch):
    games = _games()
    seen = {"pregame": 0, "live": 0}
    monkeypatch.setattr(m, "_official_status_snapshot", lambda day, pks: {
        1001: {"state": "PREGAME"},
        1002: {"state": "FINAL"},
    })
    monkeypatch.setattr(m, "_render_health", lambda counts: None)
    monkeypatch.setattr(m.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(m, "_render_pregame", lambda *args, **kwargs: seen.__setitem__("pregame", seen["pregame"] + 1))
    monkeypatch.setattr(m, "_render_live", lambda *args, **kwargs: seen.__setitem__("live", seen["live"] + 1))

    m.render_moneyline_hub(games, None, None, None, None)

    assert seen["pregame"] == 1
    assert seen["live"] == 0


def test_active_games_default_to_live_mode(monkeypatch):
    games = _games()
    seen = {}
    snapshot = {
        1001: {"state": "LIVE", "status": "In Progress"},
        1002: {"state": "PREGAME", "status": "Scheduled"},
    }
    monkeypatch.setattr(m, "_official_status_snapshot", lambda day, pks: snapshot)
    monkeypatch.setattr(m, "_render_health", lambda counts: None)
    monkeypatch.setattr(m.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.st, "warning", lambda *args, **kwargs: None)

    def radio(label, options, index, horizontal, key):
        seen["options"] = list(options)
        seen["index"] = index
        return options[index]

    monkeypatch.setattr(m.st, "radio", radio)
    monkeypatch.setattr(m, "_render_pregame", lambda *args, **kwargs: seen.setdefault("pregame", True))
    monkeypatch.setattr(m, "_render_live", lambda frame, *args, **kwargs: seen.setdefault("live_ids", frame["game_pk"].tolist()))

    m.render_moneyline_hub(games, None, None, None, None)

    assert seen["index"] == 0
    assert seen["options"][0] == "🔴 LIVE IN-GAME"
    assert seen["live_ids"] == [1001]
    assert "pregame" not in seen


def test_user_can_switch_back_to_pregame_with_live_games_present(monkeypatch):
    games = _games()
    seen = {"pregame": 0, "live": 0}
    monkeypatch.setattr(m, "_official_status_snapshot", lambda day, pks: {
        1001: {"state": "LIVE", "status": "In Progress"},
    })
    monkeypatch.setattr(m, "_render_health", lambda counts: None)
    monkeypatch.setattr(m.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.st, "caption", lambda *args, **kwargs: None)
    monkeypatch.setattr(m.st, "radio", lambda label, options, index, horizontal, key: "⏳ PREGAME")
    monkeypatch.setattr(m, "_render_pregame", lambda *args, **kwargs: seen.__setitem__("pregame", seen["pregame"] + 1))
    monkeypatch.setattr(m, "_render_live", lambda *args, **kwargs: seen.__setitem__("live", seen["live"] + 1))

    m.render_moneyline_hub(games, None, None, None, None)

    assert seen["pregame"] == 1
    assert seen["live"] == 0
