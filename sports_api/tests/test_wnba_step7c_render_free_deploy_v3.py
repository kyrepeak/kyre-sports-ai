from __future__ import annotations

from copy import deepcopy
import unittest

import sports_api.tools.wnba_step7c_render_free_deploy as base
import sports_api.tools.wnba_step7c_render_free_deploy_v3 as s


class Step7CRenderFreeDeployV3Tests(unittest.TestCase):
    def test_payload_uses_render_docker_env_specific_schema(self):
        payload = s.build_free_service_payload(owner_id="tea-test")
        details = payload["serviceDetails"]
        self.assertEqual(details["plan"], "free")
        self.assertEqual(details["runtime"], "docker")
        self.assertEqual(details["numInstances"], 1)
        self.assertNotIn("disk", details)
        self.assertNotIn("maxShutdownDelaySeconds", details)
        self.assertNotIn("dockerfilePath", details)
        self.assertNotIn("dockerContext", details)
        docker = details["envSpecificDetails"]
        self.assertEqual(docker["dockerfilePath"], "sports_api/Dockerfile")
        self.assertEqual(docker["dockerContext"], ".")
        s.validate_free_payload(payload)

    def test_paid_plan_remains_rejected(self):
        payload = s.build_free_service_payload(owner_id="tea-test")
        mutated = deepcopy(payload)
        mutated["serviceDetails"]["plan"] = "starter"
        with self.assertRaises(s.Step7CV3Error):
            s.validate_free_payload(mutated)

    def test_disk_remains_rejected(self):
        payload = s.build_free_service_payload(owner_id="tea-test")
        mutated = deepcopy(payload)
        mutated["serviceDetails"]["disk"] = {"name": "nope", "mountPath": "/data", "sizeGB": 1}
        with self.assertRaises(s.Step7CV3Error):
            s.validate_free_payload(mutated)

    def test_runtime_switches_remain_off(self):
        payload = s.build_free_service_payload(owner_id="tea-test")
        env = {row["key"]: row["value"] for row in payload["envVars"]}
        for key in base.OFF_SWITCHES:
            self.assertEqual(env[key], "false")

    def test_release_pin_unchanged(self):
        self.assertEqual(base.SOURCE_REVISION, "12b9a0bb21e72f16282f562d848673222d48c7f2")
        self.assertEqual(base.SOURCE_BRANCH, "wnba-production-7c-20260827")
        self.assertEqual(base.SERVICE_NAME, "kyre-sports-api")


if __name__ == "__main__":
    unittest.main()
