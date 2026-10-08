from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "cfb_game_total_page1_v2_step4_final_side_market_v1.py"


def _exact_market_loader(target_date: str):
    assert target_date == "2026-10-09"
    event_id = "401858254"
    return {
        event_id: {
            "event_id": event_id,
            "market_available": True,
            "projection_weight": 0.0,
            "may_modify_projection": False,
            "provider": "exact-event market context",
            "away_spread": 3.5,
            "home_spread": -3.5,
            "away_moneyline": 150,
            "home_moneyline": -185,
        }
    }, {
        "status": "GREEN",
        "date": target_date,
        "projection_weight": 0.0,
    }


def _runtime_game() -> dict:
    return {
        "espn_event_id": "401858254",
        "market_official_game_id": "401858254",
        "game_date": "2026-10-09",
        "market_identity_verified": True,
        "market_sportsbook": "FanDuel",
        "market_provider_game_id": "fd-live-event",
        "market_projection_weight": 0.0,
        "market_may_modify_projection": False,
        "market_total": 59.5,
    }


def test_frozen_fallback_reproduces_verified_identity_alias_gap() -> None:
    import cfb_game_total_page1_step4_side_market_v1 as legacy

    out = legacy.enrich_verified_side_market(
        _runtime_game(),
        loader=_exact_market_loader,
    )

    assert out["verified_side_market_status"] == "UNAVAILABLE"
    assert out["verified_side_market_reason"] == "official event identity unavailable"
    assert "verified_away_spread" not in out
    assert "verified_away_moneyline" not in out


def test_finalizer_promotes_verified_official_id_only_for_exact_event_fallback() -> None:
    assert MODULE.exists(), "final side-market successor module is missing"

    import cfb_game_total_page1_step4_side_market_v1 as legacy
    import cfb_game_total_page1_v2_step4_final_side_market_v1 as finalizer

    def direct_event_page_miss(_provider_id: str):
        return {"attachments": {"markets": {}}}

    def exact_fallback(game):
        return legacy.enrich_verified_side_market(game, loader=_exact_market_loader)

    out = finalizer.enrich_verified_side_market(
        _runtime_game(),
        event_page_loader=direct_event_page_miss,
        fallback_enricher=exact_fallback,
    )

    assert out["verified_side_market_status"] == "GREEN"
    assert out["verified_side_market_event_id"] == "401858254"
    assert out["verified_away_spread"] == 3.5
    assert out["verified_home_spread"] == -3.5
    assert out["verified_away_moneyline"] == 150
    assert out["verified_home_moneyline"] == -185
    assert out["verified_side_market_projection_weight"] == 0.0
    assert out["market_total"] == 59.5


def test_finalizer_fails_closed_on_official_id_disagreement() -> None:
    assert MODULE.exists(), "final side-market successor module is missing"

    import cfb_game_total_page1_step4_side_market_v1 as legacy
    import cfb_game_total_page1_v2_step4_final_side_market_v1 as finalizer

    game = _runtime_game()
    game["espn_event_id"] = "401858254"
    game["market_official_game_id"] = "401000999"

    def direct_event_page_miss(_provider_id: str):
        return {"attachments": {"markets": {}}}

    def exact_fallback(game):
        return legacy.enrich_verified_side_market(game, loader=_exact_market_loader)

    out = finalizer.enrich_verified_side_market(
        game,
        event_page_loader=direct_event_page_miss,
        fallback_enricher=exact_fallback,
    )

    assert out["verified_side_market_status"] == "UNAVAILABLE"
    assert out["verified_side_market_reason"] == "official event identity disagreement"
    assert "verified_away_spread" not in out
    assert "verified_away_moneyline" not in out


def test_finalizer_does_not_change_projection_or_total_contract() -> None:
    source = MODULE.read_text(encoding="utf-8") if MODULE.exists() else ""
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_OTHER_SPORTS = False" in source
    assert "hardcoded" not in source.casefold()
    assert "fuzzy" not in source.casefold()
