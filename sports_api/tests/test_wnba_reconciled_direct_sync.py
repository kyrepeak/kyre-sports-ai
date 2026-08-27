import copy
from datetime import datetime, timedelta, timezone
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import sports_api.wnba_reconciled_direct_sync as s


class Step6IReconciledDirectSyncTests(unittest.TestCase):
    def snapshot(self, *, captured_at=None):
        captured = captured_at or datetime.now(timezone.utc).isoformat()
        offers = []
        for stat_index, stat in enumerate(("points", "rebounds", "assists", "pra"), start=1):
            for player_index, player in enumerate(("A'ja Wilson", "Jackie Young"), start=1):
                market_id = f"mkt-{stat_index}-{player_index}"
                for side, odds in (("over", -110), ("under", -120)):
                    offers.append(
                        {
                            "sportsbook": "DraftKings",
                            "player_name": player,
                            "stat": stat,
                            "side": side,
                            "line": 10.5 + player_index,
                            "market_captured_at_utc": captured,
                            "source_event_id": "evt-1",
                            "source_market_id": market_id,
                            "source_offer_id": f"sel-{stat_index}-{player_index}-{side}",
                            "american_odds": odds,
                        }
                    )
        return {
            "schema_version": "wnba_step_6c_owned_market_feed_v1",
            "date": "2026-08-27",
            "season": 2026,
            "captured_at_utc": captured,
            "feed_source": "DraftKings Step 6I test",
            "feed_format": "canonical_offers_v1",
            "odds_format": "american",
            "offers": offers,
            "source_events": [
                {
                    "source_event_id": "evt-1",
                    "event_name": "LVA Aces @ PHX Mercury",
                    "event_date": "2026-08-28",
                    "participants": ["LVA Aces", "PHX Mercury"],
                    "participant_keys": ["lva aces", "phx mercury"],
                }
            ],
        }

    def green_report(self, snap=None):
        snap = snap or self.snapshot()
        markets = {row["source_market_id"] for row in snap["offers"]}
        players = sorted({row["player_name"] for row in snap["offers"]})
        return {
            "date": snap["date"],
            "season": snap["season"],
            "offer_side_count": len(snap["offers"]),
            "market_count": len(markets),
            "draftkings_event_count": len(snap["source_events"]),
            "verified_event_count": len(snap["source_events"]),
            "verified_market_count": len(markets),
            "verified_player_count": len(players),
            "verified_roster_membership_count": len(players),
            "step6g_shadow_ready": True,
            "ready_for_auto_sync": True,
            "blockers": [],
            "mismatch_details": [],
            "reconciliation_fingerprint_sha256": "a" * 64,
            "event_verifications": [
                {"source_event_id": "evt-1", "verified": True, "official_game_evidence_id": "team-schedule:test"}
            ],
            "player_verifications": [
                {"player_name": player, "verified": True} for player in players
            ],
        }

    @staticmethod
    def enabled_env():
        return {
            s._step6d.DIRECT_SYNC_ENABLED_ENV: "true",
            s._step6d.DIRECT_SYNC_PROVIDER_ENV: "draftkings",
            s.RECONCILED_SYNC_ENABLED_ENV: "true",
        }

    def build_with(self, snap, report, *, now=None, env=None):
        with patch.object(s, "fetch_verified_draftkings_snapshot", return_value=snap), \
             patch.object(s, "reconcile_team_page_snapshot", return_value=report), \
             patch.object(s, "_fetch_page", return_value={}):
            return s._build_reconciled_sync_bundle(
                date="2026-08-27",
                season=2026,
                env=env or {},
                now=now or datetime.now(timezone.utc),
            )

    def test_01_reconciled_guard_disabled_by_default(self):
        self.assertFalse(s.reconciled_sync_enabled({}))

    def test_02_both_switches_are_required_for_activation_request(self):
        env = self.enabled_env()
        self.assertTrue(s._activation_requested(env))
        env[s.RECONCILED_SYNC_ENABLED_ENV] = "false"
        self.assertFalse(s._activation_requested(env))

    def test_03_status_is_network_free_and_blocked_by_default(self):
        report = s.get_reconciled_sync_status({})
        self.assertFalse(report["reconciled_sync_active"])
        self.assertTrue(report["blockers"])
        self.assertFalse(report["safety"]["network_used_by_status"])
        self.assertFalse(report["safety"]["feed_write_performed"])

    def test_04_status_green_when_both_switches_are_requested(self):
        report = s.get_reconciled_sync_status(self.enabled_env())
        self.assertTrue(report["reconciled_sync_active"])
        self.assertEqual([], report["blockers"])

    def test_05_snapshot_hash_is_deterministic(self):
        snap = self.snapshot(captured_at="2026-08-27T00:00:00+00:00")
        self.assertEqual(s.snapshot_sha256(snap), s.snapshot_sha256(copy.deepcopy(snap)))
        self.assertEqual(64, len(s.snapshot_sha256(snap)))

    def test_06_snapshot_hash_changes_when_odds_change(self):
        snap = self.snapshot(captured_at="2026-08-27T00:00:00+00:00")
        changed = copy.deepcopy(snap)
        changed["offers"][0]["american_odds"] = -135
        self.assertNotEqual(s.snapshot_sha256(snap), s.snapshot_sha256(changed))

    def test_07_snapshot_hash_changes_when_line_changes(self):
        snap = self.snapshot(captured_at="2026-08-27T00:00:00+00:00")
        changed = copy.deepcopy(snap)
        changed["offers"][0]["line"] += 1.0
        self.assertNotEqual(s.snapshot_sha256(snap), s.snapshot_sha256(changed))

    def test_08_snapshot_hash_changes_when_event_metadata_changes(self):
        snap = self.snapshot(captured_at="2026-08-27T00:00:00+00:00")
        changed = copy.deepcopy(snap)
        changed["source_events"][0]["event_date"] = "2026-08-29"
        self.assertNotEqual(s.snapshot_sha256(snap), s.snapshot_sha256(changed))

    def test_09_green_exact_snapshot_builds_ready_attestation(self):
        now = datetime.now(timezone.utc)
        snap = self.snapshot(captured_at=(now - timedelta(seconds=5)).isoformat())
        attestation, returned = self.build_with(snap, self.green_report(snap), now=now)
        self.assertTrue(attestation["reconciliation_ready"])
        self.assertTrue(attestation["would_sync_if_enabled"])
        self.assertFalse(attestation["write_requested"])
        self.assertFalse(attestation["write_authorized"])
        self.assertEqual(s.snapshot_sha256(snap), attestation["snapshot_sha256"])
        self.assertIs(returned, snap)

    def test_10_stale_snapshot_fails_closed(self):
        now = datetime.now(timezone.utc)
        snap = self.snapshot(captured_at=(now - timedelta(seconds=121)).isoformat())
        attestation, _ = self.build_with(snap, self.green_report(snap), now=now)
        self.assertFalse(attestation["reconciliation_ready"])
        self.assertIn("snapshot_stale", attestation["blockers"])

    def test_11_future_snapshot_fails_closed(self):
        now = datetime.now(timezone.utc)
        snap = self.snapshot(captured_at=(now + timedelta(seconds=31)).isoformat())
        attestation, _ = self.build_with(snap, self.green_report(snap), now=now)
        self.assertFalse(attestation["reconciliation_ready"])
        self.assertIn("snapshot_capture_time_in_future", attestation["blockers"])

    def test_12_snapshot_date_mismatch_fails_closed(self):
        snap = self.snapshot()
        snap["date"] = "2026-08-28"
        report = self.green_report(snap)
        attestation, _ = self.build_with(snap, report)
        self.assertIn("snapshot_date_mismatch", attestation["blockers"])

    def test_13_snapshot_season_mismatch_fails_closed(self):
        snap = self.snapshot()
        snap["season"] = 2025
        report = self.green_report(snap)
        attestation, _ = self.build_with(snap, report)
        self.assertIn("snapshot_season_mismatch", attestation["blockers"])

    def test_14_step6h_blocker_fails_closed(self):
        snap = self.snapshot()
        report = self.green_report(snap)
        report["ready_for_auto_sync"] = False
        report["blockers"] = ["official_event_near_term_pair_unverified"]
        attestation, _ = self.build_with(snap, report)
        self.assertFalse(attestation["reconciliation_ready"])
        self.assertIn("step6h_not_ready", attestation["blockers"])
        self.assertIn("step6h_has_blockers", attestation["blockers"])

    def test_15_step6h_mismatch_fails_closed(self):
        snap = self.snapshot()
        report = self.green_report(snap)
        report["mismatch_details"] = [{"type": "player_team_mismatch"}]
        attestation, _ = self.build_with(snap, report)
        self.assertIn("step6h_has_mismatches", attestation["blockers"])

    def test_16_incomplete_event_verification_fails_closed(self):
        snap = self.snapshot()
        report = self.green_report(snap)
        report["verified_event_count"] = 0
        report["event_verifications"][0]["verified"] = False
        attestation, _ = self.build_with(snap, report)
        self.assertIn("not_all_events_verified", attestation["blockers"])
        self.assertIn("event_verification_contains_failure", attestation["blockers"])

    def test_17_incomplete_market_verification_fails_closed(self):
        snap = self.snapshot()
        report = self.green_report(snap)
        report["verified_market_count"] -= 1
        attestation, _ = self.build_with(snap, report)
        self.assertIn("not_all_markets_verified", attestation["blockers"])

    def test_18_failed_player_verification_fails_closed(self):
        snap = self.snapshot()
        report = self.green_report(snap)
        report["player_verifications"][0]["verified"] = False
        attestation, _ = self.build_with(snap, report)
        self.assertIn("player_verification_contains_failure", attestation["blockers"])

    def test_19_snapshot_mutation_during_reconciliation_fails_closed(self):
        now = datetime.now(timezone.utc)
        snap = self.snapshot(captured_at=(now - timedelta(seconds=1)).isoformat())
        report = self.green_report(snap)

        def mutate(snapshot, **kwargs):
            snapshot["offers"][0]["american_odds"] = -145
            return report

        with patch.object(s, "fetch_verified_draftkings_snapshot", return_value=snap), \
             patch.object(s, "reconcile_team_page_snapshot", side_effect=mutate), \
             patch.object(s, "_fetch_page", return_value={}):
            attestation, _ = s._build_reconciled_sync_bundle(
                date="2026-08-27", season=2026, env={}, now=now
            )
        self.assertFalse(attestation["reconciliation_ready"])
        self.assertIn("snapshot_mutated_during_reconciliation", attestation["blockers"])

    def test_20_disabled_guard_performs_no_fetch_and_no_write(self):
        with patch.object(s, "_build_reconciled_sync_bundle") as build, \
             patch.object(s, "_STEP6C_WRITE") as write:
            result = s.sync_reconciled_draftkings_to_kyre_feed(
                date="2026-08-27",
                season=2026,
                env={s._step6d.DIRECT_SYNC_ENABLED_ENV: "true"},
            )
        build.assert_not_called()
        write.assert_not_called()
        self.assertFalse(result["synced"])
        self.assertFalse(result["feed_write_performed"])

    def test_21_guard_enabled_without_step6d_flag_fails_before_fetch(self):
        with patch.object(s, "_build_reconciled_sync_bundle") as build:
            with self.assertRaises(s.WNBAReconciledSyncNotReadyError):
                s.sync_reconciled_draftkings_to_kyre_feed(
                    date="2026-08-27",
                    season=2026,
                    env={s.RECONCILED_SYNC_ENABLED_ENV: "true"},
                )
        build.assert_not_called()

    def test_22_per_call_url_override_is_rejected(self):
        with self.assertRaises(s.WNBAReconciledSyncNotReadyError):
            s.sync_reconciled_draftkings_to_kyre_feed(
                date="2026-08-27",
                season=2026,
                urls=["https://sportsbook-nash.draftkings.com/other"],
                env=self.enabled_env(),
            )

    def test_23_green_sync_writes_exact_snapshot_once(self):
        snap = self.snapshot()
        attestation = {
            "snapshot_sha256": s.snapshot_sha256(snap),
            "reconciliation_ready": True,
            "write_authorized": True,
            "safety": {"feed_write_performed": False},
        }
        with patch.object(s, "_build_reconciled_sync_bundle", return_value=(attestation, snap)), \
             patch.object(s, "_STEP6C_WRITE", return_value={"stored": True}) as write:
            result = s.sync_reconciled_draftkings_to_kyre_feed(
                date="2026-08-27", season=2026, env=self.enabled_env()
            )
        write.assert_called_once()
        written = write.call_args.args[0]
        self.assertEqual(s.snapshot_sha256(snap), s.snapshot_sha256(written))
        self.assertTrue(result["synced"])
        self.assertTrue(result["feed_write_performed"])

    def test_24_failed_reconciliation_never_calls_writer(self):
        snap = self.snapshot()
        attestation = {
            "snapshot_sha256": s.snapshot_sha256(snap),
            "reconciliation_ready": False,
            "write_authorized": False,
            "blockers": ["step6h_not_ready"],
            "safety": {"feed_write_performed": False},
        }
        with patch.object(s, "_build_reconciled_sync_bundle", return_value=(attestation, snap)), \
             patch.object(s, "_STEP6C_WRITE") as write:
            with self.assertRaises(s.WNBAReconciledSyncNotReadyError):
                s.sync_reconciled_draftkings_to_kyre_feed(
                    date="2026-08-27", season=2026, env=self.enabled_env()
                )
        write.assert_not_called()

    def test_25_atomic_writer_failure_does_not_report_synced(self):
        snap = self.snapshot()
        attestation = {
            "snapshot_sha256": s.snapshot_sha256(snap),
            "reconciliation_ready": True,
            "write_authorized": True,
            "safety": {"feed_write_performed": False},
        }
        with patch.object(s, "_build_reconciled_sync_bundle", return_value=(attestation, snap)), \
             patch.object(s, "_STEP6C_WRITE", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                s.sync_reconciled_draftkings_to_kyre_feed(
                    date="2026-08-27", season=2026, env=self.enabled_env()
                )

    def test_26_runtime_step6d_hook_is_interposed(self):
        self.assertIs(s._step6d.sync_draftkings_to_kyre_feed, s.sync_reconciled_draftkings_to_kyre_feed)
        self.assertTrue(s.INSTALLATION["installed"])
        self.assertFalse(s.INSTALLATION["frozen_step6d_source_modified"])

    def test_27_step6c_writer_reference_is_not_replaced_globally(self):
        from sports_api.collectors import wnba_kyre_market_feed as feed
        self.assertIs(s._STEP6C_WRITE, feed.write_kyre_market_feed)

    def test_28_max_age_is_bounded(self):
        with self.assertRaises(s.WNBAReconciledSyncNotReadyError):
            s._max_age_seconds({s.RECONCILED_SYNC_MAX_AGE_ENV: "601"})

    def test_29_status_route_is_get_only_and_no_public_sync_route_exists(self):
        from sports_api.main import app
        client = TestClient(app)
        response = client.get("/api/v1/wnba/markets/direct/draftkings/reconciled-sync-status")
        self.assertEqual(200, response.status_code)
        self.assertEqual("wnba_step6i_reconciled_direct_sync_status", response.json()["data_type"])
        self.assertEqual(405, client.post("/api/v1/wnba/markets/direct/draftkings/reconciled-sync-status").status_code)
        paths = {path for route in app.routes if (path := getattr(route, "path", None))}
        self.assertNotIn("/api/v1/wnba/markets/direct/draftkings/reconciled-sync", paths)
        self.assertNotIn("/api/v1/wnba/markets/direct/draftkings/sync", paths)


if __name__ == "__main__":
    unittest.main()
