from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "cfb_game_total_page1_v2_step4_event_page_side_market_repair_v1.py"
MARKET_ADAPTER = ROOT / "cfb_over_under_market_adapter_v1.py"
APP = ROOT / "app.py"


def _odds(value: int) -> dict:
    return {"winRunnerOdds": {"americanDisplayOdds": {"americanOddsInt": value}}}


def _runner(role: str, odds: int, handicap=None) -> dict:
    row = {
        "runnerStatus": "ACTIVE",
        "result": {"type": role},
        **_odds(odds),
    }
    if handicap is not None:
        row["handicap"] = handicap
    return row


def _market(name: str, priority: int, *, event_id=None, runners=None) -> dict:
    row = {
        "marketName": name,
        "marketStatus": "OPEN",
        "inPlay": False,
        "sortPriority": priority,
        "runners": runners or [],
    }
    if event_id is not None:
        row["eventId"] = event_id
    return row


def _event_page(provider_id: str = "fd-123") -> dict:
    return {
        "attachments": {
            "markets": {
                "money-secondary": _market(
                    "Moneyline",
                    20,
                    runners=[_runner("AWAY", 160), _runner("HOME", -190)],
                ),
                "money-primary": _market(
                    "Moneyline",
                    2,
                    runners=[_runner("AWAY", 155), _runner("HOME", -188)],
                ),
                "spread-primary": _market(
                    "Spread",
                    1,
                    runners=[
                        _runner("AWAY", -110, 3.5),
                        _runner("HOME", -110, -3.5),
                    ],
                ),
                "other-event": _market(
                    "Spread",
                    0,
                    event_id="fd-wrong",
                    runners=[
                        _runner("AWAY", -105, 1.5),
                        _runner("HOME", -115, -1.5),
                    ],
                ),
            }
        }
    }


def _verified_game() -> dict:
    return {
        "market_identity_verified": True,
        "market_sportsbook": "FanDuel",
        "market_provider_game_id": "fd-123",
        "market_official_game_id": "401752709",
        "market_projection_weight": 0.0,
        "market_may_modify_projection": False,
        "market_total": 59.5,
    }


def test_module_exists_and_declares_event_page_only_contract() -> None:
    assert MODULE.exists()
    source = MODULE.read_text(encoding="utf-8")
    assert "fetch_fanduel_event_page" in source
    assert "fetch_fanduel_ncaaf_page" not in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "MAY_MODIFY_PROJECTION = False" in source
    assert "MAY_MODIFY_OTHER_SPORTS = False" in source
    assert "No team-name or fuzzy matching is introduced." in source


def test_exact_event_page_allows_missing_market_event_id_and_selects_canonical_markets() -> None:
    import cfb_game_total_page1_v2_step4_event_page_side_market_repair_v1 as repair

    parsed = repair.parse_event_page_side_markets(_event_page(), "fd-123")
    assert parsed == {
        "away_spread": 3.5,
        "home_spread": -3.5,
        "away_spread_price": -110,
        "home_spread_price": -110,
        "away_moneyline": 155,
        "home_moneyline": -188,
        "provider_game_id": "fd-123",
    }


def test_present_mismatched_event_id_is_rejected() -> None:
    import cfb_game_total_page1_v2_step4_event_page_side_market_repair_v1 as repair

    payload = {
        "attachments": {
            "markets": {
                "ml": _market(
                    "Moneyline",
                    1,
                    event_id="wrong",
                    runners=[_runner("AWAY", 155), _runner("HOME", -188)],
                ),
                "sp": _market(
                    "Spread",
                    1,
                    event_id="wrong",
                    runners=[_runner("AWAY", -110, 3.5), _runner("HOME", -110, -3.5)],
                ),
            }
        }
    }
    assert repair.parse_event_page_side_markets(payload, "fd-123") is None


def test_verified_provider_id_drives_exact_event_page_enrichment() -> None:
    import cfb_game_total_page1_v2_step4_event_page_side_market_repair_v1 as repair

    calls = []

    def loader(provider_id: str):
        calls.append(provider_id)
        return _event_page(provider_id)

    def forbidden_fallback(_game):
        raise AssertionError("fallback should not run when exact event page is valid")

    out = repair.enrich_verified_side_market(
        _verified_game(),
        event_page_loader=loader,
        fallback_enricher=forbidden_fallback,
    )
    assert calls == ["fd-123"]
    assert out["verified_away_spread"] == 3.5
    assert out["verified_home_spread"] == -3.5
    assert out["verified_away_moneyline"] == 155
    assert out["verified_home_moneyline"] == -188
    assert out["verified_side_market_provider_event_id"] == "fd-123"
    assert out["verified_side_market_projection_weight"] == 0.0
    assert out["market_total"] == 59.5


def test_event_page_transport_failure_fails_closed_to_frozen_fallback() -> None:
    import cfb_game_total_page1_v2_step4_event_page_side_market_repair_v1 as repair

    def outage(_provider_id: str):
        raise TimeoutError("provider unavailable")

    def fallback(game):
        return {**dict(game), "fallback_used": True}

    out = repair.enrich_verified_side_market(
        _verified_game(),
        event_page_loader=outage,
        fallback_enricher=fallback,
    )
    assert out["fallback_used"] is True
    assert "verified_away_moneyline" not in out
    assert "verified_away_spread" not in out


def test_no_thaw_adapter_installs_repair_and_app_stays_frozen() -> None:
    adapter = MARKET_ADAPTER.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    import_line = (
        "from cfb_game_total_page1_v2_step4_event_page_side_market_repair_v1 "
        "import install_event_page_side_market_repair"
    )
    assert import_line in adapter
    assert "install_event_page_side_market_repair()" in adapter
    assert import_line not in app
    assert "install_event_page_side_market_repair()" not in app
