import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import sports_api.wnba_step6d_direct_integration as i
from sports_api.main import app


class Step6DIntegrationTests(unittest.TestCase):
    def test_01_disabled_by_default(self):
        self.assertFalse(i.direct_sync_enabled({}))

    def test_02_enabled_with_draftkings_provider(self):
        env = {i.DIRECT_SYNC_ENABLED_ENV: "true", i.DIRECT_SYNC_PROVIDER_ENV: "draftkings"}
        self.assertTrue(i.direct_sync_enabled(env))

    def test_03_wrong_provider_stays_disabled(self):
        env = {i.DIRECT_SYNC_ENABLED_ENV: "true", i.DIRECT_SYNC_PROVIDER_ENV: "other"}
        self.assertFalse(i.direct_sync_enabled(env))

    def test_04_status_has_blockers_when_disabled(self):
        report = i.get_step6d_direct_market_status({})
        self.assertFalse(report["direct_sync_active"])
        self.assertTrue(report["blockers"])

    def test_05_status_green_with_urls_and_enablement(self):
        env = {
            i.DIRECT_SYNC_ENABLED_ENV: "true",
            i.DIRECT_SYNC_PROVIDER_ENV: "draftkings",
            "WNBA_DRAFTKINGS_MARKET_URLS_JSON": json.dumps([
                "https://sportsbook-nash.draftkings.com/sites/US-SB/api/test/wnba"
            ]),
        }
        report = i.get_step6d_direct_market_status(env)
        self.assertTrue(report["direct_sync_active"])
        self.assertEqual([], report["blockers"])

    def test_06_installation_is_active(self):
        self.assertTrue(i.INSTALLATION["installed"])

    def test_07_frozen_sources_report_unmodified(self):
        report = i.get_step6d_direct_market_status({})
        self.assertFalse(report["safety"]["frozen_step_5o_source_modified"])
        self.assertFalse(report["safety"]["frozen_step_5p_source_modified"])

    def test_08_disabled_wrapper_does_not_sync_network(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "feed.json"
            doc = {
                "schema_version": "wnba_step_6c_owned_market_feed_v1",
                "date": "2026-08-27",
                "season": 2026,
                "captured_at_utc": "2026-08-27T00:00:00+00:00",
                "feed_source": "test",
                "feed_format": "canonical_offers_v1",
                "odds_format": "american",
                "offers": [],
            }
            path.write_text(json.dumps(doc), encoding="utf-8")
            env = {"WNBA_KYRE_MARKET_FEED_PATH": str(path)}
            with patch.object(i, "sync_draftkings_to_kyre_feed") as sync:
                result = i.collect_kyre_market_feed_step6d(date="2026-08-27", season=2026, env=env)
            sync.assert_not_called()
            self.assertEqual("kyre", result["provider_id"])

    def test_09_enabled_wrapper_syncs_before_frozen_read(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "feed.json"
            env = {
                i.DIRECT_SYNC_ENABLED_ENV: "true",
                i.DIRECT_SYNC_PROVIDER_ENV: "draftkings",
                "WNBA_KYRE_MARKET_FEED_PATH": str(path),
                "WNBA_DRAFTKINGS_MARKET_URLS_JSON": json.dumps([
                    "https://sportsbook-nash.draftkings.com/sites/US-SB/api/test/wnba"
                ]),
            }

            def fake_sync(**kwargs):
                doc = {
                    "schema_version": "wnba_step_6c_owned_market_feed_v1",
                    "date": "2026-08-27",
                    "season": 2026,
                    "captured_at_utc": "2026-08-27T00:00:00+00:00",
                    "feed_source": "DraftKings direct test",
                    "feed_format": "canonical_offers_v1",
                    "odds_format": "american",
                    "offers": [],
                }
                path.write_text(json.dumps(doc), encoding="utf-8")
                return {"synced": True}

            with patch.object(i, "sync_draftkings_to_kyre_feed", side_effect=fake_sync) as sync:
                result = i.collect_kyre_market_feed_step6d(date="2026-08-27", season=2026, env=env)
            sync.assert_called_once()
            self.assertEqual("kyre", result["provider_id"])

    def test_10_status_route_registered(self):
        client = TestClient(app)
        response = client.get("/api/v1/wnba/markets/direct/draftkings/status")
        self.assertEqual(200, response.status_code)
        self.assertEqual("wnba_step6d_direct_market_status", response.json()["data_type"])

    def test_11_status_route_is_get_only(self):
        client = TestClient(app)
        response = client.post("/api/v1/wnba/markets/direct/draftkings/status")
        self.assertEqual(405, response.status_code)

    def test_12_no_public_direct_sync_route_exists(self):
        paths = {route.path for route in app.routes}
        self.assertNotIn("/api/v1/wnba/markets/direct/draftkings/sync", paths)


if __name__ == "__main__":
    unittest.main()
