"""Regression checks for MLB Hits Step 3 hitter true-talent + contact profile."""
from copy import deepcopy

import pytest

import mlb_hit_hitter_profile_v1 as profile
import mlb_hit_hub_v1318 as hits


def test_skill_blend_is_season_dominant_and_recent_is_bounded():
    out = profile._blend_skill(
        season_avg=0.280,
        xba=0.300,
        recent_avg=0.500,
        savant_pa=500,
        recent_ab=40,
    )
    assert out["neutral_hit_skill"] is not None
    assert out["weights"]["season"] > out["weights"]["xba"]
    assert out["weights"]["recent"] < 0.10
    assert sum(out["weights"].values()) == pytest.approx(1.0)


def test_profile_labels_cover_quality_bands():
    assert profile.skill_label(0.305) == "ELITE HIT SKILL"
    assert profile.skill_label(0.282) == "STRONG HIT SKILL"
    assert profile.skill_label(0.260) == "SOLID HIT SKILL"
    assert profile.skill_label(0.215) == "WEAK HIT SKILL"
    assert profile.skill_label(None) == "DATA LIMITED"


def test_build_profile_uses_frozen_hit_sources_and_declares_zero_model_impact(monkeypatch):
    monkeypatch.setattr(
        profile.hit_engine,
        "hitter_stats",
        lambda pid: {
            "avg": ".288",
            "plate_appearances": 500,
            "at_bats": 450,
            "hits": 130,
            "strikeouts": 95,
        },
    )
    monkeypatch.setattr(
        profile.hit_engine,
        "recent_form",
        lambda pid, n=10: {
            "avg": 0.310,
            "at_bats": 36,
            "games": 10,
            "hit_games": 7,
        },
    )
    monkeypatch.setattr(
        profile.hit_engine,
        "statcast",
        lambda pid: {
            "xba": 0.281,
            "pa": 490,
            "avg_ev": 91.2,
            "hard_hit_rate": 0.46,
            "barrel_rate": 0.11,
        },
    )
    monkeypatch.setattr(
        profile.hit_engine,
        "add_statcast",
        lambda base, sc: (base, {"grade": "Strong Contact", "reliability": 0.82}),
    )

    out = profile.build_hitter_profile(123, 0.275)

    assert out["season_avg"] == pytest.approx(0.288)
    assert out["xba"] == pytest.approx(0.281)
    assert out["recent_hit_game_rate"] == pytest.approx(0.7)
    assert out["contact_grade"] == "Strong Contact"
    assert out["neutral_hit_skill"] is not None
    assert out["probability_impact"] is False
    assert out["ranking_impact"] is False
    assert out["selection_impact"] is False
    assert out["simulation_impact"] is False
    assert out["calibration_impact"] is False
    assert out["starter_input"] is False
    assert out["bullpen_input"] is False
    assert out["park_weather_input"] is False
    assert out["market_input"] is False


def test_step3_wrapper_is_additive_over_frozen_step2():
    assert hits.UI_VERSION == "V13.18"
    assert hits._BASE_PICK_HTML is hits.prior._pick_html_v1317


def test_step3_card_injects_before_frozen_deep_evidence(monkeypatch):
    frozen = (
        '<div class="hit1317-card">'
        '<div>compact Step 2 hero</div>'
        '<details class="hit1317-deep"><summary>Full Steps 1–11</summary>'
        '<div>frozen evidence</div></details>'
        '</div>'
    )
    monkeypatch.setattr(hits, "_BASE_PICK_HTML", lambda result, rank: frozen)
    monkeypatch.setattr(
        hits.profile,
        "build_hitter_profile",
        lambda player_id, fallback: {
            "season_avg": 0.288,
            "xba": 0.281,
            "recent_avg": 0.310,
            "recent_hit_game_rate": 0.70,
            "k_pct": 0.19,
            "avg_ev": 91.2,
            "hard_hit_pct": 0.46,
            "barrel_pct": 0.11,
            "neutral_hit_skill": 0.288,
            "skill_weights": {"season": 0.70, "xba": 0.24, "recent": 0.06},
            "skill_label": "STRONG HIT SKILL",
            "contact_grade": "Strong Contact",
            "data_score": 100,
            "data_label": "ELITE PROFILE DATA",
            "pa": 500,
            "recent_games": 10,
        },
    )

    result = {"player_id": 123, "season_avg": 0.288}
    before = deepcopy(result)
    html = hits._pick_html_v1318(result, 2)

    assert result == before
    assert "STEP 3 • HITTER TRUE-TALENT + CONTACT QUALITY" in html
    assert "STRONG HIT SKILL" in html
    assert "Season AVG" in html
    assert "xBA" in html
    assert "L10 hit-game" in html
    assert "Hard-Hit%" in html
    assert "Barrel%" in html
    assert "Probability / ranking impact: NONE." in html
    assert "frozen evidence" in html
    assert html.index("hit1318-profile") < html.index('hit1317-deep')


def test_profile_html_never_claims_game_matchup_inputs():
    html = hits._profile_html({
        "skill_label": "SOLID HIT SKILL",
        "data_label": "USABLE PROFILE DATA",
        "data_score": 70,
        "skill_weights": {"season": 1.0, "xba": 0.0, "recent": 0.0},
    })
    assert "Starter, bullpen, park/weather, lineup opportunity and sportsbook price are excluded" in html
    assert "Probability / ranking impact: NONE." in html
