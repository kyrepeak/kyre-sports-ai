from __future__ import annotations

import importlib


def _m():
    return importlib.import_module("cfb_player_props_page3_source_policy_v1")


def test_field_priorities_use_two_to_four_relevant_sources_only():
    m = _m()
    assert set(m.FIELD_SOURCE_PRIORITIES) == {
        "player_props", "game_lines", "player_stats", "game_state", "history", "availability"
    }
    assert all(2 <= len(v) <= 4 for v in m.FIELD_SOURCE_PRIORITIES.values())


def test_direct_or_official_sources_rank_before_aggregators():
    m = _m()
    assert m.FIELD_SOURCE_PRIORITIES["player_props"][:3] == (
        "direct_sportsbook_feed", "the_odds_api", "sportsdataio"
    )
    assert m.FIELD_SOURCE_PRIORITIES["game_lines"] == (
        "direct_sportsbook_feed", "the_odds_api", "action_network", "vegasinsider"
    )
    assert m.FIELD_SOURCE_PRIORITIES["player_stats"] == (
        "ncaa_official", "sportsdataio", "collegefootballdata", "sports_reference"
    )
    assert m.FIELD_SOURCE_PRIORITIES["game_state"] == (
        "sportsdataio", "ncaa_official", "espn", "cbs_sports"
    )
    assert m.FIELD_SOURCE_PRIORITIES["history"] == (
        "sports_reference", "collegefootballdata", "ncaa_official", "espn"
    )
    assert m.FIELD_SOURCE_PRIORITIES["availability"] == (
        "official_team_sites", "rotowire", "sportsdataio"
    )


def test_unavailable_sources_are_filtered_without_becoming_active():
    m = _m()
    ranked = m.rank_sources(
        "player_stats", ["sportsdataio", "espn", "ncaa_official", "unknown_provider"]
    )
    assert ranked == ("ncaa_official", "sportsdataio")


def test_newest_equivalent_row_wins_without_null_to_zero_coercion():
    m = _m()
    rows = [
        {"source": "ncaa_official", "value": 281, "observed_at_utc": "2026-10-20T18:00:00Z"},
        {"source": "sportsdataio", "value": None, "observed_at_utc": "not-a-time"},
        {"source": "sports_reference", "value": 289, "observed_at_utc": "2026-10-20T19:30:00Z"},
    ]
    chosen = m.choose_newest_equivalent(rows)
    assert chosen["source"] == "sports_reference"
    assert chosen["value"] == 289
    assert rows[1]["value"] is None


def test_provenance_reports_only_consulted_sources():
    m = _m()
    p = m.provenance(
        "history", ["sports_reference", "ncaa_official", "sports_reference"],
        newest_timestamp="2026-10-20T19:30:00Z",
    )
    assert p["field_family"] == "history"
    assert p["active_provider_ids"] == ("sports_reference", "ncaa_official")
    assert p["newest_timestamp"] == "2026-10-20T19:30:00Z"
    assert "collegefootballdata" not in p["active_provider_ids"]


def test_sportsbook_field_keeps_book_specific_source_family():
    m = _m()
    ranked = m.rank_sources(
        "player_props", ["sportsdataio", "the_odds_api", "direct_sportsbook_feed"]
    )
    assert ranked == ("direct_sportsbook_feed", "the_odds_api", "sportsdataio")
