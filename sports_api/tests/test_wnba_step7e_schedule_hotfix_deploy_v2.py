from __future__ import annotations

import unittest

import sports_api.tools.wnba_step7e_schedule_hotfix_deploy as base
from sports_api.tools.wnba_step7e_schedule_hotfix_deploy_v2 import validate_render_environment


class Step7EHotfixDeployV2Tests(unittest.TestCase):
    def values(self, url: str):
        out = {
            "WNBA_KYRE_DURABLE_STORAGE_BACKEND": "supabase",
            "WNBA_KYRE_SUPABASE_URL": url,
            "WNBA_KYRE_SUPABASE_SECRET_KEY": "x" * 32,
        }
        out.update({name: "false" for name in base.OFF_SWITCHES})
        return out

    def test_exact_origin_is_valid(self):
        validate_render_environment(self.values("https://jqajcdckalsfizbvngiu.supabase.co"))

    def test_trailing_root_slash_is_valid(self):
        validate_render_environment(self.values("https://jqajcdckalsfizbvngiu.supabase.co/"))

    def test_wrong_host_fails_closed(self):
        with self.assertRaises(base.Step7EHotfixDeployError):
            validate_render_environment(self.values("https://example.invalid/"))

    def test_non_https_fails_closed(self):
        with self.assertRaises(base.Step7EHotfixDeployError):
            validate_render_environment(self.values("http://jqajcdckalsfizbvngiu.supabase.co/"))

    def test_non_root_path_fails_closed(self):
        with self.assertRaises(base.Step7EHotfixDeployError):
            validate_render_environment(self.values("https://jqajcdckalsfizbvngiu.supabase.co/rest/v1"))

    def test_query_or_credentials_fail_closed(self):
        for url in (
            "https://jqajcdckalsfizbvngiu.supabase.co/?x=1",
            "https://user:pass@jqajcdckalsfizbvngiu.supabase.co/",
        ):
            with self.subTest(url=url):
                with self.assertRaises(base.Step7EHotfixDeployError):
                    validate_render_environment(self.values(url))


if __name__ == "__main__":
    unittest.main()
