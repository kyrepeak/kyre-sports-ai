from __future__ import annotations


def _snapshot(line=32.5, price=-110):
    quote = {
        "sportsbook": "FanDuel",
        "line": line,
        "over_price": price,
        "under_price": -110,
        "observed_at_utc": "2026-10-21T17:30:00Z",
        "team": "MIN",
    }
    return {
        "slate_date": "2026-10-21",
        "games": [{
            "game_id": "g1", "away_tricode": "MIN", "home_tricode": "LAL",
            "tip_utc": "2026-10-22T02:00:00Z",
        }],
        "market": {
            "anthonyedwards": {
                "player_name": "Anthony Edwards",
                "featured_quote": quote,
                "quotes": [quote, {**quote, "sportsbook":"DraftKings", "line":33.5}],
            }
        },
        "profiles": {
            "anthonyedwards": {
                "player_name": "Anthony Edwards", "team": "MIN", "position": "SG",
                "headshot": "https://example.com/ant.png", "provider_ids": {"cbs":"123"},
                "current_games": [], "prior_games": [], "stats_source":"CBS Sports roster verification",
            }
        },
        "injury_players": {"anthonyedwards": {"status":"AVAILABLE"}},
    }


def test_context_resolves_canonical_player_game_and_visual_identity():
    from nba_pra_page2_context_v1 import build_page2_context
    ctx = build_page2_context(_snapshot(), "anthonyedwards")
    assert ctx["state"] == "ready"
    assert ctx["player"]["player_name"] == "Anthony Edwards"
    assert ctx["player"]["headshot"].endswith("ant.png")
    assert ctx["team"] == "MIN"
    assert ctx["opponent"] == "LAL"
    assert ctx["game"]["game_id"] == "g1"
    assert ctx["team_logo"]
    assert ctx["opponent_logo"]
    assert ctx["availability"] == "AVAILABLE"


def test_context_preserves_exact_selected_quote_when_still_current():
    from nba_pra_page2_context_v1 import build_page2_context
    selected = dict(_snapshot()["market"]["anthonyedwards"]["featured_quote"])
    ctx = build_page2_context(_snapshot(), "anthonyedwards", selected_quote=selected)
    assert ctx["state"] == "ready"
    assert ctx["selected_quote"] == selected
    assert ctx["current_quote"] == selected
    assert ctx["line_moved"] is False


def test_context_labels_line_moved_since_selection_instead_of_replacing_quote():
    from nba_pra_page2_context_v1 import build_page2_context
    selected = dict(_snapshot(line=32.5)["market"]["anthonyedwards"]["featured_quote"])
    live = _snapshot(line=33.5)
    ctx = build_page2_context(live, "anthonyedwards", selected_quote=selected)
    assert ctx["state"] == "line_moved"
    assert ctx["selected_quote"]["line"] == 32.5
    assert ctx["current_quote"]["line"] == 33.5
    assert ctx["line_moved"] is True
    assert ctx["line_moved_label"] == "LINE MOVED SINCE SELECTION"


def test_context_rejects_stale_or_wrong_player_and_keeps_nulls_null():
    from nba_pra_page2_context_v1 import build_page2_context
    bad = build_page2_context(_snapshot(), "wrong-player")
    assert bad["state"] == "player_unavailable"
    snap = _snapshot()
    snap["profiles"]["anthonyedwards"]["position"] = None
    ctx = build_page2_context(snap, "anthonyedwards")
    assert ctx["player"]["position"] is None
