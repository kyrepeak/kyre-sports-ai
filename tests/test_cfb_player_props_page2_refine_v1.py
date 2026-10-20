from __future__ import annotations

import inspect
from types import SimpleNamespace

import cfb_player_props_page2_v1 as page


def test_navigation_contract_has_back_to_page1_and_fixed_top_control():
    source = inspect.getsource(page)
    assert 'st.button("← Back to Player Props"' in source
    assert 'id="cfbpp2-top"' in source
    assert 'href="#cfbpp2-top"' in source
    assert "cfbpp2-top-link" in source
    assert "position:fixed" in source.replace(" ", "")


def test_market_filter_maps_frozen_markets_into_user_facing_buckets():
    assert page.market_matches_filter("passing_yards", "PASS") is True
    assert page.market_matches_filter("passing_touchdowns", "PASS") is True
    assert page.market_matches_filter("rushing_yards", "RUSH") is True
    assert page.market_matches_filter("receiving_yards", "REC") is True
    assert page.market_matches_filter("receiving_receptions", "RECEPTIONS") is True
    assert page.market_matches_filter("touchdowns", "TD") is True
    assert page.market_matches_filter("rushing_yards", "PASS") is False
    assert page.market_matches_filter("touchdowns", "ALL") is True


def test_filter_markets_keeps_only_requested_market_bucket():
    markets = [
        {"market_key": "passing_yards"},
        {"market_key": "rushing_yards"},
        {"market_key": "passing_touchdowns"},
    ]
    assert [m["market_key"] for m in page.filter_player_markets(markets, "PASS")] == [
        "passing_yards", "passing_touchdowns"
    ]
    assert page.filter_player_markets(markets, "REC") == []


def test_players_with_active_filtered_markets_are_prioritized_without_reordering_groups():
    players = [SimpleNamespace(official_player_id="p1"), SimpleNamespace(official_player_id="p2"), SimpleNamespace(official_player_id="p3")]
    grouped = {
        "p1": [],
        "p2": [{"market_key": "receiving_yards"}],
        "p3": [{"market_key": "passing_yards"}],
    }
    active, inactive = page.partition_players_by_markets(players, grouped, "PASS")
    assert [p.official_player_id for p in active] == ["p3"]
    assert [p.official_player_id for p in inactive] == ["p1", "p2"]


def test_zero_market_player_card_is_compact_and_unverified_is_visually_muted():
    from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
    from cfb_player_props_page2_roster_v1 import Page2Player

    player = Page2Player(CanonicalPlayerIdentity("p1", "101", "Player One", "QB", "Away State", "AWY"))
    html = page.render_player_card_html(
        player,
        [],
        {"state": "UNVERIFIED", "verified": False},
        [],
        compact=True,
    )
    assert "cfbpp2-player compact" in html
    assert "cfbpp2-status muted" in html
    assert "No active verified prop markets." in html


def test_page2_live_market_refresh_is_wired_without_keyboard_controls():
    source = inspect.getsource(page)
    assert "st_autorefresh" in source
    assert "30_000" in source or "30000" in source
    assert "text_input(" not in source
    assert "number_input(" not in source
    assert "text_area(" not in source
