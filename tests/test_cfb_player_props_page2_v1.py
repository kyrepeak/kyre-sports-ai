from __future__ import annotations

import inspect


def test_page2_source_pins_professional_player_first_contract_without_keyboard_controls():
    import cfb_player_props_page2_v1 as page

    source = inspect.getsource(page)
    compact = source.replace(" ", "")
    assert "CFB • PLAYER PROPS • GAME COMMAND" in source
    assert 'st.button("Back"' in source
    assert "cfb_over_under_logo_resolver_v3" in source
    assert "cfb_over_under_logo_resolver_v2" in source
    assert "No verified props posted yet." in source
    assert "Selected game is unavailable. Return to Player Props." in source
    assert "Verified roster temporarily unavailable." in source
    assert 'st.button("Analyze"' in source
    assert "@media(max-width:760px)" in compact
    assert "text_input(" not in source
    assert "number_input(" not in source
    assert "text_area(" not in source
    assert "cfb_player_props_page1_v1" not in source


def test_page2_orchestration_is_lazy_for_history_and_keeps_defense_presentation_only():
    import cfb_player_props_page2_v1 as page

    source = inspect.getsource(page)
    assert "load_offensive_roster" in source
    assert "load_game_availability" in source
    assert "load_game_prop_observations" in source
    assert "group_player_markets" in source
    assert "load_game_matchup_context" in source
    assert "build_recent_production" in source
    assert "build_page2_signal" in source
    assert "grade_player_matchup" in source
    assert "apply_to_raw" not in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE" in source


def test_player_card_zero_props_remains_visible_with_truthful_copy():
    import cfb_player_props_page2_v1 as page
    from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
    from cfb_player_props_page2_roster_v1 import Page2Player

    player = Page2Player(CanonicalPlayerIdentity("p1", "101", "Player One", "QB", "Away State", "AWY"))
    html = page.render_player_card_html(
        player,
        [],
        {"state": "UNVERIFIED", "verified": False},
        [],
    )
    assert "Player One" in html
    assert "UNVERIFIED" in html
    assert "No verified props posted yet." in html
    assert "Analyze" not in html


def test_prop_row_contains_consensus_best_sides_books_movement_recent_matchup_and_signal():
    import cfb_player_props_page2_v1 as page

    market = {
        "market_key": "passing_yards", "consensus_line": 250.5, "book_count": 3,
        "best_over": {"sportsbook": "FanDuel", "line": 249.5, "price": -110},
        "best_under": {"sportsbook": "Caesars", "line": 252.5, "price": 105},
        "movement": {"available": True, "opening_line": 247.5, "current_line": 250.5, "delta": 3.0, "source": "provider-opening"},
    }
    recent = {"sample_count": 8, "last3": (280.0, 240.0, 260.0), "season_average": 255.0}
    defense = {"label": "FAVORABLE", "message": "Opponent passing defense #92"}
    signal = {"model_ready": True, "side": "over", "model_probability": .64, "edge": .05, "projection": 262.2}
    html = page.render_prop_row_html(market, recent, defense, signal)
    for needle in ("Consensus 250.5", "FanDuel", "Caesars", "3 books", "247.5", "250.5", "Recent", "FAVORABLE", "64.0%", "262.2"):
        assert needle in html
