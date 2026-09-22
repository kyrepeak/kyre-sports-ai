from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import sports_api.wnba_step6w_final_certification as s
from sports_api.api.wnba_step6w_final_certification import router


def _phase6(**_):
    return {
        "phase6_engineering_certified": True,
        "production_live": False,
        "master_freeze": {"master_manifest_sha256": "a" * 64},
        "semantics": {"network_used": False},
    }


def _real_evidence_loader():
    return s._load_step6v_evidence()


class Step6WFinalCertificationTests(unittest.TestCase):
    def test_upgrade_inventory_is_exactly_6q_through_6w(self):
        self.assertEqual([row["step"] for row in s.FINAL_UPGRADE_STEPS], ["6Q", "6R", "6S", "6T", "6U", "6V", "6W"])
        self.assertEqual(s.FINAL_UPGRADE_STEPS[-1]["state"], "certifier")

    def test_packaged_evidence_is_exact_successful_step6v_proof(self):
        evidence, digest = s._load_step6v_evidence()
        self.assertEqual(digest, s.STEP6V_EVIDENCE_FILE_SHA256)
        self.assertEqual(evidence["activation_id"], s.STEP6V_ACTIVATION_ID)
        self.assertEqual(evidence["status"], "completed")
        self.assertTrue(evidence["step6j_complete_candidate"])
        self.assertEqual(evidence["storage_backend"], "supabase")
        self.assertTrue(evidence["evidence"]["evidence_verified"])
        self.assertTrue(evidence["evidence"]["rollback_verified"])
        self.assertEqual(evidence["canary"]["offer_side_count"], 230)

    def test_final_certification_freezes_architecture_without_activation(self):
        report = s.build_step6w_final_certification(phase6_getter=_phase6, evidence_loader=_real_evidence_loader)
        self.assertTrue(report["final_architecture_certified"])
        self.assertEqual(report["state"], "wnba_upgraded_architecture_frozen")
        self.assertTrue(report["step6j_live_canary_complete"])
        self.assertFalse(report["production_live"])
        self.assertFalse(report["scheduler_authorized"])
        self.assertFalse(report["scheduler_started"])
        self.assertEqual(report["supabase"]["active_locks_after_canary"], 0)
        self.assertTrue(all(report["checks"].values()))

    def test_missing_evidence_blocks_final_freeze(self):
        def missing():
            raise FileNotFoundError("evidence missing")

        report = s.build_step6w_final_certification(phase6_getter=_phase6, evidence_loader=missing)
        self.assertFalse(report["final_architecture_certified"])
        self.assertEqual(report["state"], "wnba_final_certification_blocked")
        self.assertIn("step6v_evidence_loaded", report["blocking_reasons"])
        self.assertIsNotNone(report["evidence_error"])

    def test_evidence_hash_drift_blocks_final_freeze(self):
        evidence, _ = s._load_step6v_evidence()
        report = s.build_step6w_final_certification(
            phase6_getter=_phase6,
            evidence_loader=lambda: (evidence, "0" * 64),
        )
        self.assertFalse(report["final_architecture_certified"])
        self.assertIn("step6v_evidence_file_sha256_matches", report["blocking_reasons"])

    def test_scheduler_authorization_regression_blocks_final_freeze(self):
        evidence, digest = s._load_step6v_evidence()
        mutated = deepcopy(evidence)
        mutated["safety"]["scheduler_authorized"] = True
        report = s.build_step6w_final_certification(
            phase6_getter=_phase6,
            evidence_loader=lambda: (mutated, digest),
        )
        self.assertFalse(report["final_architecture_certified"])
        self.assertIn("step6v_scheduler_not_authorized", report["blocking_reasons"])

    def test_switch_regression_blocks_final_freeze(self):
        evidence, digest = s._load_step6v_evidence()
        mutated = deepcopy(evidence)
        mutated["final_switch_state"]["WNBA_KYRE_DIRECT_SYNC_ENABLED"] = True
        report = s.build_step6w_final_certification(
            phase6_getter=_phase6,
            evidence_loader=lambda: (mutated, digest),
        )
        self.assertFalse(report["final_architecture_certified"])
        self.assertIn("step6v_all_runtime_write_switches_finished_off", report["blocking_reasons"])

    def test_phase6_regression_blocks_final_freeze(self):
        blocked_phase6 = lambda **_: {
            "phase6_engineering_certified": False,
            "production_live": False,
            "master_freeze": {"master_manifest_sha256": "a" * 64},
            "semantics": {"network_used": False},
        }
        report = s.build_step6w_final_certification(phase6_getter=blocked_phase6, evidence_loader=_real_evidence_loader)
        self.assertFalse(report["final_architecture_certified"])
        self.assertIn("phase6_engineering_contract_certified", report["blocking_reasons"])

    def test_final_manifest_hash_is_deterministic(self):
        a = s.build_step6w_final_certification(env={"X": "1"}, phase6_getter=_phase6, evidence_loader=_real_evidence_loader)
        b = s.build_step6w_final_certification(env={"X": "2"}, phase6_getter=_phase6, evidence_loader=_real_evidence_loader)
        self.assertEqual(a["final_freeze"]["final_manifest_sha256"], b["final_freeze"]["final_manifest_sha256"])
        self.assertEqual(a["final_freeze"]["canonical_json_sha256"], a["final_freeze"]["final_manifest_sha256"])

    def test_require_certified_is_fail_closed(self):
        with patch.object(
            s,
            "build_step6w_final_certification",
            return_value={"final_architecture_certified": False, "blocking_reasons": ["proof missing"]},
        ):
            with self.assertRaises(s.WNBAStep6WNotCertifiedError):
                s.require_step6w_final_certified()

    def test_api_is_get_only(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        with patch(
            "sports_api.api.wnba_step6w_final_certification.build_step6w_final_certification",
            return_value={"state": "wnba_upgraded_architecture_frozen", "final_architecture_certified": True},
        ):
            response = client.get("/api/v1/wnba/runtime/step6w-final-certification")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["final_architecture_certified"])
        self.assertEqual(client.post("/api/v1/wnba/runtime/step6w-final-certification").status_code, 405)
        self.assertEqual(client.put("/api/v1/wnba/runtime/step6w-final-certification").status_code, 405)
        self.assertEqual(client.delete("/api/v1/wnba/runtime/step6w-final-certification").status_code, 405)


if __name__ == "__main__":
    unittest.main()
