from __future__ import annotations

import inspect

import pandas as pd
import pytest

import mlb_matchup_bullpen_v1 as bp
import mlb_matchup_hub_v27 as router
import mlb_matchup_hub_v37 as hub
import mlb_matchup_player_v31 as player


def _foundation() -> dict:
    return {
        "player_id": 99,
        "player_name": "Test Hitter",
        "team": "Away Club",
        "opponent": "Home Club",
        "game_pk": 1001,
        "game_date": "2026-09-02",
        "side": "away",
        "starter_id": 10,
        "starter_name": "Starter",
        "season": 2026,
    }


def _active() -> dict:
    return {
        "status": "VERIFIED",
        "source": "Official MLB active roster",
        "pitchers": [
            {"id": 10, "name": "Starter", "hand": "R"},
            {"id": 11, "name": "Reliever One", "hand": "R"},
            {"id": 12, "name": "Reliever Two", "hand": "L"},
            {"id": 13, "name": "Reliever Three", "hand": "R"},
            {"id": 14, "name": "Reliever Four", "hand": "L"},
            {"id": 15, "name": "Other Starter", "hand": "R"},
        ],
    }


def _stat(ip, g, gs, h, bb, er, k, bf):
    return {
        "inningsPitched": str(ip),
        "gamesPlayed": g,
        "gamesStarted": gs,
        "hits": h,
        "baseOnBalls": bb,
        "earnedRuns": er,
        "strikeOuts": k,
        "battersFaced": bf,
    }


def _season() -> dict:
    return {
        "status": "VERIFIED",
        "source": "Official MLB individual season pitching stats",
        "rows": [
            {"player_id": 10, "player_name": "Starter", "stat": _stat("150.0", 28, 28, 130, 40, 55, 170, 620)},
            {"player_id": 11, "player_name": "Reliever One", "stat": _stat("60.0", 60, 0, 48, 18, 20, 72, 240)},
            {"player_id": 12, "player_name": "Reliever Two", "stat": _stat("50.0", 55, 1, 42, 16, 18, 60, 205)},
            {"player_id": 13, "player_name": "Reliever Three", "stat": _stat("40.0", 48, 2, 34, 14, 17, 44, 168)},
            {"player_id": 14, "player_name": "Reliever Four", "stat": _stat("30.0", 40, 0, 28, 10, 12, 34, 128)},
            {"player_id": 15, "player_name": "Other Starter", "stat": _stat("120.0", 22, 20, 110, 35, 50, 130, 500)},
        ],
    }


def _recent() -> dict:
    return {
        "status": "VERIFIED",
        "source": "Official MLB prior-day pitching workloads",
        "days": [
            {"offset": 1, "status": "VERIFIED", "rows": [
                {"player_id": 11, "pitches": 35},
                {"player_id": 12, "pitches": 10},
                {"player_id": 14, "pitches": 5},
            ]},
            {"offset": 2, "status": "VERIFIED", "rows": [
                {"player_id": 12, "pitches": 12},
            ]},
            {"offset": 3, "status": "VERIFIED", "rows": [
                {"player_id": 13, "pitches": 18},
            ]},
        ],
    }


def _savant() -> dict:
    frame = pd.DataFrame(
        [
            {"player_id": 11, "pa": 250, "xera": 3.20, "est_ba": 0.220},
            {"player_id": 12, "pa": 200, "xera": 3.80, "est_ba": 0.235},
            {"player_id": 13, "pa": 160, "xera": 4.40, "est_ba": 0.250},
            {"player_id": 14, "pa": 120, "xera": 4.80, "est_ba": 0.260},
        ]
    )
    return {"status": "VERIFIED", "frame": frame, "source": "Baseball Savant expected statistics"}


def _starter_profile() -> dict:
    return {
        "ip_per_start": 5.8,
        "recent5": {"status": "VERIFIED", "ip_per_start": 5.2},
    }


def test_resolve_opponent_team_id_from_selected_side():
    games = pd.DataFrame([
        {"game_pk": 1001, "away_team_id": 1, "home_team_id": 2},
    ])
    away = _foundation()
    assert bp.resolve_opponent_team_id(games, away) == 2
    home = {**away, "side": "home"}
    assert bp.resolve_opponent_team_id(games, home) == 1


def test_reliever_classification_excludes_starter_and_rotation_arms():
    relief = _stat("30.0", 40, 2, 25, 10, 10, 35, 125)
    starter = _stat("120.0", 22, 20, 100, 30, 40, 120, 480)
    hybrid = _stat("70.0", 30, 6, 60, 20, 25, 75, 290)
    assert bp.is_reliever(relief, starter_id=10, player_id=11)
    assert not bp.is_reliever(relief, starter_id=11, player_id=11)
    assert not bp.is_reliever(starter, starter_id=10, player_id=15)
    assert bp.is_reliever(hybrid, starter_id=10, player_id=16)


def test_fatigue_rules_gate_heavy_and_back_to_back_usage():
    limited = bp.fatigue_status(30, 0, True)
    watch = bp.fatigue_status(10, 12, True)
    ready = bp.fatigue_status(0, 0, True)
    unknown = bp.fatigue_status(0, 0, False)
    assert limited["status"] == "LIMITED"
    assert limited["availability"] == pytest.approx(0.35)
    assert watch["status"] == "WATCH"
    assert watch["availability"] == pytest.approx(0.65)
    assert ready["status"] == "READY"
    assert ready["availability"] == pytest.approx(1.0)
    assert unknown["status"] == "UNKNOWN"
    assert unknown["availability"] is None


def test_starter_to_bullpen_exposure_is_nominal_inning_share_only():
    exposure = bp.starter_to_bullpen_exposure({
        "ip_per_start": 6.0,
        "recent5": {"status": "VERIFIED", "ip_per_start": 5.0},
    })
    assert exposure["status"] == "VERIFIED"
    assert exposure["starter_ip"] == pytest.approx(5.65)
    assert exposure["bullpen_ip"] == pytest.approx(3.35)
    assert exposure["bullpen_inning_share"] == pytest.approx(3.35 / 9.0)
    assert "PA" not in exposure["basis"]


def test_complete_bullpen_profile_aggregates_skill_expected_stats_hands_and_workload():
    result = bp.build_bullpen_profile(
        _foundation(), 2, _active(), _season(), _recent(), _savant(), _starter_profile()
    )
    assert result["reliever_count"] == 4
    assert result["bullpen_innings"] == pytest.approx(180.0)
    assert result["era"] == pytest.approx(9.0 * 67 / 180.0)
    assert result["whip"] == pytest.approx((152 + 58) / 180.0)
    assert result["k_pct"] == pytest.approx(210 / 741)
    assert result["bb_pct"] == pytest.approx(58 / 741)

    expected_xera = (3.2 * 250 + 3.8 * 200 + 4.4 * 160 + 4.8 * 120) / 730
    expected_xba = (0.220 * 250 + 0.235 * 200 + 0.250 * 160 + 0.260 * 120) / 730
    assert result["xera"] == pytest.approx(expected_xera)
    assert result["xba_allowed"] == pytest.approx(expected_xba)
    assert result["expected_stats_pa"] == 730

    assert result["right_share"] == pytest.approx(100 / 180)
    assert result["left_share"] == pytest.approx(80 / 180)
    assert result["hand_coverage"] == pytest.approx(1.0)
    assert result["limited_count"] == 1
    assert result["watch_count"] == 1
    assert result["ready_count"] == 2
    assert result["unknown_count"] == 0
    assert result["availability_index"] is not None

    assert result["bullpen_quality_score"] is not None
    assert result["bullpen_path_score"] is not None
    assert result["bullpen_data_score"] == 100
    assert result["bullpen_data_label"] == "ELITE BULLPEN DATA"
    assert result["expected_bullpen_ip"] == pytest.approx(9.0 - (0.65 * 5.8 + 0.35 * 5.2))


def test_missing_expected_stats_stay_missing_instead_of_being_fabricated():
    result = bp.build_bullpen_profile(
        _foundation(),
        2,
        _active(),
        _season(),
        _recent(),
        {"status": "PENDING", "frame": None, "source": "unavailable"},
        _starter_profile(),
    )
    assert result["xera"] is None
    assert result["xba_allowed"] is None
    assert result["expected_stats_pa"] == 0
    assert result["bullpen_data_score"] < 100
    assert result["bullpen_quality_score"] is not None


def test_step8_is_context_only_and_contains_no_game_probability_engine():
    assert player.PROBABILITY_IMPACT == "NONE"
    assert player.STEP8_ROLE == "BULLPEN_PATH_CONTEXT_ONLY"
    source = inspect.getsource(player) + inspect.getsource(bp)
    forbidden = [
        "def _simulate",
        "def _calibration_from_verdict",
        "p_one_plus_pre_matchup =",
        "p_two_plus =",
        "def fair_odds",
        "def monte_carlo",
    ]
    for token in forbidden:
        assert token.lower() not in source.lower()


def test_steps_1_through_8_accumulate_in_same_v2_panel_and_legacy_remains_frozen():
    source = inspect.getsource(player.render_player_layer)
    assert source.count("with st.expander(V2_INTELLIGENCE_LABEL") == 1
    for step in range(1, 8):
        assert f"step{step}._render_step{step}(games_df)" in source
    assert "_render_step8(games_df)" in source
    assert "with st.expander(LEGACY_AUDIT_LABEL" in source
    assert "frozen_detail.render_player_layer" in source


def test_hub_routes_to_step8_and_keeps_rankings_and_v1_frozen():
    router_source = inspect.getsource(router)
    hub_source = inspect.getsource(hub)
    assert "mlb_matchup_hub_v37" in router_source
    assert "mlb_matchup_player_v31 as player_layer" in hub_source
    assert "mlb_matchup_rankings_v21 as rankings" in hub_source
    assert hub.FROZEN_V1_PRESENTATION == ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")
    assert "Steps 1-8 active" in hub_source
