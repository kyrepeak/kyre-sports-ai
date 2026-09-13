from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

import requests

import nfl_rushing_yards_context_api_v1 as client


NOW = datetime(2026, 9, 13, 1, 20, tzinfo=timezone.utc)
EVENT_ID = "401872925"


def _player(athlete_id: str, team_id: str, name: str, *, negative: bool = False) -> dict:
    yards = -2 if negative else 100
    return {
        "official_athlete_id": athlete_id,
        "official_team_id": team_id,
        "player_name": name,
        "position": "QB" if negative else "RB",
        "sample_games": 2,
        "carries": 20,
        "rushing_yards": yards,
        "yards_per_carry": -0.1 if negative else 5.0,
        "carries_per_game": 10.0,
        "rushing_yards_per_game": -1.0 if negative else 50.0,
        "rushing_touchdowns": 1,
        "baseline_season": 2025,
    }


def _front(opponent_id: str) -> dict:
    return {
        "official_team_id": opponent_id,
        "baseline_season": 2025,
        "sample_games": 5,
        "rush_attempts_allowed_per_game": 24.0,
        "rush_yards_allowed_per_game": 108.0,
        "yards_per_carry_allowed": 4.5,
        "rushing_touchdowns_allowed_per_game": 1.0,
        "data_available": True,
    }


def _payload() -> dict:
    return {
        "schema_version": "nfl_rushing_yards_context_v1",
        "ready": True,
        "official_event_id": EVENT_ID,
        "captured_at_utc": "2026-09-13T01:19:30+00:00",
        "official_authority": "ESPN",
        "season": 2026,
        "teams": [
            {
                "official_team_id": "27",
                "opponent_official_team_id": "4",
                "team_name": "Tampa Bay Buccaneers",
                "team_abbreviation": "TB",
                "home_away": "away",
                "player_baseline_season": 2025,
                "player_sample_games": 2,
                "players": [_player("100", "27", "Runner One")],
                "opponent_run_front": _front("4"),
            },
            {
                "official_team_id": "4",
                "opponent_official_team_id": "27",
                "team_name": "Cincinnati Bengals",
                "team_abbreviation": "CIN",
                "home_away": "home",
                "player_baseline_season": 2025,
                "player_sample_games": 2,
                "players": [_player("200", "4", "Kneel QB", negative=True)],
                "opponent_run_front": _front("27"),
            },
        ],
        "identity": {
            "official_event_id_required": True,
            "official_athlete_id_required": True,
            "official_team_id_required": True,
            "player_name_display_only": True,
            "player_name_matching": False,
            "fuzzy_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "semantics": {
            "model_enabled": False,
            "projection_enabled": False,
            "market_enabled": False,
            "sportsbook_influence": 0.0,
            "stake_sizing_enabled": False,
            "wager_actions": False,
        },
        "source_note": "Verified ESPN rushing context.",
    }


class _Response:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return deepcopy(self._payload)


class RushingContextClientTests(unittest.TestCase):
    def test_valid_production_payload_passes_exact_contract(self):
        out = client.validate_context_payload(_payload(), EVENT_ID, now_utc=NOW)
        self.assertTrue(out["ready"])
        self.assertTrue(out["data_available"])
        self.assertEqual(out["schema_version"], "nfl_rushing_yards_context_v1")
        self.assertEqual({team["official_team_id"] for team in out["teams"]}, {"27", "4"})
        self.assertEqual(out["teams"][1]["players"][0]["yards_per_carry"], -0.1)
        self.assertFalse(out["market_enabled"])
        self.assertEqual(out["sportsbook_influence"], 0.0)
        self.assertFalse(out["stake_sizing_enabled"])

    def test_schema_mismatch_fails_closed(self):
        payload = _payload()
        payload["schema_version"] = "old_schema"
        out = client.validate_context_payload(payload, EVENT_ID, now_utc=NOW)
        self.assertFalse(out["ready"])
        self.assertIn("schema mismatch", out["reason"])

    def test_event_identity_mismatch_fails_closed(self):
        payload = _payload()
        payload["official_event_id"] = "401000000"
        out = client.validate_context_payload(payload, EVENT_ID, now_utc=NOW)
        self.assertFalse(out["ready"])
        self.assertIn("event identity mismatch", out["reason"])

    def test_weakened_market_semantics_fail_closed(self):
        payload = _payload()
        payload["semantics"]["market_enabled"] = True
        out = client.validate_context_payload(payload, EVENT_ID, now_utc=NOW)
        self.assertFalse(out["ready"])
        self.assertIn("safety contract", out["reason"])

    def test_duplicate_athlete_identity_fails_closed(self):
        payload = _payload()
        payload["teams"][1]["players"][0]["official_athlete_id"] = "100"
        out = client.validate_context_payload(payload, EVENT_ID, now_utc=NOW)
        self.assertFalse(out["ready"])
        self.assertIn("duplicate athlete", out["reason"])

    def test_nonreciprocal_opponent_identity_fails_closed(self):
        payload = _payload()
        payload["teams"][1]["opponent_official_team_id"] = "99"
        payload["teams"][1]["opponent_run_front"]["official_team_id"] = "99"
        out = client.validate_context_payload(payload, EVENT_ID, now_utc=NOW)
        self.assertFalse(out["ready"])
        self.assertIn("reciprocal opponent", out["reason"])

    def test_available_run_front_requires_complete_metrics(self):
        payload = _payload()
        payload["teams"][0]["opponent_run_front"]["yards_per_carry_allowed"] = None
        out = client.validate_context_payload(payload, EVENT_ID, now_utc=NOW)
        self.assertFalse(out["ready"])
        self.assertIn("run-front", out["reason"])

    def test_fetch_uses_exact_event_id(self):
        calls = []

        def fake_get(url, *, params, timeout, headers):
            calls.append((url, dict(params), timeout, dict(headers)))
            return _Response(_payload())

        with patch.object(client.requests, "get", side_effect=fake_get):
            out = client.fetch_event_context(EVENT_ID, now_utc=NOW, base_url="https://example.test")
        self.assertTrue(out["ready"])
        self.assertEqual(out["request_attempts"], 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], {"event_id": EVENT_ID})
        self.assertTrue(calls[0][0].endswith("/api/v1/nfl/rushing-yards"))

    def test_transient_retry_reuses_same_exact_event_id(self):
        calls = []

        def fake_get(url, *, params, timeout, headers):
            calls.append(dict(params))
            if len(calls) == 1:
                raise requests.exceptions.ReadTimeout("temporary")
            return _Response(_payload())

        with patch.object(client.requests, "get", side_effect=fake_get), patch.object(client.time, "sleep"):
            out = client.fetch_event_context(EVENT_ID, now_utc=NOW, base_url="https://example.test")
        self.assertTrue(out["ready"])
        self.assertEqual(out["request_attempts"], 2)
        self.assertEqual(calls, [{"event_id": EVENT_ID}, {"event_id": EVENT_ID}])

    def test_non_numeric_event_id_never_requests_network(self):
        with patch.object(client.requests, "get") as get:
            out = client.fetch_event_context("not-an-id", now_utc=NOW)
        self.assertFalse(out["ready"])
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
