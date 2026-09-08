"""Regression checks for College Football Step 5 Moneyline Model V1."""
from __future__ import annotations

import inspect

import pytest

import cfb_moneyline_hub_v2 as hub
import cfb_moneyline_model_v1 as model


def _profile(
    team,
    ppg=30.0,
    allowed=20.0,
    recent_ppg=30.0,
    recent_allowed=20.0,
    sos=.50,
    total_offense=400.0,
    total_defense=400.0,
    turnover_margin=0.0,
    grade="READY",
    games=5,
):
    return {
        "team": team,
        "conference": "test",
        "record_text": f"{games}-0",
        "record": {"games": games, "wins": games, "losses": 0, "ties": 0},
        "ppg": ppg,
        "points_allowed_pg": allowed,
        "recent_ppg": recent_ppg,
        "recent_points_allowed_pg": recent_allowed,
        "sos_opponent_win_pct": sos,
        "sos_coverage": 1.0,
        "data_quality": {"grade": grade},
        "official_stats": {
            "scoring_offense": {"value_numeric": ppg, "value": str(ppg)},
            "scoring_defense": {"value_numeric": allowed, "value": str(allowed)},
            "total_offense": {"value_numeric": total_offense, "value": str(total_offense)},
            "total_defense": {"value_numeric": total_defense, "value": str(total_defense)},
            "turnover_margin": {
                "value_numeric": turnover_margin,
                "value": str(turnover_margin),
                "headers": ["Rank", "Team", "G", "Margin", "Avg"],
            },
        },
    }


def _game(neutral=False, **extra):
    out = {
        "game_id": "900",
        "identity_verified": True,
        "date_matches_query": True,
        "neutral_site": neutral,
        "away_team": "Away",
        "home_team": "Home",
    }
    out.update(extra)
    return out


def test_identical_teams_neutral_site_are_exactly_even():
    away = _profile("Away")
    home = _profile("Home")

    out = model.project_matchup(_game(neutral=True), away, home)

    assert out["ready"] is True
    assert out["home_win_probability_raw"] == pytest.approx(.50, abs=1e-12)
    assert out["away_win_probability_raw"] == pytest.approx(.50, abs=1e-12)
    assert out["projected_margin_home_raw"] == pytest.approx(0.0, abs=1e-12)
    assert out["components"]["home_field_points"] == 0.0


def test_home_field_moves_identical_matchup_toward_home_team():
    away = _profile("Away")
    home = _profile("Home")

    out = model.project_matchup(_game(neutral=False), away, home)

    assert out["components"]["home_field_points"] == model.HOME_FIELD_POINTS
    assert out["projected_margin_home_raw"] > 0
    assert out["home_win_probability_raw"] > .50
    assert out["raw_model_leader_team"] == "Home"


def test_stronger_home_offense_defense_and_efficiency_raise_home_probability():
    away = _profile(
        "Away",
        ppg=24,
        allowed=30,
        recent_ppg=23,
        recent_allowed=31,
        sos=.45,
        total_offense=350,
        total_defense=450,
        turnover_margin=-1.0,
    )
    home = _profile(
        "Home",
        ppg=38,
        allowed=16,
        recent_ppg=40,
        recent_allowed=14,
        sos=.60,
        total_offense=510,
        total_defense=300,
        turnover_margin=1.0,
    )

    out = model.project_matchup(_game(neutral=False), away, home)

    assert out["ready"] is True
    assert out["home_win_probability_raw"] > .70
    assert out["projected_home_points_raw"] > out["projected_away_points_raw"]
    assert out["components"]["home_efficiency_adjustment"] > 0
    assert out["components"]["away_efficiency_adjustment"] < 0
    assert out["components"]["turnover_edge_home_points"] > 0
    assert out["components"]["sos_edge_home_points"] > 0


def test_turnover_margin_uses_ncaa_published_rate_without_double_dividing():
    profile = _profile("Team", turnover_margin=1.5, games=5)
    assert model._turnover_margin_per_game(profile) == pytest.approx(1.5)


def test_missing_qb_data_has_exactly_zero_impact():
    away = _profile("Away")
    home = _profile("Home")

    out = model.project_matchup(_game(neutral=True), away, home)
    c = out["components"]

    assert c["away_qb_adjustment_points"] == 0.0
    assert c["home_qb_adjustment_points"] == 0.0
    assert c["away_qb_state"] == "UNVERIFIED • ZERO IMPACT"
    assert c["home_qb_state"] == "UNVERIFIED • ZERO IMPACT"


def test_verified_qb_adjustment_is_used_but_capped():
    away = _profile("Away")
    home = _profile("Home")
    game = _game(
        neutral=True,
        home_qb_verified=True,
        home_qb_adjustment_points=20.0,
    )

    out = model.project_matchup(game, away, home)

    assert out["components"]["home_qb_adjustment_points"] == 7.0
    assert out["components"]["home_qb_state"] == "VERIFIED"
    assert out["home_win_probability_raw"] > .50


def test_model_fails_closed_when_mandatory_scoring_baseline_is_missing():
    away = _profile("Away")
    home = _profile("Home")
    away["ppg"] = None
    away["official_stats"].pop("scoring_offense")

    out = model.project_matchup(_game(), away, home)

    assert out["ready"] is False
    assert out["raw_probability_ready"] is False
    assert any("scoring offense/defense baseline" in x for x in out["reasons"])
    assert "home_win_probability_raw" not in out


def test_model_fails_closed_when_identity_is_unverified():
    away = _profile("Away")
    home = _profile("Home")
    game = _game()
    game["identity_verified"] = False

    out = model.project_matchup(game, away, home)

    assert out["ready"] is False
    assert any("identity" in x for x in out["reasons"])


def test_probability_complements_and_step6_outputs_remain_locked():
    out = model.project_matchup(
        _game(),
        _profile("Away", ppg=27, allowed=24),
        _profile("Home", ppg=31, allowed=21),
    )

    assert out["home_win_probability_raw"] + out["away_win_probability_raw"] == pytest.approx(1.0)
    assert out["calibrated"] is False
    assert out["sportsbook_input_used"] is False
    assert out["monte_carlo_used"] is False
    assert out["fair_moneyline_ready"] is False
    assert out["final_pick_ready"] is False


def test_small_sample_shrinks_margin_reliability():
    one_game = model.project_matchup(
        _game(),
        _profile("Away", ppg=20, allowed=35, games=1),
        _profile("Home", ppg=40, allowed=15, games=1),
    )
    five_games = model.project_matchup(
        _game(),
        _profile("Away", ppg=20, allowed=35, games=5),
        _profile("Home", ppg=40, allowed=15, games=5),
    )

    assert one_game["reliability"] < five_games["reliability"]
    assert abs(one_game["projected_margin_home_raw"]) < abs(five_games["projected_margin_home_raw"])


def test_ui_labels_model_as_raw_not_final():
    game = _game()
    away = _profile("Away")
    home = _profile("Home")
    out = model.project_matchup(game, away, home)

    html = hub._model_card(game, away, home, out)
    feature_html = hub._feature_panel(out)

    assert "RAW • PRE-CALIBRATION" in html
    assert "not a final betting pick" in html
    assert "Sportsbook input" in html
    assert "STEP 6" in html
    assert "QB firewall" in feature_html
    assert "UNVERIFIED • ZERO IMPACT" in feature_html


def test_step5_model_source_has_no_market_or_monte_carlo_dependency():
    source = inspect.getsource(model)

    forbidden = (
        "requests.get",
        "moneyline_price",
        "market_probability",
        "np.random",
        "numpy",
        "monte_carlo",
        "fair_moneyline =",
        "expected_value =",
    )
    for token in forbidden:
        assert token not in source.lower()
