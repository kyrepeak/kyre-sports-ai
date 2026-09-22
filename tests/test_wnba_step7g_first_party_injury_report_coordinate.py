from __future__ import annotations

import unittest
from unittest.mock import patch

from sports_api.wnba_availability import WNBAAvailabilityUpstreamError
import sports_api.wnba_step7g_first_party_injury_report_coordinate as coordinate


def _game() -> dict:
    return {
        "game_id": "1022600290",
        "official_schedule_date": "2026-08-27",
        "game_datetime_eastern": "2026-08-27T22:00:00-04:00",
        "away": {"team_key": "washington-mystics", "team_tricode": "WAS"},
        "home": {"team_key": "phoenix-mercury", "team_tricode": "PHX"},
    }


def _fragment(x: float, text: str) -> dict:
    return {"x": x, "y": 0.0, "text": text}


def _row(page: int, y: float, *items: tuple[float, str]) -> dict:
    return {
        "page_number": page,
        "y": y,
        "fragments": [
            {"x": x, "y": y, "text": text}
            for x, text in items
        ],
    }


def _geometry(pages: list[int]) -> dict:
    return {
        "page_count": max(pages),
        "header_geometry_verified": True,
        "pages_with_status_rows": pages,
        "coordinate_bands": coordinate.COLUMN_BANDS,
    }


class Step7GCoordinateInjuryReportTests(unittest.TestCase):
    def _parse(self, rows: list[dict]) -> dict:
        pages = sorted({int(row["page_number"]) for row in rows})
        with patch.object(
            coordinate,
            "_extract_layout_pdf_text",
            return_value=("Injury Report: 08/27/26 08:45 PM", max(pages)),
        ), patch.object(
            coordinate,
            "_extract_coordinate_rows",
            return_value=(rows, _geometry(pages)),
        ):
            return coordinate._parse_coordinate_report(b"pdf", 2026, {"games": [_game()]})

    def test_physical_x_bands_reconstruct_explicit_player_row(self) -> None:
        parsed = self._parse(
            [
                _row(
                    1,
                    148.3,
                    (24.15, "08/27/2026"),
                    (120.59, "10:00"),
                    (145.80, "(ET)"),
                    (200.95, "WAS@PHX"),
                    (265.24, "Phoenix"),
                    (300.05, "Mercury"),
                    (425.98, "Example,"),
                    (465.00, "Player"),
                    (586.71, "Questionable"),
                    (667.07, "Injury/Illness"),
                    (721.79, "-"),
                    (727.11, "Ankle"),
                )
            ]
        )
        self.assertEqual(parsed["entry_count"], 1)
        entry = parsed["entries"][0]
        self.assertEqual(entry["game_date"], "2026-08-27")
        self.assertEqual(entry["matchup"], "WAS@PHX")
        self.assertEqual(entry["team_key"], "phoenix-mercury")
        self.assertEqual(entry["status"], "Questionable")
        self.assertIn("Ankle", entry["reason"])

    def test_wrapped_reason_attaches_only_to_nearby_player_anchor(self) -> None:
        parsed = self._parse(
            [
                _row(
                    1,
                    148.3,
                    (24.15, "08/27/2026"),
                    (120.59, "10:00"),
                    (145.80, "(ET)"),
                    (200.95, "WAS@PHX"),
                    (265.24, "Phoenix"),
                    (300.05, "Mercury"),
                    (425.98, "Example,"),
                    (465.00, "Player"),
                    (586.71, "Out"),
                ),
                _row(1, 141.3, (667.07, "Coach's"), (700.33, "Decision"), (736.97, "-")),
                _row(1, 155.3, (667.07, "Developmental"), (730.00, "Player")),
            ]
        )
        self.assertEqual(parsed["entry_count"], 1)
        reason = parsed["entries"][0]["reason"]
        self.assertEqual(reason, "Coach's Decision - Developmental Player")

    def test_page_break_player_row_carries_only_prior_resolved_game_and_team(self) -> None:
        parsed = self._parse(
            [
                _row(
                    1,
                    490.9,
                    (24.15, "08/27/2026"),
                    (120.59, "10:00"),
                    (145.80, "(ET)"),
                    (200.95, "WAS@PHX"),
                    (265.24, "Phoenix"),
                    (300.05, "Mercury"),
                    (425.98, "First,"),
                    (460.00, "Player"),
                    (586.71, "Out"),
                    (667.07, "Injury/Illness"),
                ),
                _row(
                    2,
                    101.9,
                    (425.98, "Second,"),
                    (465.00, "Player"),
                    (586.71, "Out"),
                ),
                _row(2, 94.9, (667.07, "Injury/Illness"), (727.11, "Knee")),
                _row(2, 109.0, (667.07, "Not"), (687.00, "With"), (710.00, "Team")),
            ]
        )
        self.assertEqual(parsed["entry_count"], 2)
        self.assertEqual(parsed["entries"][1]["team_key"], "phoenix-mercury")
        self.assertEqual(parsed["entries"][1]["matchup"], "WAS@PHX")
        self.assertEqual(parsed["parser_diagnostics"]["page_break_carry_count"], 1)
        self.assertIn("Not With Team", parsed["entries"][1]["reason"])

    def test_page_break_without_prior_identity_fails_closed(self) -> None:
        with self.assertRaises(WNBAAvailabilityUpstreamError):
            self._parse(
                [
                    _row(
                        2,
                        101.9,
                        (425.98, "Orphan,"),
                        (465.00, "Player"),
                        (586.71, "Out"),
                        (667.07, "Injury/Illness"),
                    )
                ]
            )

    def test_not_yet_submitted_uses_printed_matchup_and_team(self) -> None:
        parsed = self._parse(
            [
                _row(
                    1,
                    221.2,
                    (200.95, "WAS@PHX"),
                    (265.24, "Washington"),
                    (316.49, "Mystics"),
                    (667.07, "NOT"),
                    (687.28, "YET"),
                    (704.17, "SUBMITTED"),
                )
            ]
        )
        self.assertEqual(parsed["team_submission_count"], 1)
        submission = parsed["team_submissions"][0]
        self.assertEqual(submission["team_key"], "washington-mystics")
        self.assertEqual(submission["matchup"], "WAS@PHX")

    def test_orphan_reason_text_fails_closed(self) -> None:
        with self.assertRaises(WNBAAvailabilityUpstreamError):
            self._parse([_row(1, 300.0, (667.07, "Unattributed injury text"))])

    def test_player_without_recognized_status_fails_closed(self) -> None:
        with self.assertRaises(WNBAAvailabilityUpstreamError):
            self._parse(
                [
                    _row(
                        1,
                        148.3,
                        (24.15, "08/27/2026"),
                        (120.59, "10:00"),
                        (145.80, "(ET)"),
                        (200.95, "WAS@PHX"),
                        (265.24, "Phoenix"),
                        (300.05, "Mercury"),
                        (425.98, "Unknown,"),
                        (465.00, "Player"),
                        (586.71, "Mystery"),
                    )
                ]
            )

    def test_hyphenated_player_name_does_not_gain_space(self) -> None:
        value = coordinate._join_tokens(["Nelson-", "Ododa,", "Olivia"])
        self.assertEqual(value, "Nelson-Ododa, Olivia")


if __name__ == "__main__":
    unittest.main(verbosity=2)
