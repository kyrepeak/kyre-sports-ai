from __future__ import annotations

import unittest

from sports_api.tools.wnba_step7e_production_smoke_v2 import (
    EXPECTED_LEGACY_STEP6U_BLOCKER,
    Step7EV2SmokeError,
    validate_step6u_phase7_preactivation,
)


class Step7EV2ProductionSmokeTests(unittest.TestCase):
    def good_status(self):
        return {
            "selected_backend": "supabase",
            "configuration_ready": False,
            "bridge_ready": False,
            "verification_required": True,
            "scheduler_authorized": False,
            "blocking_reasons": [EXPECTED_LEGACY_STEP6U_BLOCKER],
            "step_6t": {
                "configuration_ready": True,
                "verification_requires_network": True,
                "verification_is_read_only": True,
            },
            "step_5w": {
                "phase": "pre_activation_blocked",
                "checkpoint_ready": False,
                "live_cycle_allowed": False,
            },
            "safety": {
                "production_runtime_enabled": False,
                "scheduler_started": False,
                "scheduler_authorized_by_step6u": False,
                "storage_write_performed_by_status": False,
            },
        }

    def test_expected_legacy_block_is_healthy_for_phase7_preactivation(self):
        validate_step6u_phase7_preactivation(self.good_status())

    def test_unexpected_blocker_fails_closed(self):
        doc = self.good_status()
        doc["blocking_reasons"] = ["something else"]
        with self.assertRaises(Step7EV2SmokeError):
            validate_step6u_phase7_preactivation(doc)

    def test_scheduler_authority_fails_closed(self):
        doc = self.good_status()
        doc["scheduler_authorized"] = True
        with self.assertRaises(Step7EV2SmokeError):
            validate_step6u_phase7_preactivation(doc)

    def test_step6t_must_still_be_ready(self):
        doc = self.good_status()
        doc["step_6t"]["configuration_ready"] = False
        with self.assertRaises(Step7EV2SmokeError):
            validate_step6u_phase7_preactivation(doc)

    def test_legacy_step5w_must_not_allow_live_cycle(self):
        doc = self.good_status()
        doc["step_5w"]["live_cycle_allowed"] = True
        with self.assertRaises(Step7EV2SmokeError):
            validate_step6u_phase7_preactivation(doc)

    def test_production_runtime_must_remain_off(self):
        doc = self.good_status()
        doc["safety"]["production_runtime_enabled"] = True
        with self.assertRaises(Step7EV2SmokeError):
            validate_step6u_phase7_preactivation(doc)


if __name__ == "__main__":
    unittest.main()
