import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import requests

import nfl_rushing_yards_api_v1 as rushing_api


NOW = datetime(2026, 9, 12, 22, 0, tzinfo=timezone.utc)
EVENT_ID = "401872925"
ATHLETE_ID = "4360238"
TEAM_ID = "27"


def valid_payload(**overrides):
    payload = {
        "schema_version": rushing_api.SCHEMA_VERSION,
        "ready": True,
        "data_available": True,
        "official_event_id": EVENT_ID,
        "captured_at_utc": (NOW - timedelta(minutes=20)).isoformat(),
        "players": [
            {
                "official_event_id": EVENT_ID,
                "official_athlete_id": ATHLETE_ID,
                "official_team_id": TEAM_ID,
                "player_name": "Example Runner",
                "position": "RB",
                "carries": 16,
                "rushing_yards": 78,
            }
        ],
        "matchup": {"away": {"official_team_id": TEAM_ID}},
        "identity": {
            "fuzzy_matching": False,
            "player_name_matching": False,
            "synthetic_event_ids": False,
            "synthetic_player_ids": False,
        },
        "data_semantics": {
            "model_enabled": False,
            "projection_enabled": False,
            "market_enabled": False,
            "projection_weight": 0.0,
            "stake_sizing_enabled": False,
        },
    }
    payload.update(overrides)
    return payload


class RushingYardsApiClientContractTests(unittest.TestCase):
    def test_valid_exact_id_payload_is_accepted_without_market_ttl(self):
        out = rushing_api.validate_event_payload(valid_payload(), EVENT_ID, now_utc=NOW)
        self.assertTrue(out["ready"])
        self.assertTrue(out["data_available"])
        self.assertEqual(EVENT_ID, out["official_event_id"])
        self.assertEqual(ATHLETE_ID, out["players"][0]["official_athlete_id"])
        self.assertEqual(0.0, out["projection_weight"])
        self.assertFalse(out["market_enabled"])
        # Non-market rushing data is intentionally allowed to be older than the
        # frozen Passing Yards 300-second sportsbook-price freshness window.
        self.assertGreater(out["age_seconds"], 300)

    def test_non_numeric_event_id_fails_before_transport(self):
        with patch.object(rushing_api.requests, "get") as get:
            out = rushing_api.fetch_event_data("TB-v-CIN", now_utc=NOW)
        self.assertFalse(out["ready"])
        self.assertIn("official ESPN event ID", out["reason"])
        get.assert_not_called()

    def test_schema_and_event_identity_mismatches_fail_closed(self):
        wrong_schema = valid_payload(schema_version="wrong")
        self.assertFalse(rushing_api.validate_event_payload(wrong_schema, EVENT_ID, now_utc=NOW)["ready"])

        wrong_event = valid_payload(official_event_id="999999999")
        out = rushing_api.validate_event_payload(wrong_event, EVENT_ID, now_utc=NOW)
        self.assertFalse(out["ready"])
        self.assertIn("identity mismatch", out["reason"])

    def test_identity_and_semantics_contracts_fail_closed(self):
        fuzzy = valid_payload()
        fuzzy["identity"] = dict(fuzzy["identity"], fuzzy_matching=True)
        self.assertFalse(rushing_api.validate_event_payload(fuzzy, EVENT_ID, now_utc=NOW)["ready"])

        market_on = valid_payload()
        market_on["data_semantics"] = dict(market_on["data_semantics"], market_enabled=True)
        out = rushing_api.validate_event_payload(market_on, EVENT_ID, now_utc=NOW)
        self.assertFalse(out["ready"])
        self.assertIn("safety contract", out["reason"])

    def test_future_timestamp_fails_closed(self):
        payload = valid_payload(captured_at_utc=(NOW + timedelta(minutes=2)).isoformat())
        out = rushing_api.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
        self.assertFalse(out["ready"])
        self.assertIn("future", out["reason"])

    def test_duplicate_exact_athlete_id_fails_closed(self):
        payload = valid_payload()
        payload["players"] = payload["players"] * 2
        out = rushing_api.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
        self.assertFalse(out["ready"])
        self.assertIn("duplicate athlete", out["reason"])

    def test_available_flag_without_valid_exact_id_player_fails_closed(self):
        payload = valid_payload(players=[{"player_name": "Name Only"}])
        out = rushing_api.validate_event_payload(payload, EVENT_ID, now_utc=NOW)
        self.assertFalse(out["ready"])
        self.assertIn("no exact-ID player", out["reason"])

    def test_transient_timeout_retries_once_with_same_exact_event_id(self):
        response = Mock(status_code=200)
        response.json.return_value = valid_payload()
        with patch.object(
            rushing_api.requests,
            "get",
            side_effect=[requests.exceptions.ReadTimeout("slow"), response],
        ) as get, patch.object(rushing_api.time, "sleep") as sleep:
            out = rushing_api.fetch_event_data(EVENT_ID, now_utc=NOW, base_url="https://example.test")

        self.assertTrue(out["ready"])
        self.assertEqual(2, out["request_attempts"])
        self.assertEqual(2, get.call_count)
        for call in get.call_args_list:
            self.assertEqual({"event_id": EVENT_ID}, call.kwargs["params"])
            self.assertEqual("https://example.test/api/v1/nfl/rushing-yards", call.args[0])
        sleep.assert_called_once_with(rushing_api.RETRY_BACKOFF_SECONDS)

    def test_http_failure_is_one_shot_and_fails_closed(self):
        response = Mock(status_code=503)
        with patch.object(rushing_api.requests, "get", return_value=response) as get:
            out = rushing_api.fetch_event_data(EVENT_ID, now_utc=NOW, base_url="https://example.test")
        self.assertFalse(out["ready"])
        self.assertEqual(503, out["http"])
        self.assertEqual(1, out["request_attempts"])
        self.assertEqual(1, get.call_count)

    def test_athlete_lookup_is_exact_id_only(self):
        event = rushing_api.validate_event_payload(valid_payload(), EVENT_ID, now_utc=NOW)
        hit = rushing_api.data_for_athlete(event, ATHLETE_ID)
        self.assertTrue(hit["ready"])
        self.assertEqual(ATHLETE_ID, hit["official_athlete_id"])

        miss = rushing_api.data_for_athlete(event, "999999")
        self.assertFalse(miss["ready"])
        self.assertIn("exact-ID", miss["reason"])

        name = rushing_api.data_for_athlete(event, "Example Runner")
        self.assertFalse(name["ready"])
        self.assertIn("official ESPN athlete ID", name["reason"])


if __name__ == "__main__":
    unittest.main()
