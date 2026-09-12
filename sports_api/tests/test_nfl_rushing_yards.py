import unittest
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sports_api.api.nfl_rushing_yards import router


EVENT_ID = "401872925"
ATHLETE_ID = "4360238"
TEAM_ID = "27"


def espn_payload(event_id=EVENT_ID):
    return {
        "header": {
            "id": event_id,
            "competitions": [
                {
                    "id": event_id,
                    "date": "2026-09-13T17:00Z",
                    "status": {"type": {"name": "STATUS_SCHEDULED"}},
                    "venue": {"fullName": "Paycor Stadium"},
                    "competitors": [
                        {
                            "homeAway": "away",
                            "team": {"id": TEAM_ID, "displayName": "Tampa Bay Buccaneers", "abbreviation": "TB"},
                        },
                        {
                            "homeAway": "home",
                            "team": {"id": "4", "displayName": "Cincinnati Bengals", "abbreviation": "CIN"},
                        },
                    ],
                }
            ],
        },
        "boxscore": {
            "players": [
                {
                    "team": {"id": TEAM_ID},
                    "statistics": [
                        {
                            "name": "rushing",
                            "labels": ["CAR", "YDS", "AVG", "TD", "LONG"],
                            "athletes": [
                                {
                                    "athlete": {
                                        "id": ATHLETE_ID,
                                        "displayName": "Example Runner",
                                        "position": {"abbreviation": "RB"},
                                    },
                                    "stats": ["16", "78", "4.9", "1", "21"],
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    }


class NflRushingYardsBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(router)
        cls.client = TestClient(app)

    def _response(self, payload, status_code=200):
        response = Mock(status_code=status_code)
        response.json.return_value = payload
        response.raise_for_status.return_value = None
        return response

    @patch("sports_api.api.nfl_rushing_yards.httpx.get")
    def test_exact_event_returns_exact_id_rushing_rows(self, get):
        get.return_value = self._response(espn_payload())
        response = self.client.get(f"/api/v1/nfl/rushing-yards?event_id={EVENT_ID}")
        self.assertEqual(200, response.status_code)
        body = response.json()

        self.assertEqual("nfl_rushing_yards_data_v1", body["schema_version"])
        self.assertTrue(body["ready"])
        self.assertTrue(body["data_available"])
        self.assertEqual(EVENT_ID, body["official_event_id"])
        self.assertFalse(body["identity"]["fuzzy_matching"])
        self.assertFalse(body["identity"]["player_name_matching"])
        self.assertFalse(body["identity"]["synthetic_event_ids"])
        self.assertFalse(body["identity"]["synthetic_player_ids"])
        self.assertFalse(body["data_semantics"]["model_enabled"])
        self.assertFalse(body["data_semantics"]["projection_enabled"])
        self.assertFalse(body["data_semantics"]["market_enabled"])
        self.assertEqual(0.0, body["data_semantics"]["projection_weight"])
        self.assertFalse(body["data_semantics"]["stake_sizing_enabled"])

        player = body["players"][0]
        self.assertEqual(EVENT_ID, player["official_event_id"])
        self.assertEqual(ATHLETE_ID, player["official_athlete_id"])
        self.assertEqual(TEAM_ID, player["official_team_id"])
        self.assertEqual(16, player["carries"])
        self.assertEqual(78, player["rushing_yards"])
        self.assertEqual(4.9, player["yards_per_carry"])
        self.assertEqual(1, player["rushing_touchdowns"])
        self.assertEqual(21, player["long_rush"])

        self.assertEqual({"event": EVENT_ID}, get.call_args.kwargs["params"])

    @patch("sports_api.api.nfl_rushing_yards.httpx.get")
    def test_upstream_event_identity_mismatch_fails_closed(self, get):
        get.return_value = self._response(espn_payload(event_id="999999999"))
        response = self.client.get(f"/api/v1/nfl/rushing-yards?event_id={EVENT_ID}")
        self.assertEqual(409, response.status_code)
        self.assertIn("identity mismatch", response.json()["detail"])

    def test_non_numeric_event_id_is_rejected_before_upstream(self):
        with patch("sports_api.api.nfl_rushing_yards.httpx.get") as get:
            response = self.client.get("/api/v1/nfl/rushing-yards?event_id=TB-CIN")
        self.assertEqual(422, response.status_code)
        get.assert_not_called()

    @patch("sports_api.api.nfl_rushing_yards.httpx.get")
    def test_verified_pregame_event_can_return_no_rushing_rows(self, get):
        payload = espn_payload()
        payload["boxscore"] = {"players": []}
        get.return_value = self._response(payload)
        response = self.client.get(f"/api/v1/nfl/rushing-yards?event_id={EVENT_ID}")
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertTrue(body["ready"])
        self.assertFalse(body["data_available"])
        self.assertEqual([], body["players"])

    @patch("sports_api.api.nfl_rushing_yards.httpx.get")
    def test_name_without_numeric_athlete_id_is_not_promoted_to_identity(self, get):
        payload = espn_payload()
        item = payload["boxscore"]["players"][0]["statistics"][0]["athletes"][0]
        item["athlete"]["id"] = ""
        get.return_value = self._response(payload)
        response = self.client.get(f"/api/v1/nfl/rushing-yards?event_id={EVENT_ID}")
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertFalse(body["data_available"])
        self.assertEqual([], body["players"])


if __name__ == "__main__":
    unittest.main()
