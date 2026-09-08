"""Regression checks for Moneyline Step 12 final synthesis + bounded calibration."""
import math

import mlb_moneyline_hub_v178 as m


def _result(**overrides):
    row = {
        "game_pk": 777,
        "selected_side": "home",
        "team": "Home Club",
        "opponent": "Away Club",
        "away_name": "Away Club",
        "home_name": "Home Club",
        "away_team_id": 10,
        "home_team_id": 20,
        "team_id": 20,
        "win_prob": 0.58,
        "final_home": 0.58,
        "final_away": 0.42,
        "fair_odds": "-138",
    }
    row.update(overrides)
    return row


def _step10(away_mean=4.1, home_mean=4.8, away_q=100, home_q=100):
    return {
        "away": {"expected_runs": away_mean, "data_score": away_q},
        "home": {"expected_runs": home_mean, "data_score": home_q},
    }


def _market(selected_side="home", selected_odds=-120, opponent_odds=110, no_vig=0.54):
    return {
        "status": "VERIFIED",
        "selected_side": selected_side,
        "selected_odds": selected_odds,
        "opponent_odds": opponent_odds,
        "no_vig_probability": no_vig,
    }


def test_equal_run_means_are_near_fifty_fifty():
    p = m._script_home_probability(_step10(4.5, 4.5))
    assert p is not None
    assert abs(p - 0.5) < 0.01


def test_higher_home_run_mean_raises_script_home_probability():
    low = m._script_home_probability(_step10(5.0, 3.7))
    high = m._script_home_probability(_step10(3.7, 5.0))
    assert low is not None and high is not None
    assert low < 0.5 < high
    assert high > low


def test_script_probability_fails_closed_below_data_gate():
    assert m._script_home_probability(_step10(home_q=60)) is None


def test_calibration_move_is_hard_bounded():
    out = m._calibrate_home_probability(
        _result(final_home=0.51, final_away=0.49, win_prob=0.51),
        _step10(away_mean=2.0, home_mean=7.2),
    )
    assert out["status"] == "FINAL_READY"
    assert abs(out["delta"]) <= m.MAX_CALIBRATION_DELTA + 1e-12
    assert out["script_weight"] <= m.SCRIPT_BLEND_MAX + 1e-12


def test_baseline_is_preserved_when_step10_not_ready():
    out = m._calibrate_home_probability(_result(), _step10(home_q=50))
    assert out["status"] == "BASELINE_ONLY"
    assert math.isclose(out["final_home"], 0.58)
    assert math.isclose(out["delta"], 0.0)
    assert math.isclose(out["script_weight"], 0.0)


def test_final_home_and_away_sum_to_one():
    out = m._final_context(_result(), _step10(), _market())
    assert math.isclose(out["final_home"] + out["final_away"], 1.0, rel_tol=1e-12)


def test_market_has_zero_probability_weight():
    bullish = m._final_context(
        _result(),
        _step10(),
        _market(selected_odds=-250, opponent_odds=210, no_vig=0.70),
    )
    bearish = m._final_context(
        _result(),
        _step10(),
        _market(selected_odds=180, opponent_odds=-210, no_vig=0.33),
    )
    assert math.isclose(
        bullish["final_probability"],
        bearish["final_probability"],
        rel_tol=1e-12,
    )
    assert bullish["market_probability_weight"] == 0.0
    assert bearish["market_probability_weight"] == 0.0


def test_market_mapping_inverts_when_final_side_differs_from_step11_selected_side():
    market = _market(selected_side="home", selected_odds=-130, opponent_odds=115, no_vig=0.56)
    out = m._market_for_final_side(market, "away")
    assert out["status"] == "VERIFIED"
    assert out["odds"] == 115
    assert math.isclose(out["no_vig_probability"], 0.44)


def test_final_side_can_follow_calibrated_probability():
    out = m._final_context(
        _result(
            selected_side="away",
            team="Away Club",
            opponent="Home Club",
            team_id=10,
            win_prob=0.51,
            final_home=0.49,
            final_away=0.51,
        ),
        _step10(away_mean=5.2, home_mean=3.6),
        _market(selected_side="away", selected_odds=-105, opponent_odds=-105, no_vig=0.5),
    )
    assert out["final_side"] == "away"
    assert out["final_team"] == "Away Club"
    assert out["final_probability"] >= 0.5


def test_final_market_ev_uses_final_probability_only_after_model_is_built():
    out = m._final_context(_result(), _step10(), _market(selected_odds=120, opponent_odds=-130, no_vig=0.46))
    expected = out["final_probability"] * m._decimal_odds(120) - 1.0
    assert math.isclose(out["market"]["ev"], expected, rel_tol=1e-12)


def test_step12_wrapper_preserves_step5l_live_owner(monkeypatch):
    seen = {}
    original = m.prior._render_pregame_with_step11

    def fake_render(*args, **kwargs):
        seen["hook"] = m.prior._render_pregame_with_step11
        return "ok"

    monkeypatch.setattr(m.prior, "render_moneyline_hub", fake_render)
    monkeypatch.setattr(m.st, "markdown", lambda *args, **kwargs: None)

    out = m.render_moneyline_hub(None, None, None, None, None)

    assert out == "ok"
    assert seen["hook"] is m._render_pregame_with_step12
    assert m.prior._render_pregame_with_step11 is original
