from __future__ import annotations

import unittest

from sports_api.tools.wnba_step7e_schedule_hotfix_deploy import (
    EXPECTED_SUPABASE_URL,
    OFF_SWITCHES,
    PATCH_BRANCH,
    PATCH_PARENT_REVISION,
    PATCH_REVISION,
    Step7EHotfixDeployError,
    _validate_existing_service,
    _validate_render_environment,
)


class Step7EHotfixDeployTests(unittest.TestCase):
    def render_env(self):
        values = {
            "WNBA_KYRE_DURABLE_STORAGE_BACKEND": "supabase",
            "WNBA_KYRE_SUPABASE_URL": EXPECTED_SUPABASE_URL,
            "WNBA_KYRE_SUPABASE_SECRET_KEY": "x" * 32,
        }
        values.update({name: "false" for name in OFF_SWITCHES})
        return values

    def service(self):
        return {
            "type": "web_service",
            "repo": "https://github.com/kyrepeak/kyre-sports-ai",
            "branch": PATCH_BRANCH,
            "autoDeploy": "no",
            "serviceDetails": {
                "runtime": "docker",
                "plan": "free",
            },
        }

    def test_patch_identity_is_exact_and_descends_from_step7b(self):
        self.assertEqual(PATCH_REVISION, "9a45b11704bb95ec5ace275b5dd941e27e32f745")
        self.assertEqual(PATCH_PARENT_REVISION, "12b9a0bb21e72f16282f562d848673222d48c7f2")
        self.assertEqual(PATCH_BRANCH, "wnba-production-7e-schedule-fix-20260827")

    def test_valid_free_service(self):
        _validate_existing_service(self.service())

    def test_paid_service_fails_closed(self):
        service = self.service()
        service["serviceDetails"]["plan"] = "starter"
        with self.assertRaises(Step7EHotfixDeployError):
            _validate_existing_service(service)

    def test_persistent_disk_fails_closed(self):
        service = self.service()
        service["serviceDetails"]["disk"] = {"id": "disk-test"}
        with self.assertRaises(Step7EHotfixDeployError):
            _validate_existing_service(service)

    def test_supabase_wiring_and_off_switches_required(self):
        _validate_render_environment(self.render_env())
        bad = self.render_env()
        bad["WNBA_KYRE_DURABLE_STORAGE_BACKEND"] = "filesystem"
        with self.assertRaises(Step7EHotfixDeployError):
            _validate_render_environment(bad)

    def test_any_enabled_switch_fails_closed(self):
        for name in OFF_SWITCHES:
            values = self.render_env()
            values[name] = "true"
            with self.subTest(name=name):
                with self.assertRaises(Step7EHotfixDeployError):
                    _validate_render_environment(values)

    def test_missing_server_secret_fails_closed(self):
        values = self.render_env()
        values["WNBA_KYRE_SUPABASE_SECRET_KEY"] = ""
        with self.assertRaises(Step7EHotfixDeployError):
            _validate_render_environment(values)


if __name__ == "__main__":
    unittest.main()
