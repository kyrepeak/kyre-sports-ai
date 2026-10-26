from __future__ import annotations

import importlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SUCCESSOR = ROOT / "wnba_pra_page1_ultra_stier_v2.py"


def _load_page():
    assert SUCCESSOR.exists(), "WNBA PRA Page 1 ultra S-tier V2 successor is missing"
    return importlib.import_module("wnba_pra_page1_ultra_stier_v2")


def _row(**overrides):
    row = {
        "player_name": "Gabby Williams",
        "sportsbook": "DraftKings",
        "line": 26.5,
        "line_open": 27.5,
        "line_move": -1.0,
        "team": "GSV",
        "opponent": "ATL",
        "model_state": "LINE_BOUND_READY",
        "p_over": 0.116,
        "p_under": 0.884,
        "model_probability": 0.884,
        "edge": -0.365,
        "model_edge": -0.365,
        "projection_pra": 18.6,
        "over_odds": -107,
        "under_odds": -127,
        "lean": "UNDER",
    }
    row.update(overrides)
    return row


def test_compat_installs_v2_after_preserved_v1_contract_and_before_refresh_handoff():
    compat = (ROOT / "wnba_pra_hub_v3612.py").read_text(encoding="utf-8")
    preserved = "active.render_page_snapshot = _page1_final_polish.render_page_snapshot"
    install = "active.render_page_snapshot = _page1_ultra_stier_v2.render_page_snapshot"
    refresh = "import wnba_pra_hub_v3618 as refresh_handoff"
    assert preserved in compat
    assert "import wnba_pra_page1_ultra_stier_v2 as _page1_ultra_stier_v2" in compat
    assert install in compat
    assert compat.index(preserved) < compat.index(install) < compat.index(refresh)


def test_player_card_is_decision_first_and_hides_internal_model_plumbing():
    page = _load_page()
    html = page._player_card_html(_row())
    for token in (
        "Gabby Williams",
        "GSV vs ATL",
        "UNDER 26.5 PRA",
        "88.4%",
        "18.6",
        "36.5%",
        "DraftKings",
        "-127",
        "27.5 → 26.5",
        "Analyze Player",
    ):
        assert token in html
    for forbidden in ("LINE_BOUND_READY", "LINE BOUND", "MODEL STATE", "Model State", "Confidence"):
        assert forbidden not in html
    for absent_optional in (">L5<", ">L10<", ">Season<"):
        assert absent_optional not in html


def test_verified_trends_render_compactly_but_missing_trends_disappear():
    page = _load_page()
    blank = page._trend_strip_html(_row())
    assert blank == ""
    verified = page._trend_strip_html(_row(l5_hit_rate=0.8, l10_hit_rate=0.7, season_hit_rate=0.64))
    for token in ("L5", "80%", "L10", "70%", "Season", "64%"):
        assert token in verified


def test_top_three_is_one_compact_leaderboard_not_three_oversized_cards():
    page = _load_page()
    rows = [
        _row(),
        _row(player_name="Veronica Burton", line=18.5, projection_pra=15.3, model_probability=0.712, model_edge=-0.185, edge=-0.185, under_odds=-131, line_open=19.5),
        _row(player_name="Rhyne Howard", team="ATL", opponent="GSV", line=22.5, projection_pra=20.0, model_probability=0.618, model_edge=-0.119, edge=-0.119, under_odds=-116, line_open=24.5),
    ]
    html = page._leaderboard_html(rows)
    assert html.count('class="p1v2-leaderboard"') == 1
    assert html.count('class="p1v2-leader-row"') == 3
    for token in ("#1", "Gabby Williams", "#2", "Veronica Burton", "#3", "Rhyne Howard", "36.5%", "88.4%"):
        assert token in html
    assert "p1-topcard" not in html


def test_summary_is_compact_and_surfaces_best_probability_and_market_movement():
    page = _load_page()
    rows = [
        _row(),
        _row(player_name="Veronica Burton", line=18.5, projection_pra=15.3, model_probability=0.712, model_edge=-0.185, edge=-0.185, line_open=18.5, line_move=0.0),
        _row(player_name="Rhyne Howard", team="ATL", opponent="GSV", line=22.5, projection_pra=20.0, model_probability=0.618, model_edge=-0.119, edge=-0.119, line_open=21.5, line_move=1.0),
    ]
    html = page._summary_html(rows, provider="DraftKings")
    for token in ("3", "3/3", "36.5%", "88.4%", "Market Movement", "↑ 1", "↓ 1", "— 1", "DraftKings"):
        assert token in html


def test_empty_final_pick_section_is_fully_collapsed_until_certified():
    page = _load_page()
    rows = [_row()]
    assert page._final_section_html([], rows) == ""
    html = page._final_section_html([{"player_name": "Gabby Williams", "line": 26.5, "side": "under"}], rows)
    for token in ("CERTIFIED PRA PICK", "Gabby Williams", "UNDER 26.5 PRA", "88.4%", "36.5%", "DraftKings", "-127"):
        assert token in html


def test_successor_is_presentation_only_and_preserves_frozen_v1_bytes():
    assert SUCCESSOR.exists(), "successor missing"
    source = SUCCESSOR.read_text(encoding="utf-8").casefold()
    for forbidden in ("import requests", "import httpx", "curl_cffi", "sportsgameodds", "espn bet", "import espn", "render.com"):
        assert forbidden not in source
    assert "build_player_board_rows" in source
    assert "rank_top_edges" in source
    assert "_handoff" in source
    frozen = {
        "wnba_pra_page1_stier_v1.py": "8882b1034ee7e05ae3006eaedc0ccd91ab30f51f",
        "wnba_pra_page1_final_polish_v1.py": "f524cc7e8216372047690c0b61305dbb308640c9",
        "wnba_pra_page_model_artifact_final_polish_v1.py": "18a3b100228007aa19a63513cfaeedc98f337fbc",
        "runless_v2/wnba_pra_page1_final_polish_runtime_v1.py": "7973b326709bca3abd813e7a2e35849f51afd4a3",
    }
    for rel, expected in frozen.items():
        actual = subprocess.check_output(["git", "hash-object", rel], cwd=ROOT, text=True).strip()
        assert actual == expected, f"frozen byte drift: {rel} -> {actual}"
