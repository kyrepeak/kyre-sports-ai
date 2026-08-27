import json
import unittest

import sports_api.wnba_draftkings_endpoint_discovery as d


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload
        self.content = json.dumps(payload).encode("utf-8") if payload is not None else b""

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


def good_document():
    return {
        "sports": [{"id": "2", "name": "Basketball"}],
        "leagues": [{"id": "94682", "name": "WNBA"}],
        "events": [
            {
                "id": "event-1",
                "leagueId": "94682",
                "name": "Connecticut Sun vs New York Liberty",
                "participants": [
                    {"id": "team-1", "name": "Connecticut Sun"},
                    {"id": "team-2", "name": "New York Liberty"},
                ],
            }
        ],
        "markets": [
            {"id": "market-1", "eventId": "event-1", "name": "Player Points"}
        ],
        "selections": [
            {
                "id": "sel-o",
                "marketId": "market-1",
                "label": "Over 22.5",
                "points": 22.5,
                "playerName": "Breanna Stewart",
                "displayOdds": {"american": "-110", "decimal": "1.91"},
            },
            {
                "id": "sel-u",
                "marketId": "market-1",
                "label": "Under 22.5",
                "points": 22.5,
                "playerName": "Breanna Stewart",
                "displayOdds": {"american": "-110", "decimal": "1.91"},
            },
        ],
    }


class Step6EDiscoveryTests(unittest.TestCase):
    def test_01_current_wnba_identity(self):
        self.assertEqual("94682", d.WNBA_LEAGUE_ID)
        self.assertEqual("f0613a94-e73b-4ae6-bf2c-2abafc297015", d.WNBA_TEMPLATE_ID)

    def test_02_default_candidates_are_bounded(self):
        rows = d.resolve_discovery_candidates(env={})
        self.assertGreaterEqual(len(rows), 1)
        self.assertLessEqual(len(rows), d.MAX_CANDIDATES)

    def test_03_only_draftkings_https_allowed(self):
        with self.assertRaises(d.WNBADraftKingsDiscoveryInputError):
            d.resolve_discovery_candidates([{"url": "https://example.com/test"}], env={})

    def test_04_http_is_rejected(self):
        with self.assertRaises(d.WNBADraftKingsDiscoveryInputError):
            d.resolve_discovery_candidates([{"url": "http://sportsbook.draftkings.com/test"}], env={})

    def test_05_env_custom_candidates(self):
        env = {
            d.DISCOVERY_CANDIDATES_ENV: json.dumps([
                {"candidate_id": "x", "family": "test", "url": "https://sportsbook.draftkings.com/test"}
            ])
        }
        rows = d.resolve_discovery_candidates(env=env)
        self.assertEqual("x", rows[0]["candidate_id"])

    def test_06_status_is_network_free(self):
        report = d.get_endpoint_discovery_status({})
        self.assertTrue(report["configuration_ready"])
        self.assertFalse(report["live_probe_performed"])
        self.assertFalse(report["live_endpoint_verified"])

    def test_07_good_document_mentions_wnba(self):
        self.assertTrue(d._document_mentions_wnba(good_document()))

    def test_08_unrelated_document_does_not_match(self):
        self.assertFalse(d._document_mentions_wnba({"leagues": [{"id": "42648", "name": "NBA"}]}))

    def test_09_probe_verifies_supported_wnba_props(self):
        candidate = {
            "candidate_id": "good",
            "family": "test",
            "url": "https://sportsbook.draftkings.com/test",
        }
        report = d.probe_draftkings_wnba_endpoints(
            [candidate],
            env={},
            requester=lambda *args, **kwargs: FakeResponse(200, good_document()),
        )
        self.assertTrue(report["live_endpoint_verified"])
        self.assertEqual("good", report["selected_candidate"]["candidate_id"])
        self.assertEqual(2, report["selected_candidate"]["normalized_offer_count"])
        self.assertEqual(["points"], report["selected_candidate"]["supported_stats"])

    def test_10_http_failure_is_not_verified(self):
        candidate = {"candidate_id": "bad", "family": "test", "url": "https://sportsbook.draftkings.com/bad"}
        report = d.probe_draftkings_wnba_endpoints(
            [candidate], env={}, requester=lambda *args, **kwargs: FakeResponse(404, {"WNBA": True})
        )
        self.assertFalse(report["live_endpoint_verified"])
        self.assertEqual(404, report["attempts"][0]["http_status"])

    def test_11_wnba_without_supported_props_is_not_verified(self):
        candidate = {"candidate_id": "empty", "family": "test", "url": "https://sportsbook.draftkings.com/empty"}
        report = d.probe_draftkings_wnba_endpoints(
            [candidate], env={}, requester=lambda *args, **kwargs: FakeResponse(200, {"leagueId": "94682", "events": []})
        )
        self.assertFalse(report["live_endpoint_verified"])

    def test_12_first_usable_candidate_wins(self):
        candidates = [
            {"candidate_id": "bad", "url": "https://sportsbook.draftkings.com/bad"},
            {"candidate_id": "good", "url": "https://sportsbook.draftkings.com/good"},
        ]
        def requester(url, **kwargs):
            if url.endswith("/bad"):
                return FakeResponse(404, {})
            return FakeResponse(200, good_document())
        report = d.probe_draftkings_wnba_endpoints(candidates, env={}, requester=requester)
        self.assertEqual("good", report["selected_candidate"]["candidate_id"])

    def test_13_no_auth_or_wager_semantics(self):
        report = d.get_endpoint_discovery_status({})
        self.assertFalse(report["safety"]["authentication_used"])
        self.assertFalse(report["safety"]["cookies_used"])
        self.assertFalse(report["safety"]["wager_actions"])
        self.assertFalse(report["safety"]["paid_odds_vendor_used"])

    def test_14_invalid_timeout_rejected(self):
        with self.assertRaises(d.WNBADraftKingsDiscoveryInputError):
            d.probe_draftkings_wnba_endpoints(
                [{"url": "https://sportsbook.draftkings.com/test"}],
                env={d.DISCOVERY_TIMEOUT_ENV: "999"},
                requester=lambda *args, **kwargs: FakeResponse(200, good_document()),
            )


if __name__ == "__main__":
    unittest.main()
