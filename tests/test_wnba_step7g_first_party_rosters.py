from __future__ import annotations

import unittest

from sports_api.wnba_step7g_first_party_rosters import (
    _parse_card_text,
    _parse_roster_html,
    _player_id_from_href,
)


class Step7GFirstPartyRosterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.team = {
            "team_key": "washington-mystics",
            "full_name": "Washington Mystics",
            "official_team_id": 1611661322,
            "city": "Washington",
            "nickname": "Mystics",
            "abbreviation": "WAS",
            "slug": "mystics",
        }

    def test_accepts_only_official_wnba_player_links(self) -> None:
        self.assertEqual(_player_id_from_href("https://www.wnba.com/player/1642785"), 1642785)
        self.assertEqual(_player_id_from_href("/player/1642785"), 1642785)
        self.assertIsNone(_player_id_from_href("https://example.com/player/1642785"))
        self.assertIsNone(_player_id_from_href("/players/1642785"))

    def test_card_text_preserves_name_jersey_and_position(self) -> None:
        jersey, name, position = _parse_card_text(
            "#22 Sonia Citron Guard PPG 16.9 RPG 3.7 APG 4.3"
        )
        self.assertEqual(jersey, "22")
        self.assertEqual(name, "Sonia Citron")
        self.assertEqual(position, "Guard")

    def test_parser_uses_player_ids_and_does_not_require_unique_jerseys(self) -> None:
        cards = "".join(
            f'<a href="https://www.wnba.com/player/{1000 + index}">'
            f'#{44 if index in (0, 1) else index} Player {index} Guard PPG 1.0 RPG 1.0 APG 1.0</a>'
            for index in range(7)
        )
        html = f"<h3>2026 Team Roster</h3>{cards}<h2>Coaching Staff</h2>"
        players = _parse_roster_html(
            html,
            team=self.team,
            source_url="https://mystics.wnba.com/roster",
        )
        self.assertEqual(len(players), 7)
        self.assertEqual(len({row["player_id"] for row in players}), 7)
        self.assertEqual(players[0]["team_key"], "washington-mystics")
        self.assertTrue(all(row["is_current_roster"] for row in players))

    def test_parser_fails_closed_without_roster_boundary(self) -> None:
        html = '<a href="https://www.wnba.com/player/1642785">#22 Sonia Citron Guard PPG 1</a>'
        with self.assertRaises(Exception):
            _parse_roster_html(
                html,
                team=self.team,
                source_url="https://mystics.wnba.com/roster",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
