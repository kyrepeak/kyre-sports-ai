import copy
import unittest

import sports_api.wnba_draftkings_shadow_ingestion as s


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = b"{}"

    def json(self):
        return self._payload


class Step6GShadowIngestionTests(unittest.TestCase):
    def payload(self, stat, suffix):
        market_name = {
            "points": "Player Points",
            "rebounds": "Player Rebounds",
            "assists": "Player Assists",
            "pra": "Player Points + Rebounds + Assists",
        }[stat]
        return {
            "events": [{
                "id": "evt-1",
                "name": "Las Vegas Aces vs Phoenix Mercury",
                "participants": [{"name": "Las Vegas Aces"}, {"name": "Phoenix Mercury"}],
            }],
            "markets": [
                {"id": f"mkt-{suffix}-1", "eventId": "evt-1", "name": market_name,
                 "participants": [{"name": "A'ja Wilson"}]},
                {"id": f"mkt-{suffix}-2", "eventId": "evt-1", "name": market_name,
                 "participants": [{"name": "Jackie Young"}]},
            ],
            "selections": [
                {"id": f"sel-{suffix}-1-o", "marketId": f"mkt-{suffix}-1", "label": "Over 20.5",
                 "displayOdds": {"american": "-110"}, "participants": [{"name": "A'ja Wilson"}]},
                {"id": f"sel-{suffix}-1-u", "marketId": f"mkt-{suffix}-1", "label": "Under 20.5",
                 "displayOdds": {"american": "-120"}, "participants": [{"name": "A'ja Wilson"}]},
                {"id": f"sel-{suffix}-2-o", "marketId": f"mkt-{suffix}-2", "label": "Over 12.5",
                 "displayOdds": {"american": "+100"}, "participants": [{"name": "Jackie Young"}]},
                {"id": f"sel-{suffix}-2-u", "marketId": f"mkt-{suffix}-2", "label": "Under 12.5",
                 "displayOdds": {"american": "-130"}, "participants": [{"name": "Jackie Young"}]},
            ],
        }

    def requester(self, url, **kwargs):
        for index, stat in enumerate(s.REQUIRED_STATS, start=1):
            if url == s.FROZEN_ENDPOINTS[stat]["url"]:
                return FakeResponse(self.payload(stat, str(index)))
        raise AssertionError(url)

    def valid_feed(self):
        result = s.run_shadow_ingestion(date="2026-08-27", season=2026, requester=self.requester)
        self.assertTrue(result["ready_for_auto_sync"])
        # Rebuild a compact valid feed for mutation tests.
        offers = []
        for index, stat in enumerate(s.REQUIRED_STATS, start=1):
            doc = self.payload(stat, str(index))
            from sports_api.collectors.wnba_draftkings_direct import normalize_draftkings_document
            offers.extend(normalize_draftkings_document(doc, captured_at_utc="2026-08-27T00:00:00+00:00"))
        return {
            "schema_version": "wnba_step_6c_owned_market_feed_v1",
            "date": "2026-08-27",
            "season": 2026,
            "captured_at_utc": "2026-08-27T00:00:00+00:00",
            "feed_source": "test",
            "feed_format": "canonical_offers_v1",
            "odds_format": "american",
            "offers": offers,
        }

    def test_01_exact_four_endpoints_frozen(self):
        self.assertEqual(4, len(s.FROZEN_ENDPOINTS))
        self.assertEqual(set(s.REQUIRED_STATS), set(s.FROZEN_ENDPOINTS))

    def test_02_urls_pin_wnba_league(self):
        for url in s.frozen_draftkings_urls():
            self.assertIn("/leagues/94682/", url)

    def test_03_points_ids_frozen(self):
        self.assertEqual("1215", s.FROZEN_ENDPOINTS["points"]["category_id"])
        self.assertEqual("12488", s.FROZEN_ENDPOINTS["points"]["subcategory_id"])

    def test_04_rebounds_ids_frozen(self):
        self.assertEqual(("1216", "12492"), (s.FROZEN_ENDPOINTS["rebounds"]["category_id"], s.FROZEN_ENDPOINTS["rebounds"]["subcategory_id"]))

    def test_05_assists_ids_frozen(self):
        self.assertEqual(("1217", "12495"), (s.FROZEN_ENDPOINTS["assists"]["category_id"], s.FROZEN_ENDPOINTS["assists"]["subcategory_id"]))

    def test_06_pra_ids_frozen(self):
        self.assertEqual(("583", "5001"), (s.FROZEN_ENDPOINTS["pra"]["category_id"], s.FROZEN_ENDPOINTS["pra"]["subcategory_id"]))

    def test_07_readiness_is_network_free_and_safe(self):
        report = s.get_shadow_readiness()
        self.assertEqual(4, report["frozen_endpoint_count"])
        self.assertFalse(report["automatic_sync_enabled_by_step6g"])
        self.assertFalse(report["safety"]["production_feed_written"])

    def test_08_shadow_collects_all_four_stats(self):
        report = s.run_shadow_ingestion(date="2026-08-27", season=2026, requester=self.requester)
        self.assertEqual(set(s.REQUIRED_STATS), set(report["stat_summary"]))

    def test_09_shadow_offer_count(self):
        report = s.run_shadow_ingestion(date="2026-08-27", season=2026, requester=self.requester)
        self.assertEqual(16, report["offer_side_count"])

    def test_10_shadow_line_count(self):
        report = s.run_shadow_ingestion(date="2026-08-27", season=2026, requester=self.requester)
        self.assertEqual(8, report["two_sided_player_line_count"])

    def test_11_shadow_event_identity(self):
        report = s.run_shadow_ingestion(date="2026-08-27", season=2026, requester=self.requester)
        self.assertEqual(1, report["verified_event_count"])
        self.assertTrue(report["downstream_contract"]["game_identity_present"])

    def test_12_step6c_schema_contract_passes(self):
        report = s.run_shadow_ingestion(date="2026-08-27", season=2026, requester=self.requester)
        self.assertTrue(report["downstream_contract"]["step6c_feed_schema_valid"])
        self.assertEqual("canonical_offers_v1", report["downstream_contract"]["feed_format"])

    def test_13_all_lines_are_two_sided(self):
        report = s.run_shadow_ingestion(date="2026-08-27", season=2026, requester=self.requester)
        self.assertTrue(report["downstream_contract"]["all_player_lines_two_sided"])
        self.assertEqual(0, report["incomplete_pair_count"])

    def test_14_ready_for_auto_sync_is_evidence_only(self):
        report = s.run_shadow_ingestion(date="2026-08-27", season=2026, requester=self.requester)
        self.assertTrue(report["ready_for_auto_sync"])
        self.assertFalse(report["safety"]["direct_sync_enablement_changed"])
        self.assertFalse(report["safety"]["production_runtime_enablement_changed"])

    def test_15_source_summary_has_four_gets(self):
        report = s.run_shadow_ingestion(date="2026-08-27", season=2026, requester=self.requester)
        self.assertEqual(4, len(report["source_summary"]))
        self.assertTrue(all(row["http_status"] == 200 for row in report["source_summary"]))

    def test_16_missing_under_blocks(self):
        feed = self.valid_feed()
        feed["offers"] = [row for row in feed["offers"] if row["source_offer_id"] != "sel-1-1-u"]
        report = s.validate_shadow_feed(feed)
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertIn("incomplete_over_under_pairs", report["blockers"])

    def test_17_missing_stat_blocks(self):
        feed = self.valid_feed()
        feed["offers"] = [row for row in feed["offers"] if row["stat"] != "pra"]
        report = s.validate_shadow_feed(feed)
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertIn("missing_stat_pra", report["blockers"])

    def test_18_missing_event_blocks(self):
        feed = self.valid_feed()
        feed["offers"][0]["source_event_id"] = None
        report = s.validate_shadow_feed(feed)
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertFalse(report["downstream_contract"]["game_identity_present"])

    def test_19_missing_player_blocks(self):
        feed = self.valid_feed()
        feed["offers"][0]["player_name"] = ""
        report = s.validate_shadow_feed(feed)
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertFalse(report["downstream_contract"]["player_identity_present"])

    def test_20_bad_side_blocks(self):
        feed = self.valid_feed()
        feed["offers"][0]["side"] = "higher"
        report = s.validate_shadow_feed(feed)
        self.assertFalse(report["ready_for_auto_sync"])

    def test_21_bad_line_blocks(self):
        feed = self.valid_feed()
        feed["offers"][0]["line"] = -1
        report = s.validate_shadow_feed(feed)
        self.assertFalse(report["ready_for_auto_sync"])

    def test_22_wrong_sportsbook_blocks(self):
        feed = self.valid_feed()
        feed["offers"][0]["sportsbook"] = "Other"
        report = s.validate_shadow_feed(feed)
        self.assertFalse(report["ready_for_auto_sync"])

    def test_23_duplicate_offer_id_blocks(self):
        feed = self.valid_feed()
        feed["offers"][1]["source_offer_id"] = feed["offers"][0]["source_offer_id"]
        report = s.validate_shadow_feed(feed)
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertEqual(1, report["duplicate_source_offer_id_count"])

    def test_24_cross_game_market_drift_blocks(self):
        feed = self.valid_feed()
        feed["offers"][1]["source_event_id"] = "evt-2"
        report = s.validate_shadow_feed(feed)
        self.assertFalse(report["ready_for_auto_sync"])
        self.assertEqual(1, report["cross_game_market_count"])

    def test_25_fingerprint_is_stable_shape(self):
        report = s.run_shadow_ingestion(date="2026-08-27", season=2026, requester=self.requester)
        self.assertEqual(64, len(report["validation_fingerprint_sha256"]))


if __name__ == "__main__":
    unittest.main()
