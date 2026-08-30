from __future__ import annotations

import unittest
from unittest.mock import patch

from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step20b_fanduel_period_filter as period_filter


class Step20BFanDuelPeriodFilterTests(unittest.TestCase):
    def test_current_first_quarter_player_title_is_outside_full_game_scope(self) -> None:
        market = {
            "marketName": "Napheesa Collier - 1st Qtr",
            "marketType": "Player Points",
        }
        self.assertTrue(period_filter.is_explicit_period_market(market))
        self.assertIsNone(period_filter.market_stat_full_game_only_step20b(market))

    def test_quarter_and_half_variants_are_filtered(self) -> None:
        names = (
            "Player Points - First Quarter",
            "Player Rebounds Q2",
            "Player Assists - 3rd Qtr",
            "Player Points - Quarter 4",
            "Player PRA - First Half",
            "Player Points H2",
            "Player Assists - Half 1",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertTrue(period_filter.is_explicit_period_market({"marketName": name}))

    def test_normal_full_game_market_delegates_to_frozen_recognizer(self) -> None:
        markets = (
            {"marketName": "Napheesa Collier", "marketType": "Player Points"},
            {"marketName": "Napheesa Collier", "marketType": "Player Rebounds"},
            {"marketName": "Napheesa Collier", "marketType": "Player Assists"},
        )
        for market in markets:
            with self.subTest(market=market):
                expected = period_filter._ORIGINAL_MARKET_STAT(market)
                self.assertIsNotNone(expected)
                self.assertEqual(
                    period_filter.market_stat_full_game_only_step20b(market),
                    expected,
                )

    def test_period_words_inside_unrelated_name_are_not_false_positive(self) -> None:
        market = {"marketName": "Alex Quarterman", "marketType": "Player Points"}
        self.assertFalse(period_filter.is_explicit_period_market(market))
        self.assertEqual(
            period_filter.market_stat_full_game_only_step20b(market),
            period_filter._ORIGINAL_MARKET_STAT(market),
        )

    def test_installer_is_exact_and_guardrails_do_not_relax_identity(self) -> None:
        saved = fanduel._market_stat
        saved_installed = period_filter._INSTALLED
        try:
            fanduel._market_stat = period_filter._ORIGINAL_MARKET_STAT
            period_filter._INSTALLED = False
            status = period_filter.install_step20b_fanduel_period_filter()
            self.assertTrue(status["installed"])
            self.assertTrue(status["market_stat_filter_active"])
            guards = status["guardrails"]
            self.assertEqual(guards["scope"], "explicit_quarter_and_half_markets_only")
            self.assertTrue(guards["full_game_market_stat_delegated_to_frozen_helper"])
            for key in (
                "player_identity_modified",
                "roster_identity_relaxed",
                "sportsbook_transport_modified",
                "price_logic_modified",
                "exact_line_matching_modified",
                "different_lines_blended",
                "projection_math_modified",
                "monte_carlo_simulation_count_modified",
                "monte_carlo_batch_size_modified",
                "readiness_relaxed",
                "persistence_modified",
                "wagering_enabled",
            ):
                self.assertFalse(guards[key], key)
        finally:
            fanduel._market_stat = saved
            period_filter._INSTALLED = saved_installed

    def test_unknown_override_is_rejected(self) -> None:
        saved = fanduel._market_stat
        saved_installed = period_filter._INSTALLED
        try:
            fanduel._market_stat = lambda _market: "points"
            period_filter._INSTALLED = False
            with self.assertRaisesRegex(RuntimeError, "unknown FanDuel market-stat override"):
                period_filter.install_step20b_fanduel_period_filter()
        finally:
            fanduel._market_stat = saved
            period_filter._INSTALLED = saved_installed


if __name__ == "__main__":
    unittest.main(verbosity=2)
