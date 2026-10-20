from __future__ import annotations

import inspect

from cfb_player_props_market_v1 import PropObservation


def _game(gid="401999001"):
    return {
        "official_game_id": gid, "game_date": "2026-10-24",
        "kickoff_iso": "2026-10-24T19:30:00-04:00", "kickoff_phoenix": "4:30 PM MST",
        "status": "Scheduled", "away_team_id": "101", "away_team": "Away State",
        "away_team_slug": "away-state", "away_rank": 7,
        "home_team_id": "202", "home_team": "Home Tech", "home_team_slug": "home-tech", "home_rank": 12,
    }


def _obs(player, market, book, side, line=250.5, price=-110):
    return PropObservation(
        "401999001", player, player, "101", market, book, side, line, price,
        "2026-10-20T04:00:00Z", "SportsGameOdds", "evt", player, "odd", True,
    )


def test_real_game_without_props_stays_visible_with_truthful_empty_state():
    import cfb_player_props_page1_v1 as page

    card = page.build_game_card_view(_game(), [], [], {"away": {}, "home": {}})
    assert card["official_game_id"] == "401999001"
    assert card["has_props"] is False
    assert card["empty_message"] == "No verified player props posted yet"
    assert card["top_signal"] is None
    html = page.render_game_card_html(card)
    assert 'data-cfb-player-props-game="401999001"' in html
    assert "No verified player props posted yet" in html
    assert "View Game Props" not in html


def test_card_coverage_has_verified_book_count_and_market_badges():
    import cfb_player_props_page1_v1 as page

    rows = [
        _obs("p1", "passing_yards", "FanDuel", "over"),
        _obs("p1", "passing_yards", "FanDuel", "under"),
        _obs("p2", "rushing_yards", "DraftKings", "over", 80.5),
    ]
    card = page.build_game_card_view(_game(), rows, [], {"away": {}, "home": {}})
    assert card["book_count"] == 2
    assert card["market_badges"] == ("Passing Yards", "Rushing Yards")
    assert card["has_props"] is True
    html = page.render_game_card_html(card)
    assert "2 books" in html
    assert "Passing Yards" in html and "Rushing Yards" in html


def test_top_signal_rank_prefers_positive_edge_then_probability_then_books_then_name():
    import cfb_player_props_page1_v1 as page

    signals = [
        {"model_ready": True, "edge": None, "model_probability": .80, "book_count": 4, "player_name": "Zed", "market_key": "passing_yards"},
        {"model_ready": True, "edge": .03, "model_probability": .60, "book_count": 2, "player_name": "B", "market_key": "rushing_yards"},
        {"model_ready": True, "edge": .06, "model_probability": .55, "book_count": 1, "player_name": "C", "market_key": "receiving_yards"},
        {"model_ready": False, "edge": .50, "model_probability": .99, "book_count": 4, "player_name": "A", "market_key": "passing_yards"},
    ]
    assert page.rank_top_signal(signals)["player_name"] == "C"


def test_no_model_ready_candidate_means_no_top_signal():
    import cfb_player_props_page1_v1 as page

    assert page.rank_top_signal([
        {"model_ready": False, "edge": None, "model_probability": None, "book_count": 4, "player_name": "A", "market_key": "passing_yards"}
    ]) is None


def test_card_renders_verified_identity_logo_rank_kickoff_and_single_signal():
    import cfb_player_props_page1_v1 as page

    signal = {
        "model_ready": True, "player_name": "Jalen Example", "market_key": "passing_yards",
        "side": "over", "consensus_line": 275.5, "model_probability": .64,
        "edge": .05, "book_count": 3, "projection": 288.1,
    }
    visuals = {
        "away": {"logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/101.png"},
        "home": {"logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/202.png"},
    }
    card = page.build_game_card_view(_game(), [], [signal], visuals)
    html = page.render_game_card_html(card)
    assert "#7 Away State" in html
    assert "#12 Home Tech" in html
    assert "4:30 PM MST" in html
    assert html.count("Top Kyre Signal") == 1
    assert html.count("Jalen Example") == 1
    assert "64.0%" in html
    assert "https://a.espncdn.com/i/teamlogos/ncaa/500/101.png" in html


def test_page_source_uses_exact_visual_owners_tap_controls_and_no_duplicate_site_header():
    import cfb_player_props_page1_v1 as page

    source = inspect.getsource(page)
    assert "cfb_over_under_logo_resolver_v3" in source
    assert "cfb_over_under_logo_resolver_v2" in source
    assert "resolve_visuals" in source
    assert "resolve_team_logo" in source
    assert "st.segmented_control" in source
    assert 'st.button("View Game Props"' in source
    assert "CFB • PLAYER PROPS" in source
    assert "KYRE SPORTS AI" not in source
    assert "long roster" not in source.lower()
    assert "@media(max-width:760px)" in source.replace(" ", "")
