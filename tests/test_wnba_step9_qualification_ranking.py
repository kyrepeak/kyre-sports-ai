from __future__ import annotations

import copy
import unittest

from sports_api import wnba_step9_qualification_ranking as ranking
from sports_api import wnba_step9_multisportsbook_consensus as consensus_mod


def _env(**updates: str) -> dict[str, str]:
    values = {ranking.STEP9D_QUALIFICATION_RANKING_ENABLED_ENV: "true"}
    values.update(updates)
    return values


def _rehash(payload: dict) -> dict:
    surface = dict(payload)
    surface.pop("generated_at_utc", None)
    surface.pop("consensus_content_sha256", None)
    payload["consensus_content_sha256"] = ranking._canonical_hash(surface)
    return payload


def _offer(
    *,
    side: str,
    line: float,
    sportsbook: str,
    model_probability: float,
    ev: float,
    market_probability: float,
    captured_at: str,
) -> dict:
    return {
        "sportsbook": sportsbook,
        "line": line,
        "american_odds": -110,
        "decimal_odds": 1.90909091,
        "model_raw_win_probability": model_probability,
        "model_raw_push_probability": 0.0,
        "model_resolved_fair_win_probability": model_probability,
        "market_no_vig_probability": market_probability,
        "no_vig_edge_probability": model_probability - market_probability,
        "no_vig_edge_percentage_points": (model_probability - market_probability) * 100.0,
        "ev_per_unit": ev,
        "ev_roi_percentage": ev * 100.0,
        "captured_at_utc": captured_at,
        "comparison_content_sha256": ("b" if side == "over" else "c") * 64,
        "pricing_content_sha256": ("d" if side == "over" else "e") * 64,
        "selection_method": "cert_fixture",
        "cross_prop_ranking_applied": False,
    }


def _consensus(
    *,
    game_id: str = "1022600291",
    player_id: int = 1642291,
    stat: str = "points",
    side: str = "over",
    line: float = 20.5,
    model_probability: float = 0.60,
    ev: float = 0.12,
    consensus_edge: float = 0.06,
    book_count: int = 3,
    range_pp: float = 2.0,
    captured_at: str = "2026-08-28T04:50:00+00:00",
    snapshot_spread_seconds: float = 20.0,
    all_quotes_fresh: bool = True,
) -> dict:
    if side == "over":
        model_over = model_probability
        model_under = 1.0 - model_probability
        market_over = model_over - consensus_edge
        market_under = 1.0 - market_over
        over_ev = ev
        under_ev = -0.08
    else:
        model_under = model_probability
        model_over = 1.0 - model_probability
        market_under = model_under - consensus_edge
        market_over = 1.0 - market_under
        under_ev = ev
        over_ev = -0.08

    over = _offer(
        side="over",
        line=line,
        sportsbook="BookA",
        model_probability=model_over,
        ev=over_ev,
        market_probability=market_over,
        captured_at=captured_at,
    )
    under = _offer(
        side="under",
        line=line,
        sportsbook="BookB",
        model_probability=model_under,
        ev=under_ev,
        market_probability=market_under,
        captured_at=captured_at,
    )
    payload = {
        "data_type": "post_projection_multisportsbook_consensus",
        "schema_version": consensus_mod.SCHEMA_VERSION,
        "source": consensus_mod.SOURCE,
        "model_version": consensus_mod.MODEL_VERSION,
        "release_id": consensus_mod.RELEASE_ID,
        "generated_at_utc": "2026-08-28T04:50:30+00:00",
        "game_id": game_id,
        "player_id": player_id,
        "team_key": "atlanta-dream",
        "opponent_team_key": "portland-fire",
        "prop": {
            "stat": stat,
            "unique_lines": [line],
            "reference_line": line,
            "reference_line_method": "most_sportsbooks_then_lower_line_tiebreak",
            "different_lines_are_never_probability_averaged": True,
        },
        "snapshot": {
            "offer_count": max(book_count, 2),
            "unique_sportsbook_count": max(book_count, 2),
            "unique_sportsbooks": ["BookA", "BookB", "BookC"][: max(book_count, 2)],
            "earliest_captured_at_utc": captured_at,
            "latest_captured_at_utc": captured_at,
            "snapshot_spread_seconds": snapshot_spread_seconds,
            "max_snapshot_spread_seconds": 120,
            "require_fresh_quotes": True,
            "require_synchronized_snapshot": True,
            "all_quotes_fresh": all_quotes_fresh,
        },
        "same_line_consensus": [
            {
                "line": line,
                "book_count": book_count,
                "sportsbooks": ["BookA", "BookB", "BookC"][:book_count],
                "consensus_available": book_count >= 2,
                "consensus_method": (
                    "median_of_same_line_book_no_vig_probabilities" if book_count >= 2 else None
                ),
                "no_vig_over": {
                    "median_probability": market_over,
                    "median_percentage": market_over * 100.0,
                    "mean_probability": market_over,
                    "minimum_probability": market_over - range_pp / 200.0,
                    "maximum_probability": market_over + range_pp / 200.0,
                    "range_percentage_points": range_pp,
                },
                "no_vig_under": {
                    "median_probability": market_under,
                    "median_percentage": market_under * 100.0,
                    "mean_probability": market_under,
                    "minimum_probability": market_under - range_pp / 200.0,
                    "maximum_probability": market_under + range_pp / 200.0,
                    "range_percentage_points": range_pp,
                },
                "model": {
                    "resolved_fair_over_probability": model_over,
                    "resolved_fair_under_probability": model_under,
                },
                "consensus_edge": {
                    "over_probability": model_over - market_over,
                    "over_percentage_points": (model_over - market_over) * 100.0,
                    "under_probability": model_under - market_under,
                    "under_percentage_points": (model_under - market_under) * 100.0,
                },
                "guardrail": "probabilities from different statistical lines are never blended",
            }
        ],
        "best_available": {
            "over": copy.deepcopy(over),
            "under": copy.deepcopy(under),
            "reference_line_best_price": {
                "line": line,
                "over": copy.deepcopy(over),
                "under": copy.deepcopy(under),
            },
            "selection_scope": "within_one_player_prop_only; cross-prop qualification/ranking is Step 9D",
        },
        "lineage": {
            "step8_result_content_sha256": f"{player_id:064x}"[-64:],
            "step9a_release_id": "wnba_step9a_threshold_pricing_2026_regular_season_v1",
            "step9a_model_version": "wnba_step9a_post_step8_threshold_pricing_2026_regular_v1",
            "step9a_frozen_git_sha": "3b9acde91250d0e7a1767f3861765d4366f510ba",
            "step9b_release_id": "wnba_step9b_sportsbook_market_comparison_2026_regular_season_v1",
            "step9b_model_version": "wnba_step9b_post_projection_market_comparison_2026_regular_v1",
            "step9b_frozen_git_sha": "45cd3b43ca2771ae01f6fa3c7345ef0b9a444394",
            "comparison_content_sha256s": ["b" * 64, "c" * 64],
            "pricing_content_sha256s": ["d" * 64, "e" * 64],
        },
        "guardrails": {
            "basketball_projection_changed": False,
            "step8_distribution_changed": False,
            "step9a_probabilities_changed": False,
            "step9b_comparisons_changed": False,
            "sportsbook_called": False,
            "cross_sportsbook_consensus_calculated": True,
            "different_lines_blended_into_consensus": False,
            "best_offer_selected_within_prop": True,
            "cross_prop_ranking_calculated": False,
            "qualification_applied": False,
            "supabase_mutated": False,
            "persistence_mutated": False,
            "scheduler_started": False,
            "production_runtime_enabled": False,
            "production_activation_allowed": False,
        },
    }
    return _rehash(payload)


class Step9QualificationRankingTests(unittest.TestCase):
    def test_flag_is_default_off(self) -> None:
        self.assertFalse(ranking.step9d_qualification_ranking_enabled({}))

    def test_production_switch_fails_closed(self) -> None:
        with self.assertRaises(ranking.WNBAStep9QualificationRankingDisabledError):
            ranking.build_step9d_qualification_ranking(
                [_consensus()], env=_env(WNBA_PRODUCTION_RUNTIME_ENABLED="true")
            )

    def test_qualified_over_becomes_primary_card(self) -> None:
        result = ranking.build_step9d_qualification_ranking([_consensus()], env=_env())
        self.assertEqual(result["qualification_summary"]["qualified_prop_count"], 1)
        card = result["top_cards"]["primary"][0]
        self.assertEqual(card["side"], "over")
        self.assertEqual(card["top_card_rank"], 1)
        self.assertAlmostEqual(card["model_probability"], 0.60)
        self.assertAlmostEqual(card["same_line_consensus_edge_probability"], 0.06)

    def test_qualified_under_is_supported(self) -> None:
        result = ranking.build_step9d_qualification_ranking(
            [_consensus(side="under", model_probability=0.59, ev=0.11, consensus_edge=0.05)],
            env=_env(),
        )
        self.assertEqual(result["top_cards"]["primary"][0]["side"], "under")

    def test_top_five_is_never_forced(self) -> None:
        result = ranking.build_step9d_qualification_ranking(
            [_consensus(model_probability=0.54, ev=0.20, consensus_edge=0.10)],
            env=_env(),
        )
        self.assertEqual(result["qualification_summary"]["qualified_prop_count"], 0)
        self.assertEqual(result["qualification_summary"]["top_card_count"], 0)
        self.assertFalse(result["qualification_summary"]["full_requested_board_available"])
        self.assertTrue(result["top_cards"]["not_forced"])

    def test_probability_and_value_rankings_are_distinct_and_transparent(self) -> None:
        high_probability = _consensus(
            player_id=1642291, stat="points", model_probability=0.63, ev=0.08, consensus_edge=0.05
        )
        high_value = _consensus(
            player_id=1642292, stat="rebounds", model_probability=0.58, ev=0.18, consensus_edge=0.07
        )
        result = ranking.build_step9d_qualification_ranking(
            [high_value, high_probability], env=_env()
        )
        self.assertEqual(result["rankings"]["pure_probability"][0]["player_id"], 1642291)
        self.assertEqual(result["rankings"]["value"][0]["player_id"], 1642292)
        self.assertEqual(result["top_cards"]["primary"][0]["player_id"], 1642291)

    def test_one_selection_per_player_per_game_is_default(self) -> None:
        points = _consensus(player_id=1642291, stat="points", model_probability=0.62, ev=0.10)
        rebounds = _consensus(player_id=1642291, stat="rebounds", model_probability=0.60, ev=0.12)
        result = ranking.build_step9d_qualification_ranking([points, rebounds], env=_env())
        self.assertEqual(result["qualification_summary"]["qualified_prop_count"], 2)
        self.assertEqual(result["qualification_summary"]["top_card_count"], 1)
        self.assertEqual(len(result["top_cards"]["diversification_skips"]), 1)

    def test_player_diversification_can_be_explicitly_disabled(self) -> None:
        points = _consensus(player_id=1642291, stat="points", model_probability=0.62, ev=0.10)
        rebounds = _consensus(player_id=1642291, stat="rebounds", model_probability=0.60, ev=0.12)
        result = ranking.build_step9d_qualification_ranking(
            [points, rebounds], one_selection_per_player=False, env=_env()
        )
        self.assertEqual(result["qualification_summary"]["top_card_count"], 2)

    def test_best_offer_without_consensus_falls_back_to_reference_line(self) -> None:
        payload = _consensus(model_probability=0.61, ev=0.10, consensus_edge=0.05)
        alternate_line = 19.5
        alternate_offer = copy.deepcopy(payload["best_available"]["over"])
        alternate_offer["line"] = alternate_line
        alternate_offer["model_resolved_fair_win_probability"] = 0.68
        alternate_offer["model_raw_win_probability"] = 0.68
        alternate_offer["ev_per_unit"] = 0.20
        alternate_offer["ev_roi_percentage"] = 20.0
        payload["best_available"]["over"] = alternate_offer
        payload["prop"]["unique_lines"] = [19.5, 20.5]
        payload["same_line_consensus"].insert(
            0,
            {
                "line": 19.5,
                "book_count": 1,
                "sportsbooks": ["BookA"],
                "consensus_available": False,
                "consensus_method": None,
                "no_vig_over": {
                    "median_probability": 0.57,
                    "median_percentage": 57.0,
                    "mean_probability": 0.57,
                    "minimum_probability": 0.57,
                    "maximum_probability": 0.57,
                    "range_percentage_points": 0.0,
                },
                "no_vig_under": {
                    "median_probability": 0.43,
                    "median_percentage": 43.0,
                    "mean_probability": 0.43,
                    "minimum_probability": 0.43,
                    "maximum_probability": 0.43,
                    "range_percentage_points": 0.0,
                },
                "model": {
                    "resolved_fair_over_probability": 0.68,
                    "resolved_fair_under_probability": 0.32,
                },
                "consensus_edge": {
                    "over_probability": None,
                    "over_percentage_points": None,
                    "under_probability": None,
                    "under_percentage_points": None,
                },
                "guardrail": "probabilities from different statistical lines are never blended",
            },
        )
        _rehash(payload)
        result = ranking.build_step9d_qualification_ranking([payload], env=_env())
        card = result["top_cards"]["primary"][0]
        self.assertEqual(card["line"], 20.5)
        self.assertEqual(
            card["offer_selection_method"],
            "reference_line_best_price_fallback_for_consensus_support",
        )

    def test_market_disagreement_can_disqualify_candidate(self) -> None:
        result = ranking.build_step9d_qualification_ranking(
            [_consensus(range_pp=9.0)], env=_env()
        )
        self.assertEqual(result["qualification_summary"]["qualified_prop_count"], 0)
        failures = result["prop_decisions"][0]["over"]["qualification_failures"]
        self.assertIn("same_line_market_disagreement_above_threshold", failures)

    def test_minimum_book_threshold_is_enforced(self) -> None:
        result = ranking.build_step9d_qualification_ranking(
            [_consensus(book_count=2)], minimum_books_at_line=3, env=_env()
        )
        self.assertEqual(result["qualification_summary"]["qualified_prop_count"], 0)
        failures = result["prop_decisions"][0]["over"]["qualification_failures"]
        self.assertIn("books_at_line_below_threshold", failures)

    def test_stale_step9c_snapshot_fails_board_when_freshness_required(self) -> None:
        with self.assertRaises(ranking.WNBAStep9QualificationRankingNotReadyError):
            ranking.build_step9d_qualification_ranking(
                [_consensus(all_quotes_fresh=False)], env=_env()
            )

    def test_cross_prop_snapshot_spread_is_bounded(self) -> None:
        first = _consensus(player_id=1642291, captured_at="2026-08-28T04:50:00+00:00")
        second = _consensus(
            player_id=1642292,
            stat="rebounds",
            captured_at="2026-08-28T05:00:01+00:00",
        )
        with self.assertRaises(ranking.WNBAStep9QualificationRankingNotReadyError):
            ranking.build_step9d_qualification_ranking([first, second], env=_env())

    def test_tampered_step9c_payload_fails_hash_validation(self) -> None:
        payload = _consensus()
        payload["best_available"]["over"]["ev_per_unit"] = 0.99
        with self.assertRaises(ranking.WNBAStep9QualificationRankingUpstreamError):
            ranking.build_step9d_qualification_ranking([payload], env=_env())

    def test_duplicate_prop_consensus_is_rejected(self) -> None:
        payload = _consensus()
        with self.assertRaises(ranking.WNBAStep9QualificationRankingUpstreamError):
            ranking.build_step9d_qualification_ranking(
                [payload, copy.deepcopy(payload)], env=_env()
            )

    def test_ranking_hash_is_stable_across_generation_time_only(self) -> None:
        inputs = [
            _consensus(player_id=1642291, stat="points", model_probability=0.61),
            _consensus(player_id=1642292, stat="rebounds", model_probability=0.59),
        ]
        first = ranking.build_step9d_qualification_ranking(inputs, env=_env())
        second = ranking.build_step9d_qualification_ranking(inputs, env=_env())
        self.assertEqual(first["ranking_content_sha256"], second["ranking_content_sha256"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
