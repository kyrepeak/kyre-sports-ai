from __future__ import annotations

import unittest

import sports_api.wnba_availability as frozen
from sports_api.wnba_availability import WNBAAvailabilityUpstreamError
from sports_api.wnba_step7g_first_party_injury_report import (
    _parse_layout_report,
    _parse_team,
)


def _game(game_id: str, date: str, eastern: str) -> dict:
    return {
        "game_id": game_id,
        "official_schedule_date": date,
        "game_datetime_eastern": eastern,
        "away": {
            "team_key": "washington-mystics",
            "team_tricode": "WAS",
        },
        "home": {
            "team_key": "phoenix-mercury",
            "team_tricode": "PHX",
        },
    }


def _schedule(*games: dict) -> dict:
    return {"games": list(games)}


def _row(
    *,
    date: str = "",
    time: str = "",
    matchup: str = "",
    team: str = "",
    player: str = "",
    status: str = "",
    reason: str = "",
) -> str:
    return (
        f"{date:<25.25}"
        f"{time:<21.21}"
        f"{matchup:<17.17}"
        f"{team:<41.41}"
        f"{player:<42.42}"
        f"{status:<21.21}"
        f"{reason}"
    )


def _report(*rows: str) -> str:
    return "\n".join(("Injury Report: 08/27/26 06:45 PM", *rows))


class Step7GFirstPartyInjuryReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.target = _game(
            "1022600290",
            "2026-08-27",
            "2026-08-27T22:00:00-04:00",
        )

    def test_explicit_fixed_column_row_is_schedule_verified(self) -> None:
        parsed = _parse_layout_report(
            _report(
                _row(
                    date="08/27/2026",
                    time="10:00 (ET)",
                    matchup="WAS@PHX",
                    team="Phoenix Mercury",
                    player="Test Player",
                    status="Questionable",
                    reason="Ankle",
                )
            ),
            2026,
            _schedule(self.target),
        )
        self.assertEqual(parsed["entry_count"], 1)
        entry = parsed["entries"][0]
        self.assertEqual(entry["game_date"], "2026-08-27")
        self.assertEqual(entry["matchup"], "WAS@PHX")
        self.assertEqual(entry["team_key"], "phoenix-mercury")
        self.assertEqual(entry["status"], "Questionable")
        self.assertTrue(parsed["parser_diagnostics"]["all_entries_schedule_reconciled"])

    def test_blank_date_resolves_only_to_current_unique_schedule_game(self) -> None:
        old_game = _game(
            "1022600286",
            "2026-08-25",
            "2026-08-25T22:00:00-04:00",
        )
        parsed = _parse_layout_report(
            _report(
                _row(
                    time="10:00 (ET)",
                    matchup="WAS@PHX",
                    team="Phoenix Mercury",
                    player="Test Player",
                    status="Questionable",
                    reason="Ankle",
                )
            ),
            2026,
            _schedule(old_game, self.target),
        )
        self.assertEqual(parsed["entries"][0]["game_date"], "2026-08-27")
        self.assertEqual(parsed["parser_diagnostics"]["resolved_blank_date_count"], 1)

    def test_explicit_date_conflict_fails_closed(self) -> None:
        with self.assertRaises(WNBAAvailabilityUpstreamError):
            _parse_layout_report(
                _report(
                    _row(
                        date="08/28/2026",
                        time="10:00 (ET)",
                        matchup="WAS@PHX",
                        team="Phoenix Mercury",
                        player="Test Player",
                        status="Questionable",
                        reason="Ankle",
                    )
                ),
                2026,
                _schedule(self.target),
            )

    def test_ambiguous_blank_date_fails_closed(self) -> None:
        second = _game(
            "1022600999",
            "2026-08-28",
            "2026-08-28T22:00:00-04:00",
        )
        with self.assertRaises(WNBAAvailabilityUpstreamError):
            _parse_layout_report(
                _report(
                    _row(
                        time="10:00 (ET)",
                        matchup="WAS@PHX",
                        team="Phoenix Mercury",
                        player="Test Player",
                        status="Questionable",
                        reason="Ankle",
                    )
                ),
                2026,
                _schedule(self.target, second),
            )

    def test_multi_space_team_cell_collapses_before_registry_match(self) -> None:
        parsed = _parse_layout_report(
            _report(
                _row(
                    date="08/27/2026",
                    time="10:00 (ET)",
                    matchup="WAS@PHX",
                    team="Phoenix   Mercury",
                    player="Test Player",
                    status="Available",
                    reason="Return",
                )
            ),
            2026,
            _schedule(self.target),
        )
        self.assertEqual(parsed["entries"][0]["team_key"], "phoenix-mercury")

    def test_collapsed_internal_team_spacing_matches_one_official_registry_team(self) -> None:
        teams_by_name, _ = frozen._team_maps(2026)
        team = _parse_team("LasVegas Aces", teams_by_name)
        self.assertIsNotNone(team)
        self.assertEqual(team["team_key"], "las-vegas-aces")

    def test_unknown_normalized_team_cell_still_fails_closed(self) -> None:
        teams_by_name, _ = frozen._team_maps(2026)
        with self.assertRaises(WNBAAvailabilityUpstreamError):
            _parse_team("LasVegas Mystery", teams_by_name)

    def test_not_yet_submitted_team_only_row_uses_unique_schedule_identity(self) -> None:
        parsed = _parse_layout_report(
            _report(
                _row(
                    team="Phoenix Mercury",
                    reason="Not Yet Submitted",
                )
            ),
            2026,
            _schedule(self.target),
        )
        self.assertEqual(parsed["team_submission_count"], 1)
        submission = parsed["team_submissions"][0]
        self.assertEqual(submission["game_date"], "2026-08-27")
        self.assertEqual(submission["matchup"], "WAS@PHX")
        self.assertEqual(submission["team_key"], "phoenix-mercury")

    def test_ambiguous_not_yet_submitted_team_row_fails_closed(self) -> None:
        second = {
            "game_id": "1022600998",
            "official_schedule_date": "2026-08-28",
            "game_datetime_eastern": "2026-08-28T19:00:00-04:00",
            "away": {"team_key": "phoenix-mercury", "team_tricode": "PHX"},
            "home": {"team_key": "seattle-storm", "team_tricode": "SEA"},
        }
        with self.assertRaises(WNBAAvailabilityUpstreamError):
            _parse_layout_report(
                _report(_row(team="Phoenix Mercury", reason="Not Yet Submitted")),
                2026,
                _schedule(self.target, second),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
