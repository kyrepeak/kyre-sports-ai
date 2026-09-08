"""Regression checks for Moneyline Step 10 expected game script + run distribution."""
import math

import mlb_moneyline_hub_v176 as m


def _projection(**overrides):
    kwargs = {
        "side": "away",
        "season_rpg": 4.5,
        "recent_rpg": 4.8,
        "starter_matchup_score": 55,
        "lineup_score": 54,
        "opponent_bullpen_score": 48,
        "environment_score": 52,
        "opponent_defense_score": 50,
        "baserunning_score": 51,
    }
    kwargs.update(overrides)
    return m._team_projection(**kwargs)


def test_negative_binomial_distribution_is_normalized():
    out = m._nb_distribution(4.6)
    total = sum(out["probs"]) + out["tail"]
    assert abs(total - 1.0) < 1e-9
    assert out["mean"] == 4.6
    assert out["dispersion"] == m.NB_DISPERSION


def test_higher_mean_shifts_mass_to_six_plus():
    low = m._run_buckets(m._nb_distribution(3.4))
    high = m._run_buckets(m._nb_distribution(5.8))
    assert high["6_plus"] > low["6_plus"]
    assert high["0_1"] < low["0_1"]


def test_projection_fails_closed_without_season_baseline():
    out = _projection(season_rpg=None)
    assert out["expected_runs"] is None
    assert out["data_score"] == 0
    assert "season scoring baseline" in out["reason"].lower()


def test_projection_requires_supporting_components():
    out = m._team_projection(
        side="away",
        season_rpg=4.5,
        recent_rpg=None,
        starter_matchup_score=55,
        lineup_score=None,
        opponent_bullpen_score=None,
        environment_score=None,
        opponent_defense_score=None,
        baserunning_score=None,
    )
    assert out["expected_runs"] is None
    assert out["support_components"] < m.MIN_SUPPORT_COMPONENTS


def test_strong_hitter_context_increases_expected_runs():
    weak = _projection(
        starter_matchup_score=35,
        lineup_score=38,
        opponent_bullpen_score=65,
        environment_score=42,
        opponent_defense_score=65,
        baserunning_score=40,
    )
    strong = _projection(
        starter_matchup_score=68,
        lineup_score=66,
        opponent_bullpen_score=35,
        environment_score=64,
        opponent_defense_score=38,
        baserunning_score=65,
    )
    assert strong["expected_runs"] > weak["expected_runs"]


def test_home_advantage_is_small_and_bounded():
    away = _projection(side="away", recent_rpg=None)
    home = _projection(side="home", recent_rpg=None)
    assert home["expected_runs"] > away["expected_runs"]
    ratio = home["expected_runs"] / away["expected_runs"]
    assert math.isclose(ratio, m.HOME_RUN_MULTIPLIER, rel_tol=1e-6)


def test_recent_scoring_is_blended_not_replaced():
    out = _projection(season_rpg=4.0, recent_rpg=6.0)
    expected_base = (1.0 - m.RECENT_BLEND) * 4.0 + m.RECENT_BLEND * 6.0
    assert math.isclose(out["base_runs"], expected_base, rel_tol=1e-9)
    assert out["base_runs"] < 6.0


def test_schedule_density_is_not_a_step10_input():
    out = _projection()
    assert "schedule" not in out["modifiers"]
    assert "recent_scoring_blend" in out["modifiers"]


def test_script_labels_direction_and_scoring_environment():
    label, cls, note = m._script(3.0, 5.0)
    assert "HOME" in label
    assert cls == "home"
    assert "home side" in note

    label, cls, _ = m._script(5.4, 5.2)
    assert "TIGHT" in label
    assert "HIGH-SCORING" in label
    assert cls == "neutral"

    label, cls, _ = m._script(None, 4.2)
    assert label == "GAME SCRIPT PENDING"
    assert cls == "limited"


def test_step10_wrapper_preserves_step5l_live_owner(monkeypatch):
    seen = {}
    original = m.prior._render_pregame_with_step9

    def fake_render(*args, **kwargs):
        seen["hook"] = m.prior._render_pregame_with_step9
        return "ok"

    monkeypatch.setattr(m.prior, "render_moneyline_hub", fake_render)
    monkeypatch.setattr(m.st, "markdown", lambda *args, **kwargs: None)

    out = m.render_moneyline_hub(None, None, None, None, None)

    assert out == "ok"
    assert seen["hook"] is m._render_pregame_with_step10
    assert m.prior._render_pregame_with_step9 is original
