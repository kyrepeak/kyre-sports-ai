from __future__ import annotations

import math
from statistics import NormalDist, median

from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
from cfb_player_props_market_v1 import PropObservation


def _history(values, market="passing_yards"):
    return [
        {
            "event_id": f"event-{i}",
            "completed": True,
            "source": "ESPN CFB athlete gamelog",
            "market_key": market,
            "value": value,
            "game_date": f"2026-10-{18-i:02d}",
        }
        for i, value in enumerate(values)
    ]


def _obs(book, side, line, price, stamp="2026-10-20T04:00:00Z"):
    return PropObservation(
        "401999001", "12345", "Jalen Example", "77", "passing_yards",
        book, side, float(line), price, stamp, "SportsGameOdds",
        "evt", "provider-player", f"{book}-{side}", True,
    )


def test_three_games_is_not_model_ready_and_has_no_probability_or_edge():
    import cfb_player_props_model_v1 as model

    projection = model.build_prop_projection(_history([250, 265, 240]), "passing_yards")
    assert projection["model_ready"] is False
    assert projection["sample_count"] == 3
    signal = model.build_page1_signal(
        CanonicalPlayerIdentity("12345", "77", "Jalen Example", "QB", "Example State", "EXS"),
        "passing_yards",
        _history([250, 265, 240]),
        [_obs("FanDuel", "over", 250.5, -110), _obs("FanDuel", "under", 250.5, -110)],
    )
    assert signal["model_ready"] is False
    assert signal["model_probability"] is None
    assert signal["edge"] is None


def test_projection_uses_at_most_eight_games_and_exact_decay_math():
    import cfb_player_props_model_v1 as model

    values = [320, 300, 280, 260, 240, 220, 200, 180, 1000, 2000]
    result = model.build_prop_projection(_history(values), "passing_yards")
    used = values[:8]
    weights = [0.85**i for i in range(8)]
    expected = sum(w*x for w, x in zip(weights, used)) / sum(weights)
    sigma = math.sqrt(sum(w*(x-expected)**2 for w, x in zip(weights, used)) / sum(weights))
    assert result["model_ready"] is True
    assert result["sample_count"] == 8
    assert result["projection"] == pytest_approx(expected)
    assert result["uncertainty"] == pytest_approx(sigma)
    assert result["values"] == tuple(float(x) for x in used)


def pytest_approx(value):
    import pytest
    return pytest.approx(value, rel=1e-10, abs=1e-10)


def test_zero_uncertainty_is_not_ready():
    import cfb_player_props_model_v1 as model

    result = model.build_prop_projection(_history([250, 250, 250, 250]), "passing_yards")
    assert result["model_ready"] is False
    assert result["uncertainty"] == 0.0


def test_consensus_line_is_median_and_line_changes_probability_not_projection():
    import cfb_player_props_model_v1 as model

    projection = model.build_prop_projection(_history([300, 280, 260, 240]), "passing_yards")
    a = model.build_market_consensus([
        _obs("FanDuel", "over", 260.5, -110), _obs("FanDuel", "under", 260.5, -110),
        _obs("DraftKings", "over", 262.5, -105), _obs("DraftKings", "under", 262.5, -115),
    ])
    b = model.build_market_consensus([
        _obs("FanDuel", "over", 280.5, -110), _obs("FanDuel", "under", 280.5, -110),
        _obs("DraftKings", "over", 282.5, -105), _obs("DraftKings", "under", 282.5, -115),
    ])
    assert a["line"] == 261.5
    assert b["line"] == 281.5
    grade_a = model.grade_market_line(projection, a)
    grade_b = model.grade_market_line(projection, b)
    assert grade_a["projection"] == grade_b["projection"] == projection["projection"]
    assert grade_a["model_probability"] != grade_b["model_probability"]


def test_grade_uses_normal_cdf_selects_side_and_computes_no_vig_edge():
    import cfb_player_props_model_v1 as model

    projection = model.build_prop_projection(_history([300, 285, 270, 255]), "passing_yards")
    observations = [
        _obs("FanDuel", "over", 270.5, -120), _obs("FanDuel", "under", 270.5, +100),
        _obs("DraftKings", "over", 271.5, -110), _obs("DraftKings", "under", 271.5, -110),
    ]
    consensus = model.build_market_consensus(observations)
    grade = model.grade_market_line(projection, consensus)
    line = median([270.5, 270.5, 271.5, 271.5])
    p_over = 1 - NormalDist(mu=projection["projection"], sigma=projection["uncertainty"]).cdf(line)
    expected_side = "over" if p_over >= 0.5 else "under"
    assert grade["side"] == expected_side
    assert grade["model_probability"] == pytest_approx(p_over if expected_side == "over" else 1-p_over)
    assert grade["market_probability"] is not None
    assert grade["edge"] == pytest_approx(grade["model_probability"] - grade["market_probability"])


def test_missing_paired_prices_keeps_model_probability_but_edge_unavailable():
    import cfb_player_props_model_v1 as model

    projection = model.build_prop_projection(_history([300, 285, 270, 255]), "passing_yards")
    consensus = model.build_market_consensus([_obs("FanDuel", "over", 270.5, -110)])
    grade = model.grade_market_line(projection, consensus)
    assert grade["model_probability"] is not None
    assert grade["market_probability"] is None
    assert grade["edge"] is None


def test_signal_projection_is_identical_when_only_sportsbook_prices_or_lines_change():
    import cfb_player_props_model_v1 as model

    player = CanonicalPlayerIdentity("12345", "77", "Jalen Example", "QB", "Example State", "EXS")
    history = _history([300, 285, 270, 255])
    low = model.build_page1_signal(player, "passing_yards", history, [
        _obs("FanDuel", "over", 260.5, -130), _obs("FanDuel", "under", 260.5, +105),
    ])
    high = model.build_page1_signal(player, "passing_yards", history, [
        _obs("FanDuel", "over", 290.5, +110), _obs("FanDuel", "under", 290.5, -135),
    ])
    assert low["projection"] == high["projection"]
    assert low["uncertainty"] == high["uncertainty"]
    assert low["model_probability"] != high["model_probability"]
    assert "injury" not in low
    assert "status" not in low


def test_history_payload_normalization_keeps_completed_finite_rows_newest_first():
    import cfb_player_props_history_v1 as history

    payload = {
        "categories": [{
            "name": "passing",
            "labels": ["C/ATT", "YDS", "AVG", "TD", "INT"],
            "events": [
                {"eventId": "2", "date": "2026-10-18T20:00:00Z", "completed": True, "stats": ["20/30", "280", "9.3", "2", "0"]},
                {"eventId": "1", "date": "2026-10-11T20:00:00Z", "completed": True, "stats": ["18/29", "250", "8.6", "1", "1"]},
                {"eventId": "future", "date": "2026-10-25T20:00:00Z", "completed": False, "stats": ["0/0", "0", "0", "0", "0"]},
            ],
        }]
    }
    rows = history.normalize_gamelog_payload(payload, "passing_yards")
    assert [(row["event_id"], row["value"]) for row in rows] == [("2", 280.0), ("1", 250.0)]
    assert all(row["source"] == "ESPN CFB athlete gamelog" for row in rows)
