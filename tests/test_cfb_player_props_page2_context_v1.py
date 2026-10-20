from __future__ import annotations

import cfb_player_props_page1_handoff_v1 as handoff


def _game(gid: str = "401999001") -> dict:
    return {
        "official_game_id": gid,
        "game_id": gid,
        "game_date": "2026-10-24",
        "kickoff_iso": "2026-10-24T19:30:00-04:00",
        "kickoff_phoenix": "4:30 PM MST",
        "status": "Scheduled",
        "away_team_id": "101",
        "away_espn_team_id": "101",
        "away_team": "Away State",
        "away_record_summary": "6-1",
        "away_rank": 7,
        "home_team_id": "202",
        "home_espn_team_id": "202",
        "home_team": "Home Tech",
        "home_record_summary": "5-2",
        "home_rank": 12,
        "venue": "Example Stadium",
        "broadcast": "ABC",
        "espn_event_id": "espn-provider-alias-9001",
    }


def _handoff(generation: int = 12) -> dict:
    return {
        "route_version": handoff.ROUTE_VERSION,
        "slate_date": "2026-10-24",
        "official_game_id": "401999001",
        "away_team_id": "101",
        "away_team": "Away State",
        "home_team_id": "202",
        "home_team": "Home Tech",
        "kickoff_iso": "2026-10-24T19:30:00-04:00",
        "market_id": "player-props",
        "generation": generation,
    }


def test_exact_official_game_id_reconstructs_one_selected_game_and_reads_date_once():
    import cfb_player_props_page2_context_v1 as context

    seen: list[str] = []

    def schedule_reader(day):
        seen.append(str(day))
        return [_game("401999000"), _game("401999001")]

    session = {handoff.SESSION_HANDOFF_KEY: _handoff(), "date": "2026-10-24", "game_id": "401999001"}
    query = {"sport": "cfb", "market": "player-props", "date": "2026-10-24", "game_id": "401999001"}
    result = context.resolve_page2_context(session, query, schedule_reader=schedule_reader)

    assert seen == ["2026-10-24"]
    assert result["state"] == "ready"
    assert result["official_game_id"] == "401999001"
    assert result["away_team_id"] == "101"
    assert result["home_team_id"] == "202"
    assert result["away_record"] == "6-1"
    assert result["home_record"] == "5-2"
    assert result["kickoff_iso"] == "2026-10-24T19:30:00-04:00"
    assert result["kickoff_phoenix"] == "4:30 PM MST"
    assert result["venue"] == "Example Stadium"
    assert result["broadcast"] == "ABC"


def test_provider_event_id_can_never_select_page2_game():
    import cfb_player_props_page2_context_v1 as context

    result = context.resolve_page2_context(
        {"date": "2026-10-24", "game_id": "espn-provider-alias-9001"},
        {"date": "2026-10-24", "game_id": "espn-provider-alias-9001"},
        schedule_reader=lambda day: [_game()],
    )
    assert result["state"] == "unavailable"
    assert result.get("official_game_id") in {None, ""}


def test_stale_page1_team_ids_fail_closed_as_invalid():
    import cfb_player_props_page2_context_v1 as context

    stale = _handoff()
    stale["away_team_id"] = "WRONG-TEAM"
    result = context.resolve_page2_context(
        {handoff.SESSION_HANDOFF_KEY: stale, "date": "2026-10-24", "game_id": "401999001"},
        {"date": "2026-10-24", "game_id": "401999001"},
        schedule_reader=lambda day: [_game()],
    )
    assert result["state"] == "invalid"
    assert "team" in result["reason"].lower()


def test_missing_selected_game_never_substitutes_another_matchup():
    import cfb_player_props_page2_context_v1 as context

    result = context.resolve_page2_context(
        {"date": "2026-10-24", "game_id": "401999999"},
        {"date": "2026-10-24", "game_id": "401999999"},
        schedule_reader=lambda day: [_game("401999001")],
    )
    assert result["state"] == "unavailable"
    assert result.get("official_game_id") in {None, ""}


def test_clear_page2_selection_preserves_cfb_player_props_slate_identity_only():
    import cfb_player_props_page2_context_v1 as context

    session = {
        "sport": "cfb", "market": "player-props", "date": "2026-10-24",
        "game_id": "401999001", "player_id": "p1", "prop": "passing_yards",
        "cfbpp2_position": "QB", "ks_cfb_player_props_page2_handoff_v1": {"x": 1},
        handoff.SESSION_HANDOFF_KEY: _handoff(), "unrelated": "keep-me",
    }
    query = {
        "sport": "cfb", "market": "player-props", "date": "2026-10-24",
        "game_id": "401999001", "player_id": "p1", "prop": "passing_yards",
        "unrelated": "keep-me-too",
    }
    context.clear_page2_selection(session, query)

    for mapping in (session, query):
        assert mapping["date"] == "2026-10-24"
        assert mapping["sport"] == "cfb"
        assert mapping["market"] == "player-props"
        assert "game_id" not in mapping
        assert "player_id" not in mapping
        assert "prop" not in mapping
    assert "cfbpp2_position" not in session
    assert "ks_cfb_player_props_page2_handoff_v1" not in session
    assert handoff.SESSION_HANDOFF_KEY in session
    assert session["unrelated"] == "keep-me"
    assert query["unrelated"] == "keep-me-too"


def test_runtime_without_game_id_delegates_page1_once_and_never_page2(monkeypatch):
    import cfb_player_props_runtime_v2 as runtime

    calls = {"page1": 0, "page2": 0}
    monkeypatch.setattr(runtime.st, "session_state", {})
    monkeypatch.setattr(runtime.st, "query_params", {"sport": "cfb", "market": "player-props", "date": "2026-10-24"})
    monkeypatch.setattr(runtime.page1, "render_cfb_player_props_page1", lambda: calls.__setitem__("page1", calls["page1"] + 1))
    monkeypatch.setattr(runtime.page2, "render_cfb_player_props_page2", lambda: calls.__setitem__("page2", calls["page2"] + 1))

    runtime.render_cfb_player_props_runtime()
    assert calls == {"page1": 1, "page2": 0}


def test_runtime_with_game_id_renders_page2_only(monkeypatch):
    import cfb_player_props_runtime_v2 as runtime

    calls = {"page1": 0, "page2": 0}
    monkeypatch.setattr(runtime.st, "session_state", {"game_id": "401999001"})
    monkeypatch.setattr(runtime.st, "query_params", {"sport": "cfb", "market": "player-props", "date": "2026-10-24", "game_id": "401999001"})
    monkeypatch.setattr(runtime.page1, "render_cfb_player_props_page1", lambda: calls.__setitem__("page1", calls["page1"] + 1))
    monkeypatch.setattr(runtime.page2, "render_cfb_player_props_page2", lambda: calls.__setitem__("page2", calls["page2"] + 1))

    runtime.render_cfb_player_props_runtime()
    assert calls == {"page1": 0, "page2": 1}
