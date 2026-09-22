"""Regression checks for CFB Over/Under Intelligence V2 Upgrade Step 1."""
from __future__ import annotations

import inspect

import cfb_over_under_matchup_ui_v1 as ui


def _game():
    return {
        "game_id": "123",
        "identity_key": "ncaa:123",
        "espn_event_id": "401000001",
        "game_date": "2026-09-12",
        "away_team": "Oklahoma",
        "away_team_slug": "oklahoma",
        "away_conference": "SEC",
        "home_team": "Michigan",
        "home_team_slug": "michigan",
        "home_conference": "Big Ten",
        "kickoff_et": "12:00 PM ET",
        "venue": "Michigan Stadium",
        "broadcast": "FOX",
        "status": "Scheduled",
        "neutral_site": False,
        "identity_verified": True,
        "date_matches_query": True,
    }


def _profile(team, conference, rank, record):
    return {
        "team": team,
        "conference": conference,
        "ap_rank": rank,
        "record_text": record,
    }


def _payload():
    return {
        "events": [
            {
                "id": "401000001",
                "competitions": [
                    {
                        "competitors": [
                            {
                                "homeAway": "away",
                                "curatedRank": {"current": 10},
                                "records": [{"name": "overall", "summary": "2-0"}],
                                "team": {
                                    "id": "201",
                                    "location": "Oklahoma",
                                    "slug": "oklahoma-sooners",
                                    "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/201.png",
                                },
                            },
                            {
                                "homeAway": "home",
                                "curatedRank": {"current": 16},
                                "records": [{"name": "overall", "summary": "1-0"}],
                                "team": {
                                    "id": "130",
                                    "location": "Michigan",
                                    "slug": "michigan-wolverines",
                                    "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/130.png",
                                },
                            },
                        ]
                    }
                ],
            }
        ]
    }


def test_visual_extraction_uses_verified_espn_event_identity():
    out = ui._extract_visuals(_payload(), _game())

    assert out["away"]["team_id"] == "201"
    assert out["away"]["record"] == "2-0"
    assert out["away"]["rank"] == 10
    assert out["away"]["logo"].endswith("/201.png")
    assert out["home"]["team_id"] == "130"
    assert out["home"]["logo"].endswith("/130.png")


def test_event_name_match_is_a_safe_fallback_when_event_id_missing():
    game = _game()
    game["espn_event_id"] = ""
    assert ui._event_matches_game(_payload()["events"][0], game) is True


def test_enhanced_header_shows_logos_and_compact_game_context(monkeypatch):
    monkeypatch.setattr(ui, "_visuals_for_game", lambda game: ui._extract_visuals(_payload(), game))

    html = ui._enhanced_hero(
        _game(),
        _profile("Oklahoma", "SEC", 10, "2-0"),
        _profile("Michigan", "Big Ten", 16, "1-0"),
    )

    assert "O/U INTELLIGENCE V2" in html
    assert "Oklahoma" in html
    assert "Michigan" in html
    assert "#10 AP" in html
    assert "#16 AP" in html
    assert "/201.png" in html
    assert "/130.png" in html
    assert "12:00 PM ET" in html
    assert "Michigan Stadium" in html
    assert "FOX" in html
    assert "Home field" in html
    assert "FROZEN STEP-9 MODEL" in html


def test_logo_fallback_uses_monogram_without_broken_img():
    html = ui._logo_html("Michigan", {})
    assert "cfbou1-monogram" in html
    assert "MI" in html
    assert "<img" not in html


def test_wrapper_temporarily_replaces_only_frozen_hero_and_restores(monkeypatch):
    target = ui.frozen_v3.frozen_v2.frozen_v1
    original = target._hero
    seen = {}

    monkeypatch.setattr(ui.st, "caption", lambda *a, **k: None)
    monkeypatch.setattr(ui.st, "markdown", lambda *a, **k: None)

    def fake_render(*args, **kwargs):
        seen["during"] = target._hero
        return "ok"

    monkeypatch.setattr(ui.frozen_v3, "render_over_under_hub", fake_render)
    result = ui.render_over_under_hub()

    assert result == "ok"
    assert seen["during"] is ui._enhanced_hero
    assert target._hero is original


def test_upgrade_is_presentation_only_and_freezes_step9_model_contract():
    source = inspect.getsource(ui).lower()

    assert ui.FROZEN_OVER_UNDER_HUB == "cfb_over_under_hub_v3"
    assert ui.MARKET == "Over/Under"
    assert "frozen step-9 model" in source
    assert "projection or selection math is changed" in source

    forbidden = (
        "projected_total =",
        "over_probability =",
        "under_probability =",
        "selection_probability =",
        "rank_slate(",
        "analyze_game(",
        "monte carlo",
        "expected_value",
    )
    for token in forbidden:
        assert token not in source
