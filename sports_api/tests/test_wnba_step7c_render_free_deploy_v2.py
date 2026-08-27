from __future__ import annotations

import unittest

import sports_api.tools.wnba_step7c_render_free_deploy as base
import sports_api.tools.wnba_step7c_render_free_deploy_v2 as s


class Step7CRenderFreeDeployV2Tests(unittest.TestCase):
    def test_free_payload_omits_unsupported_shutdown_delay(self):
        payload = s.build_free_service_payload(owner_id="tea-test")
        details = payload["serviceDetails"]
        self.assertEqual(details["plan"], "free")
        self.assertEqual(details["numInstances"], 1)
        self.assertNotIn("disk", details)
        self.assertNotIn("maxShutdownDelaySeconds", details)
        base.validate_free_payload(payload)

    def test_source_release_remains_exact_step7b_merge(self):
        self.assertEqual(base.SOURCE_REVISION, "12b9a0bb21e72f16282f562d848673222d48c7f2")
        self.assertEqual(base.SOURCE_BRANCH, "wnba-production-7c-20260827")
        self.assertEqual(base.SERVICE_NAME, "kyre-sports-api")


if __name__ == "__main__":
    unittest.main()
