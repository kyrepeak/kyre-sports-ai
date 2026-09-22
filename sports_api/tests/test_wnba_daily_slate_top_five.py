import copy
from pathlib import Path
import unittest

from fastapi import HTTPException

import sports_api.wnba_daily_slate_top_five as l
import sports_api.wnba_player_prop_top_five_board as k
import sports_api.api.wnba_daily_slate_top_five as api
from sports_api.database.wnba_pregame_prediction_store import (
    WNBAPregameStoreError,
    WNBAPregameStoreNotReadyError,
)
from sports_api.wnba_multi_sportsbook_market_consensus import (
    WNBAMultiSportsbookModelInputError,
    WNBAMultiSportsbookNotReadyError,
    WNBAMultiSportsbookUpstreamError,
)
from sports_api.wnba_prop_threshold_probability import (
    WNBAPropThresholdModelInputError,
    WNBAPropThresholdNotFoundError,
    WNBAPropThresholdNotReadyError,
    WNBAPropThresholdUpstreamError,
)
from sports_api.wnba_rosters import WNBAStatsUpstreamError
from sports_api.wnba_schedule import WNBAScheduleUpstreamError


TEAM_BY_PLAYER = {1: "SEA", 2: "PHX", 3: "LAS", 4: "ATL", 5: "SEA", 6: "SEA"}
NAME_BY_PLAYER = {i: f"Player {i}" for i in TEAM_BY_PLAYER}
PROBS = {
    1: (.58, .64, .70),
    2: (.62, .70, .76),
    3: (.56, .61, .66),
    4: (.60, .67, .72),
    5: (.57, .63, .68),
    6: (.59, .65, .71),
}


def game(game_id="1022600001", away="SEA", home="PHX", *, playable=True, status="scheduled", changed=False):
    return {
        "game_id": game_id,
        "game_datetime_utc": "2026-08-26T23:00:00+00:00",
        "game_datetime_eastern": "2026-08-26T19:00:00-04:00",
        "status": {"code": 1 if status == "scheduled" else 2, "text": status, "category": status},
        "schedule_change": {"schedule_changed": changed},
        "venue": {"name": "Arena", "city": "City", "state": "AZ"},
        "away": {"team_key": away},
        "home": {"team_key": home},
        "verification": {"playable_pregame": playable},
    }


def slate(*games, integrity=True, date="2026-08-26", season=2026, reasons=None):
    games = list(games) or [game()]
    return {
        "season": season,
        "date": date,
        "verified_at_utc": "2026-08-26T18:00:00+00:00",
        "source_retrieved_at_utc": "2026-08-26T17:59:59+00:00",
        "slate": {
            "slate_integrity_pass": integrity,
            "blocking_reasons": reasons or ([] if integrity else ["fixture_failure"]),
        },
        "games": games,
    }


def roster(*player_ids, season=2026):
    if not player_ids:
        player_ids = (1, 2, 3, 4, 5, 6)
    players = []
    for player_id in player_ids:
        players.append({
            "player_id": player_id,
            "full_name": NAME_BY_PLAYER.get(player_id, f"Player {player_id}"),
            "team_key": TEAM_BY_PLAYER.get(player_id),
            "is_current_roster": True,
        })
    return {
        "season": season,
        "current_roster_only": True,
        "retrieved_at_utc": "2026-08-26T18:00:01+00:00",
        "player_count": len(players),
        "players": players,
    }


def scenario(name, stat, line, side, selected_probability, mean):
    over = selected_probability if side == "over" else 1.0 - selected_probability
    under = 1.0 - over
    return {
        "conditional_scenario": name,
        "stat": stat,
        "line": line,
        "fair_odds": {
            "over": {"available": True, "fair_probability": over, "fair_american_odds": -150},
            "under": {"available": True, "fair_probability": under, "fair_american_odds": 130},
        },
        "raw_probabilities": {
            "over": {"probability": over},
            "under": {"probability": under},
            "push": {"probability": 0.0},
        },
        "source_distribution_summary": {"mean": mean},
        "threshold_precision": {
            "maximum_probability_mc_standard_error": .0002,
            "passed": True,
        },
    }


def threshold(player_id, game_id, stat, line, *, side="over", probs=None):
    low, base, high = probs or PROBS.get(player_id, (.58, .64, .70))
    team = TEAM_BY_PLAYER.get(player_id, "SEA")
    if team == "SEA":
        opp = "PHX"
    elif team == "PHX":
        opp = "SEA"
    elif team == "LAS":
        opp = "ATL"
    else:
        opp = "LAS"
    results = {
        "low": scenario("low", stat, line, side, low, max(0.0, line - 2.0)),
        "base": scenario("base", stat, line, side, base, line + 1.0),
        "high": scenario("high", stat, line, side, high, line + 4.0),
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
        "team_key": team,
        "opponent_team_key": opp,
        "season": 2026,
        "season_type": "Regular Season",
        "prop": {"stat": stat, "line": line},
        "step_5e_reference": {"simulation_fingerprint_sha256": sim_fp},
        "snapshot_reference": {"snapshot_id": f"snap-{player_id}-{game_id}"},
        "model_config": config,
        "conditional_scenario_results": results,
        "scenario_sensitivity": sensitivity,
        "numerical_readiness": {
            "strict_numerical_readiness_passed": True,
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


def threshold_getter(player_id, game_id, season, *, stat, line, **kwargs):
    return threshold(player_id, game_id, stat, line)


def under_threshold_getter(player_id, game_id, season, *, stat, line, **kwargs):
    return threshold(player_id, game_id, stat, line, side="under")


def market_fixture(threshold_value, quotes, *, risk_ev=.08, base_ev=.12, **kwargs):
    base = threshold_value["conditional_scenario_results"]["base"]["fair_odds"]
    over = base["over"]["fair_probability"]
    under = base["under"]["fair_probability"]
    selected = "over" if over > under else "under"
    selected_probability = base[selected]["fair_probability"]
    market_probability = max(.01, selected_probability - .06)
    book = quotes[0].get("sportsbook", "Book A")
    return {
        "model_version": k.MARKET_CONSENSUS_MODEL_VERSION,
        "market_consensus_id": f"market-{threshold_value['player_id']}-{threshold_value['prop']['stat']}",
        "market_consensus_fingerprint_sha256": f"{threshold_value['player_id'] + 100:064x}"[-64:],
        "player_id": threshold_value["player_id"],
        "game_id": threshold_value["game_id"],
        "team_key": threshold_value["team_key"],
        "opponent_team_key": threshold_value["opponent_team_key"],
        "prop": copy.deepcopy(threshold_value["prop"]),
        "step_5f_reference": {
            "probability_fingerprint_sha256": threshold_value["probability_fingerprint_sha256"]
        },
        "quote_set": {"eligible_quote_count": len(quotes), "excluded_quote_count": 0, "stale_quote_count": 0},
        "consensus": {
            "available": len(quotes) >= 2,
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
                "sportsbooks": [{"sportsbook": book}],
            }
        },
        "ev_rankings": {
            selected: [{
                "sportsbook": book,
                "american_odds": 100,
                "decimal_odds": 2.0,
                "base_ev_per_unit": base_ev,
                "base_ev_percentage": base_ev * 100,
                "risk_adjusted_ev_per_unit": risk_ev,
                "risk_adjusted_ev_percentage": risk_ev * 100,
            }]
        },
    }


def quotes(count=2):
    rows = []
    for index in range(count):
        rows.append({
            "sportsbook": f"Book {index+1}",
            "over_odds": -110,
            "under_odds": -110,
            "market_captured_at_utc": "2026-08-26T18:00:00+00:00",
        })
    return rows


def calibration(mature=True, resolved=40):
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
    reports = {k.THRESHOLD_MODEL_VERSION: version_report}
    hashes = ["a" * 64]
    versions = [k.THRESHOLD_MODEL_VERSION]
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


def build(lines, *, slate_value=None, roster_value=None, threshold_fn=threshold_getter,
          market_fn=market_fixture, calibration_fn=None, **kwargs):
    slate_value = slate_value or slate(game(), game("1022600002", "LAS", "ATL"))
    roster_value = roster_value or roster()
    if calibration_fn is None:
        calibration_fn = lambda **_: calibration()
    return l.build_daily_slate_top_five(
        lines,
        date="2026-08-26",
        include_stored_calibration=kwargs.pop("include_stored_calibration", False),
        slate_getter=lambda *args, **kw: copy.deepcopy(slate_value),
        roster_getter=lambda *args, **kw: copy.deepcopy(roster_value),
        threshold_getter=threshold_fn,
        market_builder=market_fn,
        calibration_getter=calibration_fn,
        **kwargs,
    )


class Step5LTests(unittest.TestCase):
    def test_01_basic_candidate_generation(self):
        result = build([{"player_id":1,"stat":"points","line":19.5}])
        self.assertEqual(result["generated_candidate_count"], 1)
        self.assertEqual(result["probability_board_count"], 1)

    def test_02_stat_alias_normalized(self):
        result = build([{"player_id":1,"stat":"PTS","line":19.5}])
        self.assertEqual(result["probability_board"][0]["prop"]["stat"], "points")

    def test_03_duplicate_input_rejected(self):
        with self.assertRaises(l.WNBADailySlateTopFiveModelInputError):
            build([
                {"player_id":1,"stat":"points","line":19.5},
                {"player_id":1,"stat":"pts","line":19.5},
            ])

    def test_04_invalid_player_id_rejected(self):
        with self.assertRaises(ValueError):
            build([{"player_id":0,"stat":"points","line":19.5}])

    def test_05_invalid_stat_rejected(self):
        with self.assertRaises(ValueError):
            build([{"player_id":1,"stat":"steals","line":1.5}])

    def test_06_invalid_line_rejected(self):
        with self.assertRaises(ValueError):
            build([{"player_id":1,"stat":"points","line":-1}])

    def test_07_invalid_date_rejected(self):
        with self.assertRaises(ValueError):
            l.build_daily_slate_top_five(
                [{"player_id":1,"stat":"points","line":19.5}],
                date="08/26/2026",
                include_stored_calibration=False,
            )

    def test_08_slate_integrity_failure_blocks(self):
        with self.assertRaises(l.WNBADailySlateTopFiveNotReadyError):
            build(
                [{"player_id":1,"stat":"points","line":19.5}],
                slate_value=slate(game(), integrity=False),
            )

    def test_09_slate_integrity_can_be_explicitly_relaxed(self):
        result = build(
            [{"player_id":1,"stat":"points","line":19.5}],
            slate_value=slate(game(), integrity=False),
            require_slate_integrity=False,
        )
        self.assertEqual(result["generated_candidate_count"], 1)

    def test_10_schedule_upstream_wrapped(self):
        def bad(*args, **kwargs):
            raise WNBAScheduleUpstreamError("schedule down")
        with self.assertRaises(l.WNBADailySlateTopFiveUpstreamError):
            l.build_daily_slate_top_five(
                [{"player_id":1,"stat":"points","line":19.5}],
                date="2026-08-26",
                include_stored_calibration=False,
                slate_getter=bad,
            )

    def test_11_roster_upstream_wrapped(self):
        def bad(*args, **kwargs):
            raise WNBAStatsUpstreamError("roster down")
        with self.assertRaises(l.WNBADailySlateTopFiveUpstreamError):
            l.build_daily_slate_top_five(
                [{"player_id":1,"stat":"points","line":19.5}],
                date="2026-08-26",
                include_stored_calibration=False,
                slate_getter=lambda *a,**k: slate(game()),
                roster_getter=bad,
            )

    def test_12_player_not_current_roster_excluded(self):
        result = build(
            [{"player_id":99,"stat":"points","line":19.5}],
            roster_value=roster(1,2),
        )
        self.assertEqual(result["generated_candidate_count"], 0)
        self.assertEqual(result["line_generation_audit"][0]["exclusion_reason"], "player_not_on_current_official_roster")

    def test_13_team_not_on_playable_slate_excluded(self):
        result = build(
            [{"player_id":3,"stat":"points","line":19.5}],
            slate_value=slate(game()),
        )
        self.assertEqual(result["generated_candidate_count"], 0)
        self.assertEqual(result["line_generation_audit"][0]["exclusion_reason"], "player_team_not_on_playable_pregame_slate")

    def test_14_multiple_playable_games_for_team_excluded(self):
        result = build(
            [{"player_id":1,"stat":"points","line":19.5}],
            slate_value=slate(game("1022600001","SEA","PHX"), game("1022600003","SEA","ATL")),
        )
        self.assertEqual(result["generated_candidate_count"], 0)
        self.assertEqual(result["line_generation_audit"][0]["exclusion_reason"], "player_team_maps_to_multiple_playable_games")

    def test_15_game_identity_derived_from_slate(self):
        result = build([{"player_id":1,"stat":"points","line":19.5}])
        self.assertEqual(result["probability_board"][0]["game_id"], "1022600001")

    def test_16_live_game_not_playable(self):
        result = build(
            [{"player_id":1,"stat":"points","line":19.5}],
            slate_value=slate(game(playable=False, status="live")),
        )
        self.assertEqual(result["generated_candidate_count"], 0)

    def test_17_schedule_changed_game_not_playable(self):
        result = build(
            [{"player_id":1,"stat":"points","line":19.5}],
            slate_value=slate(game(playable=False, changed=True)),
        )
        self.assertEqual(result["generated_candidate_count"], 0)

    def test_18_threshold_not_found_isolated(self):
        def fail(*args, **kwargs):
            raise WNBAPropThresholdNotFoundError("missing")
        result = build([{"player_id":1,"stat":"points","line":19.5}], threshold_fn=fail)
        self.assertEqual(result["line_generation_audit"][0]["threshold_status"], "not_found")

    def test_19_threshold_not_ready_isolated(self):
        def fail(*args, **kwargs):
            raise WNBAPropThresholdNotReadyError("wait")
        result = build([{"player_id":1,"stat":"points","line":19.5}], threshold_fn=fail)
        self.assertEqual(result["line_generation_audit"][0]["threshold_status"], "not_ready")

    def test_20_threshold_model_input_isolated(self):
        def fail(*args, **kwargs):
            raise WNBAPropThresholdModelInputError("bad")
        result = build([{"player_id":1,"stat":"points","line":19.5}], threshold_fn=fail)
        self.assertEqual(result["line_generation_audit"][0]["threshold_status"], "model_input_error")

    def test_21_threshold_upstream_isolated(self):
        def fail(*args, **kwargs):
            raise WNBAPropThresholdUpstreamError("bad upstream")
        result = build([{"player_id":1,"stat":"points","line":19.5}], threshold_fn=fail)
        self.assertEqual(result["line_generation_audit"][0]["threshold_status"], "upstream_error")

    def test_22_one_threshold_failure_does_not_block_another(self):
        def mixed(player_id, game_id, season, *, stat, line, **kwargs):
            if player_id == 1:
                raise WNBAPropThresholdNotReadyError("wait")
            return threshold(player_id, game_id, stat, line)
        result = build([
            {"player_id":1,"stat":"points","line":19.5},
            {"player_id":2,"stat":"points","line":19.5},
        ], threshold_fn=mixed)
        self.assertEqual(result["generated_candidate_count"], 1)
        self.assertEqual(result["probability_board"][0]["player_id"], 2)

    def test_23_no_quotes_is_valid_probability_candidate(self):
        result = build([{"player_id":1,"stat":"points","line":19.5}])
        self.assertEqual(result["line_generation_audit"][0]["market_status"], "not_supplied")
        self.assertEqual(result["probability_board_count"], 1)

    def test_24_one_quote_does_not_call_step5h(self):
        called = {"value": False}
        def market_fn(*args, **kwargs):
            called["value"] = True
            return market_fixture(*args, **kwargs)
        result = build([
            {"player_id":1,"stat":"points","line":19.5,"sportsbook_quotes":quotes(1)}
        ], market_fn=market_fn)
        self.assertFalse(called["value"])
        self.assertEqual(result["line_generation_audit"][0]["market_status"], "insufficient_quotes")

    def test_25_two_quotes_generate_market_context(self):
        result = build([
            {"player_id":1,"stat":"points","line":19.5,"sportsbook_quotes":quotes(2)}
        ])
        self.assertEqual(result["step_5h_market_enriched_candidate_count"], 1)
        self.assertEqual(result["value_board_count"], 1)

    def test_26_market_not_ready_does_not_destroy_probability_candidate(self):
        def fail(*args, **kwargs):
            raise WNBAMultiSportsbookNotReadyError("wait")
        result = build([
            {"player_id":1,"stat":"points","line":19.5,"sportsbook_quotes":quotes(2)}
        ], market_fn=fail)
        self.assertEqual(result["probability_board_count"], 1)
        self.assertEqual(result["line_generation_audit"][0]["market_status"], "not_ready")

    def test_27_market_model_input_error_isolated(self):
        def fail(*args, **kwargs):
            raise WNBAMultiSportsbookModelInputError("bad")
        result = build([
            {"player_id":1,"stat":"points","line":19.5,"sportsbook_quotes":quotes(2)}
        ], market_fn=fail)
        self.assertEqual(result["probability_board_count"], 1)
        self.assertEqual(result["line_generation_audit"][0]["market_status"], "model_input_error")

    def test_28_market_upstream_error_isolated(self):
        def fail(*args, **kwargs):
            raise WNBAMultiSportsbookUpstreamError("bad upstream")
        result = build([
            {"player_id":1,"stat":"points","line":19.5,"sportsbook_quotes":quotes(2)}
        ], market_fn=fail)
        self.assertEqual(result["probability_board_count"], 1)
        self.assertEqual(result["line_generation_audit"][0]["market_status"], "upstream_error")

    def test_29_calibration_disabled(self):
        result = build([{"player_id":1,"stat":"points","line":19.5}])
        self.assertEqual(result["calibration_status"]["status"], "disabled")

    def test_30_calibration_not_ready_is_nonfatal(self):
        def fail(**kwargs):
            raise WNBAPregameStoreNotReadyError("no observations")
        result = build(
            [{"player_id":1,"stat":"points","line":19.5}],
            include_stored_calibration=True,
            calibration_fn=fail,
        )
        self.assertEqual(result["calibration_status"]["status"], "not_ready")
        self.assertEqual(result["probability_board_count"], 1)

    def test_31_calibration_store_error_is_nonfatal(self):
        def fail(**kwargs):
            raise WNBAPregameStoreError("db problem")
        result = build(
            [{"player_id":1,"stat":"points","line":19.5}],
            include_stored_calibration=True,
            calibration_fn=fail,
        )
        self.assertEqual(result["calibration_status"]["status"], "store_error")

    def test_32_calibration_loaded_into_step5k(self):
        result = build(
            [{"player_id":1,"stat":"points","line":19.5}],
            include_stored_calibration=True,
        )
        self.assertEqual(result["calibration_status"]["status"], "loaded")
        self.assertTrue(result["probability_board"][0]["historical_calibration"]["available"])

    def test_33_all_excluded_returns_clean_empty_board(self):
        result = build(
            [{"player_id":99,"stat":"points","line":19.5}],
            roster_value=roster(1,2),
        )
        self.assertEqual(result["probability_board"], [])
        self.assertIsNone(result["step_5k_board_reference"])

    def test_34_probability_board_assembled_automatically(self):
        result = build([
            {"player_id":1,"stat":"points","line":19.5},
            {"player_id":2,"stat":"points","line":19.5},
        ])
        self.assertEqual([r["player_id"] for r in result["probability_board"]], [2,1])

    def test_35_top_n_is_delegated_to_step5k(self):
        result = build([
            {"player_id":1,"stat":"points","line":19.5},
            {"player_id":2,"stat":"points","line":19.5},
        ], top_n=1)
        self.assertEqual(result["probability_board_count"], 1)

    def test_36_official_roster_name_used(self):
        result = build([{"player_id":1,"stat":"points","line":19.5}])
        self.assertEqual(result["probability_board"][0]["player_name"], "Player 1")

    def test_37_under_side_survives_orchestration(self):
        result = build(
            [{"player_id":1,"stat":"points","line":19.5}],
            threshold_fn=under_threshold_getter,
        )
        self.assertEqual(result["probability_board"][0]["selected_side"], "under")

    def test_38_alternate_lines_suppressed_by_step5k_default(self):
        result = build([
            {"player_id":1,"stat":"points","line":18.5},
            {"player_id":1,"stat":"points","line":19.5},
        ])
        self.assertEqual(result["generated_candidate_count"], 2)
        self.assertEqual(result["probability_board_count"], 1)

    def test_39_alternate_lines_can_be_allowed(self):
        result = build([
            {"player_id":1,"stat":"points","line":18.5},
            {"player_id":1,"stat":"points","line":19.5},
        ], one_line_per_player_stat=False)
        self.assertEqual(result["probability_board_count"], 2)

    def test_40_different_stats_same_player_can_both_rank(self):
        result = build([
            {"player_id":1,"stat":"points","line":19.5},
            {"player_id":1,"stat":"rebounds","line":6.5},
        ])
        self.assertEqual(result["probability_board_count"], 2)

    def test_41_market_value_cannot_move_probability_rank(self):
        def market_fn(value, quotes_value, **kwargs):
            risk = .01 if value["player_id"] == 2 else .50
            return market_fixture(value, quotes_value, risk_ev=risk)
        result = build([
            {"player_id":1,"stat":"points","line":19.5,"sportsbook_quotes":quotes(2)},
            {"player_id":2,"stat":"points","line":19.5,"sportsbook_quotes":quotes(2)},
        ], market_fn=market_fn)
        self.assertEqual([r["player_id"] for r in result["probability_board"]], [2,1])
        self.assertEqual(result["value_board"][0]["player_id"], 1)

    def test_42_fingerprint_is_deterministic(self):
        lines = [{"player_id":1,"stat":"points","line":19.5}]
        a = build(copy.deepcopy(lines))
        b = build(copy.deepcopy(lines))
        self.assertEqual(a["daily_board_fingerprint_sha256"], b["daily_board_fingerprint_sha256"])
        self.assertEqual(a["daily_board_id"], b["daily_board_id"])

    def test_43_fingerprint_changes_when_line_changes(self):
        a = build([{"player_id":1,"stat":"points","line":18.5}])
        b = build([{"player_id":1,"stat":"points","line":19.5}])
        self.assertNotEqual(a["daily_board_fingerprint_sha256"], b["daily_board_fingerprint_sha256"])

    def test_44_playable_game_ids_only(self):
        result = build(
            [{"player_id":1,"stat":"points","line":19.5}],
            slate_value=slate(game(), game("1022600099","LAS","ATL",playable=False,status="live")),
        )
        self.assertEqual(result["slate_verification"]["playable_game_ids"], ["1022600001"])

    def test_45_no_invented_line_guardrail_exposed(self):
        result = build([{"player_id":1,"stat":"points","line":19.5}])
        self.assertTrue(result["orchestration_semantics"]["sportsbook_prop_lines_are_never_invented"])

    def test_46_api_route_registered(self):
        paths = {route.path for route in api.router.routes}
        self.assertIn("/api/v1/wnba/rankings/player-props/daily-top-five", paths)

    def test_47_api_model_input_maps_422(self):
        with self.assertRaises(HTTPException) as caught:
            api._raise_api_error(l.WNBADailySlateTopFiveModelInputError("bad"))
        self.assertEqual(caught.exception.status_code, 422)

    def test_48_api_not_ready_maps_409(self):
        with self.assertRaises(HTTPException) as caught:
            api._raise_api_error(l.WNBADailySlateTopFiveNotReadyError("wait"))
        self.assertEqual(caught.exception.status_code, 409)

    def test_49_api_upstream_maps_502(self):
        with self.assertRaises(HTTPException) as caught:
            api._raise_api_error(l.WNBADailySlateTopFiveUpstreamError("bad upstream"))
        self.assertEqual(caught.exception.status_code, 502)

    def test_50_main_source_wires_daily_router(self):
        main_source = Path("sports_api/main.py").read_text(encoding="utf-8")
        self.assertIn(
            "from sports_api.api.wnba_daily_slate_top_five import router as wnba_daily_slate_top_five_router",
            main_source,
        )
        self.assertIn("app.include_router(wnba_daily_slate_top_five_router)", main_source)


if __name__ == "__main__":
    unittest.main()
