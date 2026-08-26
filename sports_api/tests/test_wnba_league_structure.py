import unittest

from sports_api.wnba_league import (
    ALLOWED_CONFERENCES,
    get_wnba_league_structure,
    get_wnba_teams,
    validate_wnba_registry,
)


class WNBALeagueStructureTests(unittest.TestCase):
    def test_registry_validation_passes(self):
        validate_wnba_registry()

    def test_2026_has_15_unique_teams(self):
        teams = get_wnba_teams(2026)
        self.assertEqual(len(teams), 15)

        for field in ("team_key", "slug", "abbreviation", "full_name"):
            values = [team[field].casefold() for team in teams]
            self.assertEqual(len(values), len(set(values)), field)

    def test_2026_conference_alignment(self):
        league = get_wnba_league_structure(2026)
        counts = {
            conference["name"]: conference["team_count"]
            for conference in league["conferences"]
        }
        self.assertEqual(counts, {"Eastern": 7, "Western": 8})

        teams = get_wnba_teams(2026)
        by_name = {team["full_name"]: team for team in teams}
        self.assertEqual(by_name["Toronto Tempo"]["conference"], "Eastern")
        self.assertEqual(by_name["Portland Fire"]["conference"], "Western")

        self.assertTrue(
            all(team["conference"] in ALLOWED_CONFERENCES for team in teams)
        )

    def test_defensive_copy_prevents_registry_mutation(self):
        first = get_wnba_teams(2026)
        first[0]["full_name"] = "Mutated Team"
        second = get_wnba_teams(2026)
        self.assertEqual(second[0]["full_name"], "Atlanta Dream")

    def test_unsupported_seasons_fail_closed(self):
        for season in (2025, 2027):
            with self.subTest(season=season):
                with self.assertRaises(ValueError):
                    get_wnba_teams(season)


if __name__ == "__main__":
    unittest.main()
