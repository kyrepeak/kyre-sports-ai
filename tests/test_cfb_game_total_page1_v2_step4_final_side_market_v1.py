from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPAIR = ROOT / "cfb_game_total_page1_v2_step4_event_page_side_market_repair_v1.py"


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


def _direct_event_page_miss(_provider_id: str):
    return {"attachments": {"markets": {}}}


def _exact_fallback(game):
    import cfb_game_total_page1_step4_side_market_v1 as legacy

    return legacy.enrich_verified_side_market(game, loader=_exact_market_loader)


def test_frozen_legacy_fallback_reproduces_verified_identity_alias_gap() -> None:
    import cfb_game_total_page1_step4_side_market_v1 as legacy

    out = legacy.enrich_verified_side_market(
        _runtime_game(),
        loader=_exact_market_loader,
    )

    assert out["verified_side_market_status"] == "UNAVAILABLE"
    assert out["verified_side_market_reason"] == "official event identity unavailable"
    assert "verified_away_spread" not in out
    assert "verified_away_moneyline" not in out


def test_repair_promotes_verified_official_id_only_for_exact_event_fallback() -> None:
    import cfb_game_total_page1_v2_step4_event_page_side_market_repair_v1 as repair

    out = repair.enrich_verified_side_market(
        _runtime_game(),
        event_page_loader=_direct_event_page_miss,
        fallback_enricher=_exact_fallback,
    )

    assert out["verified_side_market_status"] == "GREEN"
    assert out["verified_side_market_event_id"] == "401858254"
    assert out["verified_away_spread"] == 3.5
    assert out["verified_home_spread"] == -3.5
    assert out["verified_away_moneyline"] == 150
    assert out["verified_home_moneyline"] == -185
    assert out["verified_side_market_projection_weight"] == 0.0
    assert out["market_total"] == 59.5
    assert "event_id" not in out


def test_repair_fails_closed_on_verified_official_id_disagreement() -> None:
    import cfb_game_total_page1_v2_step4_event_page_side_market_repair_v1 as repair

    game = _runtime_game()
    game["espn_event_id"] = "401858254"
    game["market_official_game_id"] = "401000999"

    out = repair.enrich_verified_side_market(
        game,
        event_page_loader=_direct_event_page_miss,
        fallback_enricher=_exact_fallback,
    )

    assert out["verified_side_market_status"] == "UNAVAILABLE"
    assert out["verified_side_market_reason"] == "official event identity disagreement"
    assert "verified_away_spread" not in out
    assert "verified_away_moneyline" not in out


def test_repair_keeps_projection_and_scope_firewalls() -> None:
    source = REPAIR.read_text(encoding="utf-8")
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_OTHER_SPORTS = False" in source
