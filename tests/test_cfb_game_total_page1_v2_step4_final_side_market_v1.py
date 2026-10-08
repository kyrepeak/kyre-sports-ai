from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "cfb_game_total_clean_page_v16.py"


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


def test_v16_identity_bridge_promotes_exact_espn_id_to_generic_event_id(monkeypatch) -> None:
    import cfb_game_total_clean_page_v16 as page

    def frozen_recover(game, selected_day):
        out = dict(game or {})
        out["espn_event_id"] = "401858254"
        out["game_date"] = str(selected_day)
        return out

    monkeypatch.setattr(page, "_FROZEN_RECOVER_RUNTIME_EVENT", frozen_recover)
    out = page._recover_exact_runtime_event_v165({}, "2026-10-09")

    assert out["espn_event_id"] == "401858254"
    assert out["event_id"] == "401858254"
    assert out["game_date"] == "2026-10-09"


def test_v16_identity_bridge_does_not_overwrite_existing_event_id(monkeypatch) -> None:
    import cfb_game_total_clean_page_v16 as page

    def frozen_recover(game, selected_day):
        out = dict(game or {})
        out["espn_event_id"] = "401858254"
        out["event_id"] = "401000999"
        out["game_date"] = str(selected_day)
        return out

    monkeypatch.setattr(page, "_FROZEN_RECOVER_RUNTIME_EVENT", frozen_recover)
    out = page._recover_exact_runtime_event_v165({}, "2026-10-09")

    assert out["event_id"] == "401000999"


def test_identity_bridge_unlocks_existing_exact_event_fallback(monkeypatch) -> None:
    import cfb_game_total_clean_page_v16 as page
    import cfb_game_total_page1_v2_step4_event_page_side_market_repair_v1 as repair

    def frozen_recover(game, selected_day):
        out = dict(game or {})
        out["espn_event_id"] = "401858254"
        out["game_date"] = str(selected_day)
        return out

    monkeypatch.setattr(page, "_FROZEN_RECOVER_RUNTIME_EVENT", frozen_recover)
    game = page._recover_exact_runtime_event_v165(_runtime_game(), "2026-10-09")
    out = repair.enrich_verified_side_market(
        game,
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


def test_v16_bridge_keeps_projection_and_scope_firewalls() -> None:
    source = PAGE.read_text(encoding="utf-8")
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_OTHER_SPORTS = False" in source
    assert "NETWORK_CALLS_ADDED = 0" in source
