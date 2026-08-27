from __future__ import annotations

import unittest

from sports_api.tools.wnba_step7e_production_smoke import (
    BASE_URL,
    CRITICAL_OPENAPI_PATHS,
    ENDPOINTS,
    EXPECTED_RELEASE_REVISION,
    EXPECTED_SUPABASE_HOST,
    Step7ESmokeError,
    validate_games_today,
    validate_health,
    validate_openapi,
    validate_step6r,
    validate_step6t,
    validate_step6u,
    validate_step6w,
    validate_teams,
)


class Step7EProductionSmokeTests(unittest.TestCase):
    def test_source_and_release_are_pinned(self):
        self.assertEqual(BASE_URL, "https://kyre-sports-api.onrender.com")
        self.assertEqual(EXPECTED_RELEASE_REVISION, "12b9a0bb21e72f16282f562d848673222d48c7f2")
        self.assertEqual(EXPECTED_SUPABASE_HOST, "jqajcdckalsfizbvngiu.supabase.co")

    def test_only_get_smoke_paths_are_defined(self):
        names = [row[0] for row in ENDPOINTS]
        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(len(names), 10)
        self.assertIn("wnba_games_today", names)
        self.assertIn("step6u_bridge_status", names)

    def test_openapi_contract_requires_safety_and_data_paths(self):
        self.assertIn("/api/v1/wnba/games/today", CRITICAL_OPENAPI_PATHS)
        self.assertIn("/api/v1/wnba/runtime/step6r-supabase-storage", CRITICAL_OPENAPI_PATHS)
        self.assertIn("/api/v1/wnba/runtime/step6u-activation-bridge/status", CRITICAL_OPENAPI_PATHS)

    def test_valid_health(self):
        validate_health({"status": "ok"})
        with self.assertRaises(Step7ESmokeError):
            validate_health({"status": "bad"})

    def test_valid_openapi(self):
        paths = {path: {} for path in CRITICAL_OPENAPI_PATHS}
        for i in range(30):
            paths[f"/extra/{i}"] = {}
        validate_openapi({"paths": paths})
        with self.assertRaises(Step7ESmokeError):
            validate_openapi({"paths": {"/health": {}}})

    def test_valid_teams(self):
        teams = [{"id": i} for i in range(15)]
        validate_teams({"season": 2026, "team_count": 15, "teams": teams})
        with self.assertRaises(Step7ESmokeError):
            validate_teams({"season": 2026, "team_count": 1, "teams": [{}]})

    def test_valid_step6r(self):
        validate_step6r({
            "selected_backend": "supabase",
            "configuration_ready": True,
            "backend": {
                "project_host": EXPECTED_SUPABASE_HOST,
                "secret_configured": True,
                "secret_value_exposed": False,
            },
        })
        with self.assertRaises(Step7ESmokeError):
            validate_step6r({"selected_backend": "filesystem", "configuration_ready": True})

    def test_valid_step6t_and_step6u_remain_fail_closed(self):
        validate_step6t({
            "selected_backend": "supabase",
            "configuration_ready": True,
            "verification_requires_network": True,
            "verification_is_read_only": True,
            "scheduler_authorized": False,
        })
        validate_step6u({
            "selected_backend": "supabase",
            "configuration_ready": True,
            "bridge_ready": False,
            "verification_required": True,
            "scheduler_authorized": False,
            "safety": {"production_runtime_enabled": False, "scheduler_started": False},
        })
        with self.assertRaises(Step7ESmokeError):
            validate_step6u({
                "selected_backend": "supabase",
                "configuration_ready": True,
                "bridge_ready": True,
                "verification_required": False,
                "scheduler_authorized": True,
                "safety": {"production_runtime_enabled": True, "scheduler_started": True},
            })

    def test_valid_step6w(self):
        validate_step6w({
            "final_architecture_certified": True,
            "state": "wnba_upgraded_architecture_frozen",
            "production_live": False,
            "scheduler_authorized": False,
        })

    def test_games_today_requires_2026_and_list_shape(self):
        validate_games_today({"season": 2026, "games": []})
        with self.assertRaises(Step7ESmokeError):
            validate_games_today({"season": 2025, "games": []})


if __name__ == "__main__":
    unittest.main()
