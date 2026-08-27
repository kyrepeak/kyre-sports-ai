from __future__ import annotations

import unittest

from sports_api import wnba_step7g_first_party_team_history as base
from sports_api import wnba_step7g_first_party_team_history_cup_safe as cup_safe


class Step7GCommissionersCupExclusionTests(unittest.TestCase):
    def setUp(self) -> None:
        cup_safe.restore_base_marker_for_tests()
        cup_safe.install_exact_cup_exclusion()

    def tearDown(self) -> None:
        cup_safe.restore_base_marker_for_tests()

    def test_exact_2026_commissioners_cup_game_is_non_regular(self) -> None:
        self.assertFalse(
            base._regular_season_marker({"game_id": "1052600001"}, 2026)
        )

    def test_other_105_game_id_still_fails_closed(self) -> None:
        with self.assertRaises(base.frozen.WNBATeamHistoryUpstreamError):
            base._regular_season_marker({"game_id": "1052600002"}, 2026)

    def test_regular_2026_game_family_is_unchanged(self) -> None:
        self.assertTrue(
            base._regular_season_marker({"game_id": "1022600001", "competition": {}}, 2026)
        )

    def test_known_preseason_family_is_still_excluded(self) -> None:
        self.assertFalse(
            base._regular_season_marker({"game_id": "1012600001"}, 2026)
        )

    def test_overlay_install_is_idempotent(self) -> None:
        first = base._regular_season_marker
        cup_safe.install_exact_cup_exclusion()
        self.assertIs(base._regular_season_marker, first)


if __name__ == "__main__":
    unittest.main(verbosity=2)
