from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import sports_api.api.wnba_kyre_market_feed as api
from sports_api.collectors.wnba_kyre_market_feed import (
    KYRE_MARKET_FEED_PATH_ENV,
    MARKET_PROVIDER_MODE_ENV,
    SCHEMA_VERSION,
)

NOW = "2026-08-26T23:30:00+00:00"


def payload():
    return {
        "schema_version": SCHEMA_VERSION,
        "date": "2026-08-26",
        "season": 2026,
        "captured_at_utc": NOW,
        "feed_source": "Kyre-owned market ingestion",
        "feed_format": "canonical_offers_v1",
        "odds_format": "american",
        "offers": [],
    }


class Step6CKyreMarketRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "market.json"
        self.env = {
            api.INGEST_TOKEN_ENV: "super-secret-ingest-token",
            KYRE_MARKET_FEED_PATH_ENV: str(self.path),
            MARKET_PROVIDER_MODE_ENV: "kyre",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_routes_are_get_status_and_post_feed_only(self):
        mapping = {route.path: sorted(route.methods) for route in api.router.routes}
        self.assertEqual(mapping["/api/v1/wnba/markets/owned/status"], ["GET"])
        self.assertEqual(mapping["/api/v1/wnba/markets/owned/feed"], ["POST"])
        self.assertEqual(len(mapping), 2)

    def test_02_missing_server_token_is_503(self):
        with self.assertRaises(HTTPException) as ctx:
            api.require_ingest_authorization("Bearer x", env={})
        self.assertEqual(ctx.exception.status_code, 503)

    def test_03_missing_auth_is_401(self):
        with self.assertRaises(HTTPException) as ctx:
            api.require_ingest_authorization(None, env=self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_04_bad_auth_is_401(self):
        with self.assertRaises(HTTPException) as ctx:
            api.require_ingest_authorization("Bearer wrong", env=self.env)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_05_good_auth_passes(self):
        api.require_ingest_authorization("Bearer super-secret-ingest-token", env=self.env)

    def test_06_post_stores_sanitized_feed_without_scheduler(self):
        with patch.dict(os.environ, self.env, clear=False):
            result = api.put_owned_market_feed(payload(), "Bearer super-secret-ingest-token")
        self.assertTrue(result["stored"])
        self.assertTrue(self.path.is_file())
        self.assertFalse(result["scheduler_triggered"])
        self.assertFalse(result["monte_carlo_run"])
        self.assertFalse(result["sportsbook_vendor_called"])

    def test_07_post_never_returns_token(self):
        with patch.dict(os.environ, self.env, clear=False):
            result = api.put_owned_market_feed(payload(), "Bearer super-secret-ingest-token")
        self.assertNotIn("super-secret-ingest-token", str(result))
        self.assertFalse(result["authorization_token_returned"])

    def test_08_invalid_payload_maps_422(self):
        broken = payload()
        broken["date"] = "bad"
        with patch.dict(os.environ, self.env, clear=False):
            with self.assertRaises(HTTPException) as ctx:
                api.put_owned_market_feed(broken, "Bearer super-secret-ingest-token")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_09_get_status_is_read_only_and_sanitized(self):
        with patch.dict(os.environ, self.env, clear=False):
            result = api.get_owned_market_feed_status()
        self.assertTrue(result["ingest_api"]["enabled"])
        self.assertFalse(result["ingest_api"]["token_returned"])
        self.assertNotIn("super-secret-ingest-token", str(result))

    def test_10_main_wires_owned_market_router(self):
        source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")
        self.assertIn("wnba_kyre_market_feed_router", source)
        self.assertIn("app.include_router(wnba_kyre_market_feed_router)", source)


if __name__ == "__main__":
    unittest.main()
