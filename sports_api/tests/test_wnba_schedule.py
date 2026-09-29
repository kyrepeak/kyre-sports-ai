import copy
import unittest
from unittest.mock import patch

from sports_api.wnba_schedule import (
    WNBA_CDN_SCHEDULE_URL,
    WNBA_PUBLIC_SCHEDULE_API_URL,
    WNBA_STATS_SCHEDULE_URL,
    _CACHE,
    _date_block_iso,
    _fetch_schedule_payload,
    get_daily_schedule_dataset,
    verify_daily_slate_dataset,
)


def _team(team_id, city, name, tricode, slug):
    return {
        "teamId": team_id,
        "teamName": name,
        "teamCity": city,
        "teamTricode": tricode,
        "teamSlug": slug,
        "wins": 20,
        "losses": 10,
        "score": 0,
        "seed": 0,
    }


def _game(game_id="1022600300"):
    return {
        "gameId": game_id,
        "gameCode": "20260826/INDNYL",
        "gameStatus": 1,
        "gameStatusText": "7:00 pm ET",
        "gameSequence": 1,
        "gameDateTimeUTC": "2026-08-26T23:00:00Z",
        "gameDateTimeEst": "2026-08-26T19:00:00Z",
        "day": "Wed",
        "gameLabel": "",
        "gameSubLabel": "",
        "gameSubtype": "",
        "seriesText": "",
        "seriesGameNumber": "",
        "ifNecessary": False,
        "arenaName": "Barclays Center",
        "arenaCity": "Brooklyn",
        "arenaState": "NY",
        "isNeutral": False,
        "postponedStatus": "N",
        "broadcasters": {
            "nationalBroadcasters": [
                {"broadcasterDisplay": "ESPN"},
                {"broadcasterDisplay": "ESPN"},
            ]
        },
        "awayTeam": _team(
            1611661325, "Indiana", "Fever", "IND", "fever"
        ),
        "homeTeam": _team(
            1611661313, "New York", "Liberty", "NYL", "liberty"
        ),
    }


def _payload(games=None, season="2026", game_date="08/26/2026 00:00:00"):
    return {
        "meta": {"version": 1},
        "leagueSchedule": {
            "seasonYear": season,
            "leagueId": "10",
            "gameDates": [
                {
                    "gameDate": game_date,
                    "games": list(games if games is not None else [_game()]),
                }
            ],
        },
    }


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return copy.deepcopy(self._payload)


class WNBAScheduleTests(unittest.TestCase):
    def setUp(self):
        _CACHE.clear()

    def test_date_block_normalization(self):
        self.assertEqual(
            _date_block_iso("08/26/2026 00:00:00"),
            "2026-08-26",
        )

    @patch("sports_api.wnba_schedule._fetch_schedule_payload")
    def test_daily_schedule_maps_official_teams_and_times(self, mock_fetch):
        mock_fetch.return_value = (
            _payload(),
            "2026-08-26T00:00:00+00:00",
            "wnba_cdn_schedule",
            "https://cdn.wnba.com/schedule.json",
            False,
        )

        dataset = get_daily_schedule_dataset("2026-08-26", 2026)

        self.assertEqual(dataset["game_count"], 1)
        game = dataset["games"][0]
        self.assertEqual(game["game_id"], "1022600300")
        self.assertEqual(game["away"]["team_key"], "indiana-fever")
        self.assertEqual(game["home"]["team_key"], "new-york-liberty")
        self.assertEqual(game["venue"]["name"], "Barclays Center")
        self.assertEqual(game["status"]["category"], "scheduled")
        self.assertTrue(game["verification"]["playable_pregame"])
        self.assertEqual(game["broadcasts"], ["ESPN"])
        self.assertTrue(game["game_datetime_eastern"].endswith("-04:00"))

    @patch("sports_api.wnba_schedule._fetch_schedule_payload")
    def test_postponed_game_is_not_playable_pregame(self, mock_fetch):
        game = _game()
        game["postponedStatus"] = "Y"
        game["gameStatusText"] = "Postponed"
        mock_fetch.return_value = (
            _payload([game]),
            "2026-08-26T00:00:00+00:00",
            "wnba_cdn_schedule",
            "https://cdn.wnba.com/schedule.json",
            False,
        )

        dataset = get_daily_schedule_dataset("2026-08-26", 2026)
        normalized = dataset["games"][0]

        self.assertTrue(normalized["schedule_change"]["postponed"])
        self.assertTrue(normalized["schedule_change"]["schedule_changed"])
        self.assertEqual(normalized["status"]["category"], "postponed")
        self.assertFalse(normalized["verification"]["playable_pregame"])

    @patch("sports_api.wnba_schedule._fetch_schedule_payload")
    def test_slate_verification_rejects_duplicate_game_ids(self, mock_fetch):
        mock_fetch.return_value = (
            _payload([_game("1022600300"), _game("1022600300")]),
            "2026-08-26T00:00:00+00:00",
            "wnba_cdn_schedule",
            "https://cdn.wnba.com/schedule.json",
            False,
        )

        result = verify_daily_slate_dataset("2026-08-26", 2026)

        self.assertFalse(result["slate"]["all_game_ids_unique"])
        self.assertFalse(result["slate"]["slate_integrity_pass"])
        self.assertEqual(
            result["slate"]["duplicate_game_ids"],
            ["1022600300"],
        )
        self.assertIn("duplicate_game_id", result["slate"]["blocking_reasons"])

    @patch("sports_api.wnba_schedule._fetch_schedule_payload")
    def test_no_official_date_block_returns_verified_empty_slate(self, mock_fetch):
        mock_fetch.return_value = (
            _payload(game_date="08/25/2026 00:00:00"),
            "2026-08-26T00:00:00+00:00",
            "wnba_cdn_schedule",
            "https://cdn.wnba.com/schedule.json",
            False,
        )

        result = verify_daily_slate_dataset("2026-08-26", 2026)

        self.assertEqual(result["slate"]["normalized_game_count"], 0)
        self.assertEqual(
            result["slate"]["completeness_status"],
            "no_games_listed_for_date",
        )
        self.assertTrue(result["slate"]["slate_integrity_pass"])

    @patch("sports_api.wnba_schedule._fetch_schedule_payload")
    def test_unmapped_team_fails_slate_integrity(self, mock_fetch):
        game = _game()
        game["homeTeam"] = _team(
            9999999999,
            "Unknown",
            "Expansion",
            "XXX",
            "unknown-expansion",
        )
        mock_fetch.return_value = (
            _payload([game]),
            "2026-08-26T00:00:00+00:00",
            "wnba_cdn_schedule",
            "https://cdn.wnba.com/schedule.json",
            False,
        )

        result = verify_daily_slate_dataset("2026-08-26", 2026)

        self.assertFalse(result["slate"]["all_teams_mapped_to_registry"])
        self.assertFalse(result["slate"]["slate_integrity_pass"])
        self.assertIn(
            "unmapped_team_identity",
            result["slate"]["blocking_reasons"],
        )

    def test_invalid_date_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
            get_daily_schedule_dataset("08/26/2026", 2026)

    @patch("sports_api.wnba_schedule.httpx.get")
    def test_fetch_prefers_public_wnba_schedule_api(self, mock_get):
        valid = _payload(season="2026")
        mock_get.return_value = _FakeResponse(valid)

        _, _, source_variant, source_url, cache_hit = _fetch_schedule_payload(2026)

        self.assertEqual(source_variant, "wnba_public_schedule_api")
        self.assertEqual(source_url, WNBA_PUBLIC_SCHEDULE_API_URL)
        self.assertNotEqual(source_url, WNBA_STATS_SCHEDULE_URL)
        self.assertFalse(cache_hit)
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(
            mock_get.call_args.kwargs["params"],
            [("season", "2026"), ("regionId", "1")],
        )

    @patch("sports_api.wnba_schedule.httpx.get")
    def test_fetch_falls_back_to_current_cdn_not_retired_stats(self, mock_get):
        wrong_season = _payload(season="2025")
        valid = _payload(season="2026")
        mock_get.side_effect = [
            _FakeResponse(wrong_season),
            _FakeResponse(valid),
        ]

        _, _, source_variant, source_url, cache_hit = _fetch_schedule_payload(2026)

        self.assertEqual(source_variant, "wnba_cdn_schedule")
        self.assertEqual(source_url, WNBA_CDN_SCHEDULE_URL)
        self.assertNotEqual(source_url, WNBA_STATS_SCHEDULE_URL)
        self.assertFalse(cache_hit)
        self.assertEqual(mock_get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
