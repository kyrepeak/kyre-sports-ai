from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _page():
    offers = []
    for name, line, p_over, edge, proj in (
        ("A Player", 31.5, .64, .080, 33.2),
        ("B Player", 24.5, .59, .045, 25.8),
        ("C Player", 28.5, .43, -.040, 27.1),
        ("D Player", 19.5, .52, .015, 20.0),
    ):
        base = {
            "player_name": name,
            "sportsbook": "FanDuel",
            "line": line,
            "team": "Atlanta Dream",
            "opponent": "Golden State Valkyries",
            "model_state": "LINE_BOUND_READY",
            "p_over": p_over,
            "p_under": 1 - p_over,
            "edge": edge,
            "projection_pra": proj,
            "market_captured_at_utc": "2026-10-21T20:55:00+00:00",
        }
        offers.append(base | {"side": "over", "american_odds": -115})
        offers.append(base | {"side": "under", "american_odds": -105})
    return {
        "date": "2026-10-21",
        "snapshot_state": "READY",
        "cache_state": "FRESH",
        "selected_provider": "fanduel",
        "market_capture_at": "2026-10-21T20:55:00+00:00",
        "offers": offers,
        "final_card": [],
    }


def test_groups_exact_provider_quotes_without_averaging():
    import wnba_pra_page1_stier_v1 as page

    a = next(x for x in page.build_player_board_rows(_page()) if x["player_name"] == "A Player")
    assert (a["sportsbook"], a["line"], a["over_odds"], a["under_odds"]) == (
        "FanDuel",
        31.5,
        -115,
        -105,
    )
    assert a["lean"] == "OVER"
    assert a["model_probability"] == .64
    assert a["model_edge"] == .08


def test_top_edges_use_existing_absolute_model_edge_only():
    import wnba_pra_page1_stier_v1 as page

    ranked = page.rank_top_edges(page.build_player_board_rows(_page()), 3)
    assert [x["player_name"] for x in ranked] == ["A Player", "B Player", "C Player"]
    assert ranked[2]["lean"] == "UNDER"


def test_missing_optional_context_is_explicit():
    import wnba_pra_page1_stier_v1 as page

    assert page.optional_label(None) == "Not verified on Page 1"
    assert page.optional_label("") == "Not verified on Page 1"
    assert page.optional_label("ACTIVE") == "ACTIVE"


def test_renderer_has_approved_page1_hierarchy_and_no_network_client():
    source = (ROOT / "wnba_pra_page1_stier_v1.py").read_text(encoding="utf-8")
    for token in (
        "Top 3 Model Edges",
        "Player Discovery",
        "Analyze Player",
        "L5",
        "L10",
        "Season",
        "Opponent History",
        "Line Move",
        "Current Book",
        "Search players",
        "Sort by",
        "Game Status",
        "Final PRA Card",
    ):
        assert token in source
    assert "import requests" not in source
    assert "import httpx" not in source
    assert "curl_cffi" not in source


def test_v3617_uses_s_tier_renderer_but_keeps_one_read_orchestration():
    source = (ROOT / "wnba_pra_hub_v3617.py").read_text(encoding="utf-8")
    assert "from wnba_pra_page1_stier_v1 import render_page_snapshot" in source
    assert "fetch_page_snapshot(day, season=2026)" in source
    assert "refresh_if_claimed" in source
    assert "wnba_pra_page_snapshot_renderer_v1" not in source
