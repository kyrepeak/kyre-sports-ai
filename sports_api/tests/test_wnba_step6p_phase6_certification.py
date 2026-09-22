from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import sports_api.wnba_step6p_phase6_certification as s
from sports_api.api.wnba_step6p_phase6_certification import router


def _step6o(
    *,
    state: str = "safe_deferred",
    package_ready: bool = True,
    live_activation_ready: bool = False,
    separate_boundary: bool = True,
    rollback_ordered: bool = True,
    preserve_storage: bool = True,
) -> dict:
    return {
        "state": state,
        "package_ready": package_ready,
        "live_activation_ready": live_activation_ready,
        "activation_blocking_reasons": [] if live_activation_ready else ["durable host canary remains deferred"],
        "manifest": {"manifest_sha256": "a" * 64},
        "semantics": {
            "live_activation_requires_separate_operator_boundary": separate_boundary,
            "rollback_disables_runtime_before_refresh_or_image_recovery": rollback_ordered,
            "rollback_preserves_persistent_storage": preserve_storage,
        },
    }


class Step6PPhase6CertificationTests(unittest.TestCase):
    def test_inventory_is_exactly_6a_through_6o(self):
        expected = [f"6{chr(code)}" for code in range(ord("A"), ord("P"))]
        self.assertEqual(s._step_ids(), expected)
        self.assertTrue(s._phase6_inventory_valid())
        self.assertEqual(len(s.PHASE6_STEPS), 15)

    def test_6a_6b_are_retired_and_6c_is_successor(self):
        rows = {row["step"]: row for row in s.PHASE6_STEPS}
        self.assertEqual(rows["6A"]["state"], "retired_legacy")
        self.assertEqual(rows["6B"]["state"], "retired_legacy")
        self.assertEqual(rows["6A"]["successor"], "6C")
        self.assertEqual(rows["6B"]["successor"], "6C")
        self.assertEqual(rows["6C"]["state"], "active_frozen_contract")

    def test_safe_deferred_is_valid_phase6_completion(self):
        report = s.build_step6p_phase6_certification(step6o_getter=lambda **_: _step6o())
        self.assertTrue(report["phase6_engineering_certified"])
        self.assertEqual(report["state"], "phase6_complete_safe_deferred")
        self.assertTrue(report["safe_deferred"])
        self.assertTrue(report["live_activation_deferred"])
        self.assertFalse(report["live_activation_ready"])
        self.assertFalse(report["production_live"])

    def test_activation_ready_still_does_not_claim_production_live(self):
        report = s.build_step6p_phase6_certification(
            step6o_getter=lambda **_: _step6o(state="activation_ready", live_activation_ready=True)
        )
        self.assertTrue(report["phase6_engineering_certified"])
        self.assertTrue(report["live_activation_ready"])
        self.assertEqual(report["state"], "phase6_complete_activation_ready")
        self.assertFalse(report["production_live"])

    def test_step6o_package_failure_blocks_master_certification(self):
        report = s.build_step6p_phase6_certification(
            step6o_getter=lambda **_: _step6o(package_ready=False)
        )
        self.assertFalse(report["phase6_engineering_certified"])
        self.assertEqual(report["state"], "phase6_certification_blocked")
        self.assertIn("step6o_package_ready", report["blocking_reasons"])

    def test_step6o_safety_regression_blocks_master_certification(self):
        report = s.build_step6p_phase6_certification(
            step6o_getter=lambda **_: _step6o(preserve_storage=False)
        )
        self.assertFalse(report["phase6_engineering_certified"])
        self.assertIn("step6o_rollback_preserves_persistent_storage", report["blocking_reasons"])

    def test_master_manifest_hash_is_deterministic(self):
        getter = lambda **_: _step6o()
        a = s.build_step6p_phase6_certification(env={s.CERTIFIED_REVISION_ENV: "1" * 40}, step6o_getter=getter)
        b = s.build_step6p_phase6_certification(env={s.CERTIFIED_REVISION_ENV: "2" * 40}, step6o_getter=getter)
        self.assertEqual(
            a["master_freeze"]["master_manifest_sha256"],
            b["master_freeze"]["master_manifest_sha256"],
        )
        self.assertEqual(
            a["master_freeze"]["canonical_json_sha256"],
            a["master_freeze"]["master_manifest_sha256"],
        )

    def test_require_certified_is_fail_closed(self):
        with patch.object(
            s,
            "build_step6p_phase6_certification",
            return_value={"phase6_engineering_certified": False, "blocking_reasons": ["proof missing"]},
        ):
            with self.assertRaises(s.WNBAStep6PNotCertifiedError):
                s.require_step6p_phase6_certified()

    def test_api_is_get_only(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        with patch(
            "sports_api.api.wnba_step6p_phase6_certification.build_step6p_phase6_certification",
            return_value={"state": "phase6_complete_safe_deferred", "phase6_engineering_certified": True},
        ):
            response = client.get("/api/v1/wnba/runtime/phase6-certification")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["phase6_engineering_certified"])
        self.assertEqual(client.post("/api/v1/wnba/runtime/phase6-certification").status_code, 405)
        self.assertEqual(client.put("/api/v1/wnba/runtime/phase6-certification").status_code, 405)
        self.assertEqual(client.delete("/api/v1/wnba/runtime/phase6-certification").status_code, 405)


if __name__ == "__main__":
    unittest.main()
