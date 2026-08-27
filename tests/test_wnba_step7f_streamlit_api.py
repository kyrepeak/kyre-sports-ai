from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

import pandas as pd

from wnba_api_client_v1 import (
    BASE_URL,
    KyreWNBAAPIClient,
    KyreWNBAAPIError,
    _safe_path,
)
from wnba_api_schedule_bridge_v1 import (
    API_SOURCE_LABEL,
    WNBAAPIScheduleBridgeError,
    api_schedule_frame,
)


class _Guarded:
    @staticmethod
    def _guard_schedule(frame):
        return frame.copy()


class _V24:
    guarded = _Guarded()


class _FakeScheduleModule:
    v24 = _V24()

    @staticmethod
    def _empty_schedule():
        return pd.DataFrame(columns=[
            "game_id", "game_date", "first_tip_et", "status", "status_text",
            "away_team_id", "away_team", "away_tricode", "home_team_id",
            "home_team", "home_tricode", "venue", "source",
        ])


def _sample_payload():
    return {
        "season": 2026,
        "source_variant": "wnba_public_schedule_api",
        "source_url": "https://www.wnba.com/api/schedule",
        "games": [
            {
                "game_id": "1022600123",
                "official_schedule_date": "2026-08-27",
                "game_datetime_eastern": "2026-08-27T19:30:00-04:00",
                "status": {"category": "scheduled", "text": "7:30 pm ET"},
                "away": {
                    "official_team_id": 1611661313,
                    "full_name": "New York Liberty",
                    "team_tricode": "NYL",
                },
                "home": {
                    "official_team_id": 1611661328,
                    "full_name": "Phoenix Mercury",
                    "team_tricode": "PHX",
                },
                "venue": {"name": "PHX Arena", "city": "Phoenix"},
            }
        ],
    }


class Step7FClientTests(unittest.TestCase):
    def test_certified_origin_is_pinned(self):
        self.assertEqual(BASE_URL, "https://kyre-sports-api.onrender.com")
        self.assertEqual(KyreWNBAAPIClient().base_url, BASE_URL)
        with self.assertRaises(KyreWNBAAPIError):
            KyreWNBAAPIClient(base_url="https://evil.example.com")
        with self.assertRaises(KyreWNBAAPIError):
            KyreWNBAAPIClient(base_url="http://kyre-sports-api.onrender.com")
        with self.assertRaises(KyreWNBAAPIError):
            KyreWNBAAPIClient(base_url="https://kyre-sports-api.onrender.com/evil")

    def test_only_certified_read_paths_are_allowed(self):
        self.assertEqual(_safe_path("/health"), "/health")
        self.assertEqual(_safe_path("/api/v1/wnba/teams"), "/api/v1/wnba/teams")
        for bad in (
            "https://evil.example.com/x",
            "//evil.example.com/x",
            "/api/v1/mlb/games/today",
            "/admin",
            "api/v1/wnba/teams",
        ):
            with self.assertRaises(KyreWNBAAPIError, msg=bad):
                _safe_path(bad)

    @patch("wnba_api_client_v1.requests.get")
    def test_health_is_get_only_and_identity_checked(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {"status": "ok"}
        get.return_value = response
        body = KyreWNBAAPIClient(attempts=1).health()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(get.call_count, 1)
        args, kwargs = get.call_args
        self.assertEqual(args[0], BASE_URL + "/health")
        self.assertNotIn("authorization", {str(k).lower() for k in kwargs.get("headers", {})})

    @patch("wnba_api_client_v1.requests.get")
    def test_games_for_date_passes_only_query_params(self, get):
        response = Mock(status_code=200)
        response.json.return_value = {"season": 2026, "games": []}
        get.return_value = response
        KyreWNBAAPIClient(attempts=1).games_for_date("2026-08-27")
        args, kwargs = get.call_args
        self.assertEqual(args[0], BASE_URL + "/api/v1/wnba/games")
        self.assertEqual(kwargs["params"], {"date": "2026-08-27", "season": 2026})

    @patch("wnba_api_client_v1.requests.get")
    def test_non_200_fails_closed(self, get):
        response = Mock(status_code=502)
        response.json.return_value = {"detail": "upstream failed"}
        get.return_value = response
        with self.assertRaises(KyreWNBAAPIError):
            KyreWNBAAPIClient(attempts=1).games_today()


class Step7FScheduleBridgeTests(unittest.TestCase):
    def test_api_payload_maps_to_historical_schedule_contract(self):
        frame = api_schedule_frame(_sample_payload(), "2026-08-27", _FakeScheduleModule)
        self.assertEqual(len(frame), 1)
        row = frame.iloc[0]
        self.assertEqual(row["game_id"], "1022600123")
        self.assertEqual(row["game_date"], "2026-08-27")
        self.assertEqual(row["away_team"], "New York Liberty")
        self.assertEqual(row["away_tricode"], "NYL")
        self.assertEqual(row["home_team"], "Phoenix Mercury")
        self.assertEqual(row["home_tricode"], "PHX")
        self.assertEqual(row["status"], "SCHEDULED")
        self.assertEqual(row["source"], API_SOURCE_LABEL)

    def test_off_day_is_a_valid_empty_frame(self):
        frame = api_schedule_frame(
            {"season": 2026, "games": [], "source_variant": "wnba_public_schedule_api"},
            "2026-08-27",
            _FakeScheduleModule,
        )
        self.assertTrue(frame.empty)
        self.assertIn("game_id", frame.columns)

    def test_wrong_season_or_shape_fails_closed(self):
        with self.assertRaises(WNBAAPIScheduleBridgeError):
            api_schedule_frame({"season": 2025, "games": []}, "2026-08-27", _FakeScheduleModule)
        with self.assertRaises(WNBAAPIScheduleBridgeError):
            api_schedule_frame({"season": 2026, "games": None}, "2026-08-27", _FakeScheduleModule)


if __name__ == "__main__":
    unittest.main()
