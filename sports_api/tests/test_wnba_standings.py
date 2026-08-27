import unittest
from unittest.mock import patch

from sports_api.wnba_standings import (
    WNBAStandingsNotFoundError,
    WNBAStandingsUpstreamError,
    _standings_params,
    get_conference_standings_dataset,
    get_standings_dataset,
    get_team_standings_context_dataset,
)


TEAMS = [
    ("MIN", "Minnesota", "Lynx", "Western", 28, 7, .800),
    ("GSV", "Golden State", "Valkyries", "Western", 24, 9, .727),
    ("LVA", "Las Vegas", "Aces", "Western", 23, 11, .676),
    ("IND", "Indiana", "Fever", "Eastern", 21, 12, .636),
    ("ATL", "Atlanta", "Dream", "Eastern", 20, 12, .625),
    ("WAS", "Washington", "Mystics", "Eastern", 19, 13, .594),
    ("DAL", "Dallas", "Wings", "Western", 20, 14, .588),
    ("NYL", "New York", "Liberty", "Eastern", 20, 14, .588),
    ("POR", "Portland", "Fire", "Western", 13, 20, .394),
    ("LAS", "Los Angeles", "Sparks", "Western", 12, 20, .375),
    ("PHX", "Phoenix", "Mercury", "Western", 13, 22, .371),
    ("CHI", "Chicago", "Sky", "Eastern", 12, 22, .353),
    ("TOR", "Toronto", "Tempo", "Eastern", 10, 23, .303),
    ("CON", "Connecticut", "Sun", "Eastern", 8, 23, .258),
    ("SEA", "Seattle", "Storm", "Western", 7, 28, .200),
]


def _headers():
    return [
        "LeagueID", "SeasonID", "TeamID", "TeamCity", "TeamName", "TeamSlug",
        "Conference", "ConferenceRecord", "PlayoffRank", "ClinchIndicator",
        "Division", "DivisionRecord", "DivisionRank", "WINS", "LOSSES", "WinPCT",
        "LeagueRank", "Record", "HOME", "ROAD", "L10", "Last10Home", "Last10Road",
        "OT", "ThreePTSOrLess", "TenPTSOrMore", "CurrentHomeStreak",
        "strCurrentHomeStreak", "CurrentRoadStreak", "strCurrentRoadStreak",
        "CurrentStreak", "strCurrentStreak", "ConferenceGamesBack",
        "ClinchedConferenceTitle", "ClinchedDivisionTitle", "ClinchedPlayoffBirth",
        "EliminatedConference", "EliminatedDivision", "OppOver500", "PointsPG",
        "OppPointsPG", "DiffPointsPG", "vsEast", "vsWest", "May", "Jun", "Jul", "Aug", "Sep",
    ]


def _payload(*, duplicate_id=False, unmapped=False, wrong_league=False, no_ranks=False, cutoff_tie=False):
    rows = []
    for rank, (abbr, city, name, conf, wins, losses, pct) in enumerate(TEAMS, start=1):
        if cutoff_tie and rank == 9:
            wins, losses, pct = 20, 14, .588
        team_id = 1000 + rank
        if duplicate_id and rank == 2:
            team_id = 1001
        if unmapped and rank == 15:
            city, name = "Unknown", "Mystery"
        indicator = ""
        clinched = 1 if rank <= 3 else 0
        if rank == 15:
            indicator = "o"
        row = [
            "00" if wrong_league and rank == 1 else "10",
            "22026",
            team_id,
            city,
            name,
            f"{city.lower().replace(' ', '-')}-{name.lower()}",
            "East" if conf == "Eastern" else "West",
            "10-4",
            rank,
            indicator,
            "",
            "",
            0,
            wins,
            losses,
            pct,
            None if no_ranks else rank,
            f"{wins}-{losses}",
            "10-5",
            "9-6",
            "7-3",
            "5-2",
            "4-3",
            "1-0",
            "3-2",
            "8-4",
            2,
            "W2",
            -1,
            "L1",
            2,
            "W2",
            0.0,
            0,
            0,
            clinched,
            0,
            0,
            "8-5",
            82.1,
            78.8,
            3.3,
            "10-5",
            "8-4",
            "2-1",
            "5-2",
            "7-3",
            "4-2",
            "0-0",
        ]
        rows.append(row)
    return {"resultSets": [{"name": "Standings", "headers": _headers(), "rowSet": rows}]}


class WNBAStandingsTests(unittest.TestCase):
    def test_params_keep_league_id_first(self):
        params = _standings_params(2026, "Regular Season")
        self.assertEqual(params[0], ("LeagueID", "10"))
        self.assertEqual(params[1], ("Season", "2026"))

    @patch("sports_api.wnba_standings._request_stats_json")
    def test_standings_normalize_all_15_and_official_ranks(self, mock_request):
        mock_request.return_value = (_payload(), "2026-08-26T06:10:00+00:00", False)
        dataset = get_standings_dataset(2026)
        self.assertEqual(dataset["team_count"], 15)
        self.assertEqual(dataset["league_seed_source"], "official_LeagueRank")
        self.assertEqual(dataset["standings"][0]["team_key"], "minnesota-lynx")
        self.assertEqual(dataset["standings"][7]["team_key"], "new-york-liberty")
        self.assertEqual(dataset["standings"][7]["current_league_seed"], 8)

    @patch("sports_api.wnba_standings._request_stats_json")
    def test_conference_rank_and_registry_alignment(self, mock_request):
        mock_request.return_value = (_payload(), "2026-08-26T06:10:00+00:00", False)
        dataset = get_standings_dataset(2026)
        ind = next(t for t in dataset["standings"] if t["team_key"] == "indiana-fever")
        self.assertEqual(ind["conference"], "Eastern")
        self.assertEqual(ind["conference_rank"], 1)
        self.assertTrue(ind["conference_consistent"])

    @patch("sports_api.wnba_standings._request_stats_json")
    def test_playoff_cut_line_and_tied_win_pct(self, mock_request):
        mock_request.return_value = (_payload(cutoff_tie=True), "2026-08-26T06:10:00+00:00", False)
        dataset = get_standings_dataset(2026)
        eighth = dataset["standings"][7]
        ninth = dataset["standings"][8]
        self.assertTrue(eighth["playoff_context"]["currently_in_playoff_field"])
        self.assertFalse(ninth["playoff_context"]["currently_in_playoff_field"])
        self.assertTrue(eighth["playoff_context"]["cutoff_tied_on_win_percentage"])
        self.assertTrue(ninth["playoff_context"]["cutoff_tied_on_win_percentage"])
        self.assertEqual(ninth["playoff_context"]["games_behind_eighth_seed"], 0.0)
        self.assertEqual(dataset["playoff_cut_line"]["eighth_seed"]["team_key"], "new-york-liberty")

    @patch("sports_api.wnba_standings._request_stats_json")
    def test_clinched_and_eliminated_official_status(self, mock_request):
        mock_request.return_value = (_payload(), "2026-08-26T06:10:00+00:00", False)
        dataset = get_standings_dataset(2026)
        self.assertEqual(dataset["standings"][0]["playoff_context"]["current_status"], "clinched_playoff_berth")
        self.assertEqual(dataset["standings"][-1]["playoff_context"]["current_status"], "eliminated_from_playoff_contention")

    @patch("sports_api.wnba_standings._request_stats_json")
    def test_games_remaining_uses_44_game_schedule(self, mock_request):
        mock_request.return_value = (_payload(), "2026-08-26T06:10:00+00:00", False)
        dataset = get_standings_dataset(2026)
        min_row = dataset["standings"][0]
        self.assertEqual(min_row["games_played"], 35)
        self.assertEqual(min_row["games_remaining"], 9)
        self.assertEqual(min_row["max_possible_wins"], 37)

    @patch("sports_api.wnba_standings._request_stats_json")
    def test_conference_endpoint_returns_7_east_8_west(self, mock_request):
        mock_request.return_value = (_payload(), "2026-08-26T06:10:00+00:00", False)
        east = get_conference_standings_dataset("East", 2026)
        west = get_conference_standings_dataset("Western", 2026)
        self.assertEqual(east["team_count"], 7)
        self.assertEqual(west["team_count"], 8)

    @patch("sports_api.wnba_standings._request_stats_json")
    def test_team_context_has_adjacent_seeds(self, mock_request):
        mock_request.return_value = (_payload(), "2026-08-26T06:10:00+00:00", False)
        ctx = get_team_standings_context_dataset("new-york-liberty", 2026)
        self.assertEqual(ctx["team"]["current_league_seed"], 8)
        self.assertEqual(ctx["adjacent_seeds"]["one_seed_above"]["team_key"], "dallas-wings")
        self.assertEqual(ctx["adjacent_seeds"]["one_seed_below"]["team_key"], "portland-fire")

    def test_invalid_season_type_fails_before_network(self):
        with patch("sports_api.wnba_standings._request_stats_json") as mock_request:
            with self.assertRaisesRegex(ValueError, "season_type"):
                get_standings_dataset(2026, season_type="Playoffs")
            mock_request.assert_not_called()

    @patch("sports_api.wnba_standings._request_stats_json")
    def test_wrong_league_fails_closed(self, mock_request):
        mock_request.return_value = (_payload(wrong_league=True), "x", False)
        with self.assertRaisesRegex(WNBAStandingsUpstreamError, "unexpected LeagueID"):
            get_standings_dataset(2026)

    @patch("sports_api.wnba_standings._request_stats_json")
    def test_unmapped_team_fails_closed(self, mock_request):
        mock_request.return_value = (_payload(unmapped=True), "x", False)
        with self.assertRaisesRegex(WNBAStandingsUpstreamError, "unmapped team"):
            get_standings_dataset(2026)

    @patch("sports_api.wnba_standings._request_stats_json")
    def test_duplicate_team_id_fails_closed(self, mock_request):
        mock_request.return_value = (_payload(duplicate_id=True), "x", False)
        with self.assertRaisesRegex(WNBAStandingsUpstreamError, "duplicate team IDs"):
            get_standings_dataset(2026)

    @patch("sports_api.wnba_standings._request_stats_json")
    def test_missing_official_ranks_uses_explicit_fallback(self, mock_request):
        mock_request.return_value = (_payload(no_ranks=True), "x", False)
        dataset = get_standings_dataset(2026)
        self.assertEqual(dataset["league_seed_source"], "derived_win_pct_order_tiebreak_not_resolved")
        self.assertTrue(dataset["verification"]["playoff_context_is_descriptive_not_predictive"])

    @patch("sports_api.wnba_standings._request_stats_json")
    def test_missing_required_schema_fails_closed(self, mock_request):
        payload = _payload()
        payload["resultSets"][0]["headers"][0] = "WRONG"
        mock_request.return_value = (payload, "x", False)
        with self.assertRaisesRegex(WNBAStandingsUpstreamError, "missing required"):
            get_standings_dataset(2026)

    def test_unknown_team_fails_before_network(self):
        with patch("sports_api.wnba_standings._request_stats_json") as mock_request:
            with self.assertRaises(WNBAStandingsNotFoundError):
                get_team_standings_context_dataset("not-a-team", 2026)
            mock_request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
