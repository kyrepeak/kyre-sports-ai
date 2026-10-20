from __future__ import annotations

from datetime import datetime

from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
from cfb_player_props_market_v1 import PropObservation
from cfb_player_props_page2_roster_v1 import Page2Player


def _context(generation=12):
    return {
        "state": "ready", "slate_date": "2026-10-24", "game_date": "2026-10-24",
        "official_game_id": "401999001", "away_team_id": "101", "home_team_id": "202",
        "generation": generation,
    }


def _player():
    return Page2Player(CanonicalPlayerIdentity("p1", "101", "Player One", "QB", "Away State", "AWY"))


def _market():
    obs = PropObservation(
        "401999001", "p1", "Player One", "101", "passing_yards", "FanDuel", "over",
        250.5, -110, "2026-10-20T04:00:00Z", "SportsGameOdds", "provider-event",
        "provider-player", "provider-market", True,
    )
    return {
        "market_key": "passing_yards", "consensus_line": 250.5,
        "observations": [obs], "book_count": 1,
    }


def test_selected_prop_handoff_keeps_canonical_ids_and_provider_ids_provenance_only():
    import cfb_player_props_page2_handoff_v1 as handoff

    payload = handoff.build_selected_prop_handoff(_context(), _player(), _market(), generation=12)
    assert payload["route_version"] == "cfb-player-props-page2-v1"
    assert payload["slate_date"] == "2026-10-24"
    assert payload["official_game_id"] == "401999001"
    assert payload["away_team_id"] == "101"
    assert payload["home_team_id"] == "202"
    assert payload["official_player_id"] == "p1"
    assert payload["player_name"] == "Player One"
    assert payload["official_team_id"] == "101"
    assert payload["market_key"] == "passing_yards"
    assert payload["consensus_line"] == 250.5
    assert payload["generation"] == 12
    assert payload["selection_state"] == "selected"
    datetime.fromisoformat(payload["selected_at_utc"].replace("Z", "+00:00"))
    assert "provider_event_id" not in payload
    assert "provider_player_id" not in payload
    assert "provider_market_id" not in payload
    assert payload["provenance"][0]["provider_event_id"] == "provider-event"


def test_newer_generation_wins_and_stale_analyze_cannot_overwrite():
    import cfb_player_props_page2_handoff_v1 as handoff

    session = {}
    query = {"sport": "cfb", "market": "player-props", "date": "2026-10-24", "game_id": "401999001"}
    newest = handoff.build_selected_prop_handoff(_context(20), _player(), _market(), generation=20)
    stale = handoff.build_selected_prop_handoff(_context(19), _player(), {**_market(), "market_key": "rushing_yards"}, generation=19)
    handoff.commit_selected_prop_handoff(session, query, newest)
    handoff.commit_selected_prop_handoff(session, query, stale)
    stored = session[handoff.SESSION_HANDOFF_KEY]
    assert stored["generation"] == 20
    assert stored["market_key"] == "passing_yards"
    assert query["player_id"] == "p1"
    assert query["prop"] == "passing_yards"


def test_same_generation_can_change_current_page_selection():
    import cfb_player_props_page2_handoff_v1 as handoff

    session, query = {}, {}
    first = handoff.build_selected_prop_handoff(_context(20), _player(), _market(), generation=20)
    second = dict(first)
    second["market_key"] = "passing_touchdowns"
    handoff.commit_selected_prop_handoff(session, query, first)
    handoff.commit_selected_prop_handoff(session, query, second)
    assert session[handoff.SESSION_HANDOFF_KEY]["market_key"] == "passing_touchdowns"
    assert query["prop"] == "passing_touchdowns"
