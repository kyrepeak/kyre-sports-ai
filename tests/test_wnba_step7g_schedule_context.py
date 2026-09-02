from __future__ import annotations

import unittest

from sports_api.wnba_schedule_context import WNBARestTravelUpstreamError
from sports_api.wnba_step7g_first_party_schedule_context import (
    _validate_included_games,
    classify_step7g_step4n_game,
)


def _team(mapped: bool, team_id: int | None, key: str | None) -> dict:
    return {
        "mapped_to_registry": mapped,
        "official_team_id": team_id,
        "team_key": key,
    }


def _game(
    *,
    away_mapped: bool = True,
    home_mapped: bool = True,
    label: str | None = None,
    game_id: str = "1022600001",
    valid_id: bool = True,
    distinct: bool = True,
) -> dict:
    away_id = 1 if away_mapped else 15026
    home_id = (2 if distinct else away_id) if home_mapped else 15008
    return {
        "game_id": game_id,
        "away": _team(away_mapped, away_id, "away" if away_mapped else None),
        "home": _team(home_mapped, home_id, "home" if home_mapped else None),
        "competition": {"game_label": label},
        "verification": {
            "game_id_valid": valid_id,
            "teams_mapped_to_registry": away_mapped and home_mapped,
            "home_away_distinct": distinct,
        },
    }


class Step7GStep4NScheduleContextTests(unittest.TestCase):
    def test_mapped_franchise_game_is_included(self) -> None:
        self.assertEqual(classify_step7g_step4n_game(_game()), "include")

    def test_two_unmapped_event_is_excluded_like_frozen_step4n(self) -> None:
        self.assertEqual(
            classify_step7g_step4n_game(
                _game(away_mapped=False, home_mapped=False, label="All-Star")
            ),
            "exclude_two_unmapped",
        )

    def test_one_sided_unmapped_explicit_preseason_is_excluded(self) -> None:
        self.assertEqual(
            classify_step7g_step4n_game(
                _game(away_mapped=False, home_mapped=True, label="Preseason")
            ),
            "exclude_explicit_preseason_one_sided",
        )

    def test_preseason_label_is_case_insensitive_but_exact(self) -> None:
        self.assertEqual(
            classify_step7g_step4n_game(
                _game(away_mapped=False, home_mapped=True, label="  pReSeAsOn  ")
            ),
            "exclude_explicit_preseason_one_sided",
        )
        with self.assertRaises(WNBARestTravelUpstreamError):
            classify_step7g_step4n_game(
                _game(
                    away_mapped=False,
                    home_mapped=True,
                    label="Preseason Showcase",
                )
            )

    def test_one_sided_unmapped_regular_looking_game_fails_closed(self) -> None:
        for label in (None, "", "Regular Season", "Commissioner's Cup", "Playoffs"):
            with self.subTest(label=label):
                with self.assertRaises(WNBARestTravelUpstreamError):
                    classify_step7g_step4n_game(
                        _game(away_mapped=False, home_mapped=True, label=label)
                    )

    def test_one_sided_unmapped_home_team_also_fails_closed(self) -> None:
        with self.assertRaises(WNBARestTravelUpstreamError):
            classify_step7g_step4n_game(
                _game(away_mapped=True, home_mapped=False, label="Regular Season")
            )

    def test_included_games_reject_invalid_game_id(self) -> None:
        with self.assertRaises(WNBARestTravelUpstreamError):
            _validate_included_games([_game(valid_id=False)])

    def test_included_games_reject_duplicate_game_ids(self) -> None:
        row = _game(game_id="1022600001")
        with self.assertRaises(WNBARestTravelUpstreamError):
            _validate_included_games([row, _game(game_id="1022600001")])

    def test_included_games_reject_same_home_away_identity(self) -> None:
        with self.assertRaises(WNBARestTravelUpstreamError):
            _validate_included_games([_game(distinct=False)])

    def test_clean_included_games_pass_integrity(self) -> None:
        _validate_included_games(
            [_game(game_id="1022600001"), _game(game_id="1022600002")]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
