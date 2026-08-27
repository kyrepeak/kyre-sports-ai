import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from sports_api.wnba_availability import (
    WNBAAvailabilityNotFoundError,
    _candidate_report_datetimes,
    _report_url_for_datetime,
    _status_class,
    _validate_report_url,
    discover_latest_injury_report_url,
    get_game_availability_context_dataset,
    get_latest_injury_report_dataset,
    get_team_availability_context_dataset,
    parse_injury_report_text,
)


SAMPLE_TEXT = """Injury Report: 05/17/26 03:00 PM
Page 1 of 2
Game Date Game Time Matchup Team Player Name Current Status Reason
05/17/2026 01:30 (ET) LVA@ATL Las Vegas Aces Barker, Janiah Out Injury/Illness - Head; concussion
Atlanta Dream Howard, Rhyne Out Concussion Protocol
06:00 (ET) SEA@IND Seattle Storm Magbegor, Ezi Out Injury/Illness - Right Foot; Injury
Indiana Fever Boston, Aliyah Questionable
Injury/Illness - Right lower leg; right
lower leg
07:00 (ET) CHI@MIN Chicago Sky Carrington, DiJonai Out Injury/Illness - Left Foot; Left Foot
Minnesota Lynx Collier, Napheesa Out Injury/Illness - Left Ankle; Left Ankle
Page 2 of 2
TOR@LAS Toronto Tempo Allemand, Julie Out Injury/Illness - Left Hip; Injury
Los Angeles Sparks Atkins, Ariel Out
Injury/Illness - Head; Concussion
Protocol
05/18/2026 08:00 (ET) WAS@DAL Washington Mystics NOT YET SUBMITTED
Dallas Wings NOT YET SUBMITTED
10:00 (ET) CON@PDX Connecticut Sun NOT YET SUBMITTED
Portland Fire NOT YET SUBMITTED
"""


def roster_dataset():
    return {
        "players": [
            {"player_id": 1630163, "full_name": "Aliyah Boston", "team_key": "indiana-fever", "position": "C", "jersey_number": "7"},
            {"player_id": 1642286, "full_name": "Caitlin Clark", "team_key": "indiana-fever", "position": "G", "jersey_number": "22"},
            {"player_id": 1629482, "full_name": "Kelsey Mitchell", "team_key": "indiana-fever", "position": "G", "jersey_number": "0"},
            {"player_id": 1111, "full_name": "Lexie Hull", "team_key": "indiana-fever", "position": "G-F", "jersey_number": "10"},
            {"player_id": 2222, "full_name": "Natasha Howard", "team_key": "indiana-fever", "position": "F", "jersey_number": "6"},
            {"player_id": 3333, "full_name": "Bench Player", "team_key": "indiana-fever", "position": "G", "jersey_number": "1"},
            {"player_id": 4444, "full_name": "Ezi Magbegor", "team_key": "seattle-storm", "position": "C", "jersey_number": "13"},
        ]
    }


def report_dataset():
    return {
        "source": "WNBA Official Injury Report",
        "source_url": "https://ak-static.cms.nba.com/referee/wnba_injury/Injury-Report_2026-05-17_03_00PM.pdf",
        "report_timestamp_eastern": "2026-05-17T15:00:00-04:00",
        "retrieved_at_utc": "2026-05-17T19:01:00+00:00",
        "entries": [
            {
                "game_date": "2026-05-17",
                "game_time_eastern": "06:00",
                "matchup": "SEA@IND",
                "away_team_key": "seattle-storm",
                "home_team_key": "indiana-fever",
                "team_key": "seattle-storm",
                "team_full_name": "Seattle Storm",
                "player_name_report": "Magbegor, Ezi",
                "player_name_normalized": "ezimagbegor",
                "status": "Out",
                "reason": "Right Foot",
                "player_id": 4444,
                "roster_match": True,
            },
            {
                "game_date": "2026-05-17",
                "game_time_eastern": "06:00",
                "matchup": "SEA@IND",
                "away_team_key": "seattle-storm",
                "home_team_key": "indiana-fever",
                "team_key": "indiana-fever",
                "team_full_name": "Indiana Fever",
                "player_name_report": "Boston, Aliyah",
                "player_name_normalized": "aliyahboston",
                "status": "Questionable",
                "reason": "Right lower leg",
                "player_id": 1630163,
                "roster_match": True,
            },
        ],
        "team_submissions": [],
    }


def recent_stats():
    rows = []
    for pid, name, minutes in [
        (1642286, "Caitlin Clark", 35.0),
        (1629482, "Kelsey Mitchell", 34.0),
        (1630163, "Aliyah Boston", 32.0),
        (1111, "Lexie Hull", 29.0),
        (2222, "Natasha Howard", 28.0),
        (3333, "Bench Player", 12.0),
    ]:
        rows.append({
            "player_id": pid,
            "player_name": name,
            "stats": {"minutes": minutes, "points": 10.0, "rebounds": 5.0, "assists": 4.0},
        })
    return {"players": rows}


def lineups_dataset():
    return {
        "lineups": [
            {
                "group_id": "-1642286-1629482-1630163-1111-2222-",
                "player_ids": [1642286, 1629482, 1630163, 1111, 2222],
                "group_name": "Clark - Mitchell - Boston - Hull - Howard",
                "stats": {"minutes": 100.0},
            }
        ]
    }


def schedule_dataset(status="scheduled"):
    code = {"scheduled": 1, "live": 2, "final": 3}[status]
    return {
        "games": [
            {
                "game_id": "1022600100",
                "official_schedule_date": "2026-05-17",
                "status": {"code": code, "text": status.title(), "category": status},
                "away": {"team_key": "seattle-storm", "team_tricode": "SEA"},
                "home": {"team_key": "indiana-fever", "team_tricode": "IND"},
                "verification": {"teams_mapped_to_registry": True},
            }
        ]
    }


class WNBAAvailabilityTests(unittest.TestCase):
    def test_parse_official_report_rows_and_continuations(self):
        parsed = parse_injury_report_text(SAMPLE_TEXT, 2026)
        self.assertEqual(parsed["report_timestamp_eastern"], "2026-05-17T15:00:00-04:00")
        boston = next(row for row in parsed["entries"] if row["player_name_report"] == "Boston, Aliyah")
        self.assertEqual(boston["team_key"], "indiana-fever")
        self.assertEqual(boston["matchup"], "SEA@IND")
        self.assertEqual(boston["status"], "Questionable")
        self.assertIn("right lower leg", boston["reason"].lower())
        atkins = next(row for row in parsed["entries"] if row["player_name_report"] == "Atkins, Ariel")
        self.assertIn("Concussion Protocol", atkins["reason"])

    def test_parser_handles_portland_pdx_alias_and_submissions(self):
        parsed = parse_injury_report_text(SAMPLE_TEXT, 2026)
        pdx = [row for row in parsed["team_submissions"] if row["matchup"] == "CON@PDX"]
        self.assertEqual(len(pdx), 2)
        portland = next(row for row in pdx if row["team_full_name"] == "Portland Fire")
        self.assertEqual(portland["team_key"], "portland-fire")
        self.assertEqual(portland["home_team_key"], "portland-fire")

    def test_report_url_generation_uses_quarter_hour_filename(self):
        eastern = ZoneInfo("America/New_York")
        dt = datetime(2026, 7, 6, 13, 0, tzinfo=eastern)
        self.assertTrue(_report_url_for_datetime(dt).endswith("Injury-Report_2026-07-06_01_00PM.pdf"))

    def test_candidate_slots_descend_by_quarter_hour(self):
        eastern = ZoneInfo("America/New_York")
        slots = _candidate_report_datetimes(
            as_of_eastern=datetime(2026, 8, 26, 1, 22, tzinfo=eastern),
            lookback_hours=1,
        )
        self.assertEqual(slots[0].strftime("%H:%M"), "01:15")
        self.assertEqual(slots[1].strftime("%H:%M"), "01:00")
        self.assertEqual(slots[-1].strftime("%H:%M"), "00:15")

    @patch("sports_api.wnba_availability._probe_report_url")
    def test_discovery_selects_latest_existing_quarter_hour_report(self, mock_probe):
        eastern = ZoneInfo("America/New_York")
        as_of = datetime(2026, 8, 26, 1, 22, tzinfo=eastern)
        def side_effect(url):
            return url.endswith("Injury-Report_2026-08-26_01_00AM.pdf")
        mock_probe.side_effect = side_effect
        url, slot, cache_hit = discover_latest_injury_report_url(
            as_of_eastern=as_of,
            lookback_hours=1,
        )
        self.assertTrue(url.endswith("Injury-Report_2026-08-26_01_00AM.pdf"))
        self.assertIn("01:00:00", slot)
        self.assertFalse(cache_hit)

    def test_report_url_validation_rejects_nonofficial_host(self):
        with self.assertRaisesRegex(ValueError, "official WNBA"):
            _validate_report_url("https://example.com/report.pdf")

    def test_status_class_does_not_treat_probable_as_uncertain(self):
        meta = _status_class("Probable")
        self.assertEqual(meta["availability_class"], "probable")
        self.assertFalse(meta["availability_blocking"])
        self.assertFalse(meta["availability_uncertain"])

    @patch("sports_api.wnba_availability.get_current_players_dataset")
    @patch("sports_api.wnba_availability._extract_pdf_text")
    @patch("sports_api.wnba_availability._fetch_pdf_bytes")
    def test_latest_report_enriches_roster_player_ids(self, mock_fetch, mock_extract, mock_roster):
        mock_fetch.return_value = (b"%PDF fake", "2026-05-17T19:01:00+00:00", False)
        mock_extract.return_value = (SAMPLE_TEXT, 2)
        mock_roster.return_value = roster_dataset()
        url = "https://ak-static.cms.nba.com/referee/wnba_injury/Injury-Report_2026-05-17_03_00PM.pdf"
        dataset = get_latest_injury_report_dataset(2026, report_url=url)
        boston = next(row for row in dataset["entries"] if row["player_name_report"] == "Boston, Aliyah")
        self.assertEqual(boston["player_id"], 1630163)
        self.assertTrue(boston["roster_match"])
        self.assertEqual(dataset["page_count"], 2)

    @patch("sports_api.wnba_availability.get_lineups_dataset")
    @patch("sports_api.wnba_availability.get_player_season_stats_dataset")
    @patch("sports_api.wnba_availability.get_current_players_dataset")
    @patch("sports_api.wnba_availability.get_latest_injury_report_dataset")
    def test_team_context_ranks_observed_rotation_and_applies_injury(self, mock_report, mock_roster, mock_recent, mock_lineups):
        mock_report.return_value = report_dataset()
        mock_roster.return_value = roster_dataset()
        mock_recent.return_value = recent_stats()
        mock_lineups.return_value = lineups_dataset()
        dataset = get_team_availability_context_dataset("indiana-fever", 2026, last_n_games=5)
        players = dataset["team"]["players"]
        self.assertEqual(players[0]["player_name"], "Caitlin Clark")
        boston = next(row for row in players if row["player_id"] == 1630163)
        self.assertEqual(boston["injury_report_status"], "Questionable")
        self.assertTrue(boston["availability_uncertain"])
        self.assertTrue(boston["member_of_most_used_five_player_lineup"])
        self.assertFalse(dataset["team"]["starter_verification"]["official_starters_confirmed"])

    @patch("sports_api.wnba_availability.get_latest_injury_report_dataset")
    @patch("sports_api.wnba_availability.get_daily_schedule_dataset")
    @patch("sports_api.wnba_availability.get_lineups_dataset")
    @patch("sports_api.wnba_availability.get_player_season_stats_dataset")
    @patch("sports_api.wnba_availability.get_current_players_dataset")
    def test_game_context_pregame_never_claims_confirmed_starters(self, mock_roster, mock_recent, mock_lineups, mock_schedule, mock_report):
        mock_roster.return_value = roster_dataset()
        mock_recent.return_value = recent_stats()
        mock_lineups.return_value = lineups_dataset()
        mock_schedule.return_value = schedule_dataset("scheduled")
        mock_report.return_value = report_dataset()
        dataset = get_game_availability_context_dataset("1022600100", "2026-05-17", 2026)
        self.assertFalse(dataset["starting_lineups"]["official_starters_confirmed"])
        self.assertTrue(dataset["verification"]["no_projected_starters"])
        self.assertEqual(dataset["matchup"], "SEA@IND")

    @patch("sports_api.wnba_availability.get_game_box_score_dataset")
    @patch("sports_api.wnba_availability.get_latest_injury_report_dataset")
    @patch("sports_api.wnba_availability.get_daily_schedule_dataset")
    @patch("sports_api.wnba_availability.get_lineups_dataset")
    @patch("sports_api.wnba_availability.get_player_season_stats_dataset")
    @patch("sports_api.wnba_availability.get_current_players_dataset")
    def test_game_context_live_confirms_starters_from_box_score(self, mock_roster, mock_recent, mock_lineups, mock_schedule, mock_report, mock_box):
        mock_roster.return_value = roster_dataset()
        mock_recent.return_value = recent_stats()
        mock_lineups.return_value = lineups_dataset()
        mock_schedule.return_value = schedule_dataset("live")
        mock_report.return_value = report_dataset()
        starters_home = [{"player_id": i, "full_name": f"H{i}", "start_position": "G", "is_starter": True} for i in range(1, 6)]
        starters_away = [{"player_id": i + 10, "full_name": f"A{i}", "start_position": "F", "is_starter": True} for i in range(1, 6)]
        mock_box.return_value = {
            "source_endpoint": "boxscoretraditionalv3",
            "home": {"players": starters_home},
            "away": {"players": starters_away},
        }
        dataset = get_game_availability_context_dataset("1022600100", "2026-05-17", 2026)
        self.assertTrue(dataset["starting_lineups"]["official_starters_confirmed"])
        self.assertEqual(len(dataset["starting_lineups"]["home"]), 5)
        self.assertEqual(dataset["home"]["starter_verification"]["status"], "confirmed_from_official_box_score")

    @patch("sports_api.wnba_availability.get_daily_schedule_dataset")
    def test_unknown_game_raises_not_found(self, mock_schedule):
        mock_schedule.return_value = {"games": []}
        with self.assertRaises(WNBAAvailabilityNotFoundError):
            get_game_availability_context_dataset("1022600999", "2026-05-17", 2026)

    def test_invalid_rotation_window_fails(self):
        with self.assertRaisesRegex(ValueError, "1 through 20"):
            get_team_availability_context_dataset("indiana-fever", 2026, last_n_games=0)

    @patch("sports_api.wnba_availability.get_current_players_dataset")
    @patch("sports_api.wnba_availability._extract_pdf_text")
    @patch("sports_api.wnba_availability._fetch_pdf_bytes")
    def test_roster_enrichment_failure_keeps_report(self, mock_fetch, mock_extract, mock_roster):
        from sports_api.wnba_rosters import WNBAStatsUpstreamError
        mock_fetch.return_value = (b"%PDF fake", "2026-05-17T19:01:00+00:00", False)
        mock_extract.return_value = (SAMPLE_TEXT, 2)
        mock_roster.side_effect = WNBAStatsUpstreamError("roster down")
        url = "https://ak-static.cms.nba.com/referee/wnba_injury/Injury-Report_2026-05-17_03_00PM.pdf"
        dataset = get_latest_injury_report_dataset(2026, report_url=url)
        self.assertFalse(dataset["roster_enrichment"]["available"])
        self.assertEqual(dataset["entry_count"], 8)


if __name__ == "__main__":
    unittest.main()
