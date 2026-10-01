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
            "projection_weight": 0.0,
            "sportsbook_projection_weight": 0.0,
            "may_modify_probability": False,
            "may_modify_ranking": False,
            "may_modify_selection": False,
            "api2_used": False,
        },
        "why": "Verified reason",
        "benefit": "Verified benefit",
        "history_rows": [],
        "meetings": 0,
        "history_status": "VERIFIED_NO_HISTORY_AFTER_SOURCE_EXHAUSTION",
        "source_count_attempted": 2,
        "no_history_claim_allowed": True,
        "offense_research": {},
        "defense_pace_research": {},
        "benefits_risks": {"benefits": [], "risks": []},
        "source_freshness_audit": {},
    }


def _surface(monkeypatch):
    monkeypatch.setattr(
        repair.page,
        "_detail_card",
        lambda row, detail: (
            '<div data-testid="cfb-top-picks-market-reasoning-1" '
            'data-market="MONEYLINE" data-reasoning-status="READY">'
            "Market-Aware Football Reasoning</div>"
        ),
    )


def test_ready_live_reasoning_contract_passes(monkeypatch):
    _surface(monkeypatch)
    result = repair._validate_reasoning(_row(), _detail())
    assert result["status"] == "READY"
    assert result["rank"] == 1
    assert result["market"] == "MONEYLINE"


def test_unavailable_required_signal_fails_closed(monkeypatch):
    _surface(monkeypatch)
    detail = _detail()
    key = reasoning.REQUIRED_SIGNALS["MONEYLINE"][0]
    detail["market_reasoning"]["signals"][key]["status"] = "UNAVAILABLE"
    with pytest.raises(AssertionError, match="STEP3_SIGNAL_NOT_READY"):
        repair._validate_reasoning(_row(), detail)


def test_source_conflict_required_signal_fails_closed(monkeypatch):
    _surface(monkeypatch)
    detail = _detail()
    key = reasoning.REQUIRED_SIGNALS["MONEYLINE"][-1]
    detail["market_reasoning"]["signals"][key]["status"] = "SOURCE_CONFLICT_REVIEW"
    with pytest.raises(AssertionError, match="STEP3_SIGNAL_NOT_READY"):
        repair._validate_reasoning(_row(), detail)


def test_partial_block_status_fails_closed(monkeypatch):
    _surface(monkeypatch)
    detail = _detail()
    detail["market_reasoning"]["status"] = "PARTIAL"
    with pytest.raises(AssertionError, match="STEP3_REASONING_NOT_READY"):
        repair._validate_reasoning(_row(), detail)


def test_step3_is_verifier_only_and_keeps_projection_firewalls():
    assert repair.API2_USED is False
    assert repair.MAY_MODIFY_PROJECTION is False
    assert repair.MAY_MODIFY_RANKING is False
    assert repair.MAY_MODIFY_PROBABILITY is False
    assert repair.MAY_MODIFY_SELECTION is False
    assert repair.SPORTSBOOK_PROJECTION_WEIGHT == 0.0
    assert repair.MARKET_REASONING_PROJECTION_WEIGHT == 0.0
