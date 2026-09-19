from __future__ import annotations

from pathlib import Path

import cfb_game_total_step5_pace_v1 as step5

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_clean_page_v17.py"
ROUTER = ROOT / "streamlit_memory_lazy_router_v162.py"
APP = ROOT / "app.py"


def _identity():
    return {
        "away": {
            "team": "North Carolina",
            "team_id": "153",
            "logo": "https://example.test/unc.png",
            "conference": "ACC",
        },
        "home": {
            "team": "Clemson",
            "team_id": "228",
            "logo": "https://example.test/clemson.png",
            "conference": "ACC",
        },
    }


def _away():
    return {
        "team": "North Carolina",
        "record": "2-1",
        "record_text": "2-1",
        "conference": "ACC",
        "ppg": 31.4,
        "points_per_drive": 2.71,
        "completed_games": [{"event_id": "1"}, {"event_id": "2"}, {"event_id": "3"}],
    }


def _home():
    return {
        "team": "Clemson",
        "record": "3-0",
        "record_text": "3-0",
        "conference": "ACC",
        "ppg": 28.2,
        "points_per_drive": 2.45,
        "completed_games": [{"event_id": "4"}, {"event_id": "5"}, {"event_id": "6"}],
    }


def _pace():
    return {
        "ready": True,
        "model_ready": True,
        "coverage": 1.0,
        "sample_factor": 0.8,
        "historical_combined_plays_per_game": 137.2,
        "clock_implied_combined_plays": 141.0,
        "division_baseline_combined_plays": 136.0,
        "expected_combined_plays": 143.0,
        "pace_ratio": 1.04,
        "pace_signal": 0.33,
        "pace_label": "NEUTRAL",
        "away": {
            "plays_per_game": 72.4,
            "seconds_per_offensive_play": 23.8,
            "avg_time_of_possession_seconds": 1795.0,
            "pace_index": 1.07,
            "plays_source": "NCAA Total Offense",
            "clock_source": "NCAA Time of Possession",
        },
        "home": {
            "plays_per_game": 64.8,
            "seconds_per_offensive_play": 28.1,
            "avg_time_of_possession_seconds": 1905.0,
            "pace_index": 0.96,
            "plays_source": "NCAA Total Offense",
            "clock_source": "NCAA Time of Possession",
        },
        "sportsbook_input_used": False,
    }


def _drive():
    return {
        "away": {
            "games": 3,
            "drives_per_game": 12.7,
            "plays_per_game": 72.4,
            "seconds_per_play": 23.8,
            "avg_drive_time_seconds": 138.0,
            "situation_neutral_seconds_per_play": 25.1,
            "no_huddle_rate": 0.38,
            "source": "SportsDataverse current-season completed-game PBP",
            "delivery": "sportsdataverse_github_raw",
            "sportsdataverse_games_loaded": 3,
        },
        "home": {
            "games": 3,
            "drives_per_game": 10.9,
            "plays_per_game": 64.8,
            "seconds_per_play": 28.1,
            "avg_drive_time_seconds": 181.0,
            "situation_neutral_seconds_per_play": 28.7,
            "no_huddle_rate": 0.14,
            "source": "SportsDataverse current-season completed-game PBP",
            "delivery": "sportsdataverse_github_raw",
            "sportsdataverse_games_loaded": 3,
        },
    }


def _bypass_ppd(monkeypatch):
    monkeypatch.setattr(
        step5,
        "_with_drive_ppd",
        lambda away, home, season: (dict(away), dict(home), {"status": "READY"}),
    )


def test_v168_step5_contract_is_presentation_only():
    assert step5.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert step5.MAY_MODIFY_PROJECTION is False
    assert step5.FROZEN_PREDECESSOR == "cfb_game_total_clean_page_v16"
    assert step5.STEP5_PRESENTATION_MARKER == "CFB_GAME_TOTAL_STEP5_PACE_POSSESSIONS_ACTIVE"
    assert step5.STEP5_DATA_MARKER == "CFB_GAME_TOTAL_STEP5_NCAA_PBP_MULTISOURCE_ACTIVE"
    assert step5.STEP5_DEPLOYMENT_MARKER == "CFB_GAME_TOTAL_STEP5_V178_NONBLOCKING_ACTIVE"
    assert "sportsdataverse/cfbfastR-cfb-raw" in step5.SPORTSDATAVERSE_GAME_URL
    assert step5.MAX_PBP_GAMES == 2


def test_v178_step5_presentation_never_calls_live_ncaa_engine(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Step 5 presentation must not call frozen live NCAA scraper")

    monkeypatch.setattr(step5.pace_engine, "build_pace_engine", forbidden)
    seed = step5._safe_pace_engine(
        {"game_date": "2026-09-19"},
        _away(),
        _home(),
    )
    assert seed["model_ready"] is False
    assert seed["presentation_ready"] is False
    assert seed["presentation_ncaa_live_fetch_used"] is False
    assert "deferred" in seed["reason"].lower()


def test_v168_step5_ready_contract_has_exact_twelve_required_tiles(monkeypatch):
    _bypass_ppd(monkeypatch)
    contract = step5.build_step5_contract(
        _identity(),
        _away(),
        _home(),
        {"game_date": "2026-09-19"},
        pace=_pace(),
        drive_evidence=_drive(),
    )
    assert contract["state"] == "READY"
    assert contract["ready"] is True
    assert contract["ready_tiles"] == 12
    assert contract["tile_count"] == 12
    assert contract["coverage"] == 1.0

    expected = [
        "PLAYS / GAME",
        "SECONDS / PLAY",
        "SITUATION-NEUTRAL PACE",
        "DRIVES / GAME",
        "NO-HUDDLE RATE",
        "AVG DRIVE TIME",
    ]
    assert [row["label"] for row in contract["away"]["tiles"]] == expected
    assert [row["label"] for row in contract["home"]["tiles"]] == expected


def test_v168_step5_expected_environment_is_populated(monkeypatch):
    _bypass_ppd(monkeypatch)
    contract = step5.build_step5_contract(
        _identity(),
        _away(),
        _home(),
        {"game_date": "2026-09-19"},
        pace=_pace(),
        drive_evidence=_drive(),
    )
    assert contract["expected_combined_plays"] == 143.0
    assert contract["expected_away_drives"] is not None
    assert contract["expected_home_drives"] is not None
    assert contract["expected_combined_drives"] is not None
    assert contract["tempo_grade"] == "B+"
    assert contract["pace_volatility"] in {"LOW", "MEDIUM", "HIGH"}
    assert contract["data_confidence"] == 100
    assert contract["ou_impact"] == "SLIGHT OVER PRESSURE"


def test_v168_step5_missing_pbp_only_fields_fails_closed_to_check(monkeypatch):
    _bypass_ppd(monkeypatch)
    sparse = _drive()
    sparse["away"] = {
        "games": 0,
        "drives_per_game": None,
        "avg_drive_time_seconds": None,
        "situation_neutral_seconds_per_play": None,
        "no_huddle_rate": None,
        "source": "",
    }
    contract = step5.build_step5_contract(
        _identity(),
        _away(),
        _home(),
        {"game_date": "2026-09-19"},
        pace=_pace(),
        drive_evidence=sparse,
    )
    assert contract["state"] == "CHECK"
    away = {row["label"]: row for row in contract["away"]["tiles"]}
    assert away["SITUATION-NEUTRAL PACE"]["ready"] is False
    assert away["NO-HUDDLE RATE"]["ready"] is False
    assert away["SITUATION-NEUTRAL PACE"]["badge"] == "DATA LIMITED"


def test_v168_step5_core_pace_failure_is_data_limited(monkeypatch):
    _bypass_ppd(monkeypatch)
    pace = _pace()
    pace["model_ready"] = False
    pace["coverage"] = 0.25
    monkeypatch.setattr(
        step5,
        "_safe_sdv_pregame_pace",
        lambda identity, game, drives, frozen=None: {
            "ready": True,
            "model_ready": False,
            "presentation_ready": False,
            "coverage": 0.0,
            "away": {},
            "home": {},
            "sportsbook_input_used": False,
        },
    )
    contract = step5.build_step5_contract(
        _identity(),
        _away(),
        _home(),
        {"game_date": "2026-09-19"},
        pace=pace,
        drive_evidence=_drive(),
    )
    assert contract["state"] == "DATA LIMITED"
    assert contract["ready"] is False


def test_v168_drive_parser_reads_drives_no_huddle_and_neutral_pace():
    summary = {
        "drives": {
            "previous": [
                {
                    "team": {"id": "153"},
                    "timeElapsed": {"displayValue": "2:30"},
                    "plays": [
                        {
                            "text": "No Huddle-Shotgun pass complete",
                            "period": {"number": 1},
                            "clock": {"displayValue": "12:00"},
                            "homeScore": 0,
                            "awayScore": 0,
                        },
                        {
                            "text": "Rush for 5 yards",
                            "period": {"number": 1},
                            "clock": {"displayValue": "11:30"},
                            "homeScore": 0,
                            "awayScore": 0,
                        },
                        {
                            "text": "Pass complete",
                            "period": {"number": 1},
                            "clock": {"displayValue": "11:00"},
                            "homeScore": 0,
                            "awayScore": 0,
                        },
                    ],
                }
            ]
        }
    }
    result = step5._parse_drive_evidence([summary], "153")
    assert result["games"] == 1
    assert result["drive_count"] == 1
    assert result["drives_per_game"] == 1.0
    assert result["avg_drive_time_seconds"] == 150.0
    assert result["situation_neutral_seconds_per_play"] == 30.0
    assert round(result["no_huddle_rate"], 3) == round(1 / 3, 3)


def test_v168_sportsdataverse_parser_reads_flattened_drive_pace_and_no_huddle():
    game = {
        "plays": [
            {
                "text": "No Huddle-Shotgun pass complete",
                "teamParticipants": [{"id": "153", "type": "offense"}],
                "type.text": "Pass Reception",
                "start.down": 1,
                "period.number": 1,
                "clock.displayValue": "12:00",
                "homeScore": 0,
                "awayScore": 0,
                "drive.id": "d1",
                "drive.timeElapsed.displayValue": "2:30",
            },
            {
                "text": "Rush for 5 yards",
                "teamParticipants": [{"id": "153", "type": "offense"}],
                "type.text": "Rush",
                "start.down": 2,
                "period.number": 1,
                "clock.displayValue": "11:30",
                "homeScore": 0,
                "awayScore": 0,
                "drive.id": "d1",
                "drive.timeElapsed.displayValue": "2:30",
            },
            {
                "text": "Pass complete",
                "teamParticipants": [{"id": "153", "type": "offense"}],
                "type.text": "Pass Reception",
                "start.down": 1,
                "period.number": 1,
                "clock.displayValue": "9:00",
                "homeScore": 0,
                "awayScore": 0,
                "drive.id": "d2",
                "drive.timeElapsed.displayValue": "1:40",
            },
            {
                "text": "Rush for 2 yards",
                "teamParticipants": [{"id": "153", "type": "offense"}],
                "type.text": "Rush",
                "start.down": 2,
                "period.number": 1,
                "clock.displayValue": "8:35",
                "homeScore": 0,
                "awayScore": 0,
                "drive.id": "d2",
                "drive.timeElapsed.displayValue": "1:40",
            },
        ]
    }
    result = step5._parse_sportsdataverse_evidence([game], "153")
    assert result["games"] == 1
    assert result["drive_count"] == 2
    assert result["drives_per_game"] == 2.0
    assert result["avg_drive_time_seconds"] == 125.0
    assert result["plays_per_game"] == 4.0
    assert result["seconds_per_play"] == 27.5
    assert result["situation_neutral_seconds_per_play"] == 27.5
    assert result["no_huddle_rate"] == 0.25
    assert result["delivery"] == "sportsdataverse_github_raw"


def test_v168_sportsdataverse_is_primary_and_espn_is_not_required(monkeypatch):
    identity = _identity()
    away = _away()
    home = _home()

    def fake_sdv(event_id):
        team_id = "153" if event_id in {"2", "3"} else "228"
        return {
            "plays": [
                {
                    "text": "No Huddle-Shotgun rush",
                    "teamParticipants": [{"id": team_id, "type": "offense"}],
                    "type.text": "Rush",
                    "start.down": 1,
                    "period.number": 1,
                    "clock.displayValue": "12:00",
                    "homeScore": 0,
                    "awayScore": 0,
                    "drive.id": f"{event_id}-d1",
                    "drive.timeElapsed.displayValue": "2:00",
                },
                {
                    "text": "Rush for 4 yards",
                    "teamParticipants": [{"id": team_id, "type": "offense"}],
                    "type.text": "Rush",
                    "start.down": 2,
                    "period.number": 1,
                    "clock.displayValue": "11:35",
                    "homeScore": 0,
                    "awayScore": 0,
                    "drive.id": f"{event_id}-d1",
                    "drive.timeElapsed.displayValue": "2:00",
                },
            ]
        }

    monkeypatch.setattr(step5, "_fetch_sportsdataverse_game", fake_sdv)
    monkeypatch.setattr(
        step5,
        "_fetch_summary",
        lambda event_id: (_ for _ in ()).throw(
            AssertionError("ESPN must not be required when SportsDataverse succeeds")
        ),
    )

    result = step5._safe_drive_evidence(identity, away, home)
    assert result["away"]["games"] == 2
    assert result["home"]["games"] == 2
    assert result["away"]["espn_fallback_used"] is False
    assert result["home"]["espn_fallback_used"] is False
    assert result["away"]["sportsdataverse_games_loaded"] == 2
    assert result["home"]["sportsdataverse_games_loaded"] == 2
    assert result["away"]["source"] == "SportsDataverse current-season completed-game PBP"
    assert result["home"]["source"] == "SportsDataverse current-season completed-game PBP"


def test_v168_sportsdataverse_flattened_clock_helpers_are_supported():
    play = {
        "period.number": 3,
        "clock.displayValue": "07:21",
    }
    assert step5._play_period(play) == 3
    assert step5._play_clock(play) == 441.0


def test_v176_sdv_pbp_recovers_core_pace_without_ncaa():
    frozen = {
        "ready": True,
        "model_ready": False,
        "coverage": 0.0,
        "away": {},
        "home": {},
        "sportsbook_input_used": False,
    }
    recovered = step5._safe_sdv_pregame_pace(
        _identity(),
        {"game_date": "2026-09-19", "espn_event_id": "999"},
        _drive(),
        frozen,
    )
    assert recovered["model_ready"] is False
    assert recovered["presentation_ready"] is True
    assert recovered["coverage"] == 1.0
    assert recovered["presentation_source"] == "SportsDataverse completed-game PBP"
    assert recovered["away"]["plays_per_game"] == 72.4
    assert recovered["home"]["plays_per_game"] == 64.8
    assert recovered["away"]["seconds_per_offensive_play"] == 23.8
    assert recovered["home"]["seconds_per_offensive_play"] == 28.1
    assert recovered["away"]["plays_source"] == "SportsDataverse completed-game PBP"
    assert recovered["home"]["clock_source"] == "SportsDataverse completed-game PBP"
    assert recovered["expected_combined_plays"] == 137.2
    assert recovered["sportsbook_input_used"] is False


def test_v176_sdv_pbp_recovery_preserves_frozen_ncaa_baseline_when_available():
    frozen = {
        "ready": True,
        "model_ready": False,
        "coverage": 0.75,
        "away": {"division_baseline_plays_per_game": 67.0},
        "home": {"division_baseline_plays_per_game": 69.0},
        "sportsbook_input_used": False,
    }
    recovered = step5._safe_sdv_pregame_pace(
        _identity(),
        {"game_date": "2026-09-19"},
        _drive(),
        frozen,
    )
    assert recovered["division_baseline_combined_plays"] == 136.0
    assert recovered["away"]["pace_index"] == 72.4 / 68.0
    assert recovered["home"]["pace_index"] == 64.8 / 68.0
    assert recovered["model_ready"] is False
    assert recovered["sportsbook_input_used"] is False

def test_v175_step5_recovers_data_limited_ncaa_state_to_ready(monkeypatch):
    _bypass_ppd(monkeypatch)
    frozen = {
        "ready": True,
        "model_ready": False,
        "coverage": 0.0,
        "reason": "NCAA Total Offense pace row is unavailable",
        "away": {},
        "home": {},
        "sportsbook_input_used": False,
    }
    recovered = _pace()
    recovered["model_ready"] = False
    recovered["presentation_ready"] = True
    recovered["presentation_source"] = (
        "SportsDataverse completed-game PBP"
    )
    recovered["away"]["plays_source"] = (
        "SportsDataverse completed-game PBP"
    )
    recovered["away"]["clock_source"] = (
        "SportsDataverse pregame matchup features"
    )
    recovered["home"]["plays_source"] = (
        "SportsDataverse pregame matchup features"
    )
    recovered["home"]["clock_source"] = (
        "SportsDataverse pregame matchup features"
    )

    monkeypatch.setattr(
        step5,
        "_safe_sdv_pregame_pace",
        lambda identity, game, drives, frozen=None: dict(recovered),
    )
    contract = step5.build_step5_contract(
        _identity(),
        _away(),
        _home(),
        {"game_date": "2026-09-19"},
        pace=frozen,
        drive_evidence=_drive(),
    )
    assert contract["state"] == "READY"
    assert contract["ready"] is True
    assert contract["ready_tiles"] == 12
    assert contract["coverage"] == 1.0
    assert contract["expected_combined_plays"] == 143.0
    assert contract["expected_away_drives"] is not None
    assert contract["expected_home_drives"] is not None
    assert contract["tempo_grade"] == "B+"
    assert contract["matchup_read"] != "PACE DATA LIMITED"
    assert contract["biggest_accelerator"] != "Verified pace edge unavailable"
    assert contract["biggest_brake"] != "Verified pace brake unavailable"
    assert contract["ou_impact"] == "SLIGHT OVER PRESSURE"
    assert contract["data_confidence"] == 100
    assert contract["pace_engine"]["model_ready"] is False
    assert contract["pace_engine"]["presentation_ready"] is True
    assert contract["pace_engine"]["sportsbook_input_used"] is False


def test_v176_real_pbp_recovery_renders_ready_dom_without_parquet(monkeypatch):
    _bypass_ppd(monkeypatch)
    frozen = {
        "ready": True,
        "model_ready": False,
        "coverage": 0.0,
        "reason": "NCAA Total Offense pace row is unavailable",
        "away": {},
        "home": {},
        "sportsbook_input_used": False,
    }
    html = step5.render_step5_html(
        "CHECK",
        _identity(),
        _away(),
        _home(),
        {
            "game_date": "2026-09-18",
            "espn_event_id": "401858226",
            "away_record_summary": "2-1",
            "home_record_summary": "3-0",
        },
        pace=frozen,
        drive_evidence=_drive(),
    )
    assert 'data-testid="gt157-step-5"' in html
    assert 'data-step5-state="READY"' in html
    assert 'data-step5-coverage="100"' in html
    assert html.count('data-testid="gt168-step5-stat-tile"') == 12
    assert "72.4" in html
    assert "64.8" in html
    assert "23.8" in html
    assert "28.1" in html
    assert "DATA LIMITED" not in html
    assert "SportsDataverse completed-game PBP" in html


def test_v175_step5_renders_game_context_and_event_record_fallback(monkeypatch):
    _bypass_ppd(monkeypatch)
    away = _away()
    home = _home()
    away["record_text"] = "0-0"
    home["record_text"] = "0-0"
    html = step5.render_step5_html(
        "CHECK",
        _identity(),
        away,
        home,
        {
            "game_date": "2026-09-19",
            "kickoff_iso": "2026-09-19T23:30:00Z",
            "venue": "Memorial Stadium",
            "broadcast": "ABC",
            "away_record_summary": "2-1",
            "home_record_summary": "3-0",
        },
        pace=_pace(),
        drive_evidence=_drive(),
    )
    assert "MEMORIAL STADIUM" in html.upper()
    assert "7:30 PM ET" in html
    assert "ABC" in html
    assert "2-1" in html
    assert "3-0" in html


def test_v168_step5_render_matches_mockup_structure(monkeypatch):
    _bypass_ppd(monkeypatch)
    html = step5.render_step5_html(
        "CHECK",
        _identity(),
        _away(),
        _home(),
        {"game_date": "2026-09-19"},
        pace=_pace(),
        drive_evidence=_drive(),
    )
    assert 'data-testid="gt157-step-5"' in html
    assert 'data-step5-state="READY"' in html
    assert 'data-step5-coverage="100"' in html
    assert 'data-step5-away-pbp-delivery="sportsdataverse_github_raw"' in html
    assert 'data-step5-home-pbp-delivery="sportsdataverse_github_raw"' in html
    assert 'data-step5-away-pbp-games="3"' in html
    assert 'data-step5-home-pbp-games="3"' in html
    assert html.count('data-testid="gt168-step5-stat-tile"') == 12
    assert "PACE &amp; EXPECTED POSSESSIONS" in html or "PACE & EXPECTED POSSESSIONS" in html
    assert "EXPECTED GAME ENVIRONMENT" in html
    assert "MATCHUP READ" in html
    assert "BIGGEST ACCELERATOR" in html
    assert "BIGGEST BRAKE" in html
    assert "O/U IMPACT" in html
    assert "DATA CONFIDENCE" in html
    assert "MULTI-SOURCE VERIFIED" in html
    assert "SPORTSBOOK INFLUENCE 0.0%" in html
    assert "North Carolina Pace Profile" in html
    assert "Clemson Pace Profile" in html
    assert html.split(">", 1)[0].endswith("</style") is False


def test_v168_step5_css_keeps_two_team_mockup_and_mobile_layout():
    assert ".gt168-step5-profile-grid{display:grid;grid-template-columns:repeat(2" in step5.STEP5_CSS
    assert ".gt168-step5-metrics{display:grid;grid-template-columns:repeat(3" in step5.STEP5_CSS
    assert ".gt168-step5-insights{display:grid;grid-template-columns:1.08fr 1fr 1fr" in step5.STEP5_CSS
    assert "@media(max-width:760px)" in step5.STEP5_CSS
    assert "@media(max-width:420px)" in step5.STEP5_CSS


def test_v168_page_advances_only_step5_owner():
    source = PAGE.read_text(encoding="utf-8")
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v16"' in source
    assert "import cfb_game_total_step5_pace_v1 as step5_owner" in source
    assert "if int(number) == 5:" in source
    assert "return prior_v165.render_game_total_hub" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "STEP4_GRADE_MARKER = prior_v165.STEP4_GRADE_MARKER" in source
    assert "step3_data_owner.load_matchup_team_data" not in source
    assert "step3_owner.enrich_step3_inputs" not in source
    assert "step3_owner._runtime_v2_step3_bundle" in source
    assert "step5_away.update(step3_away)" in source
    assert "step5_home.update(step3_home)" in source
    assert "exact completed-game event IDs" in source


def test_v168_router_advances_only_exact_game_total_page_and_preserves_step4_marker():
    source = ROUTER.read_text(encoding="utf-8")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v161"' in source
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v17"' in source
    assert "CFB_GAME_TOTAL_V165_STEP4_MATCHUP_ACTIVE" in source
    assert "CFB_GAME_TOTAL_V168_STEP5_PACE_POSSESSIONS_ACTIVE" in source
    assert "CFB_GAME_TOTAL_STEP5_V178_NONBLOCKING_ACTIVE" in source
    assert "return prior.render_app()" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source


def test_app_activates_v163_router_while_preserving_v162_delegate():
    source = APP.read_text(encoding="utf-8")
    router_v163 = (ROOT / "streamlit_memory_lazy_router_v163.py").read_text(encoding="utf-8")
    runtime = source[source.find("try:"):]
    assert "from streamlit_memory_lazy_router_v163 import record_bootstrap_import_ms, render_app" in runtime
    assert "import streamlit_memory_lazy_router_v162 as prior" in router_v163
    assert "return prior.render_app()" in router_v163
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v162"' in router_v163
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in router_v163
    assert "MAY_MODIFY_PROJECTION = False" in router_v163
    assert "from streamlit_memory_lazy_router_v161 import record_bootstrap_import_ms, render_app" not in runtime


def test_v168_visual_markers_are_emitted(monkeypatch):
    _bypass_ppd(monkeypatch)
    html = step5.render_step5_html(
        "CHECK",
        _identity(),
        _away(),
        _home(),
        {"game_date": "2026-09-19"},
        pace=_pace(),
        drive_evidence=_drive(),
    )
    assert 'data-step5-marker="CFB_GAME_TOTAL_STEP5_PACE_POSSESSIONS_ACTIVE"' in html
    assert 'data-step5-data-marker="CFB_GAME_TOTAL_STEP5_NCAA_PBP_MULTISOURCE_ACTIVE"' in html
    assert 'data-step5-visual-marker="CFB_GAME_TOTAL_STEP5_V168_VISUAL_TARGET_ACTIVE"' in html
    assert 'data-step5-deployment-marker="CFB_GAME_TOTAL_STEP5_V178_NONBLOCKING_ACTIVE"' in html



def test_v182_step5_page_does_not_rerun_full_step3_live_enrichment():
    source = PAGE.read_text(encoding="utf-8")
    assert "step3_owner.enrich_step3_inputs" not in source
    assert "step3_owner._runtime_v2_step3_bundle" in source



def test_v183_step5_page_has_zero_heavy_ncaa_prerender_calls():
    source = PAGE.read_text(encoding="utf-8")
    assert "step3_data_owner.load_matchup_team_data" not in source
    assert "step3_owner.enrich_step3_inputs" not in source
    assert "step3_owner._runtime_v2_step3_bundle" in source



def test_v185_current_live_matchup_uses_verified_local_pbp_cache(monkeypatch):
    identity = {
        "away": {"team": "Coastal Carolina", "team_id": "324"},
        "home": {"team": "Delaware", "team_id": "48"},
    }
    away = {
        "team": "Coastal Carolina",
        "team_id": "324",
        "completed_games": [
            {"event_id": "401856780"},
            {"event_id": "401868008"},
        ],
    }
    home = {
        "team": "Delaware",
        "team_id": "48",
        "completed_games": [
            {"event_id": "401864424"},
            {"event_id": "401856684"},
        ],
    }

    def forbidden(*args, **kwargs):
        raise AssertionError("V185 cached matchup must not hit live PBP network")

    monkeypatch.setattr(step5, "_fetch_sportsdataverse_game", forbidden)
    monkeypatch.setattr(step5, "_fetch_summary", forbidden)

    evidence = step5._safe_drive_evidence(identity, away, home)

    assert evidence["away"]["delivery"] == "sportsdataverse_github_raw_snapshot"
    assert evidence["home"]["delivery"] == "sportsdataverse_github_raw_snapshot"
    assert evidence["away"]["sportsdataverse_games_loaded"] == 2
    assert evidence["home"]["sportsdataverse_games_loaded"] == 2
    assert evidence["away"]["plays_per_game"] == 72.5
    assert evidence["home"]["plays_per_game"] == 74.0
    assert evidence["away"]["seconds_per_play"] > 0
    assert evidence["home"]["seconds_per_play"] > 0
    assert evidence["away"]["no_huddle_rate"] > 0
    assert evidence["home"]["no_huddle_rate"] > 0
