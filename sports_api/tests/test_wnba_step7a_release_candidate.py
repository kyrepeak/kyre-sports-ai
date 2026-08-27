from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import sports_api.wnba_step7a_release_candidate as s
from sports_api.api.wnba_step7a_release_candidate import router


def _step6w(**_):
    return {
        "final_architecture_certified": True,
        "state": "wnba_upgraded_architecture_frozen",
        "step6j_live_canary_complete": True,
        "production_live": False,
        "scheduler_authorized": False,
        "scheduler_started": False,
        "final_freeze": {
            "final_manifest_sha256": s.CERTIFIED_STEP6W_FINAL_MANIFEST_SHA256,
            "canonical_json_sha256": s.CERTIFIED_STEP6W_FINAL_MANIFEST_SHA256,
        },
        "supabase": {"active_locks_after_canary": 0},
        "semantics": {
            "network_used": False,
            "production_runtime_mutated": False,
            "scheduler_authorization_mutated": False,
            "feed_write_performed": False,
            "secret_read": False,
            "secret_returned": False,
        },
    }


class Step7AReleaseCandidateTests(unittest.TestCase):
    def test_certified_step6w_identity_is_exact(self):
        self.assertEqual(s.CERTIFIED_STEP6W_REVISION, "653ea47836b436076c2bc8e9e58d6a1d11b3dee3")
        self.assertEqual(s.CERTIFIED_STEP6W_RUN_ID, 33050371110)
        self.assertEqual(s.CERTIFIED_STEP6W_ARTIFACT_ID, 9637336718)
        self.assertEqual(
            s.CERTIFIED_STEP6W_FINAL_MANIFEST_SHA256,
            "31b59ff2d9515e19143268f39ba3e5172fac07af3b839b88fe0fe08daa2aff99",
        )

    def test_happy_path_certifies_release_candidate_without_activation(self):
        report = s.build_step7a_release_candidate(step6w_getter=_step6w)
        self.assertTrue(report["release_candidate_certified"])
        self.assertEqual(report["state"], "wnba_production_release_candidate_certified")
        self.assertFalse(report["production_live"])
        self.assertFalse(report["merge_to_main_authorized"])
        self.assertFalse(report["render_deployment_authorized"])
        self.assertFalse(report["scheduler_authorized"])
        self.assertTrue(all(report["checks"].values()))

    def test_step6w_manifest_drift_blocks_candidate(self):
        bad = _step6w()
        bad["final_freeze"]["final_manifest_sha256"] = "0" * 64
        report = s.build_step7a_release_candidate(step6w_getter=lambda **_: bad)
        self.assertFalse(report["release_candidate_certified"])
        self.assertIn("step6w_manifest_matches_frozen_proof", report["blocking_reasons"])

    def test_step6w_not_certified_blocks_candidate(self):
        bad = _step6w()
        bad["final_architecture_certified"] = False
        report = s.build_step7a_release_candidate(step6w_getter=lambda **_: bad)
        self.assertFalse(report["release_candidate_certified"])
        self.assertIn("step6w_final_architecture_certified", report["blocking_reasons"])

    def test_production_runtime_regression_blocks_candidate(self):
        bad = _step6w()
        bad["production_live"] = True
        report = s.build_step7a_release_candidate(step6w_getter=lambda **_: bad)
        self.assertFalse(report["release_candidate_certified"])
        self.assertIn("production_runtime_still_off", report["blocking_reasons"])

    def test_scheduler_regression_blocks_candidate(self):
        bad = _step6w()
        bad["scheduler_authorized"] = True
        report = s.build_step7a_release_candidate(step6w_getter=lambda **_: bad)
        self.assertFalse(report["release_candidate_certified"])
        self.assertIn("scheduler_still_not_authorized", report["blocking_reasons"])

    def test_active_supabase_lock_blocks_candidate(self):
        bad = _step6w()
        bad["supabase"]["active_locks_after_canary"] = 1
        report = s.build_step7a_release_candidate(step6w_getter=lambda **_: bad)
        self.assertFalse(report["release_candidate_certified"])
        self.assertIn("supabase_canary_left_no_active_lock", report["blocking_reasons"])

    def test_release_manifest_is_deterministic(self):
        a = s.build_step7a_release_candidate(env={"A": "1"}, step6w_getter=_step6w)
        b = s.build_step7a_release_candidate(env={"A": "2"}, step6w_getter=_step6w)
        self.assertEqual(
            a["release_candidate"]["release_manifest_sha256"],
            b["release_candidate"]["release_manifest_sha256"],
        )
        self.assertEqual(
            a["release_candidate"]["release_manifest_sha256"],
            a["release_candidate"]["canonical_json_sha256"],
        )

    def test_release_policy_requires_new_step7b_boundary(self):
        report = s.build_step7a_release_candidate(step6w_getter=_step6w)
        policy = report["release_candidate"]["release_policy"]
        self.assertTrue(policy["candidate_only"])
        self.assertFalse(policy["merge_to_main_authorized"])
        self.assertFalse(policy["render_deployment_authorized"])
        self.assertFalse(policy["supabase_write_authorized"])
        self.assertEqual(policy["next_boundary"], "Step 7B explicit main-branch merge")

    def test_require_certified_is_fail_closed(self):
        with patch.object(
            s,
            "build_step7a_release_candidate",
            return_value={"release_candidate_certified": False, "blocking_reasons": ["blocked"]},
        ):
            with self.assertRaises(s.WNBAStep7ANotCertifiedError):
                s.require_step7a_release_candidate_certified()

    def test_api_is_get_only(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        with patch(
            "sports_api.api.wnba_step7a_release_candidate.build_step7a_release_candidate",
            return_value={"state": "wnba_production_release_candidate_certified", "release_candidate_certified": True},
        ):
            response = client.get("/api/v1/wnba/runtime/step7a-release-candidate")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["release_candidate_certified"])
        self.assertEqual(client.post("/api/v1/wnba/runtime/step7a-release-candidate").status_code, 405)
        self.assertEqual(client.put("/api/v1/wnba/runtime/step7a-release-candidate").status_code, 405)
        self.assertEqual(client.delete("/api/v1/wnba/runtime/step7a-release-candidate").status_code, 405)


if __name__ == "__main__":
    unittest.main()
