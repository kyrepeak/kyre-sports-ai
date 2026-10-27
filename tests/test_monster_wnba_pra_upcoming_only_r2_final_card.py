from __future__ import annotations

from pathlib import Path

import wnba_pra_page1_ultra_stier_v3 as page

ROOT = Path(__file__).resolve().parents[1]


def _row(player: str = "Allisha Gray", line: float = 20.5) -> dict:
    return {
        "player_name": player,
        "line": line,
        "lean": "OVER",
        "model_probability": 0.61,
        "projection_pra": 23.0,
        "model_edge": 0.08,
        "sportsbook": "FanDuel",
        "over_odds": -110,
    }


def test_stale_final_card_cannot_survive_when_upcoming_gate_removed_its_row() -> None:
    stale = [{"player_name": "Allisha Gray", "line": 20.5, "side": "OVER"}]
    assert page._eligible_final_cards(stale, []) == []
    assert page._final_section_html(stale, []) == ""


def test_final_card_still_renders_for_exact_current_eligible_player_and_line() -> None:
    rows = [_row()]
    finals = [{"player_name": "Allisha Gray", "line": 20.5, "side": "OVER"}]
    eligible = page._eligible_final_cards(finals, rows)
    html = page._final_section_html(finals, rows)
    assert eligible == finals
    assert "CERTIFIED PRA PICK" in html
    assert "Allisha Gray" in html


def test_wrong_line_is_treated_as_stale_and_hidden() -> None:
    rows = [_row(line=20.5)]
    finals = [{"player_name": "Allisha Gray", "line": 21.5, "side": "OVER"}]
    assert page._eligible_final_cards(finals, rows) == []
    assert page._final_section_html(finals, rows) == ""


def test_frozen_compatibility_hub_uses_v3_successor_after_upcoming_gate() -> None:
    source = (ROOT / "wnba_pra_hub_v3612.py").read_text(encoding="utf-8")
    assert "wnba_pra_api_market_bridge_upcoming_only_r1 as _upcoming_only" in source
    assert "wnba_pra_page1_ultra_stier_v3 as _page1_ultra_stier_v3" in source
    assert source.index("_upcoming_only.install()") < source.index("wnba_pra_page1_ultra_stier_v3")
    assert "_page1_ultra_stier_v3.render_page_snapshot" in source
