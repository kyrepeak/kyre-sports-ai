"""Regression checks for Moneyline Step 11 market intelligence + price context."""
import math

import mlb_moneyline_hub_v177 as m
from sports_api.mlb_step7c_moneyline_api_integration_v1 import API_CONNECTED, MATCH_METHOD


def _result(**overrides):
    row = {
        "game_pk": 777,
        "team_id": 20,
        "away_team_id": 10,
        "home_team_id": 20,
        "selected_side": "home",
        "team": "Home Club",
        "opponent": "Away Club",
        "win_prob": 0.58,
        "fair_odds": "-138",
    }
    row.update(overrides)
    return row


def _state(**overrides):
    row = {
        "integration_status": API_CONNECTED,
        "api_integration_active": True,
        "source": "FanDuel",
        "match_method": MATCH_METHOD,
        "fallback_matching_used": False,
        "feed_fresh": True,
        "snapshot_age_seconds": 12.0,
        "collected_at_utc": "2026-09-08T04:10:00Z",
        "contexts_by_game_id": {
            777: {
                "official_game_id": 777,
                "sportsbook": "FanDuel",
                "away_odds": 110,
                "home_odds": -120,
            }
        },
    }
    row.update(overrides)
    return row


def test_american_implied_probability_math():
    assert math.isclose(m._implied_probability(100), 0.5)
    assert math.isclose(m._implied_probability(-150), 0.6)
    assert math.isclose(m._implied_probability(200), 1 / 3)


def test_decimal_odds_math():
    assert math.isclose(m._decimal_odds(150), 2.5)
    assert math.isclose(m._decimal_odds(-200), 1.5)


def test_probability_to_american_round_trip_is_reasonable():
    for price in (-200, -120, 110, 180):
        p = m._implied_probability(price)
        recovered = m._prob_to_american(p)
        assert abs(recovered - price) <= 1


def test_exact_id_context_builds_no_vig_and_ev():
    out = m._build_market_context(_result(), _state())
    away_imp = m._implied_probability(110)
    home_imp = m._implied_probability(-120)
    expected_no_vig = home_imp / (home_imp + away_imp)

    assert out["status"] == "VERIFIED"
    assert out["data_score"] == 100
    assert out["selected_odds"] == -120
    assert out["opponent_odds"] == 110
    assert math.isclose(out["no_vig_probability"], expected_no_vig)
    assert math.isclose(out["overround"], home_imp + away_imp - 1.0)
    assert math.isclose(out["model_market_edge"], 0.58 - expected_no_vig)
    assert math.isclose(out["ev_per_dollar"], 0.58 * m._decimal_odds(-120) - 1.0)


def test_context_fails_closed_on_stale_snapshot():
    out = m._build_market_context(
        _result(),
        _state(feed_fresh=False, snapshot_age_seconds=95.0),
    )
    assert out["status"] == "PENDING"
    assert out["grade_cls"] == "limited"
    assert "market_snapshot_not_fresh" in out["failures"]
    assert "market_snapshot_age_out_of_bounds" in out["failures"]


def test_context_fails_closed_on_game_id_mismatch():
    state = _state()
    state["contexts_by_game_id"] = {
        777: {
            "official_game_id": 778,
            "away_odds": 110,
            "home_odds": -120,
        }
    }
    out = m._build_market_context(_result(), state)
    assert out["status"] == "PENDING"
    assert "official_game_id_mismatch" in out["failures"]


def test_context_fails_closed_on_selected_team_identity_mismatch():
    out = m._build_market_context(_result(team_id=999), _state())
    assert out["status"] == "PENDING"
    assert "selected_team_identity_mismatch" in out["failures"]


def test_market_grade_has_bounded_interpretation():
    assert m._market_grade(0.06, 0.08) == ("STRONG MODEL PRICE EDGE", "strong")
    assert m._market_grade(0.03, 0.02) == ("MODEL PRICE EDGE", "value")
    assert m._market_grade(0.01, 0.01) == ("MODEL + MARKET ALIGNED", "aligned")
    assert m._market_grade(-0.03, -0.01) == ("MARKET MORE BULLISH", "market")


def test_step11_never_marks_price_as_model_input():
    out = m._build_market_context(_result(), _state())
    assert out["model_math_impact"] is False
    assert out["probability_impact"] is False
    assert out["ranking_impact"] is False
    assert out["selection_impact"] is False
    assert out["fair_odds_impact"] is False
    assert out["sportsbook_price_model_input"] is False
    assert out["wagering_impact"] is False


def test_step11_wrapper_preserves_step5l_live_owner(monkeypatch):
    seen = {}
    original = m.prior._render_pregame_with_step10

    def fake_render(*args, **kwargs):
        seen["hook"] = m.prior._render_pregame_with_step10
        return "ok"

    monkeypatch.setattr(m.prior, "render_moneyline_hub", fake_render)
    monkeypatch.setattr(m.st, "markdown", lambda *args, **kwargs: None)

    out = m.render_moneyline_hub(None, None, None, None, None)

    assert out == "ok"
    assert seen["hook"] is m._render_pregame_with_step11
    assert m.prior._render_pregame_with_step10 is original
