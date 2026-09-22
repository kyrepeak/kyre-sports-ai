from __future__ import annotations

from pathlib import Path

import pandas as pd

import mlb_matchup_recent_stability_v1 as recent

ROOT = Path(__file__).resolve().parents[1]


def _logs(n: int, *, hits_pattern=None, start_pk: int = 1000):
    rows = []
    pattern = hits_pattern or [1]
    for i in range(n):
        hits = pattern[i % len(pattern)]
        rows.append(
            {
                "date": f"2026-08-{31-i:02d}" if i < 31 else "2026-07-31",
                "game_pk": start_pk + i,
                "pa": 4,
                "ab": 4,
                "hits": hits,
                "strikeouts": 1,
                "walks": 0,
                "home_runs": 0,
            }
        )
    return rows


def test_short_window_reliability_is_heavily_shrunk():
    assert recent.window_reliability(5, 5) == 0.1
    assert recent.window_reliability(20, 5) < 0.31
    assert recent.window_reliability(80, 20) == 0.4


def test_window_summary_shrinks_hot_small_sample_to_season():
    logs = [
        {"date": "2026-08-31", "game_pk": 1, "pa": 5, "ab": 5, "hits": 3, "strikeouts": 1, "walks": 0, "home_runs": 0}
    ]
    d = recent.window_summary(logs, 5, 0.250)
    assert d["avg"] == 0.600
    assert d["reliability"] == 0.1
    assert abs(d["shrunk_avg"] - 0.285) < 1e-9
    assert abs(d["avg_delta_vs_season"] - 0.035) < 1e-9


def test_pregame_filter_excludes_selected_date_and_future_rows():
    rows = [
        {"date": "2026-09-02", "game_pk": 3},
        {"date": "2026-09-01", "game_pk": 2},
        {"date": "2026-08-31", "game_pk": 1},
    ]
    out = recent.pregame_logs(rows, "2026-09-02")
    assert [row["game_pk"] for row in out] == [2, 1]


def test_contact_summary_classifies_swings_whiffs_and_quality():
    frame = pd.DataFrame(
        {
            "description": ["swinging_strike", "foul", "hit_into_play", "called_strike", "foul_tip"],
            "launch_speed": [None, None, 101.0, 96.0, 88.0],
            "estimated_ba_using_speedangle": [None, None, 0.700, 0.300, 0.200],
        }
    )
    d = recent.contact_summary(frame)
    assert d["swings"] == 4
    assert d["whiffs"] == 1
    assert abs(d["contact_pct"] - 0.75) < 1e-9
    assert abs(d["whiff_pct"] - 0.25) < 1e-9
    assert d["bbe"] == 3
    assert d["avg_ev"] == 95.0
    assert abs(d["hard_hit_pct"] - (2 / 3)) < 1e-9
    assert abs(d["xba_contact"] - 0.4) < 1e-9


def test_attach_contact_windows_matches_official_game_ids():
    windows = {
        5: {"game_pks": [1], "ab": 4, "reliability": 0.08},
        10: {"game_pks": [1, 2], "ab": 8, "reliability": 0.10},
        20: {"game_pks": [1, 2, 3], "ab": 12, "reliability": 0.09},
    }
    frame = pd.DataFrame(
        {
            "game_pk": [1, 2, 3, 99],
            "description": ["hit_into_play"] * 4,
            "launch_speed": [100.0, 99.0, 98.0, 50.0],
            "estimated_ba_using_speedangle": [0.7, 0.6, 0.5, 0.0],
        }
    )
    out = recent.attach_contact_windows(windows, frame)
    assert out[5]["contact"]["pitches"] == 1
    assert out[10]["contact"]["pitches"] == 2
    assert out[20]["contact"]["pitches"] == 3


def test_tiny_hot_streak_cannot_create_extreme_form_score():
    season_contact = {"xba_contact": 0.320, "hard_hit_pct": 0.400}
    windows = {
        5: {
            "reliability": 0.10,
            "shrunk_avg": 0.285,
            "hits_per_game": 3.0,
            "k_pct": 0.05,
            "contact": {"xba_contact": 0.700, "hard_hit_pct": 1.0, "contact_reliability": 0.10},
        },
        10: {
            "reliability": 0.20,
            "shrunk_avg": 0.265,
            "hits_per_game": 1.2,
            "k_pct": 0.18,
            "contact": {"xba_contact": 0.350, "hard_hit_pct": 0.45, "contact_reliability": 0.20},
        },
        20: {
            "reliability": 0.30,
            "shrunk_avg": 0.255,
            "hits_per_game": 1.0,
            "k_pct": 0.20,
            "contact": {"xba_contact": 0.325, "hard_hit_pct": 0.41, "contact_reliability": 0.30},
        },
    }
    out = recent.recent_form_index(windows, 0.250, 0.21, 1.0, season_contact)
    assert out["score"] is not None
    assert 35 <= out["score"] <= 65
    assert out["score"] < 65


def test_stability_index_requires_sample_and_rewards_consistency():
    low = {
        5: {"shrunk_avg": 0.250, "k_pct": 0.20, "ab": 5, "contact": {}},
        10: {"shrunk_avg": 0.251, "k_pct": 0.20, "ab": 10, "contact": {}},
        20: {"shrunk_avg": 0.252, "k_pct": 0.20, "ab": 20, "contact": {}},
    }
    low_out = recent.stability_index(low)
    assert low_out["label"] == "LOW SAMPLE"

    stable = {
        5: {"shrunk_avg": 0.251, "k_pct": 0.205, "ab": 20, "contact": {"hard_hit_pct": 0.41, "xba_contact": 0.32}},
        10: {"shrunk_avg": 0.249, "k_pct": 0.200, "ab": 40, "contact": {"hard_hit_pct": 0.40, "xba_contact": 0.31}},
        20: {"shrunk_avg": 0.250, "k_pct": 0.202, "ab": 80, "contact": {"hard_hit_pct": 0.405, "xba_contact": 0.315}},
    }
    stable_out = recent.stability_index(stable)
    assert stable_out["score"] >= 80
    assert stable_out["label"] == "VERY STABLE"


def test_build_profile_is_pregame_shrunk_and_context_only():
    logs = []
    for i in range(20):
        day = 31 - i if i < 31 else 1
        logs.append(
            {
                "date": f"2026-08-{day:02d}",
                "game_pk": 500 + i,
                "pa": 4,
                "ab": 4,
                "hits": 1 if i % 3 else 2,
                "strikeouts": 1,
                "walks": 0,
                "home_runs": 0,
            }
        )
    statcast = pd.DataFrame(
        {
            "game_pk": [500 + (i % 20) for i in range(80)],
            "description": ["hit_into_play", "foul", "swinging_strike", "hit_into_play"] * 20,
            "launch_speed": [98.0, None, None, 90.0] * 20,
            "estimated_ba_using_speedangle": [0.55, None, None, 0.25] * 20,
        }
    )
    foundation = {
        "player_id": 123,
        "player_name": "Test Hitter",
        "game_date": "2026-09-02",
        "season_stat": {
            "avg": ".250",
            "plateAppearances": 500,
            "hits": 120,
            "gamesPlayed": 130,
            "strikeOuts": 105,
        },
    }
    out = recent.build_recent_stability_profile(
        foundation,
        {"status": "VERIFIED", "logs": logs, "source": "Official MLB hitter game log"},
        {"status": "VERIFIED", "frame": statcast, "rows": len(statcast)},
    )
    assert out["recent_log_games"] == 20
    assert out["l5"]["games"] == 5
    assert out["l10"]["games"] == 10
    assert out["l20"]["games"] == 20
    assert out["recent_form_score"] is not None
    assert 35 <= out["recent_form_score"] <= 65
    assert out["recent_data_score"] >= 75


def test_step10_player_declares_no_probability_impact_and_role():
    text = (ROOT / "mlb_matchup_player_v33.py").read_text()
    assert 'PROBABILITY_IMPACT = "NONE"' in text
    assert 'STEP10_ROLE = "RECENT_FORM_STABILITY_CONTEXT_ONLY"' in text
    forbidden = ["def _simulate", "def fair_odds", "def monte_carlo", "p_one_plus_pre_matchup =", "p_two_plus ="]
    assert all(marker not in text for marker in forbidden)


def test_steps_1_through_10_accumulate_in_one_v2_panel():
    text = (ROOT / "mlb_matchup_player_v33.py").read_text()
    for marker in (
        "step1._render_step1",
        "step2._render_step2",
        "step3._render_step3",
        "step4._render_step4",
        "step5._render_step5",
        "step6._render_step6",
        "step7._render_step7",
        "step8._render_step8",
        "step9._render_step9",
        "_render_step10",
    ):
        assert marker in text
    assert "LEGACY_AUDIT_LABEL" in text
    assert "frozen_detail.render_player_layer" in text


def test_step10_uses_official_logs_shared_statcast_and_pregame_ids():
    text = (ROOT / "mlb_matchup_recent_stability_v1.py").read_text()
    assert '"stats": "gameLog"' in text
    assert '"group": "hitting"' in text
    assert "batted_ball.fetch_batted_ball_input" in text
    assert "strictly before the selected game's date" in text
    assert "WINDOW_PRIORS = {5: 45.0, 10: 75.0, 20: 120.0}" in text


def test_hub_and_router_point_to_step10_without_touching_rankings():
    hub = (ROOT / "mlb_matchup_hub_v39.py").read_text()
    router = (ROOT / "mlb_matchup_hub_v27.py").read_text()
    assert "import mlb_matchup_player_v33 as player_layer" in hub
    assert "import mlb_matchup_rankings_v21 as rankings" in hub
    assert 'FROZEN_V1_PRESENTATION = ("mlb_matchup_hub_v29", "mlb_matchup_player_v23")' in hub
    assert "from mlb_matchup_hub_v39 import" in router
