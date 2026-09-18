from __future__ import annotations

import cfb_game_total_step3_form_v1 as step3


def _identity(away_team="Miami (FL)", home_team="Wake Forest"):
    return {
        "away": {
            "team": away_team,
            "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/2390.png",
            "conference": "ACC",
        },
        "home": {
            "team": home_team,
            "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/154.png",
            "conference": "ACC",
        },
    }


def _games(results, base_for=35, base_against=20, quality=True):
    rows = []
    opponents = ["Florida A&M", "Ball State", "USF", "Virginia Tech", "Cal"]
    for idx, result in enumerate(results):
        pf = base_for + idx
        pa = base_against + (idx % 2)
        if result == "L":
            pf, pa = pa, pf
        rows.append(
            {
                "date": f"2026-09-{7 + idx * 7:02d}",
                "opponent": opponents[idx % len(opponents)],
                "result": result,
                "score": f"{pf}-{pa}",
                "opponent_record_pct": (0.64 - idx * 0.03) if quality else None,
                "opponent_def_rank": 22 + idx * 5 if quality else None,
            }
        )
    return rows


def _team(team, results, *, side, ppg, allowed, sos=0.58):
    games = _games(results, base_for=int(ppg), base_against=int(allowed))
    wins = sum(1 for r in results if r == "W")
    losses = sum(1 for r in results if r == "L")
    return {
        "side": side,
        "team": team,
        "conference": "ACC",
        "completed_games": games,
        "recent_record": {"wins": wins, "losses": losses, "ties": 0, "games": len(results)},
        "recent_ppg": ppg,
        "recent_points_allowed_pg": allowed,
        "recent_point_diff_pg": ppg - allowed,
        "sos_opponent_win_pct": sos,
        "sos_coverage": 1.0,
        "strength_of_schedule_rank": 36 if side == "home" else 89,
    }


def _away():
    return _team("Miami (FL)", ["W", "W", "W", "L", "W"], side="away", ppg=39.6, allowed=17.6, sos=0.49)


def _home():
    return _team("Wake Forest", ["W", "L", "W", "L", "L"], side="home", ppg=27.1, allowed=30.8, sos=0.61)


def test_step3_is_presentation_only():
    assert step3.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step3.MAY_MODIFY_PROJECTION is False
    assert step3.STEP3_REQUIRED_FIELDS == (
        "team",
        "sample_games",
        "last5_record",
        "recent_ppg",
        "recent_allowed_pg",
        "recent_diff_pg",
    )
    assert "avg_opponent_win_pct" in step3.STEP3_ADVANCED_FIELDS
    assert "record_vs_winning_teams" in step3.STEP3_ADVANCED_FIELDS


def test_step3_builds_last5_form_and_opponent_quality():
    row = step3.build_team_form_contract(
        _away(),
        _identity()["away"],
        side="away",
    )
    assert row["team"] == "Miami (FL)"
    assert row["sample_games"] == 5
    assert row["last5_record"] == "4-1"
    assert row["recent_ppg"] == 39.6
    assert row["recent_allowed_pg"] == 17.6
    assert row["recent_diff_pg"] == 22.0
    assert row["avg_opponent_win_pct"] == 0.49
    assert row["top40_defenses_faced"] == 4
    assert row["record_vs_winning_teams"]
    assert row["state"] in {"READY", "CHECK"}


def test_step3_missing_opponent_context_is_check_not_fake_ready():
    away = _away()
    away["sos_opponent_win_pct"] = None
    away["sos_coverage"] = None
    for row in away["completed_games"]:
        row.pop("opponent_record_pct", None)
        row.pop("opponent_def_rank", None)
    contract = step3.build_step3_contract(_identity(), away, _home())
    assert contract["state"] == "CHECK"
    assert contract["away"]["required_complete"] is True
    assert "avg_opponent_win_pct" in contract["away"]["missing_advanced"]


def test_step3_missing_recent_game_sample_is_data_limited():
    away = _away()
    away["completed_games"] = []
    away["recent_record"] = {}
    away["recent_ppg"] = None
    away["recent_points_allowed_pg"] = None
    away["recent_point_diff_pg"] = None
    contract = step3.build_step3_contract(_identity(), away, _home())
    assert contract["state"] == "DATA LIMITED"
    assert "sample_games" in contract["away"]["missing_required"]


def test_step3_trend_is_derived_from_recent_margin_direction():
    improving = {
        "team": "Example",
        "completed_games": [
            {"date": "2026-09-01", "opponent": "A", "score": "17-24", "result": "L"},
            {"date": "2026-09-08", "opponent": "B", "score": "20-21", "result": "L"},
            {"date": "2026-09-15", "opponent": "C", "score": "35-14", "result": "W"},
            {"date": "2026-09-22", "opponent": "D", "score": "42-17", "result": "W"},
        ],
        "recent_ppg": 28.5,
        "recent_points_allowed_pg": 19.0,
        "recent_point_diff_pg": 9.5,
    }
    row = step3.build_team_form_contract(improving, {"team": "Example"}, side="away")
    assert row["trend_direction"] == "Improving"


def test_step3_render_matches_locked_expanded_form_layout():
    html = step3.render_step3_html("CHECK", _identity(), _away(), _home())
    assert 'data-testid="gt157-step-3"' in html
    assert "Current Form &amp; Opponent Quality" in html
    assert "Last 3–5 Games" in html
    assert 'data-testid="gt168-step3-away"' in html
    assert 'data-testid="gt168-step3-home"' in html
    assert 'data-testid="gt168-step3-comparison"' in html
    assert 'data-testid="gt168-step3-takeaways"' in html
    assert 'data-testid="gt168-step3-edge"' in html
    assert "Last 5 Games" in html
    assert "Opponent Quality" in html
    assert "FORM COMPARISON" in html
    assert "KEY TAKEAWAYS" in html
    assert "FORM EDGE" in html
    assert "Miami (FL)" in html
    assert "Wake Forest" in html
    assert "39.6" in html
    assert "30.8" in html


def test_step3_is_universal_not_mockup_hardcoded():
    identity = _identity("Oregon", "Penn State")
    away = _team("Oregon", ["W", "W", "L"], side="away", ppg=34.2, allowed=20.1, sos=0.55)
    home = _team("Penn State", ["W", "L", "W"], side="home", ppg=30.4, allowed=18.7, sos=0.62)
    html = step3.render_step3_html("CHECK", identity, away, home)
    assert "Oregon" in html
    assert "Penn State" in html
    assert "Miami (FL)" not in html
    assert "Wake Forest" not in html


def test_step3_css_keeps_purple_expanded_screenshot_style():
    assert ".gt168-step3:before" in step3.STEP3_CSS
    assert ".gt168-grid{display:grid" in step3.STEP3_CSS
    assert ".gt168-table" in step3.STEP3_CSS
    assert ".gt168-center-card" in step3.STEP3_CSS
    assert ".gt168-edge" in step3.STEP3_CSS
    assert "@media(max-width:920px)" in step3.STEP3_CSS



def test_step3_exact_id_schedule_fallback_fills_missing_recent_core(monkeypatch):
    identity = {
        "away": {"team": "Coastal Carolina", "team_id": "324", "logo": "https://example.test/324.png"},
        "home": {"team": "Delaware", "team_id": "48", "logo": "https://example.test/48.png"},
    }
    game = {
        "game_date": "2026-09-19",
        "espn_event_id": "401869940",
        "away_espn_team_id": "324",
        "home_espn_team_id": "48",
    }
    monkeypatch.setattr(step3.deep, "_season", lambda game: 2026)
    monkeypatch.setattr(step3.deep, "_cutoff", lambda game: object())

    rows = {
        "324": [
            {
                "event_id": "a1",
                "date": "2026-09-05T00:00:00Z",
                "opponent_name": "Opponent A",
                "opponent_id": "901",
                "location": "home",
                "points_for": 35,
                "points_against": 14,
                "opponent_record_pct": 0.50,
            },
            {
                "event_id": "a2",
                "date": "2026-09-12T00:00:00Z",
                "opponent_name": "Opponent B",
                "opponent_id": "902",
                "location": "away",
                "points_for": 28,
                "points_against": 24,
                "opponent_record_pct": 0.60,
            },
        ],
        "48": [
            {
                "event_id": "h1",
                "date": "2026-09-06T00:00:00Z",
                "opponent_name": "Opponent C",
                "opponent_id": "903",
                "location": "home",
                "points_for": 31,
                "points_against": 10,
                "opponent_record_pct": 0.45,
            },
            {
                "event_id": "h2",
                "date": "2026-09-13T00:00:00Z",
                "opponent_name": "Opponent D",
                "opponent_id": "904",
                "location": "home",
                "points_for": 21,
                "points_against": 24,
                "opponent_record_pct": 0.70,
            },
        ],
    }
    monkeypatch.setattr(
        step3.deep.history_engine,
        "_fetch_team_schedule",
        lambda team_id, season: (
            {"team_id": team_id, "events": ["fixture"]},
            [{"provider": "exact schedule"}],
        ),
    )
    monkeypatch.setattr(
        step3.deep.form_engine,
        "_current_season_rows",
        lambda payload, team_id, season, cutoff, event_id: list(reversed(rows[team_id])),
    )

    away, home, diag = step3.enrich_step3_inputs(
        identity,
        {"team": "Coastal Carolina"},
        {"team": "Delaware"},
        game,
    )
    contract = step3.build_step3_contract(identity, away, home)
    assert contract["state"] == "CHECK"
    assert contract["away"]["sample_games"] == 2
    assert contract["home"]["sample_games"] == 2
    assert contract["away"]["last5_record"] == "2-0"
    assert contract["home"]["last5_record"] == "1-1"
    assert contract["away"]["required_complete"] is True
    assert contract["home"]["required_complete"] is True
    assert diag["away"]["fallback_used"] is True
    assert diag["home"]["fallback_used"] is True
    assert diag["away"]["opponent_record_mode"] == "inline_only"
    assert diag["home"]["opponent_record_mode"] == "inline_only"



def test_step3_lightweight_fallback_does_not_call_heavy_opponent_hydration(monkeypatch):
    identity = {
        "away": {"team": "Away", "team_id": "324"},
        "home": {"team": "Home", "team_id": "48"},
    }
    game = {
        "game_date": "2026-09-19",
        "espn_event_id": "401869940",
        "away_espn_team_id": "324",
        "home_espn_team_id": "48",
    }
    monkeypatch.setattr(step3.deep, "_season", lambda game: 2026)
    monkeypatch.setattr(step3.deep, "_cutoff", lambda game: object())
    monkeypatch.setattr(
        step3.deep.history_engine,
        "_fetch_team_schedule",
        lambda team_id, season: ({"events": []}, [{"provider": "schedule"}]),
    )
    monkeypatch.setattr(
        step3.deep.form_engine,
        "_current_season_rows",
        lambda payload, team_id, season, cutoff, event_id: [],
    )
    monkeypatch.setattr(
        step3.deep,
        "_current_rows",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("heavy fallback must not run")),
    )

    away, home, diag = step3.enrich_step3_inputs(
        identity,
        {"team": "Away"},
        {"team": "Home"},
        game,
    )
    assert away["team"] == "Away"
    assert home["team"] == "Home"
    assert diag["away"]["rows"] == 0
    assert diag["home"]["rows"] == 0
