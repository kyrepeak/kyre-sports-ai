from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import unittest


class Step7GFirstPartyIntegrationTests(unittest.TestCase):
    def _run_child(self, code: str, *, enabled: bool) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["WNBA_STEP7G_FIRST_PARTY_ENABLED"] = "true" if enabled else "false"
        return subprocess.run(
            [sys.executable, "-c", textwrap.dedent(code)],
            cwd=os.getcwd(),
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_default_off_import_does_not_install_core_seams(self) -> None:
        completed = self._run_child(
            """
            import sports_api.wnba_step7g_first_party_integration as integration
            status = integration.get_step7g_first_party_status()
            assert status["enabled_flag"] is False, status
            assert status["all_core_seams_installed"] is False, status
            assert integration.INSTALLATION["installed"] is False, integration.INSTALLATION
            assert status["safety"]["default_enabled"] is False
            assert integration.availability.get_daily_schedule_dataset is integration._ORIGINAL_AVAILABILITY_DAILY_SCHEDULE
            assert integration.availability.get_latest_injury_report_dataset is integration._ORIGINAL_AVAILABILITY_INJURY_REPORT
            """,
            enabled=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_explicit_enable_installs_all_certified_core_seams(self) -> None:
        completed = self._run_child(
            """
            import sports_api.wnba_step7g_first_party_integration as integration
            status = integration.get_step7g_first_party_status()
            assert status["enabled_flag"] is True, status
            assert status["all_core_seams_installed"] is True, status
            assert integration.INSTALLATION["installed"] is True, integration.INSTALLATION
            assert all(status["seams"].values()), status
            assert status["seams"]["availability_daily_schedule"] is True
            assert status["seams"]["availability_current_roster"] is True
            assert status["seams"]["availability_injury_report"] is True
            assert status["certified_scope"]["core_model_input_readiness"] is True
            assert status["certified_scope"]["current_availability_daily_schedule"] is True
            assert status["certified_scope"]["current_availability_roster"] is True
            assert status["certified_scope"]["current_availability_injury_report"] is True
            assert status["certified_scope"]["current_availability"] is True
            assert status["certified_scope"]["shot_context"] is False
            assert status["certified_scope"]["advanced_context"] is False
            assert status["certified_scope"]["officiating_context"] is False
            assert status["safety"]["frozen_step4i_source_modified"] is False
            assert status["safety"]["frozen_step4c_source_modified"] is False
            """,
            enabled=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_rotation_bypass_raises_only_expected_upstream_family(self) -> None:
        completed = self._run_child(
            """
            import sports_api.wnba_step7g_first_party_integration as integration
            from sports_api.wnba_game_history import WNBAHistoryUpstreamError
            try:
                integration.rotation._request_stats_json("gamerotation", [])
            except WNBAHistoryUpstreamError:
                pass
            else:
                raise AssertionError("rotation bypass did not raise WNBAHistoryUpstreamError")
            """,
            enabled=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_optional_lineup_bypass_uses_frozen_fail_soft_error_family(self) -> None:
        completed = self._run_child(
            """
            import sports_api.wnba_step7g_first_party_integration as integration
            try:
                integration.opportunity.get_lineups_dataset()
            except integration.opportunity.WNBALineupContextUpstreamError:
                pass
            else:
                raise AssertionError("optional lineup bypass did not use fail-soft error family")
            """,
            enabled=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_step4i_schedule_failure_translates_to_availability_error_family(self) -> None:
        completed = self._run_child(
            """
            import sports_api.wnba_step7g_first_party_integration as integration
            from sports_api.wnba_schedule import WNBAScheduleUpstreamError

            def broken(*args, **kwargs):
                raise WNBAScheduleUpstreamError("synthetic schedule failure")

            integration.get_step7g_step4i_daily_schedule_dataset = broken
            try:
                integration.availability.get_daily_schedule_dataset("2026-08-27", 2026)
            except integration.availability.WNBAAvailabilityUpstreamError as exc:
                assert "synthetic schedule failure" in str(exc)
            else:
                raise AssertionError("Step 4I schedule failure did not translate to availability family")
            """,
            enabled=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)

    def test_guard_refuses_unknown_override(self) -> None:
        completed = self._run_child(
            """
            import sports_api.wnba_step7g_first_party_integration as integration
            def original():
                return None
            def target():
                return None
            def unknown():
                return None
            try:
                integration._guarded_replace(
                    label="test seam",
                    current=unknown,
                    original=original,
                    target=target,
                )
            except RuntimeError:
                pass
            else:
                raise AssertionError("unknown override was silently replaced")
            """,
            enabled=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
