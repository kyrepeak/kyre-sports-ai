from __future__ import annotations

import unittest

import sports_api.tools.wnba_step7d_render_supabase_wiring as s


class Step7DRenderSupabaseWiringTests(unittest.TestCase):
    def base_env(self):
        return {
            "RENDER_API_KEY": "render-test-key-abcdefghijklmnopqrstuvwxyz",
            "WNBA_KYRE_SUPABASE_URL": "https://jqajcdckalsfizbvngiu.supabase.co",
            "WNBA_KYRE_SUPABASE_SECRET_KEY": "unit-test-server-credential-not-real-12345",
            "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
            "WNBA_KYRE_DIRECT_SYNC_ENABLED": "false",
            "WNBA_KYRE_RECONCILED_SYNC_ENABLED": "false",
            "WNBA_STEP6J_CANARY_ENABLED": "false",
        }

    def test_render_env_selects_supabase_and_keeps_all_switches_off(self):
        values = s.build_render_env_values(self.base_env())
        self.assertEqual(values["WNBA_KYRE_DURABLE_STORAGE_BACKEND"], "supabase")
        self.assertEqual(values["WNBA_KYRE_SUPABASE_URL"], "https://jqajcdckalsfizbvngiu.supabase.co")
        self.assertIn("WNBA_KYRE_SUPABASE_SECRET_KEY", values)
        for key in s.OFF_SWITCHES:
            self.assertEqual(values[key], "false")

    def test_enabled_runtime_is_rejected(self):
        env = self.base_env()
        env["WNBA_PRODUCTION_RUNTIME_ENABLED"] = "true"
        with self.assertRaises(s.Step7DWiringError):
            s.build_render_env_values(env)

    def test_enabled_direct_sync_is_rejected(self):
        env = self.base_env()
        env["WNBA_KYRE_DIRECT_SYNC_ENABLED"] = "true"
        with self.assertRaises(s.Step7DWiringError):
            s.build_render_env_values(env)

    def test_wrong_supabase_project_is_rejected(self):
        env = self.base_env()
        env["WNBA_KYRE_SUPABASE_URL"] = "https://wrong-project.supabase.co"
        with self.assertRaises(s.Step7DWiringError):
            s.build_render_env_values(env)

    def test_missing_secret_is_rejected(self):
        env = self.base_env()
        env.pop("WNBA_KYRE_SUPABASE_SECRET_KEY")
        with self.assertRaises(s.Step7DWiringError):
            s.build_render_env_values(env)

    def test_source_release_remains_exact_step7b_merge(self):
        self.assertEqual(s.step7c.SOURCE_REVISION, "12b9a0bb21e72f16282f562d848673222d48c7f2")
        self.assertEqual(s.step7c.SOURCE_BRANCH, "wnba-production-7c-20260827")
        self.assertEqual(s.SERVICE_URL, "https://kyre-sports-api.onrender.com")
        self.assertEqual(s.EXPECTED_SUPABASE_HOST, "jqajcdckalsfizbvngiu.supabase.co")


if __name__ == "__main__":
    unittest.main()
