from __future__ import annotations

import unittest

from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step19l_fanduel_identity_trace as step19l


class Step19LIdentityTraceTests(unittest.TestCase):
    def setUp(self) -> None:
        step19l._clear_for_test()

    def test_market_identity_trace_returns_original_surface_unchanged(self) -> None:
        first = {
            "marketId": "m1",
            "marketName": "Player Points",
            "marketType": "PLAYER_POINTS_TOTAL_WNBA",
            "runners": [
                {"selectionId": "o1", "runnerName": "Over 19.5", "handicap": 19.5},
                {"selectionId": "u1", "runnerName": "Under 19.5", "handicap": 19.5},
            ],
        }
        second = {
            "marketId": "m1",
            "marketName": "Player Points",
            "marketType": "PLAYER_POINTS_TOTAL_WNBA",
            "runners": [
                {"selectionId": "o2", "runnerName": "Over 20.5", "handicap": 20.5},
                {"selectionId": "u2", "runnerName": "Under 20.5", "handicap": 20.5},
            ],
        }
        trace = {"seen": {}, "drifts": []}
        token = step19l._ACTIVE_TRACE.set(trace)
        try:
            observed_first = step19l.market_identity_surface_step19l(first)
            observed_second = step19l.market_identity_surface_step19l(second)
        finally:
            step19l._ACTIVE_TRACE.reset(token)

        self.assertEqual(observed_first, step19l._ORIGINAL_MARKET_IDENTITY_SURFACE(first))
        self.assertEqual(observed_second, step19l._ORIGINAL_MARKET_IDENTITY_SURFACE(second))
        self.assertEqual(len(trace["drifts"]), 1)
        drift = trace["drifts"][0]
        self.assertIn("runners", drift["changed_fields"])
        self.assertTrue(drift["line_shape_changed"])
        self.assertTrue(drift["selection_ids_changed"])
        self.assertNotIn("price", drift)

    def test_success_result_is_returned_without_modification(self) -> None:
        expected = {"sentinel": {"nested": [1, 2, 3]}}
        old = step19l._UPSTREAM_FETCH_STEP11C
        try:
            step19l._UPSTREAM_FETCH_STEP11C = lambda *args, **kwargs: expected
            actual = step19l.fetch_step11c_with_identity_trace()
        finally:
            step19l._UPSTREAM_FETCH_STEP11C = old
        self.assertIs(actual, expected)
        status = step19l.installation_status()
        self.assertEqual(status["fetch_count"], 1)
        self.assertEqual(status["success_count"], 1)
        self.assertEqual(status["identity_error_count"], 0)

    def test_identity_exception_is_recorded_and_reraised_unchanged(self) -> None:
        expected = fanduel.WNBAStep11FanDuelProviderIdentityError(
            "Conflicting FanDuel market identity for 12345."
        )

        def boom(*args, **kwargs):
            raise expected

        old = step19l._UPSTREAM_FETCH_STEP11C
        try:
            step19l._UPSTREAM_FETCH_STEP11C = boom
            with self.assertRaises(fanduel.WNBAStep11FanDuelProviderIdentityError) as caught:
                step19l.fetch_step11c_with_identity_trace()
        finally:
            step19l._UPSTREAM_FETCH_STEP11C = old

        self.assertIs(caught.exception, expected)
        status = step19l.get_step19l_fanduel_identity_trace()
        self.assertEqual(status["identity_error_count"], 1)
        self.assertEqual(status["latest_error"]["category"], "conflicting_market_identity")
        self.assertFalse(status["latest_error"]["payload_logged"])
        self.assertFalse(status["latest_error"]["prices_logged"])

    def test_guardrails_are_semantics_neutral(self) -> None:
        guards = step19l.installation_status()["guardrails"]
        for key in (
            "provider_result_modified",
            "exception_modified",
            "identity_matching_modified",
            "game_uniqueness_relaxed",
            "player_identity_relaxed",
            "market_identity_relaxed",
            "line_matching_modified",
            "prices_logged",
            "payload_logged",
            "query_logged",
            "readiness_relaxed",
            "provider_retry_policy_modified",
            "controller_state_modified",
            "projection_logic_modified",
            "persistence_modified",
            "wagering_enabled",
        ):
            self.assertFalse(guards[key], key)


if __name__ == "__main__":
    unittest.main(verbosity=2)
