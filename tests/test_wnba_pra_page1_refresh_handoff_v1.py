from __future__ import annotations

import importlib
from pathlib import Path


def _payload(state: str, *, cache: str = "MODEL_UNAVAILABLE") -> dict:
    return {
        "schema_version": "wnba_pra_page_snapshot_v1",
        "date": "2026-10-21",
        "season": 2026,
        "snapshot_state": state,
        "cache_state": cache,
        "refresh_required": state != "READY",
        "market_board_reads": 1,
        "consensus_averaging": False,
        "offers": [],
        "final_card": [],
    }


def test_model_unavailable_converges_to_ready_without_second_refresh(monkeypatch):
    active = importlib.import_module("wnba_pra_hub_v3618")
    reads = iter([
        _payload("MODEL_UNAVAILABLE"),
        _payload("MODEL_UNAVAILABLE"),
        _payload("READY", cache="FRESH"),
    ])
    fetch_calls: list[str] = []
    refresh_calls: list[tuple[str, bool]] = []
    rendered: list[dict] = []

    def fake_fetch(day: str, season: int = 2026):
        fetch_calls.append(day)
        return next(reads)

    def fake_refresh(day: str, *, background: bool):
        refresh_calls.append((day, background))
        return True

    monkeypatch.setattr(active, "resolve_active_slate_date", lambda: "2026-10-21")
    monkeypatch.setattr(active, "fetch_page_snapshot", fake_fetch)
    monkeypatch.setattr(active, "_refresh", fake_refresh)
    monkeypatch.setattr(active, "render_page_snapshot", lambda payload, **kwargs: rendered.append(payload))
    monkeypatch.setattr(active, "_convergence_sleep", lambda seconds: None)

    result = active.render_wnba_pra_hub()

    assert result["snapshot_state"] == "READY"
    assert result["cache_state"] == "FRESH"
    assert refresh_calls == [("2026-10-21", False)]
    assert len(fetch_calls) == 3
    assert rendered[-1]["snapshot_state"] == "READY"


def test_convergence_is_bounded_and_never_reissues_refresh(monkeypatch):
    active = importlib.import_module("wnba_pra_hub_v3618")
    fetch_calls: list[str] = []
    refresh_calls: list[tuple[str, bool]] = []
    rendered: list[dict] = []

    def fake_fetch(day: str, season: int = 2026):
        fetch_calls.append(day)
        return _payload("MODEL_UNAVAILABLE")

    def fake_refresh(day: str, *, background: bool):
        refresh_calls.append((day, background))
        return True

    monkeypatch.setattr(active, "resolve_active_slate_date", lambda: "2026-10-21")
    monkeypatch.setattr(active, "fetch_page_snapshot", fake_fetch)
    monkeypatch.setattr(active, "_refresh", fake_refresh)
    monkeypatch.setattr(active, "render_page_snapshot", lambda payload, **kwargs: rendered.append(payload))
    monkeypatch.setattr(active, "_convergence_sleep", lambda seconds: None)

    result = active.render_wnba_pra_hub()

    assert result["snapshot_state"] == "MODEL_UNAVAILABLE"
    assert refresh_calls == [("2026-10-21", False)]
    assert len(fetch_calls) == 4
    assert len(rendered) == 1


def test_v3612_preserves_frozen_contract_and_delegates_to_v3618():
    root = Path(__file__).resolve().parents[1]
    router = (root / "streamlit_memory_lazy_router_v1.py").read_text()
    compat = (root / "wnba_pra_hub_v3612.py").read_text()
    assert '_import("wnba_pra_hub_v3612")' in router
    assert 'import wnba_pra_hub_v3617 as active' in compat
    assert 'active.render_page_snapshot = _page1_final_polish.render_page_snapshot' in compat
    assert 'import wnba_pra_hub_v3618 as refresh_handoff' in compat
    assert 'return refresh_handoff.render_wnba_pra_hub' in compat
