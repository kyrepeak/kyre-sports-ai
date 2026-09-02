from pathlib import Path

import pandas as pd
import pytest

import mlb_matchup_pitcher_profile_v1 as profile
import mlb_matchup_player_v26 as step3


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
        "starter_id": 654321,
        "starter_name": "Example Starter",
        "starter_hand": "R",
        "foundation_ready": True,
    }


def _season_stat():
    return {
        "gamesStarted": 25,
        "inningsPitched": "150.0",
        "hits": 130,
        "earnedRuns": 55,
        "homeRuns": 15,
        "baseOnBalls": 40,
        "hitBatsmen": 5,
        "strikeOuts": 180,
        "battersFaced": 610,
        "era": "3.30",
        "whip": "1.13",
    }


def _logs():
    rows = []
    for i in range(10):
        rows.append(
            {
                "date": f"2026-08-{31-i:02d}",
                "ip": 6.0,
                "hits": 5,
                "earned_runs": 2,
                "home_runs": 1,
                "walks": 1,
                "hit_batters": 0,
                "strikeouts": 7,
                "batters_faced": 24,
                "pitches": 96,
                "games_started": 1,
            }
        )
    return rows


def _savant():
    return {
        "source": "Baseball Savant expected statistics",
        "pa": 610,
        "bip": 390,
        "ba_allowed": 0.226,
        "xba_allowed": 0.221,
        "era": 3.30,
        "xera": 3.10,
        "xwoba_allowed": 0.285,
    }


def _tto():
    return {
        "status": "VERIFIED",
        "segments": {
            "1st": {"bf": 180, "ab": 160, "hits": 34, "avg": 0.2125, "k_pct": 0.32},
            "2nd": {"bf": 165, "ab": 148, "hits": 35, "avg": 0.2365, "k_pct": 0.29},
            "3rd+": {"bf": 90, "ab": 82, "hits": 22, "avg": 0.2683, "k_pct": 0.24},
        },
        "third_time_avg_delta": 0.0558,
        "third_time_label": "MATERIAL 3RD-TIME FADE",
        "terminal_pa": 435,
    }


def test_baseball_innings_notation_is_converted_to_true_innings():
    assert profile._ip("6.0") == pytest.approx(6.0)
    assert profile._ip("6.1") == pytest.approx(6 + 1 / 3)
    assert profile._ip("6.2") == pytest.approx(6 + 2 / 3)


def test_fip_uses_supplied_current_season_league_constant():
    result = profile.calculate_fip(_season_stat(), 3.12)
    expected = (13 * 15 + 3 * (40 + 5) - 2 * 180) / 150 + 3.12
    assert result == pytest.approx(expected)


def test_fip_stays_missing_when_current_season_constant_is_missing():
    assert profile.calculate_fip(_season_stat(), None) is None


def test_recent_form_aggregates_l5_without_averaging_era_rows():
    result = profile.recent_form(_logs(), 5)
    assert result["starts"] == 5
    assert result["ip"] == pytest.approx(30.0)
    assert result["era"] == pytest.approx(3.0)
    assert result["whip"] == pytest.approx(1.0)
    assert result["h9"] == pytest.approx(7.5)
    assert result["k_pct"] == pytest.approx(35 / 120)
    assert result["bb_pct"] == pytest.approx(5 / 120)
    assert result["pitches_per_start"] == pytest.approx(96.0)


def test_tto_profile_detects_third_time_fade_from_terminal_pa_rows():
    rows = []
    at_bat = 1
    for game in range(12):
        game_pk = 900000 + game
        batter = 1000 + game
        for turn, event in enumerate(("field_out", "single", "single"), 1):
            rows.append(
                {
                    "game_pk": game_pk,
                    "batter": batter,
                    "events": event,
                    "at_bat_number": at_bat,
                }
            )
            at_bat += 1
    result = profile.tto_profile_from_frame(pd.DataFrame(rows))
    assert result["status"] == "VERIFIED"
    assert result["segments"]["1st"]["ab"] == 12
    assert result["segments"]["1st"]["avg"] == pytest.approx(0.0)
    assert result["segments"]["2nd"]["avg"] == pytest.approx(1.0)
    assert result["segments"]["3rd+"]["avg"] == pytest.approx(1.0)
    assert result["third_time_avg_delta"] == pytest.approx(1.0)
    assert result["third_time_label"] == "MATERIAL 3RD-TIME FADE"


def test_complete_step3_profile_builds_required_starter_signals():
    result = profile.build_pitcher_profile(
        _foundation(),
        _season_stat(),
        _logs(),
        _savant(),
        3.12,
        _tto(),
    )
    assert result["era"] == pytest.approx(3.30)
    assert result["xera"] == pytest.approx(3.10)
    assert result["fip"] is not None
    assert result["whip"] == pytest.approx(1.13)
    assert result["h9"] == pytest.approx(7.8)
    assert result["k_pct"] == pytest.approx(180 / 610)
    assert result["bb_pct"] == pytest.approx(40 / 610)
    assert result["xba_allowed"] == pytest.approx(0.221)
    assert result["recent5"]["status"] == "VERIFIED"
    assert result["recent10"]["status"] == "VERIFIED"
    assert result["ip_per_start"] == pytest.approx(6.0)
    assert result["pitches_per_start"] == pytest.approx(96.0)
    assert result["third_time_label"] == "MATERIAL 3RD-TIME FADE"
    assert result["starter_profile_score"] == 100
    assert result["starter_profile_label"] == "ELITE STARTER DATA"
    assert result["starter_strength_score"] is not None


def test_missing_expected_stats_and_fip_are_not_fabricated():
    result = profile.build_pitcher_profile(
        _foundation(),
        _season_stat(),
        _logs(),
        None,
        None,
        {"status": "PENDING", "segments": {}},
    )
    assert result["xera"] is None
    assert result["xba_allowed"] is None
    assert result["fip"] is None
    assert result["savant_source"] == "UNAVAILABLE"
    assert result["fip_constant_source"] == "UNAVAILABLE"
    assert result["third_time_avg_delta"] is None
    assert result["starter_profile_score"] < 100


def test_stronger_pitcher_rates_produce_higher_descriptive_starter_index():
    strong = profile.starter_strength_score(
        {"xera": 2.70, "fip": 2.90, "era": 2.80, "whip": 1.02, "xba_allowed": 0.205, "k_pct": 0.31, "bb_pct": 0.06}
    )
    weak = profile.starter_strength_score(
        {"xera": 5.40, "fip": 5.10, "era": 5.25, "whip": 1.55, "xba_allowed": 0.285, "k_pct": 0.17, "bb_pct": 0.11}
    )
    assert strong["score"] > weak["score"]
    assert strong["coverage"] == pytest.approx(1.0)
    assert weak["coverage"] == pytest.approx(1.0)


def test_step3_declares_zero_probability_impact():
    assert step3.PROBABILITY_IMPACT == "NONE"
    assert step3.STEP3_ROLE == "STARTER_QUALITY_CONTEXT_ONLY"
    source = _text("mlb_matchup_player_v26.py") + _text("mlb_matchup_pitcher_profile_v1.py")
    for forbidden in (
        "def _simulate",
        "def _calibration_from_verdict",
        "p_one_plus_pre_matchup",
        "p_two_plus",
        "fair_odds",
        "monte_carlo",
    ):
        assert forbidden not in source.lower()


def test_steps_one_two_and_three_accumulate_inside_one_v2_panel():
    source = _text("mlb_matchup_player_v26.py")
    assert 'V2_INTELLIGENCE_LABEL = "🧠 Matchup Intelligence V2 — new steps"' in source
    assert 'LEGACY_AUDIT_LABEL = "🧊 Legacy V1 Matchup audit — frozen"' in source
    assert "with st.expander(V2_INTELLIGENCE_LABEL, expanded=True):" in source
    assert "step1._render_step1(games_df)" in source
    assert "step2._render_step2(games_df)" in source
    assert "_render_step3(games_df)" in source
    assert "STEP 3 • STARTING PITCHER QUALITY" in source
    assert "with st.expander(LEGACY_AUDIT_LABEL, expanded=False):" in source


def test_step3_keeps_certified_step2_and_frozen_v1_as_imported_layers():
    source = _text("mlb_matchup_player_v26.py")
    assert "import mlb_matchup_player_v24 as step1" in source
    assert "import mlb_matchup_player_v25 as step2" in source
    assert "import mlb_matchup_player_v20 as frozen_detail" in source
    assert "import mlb_matchup_player_v22 as clean" in source
    assert "frozen_detail.render_player_layer" in source
    assert "clean._render_snapshot" in source


def test_hub_routes_to_step3_and_daily_rankings_remain_frozen():
    hub = _text("mlb_matchup_hub_v32.py")
    entry = _text("mlb_matchup_hub_v27.py")
    assert "import mlb_matchup_player_v26 as player_layer" in hub
    assert "import mlb_matchup_rankings_v21 as rankings" in hub
    assert 'FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")' in hub
    assert "from mlb_matchup_hub_v32 import FROZEN_MATCHUP_CHAIN, VERSION, render_matchup_hub" in entry
