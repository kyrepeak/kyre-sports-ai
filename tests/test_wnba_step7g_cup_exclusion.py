from __future__ import annotations

import unittest
from unittest.mock import patch

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
        marker = base._regular_season_marker
        loader = base.get_first_party_game_box_score_dataset
        cup_safe.install_exact_cup_exclusion()
        self.assertIs(base._regular_season_marker, marker)
        self.assertIs(base.get_first_party_game_box_score_dataset, loader)

    def test_transient_upstream_box_failure_is_retried_then_succeeds(self) -> None:
        transient = base.WNBAStep7GFirstPartyUpstreamError("transient 502")
        expected = {"game_id": "1022600150"}
        with patch.object(
            cup_safe,
            "_ORIGINAL_BOX_LOADER",
            side_effect=[transient, transient, expected],
        ) as loader, patch.object(cup_safe, "sleep") as sleeper:
            result = cup_safe._retrying_box_loader("1022600150", 2026)
        self.assertEqual(result, expected)
        self.assertEqual(loader.call_count, 3)
        self.assertEqual(sleeper.call_count, 2)

    def test_non_transport_failure_is_not_retried(self) -> None:
        with patch.object(
            cup_safe,
            "_ORIGINAL_BOX_LOADER",
            side_effect=ValueError("malformed data"),
        ) as loader, patch.object(cup_safe, "sleep") as sleeper:
            with self.assertRaises(ValueError):
                cup_safe._retrying_box_loader("1022600150", 2026)
        self.assertEqual(loader.call_count, 1)
        sleeper.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
