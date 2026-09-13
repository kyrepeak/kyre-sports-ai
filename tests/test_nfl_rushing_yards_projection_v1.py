from __future__ import annotations

import copy
import math

import nfl_rushing_yards_projection_v1 as projection


def _context() -> dict:
    return {
        "ready": True,
        "data_available": True,
        "schema_version": "nfl_rushing_yards_context_v1",
        "official_event_id": "401872925",
        "model_enabled": False,
        "projection_enabled": False,
        "market_enabled": False,
        "sportsbook_influence": 0.0,
        "stake_sizing_enabled": False,
        "wager_actions": False,
        "teams": [
            {
                "official_team_id": "4",
                "opponent_official_team_id": "27",
                "team_name": "Cincinnati Bengals",
                "players": [
                    {
                        "official_event_id": "401872925",
                        "official_team_id": "4",
                        "official_athlete_id": "1001",
                        "player_name": "Runner One",
                        "position": "RB",
                        "baseline_season": 2025,
                        "sample_games": 5,
                        "carries": 75,
                        "rushing_yards": 330.0,
                        "carries_per_game": 15.0,
                        "rushing_yards_per_game": 66.0,
                        "yards_per_carry": 4.4,
                        "rushing_touchdowns": 3.0,
                    },
                    {
                        "official_event_id": "401872925",
                        "official_team_id": "4",
                        "official_athlete_id": "1002",
                        "player_name": "Kneel Quarterback",
                        "position": "QB",
                        "baseline_season": 2025,
                        "sample_games": 5,
                        "carries": 5,
                        "rushing_yards": -5.0,
                        "carries_per_game": 1.0,
                        "rushing_yards_per_game": -1.0,
                        "yards_per_carry": -1.0,
                        "rushing_touchdowns": 0.0,
                    },
                ],
                "opponent_run_front": {
                    "official_team_id": "27",
                    "data_available": True,
                    "rush_attempts_allowed_per_game": 25.0,
                    "rush_yards_allowed_per_game": 112.5,
                    "yards_per_carry_allowed": 4.5,
                    "rushing_touchdowns_allowed_per_game": 0.8,
                },
            },
            {
                "official_team_id": "27",
                "opponent_official_team_id": "4",
                "team_name": "Tampa Bay Buccaneers",
                "players": [
                    {
                        "official_event_id": "401872925",
                        "official_team_id": "27",
                        "official_athlete_id": "2001",
                        "player_name": "Runner Two",
                        "position": "RB",
                        "baseline_season": 2025,
                        "sample_games": 5,
                        "carries": 60,
                        "rushing_yards": 300.0,
                        "carries_per_game": 12.0,
                        "rushing_yards_per_game": 60.0,
                        "yards_per_carry": 5.0,
                        "rushing_touchdowns": 2.0,
                    }
                ],
                "opponent_run_front": {
                    "official_team_id": "4",
                    "data_available": True,
                    "rush_attempts_allowed_per_game": 24.0,
                    "rush_yards_allowed_per_game": 100.8,
                    "yards_per_carry_allowed": 4.2,
                    "rushing_touchdowns_allowed_per_game": 0.6,
                },
            },
        ],
    }


def test_market_blind_projection_is_deterministic_and_explainable():
    context = _context()
    first = projection.build_event_projections(context)
    second = projection.build_event_projections(copy.deepcopy(context))

    assert first == second
    assert first["ready"] is True
    assert first["schema_version"] == "nfl_rushing_yards_projection_v1"
    assert first["official_event_id"] == "401872925"
    assert first["projection_count"] == 2
    assert first["withheld_count"] == 1

    runner = next(row for row in first["projections"] if row["official_athlete_id"] == "1001")
    expected_ypc = (4.4 * 0.65) + (4.5 * 0.35)
    assert runner["expected_carries"] == 15.0
    assert math.isclose(runner["expected_yards_per_carry"], expected_ypc, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(runner["projection_yards"], 15.0 * expected_ypc, rel_tol=0, abs_tol=1e-12)
    assert runner["efficiency_coverage"] == 1.0
    assert runner["coverage_grade"] == "GREEN"
    assert len(runner["efficiency_components"]) == 2


def test_exact_identity_is_preserved_end_to_end():
    out = projection.build_event_projections(_context())
    assert out["ready"] is True
    by_id = {row["official_athlete_id"]: row for row in out["projections"]}
    assert by_id["1001"]["official_event_id"] == "401872925"
    assert by_id["1001"]["official_team_id"] == "4"
    assert by_id["1001"]["opponent_official_team_id"] == "27"
    assert by_id["2001"]["official_team_id"] == "27"
    assert by_id["2001"]["opponent_official_team_id"] == "4"


def test_market_and_wager_features_stay_hard_off():
    out = projection.build_event_projections(_context())
    assert out["ready"] is True
    assert out["model_enabled"] is True
    assert out["projection_enabled"] is True
    assert out["sportsbook_influence"] == 0.0
    for key in (
        "probability_enabled",
        "monte_carlo_enabled",
        "market_enabled",
        "fair_line_enabled",
        "ev_enabled",
        "ranking_enabled",
        "recommendation_enabled",
        "stake_sizing_enabled",
        "wager_actions",
    ):
        assert out[key] is False
        assert all(row[key] is False for row in out["projections"])

    forbidden = {
        "sportsbook_line",
        "market_line",
        "odds",
        "price",
        "fair_odds",
        "ev",
        "edge",
        "stake",
        "bet",
        "recommendation",
        "rank",
    }
    assert forbidden.isdisjoint(out.keys())
    for row in out["projections"]:
        assert forbidden.isdisjoint(row.keys())


def test_weakened_step2_safety_contract_fails_closed():
    for key, value in (
        ("projection_enabled", True),
        ("market_enabled", True),
        ("sportsbook_influence", 0.01),
        ("stake_sizing_enabled", True),
        ("wager_actions", True),
    ):
        context = _context()
        context[key] = value
        out = projection.build_event_projections(context)
        assert out["ready"] is False
        assert out["projections"] == []
        assert "safety contract" in out["reason"]


def test_wrong_context_schema_or_event_identity_fails_closed():
    context = _context()
    context["schema_version"] = "wrong"
    assert projection.build_event_projections(context)["ready"] is False

    context = _context()
    context["official_event_id"] = "not-an-id"
    out = projection.build_event_projections(context)
    assert out["ready"] is False
    assert "event ID" in out["reason"]


def test_reciprocal_team_identity_mismatch_fails_closed():
    context = _context()
    context["teams"][0]["opponent_official_team_id"] = "99"
    out = projection.build_event_projections(context)
    assert out["ready"] is False
    assert "reciprocal" in out["reason"]


def test_duplicate_athlete_identity_fails_closed_for_entire_event():
    context = _context()
    context["teams"][1]["players"][0]["official_athlete_id"] = "1001"
    out = projection.build_event_projections(context)
    assert out["ready"] is False
    assert out["projections"] == []
    assert "athlete identity" in out["reason"]


def test_missing_or_mismatched_run_front_withholds_player():
    context = _context()
    context["teams"][0]["opponent_run_front"]["data_available"] = False
    out = projection.build_event_projections(context)
    assert out["ready"] is True
    assert {row["official_athlete_id"] for row in out["projections"]} == {"2001"}
    assert any("run-front" in row["reason"] for row in out["withheld"])

    context = _context()
    context["teams"][0]["opponent_run_front"]["official_team_id"] = "4"
    out = projection.build_event_projections(context)
    assert out["ready"] is True
    assert {row["official_athlete_id"] for row in out["projections"]} == {"2001"}
    assert any("identity mismatch" in row["reason"] for row in out["withheld"])


def test_negative_kneel_down_stats_are_accepted_as_context_but_projection_is_withheld():
    out = projection.build_event_projections(_context())
    assert out["ready"] is True
    withheld = next(row for row in out["withheld"] if row["official_athlete_id"] == "1002")
    assert withheld["ready"] is False
    assert "kneel-only" in withheld["reason"]
    assert math.isnan(withheld["projection_yards"])


def test_missing_carries_per_game_uses_exact_sample_workload_fallback():
    context = _context()
    runner = context["teams"][0]["players"][0]
    runner["carries_per_game"] = None
    out = projection.build_event_projections(context)
    row = next(item for item in out["projections"] if item["official_athlete_id"] == "1001")
    assert row["expected_carries"] == 15.0
    assert row["workload_source"] == "verified carries / sample_games"


def test_missing_player_ypc_uses_exact_rushing_totals_fallback():
    context = _context()
    runner = context["teams"][0]["players"][0]
    runner["yards_per_carry"] = None
    out = projection.build_event_projections(context)
    row = next(item for item in out["projections"] if item["official_athlete_id"] == "1001")
    assert math.isclose(row["efficiency_inputs"]["player_yards_per_carry"], 330.0 / 75.0)
    assert row["player_efficiency_source"] == "verified rushing_yards / carries"


def test_sanity_bounds_withhold_corrupt_player_values():
    context = _context()
    context["teams"][0]["players"][0]["carries_per_game"] = 999.0
    context["teams"][0]["players"][0]["carries"] = 9999
    out = projection.build_event_projections(context)
    assert out["ready"] is True
    assert {row["official_athlete_id"] for row in out["projections"]} == {"2001"}
    assert any("carry workload" in row["reason"] for row in out["withheld"])


def test_efficiency_weights_are_explicit_and_sum_to_one():
    assert projection.EFFICIENCY_WEIGHTS == {
        "player_yards_per_carry": 0.65,
        "opponent_yards_per_carry_allowed": 0.35,
    }
    assert math.isclose(sum(projection.EFFICIENCY_WEIGHTS.values()), 1.0)
