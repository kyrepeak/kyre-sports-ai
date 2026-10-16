from datetime import datetime, timezone

import pytest

from nba_spread_injury_availability_v1 import (
    INJURY_SECTION_LABEL,
    MAY_MODIFY_MODEL,
    MAY_MODIFY_PROBABILITY,
    MAY_MODIFY_PROJECTION,
    SPORTSBOOK_PROJECTION_INFLUENCE,
    parse_espn_injury_payload,
    parse_official_injury_report_text,
    reconcile_injury_sources,
    build_game_injury_features,
)


def _game():
    return {
        "game_key": "BKN@MIA:2026-10-14",
        "away_tricode": "BKN",
        "away_name": "Brooklyn Nets",
        "home_tricode": "MIA",
        "home_name": "Miami Heat",
        "game_date_phoenix": "2026-10-14",
        "tip_utc": "2026-10-15T00:30:00Z",
        "status": "UPCOMING",
    }


def test_step7_is_descriptive_only_and_cannot_modify_model():
    assert INJURY_SECTION_LABEL == "Injury + Availability"
    assert SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert MAY_MODIFY_MODEL is False
    assert MAY_MODIFY_PROJECTION is False
    assert MAY_MODIFY_PROBABILITY is False


def test_official_report_parser_maps_matchup_team_player_status_and_reason():
    text = """
Injury Report: 10/14/26 03:15 PM
10/14/2026 08:30 (ET) BKN@MIA Brooklyn Nets Simmons, Ben Questionable Injury/Illness - Left Knee; Soreness
Miami Heat Herro, Tyler Out Injury/Illness - Right Ankle; Sprain
"""
    rows = parse_official_injury_report_text(text, games=[_game()])
    assert rows == [
        {
            "game_key": "BKN@MIA:2026-10-14",
            "team_tricode": "BKN",
            "team_name": "Brooklyn Nets",
            "player_name": "Ben Simmons",
            "status": "QUESTIONABLE",
            "reason": "Injury/Illness - Left Knee; Soreness",
            "provider": "nba_official",
        },
        {
            "game_key": "BKN@MIA:2026-10-14",
            "team_tricode": "MIA",
            "team_name": "Miami Heat",
            "player_name": "Tyler Herro",
            "status": "OUT",
            "reason": "Injury/Illness - Right Ankle; Sprain",
            "provider": "nba_official",
        },
    ]


def test_espn_parser_normalizes_grouped_injury_payload_to_step3_identity():
    payload = {
        "injuries": [
            {
                "team": {"abbreviation": "BKN", "displayName": "Brooklyn Nets"},
                "injuries": [
                    {
                        "athlete": {"displayName": "Ben Simmons"},
                        "status": "Questionable",
                        "shortComment": "Left knee soreness",
                    }
                ],
            }
        ]
    }
    rows = parse_espn_injury_payload(payload, games=[_game()])
    assert rows == [
        {
            "game_key": "BKN@MIA:2026-10-14",
            "team_tricode": "BKN",
            "team_name": "Brooklyn Nets",
            "player_name": "Ben Simmons",
            "status": "QUESTIONABLE",
            "reason": "Left knee soreness",
            "provider": "espn",
        }
    ]


def test_reconcile_requires_exact_player_status_agreement_when_both_sources_report_player():
    official = [{
        "game_key": "BKN@MIA:2026-10-14", "team_tricode": "BKN", "team_name": "Brooklyn Nets",
        "player_name": "Ben Simmons", "status": "QUESTIONABLE", "reason": "Left knee",
        "provider": "nba_official",
    }]
    espn = [{
        "game_key": "BKN@MIA:2026-10-14", "team_tricode": "BKN", "team_name": "Brooklyn Nets",
        "player_name": "Ben Simmons", "status": "OUT", "reason": "Left knee",
        "provider": "espn",
    }]
    result = reconcile_injury_sources(official, espn)
    assert result["verification"] == "UNAVAILABLE"
    assert result["diagnostic_state"] == "PROVIDER_CONFLICT"
    assert result["players"] == []


def test_reconcile_accepts_official_primary_and_records_independent_corroboration():
    official = [{
        "game_key": "BKN@MIA:2026-10-14", "team_tricode": "BKN", "team_name": "Brooklyn Nets",
        "player_name": "Ben Simmons", "status": "QUESTIONABLE", "reason": "Left knee",
        "provider": "nba_official",
    }]
    espn = [{
        "game_key": "BKN@MIA:2026-10-14", "team_tricode": "BKN", "team_name": "Brooklyn Nets",
        "player_name": "Ben Simmons", "status": "QUESTIONABLE", "reason": "Left knee soreness",
        "provider": "espn",
    }]
    result = reconcile_injury_sources(official, espn)
    assert result["verification"] == "VERIFIED"
    assert result["diagnostic_state"] == "OK"
    assert result["providers_consulted"] == ["nba_official", "espn"]
    assert result["players"][0]["status"] == "QUESTIONABLE"
    assert result["players"][0]["source_count"] == 2


def test_reconcile_uses_same_semantic_espn_fallback_when_official_is_unavailable():
    espn = [{
        "game_key": "BKN@MIA:2026-10-14", "team_tricode": "BKN", "team_name": "Brooklyn Nets",
        "player_name": "Ben Simmons", "status": "QUESTIONABLE", "reason": "Left knee soreness",
        "provider": "espn",
    }]
    result = reconcile_injury_sources([], espn, official_available=False, espn_available=True)
    assert result["verification"] == "VERIFIED_FALLBACK"
    assert result["diagnostic_state"] == "PRIMARY_UNAVAILABLE"
    assert result["providers_consulted"] == ["espn"]
    assert result["players"][0]["source_count"] == 1


def test_build_game_features_fails_closed_on_stale_snapshot():
    now = datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc)
    stale = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    result = build_game_injury_features(
        [_game()],
        official_rows=[],
        espn_rows=[],
        official_available=False,
        espn_available=False,
        fetched_at_utc=stale,
        now_utc=now,
        max_age_seconds=3600,
    )
    feature = result["features"][0]
    assert feature["verification"] == "UNAVAILABLE"
    assert feature["diagnostic_state"] == "STALE_SNAPSHOT"
    assert result["sportsbook_projection_influence"] == 0.0


def test_build_game_features_keeps_matchups_separate_and_counts_statuses():
    rows = [
        {"game_key":"BKN@MIA:2026-10-14","team_tricode":"BKN","team_name":"Brooklyn Nets","player_name":"A Player","status":"OUT","reason":"ankle","provider":"nba_official"},
        {"game_key":"BKN@MIA:2026-10-14","team_tricode":"MIA","team_name":"Miami Heat","player_name":"B Player","status":"QUESTIONABLE","reason":"knee","provider":"nba_official"},
    ]
    result = build_game_injury_features(
        [_game()],
        official_rows=rows,
        espn_rows=[],
        official_available=True,
        espn_available=False,
        fetched_at_utc=datetime(2026,10,14,19,55,tzinfo=timezone.utc),
        now_utc=datetime(2026,10,14,20,0,tzinfo=timezone.utc),
    )
    feature = result["features"][0]
    assert feature["verification"] == "VERIFIED"
    assert feature["away"]["counts"]["OUT"] == 1
    assert feature["home"]["counts"]["QUESTIONABLE"] == 1
    assert feature["away"]["players"][0]["player_name"] == "A Player"
    assert feature["home"]["players"][0]["player_name"] == "B Player"


def test_step7_page_wrapper_preserves_step6_page_and_adds_injury_hook():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    wrapper = root / "nba_spread_page_v2.py"
    assert wrapper.exists(), "Step-7 wrapper page is missing"
    source = wrapper.read_text(encoding="utf-8")
    assert "import nba_spread_page_v1 as base" in source
    assert "load_injury_availability_features" in source
    assert "NBA_SPREAD_STEP7_INJURY_AVAILABILITY_ACTIVE" in source
    assert "data-testid=\"nba-spread-step7-injury-card\"" in source
    assert "_render_game_group" in source


def test_step7_router_preserves_step2_compatibility_constant_and_uses_runtime_wrapper():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    router = (root / "streamlit_memory_lazy_router_nba_spread_step2_activation_v1.py").read_text(encoding="utf-8")
    assert 'ACTIVE_PAGE = "nba_spread_page_v1"' in router
    assert 'STEP7_ACTIVE_PAGE = "nba_spread_page_v2"' in router
    assert 'importlib.import_module(STEP7_ACTIVE_PAGE)' in router
