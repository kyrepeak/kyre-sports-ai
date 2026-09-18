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



def test_step3_runtime_snapshot_fills_form_and_opponent_quality_to_ready(monkeypatch):
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
    payload = {
        "version": 2,
        "generated_at": "2026-09-18T18:28:25Z",
        "_runtime_snapshot_source": "remote:cfb-runtime-snapshot-auto-refresh-v2",
        "games": [
            {
                "event_id": "401869940",
                "game_date": "2026-09-19",
                "away_team": "Coastal Carolina",
                "home_team": "Delaware",
                "away": {
                    "team_id": "324",
                    "record_text": "1-1",
                    "points_allowed_pg": 19.0,
                    "completed_games": [
                        {
                            "event_id": "a1",
                            "date": "2026-09-05T00:00:00Z",
                            "opponent": "Opponent A",
                            "opponent_id": "901",
                            "location": "away",
                            "points_for": 24,
                            "points_against": 31,
                        },
                        {
                            "event_id": "a2",
                            "date": "2026-09-12T00:00:00Z",
                            "opponent": "Opponent B",
                            "opponent_id": "902",
                            "location": "home",
                            "points_for": 45,
                            "points_against": 7,
                        },
                    ],
                },
                "home": {
                    "team_id": "48",
                    "record_text": "1-1",
                    "points_allowed_pg": 21.0,
                    "completed_games": [
                        {
                            "event_id": "h1",
                            "date": "2026-09-03T00:00:00Z",
                            "opponent": "Opponent C",
                            "opponent_id": "903",
                            "location": "home",
                            "points_for": 42,
                            "points_against": 7,
                        },
                        {
                            "event_id": "h2",
                            "date": "2026-09-12T00:00:00Z",
                            "opponent": "Opponent D",
                            "opponent_id": "904",
                            "location": "away",
                            "points_for": 26,
                            "points_against": 35,
                        },
                    ],
                },
            },
            {
                "event_id": "opponents-1",
                "game_date": "2026-09-19",
                "away_team": "Opponent A",
                "home_team": "Opponent B",
                "away": {
                    "team_id": "901",
                    "record_text": "2-0",
                    "points_allowed_pg": 10.0,
                    "completed_games": [],
                },
                "home": {
                    "team_id": "902",
                    "record_text": "1-1",
                    "points_allowed_pg": 20.0,
                    "completed_games": [],
                },
            },
            {
                "event_id": "opponents-2",
                "game_date": "2026-09-19",
                "away_team": "Opponent C",
                "home_team": "Opponent D",
                "away": {
                    "team_id": "903",
                    "record_text": "3-0",
                    "points_allowed_pg": 7.0,
                    "completed_games": [],
                },
                "home": {
                    "team_id": "904",
                    "record_text": "0-2",
                    "points_allowed_pg": 40.0,
                    "completed_games": [],
                },
            },
        ],
    }
    monkeypatch.setattr(
        step3.runtime_snapshot,
        "_load_v2_snapshot",
        lambda: payload,
    )

    away, home, diag = step3.enrich_step3_inputs(
        identity,
        {"team": "Coastal Carolina"},
        {"team": "Delaware"},
        game,
    )
    contract = step3.build_step3_contract(identity, away, home)

    assert contract["state"] == "READY"
    assert contract["away"]["sample_games"] == 2
    assert contract["home"]["sample_games"] == 2
    assert contract["away"]["last5_record"] == "1-1"
    assert contract["home"]["last5_record"] == "1-1"
    assert contract["away"]["sos_coverage"] == 1.0
    assert contract["home"]["sos_coverage"] == 1.0
    assert contract["away"]["avg_opponent_win_pct"] == 0.75
    assert contract["home"]["avg_opponent_win_pct"] == 0.5
    assert contract["away"]["avg_opponent_def_rank"] is not None
    assert contract["home"]["avg_opponent_def_rank"] is not None
    assert contract["away"]["top40_defenses_faced"] is not None
    assert contract["home"]["top40_defenses_faced"] is not None
    assert contract["away"]["record_vs_winning_teams"] == "0-1"
    assert contract["home"]["record_vs_winning_teams"] == "1-0"
    assert contract["away"]["strength_of_schedule_rank"] == 1
    assert contract["home"]["strength_of_schedule_rank"] == 2
    assert diag["away"]["fallback_used"] is True
    assert diag["home"]["fallback_used"] is True
    assert diag["away"]["provider"] == "remote:cfb-runtime-snapshot-auto-refresh-v2"


def test_step3_one_game_is_not_enough_for_ready():
    identity = {
        "away": {"team": "A"},
        "home": {"team": "B"},
    }
    one = {
        "team": "A",
        "completed_games": [
            {
                "date": "2026-09-12",
                "opponent": "X",
                "result": "W",
                "points_for": 30,
                "points_against": 20,
                "opponent_record_pct": 0.75,
                "opponent_def_rank": 12,
            }
        ],
        "recent_record": {"wins": 1, "losses": 0, "ties": 0, "games": 1},
        "recent_ppg": 30.0,
        "recent_points_allowed_pg": 20.0,
        "recent_point_diff_pg": 10.0,
        "sos_opponent_win_pct": 0.75,
        "sos_coverage": 1.0,
        "strength_of_schedule_rank": 10,
    }
    row = step3.build_team_form_contract(one, identity["away"], side="away")
    assert row["state"] == "DATA LIMITED"
    assert "sample_games" in row["missing_required"]

