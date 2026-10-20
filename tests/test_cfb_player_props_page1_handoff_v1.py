from __future__ import annotations

from datetime import date


def _game(game_id: str):
    return {
        "official_game_id": game_id,
        "game_date": "2026-10-24",
        "kickoff_iso": "2026-10-24T19:30:00-04:00",
        "away_team_id": "101",
        "away_team": "Away State",
        "home_team_id": "202",
        "home_team": "Home Tech",
        "provider_game_id": "provider-should-not-navigate",
        "espn_event_id": "espn-alias-only",
    }


def test_handoff_is_canonical_and_provider_ids_are_not_navigation_keys():
    import cfb_player_props_page1_handoff_v1 as handoff

    payload = handoff.build_selected_game_handoff(_game("401999001"), slate_date=date(2026, 10, 24), generation=9)
    assert payload == {
        "route_version": "cfb-player-props-v1",
        "slate_date": "2026-10-24",
        "official_game_id": "401999001",
        "away_team_id": "101",
        "away_team": "Away State",
        "home_team_id": "202",
        "home_team": "Home Tech",
        "kickoff_iso": "2026-10-24T19:30:00-04:00",
        "market_id": "player-props",
        "generation": 9,
    }
    assert "provider_game_id" not in payload
    assert "espn_event_id" not in payload


def test_commit_latest_game_replaces_prior_game_and_clears_player_identity():
    import cfb_player_props_page1_handoff_v1 as handoff

    session = {handoff.SESSION_HANDOFF_KEY: handoff.build_selected_game_handoff(_game("A"), slate_date=date(2026, 10, 24), generation=1), "player_id": "old-player"}
    query = {"sport": "cfb", "market": "player-props", "game_id": "A", "player_id": "old-player"}
    payload = handoff.build_selected_game_handoff(_game("B"), slate_date=date(2026, 10, 24), generation=2)
    handoff.commit_selected_game_handoff(session, query, payload)
    assert session[handoff.SESSION_HANDOFF_KEY]["official_game_id"] == "B"
    assert session["game_id"] == "B"
    assert "player_id" not in session
    assert query == {"sport": "cfb", "market": "player-props", "date": "2026-10-24", "game_id": "B"}


def test_stale_generation_cannot_overwrite_newer_handoff():
    import cfb_player_props_page1_handoff_v1 as handoff

    newer = handoff.build_selected_game_handoff(_game("NEW"), slate_date=date(2026, 10, 24), generation=10)
    stale = handoff.build_selected_game_handoff(_game("OLD"), slate_date=date(2026, 10, 24), generation=9)
    session = {handoff.SESSION_HANDOFF_KEY: newer, "game_id": "NEW"}
    query = {"sport": "cfb", "market": "player-props", "date": "2026-10-24", "game_id": "NEW"}
    handoff.commit_selected_game_handoff(session, query, stale)
    assert session[handoff.SESSION_HANDOFF_KEY] == newer
    assert query["game_id"] == "NEW"
