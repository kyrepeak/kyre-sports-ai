import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sports_api.collectors.wnba_kyre_market_feed import KYRE_MARKET_FEED_PATH_ENV, write_kyre_market_feed
import sports_api.wnba_step6j_canary_activation as s


class Step6JCanaryActivationTests(unittest.TestCase):
    def feed(self, *, source="test", captured="2026-08-27T02:00:00+00:00", odds=-110):
        return {
            "schema_version": "wnba_step_6c_owned_market_feed_v1",
            "date": "2026-08-27",
            "season": 2026,
            "captured_at_utc": captured,
            "feed_source": source,
            "feed_format": "canonical_offers_v1",
            "odds_format": "american",
            "offers": [{
                "sportsbook": "DraftKings",
                "player_name": "A'ja Wilson",
                "stat": "points",
                "side": "over",
                "line": 24.5,
                "american_odds": odds,
            }],
        }

    def env(self, path, activation_id="step6j-test-001"):
        return {
            KYRE_MARKET_FEED_PATH_ENV: str(path),
            s.CANARY_ENABLED_ENV: "true",
            s.ACTIVATION_ID_ENV: activation_id,
            s.DIRECT_SYNC_ENABLED_ENV: "true",
            s.DIRECT_SYNC_PROVIDER_ENV: "draftkings",
            s.RECONCILED_SYNC_ENABLED_ENV: "true",
            s.PRODUCTION_RUNTIME_ENV: "false",
        }

    def fake_sync(self, document):
        def _sync(*, date, season, env, path, **kwargs):
            storage = write_kyre_market_feed(copy.deepcopy(document), path=path, env=env)
            return {
                "synced": True,
                "feed_write_performed": True,
                "storage": storage,
                "persistent_feed_sha256": s.persistent_feed_sha256(document),
                "snapshot_sha256": "1" * 64,
                "reconciliation_fingerprint_sha256": "2" * 64,
                "attestation_sha256": "3" * 64,
                "offer_side_count": len(document["offers"]),
            }
        return _sync

    def test_01_status_is_network_free_and_disabled_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "feed.json"
            status = s.get_step6j_canary_status({KYRE_MARKET_FEED_PATH_ENV: str(path)})
        self.assertFalse(status["canary_enabled"])
        self.assertFalse(status["feed_exists"])
        self.assertFalse(status["safety"]["network_used_by_status"])
        self.assertFalse(status["safety"]["feed_write_performed_by_status"])

    def test_02_activation_id_must_match_before_sync(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "feed.json"
            with patch.object(s, "sync_reconciled_draftkings_to_kyre_feed") as sync:
                with self.assertRaises(s.WNBAStep6JCanaryError):
                    s.run_step6j_canary(date="2026-08-27", season=2026, activation_id="wrong-id-999", env=self.env(path))
            sync.assert_not_called()

    def test_03_production_runtime_must_remain_off(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "feed.json"
            env = self.env(path)
            env[s.PRODUCTION_RUNTIME_ENV] = "true"
            with patch.object(s, "sync_reconciled_draftkings_to_kyre_feed") as sync:
                with self.assertRaises(s.WNBAStep6JCanaryError):
                    s.run_step6j_canary(date="2026-08-27", season=2026, activation_id=env[s.ACTIVATION_ID_ENV], env=env)
            sync.assert_not_called()

    def test_04_green_canary_backs_up_writes_and_verifies_exact_feed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "feed.json"
            env = self.env(path)
            old = self.feed(source="old", odds=-105)
            write_kyre_market_feed(old, path=path, env=env)
            old_bytes = path.read_bytes()
            new = self.feed(source="new", odds=-118)
            with patch.object(s, "sync_reconciled_draftkings_to_kyre_feed", side_effect=self.fake_sync(new)) as sync:
                result = s.run_step6j_canary(date="2026-08-27", season=2026, activation_id=env[s.ACTIVATION_ID_ENV], env=env)
            self.assertEqual(1, sync.call_count)
            self.assertEqual("completed", result["status"])
            self.assertTrue(result["safety"]["feed_write_performed"])
            self.assertEqual(s.persistent_feed_sha256(new), result["verified_persistent_feed_sha256"])
            backup = path.parent / f"{s.BACKUP_PREFIX}{env[s.ACTIVATION_ID_ENV]}.bin"
            self.assertEqual(old_bytes, backup.read_bytes())
            status = s.get_step6j_canary_status(env)
            self.assertEqual("completed", status["canary_state"]["status"])
            self.assertEqual(status["feed_content_sha256"], status["canary_state"]["post_write_sha256"])

    def test_05_postwrite_identity_mismatch_restores_exact_old_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "feed.json"
            env = self.env(path)
            old = self.feed(source="old", odds=-101)
            write_kyre_market_feed(old, path=path, env=env)
            old_bytes = path.read_bytes()
            new = self.feed(source="new", odds=-130)

            def bad_sync(*, date, season, env, path, **kwargs):
                storage = write_kyre_market_feed(new, path=path, env=env)
                return {"synced": True, "feed_write_performed": True, "storage": storage, "persistent_feed_sha256": "f" * 64, "offer_side_count": 1}

            with patch.object(s, "sync_reconciled_draftkings_to_kyre_feed", side_effect=bad_sync):
                with self.assertRaises(s.WNBAStep6JCanaryError):
                    s.run_step6j_canary(date="2026-08-27", season=2026, activation_id=env[s.ACTIVATION_ID_ENV], env=env)
            self.assertEqual(old_bytes, path.read_bytes())
            status = s.get_step6j_canary_status(env)
            self.assertEqual("rolled_back", status["canary_state"]["status"])
            self.assertTrue(status["canary_state"]["rollback_verified"])

    def test_06_same_completed_activation_id_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "feed.json"
            env = self.env(path)
            new = self.feed(source="new")
            with patch.object(s, "sync_reconciled_draftkings_to_kyre_feed", side_effect=self.fake_sync(new)):
                first = s.run_step6j_canary(date="2026-08-27", season=2026, activation_id=env[s.ACTIVATION_ID_ENV], env=env)
            with patch.object(s, "sync_reconciled_draftkings_to_kyre_feed") as sync:
                second = s.run_step6j_canary(date="2026-08-27", season=2026, activation_id=env[s.ACTIVATION_ID_ENV], env=env)
            sync.assert_not_called()
            self.assertFalse(first["already_completed"])
            self.assertTrue(second["already_completed"])

    def test_07_manual_rollback_restores_precanary_feed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "feed.json"
            env = self.env(path)
            old = self.feed(source="old", odds=-102)
            write_kyre_market_feed(old, path=path, env=env)
            old_bytes = path.read_bytes()
            new = self.feed(source="new", odds=-125)
            with patch.object(s, "sync_reconciled_draftkings_to_kyre_feed", side_effect=self.fake_sync(new)):
                s.run_step6j_canary(date="2026-08-27", season=2026, activation_id=env[s.ACTIVATION_ID_ENV], env=env)
            result = s.rollback_step6j_canary(activation_id=env[s.ACTIVATION_ID_ENV], env=env)
            self.assertTrue(result["rollback_verified"])
            self.assertEqual(old_bytes, path.read_bytes())
            with self.assertRaises(s.WNBAStep6JCanaryError):
                s.run_step6j_canary(date="2026-08-27", season=2026, activation_id=env[s.ACTIVATION_ID_ENV], env=env)

    def test_08_api_requires_bearer_token_and_activation_header(self):
        import sports_api.api.wnba_step6j_canary as api
        app = FastAPI()
        app.include_router(api.router)
        client = TestClient(app)
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {"WNBA_KYRE_MARKET_INGEST_TOKEN": "secret-token", KYRE_MARKET_FEED_PATH_ENV: str(Path(td) / "feed.json")}, clear=False):
            response = client.post("/api/v1/wnba/markets/direct/draftkings/step6j-canary?date=2026-08-27&season=2026")
            self.assertEqual(401, response.status_code)
            with patch.object(api, "run_step6j_canary", return_value={"status": "completed"}) as run:
                response = client.post(
                    "/api/v1/wnba/markets/direct/draftkings/step6j-canary?date=2026-08-27&season=2026",
                    headers={"Authorization": "Bearer secret-token", "X-WNBA-Step6J-Activation-ID": "step6j-test-001"},
                )
            self.assertEqual(200, response.status_code)
            self.assertEqual("completed", response.json()["status"])
            run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
