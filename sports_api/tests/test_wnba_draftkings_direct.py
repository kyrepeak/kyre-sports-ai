import json
import tempfile
import unittest
from pathlib import Path

import sports_api.collectors.wnba_draftkings_direct as d


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = json.dumps(payload).encode("utf-8")

    def json(self):
        return self._payload


class Step6DDirectDraftKingsTests(unittest.TestCase):
    def setUp(self):
        self.url = "https://sportsbook-nash.draftkings.com/sites/US-SB/api/test/wnba"
        self.date = "2026-08-27"
        self.season = 2026

    def modern_payload(self):
        return {
            "events": [
                {
                    "id": "evt-1",
                    "name": "Las Vegas Aces vs Phoenix Mercury",
                    "participants": [
                        {"name": "Las Vegas Aces"},
                        {"name": "Phoenix Mercury"},
                    ],
                }
            ],
            "markets": [
                {
                    "id": "mkt-1",
                    "eventId": "evt-1",
                    "name": "Player Points",
                    "participants": [{"name": "A'ja Wilson"}],
                }
            ],
            "selections": [
                {
                    "id": "sel-o",
                    "marketId": "mkt-1",
                    "label": "Over 24.5",
                    "displayOdds": {"american": "−115", "decimal": "1.87"},
                    "participants": [{"name": "A'ja Wilson"}],
                },
                {
                    "id": "sel-u",
                    "marketId": "mkt-1",
                    "label": "Under 24.5",
                    "displayOdds": {"american": "+100", "decimal": "2.00"},
                    "participants": [{"name": "A'ja Wilson"}],
                },
            ],
        }

    def requester(self, url, **kwargs):
        self.assertEqual(self.url, url)
        self.assertIn("headers", kwargs)
        return FakeResponse(self.modern_payload())

    def test_01_urls_require_configuration(self):
        with self.assertRaises(d.WNBADraftKingsDirectNotReadyError):
            d.resolve_draftkings_urls(env={})

    def test_02_urls_parse_json_array(self):
        env = {d.DRAFTKINGS_URLS_ENV: json.dumps([self.url])}
        self.assertEqual([self.url], d.resolve_draftkings_urls(env=env))

    def test_03_urls_reject_http(self):
        with self.assertRaises(d.WNBADraftKingsDirectModelInputError):
            d.resolve_draftkings_urls(["http://sportsbook.draftkings.com/x"])

    def test_04_urls_reject_non_draftkings_host(self):
        with self.assertRaises(d.WNBADraftKingsDirectModelInputError):
            d.resolve_draftkings_urls(["https://example.com/x"])

    def test_05_urls_reject_embedded_credentials(self):
        with self.assertRaises(d.WNBADraftKingsDirectModelInputError):
            d.resolve_draftkings_urls(["https://user:pass@sportsbook.draftkings.com/x"])

    def test_06_urls_are_deduplicated(self):
        self.assertEqual([self.url], d.resolve_draftkings_urls([self.url, self.url]))

    def test_07_status_is_network_free(self):
        report = d.describe_draftkings_direct_onboarding({d.DRAFTKINGS_URLS_ENV: json.dumps([self.url])})
        self.assertTrue(report["ready"])
        self.assertFalse(report["secret_required"])
        self.assertEqual("GET", report["http_method"])

    def test_08_status_does_not_return_url_query_secrets(self):
        url = self.url + "?token=do-not-return"
        report = d.describe_draftkings_direct_onboarding({d.DRAFTKINGS_URLS_ENV: json.dumps([url])})
        self.assertNotIn("do-not-return", str(report))

    def test_09_modern_points_normalization(self):
        offers = d.normalize_draftkings_document(self.modern_payload(), captured_at_utc="2026-08-27T00:00:00+00:00")
        self.assertEqual(2, len(offers))
        self.assertEqual("points", offers[0]["stat"])
        self.assertEqual("A'ja Wilson", offers[0]["player_name"])
        self.assertEqual(24.5, offers[0]["line"])

    def test_10_unicode_minus_normalizes(self):
        offers = d.normalize_draftkings_document(self.modern_payload())
        self.assertEqual(-115, offers[0]["american_odds"])

    def test_11_positive_american_odds_normalize(self):
        offers = d.normalize_draftkings_document(self.modern_payload())
        self.assertEqual(100, offers[1]["american_odds"])

    def test_12_rebound_stat_maps(self):
        payload = self.modern_payload()
        payload["markets"][0]["name"] = "Player Rebounds"
        self.assertEqual("rebounds", d.normalize_draftkings_document(payload)[0]["stat"])

    def test_13_assist_stat_maps(self):
        payload = self.modern_payload()
        payload["markets"][0]["name"] = "Player Assists"
        self.assertEqual("assists", d.normalize_draftkings_document(payload)[0]["stat"])

    def test_14_pra_stat_maps(self):
        payload = self.modern_payload()
        payload["markets"][0]["name"] = "Player Points + Rebounds + Assists"
        self.assertEqual("pra", d.normalize_draftkings_document(payload)[0]["stat"])

    def test_15_team_participant_is_not_used_as_player(self):
        payload = self.modern_payload()
        payload["markets"][0]["participants"] = [{"name": "Las Vegas Aces"}]
        for row in payload["selections"]:
            row["participants"] = [{"name": "Las Vegas Aces"}]
        self.assertEqual([], d.normalize_draftkings_document(payload))

    def test_16_unsupported_market_is_ignored(self):
        payload = self.modern_payload()
        payload["markets"][0]["name"] = "First Basket"
        self.assertEqual([], d.normalize_draftkings_document(payload))

    def test_17_non_object_response_rejected(self):
        with self.assertRaises(d.WNBADraftKingsDirectModelInputError):
            d.normalize_draftkings_document([])

    def test_18_fetch_builds_canonical_feed(self):
        feed = d.fetch_draftkings_canonical_feed(
            date=self.date,
            season=self.season,
            urls=[self.url],
            requester=self.requester,
        )
        self.assertEqual(d.CANONICAL_FEED_FORMAT, feed["feed_format"])
        self.assertEqual(2, len(feed["offers"]))
        self.assertEqual("american", feed["odds_format"])

    def test_19_fetch_rejects_bad_date(self):
        with self.assertRaises(d.WNBADraftKingsDirectModelInputError):
            d.fetch_draftkings_canonical_feed(date="08/27/2026", season=2026, urls=[self.url], requester=self.requester)

    def test_20_http_error_fails_closed(self):
        def requester(url, **kwargs):
            return FakeResponse({}, status_code=503)
        with self.assertRaises(d.WNBADraftKingsDirectUpstreamError):
            d.fetch_draftkings_canonical_feed(date=self.date, season=self.season, urls=[self.url], requester=requester)

    def test_21_zero_supported_offers_is_not_ready(self):
        def requester(url, **kwargs):
            return FakeResponse({"events": [], "markets": [], "selections": []})
        with self.assertRaises(d.WNBADraftKingsDirectNotReadyError):
            d.fetch_draftkings_canonical_feed(date=self.date, season=self.season, urls=[self.url], requester=requester)

    def test_22_sync_writes_kyre_owned_feed(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "market.json")
            report = d.sync_draftkings_to_kyre_feed(
                date=self.date,
                season=self.season,
                urls=[self.url],
                requester=self.requester,
                path=path,
            )
            self.assertTrue(report["synced"])
            self.assertTrue(Path(path).is_file())
            self.assertEqual(2, report["storage"]["offer_count"])

    def test_23_sync_never_returns_credentials(self):
        with tempfile.TemporaryDirectory() as td:
            path = str(Path(td) / "market.json")
            report = d.sync_draftkings_to_kyre_feed(
                date=self.date,
                season=self.season,
                urls=[self.url + "?public=1"],
                requester=lambda url, **kwargs: FakeResponse(self.modern_payload()),
                path=path,
            )
            self.assertFalse(report["safety"]["authentication_used"])
            self.assertFalse(report["safety"]["cookies_used"])
            self.assertFalse(report["safety"]["wager_action_performed"])

    def test_24_legacy_nested_offer_normalizes(self):
        payload = {
            "eventGroup": {
                "events": [{"eventId": "evt-1", "participants": [{"name": "Las Vegas Aces"}, {"name": "Phoenix Mercury"}]}],
                "offerCategories": [{
                    "offerSubcategoryDescriptors": [{
                        "offerSubcategory": {
                            "offers": [[{
                                "eventId": "evt-1",
                                "offerId": "m-legacy",
                                "label": "A'ja Wilson Points",
                                "outcomes": [
                                    {"outcomeId": "o1", "label": "Over", "line": 25.5, "oddsAmerican": -110},
                                    {"outcomeId": "o2", "label": "Under", "line": 25.5, "oddsAmerican": -120},
                                ],
                            }]]
                        }
                    }]
                }]
            }
        }
        offers = d.normalize_draftkings_document(payload)
        self.assertEqual(2, len(offers))
        self.assertEqual("A'ja Wilson", offers[0]["player_name"])
        self.assertEqual("points", offers[0]["stat"])


if __name__ == "__main__":
    unittest.main()
