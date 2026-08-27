from __future__ import annotations

import copy
import os
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from sports_api.wnba_step6q_durable_storage import FILESYSTEM_BACKEND, SUPABASE_BACKEND
import sports_api.wnba_step6u_activation_bridge as u


class Step6UActivationBridgeTests(unittest.TestCase):
    def step6t_status(self, backend=SUPABASE_BACKEND):
        return {
            "selected_backend": backend,
            "configuration_ready": True,
            "configuration_error": None,
            "verification_requires_network": backend == SUPABASE_BACKEND,
            "verification_is_read_only": True,
        }

    def step5w(self, checkpoint="a" * 64):
        return {
            "phase": "pre_activation_checkpoint_ready",
            "activation_requested": False,
            "checkpoint_ready": True,
            "live_cycle_allowed": False,
            "activation_checkpoint_sha256": checkpoint,
        }

    def evidence(self, backend=SUPABASE_BACKEND, evidence_sha="b" * 64):
        return {
            "evidence_verified": True,
            "scheduler_authorized": False,
            "evidence_sha256": evidence_sha,
            "canary_identity": {
                "storage_backend": backend,
                "activation_id": "step6u-test-001",
                "status": "completed",
                "date": "2026-08-27",
                "season": 2026,
                "completed_at_utc": "2026-08-27T05:00:00+00:00",
                "preexisting_feed": True,
                "pre_write_sha256": "1" * 64,
                "post_write_sha256": "2" * 64,
                "verified_persistent_feed_sha256": "3" * 64,
                "offer_side_count": 12,
                "rollback_verified": True,
                "rollback_mode": "restore_exact_backup_bytes",
                "backup_content_sha256": "1" * 64,
            },
        }

    def step6k(self, checkpoint="a" * 64, *, step6j_verified=True, preactivation_ready=True):
        return {
            "step6j_verified": step6j_verified,
            "preactivation_ready": preactivation_ready,
            "scheduler_authorized": False,
            "activation_checkpoint_sha256": "4" * 64,
            "step_5w": {"activation_checkpoint_sha256": checkpoint},
        }

    def build_supabase(self, evidence=None, step5w=None):
        evidence = evidence or self.evidence()
        step5w = step5w or self.step5w()
        with patch.object(u, "get_step6t_canary_evidence_status", return_value=self.step6t_status()), patch.object(
            u, "get_staging_activation_gate", return_value=step5w
        ), patch.object(
            u,
            "get_step6k_activation_preflight",
            side_effect=AssertionError("Supabase bridge must not use legacy Step 6K as remote verifier"),
        ):
            return u.build_step6u_activation_bridge(env={}, evidence=evidence)

    def test_01_status_is_network_free_and_never_claims_bridge_ready(self):
        with patch.object(u, "get_step6t_canary_evidence_status", return_value=self.step6t_status()), patch.object(
            u, "get_staging_activation_gate", return_value=self.step5w()
        ), patch.object(
            u,
            "verify_step6t_canary_evidence",
            side_effect=AssertionError("status must not verify storage evidence"),
        ):
            result = u.get_step6u_activation_bridge_status({})
        self.assertTrue(result["configuration_ready"])
        self.assertFalse(result["bridge_ready"])
        self.assertIsNone(result["bridge_checkpoint_sha256"])
        self.assertFalse(result["scheduler_authorized"])
        self.assertFalse(result["safety"]["network_used_by_status"])
        self.assertFalse(result["safety"]["storage_read_performed_by_status"])

    def test_02_status_blocks_when_step5w_checkpoint_is_not_ready(self):
        step5w = self.step5w()
        step5w["checkpoint_ready"] = False
        with patch.object(u, "get_step6t_canary_evidence_status", return_value=self.step6t_status()), patch.object(
            u, "get_staging_activation_gate", return_value=step5w
        ):
            result = u.get_step6u_activation_bridge_status({})
        self.assertFalse(result["configuration_ready"])
        self.assertTrue(any("Step 5W" in reason for reason in result["blocking_reasons"]))

    def test_03_supabase_bridge_binds_verified_evidence_without_scheduler_authority(self):
        result = self.build_supabase()
        self.assertTrue(result["bridge_ready"])
        self.assertFalse(result["scheduler_authorized"])
        self.assertEqual(SUPABASE_BACKEND, result["selected_backend"])
        self.assertEqual("b" * 64, result["step_6t_evidence_sha256"])
        self.assertEqual(64, len(result["bridge_checkpoint_sha256"]))
        self.assertIsNone(result["filesystem_step_6k"])
        self.assertFalse(result["safety"]["storage_write_performed"])
        self.assertFalse(result["safety"]["scheduler_authorized_by_step6u"])

    def test_04_bridge_checkpoint_is_deterministic(self):
        first = self.build_supabase()
        second = self.build_supabase()
        self.assertEqual(first["bridge_checkpoint_sha256"], second["bridge_checkpoint_sha256"])

    def test_05_bridge_checkpoint_changes_when_evidence_hash_changes(self):
        first = self.build_supabase()
        changed = self.evidence(evidence_sha="c" * 64)
        second = self.build_supabase(evidence=changed)
        self.assertNotEqual(first["bridge_checkpoint_sha256"], second["bridge_checkpoint_sha256"])

    def test_06_bridge_checkpoint_changes_when_step5w_checkpoint_changes(self):
        first = self.build_supabase()
        second = self.build_supabase(step5w=self.step5w(checkpoint="d" * 64))
        self.assertNotEqual(first["bridge_checkpoint_sha256"], second["bridge_checkpoint_sha256"])

    def test_07_invalid_step6t_evidence_hash_fails_closed(self):
        bad = self.evidence()
        bad["evidence_sha256"] = "not-a-sha"
        with self.assertRaises(u.WNBAStep6UActivationBridgeNotReadyError):
            self.build_supabase(evidence=bad)

    def test_08_evidence_that_claims_scheduler_authority_is_rejected(self):
        bad = self.evidence()
        bad["scheduler_authorized"] = True
        with self.assertRaises(u.WNBAStep6UActivationBridgeNotReadyError):
            self.build_supabase(evidence=bad)

    def test_09_backend_mismatch_fails_closed(self):
        bad = self.evidence(backend=FILESYSTEM_BACKEND)
        with self.assertRaises(u.WNBAStep6UActivationBridgeNotReadyError):
            self.build_supabase(evidence=bad)

    def test_10_unverified_rollback_fails_closed(self):
        bad = self.evidence()
        bad["canary_identity"]["rollback_verified"] = False
        with self.assertRaises(u.WNBAStep6UActivationBridgeNotReadyError):
            self.build_supabase(evidence=bad)

    def test_11_filesystem_bridge_requires_frozen_step6k_green(self):
        with patch.object(
            u, "get_step6t_canary_evidence_status", return_value=self.step6t_status(FILESYSTEM_BACKEND)
        ), patch.object(u, "get_staging_activation_gate", return_value=self.step5w()), patch.object(
            u, "get_step6k_activation_preflight", return_value=self.step6k()
        ):
            result = u.build_step6u_activation_bridge(env={}, evidence=self.evidence(FILESYSTEM_BACKEND))
        self.assertTrue(result["bridge_ready"])
        self.assertTrue(result["filesystem_step_6k"]["step6j_verified"])
        self.assertTrue(result["filesystem_step_6k"]["preactivation_ready"])
        self.assertFalse(result["filesystem_step_6k"]["scheduler_authorized"])

    def test_12_filesystem_bridge_fails_if_frozen_step6k_step6j_is_not_verified(self):
        with patch.object(
            u, "get_step6t_canary_evidence_status", return_value=self.step6t_status(FILESYSTEM_BACKEND)
        ), patch.object(u, "get_staging_activation_gate", return_value=self.step5w()), patch.object(
            u,
            "get_step6k_activation_preflight",
            return_value=self.step6k(step6j_verified=False, preactivation_ready=False),
        ):
            with self.assertRaises(u.WNBAStep6UActivationBridgeNotReadyError):
                u.build_step6u_activation_bridge(env={}, evidence=self.evidence(FILESYSTEM_BACKEND))

    def test_13_filesystem_bridge_fails_if_step6k_and_step5w_checkpoint_differ(self):
        with patch.object(
            u, "get_step6t_canary_evidence_status", return_value=self.step6t_status(FILESYSTEM_BACKEND)
        ), patch.object(u, "get_staging_activation_gate", return_value=self.step5w()), patch.object(
            u, "get_step6k_activation_preflight", return_value=self.step6k(checkpoint="e" * 64)
        ):
            with self.assertRaises(u.WNBAStep6UActivationBridgeNotReadyError):
                u.build_step6u_activation_bridge(env={}, evidence=self.evidence(FILESYSTEM_BACKEND))

    def test_14_omitted_evidence_invokes_step6t_read_only_verifier_once(self):
        evidence = self.evidence()
        with patch.object(u, "get_step6t_canary_evidence_status", return_value=self.step6t_status()), patch.object(
            u, "verify_step6t_canary_evidence", return_value=evidence
        ) as verify, patch.object(u, "get_staging_activation_gate", return_value=self.step5w()), patch.object(
            u,
            "get_step6k_activation_preflight",
            side_effect=AssertionError("Supabase bridge must not call legacy Step 6K"),
        ):
            result = u.require_step6u_bridge_ready(env={})
        verify.assert_called_once()
        self.assertTrue(result["bridge_ready"])
        self.assertFalse(result["scheduler_authorized"])

    def test_15_api_status_and_authenticated_verify_are_separate(self):
        import sports_api.api.wnba_step6u_activation_bridge as api

        app = FastAPI()
        app.include_router(api.router)
        client = TestClient(app)
        safe_status = {
            "configuration_ready": True,
            "bridge_ready": False,
            "scheduler_authorized": False,
            "safety": {"network_used_by_status": False},
        }
        verified = {
            "bridge_ready": True,
            "bridge_checkpoint_sha256": "f" * 64,
            "scheduler_authorized": False,
        }
        with patch.dict(os.environ, {"WNBA_KYRE_MARKET_INGEST_TOKEN": "step6u-secret"}, clear=False), patch.object(
            api, "get_step6u_activation_bridge_status", return_value=safe_status
        ), patch.object(api, "require_step6u_bridge_ready", return_value=verified) as verify:
            status = client.get("/api/v1/wnba/runtime/step6u-activation-bridge/status")
            unauthorized = client.post("/api/v1/wnba/runtime/step6u-activation-bridge/verify")
            authorized = client.post(
                "/api/v1/wnba/runtime/step6u-activation-bridge/verify",
                headers={"Authorization": "Bearer step6u-secret"},
            )
        self.assertEqual(200, status.status_code)
        self.assertFalse(status.json()["bridge_ready"])
        self.assertEqual(401, unauthorized.status_code)
        self.assertEqual(200, authorized.status_code)
        self.assertFalse(authorized.json()["scheduler_authorized"])
        verify.assert_called_once()


if __name__ == "__main__":
    unittest.main()
