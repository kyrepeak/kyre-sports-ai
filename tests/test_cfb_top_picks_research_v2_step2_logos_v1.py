from __future__ import annotations

from pathlib import Path

import cfb_top_picks_page_v2 as cards
import cfb_top_picks_team_identity_v1 as identity
from devsystem.cfb_top_picks_research_v2_step2_logos_v1 import check_repository

ENGINE = Path("cfb_top_picks_engine_v1.py").read_text(encoding="utf-8")
RESOLVER = Path("cfb_top_picks_team_identity_v1.py").read_text(encoding="utf-8")


def _game(i: int = 1) -> dict:
    return {
        "espn_event_id": str(401900000 + i),
        "away_team": f"Away {i}",
        "home_team": f"Home {i}",
        "away_espn_team_id": str(1000 + i),
        "home_espn_team_id": str(2000 + i),
        "away_conference": "ACC",
        "home_conference": "SEC",
    }


def _pick(i: int = 1) -> dict:
    return {
        "rank": i,
        "event_id": str(401900000 + i),
        "away": f"Away {i}",
        "away_abbr": f"A{i}",
        "home": f"Home {i}",
        "home_abbr": f"H{i}",
        "time": "Sat, 12:00 PM",
        "network": "ESPN",
        "market": "OVER/UNDER",
        "pick": "Over 51.5",
        "odds": "FanDuel",
        "probability": 64,
        "probability_value": 0.64,
        "reliability": 0.88,
        "toughness": 3,
        "toughness_label": "Medium",
    }


def test_exact_ids_generate_real_espn_logo_urls_without_fallback(monkeypatch):
    def fallback_must_not_run(*args, **kwargs):
        raise AssertionError("multi-source fallback should not run for exact IDs")

    monkeypatch.setattr(identity.multisource, "resolve_team_logo", fallback_must_not_run)
    out = identity.resolve_ranked_pick(_pick(), _game())
    assert out["away_team_id"] == "1001"
    assert out["home_team_id"] == "2001"
    assert out["away_logo_url"].endswith("/1001.png")
    assert out["home_logo_url"].endswith("/2001.png")
    assert out["away_logo_provider"] == "espn_exact_team_id"
    assert out["home_logo_provider"] == "espn_exact_team_id"
    assert out["logo_identity_ready"] is True
    assert out["api2_used_for_logos"] is False


def test_independent_multisource_fallback_fills_missing_exact_logo(monkeypatch):
    monkeypatch.setattr(
        identity.exact_logo,
        "resolve_visuals",
        lambda game: {
            "away": {"team_id": game["away_espn_team_id"], "logo": ""},
            "home": {"team_id": game["home_espn_team_id"], "logo": ""},
        },
    )
    monkeypatch.setattr(
        identity.multisource,
        "resolve_team_logo",
        lambda name, slug="", conference="": {
            "logo": f"https://logos.example/{slug}.png",
            "logo_provider": "official_athletics",
            "source": "Official athletics website",
            "logo_source_url": f"https://logos.example/{slug}.png",
            "confidence": "HIGH",
            "provider_attempts": [{"provider": "official", "status": "resolved"}],
        },
    )
    out = identity.resolve_ranked_pick(_pick(), _game())
    assert out["away_logo_provider"] == "official_athletics"
    assert out["home_logo_provider"] == "official_athletics"
    assert out["logo_identity_ready"] is True


def test_all_ten_ranked_rows_can_be_enriched_without_reordering():
    picks = [_pick(i) for i in range(1, 11)]
    games = {str(401900000 + i): _game(i) for i in range(1, 11)}
    out = identity.enrich_ranked_picks(picks, games)
    assert [row["rank"] for row in out] == list(range(1, 11))
    assert [row["probability"] for row in out] == [64] * 10
    assert len(out) == 10
    assert all(row["logo_identity_ready"] for row in out)
    assert sum(bool(row["away_logo_url"]) + bool(row["home_logo_url"]) for row in out) == 20


def test_live_card_markup_uses_real_images_not_initial_placeholders():
    row = identity.resolve_ranked_pick(_pick(), _game())
    html = cards._card(row)
    assert html.count('data-top-picks-real-logo="true"') == 2
    assert 'data-testid="cfb-top-picks-logo-away-1"' in html
    assert 'data-testid="cfb-top-picks-logo-home-1"' in html
    assert "/1001.png" in html and "/2001.png" in html
    assert 'data-logo-placeholder="true"' not in html


def test_logo_enrichment_is_after_frozen_ranking_and_api2_stays_separate():
    assert ENGINE.index("picks = _rank_balanced(candidates, limit=limit)") < ENGINE.index(
        "picks = team_identity.enrich_ranked_picks(picks, games_by_event)"
    )
    assert "sports_api" not in RESOLVER
    assert "KYRE_SPORTS_API" not in RESOLVER
    assert "API2_USED = False" in RESOLVER


def test_step2_permanent_contract_guard():
    result = check_repository()
    assert result["status"] == "GREEN"
    assert result["required_real_logo_images"] == 20
    assert result["exact_identity_primary"] is True
    assert result["multi_source_fallback"] is True
    assert result["api2_protected"] is True
    assert result["ranking_math_changed"] is False
    assert result["probability_math_changed"] is False
