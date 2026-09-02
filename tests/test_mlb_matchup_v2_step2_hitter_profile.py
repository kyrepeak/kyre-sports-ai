from pathlib import Path

import pytest

import mlb_matchup_hitter_profile_v1 as profile
import mlb_matchup_player_v25 as step2


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _foundation():
    return {
        "player_id": 592450,
        "player_name": "Example Hitter",
        "team": "Example Team",
        "opponent": "Opponent Team",
        "season": 2026,
        "season_stat": {
            "plateAppearances": 500,
            "atBats": 450,
            "hits": 130,
            "homeRuns": 25,
            "strikeOuts": 100,
            "sacFlies": 5,
            "avg": ".289",
            "gamesPlayed": 130,
        },
        "foundation_ready": True,
    }


def _savant():
    return {
        "source": "Baseball Savant custom leaderboard",
        "pa": 500,
        "ab": 450,
        "hits": 130,
        "xba": 0.280,
        "k_pct": 0.200,
        "whiff_pct": 0.220,
        "zone_contact_pct": 0.840,
        "hard_hit_pct": 0.450,
        "avg_ev": 91.1,
        "barrel_pct": 0.105,
        "bbe": 340,
    }


def _logs():
    return [
        {"AB": 4, "H": 2},
        {"AB": 4, "H": 1},
        {"AB": 4, "H": 0},
        {"AB": 4, "H": 1},
        {"AB": 4, "H": 1},
    ]


def test_savant_custom_request_includes_step2_core_metrics():
    required = {
        "xba",
        "k_percent",
        "hard_hit_percent",
        "iz_contact_percent",
        "whiff_percent",
        "batted_ball",
    }
    assert required.issubset(set(profile.SAVANT_SELECTIONS))


def test_recent_form_is_ab_weighted_and_recency_decayed():
    result = profile.weighted_recent_avg(
        [{"AB": 4, "H": 2}, {"AB": 4, "H": 0}],
        decay=0.5,
    )
    assert result["ab"] == 8
    assert result["hits"] == 2
    assert result["avg"] == pytest.approx(2 / 6)
    assert result["avg"] > 2 / 8


def test_complete_profile_builds_all_required_step2_signals():
    result = profile.build_hitter_profile(_foundation(), _logs(), _savant())
    assert result["season_avg"] == pytest.approx(0.289)
    assert result["hit_per_pa"] == pytest.approx(130 / 500)
    assert result["k_pct"] == pytest.approx(100 / 500)
    assert result["xba"] == pytest.approx(0.280)
    assert result["expected_hits"] == pytest.approx(126.0)
    assert result["contact_pct"] == pytest.approx(0.780)
    assert result["zone_contact_pct"] == pytest.approx(0.840)
    assert result["whiff_pct"] == pytest.approx(0.220)
    assert result["hard_hit_pct"] == pytest.approx(0.450)
    assert result["babip"] == pytest.approx(105 / 330)
    assert result["babip_label"] == "ALIGNED"
    assert result["profile_score"] == 100
    assert result["profile_quality_label"] == "ELITE PROFILE DATA"
    assert sum(result["skill_weights"].values()) == pytest.approx(1.0)


def test_hot_recent_form_is_sample_shrunk_not_allowed_to_dominate():
    logs = [{"AB": 4, "H": 4} for _ in range(5)]
    result = profile.build_hitter_profile(_foundation(), logs, _savant())
    assert result["recent_avg"] == pytest.approx(1.0)
    assert result["skill_weights"]["recent"] < 0.10
    assert result["neutral_hit_skill"] < 0.350
    assert result["neutral_hit_skill"] > 0.280


def test_missing_savant_stays_missing_instead_of_fabricating_metrics():
    result = profile.build_hitter_profile(_foundation(), _logs(), None)
    assert result["xba"] is None
    assert result["expected_hits"] is None
    assert result["whiff_pct"] is None
    assert result["contact_pct"] is None
    assert result["zone_contact_pct"] is None
    assert result["hard_hit_pct"] is None
    assert result["savant_source"] == "UNAVAILABLE"
    assert result["profile_score"] < 100
    assert result["neutral_hit_skill"] is not None


def test_step2_declares_zero_game_probability_impact():
    assert step2.PROBABILITY_IMPACT == "NONE"
    assert step2.STEP2_ROLE == "PLAYER_SKILL_PROFILE_ONLY"
    source = _text("mlb_matchup_player_v25.py") + _text("mlb_matchup_hitter_profile_v1.py")
    for forbidden in (
        "def _simulate",
        "def _calibration_from_verdict",
        "p_one_plus_pre_matchup",
        "p_two_plus",
        "fair_odds",
    ):
        assert forbidden not in source


def test_steps_one_and_two_accumulate_inside_one_v2_panel():
    source = _text("mlb_matchup_player_v25.py")
    assert 'V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"' in source
    assert 'LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"' in source
    assert "with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):" in source
    assert "step1._render_step1(games_df)" in source
    assert "_render_step2(games_df)" in source
    assert "STEP 2 • HITTER TRUE-TALENT HIT PROFILE" in source
    assert "with st.expander(LEGACY_AUDIT_LABEL, expanded=False):" in source


def test_step2_keeps_frozen_v1_as_imported_rollback_not_reimplementation():
    source = _text("mlb_matchup_player_v25.py")
    assert "import mlb_matchup_player_v20 as frozen_detail" in source
    assert "import mlb_matchup_player_v22 as clean" in source
    assert "import mlb_matchup_player_v24 as step1" in source
    assert "frozen_detail.render_player_layer" in source
    assert "clean._render_snapshot" in source


def test_hub_routes_to_step2_and_rankings_remain_frozen():
    hub = _text("mlb_matchup_hub_v31.py")
    entry = _text("mlb_matchup_hub_v27.py")
    assert "import mlb_matchup_player_v25 as player_layer" in hub
    assert "import mlb_matchup_rankings_v21 as rankings" in hub
    assert 'FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")' in hub
    assert "from mlb_matchup_hub_v31 import FROZEN_MATCHUP_CHAIN, VERSION, render_matchup_hub" in entry
