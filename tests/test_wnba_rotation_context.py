import unittest
from unittest.mock import patch

from sports_api import wnba_rotation_context as m


GAME_ID = "1022600204"
HEADERS = [
    "GAME_ID", "TEAM_ID", "TEAM_CITY", "TEAM_NAME", "PERSON_ID",
    "PLAYER_FIRST", "PLAYER_LAST", "IN_TIME_REAL", "OUT_TIME_REAL",
    "PLAYER_PTS", "PT_DIFF", "USG_PCT",
]


def _payload(*, away_rows=None, home_rows=None):
    if away_rows is None:
        away_rows = [[
            GAME_ID, 2, "Toronto", "Tempo", 10, "Away", "Player",
            0, 24000, 12, -2, 0.20,
        ]]
    if home_rows is None:
        home_rows = [[
            GAME_ID, 1, "Seattle", "Storm", 20, "Home", "Player",
            0, 24000, 15, 4, 0.30,
        ]]
    return {
        "resultSets": [
            {"name": "AwayTeam", "headers": HEADERS, "rowSet": away_rows},
            {"name": "HomeTeam", "headers": HEADERS, "rowSet": home_rows},
        ]
    }


class WNBARotationStep4RFrozenContractTests(unittest.TestCase):
    """Regression contract captured from the frozen pre-fallback Step 4R behavior."""

    def test_input_validation_contract(self):
        self.assertEqual(m._game_id(f" {GAME_ID} "), GAME_ID)
        for bad in ("", "123", "abcdefghij", "10226002040"):
            with self.subTest(game_id=bad):
                with self.assertRaises(ValueError):
                    m._game_id(bad)
        self.assertEqual(m._player_id(123), 123)
        for bad in (0, -1, True, 1.5):
            with self.subTest(player_id=bad):
                with self.assertRaises(ValueError):
                    m._player_id(bad)
        self.assertEqual(m._choice("player_pts", m.ALLOWED_ROTATION_STATS, "rotation_stat"), "PLAYER_PTS")
        with self.assertRaises(ValueError):
            m._choice("NOPE", m.ALLOWED_ROTATION_STATS, "rotation_stat")
        self.assertEqual(m._recent_game_count(1), 1)
        self.assertEqual(m._recent_game_count(20), 20)
        for bad in (0, 21, True, 2.5):
            with self.subTest(last_n_games=bad):
                with self.assertRaises(ValueError):
                    m._recent_game_count(bad)

    def test_period_boundary_clock_contract(self):
        self.assertEqual(m._clock_from_tenths(0, boundary_role="in")["game_clock"], "10:00.0")
        q1_out = m._clock_from_tenths(6000, boundary_role="out")
        self.assertEqual((q1_out["period_label"], q1_out["game_clock"]), ("Q1", "0:00.0"))
        q2_in = m._clock_from_tenths(6000, boundary_role="in")
        self.assertEqual((q2_in["period_label"], q2_in["game_clock"]), ("Q2", "10:00.0"))
        regulation_out = m._clock_from_tenths(24000, boundary_role="out")
        self.assertEqual((regulation_out["period_label"], regulation_out["game_clock"]), ("Q4", "0:00.0"))
        ot1_in = m._clock_from_tenths(24000, boundary_role="in")
        self.assertEqual((ot1_in["period_label"], ot1_in["game_clock"]), ("OT1", "5:00.0"))
        ot1_out = m._clock_from_tenths(27000, boundary_role="out")
        self.assertEqual((ot1_out["period_label"], ot1_out["game_clock"]), ("OT1", "0:00.0"))
        ot2_in = m._clock_from_tenths(27000, boundary_role="in")
        self.assertEqual((ot2_in["period_label"], ot2_in["game_clock"]), ("OT2", "5:00.0"))

    def test_result_set_schema_is_fail_closed(self):
        with self.assertRaises(m.WNBARotationUpstreamError):
            m._result_set({"resultSets": []}, "AwayTeam")
        missing_headers = [h for h in HEADERS if h != "USG_PCT"]
        payload = {"resultSets": [{"name": "AwayTeam", "headers": missing_headers, "rowSet": []}]}
        with self.assertRaisesRegex(m.WNBARotationUpstreamError, "USG_PCT"):
            m._result_set(payload, "AwayTeam")
        malformed = {"resultSets": [{"name": "AwayTeam", "headers": HEADERS, "rowSet": [[GAME_ID]]}]}
        with self.assertRaisesRegex(m.WNBARotationUpstreamError, "malformed row"):
            m._result_set(malformed, "AwayTeam")

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_direct_stats_success_preserves_frozen_shape(self, request):
        request.return_value = (_payload(), "2026-08-27T00:00:00+00:00", False, 60)
        result = m.get_game_rotation(GAME_ID, 2026)

        self.assertEqual(result["source"], m.WNBA_HISTORY_SOURCE)
        self.assertEqual(result["source_url"], m.WNBA_HISTORY_SOURCE_URL)
        self.assertEqual(result["source_endpoint"], m.ROTATION_ENDPOINT)
        self.assertEqual(result["data_type"], "official_game_rotation_stints")
        self.assertEqual(result["game_id"], GAME_ID)
        self.assertEqual(result["rotation_stat"], "PLAYER_PTS")
        self.assertNotIn("provider_mode", result)
        self.assertEqual(result["time_basis"]["source_fields"], ["IN_TIME_REAL", "OUT_TIME_REAL"])
        self.assertEqual(result["time_basis"]["derived_seconds_divisor"], 10)
        self.assertTrue(result["verification"]["required_rotation_schema_verified"])
        self.assertTrue(result["verification"]["no_projected_minutes_created"])
        self.assertTrue(result["verification"]["no_betting_probability_created"])

        away = result["away"]
        self.assertEqual(away["team_full_name"], "Toronto Tempo")
        self.assertEqual(away["player_count"], 1)
        self.assertEqual(away["stint_count"], 1)
        self.assertEqual(away["maximum_source_time_tenths"], 24000)
        player = away["players"][0]
        self.assertEqual(player["player_id"], 10)
        self.assertEqual(player["player_name"], "Away Player")
        self.assertEqual(player["tracked_seconds"], 2400.0)
        self.assertEqual(player["tracked_minutes"], 40.0)
        self.assertTrue(player["started_game"])
        self.assertTrue(player["finished_game"])
        self.assertEqual(player["player_points_during_stints"], 12.0)
        self.assertEqual(player["time_weighted_usage_percentage"], 0.2)

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_direct_empty_rotation_is_not_found(self, request):
        request.return_value = (_payload(away_rows=[], home_rows=[]), "x", False, 60)
        with self.assertRaises(m.WNBARotationNotFoundError):
            m.get_game_rotation(GAME_ID, 2026)

    @patch("sports_api.wnba_rotation_context._request_stats_json")
    def test_direct_one_sided_rotation_is_rejected(self, request):
        request.return_value = (_payload(home_rows=[]), "x", False, 60)
        with self.assertRaisesRegex(m.WNBARotationUpstreamError, "only one team"):
            m.get_game_rotation(GAME_ID, 2026)

    @patch("sports_api.wnba_rotation_context.get_game_rotation")
    def test_game_player_rotation_contract(self, get_game_rotation):
        get_game_rotation.return_value = {
            "source": "WNBA Stats API",
            "source_url": "https://stats.wnba.com/stats/",
            "source_endpoint": "gamerotation",
            "league_id": "10",
            "game_id": GAME_ID,
            "rotation_stat": "PLAYER_PTS",
            "time_basis": {"derived_seconds_divisor": 10},
            "away": {"players": [{"player_id": 10, "player_name": "Away Player", "stints": []}]},
            "home": {"players": [{"player_id": 20, "player_name": "Home Player", "stints": []}]},
        }
        result = m.get_game_player_rotation(GAME_ID, 10, 2026)
        self.assertEqual(result["data_type"], "official_game_player_rotation_stints")
        self.assertEqual(result["player"]["player_id"], 10)
        self.assertNotIn("provider_mode", result)
        with self.assertRaises(m.WNBARotationNotFoundError):
            m.get_game_player_rotation(GAME_ID, 999, 2026)

    @patch("sports_api.wnba_rotation_context.get_game_rotation")
    @patch("sports_api.wnba_rotation_context.get_player_game_log_dataset")
    def test_recent_rotation_context_aggregation_contract(self, history, get_rotation):
        history.return_value = {
            "games": [
                {"game_id": GAME_ID, "game_date": "2026-08-01", "matchup": "TOR @ SEA"},
                {"game_id": "1022600205", "game_date": "2026-08-03", "matchup": "TOR vs. MIN"},
            ]
        }
        player = {
            "player_id": 10,
            "player_name": "Away Player",
            "team_key": "toronto-tempo",
            "started_game": True,
            "stints": [{
                "duration_seconds": 1200.0,
                "usage_percentage_during_stint": 0.25,
                "player_points_during_stint": 8.0,
                "team_point_differential_during_stint": 2.0,
            }],
        }
        get_rotation.side_effect = [
            {"away": {"players": [player]}, "home": {"players": []}},
            m.WNBARotationNotFoundError("missing"),
        ]
        result = m.get_player_recent_rotation_context(10, 2026, last_n_games=2)
        self.assertEqual(result["selected_game_count"], 2)
        self.assertEqual(result["rotation_game_count"], 1)
        self.assertEqual(result["missing_rotation_game_ids"], ["1022600205"])
        self.assertEqual(result["aggregate"]["tracked_minutes"], 20.0)
        self.assertEqual(result["aggregate"]["starts_in_rotation_games"], 1)
        self.assertEqual(result["aggregate"]["start_share"], 1.0)
        self.assertEqual(result["aggregate"]["time_weighted_usage_percentage"], 0.25)
        self.assertTrue(result["verification"]["missing_rotation_games_are_reported_not_fabricated"])


if __name__ == "__main__":
    unittest.main()
