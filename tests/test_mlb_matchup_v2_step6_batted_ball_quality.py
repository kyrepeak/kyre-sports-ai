from pathlib import Path

import pandas as pd
import pytest

import mlb_matchup_batted_ball_v1 as bb
import mlb_matchup_player_v29 as step6


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _foundation():
    return {
        "player_id": 592450,
        "player_name": "Example Hitter",
        "batter_hand": "R",
        "season": 2026,
        "foundation_ready": True,
    }


def _frame(n: int = 40) -> pd.DataFrame:
    rows = []
    for i in range(n):
        quarter = i % 4
        if quarter == 0:
            hx, bb_type = 90.0, "ground_ball"
        elif quarter == 1:
            hx, bb_type = 125.42, "line_drive"
        elif quarter == 2:
            hx, bb_type = 160.0, "fly_ball"
        else:
            hx, bb_type = 125.42, "popup"
        rows.append(
            {
                "batter": 592450,
                "pitch_type": "FF",
                "launch_speed": 100.0 if i % 2 == 0 else 90.0,
                "launch_angle": 15.0 if i % 2 == 0 else 0.0,
                "launch_speed_angle": 6 if i % 2 == 0 else 4,
                "estimated_ba_using_speedangle": 0.40 if i % 2 == 0 else 0.20,
                "bb_type": bb_type,
                "hc_x": hx,
                "hc_y": 100.0,
                "stand": "R",
            }
        )
    return pd.DataFrame(rows)


def test_sample_reliability_has_hard_floor_and_full_sample_cap():
    assert bb.sample_reliability(19) == 0.0
    assert bb.sample_reliability(20) == pytest.approx(20 / 160)
    assert bb.sample_reliability(160) == 1.0
    assert bb.sample_reliability(300) == 1.0


def test_batted_ball_metrics_cover_step6_core_signals():
    result = bb.batted_ball_metrics(_frame())
    assert result["bbe"] == 40
    assert result["avg_ev"] == pytest.approx(95.0)
    assert result["max_ev"] == pytest.approx(100.0)
    assert result["hard_hit_pct"] == pytest.approx(0.5)
    assert result["barrel_pct"] == pytest.approx(0.5)
    assert result["avg_launch_angle"] == pytest.approx(7.5)
    assert result["sweet_spot_pct"] == pytest.approx(0.5)
    assert result["xba_contact"] == pytest.approx(0.30)
    assert result["ground_ball_pct"] == pytest.approx(0.25)
    assert result["line_drive_pct"] == pytest.approx(0.25)
    assert result["fly_ball_pct"] == pytest.approx(0.25)
    assert result["popup_pct"] == pytest.approx(0.25)
    assert result["spray_bip"] == 40
    assert result["pull_pct"] == pytest.approx(0.25)
    assert result["center_pct"] == pytest.approx(0.50)
    assert result["oppo_pct"] == pytest.approx(0.25)


def test_contact_quality_score_is_shrunk_toward_neutral_by_sample_reliability():
    payload = {"status": "VERIFIED", "rows": 40, "frame": _frame()}
    result = bb.build_batted_ball_profile(_foundation(), payload)
    assert result["batted_ball_reliability"] == pytest.approx(0.25)
    assert result["batted_ball_raw_score"] is not None
    assert result["batted_ball_score"] is not None
    assert abs(result["batted_ball_score"] - 50) <= abs(result["batted_ball_raw_score"] - 50)
    assert result["batted_ball_data_score"] == 100


def test_thin_bbe_sample_does_not_issue_contact_quality_index():
    payload = {"status": "VERIFIED", "rows": 10, "frame": _frame(10)}
    result = bb.build_batted_ball_profile(_foundation(), payload)
    assert result["batted_ball_reliability"] == 0.0
    assert result["batted_ball_score"] is None
    assert result["batted_ball_label"] == "PENDING"


def test_missing_statcast_stays_missing_instead_of_fabricating_contact_metrics():
    result = bb.build_batted_ball_profile(_foundation(), None)
    assert result["hitter_statcast_status"] == "PENDING"
    assert result["bbe"] == 0
    assert result["avg_ev"] is None
    assert result["hard_hit_pct"] is None
    assert result["barrel_pct"] is None
    assert result["xba_contact"] is None
    assert result["batted_ball_score"] is None


def test_step6_reuses_existing_statcast_cache_without_new_network_client():
    source = _text("mlb_matchup_batted_ball_v1.py")
    assert "import mlb_matchup_rankings_v17 as statcast_feed" in source
    assert "statcast_feed._statcast_rows" in source
    assert "requests.get" not in source
    assert "requests.Session" not in source


def test_step6_declares_zero_game_probability_impact():
    assert step6.PROBABILITY_IMPACT == "NONE"
    assert step6.STEP6_ROLE == "BATTED_BALL_QUALITY_CONTEXT_ONLY"
    source = _text("mlb_matchup_player_v29.py") + _text("mlb_matchup_batted_ball_v1.py")
    for forbidden in (
        "def _simulate",
        "def _calibration_from_verdict",
        "p_one_plus_pre_matchup =",
        "p_two_plus =",
        "def fair_odds",
        "def monte_carlo",
    ):
        assert forbidden not in source


def test_steps_one_through_six_accumulate_inside_one_v2_panel():
    source = _text("mlb_matchup_player_v29.py")
    assert "step1._render_step1(games_df)" in source
    assert "step2._render_step2(games_df)" in source
    assert "step3._render_step3(games_df)" in source
    assert "step4._render_step4(games_df)" in source
    assert "step5._render_step5(games_df)" in source
    assert "_render_step6(games_df)" in source
    assert "STEP 6 • BATTED-BALL QUALITY" in source
    assert "frozen_detail.render_player_layer" in source


def test_hub_routes_to_step6_and_daily_rankings_remain_frozen():
    hub = _text("mlb_matchup_hub_v35.py")
    entry = _text("mlb_matchup_hub_v27.py")
    assert "import mlb_matchup_player_v29 as player_layer" in hub
    assert "import mlb_matchup_rankings_v21 as rankings" in hub
    assert 'FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")' in hub
    assert "from mlb_matchup_hub_v35 import FROZEN_MATCHUP_CHAIN, VERSION, render_matchup_hub" in entry
