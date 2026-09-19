from __future__ import annotations

from pathlib import Path

import cfb_game_total_step6_scoring_v1 as step6

PAGE = Path("cfb_game_total_clean_page_v18.py")
ROUTER = Path("streamlit_memory_lazy_router_v163.py")
APP = Path("app.py")


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
    return {"team": "North Carolina", "record_text": "3-0"}


def _home():
    return {"team": "Clemson", "record_text": "2-1"}


def _metrics(
    pass_rate,
    rush_rate,
    overall_rate,
    ops,
    conversion,
    rz_td,
    *,
    games=4,
    defense=False,
):
    row = {
        "games": games,
        "pass_explosive_rate": pass_rate,
        "rush_explosive_rate": rush_rate,
        "overall_explosive_rate": overall_rate,
        "scoring_ops_pg": ops,
        "scoring_op_conversion": conversion,
        "red_zone_td_rate": rz_td,
        "source": "SportsDataverse current-season completed-game PBP",
        "delivery": "sportsdataverse_github_raw",
        "coverage": 1.0,
    }
    if defense:
        row["big_play_susceptibility"] = overall_rate
        row["red_zone_td_rate_allowed"] = rz_td
        row["scoring_op_conversion_allowed"] = conversion
    return row


def _evidence():
    return {
        "away_offense": _metrics(0.18, 0.22, 0.19, 5.7, 0.78, 0.68),
        "away_defense": _metrics(0.12, 0.18, 0.14, 4.4, 0.64, 0.55, defense=True),
        "home_offense": _metrics(0.15, 0.17, 0.16, 4.8, 0.70, 0.61),
        "home_defense": _metrics(0.10, 0.14, 0.11, 3.8, 0.58, 0.48, defense=True),
        "away_event_ids": ["401000001", "401000002"],
        "home_event_ids": ["401000003", "401000004"],
        "unique_events_loaded": 4,
    }


def test_v184_ready_contract_is_100_percent_and_12_of_12():
    contract = step6.build_step6_contract(
        _identity(),
        _away(),
        _home(),
        {"game_date": "2026-09-21"},
        evidence=_evidence(),
    )
    assert contract["state"] == "READY"
    assert contract["ready"] is True
    assert contract["coverage"] == 100
    assert contract["ready_tiles"] == 12
    assert contract["tile_count"] == 12
    assert contract["sportsbook_input_used"] is False
    assert contract["projection_mutation"] is False
    assert contract["away_creation_grade"] != "—"
    assert contract["home_creation_grade"] != "—"
    assert contract["expected_scoring_chances"] is not None
    assert contract["ou_impact"] in {
        "OVER PRESSURE",
        "SLIGHT OVER PRESSURE",
        "NEUTRAL",
        "SLIGHT UNDER PRESSURE",
        "UNDER PRESSURE",
    }


def test_v184_data_limited_fails_closed_without_inventing_tiles():
    evidence = _evidence()
    evidence["home_defense"] = {
        "games": 0,
        "source": "",
        "delivery": "sportsdataverse_github_raw",
        "coverage": 0.0,
    }
    contract = step6.build_step6_contract(
        _identity(),
        _away(),
        _home(),
        {"game_date": "2026-09-21"},
        evidence=evidence,
    )
    assert contract["state"] == "DATA LIMITED"
    assert contract["ready"] is False
    assert contract["coverage"] < 100
    assert contract["ready_tiles"] < 12
    assert contract["projection_mutation"] is False


def test_v184_html_matches_scoring_creation_visual_contract():
    html = step6.render_step6_html(
        "READY",
        _identity(),
        _away(),
        _home(),
        {
            "game_date": "2026-09-21",
            "kickoff_et": "7:30 PM ET",
            "venue": "Memorial Stadium",
            "broadcast": "ABC",
        },
        evidence=_evidence(),
    )
    assert 'data-testid="gt157-step-6"' in html
    assert 'data-step6-state="READY"' in html
    assert 'data-step6-coverage="100"' in html
    assert 'data-step6-ready-tiles="12"' in html
    assert 'data-step6-deployment-marker="CFB_GAME_TOTAL_STEP6_V184_DEPLOYMENT_ACTIVE"' in html
    assert html.count('data-testid="gt184-step6-stat-tile"') == 12
    assert html.count('data-ready="true"') == 12
    assert "💥 Scoring Creation" in html
    assert "SCORING ENVIRONMENT" in html
    assert "MATCHUP READ" in html
    assert "BIGGEST ACCELERATOR" in html
    assert "BIGGEST SUPPRESSOR" in html
    assert "O/U IMPACT" in html
    assert "DATA CONFIDENCE" in html
    assert "EXPLOSIVE PASS RATE" in html
    assert "EXPLOSIVE RUSH RATE" in html
    assert "OVERALL EXPLOSIVE RATE" in html
    assert "SCORING-OPPORTUNITY CONVERSION" in html
    assert "Big-play susceptibility" in html
    assert "Red-zone TD rate allowed" in html
    assert "POINTS / OPPORTUNITY" not in html
    assert "TD DRIVES" not in html
    assert "SPORTSBOOK INFLUENCE 0.0%" in html
    assert "PROJECTION MUTATION OFF" in html


def test_v184_sdv_parser_builds_offense_and_defense_creation_metrics():
    game = {
        "plays": [
            {
                "pos_team": 153,
                "def_pos_team": 228,
                "drive.id": "d1",
                "pass": True,
                "yds_receiving": 27,
                "rz_play": False,
                "scoring_opp": False,
                "pos_score_pts": 0,
                "drive.result": "TD",
            },
            {
                "pos_team": 153,
                "def_pos_team": 228,
                "drive.id": "d1",
                "rush": True,
                "yds_rushed": 12,
                "rz_play": True,
                "scoring_opp": True,
                "td_play": True,
                "pos_score_pts": 6,
                "drive.result": "TD",
            },
            {
                "pos_team": 153,
                "def_pos_team": 228,
                "drive.id": "d2",
                "pass": True,
                "yds_receiving": 8,
                "rz_play": False,
                "scoring_opp": True,
                "pos_score_pts": 3,
                "drive.result": "FG",
            },
        ]
    }
    offense = step6._side_metrics([game], "153", defense=False)
    defense = step6._side_metrics([game], "228", defense=True)

    assert offense["pass_explosive_rate"] == 0.5
    assert offense["rush_explosive_rate"] == 1.0
    assert offense["overall_explosive_rate"] == 2 / 3
    assert offense["scoring_ops_pg"] == 2.0
    assert offense["scoring_op_conversion"] == 1.0
    assert offense["red_zone_td_rate"] == 1.0
    assert defense["pass_explosive_rate"] == offense["pass_explosive_rate"]
    assert defense["rush_explosive_rate"] == offense["rush_explosive_rate"]
    assert defense["overall_explosive_rate"] == offense["overall_explosive_rate"]
    assert defense["big_play_susceptibility"] == defense["overall_explosive_rate"]
    assert defense["red_zone_td_rate_allowed"] == defense["red_zone_td_rate"]
    assert defense["scoring_op_conversion_allowed"] == defense["scoring_op_conversion"]


def test_v184_page_advances_only_step6_and_freezes_step5():
    source = PAGE.read_text(encoding="utf-8")
    assert 'FROZEN_PRESENTATION = "cfb_game_total_clean_page_v17"' in source
    assert "import cfb_game_total_step6_scoring_v1 as step6_owner" in source
    assert "if int(number) == 6:" in source
    assert "step6_owner.render_step6_html" in source
    assert "STEP5_PRESENTATION_MARKER = prior_v168.STEP5_PRESENTATION_MARKER" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "load_matchup_team_data" not in source
    assert "enrich_step3_inputs" not in source
    assert "_runtime_v2_step3_bundle" in source



def test_v184_step6_owner_avoids_heavy_live_ncaa_engines():
    source = Path("cfb_game_total_step6_scoring_v1.py").read_text(encoding="utf-8")
    assert "cfb_over_under_explosive_engine_v1" not in source
    assert "cfb_over_under_red_zone_engine_v1" not in source
    assert "load_matchup_team_data" not in source
    assert "enrich_step3_inputs" not in source
    assert "_fetch_sportsdataverse_game" in source
    assert "ThreadPoolExecutor" not in source


def test_v184_step6_pbp_fetch_is_bounded_and_sequential(monkeypatch):
    calls = []

    def fake_fetch(event_id):
        calls.append(event_id)
        return {}

    monkeypatch.setattr(step6.step5_pace, "_fetch_sportsdataverse_game", fake_fetch)

    away = {
        "completed_games": [
            {"event_id": "401000001"},
            {"event_id": "401000002"},
            {"event_id": "401000003"},
        ]
    }
    home = {
        "completed_games": [
            {"event_id": "401000004"},
            {"event_id": "401000005"},
            {"event_id": "401000006"},
        ]
    }

    step6._load_pbp_evidence(_identity(), away, home)

    assert len(calls) <= 2 * step6.MAX_PBP_GAMES
    assert calls == list(dict.fromkeys(calls))



def test_v184_ten_yard_rush_is_explosive_but_nine_is_not():
    ten = {"plays": [{
        "pos_team": 153,
        "def_pos_team": 228,
        "drive.id": "d10",
        "rush": True,
        "scrimmage_play": True,
        "yds_rushed": 10,
        "drive.result": "PUNT",
    }]}
    nine = {"plays": [{
        "pos_team": 153,
        "def_pos_team": 228,
        "drive.id": "d9",
        "rush": True,
        "scrimmage_play": True,
        "yds_rushed": 9,
        "drive.result": "PUNT",
    }]}
    assert step6._side_metrics([ten], "153")["rush_explosive_rate"] == 1.0
    assert step6._side_metrics([nine], "153")["rush_explosive_rate"] == 0.0


def test_v184_non_scrimmage_play_cannot_create_explosive_evidence():
    kickoff = {"plays": [{
        "pos_team": 153,
        "def_pos_team": 228,
        "drive.id": "kick",
        "pass": True,
        "scrimmage_play": False,
        "statYardage": 70,
        "drive.result": "TD",
    }]}
    metrics = step6._side_metrics([kickoff], "153")
    assert metrics["games"] == 0
    assert metrics["coverage"] == 0.0


def test_v184_router_activates_only_page_v18_and_app_boots_router_v163():
    router = ROUTER.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    assert "import streamlit_memory_lazy_router_v162 as prior" in router
    assert 'ACTIVE_PAGE = "cfb_game_total_clean_page_v18"' in router
    assert "CFB_GAME_TOTAL_V184_STEP6_SCORING_CREATION_ACTIVE" in router
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in router
    assert "MAY_MODIFY_PROJECTION = False" in router
    assert "return prior.render_app()" in router
    assert "from streamlit_memory_lazy_router_v163 import record_bootstrap_import_ms, render_app" in app


def test_v184_page_reexports_step6_deployment_marker():
    source = PAGE.read_text(encoding="utf-8")
    assert "STEP6_DEPLOYMENT_MARKER = step6_owner.STEP6_DEPLOYMENT_MARKER" in source



def _snapshot_identity():
    return {
        "away": {
            "team": "Coastal Carolina",
            "team_id": "324",
            "conference": "Sun Belt",
        },
        "home": {
            "team": "Delaware",
            "team_id": "48",
            "conference": "CUSA",
        },
    }


def _snapshot_away():
    return {
        "team": "Coastal Carolina",
        "completed_games": [
            {"event_id": "401856780"},
            {"event_id": "401868008"},
        ],
    }


def _snapshot_home():
    return {
        "team": "Delaware",
        "completed_games": [
            {"event_id": "401864424"},
            {"event_id": "401856684"},
        ],
    }


def test_v184_exact_snapshot_match_is_nonblocking_and_ready(monkeypatch):
    def forbidden_network(_event_id):
        raise AssertionError("live SportsDataverse fetch must not run on exact snapshot hit")

    monkeypatch.setattr(step6.step5_pace, "_fetch_sportsdataverse_game", forbidden_network)

    evidence = step6._load_pbp_evidence(
        _snapshot_identity(),
        _snapshot_away(),
        _snapshot_home(),
    )
    assert evidence["snapshot_used"] is True
    assert evidence["unique_events_loaded"] == 4
    assert evidence["away_offense"]["delivery"] == "sportsdataverse_github_raw_snapshot"
    assert evidence["away_defense"]["delivery"] == "sportsdataverse_github_raw_snapshot"
    assert evidence["home_offense"]["delivery"] == "sportsdataverse_github_raw_snapshot"
    assert evidence["home_defense"]["delivery"] == "sportsdataverse_github_raw_snapshot"

    contract = step6.build_step6_contract(
        _snapshot_identity(),
        _snapshot_away(),
        _snapshot_home(),
        {
            "espn_event_id": "401869940",
            "game_date": "2026-09-19",
        },
        evidence=evidence,
    )
    assert contract["state"] == "READY"
    assert contract["coverage"] == 100
    assert contract["ready_tiles"] == 12
    assert contract["tile_count"] == 12
    assert contract["sportsbook_input_used"] is False
    assert contract["projection_mutation"] is False


def test_v184_snapshot_rejects_event_drift_and_uses_live_fallback(monkeypatch):
    calls = []

    def empty_live_fetch(event_id):
        calls.append(str(event_id))
        return {}

    monkeypatch.setattr(step6.step5_pace, "_fetch_sportsdataverse_game", empty_live_fetch)
    away = _snapshot_away()
    away["completed_games"][-1] = {"event_id": "499999999"}

    evidence = step6._load_pbp_evidence(
        _snapshot_identity(),
        away,
        _snapshot_home(),
    )
    assert evidence["snapshot_used"] is False
    assert "499999999" in calls

    contract = step6.build_step6_contract(
        _snapshot_identity(),
        away,
        _snapshot_home(),
        {"game_date": "2026-09-19"},
        evidence=evidence,
    )
    assert contract["state"] == "DATA LIMITED"
    assert contract["ready_tiles"] < 12
    assert contract["projection_mutation"] is False


def test_v184_snapshot_file_locks_verified_current_provenance():
    snapshot = Path("data/cfb_step6_scoring_snapshot_v1.json").read_text(
        encoding="utf-8"
    )
    assert '"current_event_id": "401869940"' in snapshot
    assert '"current_game_date": "2026-09-19"' in snapshot
    assert '"401864424": "af13fc7044fc65a67586fcc1ad53d3a7f4c13b55"' in snapshot
    assert '"401856684": "e087aebe4c8e79090d998809c95dc7d94dbde4bc"' in snapshot
    assert '"401856780": "bb4d0ed6fa6afdff3f93124fbe3e1c5e3435fc93"' in snapshot
    assert '"401868008": "d63674cd525c8751da6d34f3daeb83c2acb25441"' in snapshot
