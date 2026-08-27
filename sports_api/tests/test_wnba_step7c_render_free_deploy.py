from __future__ import annotations

from copy import deepcopy
import unittest

import sports_api.tools.wnba_step7c_render_free_deploy as s


class Step7CRenderFreeDeployTests(unittest.TestCase):
    def test_payload_is_free_diskless_and_preactivation_only(self):
        payload = s.build_free_service_payload(owner_id="tea-test")
        details = payload["serviceDetails"]
        self.assertEqual(payload["type"], "web_service")
        self.assertEqual(payload["autoDeploy"], "no")
        self.assertEqual(payload["repo"], s.SOURCE_REPOSITORY)
        self.assertEqual(payload["branch"], s.SOURCE_BRANCH)
        self.assertEqual(details["runtime"], "docker")
        self.assertEqual(details["plan"], "free")
        self.assertEqual(details["numInstances"], 1)
        self.assertNotIn("disk", details)
        self.assertEqual(details["dockerfilePath"], "sports_api/Dockerfile")
        env = {row["key"]: row["value"] for row in payload["envVars"]}
        for key in s.OFF_SWITCHES:
            self.assertEqual(env[key], "false")
        self.assertEqual(env["WEB_CONCURRENCY"], "1")
        self.assertEqual(env["WNBA_RELEASE_REVISION"], s.SOURCE_REVISION)

    def test_paid_plan_is_rejected(self):
        payload = s.build_free_service_payload(owner_id="tea-test")
        mutated = deepcopy(payload)
        mutated["serviceDetails"]["plan"] = "starter"
        with self.assertRaises(s.Step7CRenderError):
            s.validate_free_payload(mutated)

    def test_persistent_disk_is_rejected(self):
        payload = s.build_free_service_payload(owner_id="tea-test")
        mutated = deepcopy(payload)
        mutated["serviceDetails"]["disk"] = {
            "name": "should-not-exist",
            "mountPath": "/data",
            "sizeGB": 1,
        }
        with self.assertRaises(s.Step7CRenderError):
            s.validate_free_payload(mutated)

    def test_live_runtime_switch_is_rejected(self):
        payload = s.build_free_service_payload(owner_id="tea-test")
        mutated = deepcopy(payload)
        for row in mutated["envVars"]:
            if row["key"] == "WNBA_PRODUCTION_RUNTIME_ENABLED":
                row["value"] = "true"
        with self.assertRaises(s.Step7CRenderError):
            s.validate_free_payload(mutated)

    def test_secret_injection_is_rejected(self):
        payload = s.build_free_service_payload(owner_id="tea-test")
        mutated = deepcopy(payload)
        mutated["envVars"].append({"key": "RENDER_API_KEY", "value": "do-not-inject"})
        with self.assertRaises(s.Step7CRenderError):
            s.validate_free_payload(mutated)

    def test_source_pin_is_exact_step7b_merge(self):
        self.assertEqual(s.SOURCE_REVISION, "12b9a0bb21e72f16282f562d848673222d48c7f2")
        self.assertEqual(s.SOURCE_BRANCH, "wnba-production-7c-20260827")
        self.assertEqual(s.SERVICE_NAME, "kyre-sports-api")


if __name__ == "__main__":
    unittest.main()
