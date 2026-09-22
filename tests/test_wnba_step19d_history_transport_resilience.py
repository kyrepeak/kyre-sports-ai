import unittest
from unittest.mock import patch

from sports_api import wnba_rotation_context as rotation
from sports_api import wnba_step7g_first_party_history as first_party
from sports_api import wnba_step19d_history_transport_resilience as m


GAME_1 = "1022600246"
GAME_2 = "1022600247"


def _history():
    return {
        "games": [
            {"game_id": GAME_1, "game_date": "2026-08-09", "matchup": "PHX vs. CON"},
            {"game_id": GAME_2, "game_date": "2026-08-11", "matchup": "PHX @ LAS"},
        ]
    }


def _rotation_game():
    player = {
        "player_id": 10,
        "player_name": "Test Player",
        "team_key": "phoenix-mercury",
        "started_game": True,
        "stints": [
            {
                "duration_seconds": 1200.0,
                "usage_percentage_during_stint": None,
                "player_points_during_stint": None,
                "team_point_differential_during_stint": None,
            }
        ],
    }
    return {"away": {"players": []}, "home": {"players": [player]}}


def _page_transport_rotation_error(game_id=GAME_2):
    return rotation.WNBARotationUpstreamError(
        "Official WNBA Stats gamerotation transport failed and the certified "
        "first-party fallback also failed: Official WNBA.com page request failed for "
        f"https://www.wnba.com/game/{game_id}: HTTPStatusError"
    )


class WNBAStep19DHistoryTransportResilienceTests(unittest.TestCase):
    def test_page_transport_retries_then_succeeds(self):
        expected = ({"game": {}}, "2026-08-29T00:00:00+00:00", False, 30)
        transient = first_party.WNBAStep7GFirstPartyUpstreamError(
            "Official WNBA.com page request failed for https://www.wnba.com/game/1022600247: HTTPStatusError"
        )
        with patch.object(m, "_ORIGINAL_PAGE_REQUEST", side_effect=[transient, expected]) as request, patch.object(m.time, "sleep") as sleeper:
            result = m._request_page_props_with_bounded_retry(
                "https://www.wnba.com/game/1022600247", ttl_seconds=30
            )
        self.assertEqual(result, expected)
        self.assertEqual(request.call_count, 2)
        sleeper.assert_called_once_with(m.PAGE_RETRY_DELAYS_SECONDS[0])

    def test_not_found_is_never_retried(self):
        missing = first_party.WNBAStep7GFirstPartyNotFoundError("missing")
        with patch.object(m, "_ORIGINAL_PAGE_REQUEST", side_effect=missing) as request, patch.object(m.time, "sleep") as sleeper:
            with self.assertRaises(first_party.WNBAStep7GFirstPartyNotFoundError):
                m._request_page_props_with_bounded_retry(
                    "https://www.wnba.com/game/1022600247", ttl_seconds=30
                )
        self.assertEqual(request.call_count, 1)
        sleeper.assert_not_called()

    def test_malformed_payload_error_is_not_retried(self):
        malformed = first_party.WNBAStep7GFirstPartyUpstreamError(
            "WNBA.com page did not expose __NEXT_DATA__ for https://www.wnba.com/game/1022600247."
        )
        with patch.object(m, "_ORIGINAL_PAGE_REQUEST", side_effect=malformed) as request, patch.object(m.time, "sleep") as sleeper:
            with self.assertRaises(first_party.WNBAStep7GFirstPartyUpstreamError):
                m._request_page_props_with_bounded_retry(
                    "https://www.wnba.com/game/1022600247", ttl_seconds=30
                )
        self.assertEqual(request.call_count, 1)
        sleeper.assert_not_called()

    def test_one_historical_page_transport_failure_uses_existing_missing_contract(self):
        with patch.object(rotation, "get_wnba_teams"), patch.object(
            rotation, "get_player_game_log_dataset", return_value=_history()
        ), patch.object(
            rotation,
            "get_game_rotation",
            side_effect=[_rotation_game(), _page_transport_rotation_error()],
        ):
            result = m.get_player_recent_rotation_context_step19d(
                10, 2026, last_n_games=2
            )
        self.assertEqual(result["selected_game_count"], 2)
        self.assertEqual(result["rotation_game_count"], 1)
        self.assertEqual(result["missing_rotation_game_ids"], [GAME_2])
        self.assertEqual(result["aggregate"]["tracked_minutes"], 20.0)
        self.assertTrue(
            result["verification"]["missing_rotation_games_are_reported_not_fabricated"]
        )

    def test_non_transport_rotation_integrity_error_still_fails_closed(self):
        with patch.object(rotation, "get_wnba_teams"), patch.object(
            rotation, "get_player_game_log_dataset", return_value=_history()
        ), patch.object(
            rotation,
            "get_game_rotation",
            side_effect=rotation.WNBARotationUpstreamError(
                "WNBA first-party rotation reconstruction failed: ambiguous lineup"
            ),
        ):
            with self.assertRaises(rotation.WNBARotationUpstreamError):
                m.get_player_recent_rotation_context_step19d(
                    10, 2026, last_n_games=2
                )

    def test_all_historical_page_transport_failures_remain_not_found(self):
        with patch.object(rotation, "get_wnba_teams"), patch.object(
            rotation, "get_player_game_log_dataset", return_value=_history()
        ), patch.object(
            rotation,
            "get_game_rotation",
            side_effect=[
                _page_transport_rotation_error(GAME_1),
                _page_transport_rotation_error(GAME_2),
            ],
        ):
            with self.assertRaises(rotation.WNBARotationNotFoundError):
                m.get_player_recent_rotation_context_step19d(
                    10, 2026, last_n_games=2
                )

    def test_installer_updates_already_bound_opportunity_seam(self):
        status = m.install_step19d_history_transport_resilience()
        self.assertTrue(status["installed"])
        from sports_api import wnba_player_opportunity_context as opportunity

        self.assertIs(
            opportunity.get_player_recent_rotation_context,
            m.get_player_recent_rotation_context_step19d,
        )
        self.assertFalse(status["current_availability_gates_relaxed"])
        self.assertFalse(status["projection_fabrication_allowed"])


if __name__ == "__main__":
    unittest.main()
