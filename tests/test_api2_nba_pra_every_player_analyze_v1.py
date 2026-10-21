from __future__ import annotations

from types import SimpleNamespace

import nba_pra_page1_v2 as page


class FakeStreamlit:
    def __init__(self, clicked_key: str | None = None) -> None:
        self.clicked_key = clicked_key
        self.events: list[tuple] = []
        self.session_state: dict[str, object] = {}
        self.rerun_count = 0

    def markdown(self, body: str, *, unsafe_allow_html: bool = False) -> None:
        self.events.append(("card", body, unsafe_allow_html))

    def button(self, label: str, *, key: str, use_container_width: bool = False) -> bool:
        self.events.append(("button", label, key, use_container_width))
        return key == self.clicked_key

    def rerun(self) -> None:
        self.rerun_count += 1


def _player(key: str, name: str) -> dict[str, object]:
    return {
        "key": key,
        "player_name": name,
        "team": "TST",
        "position": "G",
        "featured_quote": {"line": 20.5, "book": "FanDuel", "observed_at_utc": "2026-10-21T21:00:00Z"},
        "model": {"projection": 24.0},
        "grade": {"lean": "OVER", "edge": 3.5, "over_probability": 0.64, "confidence": "HIGH", "score": 8.0, "tier": "STRONG"},
    }


def test_every_visible_player_card_gets_one_adjacent_analyze_action(monkeypatch) -> None:
    items = [_player("first", "First Player"), _player("middle", "Middle Player"), _player("last", "Last Player")]
    st = FakeStreamlit(clicked_key="np3-all-middle")
    opened: list[str] = []

    monkeypatch.setattr(page, "build_market_row_html", lambda item, now_utc=None: f"CARD:{item['key']}")
    monkeypatch.setattr(page, "_open_player", lambda _st, item: opened.append(str(item["key"])))

    page.render_market_player_cards(st, items, now_utc=None)

    assert st.events == [
        ("card", "CARD:first", True),
        ("button", "ANALYZE FIRST PLAYER →", "np3-all-first", False),
        ("card", "CARD:middle", True),
        ("button", "ANALYZE MIDDLE PLAYER →", "np3-all-middle", False),
        ("card", "CARD:last", True),
        ("button", "ANALYZE LAST PLAYER →", "np3-all-last", False),
    ]
    assert opened == ["middle"]


def test_first_middle_and_last_player_can_each_open_page2(monkeypatch) -> None:
    items = [_player("first", "First Player"), _player("middle", "Middle Player"), _player("last", "Last Player")]
    monkeypatch.setattr(page, "build_market_row_html", lambda item, now_utc=None: f"CARD:{item['key']}")

    for clicked in ("first", "middle", "last"):
        st = FakeStreamlit(clicked_key=f"np3-all-{clicked}")
        opened: list[str] = []
        monkeypatch.setattr(page, "_open_player", lambda _st, item, opened=opened: opened.append(str(item["key"])))
        page.render_market_player_cards(st, items, now_utc=None)
        assert opened == [clicked]
