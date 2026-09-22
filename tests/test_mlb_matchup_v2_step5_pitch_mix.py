from pathlib import Path

import pandas as pd
import pytest

import mlb_matchup_pitch_mix_v1 as pitch_mix
import mlb_matchup_player_v28 as step5


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _foundation(starter_hand="R"):
    return {
        "player_id": 100,
        "player_name": "Example Hitter",
        "starter_id": 200,
        "starter_name": "Example Starter",
        "starter_hand": starter_hand,
        "batter_hand": "L",
        "season": 2026,
        "foundation_ready": True,
    }


def _rows(code, n, hand="R", xba=0.300, ev=91.0, description="foul"):
    return [
        {
            "pitch_type": code,
            "p_throws": hand,
            "estimated_ba_using_speedangle": xba,
            "launch_speed": ev,
            "description": description,
            "batter": 100,
            "pitcher": 999,
        }
        for _ in range(n)
    ]


def test_sample_reliability_has_hard_floor_and_full_sample_cap():
    assert pitch_mix.sample_reliability(0) == 0.0
    assert pitch_mix.sample_reliability(7) == 0.0
    assert pitch_mix.sample_reliability(8) == pytest.approx(8 / 45)
    assert pitch_mix.sample_reliability(45) == 1.0
    assert pitch_mix.sample_reliability(100) == 1.0


def test_starter_arsenal_uses_actual_pitch_counts_and_usage():
    frame = pd.DataFrame(
        [{"pitch_type": "FF"}] * 60
        + [{"pitch_type": "SL"}] * 30
        + [{"pitch_type": "CH"}] * 10
    )
    arsenal = pitch_mix.starter_arsenal_from_frame(frame)
    assert arsenal[0]["code"] == "FF"
    assert arsenal[0]["usage"] == pytest.approx(0.60)
    assert arsenal[1]["usage"] == pytest.approx(0.30)
    assert arsenal[2]["usage"] == pytest.approx(0.10)
    assert sum(x["usage"] for x in arsenal) == pytest.approx(1.0)


def test_same_hand_filter_is_only_applied_after_sample_gate():
    rich = pd.DataFrame(_rows("FF", 80, hand="R") + _rows("FF", 20, hand="L"))
    filtered, info = pitch_mix.filter_hitter_for_starter_hand(rich, "R")
    assert info["applied"] is True
    assert len(filtered) == 80
    assert set(filtered["p_throws"].unique()) == {"R"}

    thin = pd.DataFrame(_rows("FF", 50, hand="R") + _rows("FF", 30, hand="L"))
    filtered, info = pitch_mix.filter_hitter_for_starter_hand(thin, "R")
    assert info["applied"] is False
    assert len(filtered) == 80
    assert info["same_hand_rows"] == 50


def test_pitch_type_performance_computes_contact_whiff_xba_ev_and_hard_hit():
    frame = pd.DataFrame(
        _rows("FF", 10, xba=0.320, ev=96.0, description="foul")
        + _rows("FF", 5, xba=0.280, ev=90.0, description="swinging_strike")
        + _rows("SL", 10, xba=0.100, ev=80.0, description="swinging_strike")
    )
    perf = pitch_mix.pitch_type_performance(frame, "FF")
    assert perf["pitches"] == 15
    assert perf["swings"] == 15
    assert perf["whiffs"] == 5
    assert perf["contact_pct"] == pytest.approx(10 / 15)
    assert perf["whiff_pct"] == pytest.approx(5 / 15)
    assert perf["xba"] == pytest.approx((10 * 0.320 + 5 * 0.280) / 15)
    assert perf["avg_ev"] == pytest.approx((10 * 96.0 + 5 * 90.0) / 15)
    assert perf["hard_hit_pct"] == pytest.approx(10 / 15)


def test_sub_minimum_pitch_type_gets_zero_effective_weight():
    pitcher = pd.DataFrame([{"pitch_type": "FF"}] * 50 + [{"pitch_type": "SL"}] * 50)
    hitter = pd.DataFrame(_rows("FF", 45) + _rows("SL", 7, xba=0.500, ev=110.0))
    result = pitch_mix.build_pitch_mix_profile(
        _foundation(),
        {"status": "VERIFIED", "rows": len(pitcher), "frame": pitcher},
        {"status": "VERIFIED", "rows": len(hitter), "frame": hitter},
    )
    by_code = {row["code"]: row for row in result["pitch_rows"]}
    assert by_code["SL"]["reliability"] == 0.0
    assert by_code["SL"]["effective_weight"] == 0.0
    assert by_code["FF"]["effective_weight"] > 0.0


def test_starter_usage_and_sample_reliability_drive_weighted_matchup_score():
    pitcher = pd.DataFrame([{"pitch_type": "FF"}] * 80 + [{"pitch_type": "SL"}] * 20)
    hitter = pd.DataFrame(
        _rows("FF", 60, xba=0.360, ev=96.0, description="foul")
        + _rows("SL", 60, xba=0.140, ev=82.0, description="swinging_strike")
    )
    result = pitch_mix.build_pitch_mix_profile(
        _foundation(),
        {"status": "VERIFIED", "rows": len(pitcher), "frame": pitcher},
        {"status": "VERIFIED", "rows": len(hitter), "frame": hitter},
    )
    assert result["pitch_mix_score"] is not None
    assert result["pitch_mix_score"] > 50
    assert result["weighted_xba"] > 0.250
    assert result["pitch_mix_coverage"] > 0.90


def test_missing_statcast_fails_closed_without_invented_matchup_score():
    result = pitch_mix.build_pitch_mix_profile(_foundation(), None, None)
    assert result["arsenal"] == []
    assert result["pitch_rows"] == []
    assert result["pitch_mix_score"] is None
    assert result["weighted_xba"] is None
    assert result["weighted_contact_pct"] is None
    assert result["pitch_mix_coverage"] == 0.0
    assert result["pitch_mix_data_score"] < 40


def test_step5_declares_zero_probability_impact_and_context_only_role():
    assert step5.PROBABILITY_IMPACT == "NONE"
    assert step5.STEP5_ROLE == "PITCH_MIX_CONTEXT_ONLY"
    source = _text("mlb_matchup_player_v28.py") + _text("mlb_matchup_pitch_mix_v1.py")
    for forbidden in (
        "def _simulate",
        "def _calibration_from_verdict",
        "p_one_plus_pre_matchup =",
        "p_two_plus =",
        "def fair_odds",
        "def monte_carlo",
    ):
        assert forbidden not in source


def test_steps_one_through_five_accumulate_inside_one_v2_panel():
    source = _text("mlb_matchup_player_v28.py")
    assert 'V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"' in source
    assert "step1._render_step1(games_df)" in source
    assert "step2._render_step2(games_df)" in source
    assert "step3._render_step3(games_df)" in source
    assert "step4._render_step4(games_df)" in source
    assert "_render_step5(games_df)" in source
    assert "STEP 5 • PITCH-MIX MATCHUP" in source
    assert "with st.expander(LEGACY_AUDIT_LABEL, expanded=False):" in source


def test_step5_uses_shared_statcast_cache_not_a_new_network_client():
    source = _text("mlb_matchup_pitch_mix_v1.py")
    assert "import mlb_matchup_rankings_v17 as statcast_feed" in source
    assert "statcast_feed._statcast_rows" in source
    assert "requests.get" not in source
    assert "requests.Session" not in source


def test_hub_routes_to_step5_while_daily_rankings_stay_frozen():
    hub = _text("mlb_matchup_hub_v34.py")
    entry = _text("mlb_matchup_hub_v27.py")
    assert "import mlb_matchup_player_v28 as player_layer" in hub
    assert "import mlb_matchup_rankings_v21 as rankings" in hub
    assert 'FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")' in hub
    assert "from mlb_matchup_hub_v34 import FROZEN_MATCHUP_CHAIN, VERSION, render_matchup_hub" in entry
