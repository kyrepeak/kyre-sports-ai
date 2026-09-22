import copy
import unittest

from fastapi import HTTPException

import sports_api.wnba_player_prop_top_five_board as k
import sports_api.api.wnba_player_prop_top_five_board as api


def scenario(name, stat, line, selected_side, selected_probability, *, mean=20.0, push=0.0, mc_se=.0002):
    over = selected_probability if selected_side == "over" else 1.0 - selected_probability
    under = 1.0 - over
    return {
        "conditional_scenario": name,
        "stat": stat,
        "line": line,
        "fair_odds": {
            "over": {
                "available": True,
                "fair_probability": over,
                "fair_american_odds": -150 if over >= .60 else 120,
            },
            "under": {
                "available": True,
                "fair_probability": under,
                "fair_american_odds": -150 if under >= .60 else 120,
            },
        },
        "raw_probabilities": {
            "over": {"probability": over * (1.0 - push)},
            "under": {"probability": under * (1.0 - push)},
            "push": {"probability": push},
        },
        "source_distribution_summary": {"mean": mean},
        "threshold_precision": {
            "maximum_probability_mc_standard_error": mc_se,
            "passed": True,
        },
    }


def threshold(
    player_id=1,
    *,
    game_id=None,
    stat="points",
    line=19.5,
    side="over",
    low=.58,
    base=.64,
    high=.70,
    strict_ready=True,
    push=0.0,
    mc_se=.0002,
):
    game_id = game_id or f"10226{player_id:05d}"[-10:]
    probabilities = {"low": low, "base": base, "high": high}
    means = {"low": 18.0, "base": 20.0, "high": 22.0}
    results = {
        name: scenario(
            name,
            stat,
            line,
            side,
            probabilities[name],
            mean=means[name],
            push=push,
            mc_se=mc_se,
        )
        for name in k.SCENARIOS
    }
    favored = {}
    for name, row in results.items():
        op = row["fair_odds"]["over"]["fair_probability"]
        up = row["fair_odds"]["under"]["fair_probability"]
        favored[name] = "balanced" if abs(op-up) < 1e-12 else ("over" if op > up else "under")
    sensitivity = {"favored_side_by_scenario": favored, "fixture": True}
    sim_fp = f"{player_id:064x}"[-64:]
    config = {"fixture": True, "stat": stat, "line": line}
    value = {
        "model_version": k.THRESHOLD_MODEL_VERSION,
        "player_id": player_id,
        "game_id": game_id,
        "team_key": f"T{player_id}",
        "opponent_team_key": f"O{player_id}",
        "season": 2026,
        "season_type": "Regular Season",
        "prop": {"stat": stat, "line": line},
        "step_5e_reference": {"simulation_fingerprint_sha256": sim_fp},
        "snapshot_reference": {"snapshot_id": f"snap-{player_id}"},
        "model_config": config,
        "conditional_scenario_results": results,
        "scenario_sensitivity": sensitivity,
        "numerical_readiness": {
            "strict_numerical_readiness_passed": strict_ready,
            "all_fair_odds_available": True,
        },
        "probability_id": f"prob-{player_id}-{stat}-{line}",
    }
    value["probability_fingerprint_sha256"] = k._hash({
        "step_5e_simulation_fingerprint_sha256": sim_fp,
        "model_config": config,
        "conditional_threshold_results": results,
        "scenario_sensitivity": sensitivity,
    })
    return value


def candidate(player_id=1, **kwargs):
    name = kwargs.pop("player_name", f"Player {player_id}")
    market = kwargs.pop("market_consensus", None)
    return {
        "threshold": threshold(player_id, **kwargs),
        "market_consensus": market,
        "player_name": name,
    }


def market(threshold_value, *, risk_ev=.08, base_ev=.12, sportsbook="Book A", available=True):
    base = threshold_value["conditional_scenario_results"]["base"]["fair_odds"]
    over = base["over"]["fair_probability"]
    under = base["under"]["fair_probability"]
    selected = "over" if over > under else "under"
    selected_probability = base[selected]["fair_probability"]
    market_probability = max(0.01, min(.99, selected_probability - .06))
    return {
        "model_version": k.MARKET_CONSENSUS_MODEL_VERSION,
        "market_consensus_id": f"market-{threshold_value['player_id']}",
        "market_consensus_fingerprint_sha256": "f" * 64,
        "player_id": threshold_value["player_id"],
        "game_id": threshold_value["game_id"],
        "team_key": threshold_value["team_key"],
        "opponent_team_key": threshold_value["opponent_team_key"],
        "prop": copy.deepcopy(threshold_value["prop"]),
        "step_5f_reference": {
            "probability_fingerprint_sha256": threshold_value["probability_fingerprint_sha256"]
        },
        "quote_set": {
            "eligible_quote_count": 2,
            "excluded_quote_count": 0,
            "stale_quote_count": 0,
        },
        "consensus": {
            "available": available,
            "no_vig_probability": {
                "consensus_over": market_probability if selected == "over" else 1-market_probability,
                "consensus_under": market_probability if selected == "under" else 1-market_probability,
            },
        },
        "model_vs_market_consensus": {
            "model_base_resolved_fair_probability": {"over": over, "under": under},
            "model_edge_vs_consensus_no_vig": {
                "over_probability": over - (market_probability if selected == "over" else 1-market_probability),
                "under_probability": under - (market_probability if selected == "under" else 1-market_probability),
            },
        },
        "best_prices": {
            selected: {
                "side": selected,
                "best_decimal_odds": 2.0,
                "best_american_odds": 100,
                "sportsbooks": [{"sportsbook": sportsbook}],
            }
        },
        "ev_rankings": {
            selected: [{
                "sportsbook": sportsbook,
                "american_odds": 100,
                "decimal_odds": 2.0,
                "base_ev_per_unit": base_ev,
                "base_ev_percentage": base_ev * 100,
                "risk_adjusted_ev_per_unit": risk_ev,
                "risk_adjusted_ev_percentage": risk_ev * 100,
            }]
        },
    }


def calibration(*, mature=True, resolved=40, model_version=None):
    model_version = model_version or k.THRESHOLD_MODEL_VERSION
    probability = {
        "total_observation_count": resolved,
        "resolved_observation_count": resolved,
        "minimum_resolved_for_calibration_claim": 30,
        "calibration_claim_ready": mature,
        "brier_score": .21,
        "log_loss": .61,
        "favored_side_hit_rate": .64,
        "calibration": {
            "expected_calibration_error": .04,
            "maximum_calibration_error": .08,
        },
    }
    version_report = {
        "probability": probability,
        "by_stat": {
            "points": {
                "observation_count": resolved,
                "probability": {"resolved_observation_count": resolved, "brier_score": .20},
            }
        },
    }
    config = {"fixture": True}
    reports = {model_version: version_report}
    hashes = ["a" * 64]
    versions = [model_version]
    value = {
        "schema_version": k.CALIBRATION_SCHEMA_VERSION,
        "model_version": k.BACKTEST_CALIBRATION_MODEL_VERSION,
        "calibration_report_id": "cal-1",
        "observation_count": resolved,
        "observation_hashes": hashes,
        "probability_model_versions": versions,
        "model_config": config,
        "reports_by_probability_model_version": reports,
    }
    value["calibration_report_fingerprint_sha256"] = k._hash({
        "observation_hashes": sorted(hashes),
        "probability_model_versions": versions,
        "model_config": config,
        "reports_by_probability_model_version": reports,
    })
    return value


class Step5KTests(unittest.TestCase):
    def test_01_probability_board_ranks_highest_base_first(self):
        result = k.build_player_prop_top_five_board([
            candidate(1, base=.61, low=.56, high=.67),
            candidate(2, base=.72, low=.64, high=.78),
            candidate(3, base=.66, low=.60, high=.71),
        ])
        self.assertEqual([row["player_id"] for row in result["probability_board"]], [2,3,1])

    def test_02_top_five_is_maximum_not_quota(self):
        result = k.build_player_prop_top_five_board([candidate(1), candidate(2)])
        self.assertEqual(result["probability_board_count"], 2)

    def test_03_top_n_limits_board(self):
        rows = [candidate(i, base=.70-i*.01, low=.60, high=.75) for i in range(1,8)]
        result = k.build_player_prop_top_five_board(rows, top_n=5)
        self.assertEqual(len(result["probability_board"]), 5)

    def test_04_under_can_be_selected(self):
        result = k.build_player_prop_top_five_board([
            candidate(1, side="under", low=.57, base=.65, high=.71)
        ])
        self.assertEqual(result["probability_board"][0]["selected_side"], "under")

    def test_05_base_probability_gate(self):
        result = k.build_player_prop_top_five_board([
            candidate(1, low=.50, base=.54, high=.58)
        ])
        self.assertEqual(result["probability_board"], [])
        self.assertIn("base_probability_below_minimum", result["all_candidates"][0]["qualification"]["reason_codes"])

    def test_06_worst_scenario_gate(self):
        result = k.build_player_prop_top_five_board([
            candidate(1, low=.48, base=.65, high=.72)
        ])
        self.assertIn("worst_scenario_probability_below_minimum", result["all_candidates"][0]["qualification"]["reason_codes"])

    def test_07_scenario_span_gate(self):
        result = k.build_player_prop_top_five_board([
            candidate(1, low=.51, base=.65, high=.80)
        ], maximum_scenario_span_percentage_points=20)
        self.assertIn("scenario_probability_span_above_maximum", result["all_candidates"][0]["qualification"]["reason_codes"])

    def test_08_scenario_side_flip_gate(self):
        value = threshold(1, low=.40, base=.65, high=.72)
        result = k.build_player_prop_top_five_board([{"threshold":value}])
        self.assertIn("favored_side_changes_across_scenarios", result["all_candidates"][0]["qualification"]["reason_codes"])

    def test_09_side_flip_can_be_allowed(self):
        value = threshold(1, low=.40, base=.65, high=.72)
        result = k.build_player_prop_top_five_board(
            [{"threshold":value}],
            require_same_favored_side_all_scenarios=False,
            minimum_worst_scenario_probability=.35,
            maximum_scenario_span_percentage_points=40,
        )
        self.assertEqual(result["probability_board_count"], 1)

    def test_10_strict_numerical_readiness_gate(self):
        result = k.build_player_prop_top_five_board([candidate(1, strict_ready=False)])
        self.assertIn("strict_numerical_readiness_failed", result["all_candidates"][0]["qualification"]["reason_codes"])

    def test_11_numerical_gate_can_be_disabled(self):
        result = k.build_player_prop_top_five_board(
            [candidate(1, strict_ready=False)], require_strict_numerical_readiness=False
        )
        self.assertEqual(result["probability_board_count"], 1)

    def test_12_probability_tiebreaks_on_worst_scenario(self):
        result = k.build_player_prop_top_five_board([
            candidate(1, low=.56, base=.65, high=.70),
            candidate(2, low=.60, base=.65, high=.70),
        ])
        self.assertEqual(result["probability_board"][0]["player_id"], 2)

    def test_13_probability_tiebreaks_on_smaller_span(self):
        result = k.build_player_prop_top_five_board([
            candidate(1, low=.60, base=.65, high=.72),
            candidate(2, low=.60, base=.65, high=.68),
        ])
        self.assertEqual(result["probability_board"][0]["player_id"], 2)

    def test_14_probability_tiebreaks_on_lower_mc_error(self):
        result = k.build_player_prop_top_five_board([
            candidate(1, low=.60, base=.65, high=.70, mc_se=.0003),
            candidate(2, low=.60, base=.65, high=.70, mc_se=.0001),
        ])
        self.assertEqual(result["probability_board"][0]["player_id"], 2)

    def test_15_market_does_not_move_probability_rank(self):
        one = threshold(1, low=.60, base=.68, high=.72)
        two = threshold(2, low=.58, base=.64, high=.69)
        result = k.build_player_prop_top_five_board([
            {"threshold":one, "market_consensus":market(one, risk_ev=.01)},
            {"threshold":two, "market_consensus":market(two, risk_ev=.50)},
        ])
        self.assertEqual([r["player_id"] for r in result["probability_board"]], [1,2])

    def test_16_value_board_ranks_risk_adjusted_ev(self):
        one = threshold(1, low=.60, base=.68, high=.72)
        two = threshold(2, low=.58, base=.64, high=.69)
        result = k.build_player_prop_top_five_board([
            {"threshold":one, "market_consensus":market(one, risk_ev=.04)},
            {"threshold":two, "market_consensus":market(two, risk_ev=.20)},
        ])
        self.assertEqual([r["player_id"] for r in result["value_board"]], [2,1])

    def test_17_nonpositive_risk_ev_not_forced(self):
        one = threshold(1)
        result = k.build_player_prop_top_five_board([
            {"threshold":one, "market_consensus":market(one, risk_ev=-.01)}
        ])
        self.assertEqual(result["value_board"], [])

    def test_18_missing_market_is_valid(self):
        result = k.build_player_prop_top_five_board([candidate(1)])
        self.assertFalse(result["probability_board"][0]["market_context"]["available"])

    def test_19_unavailable_multi_book_not_on_value_board(self):
        one = threshold(1)
        result = k.build_player_prop_top_five_board([
            {"threshold":one, "market_consensus":market(one, risk_ev=.20, available=False)}
        ])
        self.assertEqual(result["value_board"], [])

    def test_20_step5h_reference_mismatch_rejected(self):
        one = threshold(1)
        bad = market(one)
        bad["step_5f_reference"]["probability_fingerprint_sha256"] = "b"*64
        with self.assertRaises(k.WNBAPlayerPropBoardUpstreamError):
            k.build_player_prop_top_five_board([{"threshold":one,"market_consensus":bad}])

    def test_21_step5h_model_probability_mismatch_rejected(self):
        one = threshold(1)
        bad = market(one)
        bad["model_vs_market_consensus"]["model_base_resolved_fair_probability"]["over"] += .01
        with self.assertRaises(k.WNBAPlayerPropBoardUpstreamError):
            k.build_player_prop_top_five_board([{"threshold":one,"market_consensus":bad}])

    def test_22_threshold_fingerprint_tamper_rejected(self):
        one = threshold(1)
        one["conditional_scenario_results"]["base"]["source_distribution_summary"]["mean"] = 99
        with self.assertRaises(k.WNBAPlayerPropBoardUpstreamError):
            k.build_player_prop_top_five_board([{"threshold":one}])

    def test_23_wrong_step5f_version_rejected(self):
        one = threshold(1)
        one["model_version"] = "wrong"
        with self.assertRaises(k.WNBAPlayerPropBoardUpstreamError):
            k.build_player_prop_top_five_board([{"threshold":one}])

    def test_24_duplicate_logical_candidate_rejected(self):
        one = candidate(1)
        with self.assertRaises(k.WNBAPlayerPropBoardModelInputError):
            k.build_player_prop_top_five_board([one, copy.deepcopy(one)])

    def test_25_alternate_line_suppressed_by_default(self):
        a = candidate(1, line=19.5, low=.60, base=.68, high=.72)
        b = candidate(1, line=20.5, low=.56, base=.63, high=.69)
        result = k.build_player_prop_top_five_board([a,b])
        self.assertEqual(result["probability_board_count"], 1)
        self.assertEqual(result["alternate_line_suppressed_count"], 1)

    def test_26_alternate_lines_can_be_allowed(self):
        a = candidate(1, line=19.5, low=.60, base=.68, high=.72)
        b = candidate(1, line=20.5, low=.56, base=.63, high=.69)
        result = k.build_player_prop_top_five_board([a,b], one_line_per_player_stat=False)
        self.assertEqual(result["probability_board_count"], 2)

    def test_27_different_stats_same_player_not_suppressed(self):
        a = candidate(1, stat="points", line=19.5)
        b = candidate(1, stat="rebounds", line=6.5)
        result = k.build_player_prop_top_five_board([a,b])
        self.assertEqual(result["probability_board_count"], 2)

    def test_28_calibration_is_attached_but_does_not_rescale(self):
        report = calibration(mature=True)
        result = k.build_player_prop_top_five_board([candidate(1)], calibration_report=report)
        row = result["probability_board"][0]
        self.assertTrue(row["historical_calibration"]["available"])
        self.assertEqual(row["probability"]["base"], .64)

    def test_29_immature_calibration_does_not_block_by_default(self):
        result = k.build_player_prop_top_five_board(
            [candidate(1)], calibration_report=calibration(mature=False, resolved=10)
        )
        self.assertEqual(result["probability_board_count"], 1)

    def test_30_require_mature_calibration_blocks_immature(self):
        result = k.build_player_prop_top_five_board(
            [candidate(1)],
            calibration_report=calibration(mature=False, resolved=10),
            require_mature_calibration=True,
        )
        self.assertEqual(result["probability_board_count"], 0)
        self.assertIn("mature_historical_calibration_required", result["all_candidates"][0]["qualification"]["reason_codes"])

    def test_31_require_mature_calibration_accepts_mature(self):
        result = k.build_player_prop_top_five_board(
            [candidate(1)], calibration_report=calibration(mature=True), require_mature_calibration=True
        )
        self.assertEqual(result["probability_board_count"], 1)

    def test_32_calibration_fingerprint_tamper_rejected(self):
        report = calibration()
        report["reports_by_probability_model_version"][k.THRESHOLD_MODEL_VERSION]["probability"]["brier_score"] = .99
        with self.assertRaises(k.WNBAPlayerPropBoardUpstreamError):
            k.build_player_prop_top_five_board([candidate(1)], calibration_report=report)

    def test_33_nonmatching_calibration_version_is_unavailable(self):
        report = calibration(model_version="old-model")
        result = k.build_player_prop_top_five_board([candidate(1)], calibration_report=report)
        self.assertFalse(result["probability_board"][0]["historical_calibration"]["available"])

    def test_34_stat_slice_is_attached(self):
        result = k.build_player_prop_top_five_board([candidate(1)], calibration_report=calibration())
        self.assertIsNotNone(result["probability_board"][0]["historical_calibration"]["stat_slice"])

    def test_35_push_probability_is_preserved_for_display(self):
        result = k.build_player_prop_top_five_board([candidate(1, push=.05)])
        self.assertEqual(result["probability_board"][0]["raw_push_probability"]["base"], .05)

    def test_36_player_name_is_display_only(self):
        result = k.build_player_prop_top_five_board([
            candidate(1, player_name="Zed", base=.68, low=.60, high=.72),
            candidate(2, player_name="Aaron", base=.64, low=.58, high=.69),
        ])
        self.assertEqual(result["probability_board"][0]["player_name"], "Zed")

    def test_37_board_fingerprint_deterministic(self):
        rows = [candidate(1), candidate(2, base=.62, low=.57, high=.68)]
        a = k.build_player_prop_top_five_board(copy.deepcopy(rows))
        b = k.build_player_prop_top_five_board(copy.deepcopy(rows))
        self.assertEqual(a["board_fingerprint_sha256"], b["board_fingerprint_sha256"])
        self.assertEqual(a["board_id"], b["board_id"])

    def test_38_invalid_top_n_rejected(self):
        with self.assertRaises(ValueError):
            k.build_player_prop_top_five_board([candidate(1)], top_n=0)

    def test_39_empty_candidates_rejected(self):
        with self.assertRaises(ValueError):
            k.build_player_prop_top_five_board([])

    def test_40_api_route_registered(self):
        paths = {route.path for route in api.router.routes}
        self.assertIn("/api/v1/wnba/rankings/player-props/top-five", paths)

    def test_41_api_model_input_maps_422(self):
        with self.assertRaises(HTTPException) as caught:
            api._raise_api_error(k.WNBAPlayerPropBoardModelInputError("bad"))
        self.assertEqual(caught.exception.status_code, 422)

    def test_42_api_not_ready_maps_409(self):
        with self.assertRaises(HTTPException) as caught:
            api._raise_api_error(k.WNBAPlayerPropBoardNotReadyError("wait"))
        self.assertEqual(caught.exception.status_code, 409)

    def test_43_api_upstream_maps_502(self):
        with self.assertRaises(HTTPException) as caught:
            api._raise_api_error(k.WNBAPlayerPropBoardUpstreamError("bad upstream"))
        self.assertEqual(caught.exception.status_code, 502)


if __name__ == "__main__":
    unittest.main()
