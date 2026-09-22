from pathlib import Path

import pytest

import mlb_matchup_platoon_bvp_v1 as profile
import mlb_matchup_player_v27 as step4


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _foundation(batter_hand="L", starter_hand="R"):
    return {
        "player_id": 592450,
        "player_name": "Example Hitter",
        "team": "Example Team",
        "opponent": "Opponent Team",
        "starter_id": 605400,
        "starter_name": "Example Starter",
        "starter_hand": starter_hand,
        "batter_hand": batter_hand,
        "season": 2026,
        "season_avg": ".280",
        "foundation_ready": True,
    }


def _hitter_split():
    return {
        "status": "VERIFIED",
        "source": "MLB Stats API statSplits",
        "stat": {
            "plateAppearances": 220,
            "atBats": 200,
            "hits": 60,
            "avg": ".300",
            "ops": ".850",
            "strikeOuts": 40,
            "baseOnBalls": 15,
        },
    }


def _pitcher_split():
    return {
        "status": "VERIFIED",
        "source": "MLB Stats API statSplits",
        "stat": {
            "battersFaced": 250,
            "hits": 60,
            "avg": ".245",
            "ops": ".690",
            "strikeOuts": 70,
            "baseOnBalls": 20,
        },
    }


def _tiny_bvp():
    return {
        "status": "VERIFIED",
        "source": "MLB Stats API vsPlayer",
        "stat": {
            "plateAppearances": 5,
            "atBats": 5,
            "hits": 3,
            "homeRuns": 1,
            "strikeOuts": 1,
            "baseOnBalls": 0,
            "avg": ".600",
            "ops": "1.400",
        },
    }


def test_handedness_uses_starter_hand_for_hitter_and_batter_side_for_pitcher():
    result = profile.resolve_handedness("R", "L")
    assert result["hitter_split_code"] == "vr"
    assert result["hitter_split_label"] == "RHP"
    assert result["effective_batter_hand"] == "L"
    assert result["pitcher_split_code"] == "vl"
    assert result["pitcher_split_label"] == "LHB"
    assert result["switch_adjusted"] is False


def test_switch_hitter_resolves_to_opposite_side_of_starter():
    vs_right = profile.resolve_handedness("R", "S")
    assert vs_right["effective_batter_hand"] == "L"
    assert vs_right["pitcher_split_code"] == "vl"
    assert vs_right["switch_adjusted"] is True

    vs_left = profile.resolve_handedness("L", "S")
    assert vs_left["effective_batter_hand"] == "R"
    assert vs_left["pitcher_split_code"] == "vr"
    assert vs_left["switch_adjusted"] is True


def test_tiny_bvp_is_heavily_shrunk_toward_matchup_baseline():
    result = profile.shrink_bvp_avg(0.600, 5, 0.280)
    assert result["reliability"] == pytest.approx(5 / 35)
    assert result["shrunk_avg"] < 0.350
    assert result["shrunk_avg"] > 0.280
    assert abs(result["shrunk_avg"] - 0.280) < abs(0.600 - 0.280)


def test_bvp_reliability_is_capped_even_for_large_samples():
    assert profile.bvp_reliability(5) < 0.20
    assert profile.bvp_reliability(30) == pytest.approx(0.50)
    assert profile.bvp_reliability(500) == pytest.approx(profile.BVP_MAX_RELIABILITY)


def test_complete_step4_profile_builds_splits_bvp_and_context_without_tiny_sample_takeover():
    result = profile.build_platoon_bvp_profile(
        _foundation(),
        _hitter_split(),
        _pitcher_split(),
        _tiny_bvp(),
        0.285,
    )
    assert result["hitter_split_avg"] == pytest.approx(0.300)
    assert result["hitter_split_ops"] == pytest.approx(0.850)
    assert result["hitter_split_k_pct"] == pytest.approx(40 / 220)
    assert result["pitcher_split_avg"] == pytest.approx(0.245)
    assert result["pitcher_split_k_pct"] == pytest.approx(70 / 250)
    assert result["bvp_avg"] == pytest.approx(0.600)
    assert result["bvp_reliability"] < 0.20
    assert result["bvp_shrunk_avg"] < 0.350
    assert result["matchup_data_score"] == 100
    assert result["matchup_data_label"] == "ELITE MATCHUP DATA"
    # A noisy 3-for-5 BvP cannot manufacture a huge hitter edge.
    assert 40 <= result["platoon_context_score"] <= 55
    assert result["platoon_context_components"]["bvp_effective_weight"] < 0.03


def test_verified_no_bvp_history_is_neutral_information_not_negative_signal():
    no_history = {
        "status": "VERIFIED_NO_HISTORY",
        "source": "MLB Stats API vsPlayer",
        "stat": {},
    }
    result = profile.build_platoon_bvp_profile(
        _foundation(),
        _hitter_split(),
        _pitcher_split(),
        no_history,
        0.285,
    )
    assert result["bvp_ab"] == 0
    assert result["bvp_avg"] is None
    assert result["bvp_reliability"] == 0.0
    assert result["bvp_shrunk_avg"] == pytest.approx(result["bvp_baseline_avg"])
    assert result["platoon_context_components"]["bvp_effective_weight"] == 0.0
    assert result["matchup_data_score"] == 98


def test_missing_handedness_fails_closed_for_split_selection():
    result = profile.resolve_handedness("—", "S")
    assert result["hitter_split_code"] is None
    assert result["pitcher_split_code"] is None
    assert result["effective_batter_hand"] == "S"


def test_step4_declares_zero_probability_impact_and_context_only_role():
    assert step4.PROBABILITY_IMPACT == "NONE"
    assert step4.STEP4_ROLE == "PLATOON_BVP_CONTEXT_ONLY"
    source = _text("mlb_matchup_player_v27.py") + _text("mlb_matchup_platoon_bvp_v1.py")
    for forbidden in (
        "def _simulate",
        "def _calibration_from_verdict",
        "p_one_plus_pre_matchup",
        "p_two_plus",
        "fair_odds",
        "monte_carlo",
    ):
        assert forbidden not in source.lower()


def test_steps_one_through_four_accumulate_in_one_v2_panel():
    source = _text("mlb_matchup_player_v27.py")
    assert 'V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"' in source
    assert "with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):" in source
    assert "step1._render_step1(games_df)" in source
    assert "step2._render_step2(games_df)" in source
    assert "step3._render_step3(games_df)" in source
    assert "_render_step4(games_df)" in source
    assert "STEP 4 • PLATOON + BATTER-VS-PITCHER" in source
    assert "with st.expander(LEGACY_AUDIT_LABEL, expanded=False):" in source


def test_step4_fetches_correct_official_split_and_vsplayer_endpoints():
    source = _text("mlb_matchup_platoon_bvp_v1.py")
    assert '"stats": "statSplits"' in source
    assert '"sitCodes": sit_code' in source
    assert '"stats": "vsPlayer"' in source
    assert '"opposingPlayerId": int(pitcher_id)' in source
    assert '"season": int(season)' in source


def test_step4_keeps_prior_steps_and_frozen_v1_as_imported_boundaries():
    source = _text("mlb_matchup_player_v27.py")
    assert "import mlb_matchup_player_v24 as step1" in source
    assert "import mlb_matchup_player_v25 as step2" in source
    assert "import mlb_matchup_player_v26 as step3" in source
    assert "import mlb_matchup_player_v20 as frozen_detail" in source
    assert "import mlb_matchup_player_v22 as clean" in source
    assert "frozen_detail.render_player_layer" in source
    assert "clean._render_snapshot" in source


def test_hub_routes_to_step4_and_rankings_remain_frozen():
    hub = _text("mlb_matchup_hub_v33.py")
    entry = _text("mlb_matchup_hub_v27.py")
    assert "import mlb_matchup_player_v27 as player_layer" in hub
    assert "import mlb_matchup_rankings_v21 as rankings" in hub
    assert 'FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")' in hub
    assert "from mlb_matchup_hub_v33 import FROZEN_MATCHUP_CHAIN, VERSION, render_matchup_hub" in entry
