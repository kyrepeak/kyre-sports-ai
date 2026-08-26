from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import sports_api.wnba_prop_feed_failover as failover
from sports_api.collectors.wnba_kyre_market_feed import (
    DEFAULT_KYRE_MARKET_FEED_PATH,
    KYRE_MARKET_FEED_PATH_ENV,
    MARKET_PROVIDER_MODE_ENV,
    SCHEMA_VERSION,
    WNBAKyreMarketFeedModelInputError,
    WNBAKyreMarketFeedNotReadyError,
    collect_kyre_market_feed,
    describe_kyre_market_onboarding,
    kyre_market_ready,
    market_provider_mode,
    resolve_kyre_market_feed_path,
    validate_kyre_market_feed,
    write_kyre_market_feed,
)
from sports_api.collectors.wnba_sportsgameodds import SPORTSGAMEODDS_API_KEY_ENV
from sports_api.database.wnba_prop_feed_store import STORE_PATH_ENV

NOW = "2026-08-26T23:30:00+00:00"


def feed(**changes):
    value = {
        "schema_version": SCHEMA_VERSION,
        "date": "2026-08-26",
        "season": 2026,
        "captured_at_utc": NOW,
        "feed_source": "Kyre-owned market ingestion",
        "feed_format": "canonical_offers_v1",
        "odds_format": "american",
        "offers": [
            {
                "sportsbook": "DraftKings",
                "player_name": "A'ja Wilson",
                "stat": "points",
                "side": "over",
                "line": 22.5,
                "american_odds": -110,
                "market_captured_at_utc": NOW,
            }
        ],
    }
    value.update(changes)
    return value


class Step6CKyreMarketFeedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "wnba_market_feed.json"
        self.store = Path(self.tmp.name) / "feed.sqlite3"
        self.env = {
            MARKET_PROVIDER_MODE_ENV: "kyre",
            KYRE_MARKET_FEED_PATH_ENV: str(self.path),
            STORE_PATH_ENV: str(self.store),
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_default_path_is_persistent_disk(self):
        self.assertEqual(DEFAULT_KYRE_MARKET_FEED_PATH, "/var/lib/kyre-sports-api/wnba_market_feed.json")

    def test_02_mode_unset_preserves_legacy_none(self):
        self.assertIsNone(market_provider_mode({}))

    def test_03_mode_kyre(self):
        self.assertEqual(market_provider_mode({MARKET_PROVIDER_MODE_ENV: "KYRE"}), "kyre")

    def test_04_mode_auto(self):
        self.assertEqual(market_provider_mode({MARKET_PROVIDER_MODE_ENV: "auto"}), "auto")

    def test_05_invalid_mode_rejected(self):
        with self.assertRaises(WNBAKyreMarketFeedModelInputError):
            market_provider_mode({MARKET_PROVIDER_MODE_ENV: "vendor-x"})

    def test_06_relative_path_rejected(self):
        with self.assertRaises(WNBAKyreMarketFeedModelInputError):
            resolve_kyre_market_feed_path("relative.json")

    def test_07_valid_feed_normalized(self):
        result = validate_kyre_market_feed(feed())
        self.assertEqual(result["date"], "2026-08-26")
        self.assertEqual(len(result["offers"]), 1)

    def test_08_non_object_rejected(self):
        with self.assertRaises(WNBAKyreMarketFeedModelInputError):
            validate_kyre_market_feed([])

    def test_09_bad_schema_rejected(self):
        with self.assertRaises(WNBAKyreMarketFeedModelInputError):
            validate_kyre_market_feed(feed(schema_version="bad"))

    def test_10_bad_date_rejected(self):
        with self.assertRaises(WNBAKyreMarketFeedModelInputError):
            validate_kyre_market_feed(feed(date="08/26/2026"))

    def test_11_bad_season_rejected(self):
        with self.assertRaises(WNBAKyreMarketFeedModelInputError):
            validate_kyre_market_feed(feed(season="bad"))

    def test_12_naive_timestamp_rejected(self):
        with self.assertRaises(WNBAKyreMarketFeedModelInputError):
            validate_kyre_market_feed(feed(captured_at_utc="2026-08-26T23:30:00"))

    def test_13_bad_feed_format_rejected(self):
        with self.assertRaises(WNBAKyreMarketFeedModelInputError):
            validate_kyre_market_feed(feed(feed_format="vendor-specific"))

    def test_14_bad_odds_format_rejected(self):
        with self.assertRaises(WNBAKyreMarketFeedModelInputError):
            validate_kyre_market_feed(feed(odds_format="fractional"))

    def test_15_offers_must_be_list(self):
        with self.assertRaises(WNBAKyreMarketFeedModelInputError):
            validate_kyre_market_feed(feed(offers={}))

    def test_16_offer_rows_must_be_objects(self):
        with self.assertRaises(WNBAKyreMarketFeedModelInputError):
            validate_kyre_market_feed(feed(offers=["bad"]))

    def test_17_missing_file_not_ready(self):
        with self.assertRaises(WNBAKyreMarketFeedNotReadyError):
            collect_kyre_market_feed(date="2026-08-26", season=2026, env=self.env)

    def test_18_write_creates_feed(self):
        result = write_kyre_market_feed(feed(), env=self.env)
        self.assertTrue(result["stored"])
        self.assertTrue(self.path.is_file())

    def test_19_write_response_sanitized(self):
        result = write_kyre_market_feed(feed(), env=self.env)
        encoded = json.dumps(result)
        self.assertNotIn("offers", encoded)
        self.assertTrue(result["secret_values_returned"] is False)

    def test_20_write_then_collect_is_network_free(self):
        write_kyre_market_feed(feed(), env=self.env)
        result = collect_kyre_market_feed(date="2026-08-26", season=2026, env=self.env)
        self.assertFalse(result["transport"]["network_used"])
        self.assertEqual(result["provider_id"], "kyre")

    def test_21_collect_returns_canonical_raw_feed(self):
        write_kyre_market_feed(feed(), env=self.env)
        result = collect_kyre_market_feed(date="2026-08-26", season=2026, env=self.env)
        self.assertEqual(result["feed_format"], "canonical_offers_v1")
        self.assertEqual(result["raw_feed"]["offers"][0]["sportsbook"], "DraftKings")

    def test_22_collect_date_mismatch_not_ready(self):
        write_kyre_market_feed(feed(), env=self.env)
        with self.assertRaises(WNBAKyreMarketFeedNotReadyError):
            collect_kyre_market_feed(date="2026-08-27", season=2026, env=self.env)

    def test_23_collect_season_mismatch_not_ready(self):
        write_kyre_market_feed(feed(), env=self.env)
        with self.assertRaises(WNBAKyreMarketFeedNotReadyError):
            collect_kyre_market_feed(date="2026-08-26", season=2025, env=self.env)

    def test_24_status_not_ready_before_import(self):
        result = describe_kyre_market_onboarding(self.env)
        self.assertFalse(result["ready"])
        self.assertFalse(result["secret_required"])

    def test_25_status_ready_after_import(self):
        write_kyre_market_feed(feed(), env=self.env)
        result = describe_kyre_market_onboarding(self.env)
        self.assertTrue(result["ready"])
        self.assertEqual(result["offer_count"], 1)

    def test_26_ready_helper(self):
        write_kyre_market_feed(feed(), env=self.env)
        self.assertTrue(kyre_market_ready(self.env))

    def test_27_step5o_kyre_mode_resolves_kyre_only(self):
        write_kyre_market_feed(feed(), env=self.env)
        self.assertEqual(failover.resolve_failover_order(env=self.env), ["kyre"])

    def test_28_step5o_kyre_mode_fails_closed_without_feed(self):
        with self.assertRaises(failover.WNBAPropFeedFailoverNotReadyError):
            failover.resolve_failover_order(env=self.env)

    def test_29_sgo_key_does_not_bypass_kyre_mode(self):
        env = dict(self.env)
        env[SPORTSGAMEODDS_API_KEY_ENV] = "legacy-key"
        with self.assertRaises(failover.WNBAPropFeedFailoverNotReadyError):
            failover.resolve_failover_order(env=env)

    def test_30_auto_mode_prefers_kyre_when_ready(self):
        write_kyre_market_feed(feed(), env=self.env)
        env = dict(self.env)
        env[MARKET_PROVIDER_MODE_ENV] = "auto"
        env[SPORTSGAMEODDS_API_KEY_ENV] = "legacy-key"
        order = failover.resolve_failover_order(env=env)
        self.assertEqual(order[0], "kyre")
        self.assertIn("sportsgameodds", order)

    def test_31_legacy_mode_can_use_sgo(self):
        env = {MARKET_PROVIDER_MODE_ENV: "legacy_sportsgameodds", SPORTSGAMEODDS_API_KEY_ENV: "x"}
        self.assertEqual(failover.resolve_failover_order(env=env)[0], "sportsgameodds")

    def test_32_onboarding_reports_owned_provider(self):
        write_kyre_market_feed(feed(), env=self.env)
        result = failover.describe_provider_onboarding(self.env)
        self.assertTrue(result["kyre_owned_provider"]["ready"])
        self.assertEqual(result["resolved_failover_order"], ["kyre"])

    def test_33_failover_can_select_kyre_with_injected_line_builder(self):
        write_kyre_market_feed(feed(), env=self.env)
        board = {
            "line_board_fingerprint_sha256": "c" * 64,
            "normalized_line_count": 1,
            "official_slate_reference": {"playable_game_ids": ["g1"]},
            "step_5l_prop_lines": [{"player_id": 1, "stat": "points", "line": 22.5}],
        }
        result = failover.collect_failover_line_board(
            env=self.env,
            store_path=self.store,
            line_board_builder=lambda *args, **kwargs: board,
        )
        self.assertEqual(result["selected_provider_id"], "kyre")
        self.assertEqual(result["selected_failover_rank"], 1)

    def test_34_no_external_secret_needed(self):
        write_kyre_market_feed(feed(), env=self.env)
        result = collect_kyre_market_feed(date="2026-08-26", season=2026, env=self.env)
        self.assertTrue(result["collector_semantics"]["sportsbook_vendor_key_required"] is False)

    def test_35_atomic_replacement_uses_latest_feed(self):
        write_kyre_market_feed(feed(), env=self.env)
        write_kyre_market_feed(feed(offers=[]), env=self.env)
        result = collect_kyre_market_feed(date="2026-08-26", season=2026, env=self.env)
        self.assertEqual(result["raw_feed"]["offers"], [])


if __name__ == "__main__":
    unittest.main()
