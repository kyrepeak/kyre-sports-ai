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

    def _fixture(
        self,
        *,
        count: int = 7,
        wrong_name_id: int | None = None,
        wrong_team_id: int | None = None,
        include_flight: bool = True,
    ) -> str:
        tiles: list[str] = []
        flight: list[str] = []
        for index in range(count):
            player_id = 1000 + index
            name = f"Player Name {chr(65 + index)}"
            number = str(index + 1)
            tiles.append(
                f'<li class="TeamRoster_playerTile__ep6JE">'
                f'<a href="https://www.wnba.com/player/{player_id}">'
                f'<span class="_PlayerTile__number__digit_x">{number}</span>'
                f'<img src="https://cdn.wnba.com/headshots/wnba/latest/260x190/{player_id}.png" '
                f'alt="{name} headshot"/>'
                f'<h3 class="_PlayerTile__player__name_x">{name}</h3>'
                f'<p class="_PlayerTile__player__subtitle_x"><span>Guard</span><span></span></p>'
                f'</a></li>'
            )
            flight_name = "Wrong Player" if wrong_name_id == player_id else name
            team_id = wrong_team_id if wrong_team_id is not None and index == 0 else 1611661322
            flight.append(
                '{'
                f'"playerId":{player_id},'
                f'"playerName":"{flight_name}",'
                f'"playerNumber":"{number}",'
                '"position":"Guard",'
                f'"teamId":"{team_id}",'
                f'"playerLink":"https://www.wnba.com/player/{player_id}"'
                '}'
            )
        script = f'<script>{"".join(flight)}</script>' if include_flight else ""
        return (
            '<h2>2026 Team Roster</h2>'
            + "".join(tiles)
            + '<h2>Coaching Staff</h2>'
            + script
        )

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
        self.assertIsNone(_plain_name_candidate("Sonia Citron headshot"))

    def test_parser_cross_checks_rendered_tiles_and_react_identity(self) -> None:
        players = _parse_roster_html(
            self._fixture(),
            team=self.team,
            source_url="https://mystics.wnba.com/roster",
        )
        self.assertEqual(len(players), 7)
        self.assertEqual(len({row["player_id"] for row in players}), 7)
        by_id = {row["player_id"]: row for row in players}
        self.assertEqual(by_id[1000]["full_name"], "Player Name A")
        self.assertEqual(by_id[1000]["jersey_number"], "1")
        self.assertEqual(by_id[1000]["position"], "Guard")
        self.assertEqual(by_id[1000]["team_key"], "washington-mystics")
        self.assertTrue(all(row["is_current_roster"] for row in players))

    def test_parser_preserves_react_team_id_without_static_registry_id(self) -> None:
        team = dict(self.team)
        team.pop("official_team_id", None)
        players = _parse_roster_html(
            self._fixture(),
            team=team,
            source_url="https://mystics.wnba.com/roster",
        )
        self.assertEqual({row["official_team_id"] for row in players}, {1611661322})

    def test_parser_fails_closed_on_tile_react_name_mismatch(self) -> None:
        with self.assertRaises(Exception):
            _parse_roster_html(
                self._fixture(wrong_name_id=1002),
                team=self.team,
                source_url="https://mystics.wnba.com/roster",
            )

    def test_parser_fails_closed_on_wrong_react_team_id(self) -> None:
        with self.assertRaises(Exception):
            _parse_roster_html(
                self._fixture(wrong_team_id=999),
                team=self.team,
                source_url="https://mystics.wnba.com/roster",
            )

    def test_parser_fails_closed_without_react_identity_surface(self) -> None:
        with self.assertRaises(Exception):
            _parse_roster_html(
                self._fixture(include_flight=False),
                team=self.team,
                source_url="https://mystics.wnba.com/roster",
            )

    def test_parser_fails_closed_without_roster_markers(self) -> None:
        html = self._fixture().replace("2026 Team Roster", "Players").replace("Coaching Staff", "Staff")
        with self.assertRaises(Exception):
            _parse_roster_html(
                html,
                team=self.team,
                source_url="https://mystics.wnba.com/roster",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
