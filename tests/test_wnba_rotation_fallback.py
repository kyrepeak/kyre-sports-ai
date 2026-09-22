import unittest
from unittest.mock import patch

from sports_api import wnba_rotation_context as m
from sports_api import wnba_rotation_reconstruction as rr
from sports_api.wnba_game_history import WNBAHistoryUpstreamError
from sports_api.wnba_rotation_reconstruction import WNBARotationReconstructionError


HEADERS = [
    "GAME_ID", "TEAM_ID", "TEAM_CITY", "TEAM_NAME", "PERSON_ID",
    "PLAYER_FIRST", "PLAYER_LAST", "IN_TIME_REAL", "OUT_TIME_REAL",
    "PLAYER_PTS", "PT_DIFF", "USG_PCT",
]


def direct_payload():
    away = [
        ["1022600204", 2, "Toronto", "Tempo", 10, "Away", "Player", 0, 24000, 12, -2, .2]
    ]
    home = [
        ["1022600204", 1, "Seattle", "Storm", 20, "Home", "Player", 0, 24000, 15, 4, .3]
    ]
    return {
        "resultSets": [
            {"name": "AwayTeam", "headers": HEADERS, "rowSet": away},
            {"name": "HomeTeam", "headers": HEADERS, "rowSet": home},
        ]
    }


def fallback_result():
    base = {
        "source": "WNBA.com First-Party Page Data",
        "source_urls": {
            "box_score": "https://www.wnba.com/game/1022600204",
            "play_by_play": "https://www.wnba.com/game/1022600204",
        },
        "source_endpoint": "period-aware WNBA.com box-score + play-by-play reconstruction",
        "retrieved_at_utc": "2026-08-27T00:00:00+00:00",
        "cache_hit": False,
        "cache_ttl_seconds": 4,
        "diagnostics": {
            "away": {"unique_solution": True, "max_abs_player_delta_seconds": 0.2},
            "home": {"unique_solution": True, "max_abs_player_delta_seconds": 0.2},
        },
    }
    base["away_rows"] = [{
        "GAME_ID": "1022600204",
        "TEAM_ID": 2,
        "TEAM_CITY": "Toronto",
        "TEAM_NAME": "Tempo",
        "PERSON_ID": 10,
        "PLAYER_FIRST": "Away",
        "PLAYER_LAST": "Player",
        "IN_TIME_REAL": 0,
        "OUT_TIME_REAL": 24000,
        "PLAYER_PTS": None,
        "PT_DIFF": None,
        "USG_PCT": None,
    }]
    base["home_rows"] = [{
        "GAME_ID": "1022600204",
        "TEAM_ID": 1,
        "TEAM_CITY": "Seattle",
        "TEAM_NAME": "Storm",
        "PERSON_ID": 20,
        "PLAYER_FIRST": "Home",
        "PLAYER_LAST": "Player",
        "IN_TIME_REAL": 0,
        "OUT_TIME_REAL": 24000,
        "PLAYER_PTS": None,
        "PT_DIFF": None,
        "USG_PCT": None,
    }]
    return base


class WNBARotationFallbackTests(unittest.TestCase):
    @patch("sports_api.wnba_rotation_reconstruction.reconstruct_game_rotation_rows")
    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_direct_stats_success_never_calls_fallback(self, request, fallback):
        request.return_value = (direct_payload(), "x", False, 60)
        result = m.get_game_rotation("1022600204", 2026)
        fallback.assert_not_called()
        self.assertEqual(result["source"], m.WNBA_HISTORY_SOURCE)
        self.assertNotIn("provider_mode", result)

    @patch("sports_api.wnba_rotation_reconstruction.reconstruct_game_rotation_rows")
    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_transport_failure_uses_certified_fallback(self, request, fallback):
        request.side_effect = WNBAHistoryUpstreamError("timeout")
        fallback.return_value = fallback_result()
        result = m.get_game_rotation("1022600204", 2026)
        fallback.assert_called_once_with("1022600204", 2026)
        self.assertEqual(result["provider_mode"], "first_party_reconstruction_fallback")
        stint = result["home"]["stints"][0]
        self.assertIsNone(stint["player_points_during_stint"])
        self.assertIsNone(stint["team_point_differential_during_stint"])
        self.assertIsNone(stint["usage_percentage_during_stint"])
        self.assertFalse(result["verification"]["fabricated_stint_metrics"])

    @patch("sports_api.wnba_rotation_reconstruction.reconstruct_game_rotation_rows")
    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_malformed_direct_response_is_not_masked_by_fallback(self, request, fallback):
        request.return_value = ({"resultSets": []}, "x", False, 60)
        with self.assertRaises(m.WNBARotationUpstreamError):
            m.get_game_rotation("1022600204", 2026)
        fallback.assert_not_called()

    @patch("sports_api.wnba_rotation_reconstruction.reconstruct_game_rotation_rows")
    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_fallback_failure_remains_fail_closed(self, request, fallback):
        request.side_effect = WNBAHistoryUpstreamError("timeout")
        fallback.side_effect = WNBARotationReconstructionError("ambiguous")
        with self.assertRaisesRegex(m.WNBARotationUpstreamError, "fallback also failed"):
            m.get_game_rotation("1022600204", 2026)

    def test_unique_first_name_can_resolve_official_substitution_label(self):
        players = [
            {
                "player_id": 1629566,
                "first_name": "Xu",
                "last_name": "Han",
                "full_name": "Xu Han",
                "name_initial": "Han",
            },
            {
                "player_id": 1630384,
                "first_name": "Raquel",
                "last_name": "Carrera",
                "full_name": "Raquel Carrera",
                "name_initial": "R. Carrera",
            },
        ]
        lookup = rr._player_lookup(players)
        self.assertEqual(rr._resolve_incoming("Xu", lookup), 1629566)
        self.assertTrue(rr._outgoing_label_matches("Xu", 1629566, players))

    def test_duplicate_first_name_remains_ambiguous_and_fail_closed(self):
        players = [
            {
                "player_id": 1,
                "first_name": "Marine",
                "last_name": "Johannes",
                "full_name": "Marine Johannes",
                "name_initial": "M. Johannes",
            },
            {
                "player_id": 2,
                "first_name": "Marine",
                "last_name": "Fauthoux",
                "full_name": "Marine Fauthoux",
                "name_initial": "M. Fauthoux",
            },
        ]
        lookup = rr._player_lookup(players)
        self.assertIsNone(rr._resolve_incoming("Marine", lookup))

    def test_xu_substitution_parses_with_person_id_as_outgoing_player(self):
        players = [
            {
                "player_id": 1629566,
                "first_name": "Xu",
                "last_name": "Han",
                "full_name": "Xu Han",
                "name_initial": "Han",
            },
            {
                "player_id": 1630384,
                "first_name": "Raquel",
                "last_name": "Carrera",
                "full_name": "Raquel Carrera",
                "name_initial": "R. Carrera",
            },
        ]
        actions = [{
            "event_category": "substitution",
            "team_key": "new-york-liberty",
            "period": 2,
            "elapsed_game_seconds": 898.0,
            "description": "SUB: Carrera FOR Xu",
            "person_id": 1629566,
            "action_number": 240,
            "clock": "PT05M02.00S",
        }]
        by_period, errors = rr._parse_substitutions(
            "new-york-liberty", players, actions
        )
        self.assertEqual(errors, [])
        self.assertEqual(by_period[2][0]["incoming_player_id"], 1630384)
        self.assertEqual(by_period[2][0]["outgoing_player_id"], 1629566)


if __name__ == "__main__":
    unittest.main()
