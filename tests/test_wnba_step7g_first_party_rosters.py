from __future__ import annotations

import unittest

from sports_api.wnba_step7g_first_party_rosters import (
    _parse_card_text,
    _parse_roster_html,
    _plain_name_candidate,
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

    def test_plain_name_candidate_accepts_name_only_anchor(self) -> None:
        self.assertEqual(_plain_name_candidate("Sonia Citron"), "Sonia Citron")
        self.assertEqual(_plain_name_candidate("A'ja Wilson"), "A'ja Wilson")
        self.assertIsNone(_plain_name_candidate("View Profile"))
        self.assertIsNone(_plain_name_candidate("PPG 16.9"))
        self.assertIsNone(_plain_name_candidate("Sonia Citron headshot"))

    def test_parser_pairs_ordered_ids_with_sibling_visible_cards(self) -> None:
        cards = []
        for index in range(7):
            player_id = 1000 + index
            name = f"Player Name {chr(65 + index)}"
            # The canonical player link contains only an image; the actual roster
            # card text is a sibling. This mirrors the live team-page structure.
            cards.append(
                f'<div><a href="https://www.wnba.com/player/{player_id}">'
                f'<img alt="{name} headshot" src="headshot.png"></a>'
                f'<span>#{44 if index in (0, 1) else index} {name} Guard '</n                f'PPG 1.0 RPG 1.0 APG 1.0</span></div>'
            )
            # Duplicate presentation link to the same player must collapse by ID.
            cards.append(
                f'<a href="https://www.wnba.com/player/{player_id}">Show more</a>'
            )
        html = (
            '<a href="https://www.wnba.com/player/999999">Old News Player</a>'
            '<h3>2026 Team Roster</h3>'
            + "".join(cards)
            + '<h2>Coaching Staff</h2>'
            + '<a href="https://www.wnba.com/player/888888">Another News Player</a>'
        )
        players = _parse_roster_html(
            html,
            team=self.team,
            source_url="https://mystics.wnba.com/roster",
        )
        self.assertEqual(len(players), 7)
        self.assertEqual(len({row["player_id"] for row in players}), 7)
        self.assertNotIn(999999, {row["player_id"] for row in players})
        self.assertNotIn(888888, {row["player_id"] for row in players})
        self.assertEqual(players[0]["full_name"], "Player Name A")
        self.assertEqual(players[0]["team_key"], "washington-mystics")
        self.assertTrue(all(row["is_current_roster"] for row in players))

    def test_parser_fails_closed_when_id_and_visible_card_counts_disagree(self) -> None:
        html = (
            '<h3>2026 Team Roster</h3>'
            '<a href="https://www.wnba.com/player/1001"></a>'
            '<a href="https://www.wnba.com/player/1002"></a>'
            '<a href="https://www.wnba.com/player/1003"></a>'
            '<a href="https://www.wnba.com/player/1004"></a>'
            '<a href="https://www.wnba.com/player/1005"></a>'
            '<a href="https://www.wnba.com/player/1006"></a>'
            '<a href="https://www.wnba.com/player/1007"></a>'
            '<span>#1 Only One Card Guard PPG 1.0 RPG 1.0 APG 1.0</span>'
            '<h2>Coaching Staff</h2>'
        )
        with self.assertRaises(Exception):
            _parse_roster_html(
                html,
                team=self.team,
                source_url="https://mystics.wnba.com/roster",
            )

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
