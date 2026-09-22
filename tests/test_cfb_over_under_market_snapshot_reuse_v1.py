"""Regression tests for CFB Over/Under performance Step 5."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import types

import cfb_over_under_clean_page_v35 as page
import cfb_over_under_market_adapter_v3 as adapter
import streamlit_memory_lazy_router_v76 as router


NOW = datetime(2026, 9, 11, 17, 45, 0, tzinfo=timezone.utc)


def _payload() -> dict:
    return {
        "step": 3,
        "schema_version": "cfb_odds_v1",
        "captured_at_utc": "2026-09-11T17:44:00+00:00",
        "source": "test",
        "game_count": 1,
        "games": [
            {
                "game_id": "401858222",
                "provider_game_id": "provider-1",
                "game_date": "2026-09-11",
                "away_team": "Richmond",
                "home_team": "NC State",
                "sportsbook": "FanDuel",
                "market_type": "game_total",
                "total": 50.5,
                "line_status": "active",
                "line_updated_at_utc": "2026-09-11T17:44:00+00:00",
                "identity_verified": True,
            }
        ],
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
        "diagnostics": {
            "complete_identity_coverage": True,
            "unmatched_market_rows": 0,
            "synthetic_official_ids": False,
            "fuzzy_matching": False,
        },
    }


def _green_diag() -> dict:
    return {
        "status": "GREEN",
        "requested_date": "2026-09-11",
        "sportsbook": "FanDuel",
        "game_count": 1,
        "identity_verified_rows": 1,
        "projection_weight": 0.0,
        "market_context_only": True,
        "may_modify_projection": False,
        "error": "",
    }


def _reset_snapshot_cache() -> None:
    adapter._load_market_snapshot.clear()


def test_v3_cache_window_stays_inside_freshness_firewall_and_reuses_attachment():
    assert adapter.FROZEN_ADAPTER == "cfb_over_under_market_adapter_v2"
    assert adapter.SNAPSHOT_CACHE_TTL_SECONDS == 240.0
    assert adapter.SNAPSHOT_CACHE_TTL_SECONDS < adapter.MAX_MARKET_AGE_SECONDS
    assert adapter.attach_market_lines is adapter.frozen.attach_market_lines
    assert adapter.market_line is adapter.frozen.market_line


def test_successful_snapshot_is_reused_but_freshness_is_checked_each_access(monkeypatch):
    calls = {"load": 0, "validate": 0}

    def fake_load(target_date, sportsbook):
        calls["load"] += 1
        return _payload(), _green_diag()

    real_validate = adapter.frozen.validate_fresh_payload

    def counted_validate(payload, *, requested_sportsbook, now_utc=None):
        calls["validate"] += 1
        return real_validate(
            payload,
            requested_sportsbook=requested_sportsbook,
            now_utc=now_utc,
        )

    monkeypatch.setattr(adapter.frozen, "load_odds_for_date", fake_load)
    monkeypatch.setattr(adapter.frozen, "validate_fresh_payload", counted_validate)
    monkeypatch.setattr(adapter, "_utc_now", lambda: NOW)
    _reset_snapshot_cache()
    try:
        first_payload, first_diag = adapter.load_odds_for_date("2026-09-11", "FanDuel")
        second_payload, second_diag = adapter.load_odds_for_date("2026-09-11", "FanDuel")
    finally:
        _reset_snapshot_cache()

    assert calls["load"] == 1
    assert calls["validate"] == 2
    assert first_payload == second_payload
    assert first_diag["status"] == second_diag["status"] == "GREEN"
    assert second_diag["freshness_revalidated_on_access"] is True
    assert second_diag["snapshot_cache_ttl_seconds"] == 240.0
    assert second_diag["projection_weight"] == 0.0
    assert second_diag["may_modify_projection"] is False


def test_cached_snapshot_that_ages_stale_is_refreshed_then_fails_closed(monkeypatch):
    calls = {"load": 0}
    clock = {"now": NOW}

    def fake_load(target_date, sportsbook):
        calls["load"] += 1
        return _payload(), _green_diag()

    monkeypatch.setattr(adapter.frozen, "load_odds_for_date", fake_load)
    monkeypatch.setattr(adapter, "_utc_now", lambda: clock["now"])
    _reset_snapshot_cache()
    try:
        fresh_payload, fresh_diag = adapter.load_odds_for_date("2026-09-11", "FanDuel")
        assert fresh_payload["game_count"] == 1
        assert fresh_diag["status"] == "GREEN"
        assert calls["load"] == 1

        clock["now"] = NOW + timedelta(minutes=7)
        stale_payload, stale_diag = adapter.load_odds_for_date("2026-09-11", "FanDuel")
    finally:
        _reset_snapshot_cache()

    assert calls["load"] == 2
    assert stale_payload["games"] == []
    assert stale_payload["game_count"] == 0
    assert stale_diag["status"] == "STALE"
    assert stale_diag["freshness_status"] == "STALE"
    assert stale_diag["projection_weight"] == 0.0
    assert stale_diag["may_modify_projection"] is False


def test_v35_market_proxy_keeps_profiler_and_uses_v3(monkeypatch):
    expected = ({"games": [{"game_id": "401858222"}]}, {"status": "GREEN"})
    seen = {"load": 0}

    def fake_load(*args, **kwargs):
        seen["load"] += 1
        return expected

    monkeypatch.setattr(page.market_v3, "load_odds_for_date", fake_load)
    monkeypatch.setattr(page.frozen_page, "_selected_game_from_context", lambda day: {})

    result = page._MARKET_PROXY.load_odds_for_date("2026-09-11", "FanDuel")

    assert result == expected
    assert seen["load"] == 1
    assert page.ACTIVE_MARKET_ADAPTER == "cfb_over_under_market_adapter_v3"
    assert page.ACTIVE_RUNTIME_SLATE == page.frozen_page.ACTIVE_RUNTIME_SLATE


def test_v35_marker_preserves_frozen_contracts():
    marker = page._V35_MARKER
    assert "CFB O/U • CLEAN PAGE V35 ACTIVE" in marker
    assert "FRESHNESS-SAFE MARKET SNAPSHOT REUSE ACTIVE" in marker
    assert "FRESHNESS REVALIDATED EVERY ACCESS" in marker
    assert "PARALLEL ANALYSIS PREWARM ACTIVE" in marker
    assert "FUTURE SLATE COVERAGE ACTIVE" in marker
    assert "OFFICIAL ESPN IDENTITY RECOVERY" in marker
    assert "NO FUZZY MATCHING" in marker
    assert "NO SYNTHETIC IDS" in marker
    assert "FRESHNESS FIREWALL ACTIVE" in marker
    assert "0.0% SPORTSBOOK PROJECTION INFLUENCE" in marker
    assert "FROZEN V14 PROJECTION MATH PRESERVED" in marker


def test_router_v76_targets_only_v35_for_active_cfb_over_under(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        router.st,
        "session_state",
        {"ks_sport_touch": "College Football", "ks_cfb_market_touch": "Over/Under"},
    )
    module = types.SimpleNamespace(
        render_cfb_hub=lambda market, *args: seen.update({"market": market})
    )
    monkeypatch.setattr(
        router.root,
        "_import",
        lambda name: (seen.update({"module": name}) or module),
    )

    router._render_cfb_ou_direct("Over/Under")

    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v75"
    assert router.ACTIVE_PAGE == "cfb_over_under_clean_page_v35"
    assert seen == {
        "module": "cfb_over_under_clean_page_v35",
        "market": "Over/Under",
    }


def test_app_advances_to_v76_and_retains_v75_guard():
    text = Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v75 import render_app as _frozen_v75_render_app" in text
    assert "from streamlit_memory_lazy_router_v76 import render_app" in text
    assert (
        'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V76_CFB_OU_MARKET_SNAPSHOT_REUSE_2026-09-11"'
        in text
    )
    assert "frozen V14 projection math" in text
    assert "0.0% sportsbook projection influence" in text
