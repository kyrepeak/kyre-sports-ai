from __future__ import annotations

import pytest

import cfb_top_picks_market_reasoning_v1 as reasoning
from devsystem import cfb_top_picks_market_reasoning_repair_step3_v1 as repair


def _row(market: str = "MONEYLINE") -> dict:
    return {
        "rank": 1,
        "event_id": "401234567",
        "away": "Away State",
        "home": "Home Tech",
        "market": market,
        "pick": "Away State",
    }


def _signal(text: str = "Verified football evidence supports this market context.") -> dict:
    return {
        "status": "VERIFIED",
        "text": text,
        "sources": ["verified source"],
        "observed_at": "2026-10-01T19:00:00+00:00",
    }


def _detail(market: str = "MONEYLINE") -> dict:
    required = list(reasoning.REQUIRED_SIGNALS[market])
    signals = {key: _signal() for key in required}
    return {
        "market_reasoning": {
            "market": market,
            "status": "READY",
            "required_signals": required,
            "signals": signals,
            "summary": "Verified market-specific football evidence is complete for this ranked pick.",
            "projection_weight": 0.0,\n            "sportsbook_projection_weight": 0.0,\n            "may_modify_projection": False,
            "may_modify_probability": False,
            "may_modify_ranking": False,
            "may_modify_selection": False,
            "api2_used": False,
        },
    }


def _surface(monkeypatch, status: str = "READY"):
    monkeypatch.setattr(
        repair.page,
        "_detail_card",
        lambda row, detail: (
            '<div data-testid="cfb-top-picks-market-reasoning-1" '
            f'data-market="MONEYLINE" data-reasoning-status="{status}">'
            "Market-Aware Football Reasoning</div>"
        ),
    )


def test_ready_live_reasoning_contract_passes(monkeypatch):
    _surface(monkeypatch)
    result = repair._validate_reasoning(_row(), _detail())
    assert result["status"] == "READY"
    assert result["history_source_conflict_disclosed"] is False


def test_unavailable_required_signal_fails_closed(monkeypatch):
    _surface(monkeypatch)
    detail = _detail()
    key = reasoning.REQUIRED_SIGNALS["MONEYLINE"][0]
    detail["market_reasoning"]["signals"][key]["status"] = "UNAVAILABLE"
    with pytest.raises(AssertionError, match="STEP3_SIGNAL_NOT_READY"):
        repair._validate_reasoning(_row(), detail)


def test_history_source_conflict_is_transparent_partial(monkeypatch):
    _surface(monkeypatch, status="PARTIAL")
    detail = _detail()
    key = repair.HISTORY_SIGNAL_BY_MARKET["MONEYLINE"]
    detail["market_reasoning"]["signals"][key] = {
        "status": "SOURCE_CONFLICT_REVIEW",
        "text": "No historical edge is claimed because independent sources disagree.",
        "sources": ["ESPN team schedules", "Winsipedia"],
        "observed_at": "2026-10-01T19:00:00+00:00",
    }
    detail["market_reasoning"]["status"] = "PARTIAL"
    result = repair._validate_reasoning(_row(), detail)
    assert result["status"] == "PARTIAL"
    assert result["history_source_conflict_disclosed"] is True


def test_non_history_source_conflict_fails_closed(monkeypatch):
    _surface(monkeypatch)
    detail = _detail()
    key = "offense_vs_defense_edge"
    detail["market_reasoning"]["signals"][key]["status"] = "SOURCE_CONFLICT_REVIEW"
    with pytest.raises(AssertionError, match="STEP3_SIGNAL_NOT_READY"):
        repair._validate_reasoning(_row(), detail)


def test_partial_without_history_conflict_fails_truth_gate(monkeypatch):
    _surface(monkeypatch, status="PARTIAL")
    detail = _detail()
    detail["market_reasoning"]["status"] = "PARTIAL"
    with pytest.raises(AssertionError, match="STEP3_REASONING_STATUS_TRUTH"):
        repair._validate_reasoning(_row(), detail)


def test_step3_is_verifier_only_and_keeps_projection_firewalls():
    assert repair.API2_USED is False
    assert repair.MAY_MODIFY_PROJECTION is False
    assert repair.MAY_MODIFY_RANKING is False
    assert repair.MAY_MODIFY_PROBABILITY is False
    assert repair.MAY_MODIFY_SELECTION is False
    assert repair.SPORTSBOOK_PROJECTION_WEIGHT == 0.0
    assert repair.MARKET_REASONING_PROJECTION_WEIGHT == 0.0
