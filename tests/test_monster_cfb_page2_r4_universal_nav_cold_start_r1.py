from __future__ import annotations

from types import SimpleNamespace

import streamlit_memory_lazy_router_universal_nav_v3 as nav3


def test_v3_cold_start_seeds_canonical_route_from_valid_query(monkeypatch) -> None:
    session: dict[str, object] = {}
    query: dict[str, object] = {"sport": "cfb", "market": "game-total"}
    fake_st = SimpleNamespace(session_state=session, query_params=query)

    monkeypatch.setattr(nav3, "st", fake_st)
    monkeypatch.setattr(nav3.prior, "render_app", lambda: "delegated")

    assert nav3.render_app() == "delegated"
    assert session["ks_universal_sport"] == "cfb"
    assert session["ks_universal_market"] == "game-total"
    assert session["ks_cfb_market"] == "Game Total"


def test_v3_valid_existing_canonical_route_remains_authoritative(monkeypatch) -> None:
    session: dict[str, object] = {
        "ks_universal_sport": "cfb",
        "ks_universal_market": "game-total",
        "ks_universal_nav_source": "canonical",
        "ks_universal_epoch": 3,
        "ks_universal_last_market_by_sport": {"cfb": "game-total"},
    }
    query: dict[str, object] = {"sport": "mlb", "market": "slate"}
    fake_st = SimpleNamespace(session_state=session, query_params=query)

    monkeypatch.setattr(nav3, "st", fake_st)
    monkeypatch.setattr(nav3.prior, "render_app", lambda: "delegated")

    assert nav3.render_app() == "delegated"
    assert session["ks_universal_sport"] == "cfb"
    assert session["ks_universal_market"] == "game-total"
