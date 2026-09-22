from __future__ import annotations

from copy import deepcopy
import unittest
from unittest.mock import patch

from sports_api import wnba_team_history as frozen
from sports_api import wnba_step7g_first_party_team_history as adapter

SEASON = 2026
TOR = {
    "official_team_id": 1611661330,
    "team_key": "toronto-tempo",
    "full_name": "Toronto Tempo",
    "team_abbreviation": "TOR",
}
NYL = {
    "official_team_id": 1611661313,
    "team_key": "new-york-liberty",
    "full_name": "New York Liberty",
    "team_abbreviation": "NYL",
}
ATL = {
    "official_team_id": 1611661331,
    "team_key": "atlanta-dream",
    "full_name": "Atlanta Dream",
    "team_abbreviation": "ATL",
}


def _stats(points: int, *, minutes: float = 200.0) -> dict:
    return {
        "minutes_raw": str(minutes),
        "minutes": minutes,
        "field_goals_made": 30,
        "field_goals_attempted": 70,
        "field_goal_percentage": 30 / 70,
        "three_pointers_made": 8,
        "three_pointers_attempted": 24,
        "three_point_percentage": 8 / 24,
        "free_throws_made": 12,
        "free_throws_attempted": 15,
        "free_throw_percentage": 0.8,
        "offensive_rebounds": 8,
        "defensive_rebounds": 28,
        "rebounds": 36,
        "assists": 19,
        "steals": 7,
        "blocks": 4,
        "turnovers": 12,
        "personal_fouls": 18,
        "points": points,
        "plus_minus": None,
    }


def _schedule_team(team: dict, score: int) -> dict:
    return {
        "official_team_id": team["official_team_id"],
        "team_key": team["team_key"],
        "full_name": team["full_name"],
        "team_tricode": team["team_abbreviation"],
        "score": score,
        "mapped_to_registry": True,
    }


def _game(
    game_id: str = "1022600001",
    *,
    game_date: str = "2026-05-10",
    away: dict = TOR,
    home: dict = NYL,
    away_score: int = 80,
    home_score: int = 75,
    status: str = "final",
    label: str | None = None,
) -> dict:
    return {
        "game_id": game_id,
        "official_schedule_date": game_date,
        "status": {"category": status},
        "competition": {"game_label": label},
        "away": _schedule_team(away, away_score),
        "home": _schedule_team(home, home_score),
        "verification": {
            "game_id_valid": True,
            "teams_mapped_to_registry": True,
            "home_away_distinct": True,
        },
    }


def _box(
    game: dict,
    *,
    away: dict | None = None,
    home: dict | None = None,
    away_minutes: float = 200.0,
    home_minutes: float = 200.0,
) -> dict:
    away_identity = away or TOR
    home_identity = home or NYL
    return {
        "source": adapter.WNBA_FIRST_PARTY_SOURCE,
        "source_url": f"https://www.wnba.com/game/{game['game_id']}",
        "game_id": game["game_id"],
        "cache_hit": False,
        "away": {
            **away_identity,
            "stats": _stats(game["away"]["score"], minutes=away_minutes),
        },
        "home": {
            **home_identity,
            "stats": _stats(game["home"]["score"], minutes=home_minutes),
        },
    }


def _schedule(*games: dict) -> dict:
    return {
        "source": "WNBA.com",
        "source_url": "https://www.wnba.com/schedule",
        "source_variant": "wnba_com_first_party_schedule_step4n_context",
        "retrieved_at_utc": "2026-08-27T00:00:00+00:00",
        "games": list(games),
    }


class Step7GStep4JTeamHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        adapter._CACHE.clear()

    def test_completed_regular_season_game_builds_frozen_step4j_pair(self) -> None:
        game = _game()
        base = adapter._build_team_history_base(
            _schedule(game),
            TOR["team_key"],
            SEASON,
            box_loader=lambda game_id, season: _box(game),
        )
        target = [row for row in base["rows"] if row["team_key"] == TOR["team_key"]]
        self.assertEqual(len(target), 1)
        row = target[0]
        self.assertTrue(row["paired_opponent_row"])
        self.assertEqual(row["opponent_team_key"], NYL["team_key"])
        self.assertEqual(row["opponent_points"], 75.0)
        self.assertEqual(row["point_margin_from_scores"], 5.0)
        self.assertEqual(row["result"], "W")
        self.assertTrue(base["verification"]["normalized_with_frozen_step4j_row_contract"])
        self.assertTrue(base["verification"]["all_game_ids_have_two_team_rows"])

    def test_non_final_game_is_not_observed_history(self) -> None:
        game = _game(status="scheduled")
        calls: list[str] = []

        def loader(game_id: str, season: int) -> dict:
            calls.append(game_id)
            return _box(game)

        base = adapter._build_team_history_base(
            _schedule(game), TOR["team_key"], SEASON, box_loader=loader
        )
        self.assertEqual(base["season_team_game_count"], 0)
        self.assertEqual(calls, [])

    def test_known_preseason_family_is_excluded(self) -> None:
        game = _game(game_id="1012600001", label="Preseason")
        base = adapter._build_team_history_base(
            _schedule(game),
            TOR["team_key"],
            SEASON,
            box_loader=lambda game_id, season: self.fail("preseason box should not load"),
        )
        self.assertEqual(base["season_team_game_count"], 0)

    def test_unknown_completed_game_family_fails_closed(self) -> None:
        with self.assertRaises(frozen.WNBATeamHistoryUpstreamError):
            adapter._build_team_history_base(
                _schedule(_game(game_id="1092600001")),
                TOR["team_key"],
                SEASON,
                box_loader=lambda game_id, season: {},
            )

    def test_regular_marker_conflicting_with_preseason_label_fails_closed(self) -> None:
        with self.assertRaises(frozen.WNBATeamHistoryUpstreamError):
            adapter._build_team_history_base(
                _schedule(_game(label="Preseason")),
                TOR["team_key"],
                SEASON,
                box_loader=lambda game_id, season: {},
            )

    def test_schedule_box_team_identity_mismatch_fails_closed(self) -> None:
        game = _game()
        with self.assertRaises(frozen.WNBATeamHistoryUpstreamError):
            adapter._build_team_history_base(
                _schedule(game),
                TOR["team_key"],
                SEASON,
                box_loader=lambda game_id, season: _box(game, away=ATL),
            )

    def test_schedule_box_score_mismatch_fails_closed(self) -> None:
        game = _game()
        bad = _box(game)
        bad["away"]["stats"]["points"] = 79
        with self.assertRaises(frozen.WNBATeamHistoryUpstreamError):
            adapter._build_team_history_base(
                _schedule(game),
                TOR["team_key"],
                SEASON,
                box_loader=lambda game_id, season: bad,
            )

    def test_missing_team_minutes_fails_closed(self) -> None:
        game = _game()
        bad = _box(game)
        bad["away"]["stats"]["minutes"] = None
        with self.assertRaises(frozen.WNBATeamHistoryUpstreamError):
            adapter._build_team_history_base(
                _schedule(game),
                TOR["team_key"],
                SEASON,
                box_loader=lambda game_id, season: bad,
            )

    def test_duplicate_schedule_game_id_fails_closed(self) -> None:
        game = _game()
        with self.assertRaises(frozen.WNBATeamHistoryUpstreamError):
            adapter._build_team_history_base(
                _schedule(game, deepcopy(game)),
                TOR["team_key"],
                SEASON,
                box_loader=lambda game_id, season: _box(game),
            )

    def test_overtime_team_minutes_are_preserved_not_clamped(self) -> None:
        game = _game()
        base = adapter._build_team_history_base(
            _schedule(game),
            TOR["team_key"],
            SEASON,
            box_loader=lambda game_id, season: _box(
                game, away_minutes=225.0, home_minutes=225.0
            ),
        )
        target = next(row for row in base["rows"] if row["team_key"] == TOR["team_key"])
        self.assertEqual(target["minutes"], 225.0)

    def test_public_adapter_reuses_frozen_filter_and_summary_semantics(self) -> None:
        first = _game(
            game_id="1022600001",
            game_date="2026-05-10",
            away=TOR,
            home=NYL,
            away_score=80,
            home_score=75,
        )
        second = _game(
            game_id="1022600002",
            game_date="2026-05-12",
            away=ATL,
            home=TOR,
            away_score=70,
            home_score=90,
        )
        boxes = {
            first["game_id"]: _box(first),
            second["game_id"]: _box(second, away=ATL, home=TOR),
        }
        base = adapter._build_team_history_base(
            _schedule(first, second),
            TOR["team_key"],
            SEASON,
            box_loader=lambda game_id, season: boxes[game_id],
        )
        with patch.object(adapter, "_cached_base", return_value=(deepcopy(base), False)):
            dataset = adapter.get_first_party_team_game_log_dataset(
                TOR["team_key"], SEASON, last_n_games=1, location="Home"
            )
        self.assertEqual(dataset["game_count"], 1)
        self.assertEqual(dataset["games"][0]["game_id"], second["game_id"])
        self.assertEqual(dataset["summary"]["record"], {
            "wins": 1,
            "losses": 0,
            "win_percentage": 1.0,
        })

    def test_non_regular_season_request_fails_closed(self) -> None:
        with self.assertRaises(frozen.WNBATeamHistoryUpstreamError):
            adapter.get_first_party_team_game_log_dataset(
                TOR["team_key"], SEASON, season_type="Playoffs"
            )

    def test_same_team_opponent_filter_keeps_frozen_validation(self) -> None:
        with self.assertRaises(ValueError):
            adapter.get_first_party_team_game_log_dataset(
                TOR["team_key"],
                SEASON,
                opponent_team_key=TOR["team_key"],
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
