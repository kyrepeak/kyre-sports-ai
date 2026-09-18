from __future__ import annotations

import json

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



def _stub_quality_sources(monkeypatch, *, record_pct=0.50):
    monkeypatch.setattr(
        step3,
        "_runtime_v2_step3_bundle",
        lambda game, target_day: ({}, {"source": "test_disabled"}),
    )
    monkeypatch.setattr(
        step3,
        "_candidate_game_days",
        lambda team_name, team_slug, target_day, season: ([], []),
    )
    monkeypatch.setattr(
        step3,
        "_scoreboard_rows_for_team",
        lambda team_id, game_days: ([], []),
    )
    monkeypatch.setattr(
        step3,
        "_scoreboard_range_rows_for_team",
        lambda team_id, target_day: ([], []),
    )
    monkeypatch.setattr(
        step3,
        "_scoreboard_quality_universe",
        lambda target_day: ({}, {"attempts": []}),
    )
    monkeypatch.setattr(
        step3,
        "_opponent_defense_rank_map",
        lambda names: ({}, {"requested": len(names), "resolved": 0, "attempts": []}),
    )
    monkeypatch.setattr(
        step3,
        "_strength_of_schedule_rank_map",
        lambda target_day: ({}, {"ranked_teams": 0, "attempts": []}),
    )
    monkeypatch.setattr(
        step3.deep.form_engine,
        "_hydrate_opponent_records",
        lambda rows, season, cutoff, excluded_event_id="": (
            [
                {
                    **dict(row),
                    "opponent_record_pct": (
                        row.get("opponent_record_pct")
                        if row.get("opponent_record_pct") is not None
                        else record_pct
                    ),
                }
                for row in rows
            ],
            {
                "inline_records": sum(
                    row.get("opponent_record_pct") is not None for row in rows
                ),
                "fallback_requested": sum(
                    row.get("opponent_record_pct") is None for row in rows
                ),
                "fallback_resolved": sum(
                    row.get("opponent_record_pct") is None for row in rows
                ),
                "attempts": [],
            },
        ),
    )

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
    _stub_quality_sources(monkeypatch)
    monkeypatch.setattr(step3, "_snapshot_rows_for_team", lambda team_id, target_day: [])
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
    assert diag["away"]["refresh_used"] is True
    assert diag["home"]["refresh_used"] is True
    assert diag["away"]["fallback_used"] is False
    assert diag["home"]["fallback_used"] is False
    assert diag["away"]["source"] == "live_exact_schedule"
    assert diag["home"]["source"] == "live_exact_schedule"



def test_step3_lightweight_fallback_does_not_call_heavy_opponent_hydration(monkeypatch):
    _stub_quality_sources(monkeypatch)
    monkeypatch.setattr(step3, "_snapshot_rows_for_team", lambda team_id, target_day: [])
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



def test_step3_checked_in_snapshot_fills_core_only_when_live_refresh_fails(monkeypatch, tmp_path):
    _stub_quality_sources(monkeypatch)
    snapshot = {
        "games": [
            {
                "event_id": "401868008",
                "game_date": "2026-09-12",
                "away_team": "Fordham",
                "home_team": "Coastal Carolina",
                "away": {"team_id": "2230", "completed_games": []},
                "home": {
                    "team_id": "324",
                    "completed_games": [
                        {
                            "event_id": "401856780",
                            "date": "2026-09-05T16:00Z",
                            "location": "away",
                            "points_for": 24,
                            "points_against": 31,
                            "opponent": "West Virginia Mountaineers",
                            "opponent_id": "277",
                        }
                    ],
                },
            },
            {
                "event_id": "401856684",
                "game_date": "2026-09-12",
                "away_team": "Delaware",
                "home_team": "Vanderbilt",
                "away": {
                    "team_id": "48",
                    "completed_games": [
                        {
                            "event_id": "401864424",
                            "date": "2026-09-03T23:00Z",
                            "location": "home",
                            "points_for": 42,
                            "points_against": 7,
                            "opponent": "Merrimack Warriors",
                            "opponent_id": "2771",
                        }
                    ],
                },
                "home": {"team_id": "238", "completed_games": []},
            },
        ]
    }
    snapshot_path = tmp_path / "cfb_runtime_snapshot_v2.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(step3, "STEP3_RUNTIME_SNAPSHOT_PATH", snapshot_path)
    monkeypatch.setattr(
        step3.deep.history_engine,
        "_fetch_team_schedule",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError("live schedule unavailable")
        ),
    )

    identity = {
        "away": {"team": "Coastal Carolina", "team_id": "324"},
        "home": {"team": "Delaware", "team_id": "48"},
    }
    game = {
        "game_date": "2026-09-19",
        "espn_event_id": "401869940",
        "away_espn_team_id": "324",
        "home_espn_team_id": "48",
    }

    away, home, diag = step3.enrich_step3_inputs(
        identity,
        {"team": "Coastal Carolina"},
        {"team": "Delaware"},
        game,
    )
    contract = step3.build_step3_contract(identity, away, home)

    assert contract["state"] == "CHECK"
    assert contract["away"]["sample_games"] == 1
    assert contract["home"]["sample_games"] == 1
    assert contract["away"]["last5_record"] == "0-1"
    assert contract["home"]["last5_record"] == "1-0"
    assert contract["away"]["recent_ppg"] == 24.0
    assert contract["home"]["recent_ppg"] == 42.0
    assert diag["away"]["source"] == "checked_in_runtime_snapshot"
    assert diag["home"]["source"] == "checked_in_runtime_snapshot"
    assert diag["away"]["fallback_used"] is True
    assert diag["home"]["fallback_used"] is True


def test_step3_snapshot_filters_rows_on_or_after_target_day(monkeypatch, tmp_path):
    snapshot = {
        "games": [
            {
                "away": {
                    "team_id": "324",
                    "completed_games": [
                        {
                            "event_id": "old",
                            "date": "2026-09-05T16:00Z",
                            "points_for": 24,
                            "points_against": 31,
                            "opponent": "Old Opponent",
                        },
                        {
                            "event_id": "target",
                            "date": "2026-09-19T16:00Z",
                            "points_for": 99,
                            "points_against": 0,
                            "opponent": "Future Opponent",
                        },
                    ],
                },
                "home": {},
            }
        ]
    }
    snapshot_path = tmp_path / "cfb_runtime_snapshot_v2.json"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    monkeypatch.setattr(step3, "STEP3_RUNTIME_SNAPSHOT_PATH", snapshot_path)

    rows = step3._snapshot_rows_for_team("324", "2026-09-19")
    assert [row["event_id"] for row in rows] == ["old"]



def test_step3_live_schedule_refreshes_even_when_existing_core_looks_complete(monkeypatch):
    _stub_quality_sources(monkeypatch)
    identity = {
        "away": {"team": "Miami (FL)", "team_id": "2390"},
        "home": {"team": "Wake Forest", "team_id": "154"},
    }
    game = {
        "game_date": "2026-09-18",
        "espn_event_id": "target",
        "away_espn_team_id": "2390",
        "home_espn_team_id": "154",
    }
    stale_away = {
        "team": "Miami (FL)",
        "completed_games": [
            {
                "event_id": "mia1",
                "date": "2026-09-05T01:00:00Z",
                "opponent": "Stanford Cardinal",
                "points_for": 45,
                "points_against": 6,
                "result": "W",
            }
        ],
        "recent_record": {"wins": 1, "losses": 0, "games": 1},
        "recent_ppg": 45.0,
        "recent_points_allowed_pg": 6.0,
        "recent_point_diff_pg": 39.0,
    }
    stale_home = {
        "team": "Wake Forest",
        "completed_games": [
            {
                "event_id": "wf1",
                "date": "2026-09-03T23:00:00Z",
                "opponent": "Akron Zips",
                "points_for": 38,
                "points_against": 16,
                "result": "W",
            }
        ],
        "recent_record": {"wins": 1, "losses": 0, "games": 1},
        "recent_ppg": 38.0,
        "recent_points_allowed_pg": 16.0,
        "recent_point_diff_pg": 22.0,
    }
    rows = {
        "2390": [
            {
                "event_id": "mia1",
                "date": "2026-09-05T01:00:00Z",
                "opponent_name": "Stanford Cardinal",
                "opponent_id": "24",
                "points_for": 45,
                "points_against": 6,
            },
            {
                "event_id": "mia2",
                "date": "2026-09-10T23:30:00Z",
                "opponent_name": "Florida A&M Rattlers",
                "opponent_id": "50",
                "points_for": 42,
                "points_against": 14,
            },
        ],
        "154": [
            {
                "event_id": "wf1",
                "date": "2026-09-03T23:00:00Z",
                "opponent_name": "Akron Zips",
                "opponent_id": "2006",
                "points_for": 38,
                "points_against": 16,
            },
            {
                "event_id": "wf2",
                "date": "2026-09-12T16:00:00Z",
                "opponent_name": "Purdue Boilermakers",
                "opponent_id": "2509",
                "points_for": 27,
                "points_against": 24,
            },
        ],
    }

    monkeypatch.setattr(step3.deep, "_season", lambda game: 2026)
    monkeypatch.setattr(step3.deep, "_cutoff", lambda game: object())
    monkeypatch.setattr(
        step3.deep.history_engine,
        "_fetch_team_schedule",
        lambda team_id, season: ({"team_id": team_id}, [{"provider": "exact schedule"}]),
    )
    monkeypatch.setattr(
        step3.deep.form_engine,
        "_current_season_rows",
        lambda payload, team_id, season, cutoff, event_id: list(rows[team_id]),
    )

    away, home, diag = step3.enrich_step3_inputs(
        identity,
        stale_away,
        stale_home,
        game,
    )
    contract = step3.build_step3_contract(identity, away, home)

    assert contract["away"]["sample_games"] == 2
    assert contract["home"]["sample_games"] == 2
    assert contract["away"]["last5_record"] == "2-0"
    assert contract["home"]["last5_record"] == "2-0"
    assert round(contract["away"]["recent_ppg"], 1) == 43.5
    assert round(contract["home"]["recent_ppg"], 1) == 32.5
    assert diag["away"]["refresh_used"] is True
    assert diag["home"]["refresh_used"] is True
    assert diag["away"]["source"] == "live_exact_schedule"
    assert diag["home"]["source"] == "live_exact_schedule"



def test_step3_opponent_quality_populates_all_five_rows(monkeypatch):
    _stub_quality_sources(monkeypatch)
    identity = {
        "away": {"team": "Miami (FL)", "team_id": "2390"},
        "home": {"team": "Wake Forest", "team_id": "154"},
    }
    game = {
        "game_date": "2026-09-18",
        "espn_event_id": "target",
        "away_espn_team_id": "2390",
        "home_espn_team_id": "154",
    }
    rows = {
        "2390": [
            {
                "event_id": "mia1",
                "date": "2026-09-05T01:00:00Z",
                "opponent_name": "Stanford Cardinal",
                "opponent_id": "24",
                "points_for": 45,
                "points_against": 6,
            },
            {
                "event_id": "mia2",
                "date": "2026-09-10T23:30:00Z",
                "opponent_name": "Florida A&M Rattlers",
                "opponent_id": "50",
                "points_for": 42,
                "points_against": 14,
            },
        ],
        "154": [
            {
                "event_id": "wf1",
                "date": "2026-09-03T23:00:00Z",
                "opponent_name": "Akron Zips",
                "opponent_id": "2006",
                "points_for": 38,
                "points_against": 16,
            },
            {
                "event_id": "wf2",
                "date": "2026-09-12T16:00:00Z",
                "opponent_name": "Purdue Boilermakers",
                "opponent_id": "2509",
                "points_for": 27,
                "points_against": 24,
            },
        ],
    }
    pcts = {
        "24": 0.67,
        "50": 0.25,
        "2006": 0.50,
        "2509": 0.75,
    }
    monkeypatch.setattr(step3.deep, "_season", lambda game: 2026)
    monkeypatch.setattr(step3.deep, "_cutoff", lambda game: object())
    monkeypatch.setattr(
        step3.deep.history_engine,
        "_fetch_team_schedule",
        lambda team_id, season: ({"team_id": team_id}, [{"provider": "exact schedule"}]),
    )
    monkeypatch.setattr(
        step3.deep.form_engine,
        "_current_season_rows",
        lambda payload, team_id, season, cutoff, event_id: list(rows[team_id]),
    )
    monkeypatch.setattr(
        step3.deep.form_engine,
        "_hydrate_opponent_records",
        lambda recent, season, cutoff, excluded_event_id="": (
            [
                {**dict(row), "opponent_record_pct": pcts[row["opponent_id"]]}
                for row in recent
            ],
            {
                "inline_records": 0,
                "fallback_requested": len(recent),
                "fallback_resolved": len(recent),
                "attempts": [],
            },
        ),
    )
    defense = {
        step3.ncaa_team_data._canonical_name("Stanford Cardinal"): 18,
        step3.ncaa_team_data._canonical_name("Florida A&M Rattlers"): 64,
        step3.ncaa_team_data._canonical_name("Akron Zips"): 92,
        step3.ncaa_team_data._canonical_name("Purdue Boilermakers"): 27,
    }
    monkeypatch.setattr(
        step3,
        "_opponent_defense_rank_map",
        lambda names: (
            defense,
            {"requested": 4, "resolved": 4, "attempts": []},
        ),
    )
    monkeypatch.setattr(
        step3,
        "_strength_of_schedule_rank_map",
        lambda target_day: (
            {
                step3.ncaa_team_data._canonical_name("Miami (FL)"): 41,
                step3.ncaa_team_data._canonical_name("Wake Forest"): 24,
            },
            {"ranked_teams": 2, "attempts": []},
        ),
    )

    away, home, _ = step3.enrich_step3_inputs(
        identity,
        {"team": "Miami (FL)"},
        {"team": "Wake Forest"},
        game,
    )
    contract = step3.build_step3_contract(identity, away, home)

    assert contract["away"]["avg_opponent_win_pct"] == 0.46
    assert contract["home"]["avg_opponent_win_pct"] == 0.625
    assert contract["away"]["avg_opponent_def_rank"] == 41.0
    assert contract["home"]["avg_opponent_def_rank"] == 59.5
    assert contract["away"]["top40_defenses_faced"] == 1
    assert contract["home"]["top40_defenses_faced"] == 1
    assert contract["away"]["record_vs_winning_teams"] == "1-0"
    assert contract["home"]["record_vs_winning_teams"] == "1-0"
    assert contract["away"]["strength_of_schedule_rank"] == 41
    assert contract["home"]["strength_of_schedule_rank"] == 24
    assert contract["state"] == "READY"



def test_step3_one_game_uses_early_season_sample_language():
    row = step3.build_team_form_contract(
        {
            "team": "Miami (FL)",
            "completed_games": [
                {
                    "date": "2026-09-05",
                    "opponent": "Stanford",
                    "result": "W",
                    "score": "45-6",
                }
            ],
            "recent_ppg": 45.0,
            "recent_points_allowed_pg": 6.0,
            "recent_point_diff_pg": 39.0,
        },
        {"team": "Miami (FL)"},
        side="away",
    )
    assert row["trend_direction"] == "Early-season sample"
    assert row["trend_detail"] == "1 completed game"


def test_step3_two_games_remain_early_season_sample():
    row = step3.build_team_form_contract(
        {
            "team": "Wake Forest",
            "completed_games": [
                {
                    "date": "2026-09-03",
                    "opponent": "Akron",
                    "result": "W",
                    "score": "38-16",
                },
                {
                    "date": "2026-09-12",
                    "opponent": "Purdue",
                    "result": "W",
                    "score": "27-24",
                },
            ],
            "recent_ppg": 32.5,
            "recent_points_allowed_pg": 20.0,
            "recent_point_diff_pg": 12.5,
        },
        {"team": "Wake Forest"},
        side="home",
    )
    assert row["trend_direction"] == "Early-season sample"
    assert row["trend_detail"] == "2 completed games"


def test_step3_render_never_uses_insufficient_sample_wording():
    away = {
        "team": "Miami (FL)",
        "completed_games": [
            {"date": "2026-09-05", "opponent": "Stanford", "result": "W", "score": "45-6"}
        ],
        "recent_ppg": 45.0,
        "recent_points_allowed_pg": 6.0,
        "recent_point_diff_pg": 39.0,
    }
    home = {
        "team": "Wake Forest",
        "completed_games": [
            {"date": "2026-09-03", "opponent": "Akron", "result": "W", "score": "38-16"}
        ],
        "recent_ppg": 38.0,
        "recent_points_allowed_pg": 16.0,
        "recent_point_diff_pg": 22.0,
    }
    html = step3.render_step3_html("CHECK", _identity(), away, home)
    assert "Early-season sample" in html
    assert "1 completed game" in html
    assert "Insufficient sample" not in html



def test_step3_ready_requires_minimum_opponent_quality_coverage():
    evidence = _away()
    games = evidence["completed_games"]
    # Keep all summary scalars populated, but only one of five recent games
    # has opponent-record/defense-rank coverage.
    for idx, row in enumerate(games):
        row["opponent_record_pct"] = 0.60 if idx == 0 else None
        row["opponent_def_rank"] = 25 if idx == 0 else None
    evidence["sos_opponent_win_pct"] = 0.60
    evidence["sos_coverage"] = 0.20
    evidence["avg_opponent_def_rank"] = 25.0
    evidence["top40_defenses_faced"] = 1
    evidence["record_vs_winning_teams"] = "1-0"
    evidence["strength_of_schedule_rank"] = 40

    row = step3.build_team_form_contract(
        evidence,
        _identity()["away"],
        side="away",
    )
    assert row["required_complete"] is True
    assert row["opponent_record_coverage"] == 0.20
    assert row["opponent_defense_rank_coverage"] == 0.20
    assert row["opponent_quality_ready"] is False
    assert row["state"] == "CHECK"
    assert "below the 60% READY threshold" in row["status_reason"]


def test_step3_full_opponent_quality_coverage_is_ready():
    row = step3.build_team_form_contract(
        _away(),
        _identity()["away"],
        side="away",
    )
    assert row["opponent_record_coverage"] == 1.0
    assert row["opponent_defense_rank_coverage"] == 1.0
    assert row["opponent_quality_coverage"] == 1.0
    assert row["opponent_quality_ready"] is True
    assert row["state"] == "READY"
    assert "meet the Step 3 READY contract" in row["status_reason"]


def test_step3_status_reason_is_visible_when_checking():
    away = _away()
    for row in away["completed_games"]:
        row["opponent_record_pct"] = None
        row["opponent_def_rank"] = None
    away["sos_opponent_win_pct"] = None
    away["sos_coverage"] = 0.0
    away["avg_opponent_def_rank"] = None
    away["top40_defenses_faced"] = None
    away["record_vs_winning_teams"] = ""
    away["strength_of_schedule_rank"] = None

    html = step3.render_step3_html("CHECK", _identity(), away, _home())
    assert 'data-testid="gt168-step3-status-reason"' in html
    assert "CHECK — Opponent quality is still checking:" in html
    assert "Opponent-quality coverage 0%" in html


def test_step3_missing_core_remains_data_limited_with_reason():
    away = _away()
    away["completed_games"] = []
    away["recent_record"] = {}
    away["recent_ppg"] = None
    away["recent_points_allowed_pg"] = None
    away["recent_point_diff_pg"] = None
    row = step3.build_team_form_contract(
        away,
        _identity()["away"],
        side="away",
    )
    assert row["state"] == "DATA LIMITED"
    assert row["required_complete"] is False
    assert "Core recent-form evidence is incomplete" in row["status_reason"]



def test_step3_scoreboard_recovery_repairs_stale_one_game_miami_wake_sample(monkeypatch):
    _stub_quality_sources(monkeypatch)
    identity = {
        "away": {"team": "Miami (FL)", "team_id": "2390"},
        "home": {"team": "Wake Forest", "team_id": "154"},
    }
    game = {
        "game_date": "2026-09-18",
        "espn_event_id": "target",
        "away_espn_team_id": "2390",
        "home_espn_team_id": "154",
    }

    stale_rows = {
        "2390": [
            {
                "event_id": "mia-stanford",
                "date": "2026-09-05T01:00:00Z",
                "opponent_name": "Stanford Cardinal",
                "opponent_id": "24",
                "points_for": 45,
                "points_against": 6,
            }
        ],
        "154": [
            {
                "event_id": "wf-akron",
                "date": "2026-09-03T23:00:00Z",
                "opponent_name": "Akron Zips",
                "opponent_id": "2006",
                "points_for": 38,
                "points_against": 16,
            }
        ],
    }
    recovered = {
        "2390": [
            stale_rows["2390"][0],
            {
                "event_id": "mia-famu",
                "date": "2026-09-11T00:00:00Z",
                "opponent_name": "Florida A&M Rattlers",
                "opponent_id": "50",
                "points_for": 77,
                "points_against": 7,
            },
        ],
        "154": [
            stale_rows["154"][0],
            {
                "event_id": "wf-purdue",
                "date": "2026-09-12T16:00:00Z",
                "opponent_name": "Purdue Boilermakers",
                "opponent_id": "2509",
                "points_for": 38,
                "points_against": 36,
            },
        ],
    }

    monkeypatch.setattr(step3.deep, "_season", lambda game: 2026)
    monkeypatch.setattr(step3.deep, "_cutoff", lambda game: object())
    monkeypatch.setattr(
        step3.deep.history_engine,
        "_fetch_team_schedule",
        lambda team_id, season: ({"team_id": team_id}, [{"provider": "team schedule"}]),
    )
    monkeypatch.setattr(
        step3.deep.form_engine,
        "_current_season_rows",
        lambda payload, team_id, season, cutoff, event_id: list(stale_rows[team_id]),
    )
    monkeypatch.setattr(
        step3,
        "_candidate_game_days",
        lambda team_name, team_slug, target_day, season: (
            ["2026-09-04", "2026-09-10"]
            if "Miami" in team_name
            else ["2026-09-03", "2026-09-12"],
            [{"provider": "NCAA candidate dates"}],
        ),
    )
    monkeypatch.setattr(
        step3,
        "_scoreboard_rows_for_team",
        lambda team_id, game_days: (
            list(recovered[team_id]),
            [{"provider": "ESPN daily scoreboard"}],
        ),
    )

    away, home, diag = step3.enrich_step3_inputs(
        identity,
        {"team": "Miami (FL)"},
        {"team": "Wake Forest"},
        game,
    )
    contract = step3.build_step3_contract(identity, away, home)

    assert contract["away"]["sample_games"] == 2
    assert contract["home"]["sample_games"] == 2
    assert contract["away"]["last5_record"] == "2-0"
    assert contract["home"]["last5_record"] == "2-0"
    assert contract["away"]["recent_ppg"] == 61.0
    assert contract["away"]["recent_allowed_pg"] == 6.5
    assert contract["home"]["recent_ppg"] == 38.0
    assert contract["home"]["recent_allowed_pg"] == 26.0
    assert diag["away"]["team_schedule_rows"] == 1
    assert diag["away"]["scoreboard_rows"] == 2
    assert diag["home"]["team_schedule_rows"] == 1
    assert diag["home"]["scoreboard_rows"] == 2
    assert diag["away"]["source"] == "live_exact_schedule+daily_scoreboard"
    assert diag["home"]["source"] == "live_exact_schedule+daily_scoreboard"


def test_step3_candidate_dates_exclude_target_and_future_games(monkeypatch):
    class _DT:
        def __init__(self, day):
            self._day = day
        def astimezone(self, tz):
            return self
        def date(self):
            from datetime import date
            return date.fromisoformat(self._day)

    contests = [
        {"id": "old1"},
        {"id": "old2"},
        {"id": "target"},
        {"id": "future"},
    ]
    pairs = {
        "old1": (
            {"name": "Miami (FL)", "slug": "miami-fl"},
            {"name": "Stanford", "slug": "stanford"},
        ),
        "old2": (
            {"name": "Florida A&M", "slug": "florida-am"},
            {"name": "Miami (FL)", "slug": "miami-fl"},
        ),
        "target": (
            {"name": "Miami (FL)", "slug": "miami-fl"},
            {"name": "Wake Forest", "slug": "wake-forest"},
        ),
        "future": (
            {"name": "Central Michigan", "slug": "central-michigan"},
            {"name": "Miami (FL)", "slug": "miami-fl"},
        ),
    }
    days = {
        "old1": "2026-09-04",
        "old2": "2026-09-10",
        "target": "2026-09-18",
        "future": "2026-09-26",
    }

    monkeypatch.setattr(
        step3.ncaa_schedule,
        "_fetch_json_with_fallback",
        lambda *args, **kwargs: ({"ok": True}, [{"provider": "NCAA"}]),
    )
    monkeypatch.setattr(step3.ncaa_schedule, "_walk_contests", lambda payload: contests)
    monkeypatch.setattr(
        step3.ncaa_team_data,
        "_contest_teams",
        lambda contest: pairs[contest["id"]],
    )
    monkeypatch.setattr(
        step3.ncaa_schedule,
        "_contest_datetime",
        lambda contest: _DT(days[contest["id"]]),
    )

    found, _ = step3._candidate_game_days(
        "Miami (FL)",
        "miami-fl",
        "2026-09-18",
        2026,
    )
    assert found == ["2026-09-04", "2026-09-10"]



def test_step3_scoreboard_range_recovers_exact_team_across_fbs_and_fcs(monkeypatch):
    def _event(event_id, day, mine_id, opp_id, mine_score, opp_score):
        return {
            "id": event_id,
            "date": f"{day}T16:00:00Z",
            "status": {"type": {"completed": True, "name": "STATUS_FINAL"}},
            "competitions": [{
                "competitors": [
                    {
                        "homeAway": "home",
                        "score": str(mine_score),
                        "team": {
                            "id": mine_id,
                            "displayName": "Target Team",
                        },
                    },
                    {
                        "homeAway": "away",
                        "score": str(opp_score),
                        "team": {
                            "id": opp_id,
                            "displayName": "Opponent",
                        },
                    },
                ]
            }],
        }

    calls = []
    def fake_fetch(url, params, provider):
        calls.append(dict(params))
        group = str(params["groups"])
        if group == "80":
            return {
                "events": [
                    _event("g1", "2026-09-05", "324", "277", 24, 31),
                    # Exact-team filter must reject this unrelated completed game.
                    _event("other", "2026-09-06", "999", "998", 30, 20),
                ]
            }, [{"provider": provider}]
        return {
            "events": [
                _event("g2", "2026-09-12", "324", "2230", 45, 17),
            ]
        }, [{"provider": provider}]

    monkeypatch.setattr(step3.ncaa_schedule, "_fetch_json_with_fallback", fake_fetch)

    rows, attempts = step3._scoreboard_range_rows_for_team(
        "324",
        "2026-09-19",
    )

    assert [row["event_id"] for row in rows] == ["g1", "g2"]
    assert len(calls) >= 4
    assert {str(call["groups"]) for call in calls} == {"80", "81"}
    assert all(int(call["year"]) == 2026 for call in calls)
    assert all(int(call["seasontype"]) == 2 for call in calls)
    assert all("week" in call for call in calls)
    assert all(int(call["limit"]) == 1000 for call in calls)
    assert len(attempts) == len(calls)


def test_step3_range_recovery_wins_when_candidate_dates_are_empty(monkeypatch):
    _stub_quality_sources(monkeypatch)
    identity = {
        "away": {"team": "Miami (FL)", "team_id": "2390"},
        "home": {"team": "Wake Forest", "team_id": "154"},
    }
    game = {
        "game_date": "2026-09-18",
        "espn_event_id": "target",
        "away_espn_team_id": "2390",
        "home_espn_team_id": "154",
    }
    one_game = {
        "2390": [{
            "event_id": "mia1",
            "date": "2026-09-05T01:00:00Z",
            "opponent_name": "Stanford Cardinal",
            "opponent_id": "24",
            "points_for": 45,
            "points_against": 6,
        }],
        "154": [{
            "event_id": "wf1",
            "date": "2026-09-03T23:00:00Z",
            "opponent_name": "Akron Zips",
            "opponent_id": "2006",
            "points_for": 38,
            "points_against": 16,
        }],
    }
    recovered = {
        "2390": one_game["2390"] + [{
            "event_id": "mia2",
            "date": "2026-09-10T23:30:00Z",
            "opponent_name": "Florida A&M Rattlers",
            "opponent_id": "50",
            "points_for": 77,
            "points_against": 7,
        }],
        "154": one_game["154"] + [{
            "event_id": "wf2",
            "date": "2026-09-12T16:00:00Z",
            "opponent_name": "Purdue Boilermakers",
            "opponent_id": "2509",
            "points_for": 38,
            "points_against": 36,
        }],
    }

    monkeypatch.setattr(step3.deep, "_season", lambda game: 2026)
    monkeypatch.setattr(step3.deep, "_cutoff", lambda game: object())
    monkeypatch.setattr(
        step3.deep.history_engine,
        "_fetch_team_schedule",
        lambda team_id, season: ({"team_id": team_id}, []),
    )
    monkeypatch.setattr(
        step3.deep.form_engine,
        "_current_season_rows",
        lambda payload, team_id, season, cutoff, event_id: list(one_game[team_id]),
    )
    monkeypatch.setattr(
        step3,
        "_scoreboard_range_rows_for_team",
        lambda team_id, target_day: (list(recovered[team_id]), []),
    )

    away, home, diag = step3.enrich_step3_inputs(
        identity,
        {"team": "Miami (FL)"},
        {"team": "Wake Forest"},
        game,
    )
    contract = step3.build_step3_contract(identity, away, home)

    assert contract["away"]["sample_games"] == 2
    assert contract["home"]["sample_games"] == 2
    assert contract["away"]["last5_record"] == "2-0"
    assert contract["home"]["last5_record"] == "2-0"
    assert diag["away"]["scoreboard_range_rows"] == 2
    assert diag["home"]["scoreboard_range_rows"] == 2
    assert "scoreboard_range" in diag["away"]["source"]
    assert "scoreboard_range" in diag["home"]["source"]



def test_step3_scoreboard_quality_universe_builds_records_defense_and_sos(monkeypatch):
    def event(event_id, a_id, a_score, b_id, b_score):
        return {
            "id": event_id,
            "date": "2026-09-10T16:00:00Z",
            "status": {"type": {"completed": True}},
            "competitions": [{
                "competitors": [
                    {
                        "homeAway": "home",
                        "score": str(a_score),
                        "team": {"id": a_id, "displayName": f"Team {a_id}"},
                    },
                    {
                        "homeAway": "away",
                        "score": str(b_score),
                        "team": {"id": b_id, "displayName": f"Team {b_id}"},
                    },
                ]
            }],
        }

    events = [
        event("1", "100", 30, "200", 10),
        event("2", "100", 20, "300", 10),
        event("3", "200", 24, "400", 7),
        event("4", "400", 21, "300", 14),
    ]
    monkeypatch.setattr(
        step3,
        "_scoreboard_range_events",
        lambda target_day, lookback_days=70: (
            events,
            [{"provider": "range"}],
        ),
    )

    universe, diag = step3._scoreboard_quality_universe("2026-09-18")

    assert universe["records"]["100"] == 1.0
    assert universe["records"]["200"] == 0.5
    assert universe["records"]["300"] == 0.0
    assert universe["records"]["400"] == 0.5
    assert set(universe["defense_ranks"]) == {"100", "200", "300", "400"}
    assert set(universe["sos_ranks"]) == {"100", "200", "300", "400"}
    assert universe["event_count"] == 4
    assert diag["events"] == 4
    assert diag["teams"] == 4


def test_step3_scoreboard_quality_populates_all_required_opponent_rows():
    universe = {
        "records": {
            "200": 0.75,
            "300": 0.25,
            "100": 1.0,
        },
        "defense_ranks": {
            "200": 12,
            "300": 55,
            "100": 3,
        },
        "sos_values": {"100": 0.50},
        "sos_ranks": {"100": 24},
    }
    evidence = {
        "team": "Target",
        "completed_games": [
            {
                "date": "2026-09-05",
                "opponent": "Opponent 200",
                "opponent_id": "200",
                "result": "W",
                "points_for": 35,
                "points_against": 14,
            },
            {
                "date": "2026-09-12",
                "opponent": "Opponent 300",
                "opponent_id": "300",
                "result": "W",
                "points_for": 28,
                "points_against": 17,
            },
        ],
    }

    hydrated = step3._apply_scoreboard_quality(evidence, "100", universe)
    row = step3.build_team_form_contract(
        hydrated,
        {"team": "Target"},
        side="away",
    )

    assert row["sample_games"] == 2
    assert row["avg_opponent_win_pct"] == 0.50
    assert row["avg_opponent_def_rank"] == 33.5
    assert row["top40_defenses_faced"] == 1
    assert row["record_vs_winning_teams"] == "1-0"
    assert row["strength_of_schedule_rank"] == 24
    assert row["opponent_record_coverage"] == 1.0
    assert row["opponent_defense_rank_coverage"] == 1.0
    assert row["state"] == "READY"


def test_step3_scoreboard_range_events_queries_explicit_fbs_and_fcs_weeks(monkeypatch):
    calls = []

    def fake_fetch(url, params, provider):
        calls.append(dict(params))
        return {"events": []}, [{"provider": provider}]

    monkeypatch.setattr(
        step3.ncaa_schedule,
        "_fetch_json_with_fallback",
        fake_fetch,
    )
    try:
        step3._scoreboard_range_events.clear()
    except Exception:
        pass

    events, attempts = step3._scoreboard_range_events(
        "2026-10-02",
        lookback_days=70,
    )

    assert events == []
    assert len(calls) >= 4
    assert {str(call["groups"]) for call in calls} == {"80", "81"}
    assert all(int(call["year"]) == 2026 for call in calls)
    assert all(int(call["seasontype"]) == 2 for call in calls)
    assert all(isinstance(call["week"], int) for call in calls)
    assert all(int(call["limit"]) == 1000 for call in calls)
    assert len(attempts) == len(calls)



def test_step3_merges_ncaa_fbs_fcs_crossovers_without_duplicates():
    tg = step3.ncaa_team_data.TeamGame
    fbs_ledgers = {
        "coastalcarolina": [
            tg("2026-09-05", "West Virginia", "west-virginia", "away", 24, 31, "L", -7),
        ],
        "delaware": [
            tg("2026-09-12", "Vanderbilt", "vanderbilt", "away", 26, 35, "L", -9),
        ],
    }
    fcs_ledgers = {
        "coastalcarolina": [
            tg("2026-09-12", "Fordham", "fordham", "home", 45, 7, "W", 38),
        ],
        "delaware": [
            tg("2026-09-03", "Merrimack", "merrimack", "home", 42, 7, "W", 35),
            # Duplicate crossover row must not be doubled.
            tg("2026-09-12", "Vanderbilt", "vanderbilt", "away", 26, 35, "L", -9),
        ],
    }

    ledgers, meta = step3._merge_ncaa_ledgers(
        (fbs_ledgers, {
            "coastalcarolina": {"team": "Coastal Carolina", "team_slug": "coastal-carolina"},
            "delaware": {"team": "Delaware", "team_slug": "delaware"},
        }),
        (fcs_ledgers, {}),
    )

    assert len(ledgers["coastalcarolina"]) == 2
    assert len(ledgers["delaware"]) == 2
    assert [g.opponent for g in ledgers["coastalcarolina"]] == [
        "West Virginia",
        "Fordham",
    ]
    assert [g.opponent for g in ledgers["delaware"]] == [
        "Merrimack",
        "Vanderbilt",
    ]
    assert meta["coastalcarolina"]["team"] == "Coastal Carolina"


def test_step3_ncaa_evidence_builds_ready_two_game_profiles():
    tg = step3.ncaa_team_data.TeamGame
    universe = {
        "ledgers": {
            "coastalcarolina": [
                tg("2026-09-05", "West Virginia", "west-virginia", "away", 24, 31, "L", -7),
                tg("2026-09-12", "Fordham", "fordham", "home", 45, 7, "W", 38),
            ],
            "delaware": [
                tg("2026-09-03", "Merrimack", "merrimack", "home", 42, 7, "W", 35),
                tg("2026-09-12", "Vanderbilt", "vanderbilt", "away", 26, 35, "L", -9),
            ],
        },
        "meta": {
            "coastalcarolina": {
                "team": "Coastal Carolina",
                "team_slug": "coastal-carolina",
                "conference": "Sun Belt",
            },
            "delaware": {
                "team": "Delaware",
                "team_slug": "delaware",
                "conference": "CUSA",
            },
        },
        "records": {
            "westvirginia": 0.50,
            "fordham": 1.00,
            "merrimack": 0.00,
            "vanderbilt": 1.00,
        },
        "defense_ranks": {
            "westvirginia": 38,
            "fordham": 92,
            "merrimack": 110,
            "vanderbilt": 24,
        },
        "sos_ranks": {
            "coastalcarolina": 61,
            "delaware": 49,
        },
    }

    away = step3._ncaa_step3_evidence(
        "Coastal Carolina",
        "coastal-carolina",
        universe,
    )
    home = step3._ncaa_step3_evidence(
        "Delaware",
        "delaware",
        universe,
    )
    identity = {
        "away": {"team": "Coastal Carolina"},
        "home": {"team": "Delaware"},
    }
    contract = step3.build_step3_contract(identity, away, home)

    assert contract["state"] == "READY"
    assert contract["away"]["sample_games"] == 2
    assert contract["home"]["sample_games"] == 2
    assert contract["away"]["last5_record"] == "1-1"
    assert contract["home"]["last5_record"] == "1-1"
    assert contract["away"]["top40_defenses_faced"] == 1
    assert contract["home"]["top40_defenses_faced"] == 1
    assert contract["away"]["strength_of_schedule_rank"] == 61
    assert contract["home"]["strength_of_schedule_rank"] == 49
    assert contract["away"]["opponent_quality_ready"] is True
    assert contract["home"]["opponent_quality_ready"] is True


def test_step3_ncaa_ready_short_circuits_blocked_espn(monkeypatch):
    monkeypatch.setattr(
        step3,
        "_runtime_v2_step3_bundle",
        lambda game, target_day: ({}, {"source": "test_disabled"}),
    )
    tg = step3.ncaa_team_data.TeamGame
    universe = {
        "ledgers": {
            "coastalcarolina": [
                tg("2026-09-05", "West Virginia", "west-virginia", "away", 24, 31, "L", -7),
                tg("2026-09-12", "Fordham", "fordham", "home", 45, 7, "W", 38),
            ],
            "delaware": [
                tg("2026-09-03", "Merrimack", "merrimack", "home", 42, 7, "W", 35),
                tg("2026-09-12", "Vanderbilt", "vanderbilt", "away", 26, 35, "L", -9),
            ],
        },
        "meta": {
            "coastalcarolina": {"team": "Coastal Carolina", "team_slug": "coastal-carolina"},
            "delaware": {"team": "Delaware", "team_slug": "delaware"},
        },
        "records": {
            "westvirginia": 0.50,
            "fordham": 1.00,
            "merrimack": 0.00,
            "vanderbilt": 1.00,
        },
        "defense_ranks": {
            "westvirginia": 38,
            "fordham": 92,
            "merrimack": 110,
            "vanderbilt": 24,
        },
        "sos_ranks": {
            "coastalcarolina": 61,
            "delaware": 49,
        },
    }
    monkeypatch.setattr(
        step3,
        "_ncaa_combined_step3_universe",
        lambda target_day, season: (
            universe,
            {
                "strict_day": "2026-09-18",
                "fbs": {"teams": 130, "completed_contests": 100},
                "fcs": {"teams": 120, "completed_contests": 90},
                "combined_teams": 250,
                "attempts": [],
            },
        ),
    )
    monkeypatch.setattr(
        step3.deep.history_engine,
        "_fetch_team_schedule",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("ESPN must not run after NCAA Step 3 reaches READY")
        ),
    )
    monkeypatch.setattr(step3.deep, "_season", lambda game: 2026)
    monkeypatch.setattr(step3.deep, "_cutoff", lambda game: object())

    identity = {
        "away": {"team": "Coastal Carolina", "team_id": "324"},
        "home": {"team": "Delaware", "team_id": "48"},
    }
    game = {
        "game_date": "2026-09-19",
        "away_team": "Coastal Carolina",
        "away_team_slug": "coastal-carolina",
        "home_team": "Delaware",
        "home_team_slug": "delaware",
        "away_espn_team_id": "324",
        "home_espn_team_id": "48",
    }

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
    assert diag["away"]["source"] == "ncaa_combined_fbs_fcs"
    assert diag["home"]["source"] == "ncaa_combined_fbs_fcs"
    assert diag["away"]["ncaa_contract_state"] == "READY"
    assert diag["home"]["ncaa_contract_state"] == "READY"



def _runtime_v2_test_payload():
    def side(team_id, team, record_text, completed):
        return {
            "team_id": str(team_id),
            "record_text": record_text,
            "completed_games": completed,
        }

    coastal_games = [
        {
            "event_id": "cc-wvu",
            "date": "2026-09-05T16:00Z",
            "location": "away",
            "points_for": 24,
            "points_against": 31,
            "opponent": "West Virginia Mountaineers",
            "opponent_id": "277",
        },
        {
            "event_id": "cc-fordham",
            "date": "2026-09-12T23:30Z",
            "location": "home",
            "points_for": 45,
            "points_against": 7,
            "opponent": "Fordham Rams",
            "opponent_id": "2230",
        },
        {
            "event_id": "cc-target-day-leak",
            "date": "2026-09-19T12:00Z",
            "location": "home",
            "points_for": 99,
            "points_against": 0,
            "opponent": "Future Leak",
            "opponent_id": "9999",
        },
    ]
    delaware_games = [
        {
            "event_id": "del-merrimack",
            "date": "2026-09-03T23:00Z",
            "location": "home",
            "points_for": 42,
            "points_against": 7,
            "opponent": "Merrimack Warriors",
            "opponent_id": "2771",
        },
        {
            "event_id": "del-vandy",
            "date": "2026-09-12T20:15Z",
            "location": "away",
            "points_for": 26,
            "points_against": 35,
            "opponent": "Vanderbilt Commodores",
            "opponent_id": "238",
        },
    ]

    return {
        "version": 2,
        "generated_at": "2026-09-18T18:28:25Z",
        "window": {"start": "2026-09-17", "end": "2026-09-24"},
        "_runtime_snapshot_source": "certified-runtime-branch",
        "games": [
            {
                "event_id": "401869940",
                "game_date": "2026-09-19",
                "away_team": "Coastal Carolina",
                "home_team": "Delaware",
                "away": side("324", "Coastal Carolina", "1-1", coastal_games),
                "home": side("48", "Delaware", "1-1", delaware_games),
            },
            {
                "event_id": "wvu-next",
                "game_date": "2026-09-20",
                "away_team": "West Virginia",
                "home_team": "Dummy A",
                "away": side(
                    "277",
                    "West Virginia",
                    "2-0",
                    [
                        {
                            "event_id": "wvu-1",
                            "date": "2026-09-05T16:00Z",
                            "points_for": 31,
                            "points_against": 24,
                            "opponent": "Coastal Carolina",
                            "opponent_id": "324",
                        },
                        {
                            "event_id": "wvu-2",
                            "date": "2026-09-12T17:00Z",
                            "points_for": 52,
                            "points_against": 7,
                            "opponent": "UT Martin",
                            "opponent_id": "2630",
                        },
                    ],
                ),
                "home": side(
                    "9001",
                    "Dummy A",
                    "1-1",
                    [
                        {"date": "2026-09-05", "points_for": 20, "points_against": 10, "opponent_id": "9002"},
                        {"date": "2026-09-12", "points_for": 7, "points_against": 17, "opponent_id": "9003"},
                    ],
                ),
            },
            {
                "event_id": "fordham-next",
                "game_date": "2026-09-20",
                "away_team": "Fordham",
                "home_team": "Dummy B",
                "away": side(
                    "2230",
                    "Fordham",
                    "0-2",
                    [
                        {"date": "2026-09-05", "points_for": 0, "points_against": 38, "opponent_id": "2449"},
                        {"date": "2026-09-12", "points_for": 7, "points_against": 45, "opponent_id": "324"},
                    ],
                ),
                "home": side(
                    "9002",
                    "Dummy B",
                    "1-0",
                    [{"date": "2026-09-06", "points_for": 17, "points_against": 10, "opponent_id": "9001"}],
                ),
            },
            {
                "event_id": "merrimack-next",
                "game_date": "2026-09-20",
                "away_team": "Merrimack",
                "home_team": "Dummy C",
                "away": side(
                    "2771",
                    "Merrimack",
                    "1-1",
                    [
                        {"date": "2026-09-03", "points_for": 7, "points_against": 42, "opponent_id": "48"},
                        {"date": "2026-09-12", "points_for": 23, "points_against": 14, "opponent_id": "311"},
                    ],
                ),
                "home": side(
                    "9003",
                    "Dummy C",
                    "0-1",
                    [{"date": "2026-09-07", "points_for": 3, "points_against": 21, "opponent_id": "9002"}],
                ),
            },
            {
                "event_id": "vandy-next",
                "game_date": "2026-09-20",
                "away_team": "Vanderbilt",
                "home_team": "Dummy D",
                "away": side(
                    "238",
                    "Vanderbilt",
                    "2-0",
                    [
                        {"date": "2026-09-05", "points_for": 28, "points_against": 9, "opponent_id": "2046"},
                        {"date": "2026-09-12", "points_for": 35, "points_against": 26, "opponent_id": "48"},
                    ],
                ),
                "home": side(
                    "9004",
                    "Dummy D",
                    "0-1",
                    [{"date": "2026-09-08", "points_for": 10, "points_against": 24, "opponent_id": "9001"}],
                ),
            },
        ],
    }


def test_step3_runtime_v2_bundle_filters_target_day_and_reaches_ready(monkeypatch):
    payload = _runtime_v2_test_payload()
    monkeypatch.setattr(
        step3.runtime_snapshot_v2,
        "_load_v2_snapshot",
        lambda: payload,
    )
    game = {
        "game_date": "2026-09-19",
        "espn_event_id": "401869940",
        "away_espn_team_id": "324",
        "home_espn_team_id": "48",
    }
    bundle, diag = step3._runtime_v2_step3_bundle(
        game,
        "2026-09-19",
    )
    identity = {
        "away": {"team": "Coastal Carolina"},
        "home": {"team": "Delaware"},
    }
    contract = step3.build_step3_contract(
        identity,
        bundle["away"],
        bundle["home"],
    )

    assert diag["source"] == "certified-runtime-branch"
    assert diag["selected_event_found"] is True
    assert diag["away_rows"] == 2
    assert diag["home_rows"] == 2
    assert contract["state"] == "READY"
    assert contract["away"]["last5_record"] == "1-1"
    assert contract["home"]["last5_record"] == "1-1"
    assert contract["away"]["sample_games"] == 2
    assert contract["home"]["sample_games"] == 2
    assert round(contract["away"]["avg_opponent_win_pct"], 3) == 0.5
    assert round(contract["home"]["avg_opponent_win_pct"], 3) == 0.75
    assert contract["away"]["avg_opponent_def_rank"] is not None
    assert contract["home"]["avg_opponent_def_rank"] is not None
    assert contract["away"]["top40_defenses_faced"] is not None
    assert contract["home"]["top40_defenses_faced"] is not None
    assert contract["away"]["record_vs_winning_teams"] == "0-1"
    assert contract["home"]["record_vs_winning_teams"] == "0-1"
    assert contract["away"]["strength_of_schedule_rank"] is not None
    assert contract["home"]["strength_of_schedule_rank"] is not None
    assert all(
        row["event_id"] != "cc-target-day-leak"
        for row in bundle["away"]["completed_games"]
    )


def test_step3_runtime_v2_ready_short_circuits_all_live_provider_fallbacks(monkeypatch):
    payload = _runtime_v2_test_payload()
    monkeypatch.setattr(
        step3.runtime_snapshot_v2,
        "_load_v2_snapshot",
        lambda: payload,
    )
    monkeypatch.setattr(
        step3,
        "_ncaa_combined_step3_universe",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("NCAA must not run after Runtime V2 reaches READY")
        ),
    )
    monkeypatch.setattr(
        step3.deep.history_engine,
        "_fetch_team_schedule",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("ESPN must not run after Runtime V2 reaches READY")
        ),
    )
    monkeypatch.setattr(step3.deep, "_season", lambda game: 2026)
    monkeypatch.setattr(step3.deep, "_cutoff", lambda game: object())

    identity = {
        "away": {"team": "Coastal Carolina", "team_id": "324"},
        "home": {"team": "Delaware", "team_id": "48"},
    }
    game = {
        "game_date": "2026-09-19",
        "espn_event_id": "401869940",
        "away_espn_team_id": "324",
        "home_espn_team_id": "48",
    }

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
    assert diag["away"]["source"] == "certified_runtime_snapshot_v2"
    assert diag["home"]["source"] == "certified_runtime_snapshot_v2"
    assert diag["away"]["runtime_v2_contract_state"] == "READY"
    assert diag["home"]["runtime_v2_contract_state"] == "READY"
