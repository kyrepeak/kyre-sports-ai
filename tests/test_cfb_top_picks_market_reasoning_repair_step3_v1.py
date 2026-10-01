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
            "may_modify_projection": False,
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

class _FakeHeading:
    def __init__(self, *, count: int = 1, visible: bool = True, text: str = repair.PUBLIC_HEADING):
        self._count = count
        self._visible = visible
        self._text = text

    def count(self) -> int:
        return self._count

    @property
    def first(self):
        return self

    def is_visible(self) -> bool:
        return self._visible

    def text_content(self, timeout: int = 5000) -> str:
        return self._text


class _FakeReasoningLocator:
    def __init__(self, heading: _FakeHeading):
        self.heading = heading

    def locator(self, selector: str):
        assert selector == "h4"
        return self.heading


def test_public_heading_contract_requires_visible_exact_h4():
    loc = _FakeReasoningLocator(_FakeHeading())
    assert repair._validate_public_heading(loc) == repair.PUBLIC_HEADING


def test_public_heading_contract_rejects_hidden_h4():
    loc = _FakeReasoningLocator(_FakeHeading(visible=False))
    with pytest.raises(AssertionError, match="STEP3_PUBLIC_HEADING_NOT_VISIBLE"):
        repair._validate_public_heading(loc)


def test_public_heading_contract_rejects_wrong_h4_text():
    loc = _FakeReasoningLocator(_FakeHeading(text="Market reasoning"))
    with pytest.raises(AssertionError, match="STEP3_PUBLIC_HEADING_TEXT"):
        repair._validate_public_heading(loc)

class _FakeMarker:
    def __init__(self, *, count: int = 1, text: str = repair.page.PAGE_MARKER):
        self._count = count
        self._text = text

    def count(self) -> int:
        return self._count

    @property
    def first(self):
        return self

    def text_content(self, timeout: int = 5000) -> str:
        return self._text


class _FakeFrame:
    def __init__(self, marker: _FakeMarker):
        self.marker = marker

    def locator(self, selector: str):
        assert selector == '[data-testid="cfb-top-picks-research-v2-step9-marker"]'
        return self.marker


def test_public_v9_marker_contract_reads_hidden_dom_marker():
    frame = _FakeFrame(_FakeMarker())
    assert repair._validate_public_v9_marker(frame) == repair.page.PAGE_MARKER


def test_public_v9_marker_contract_rejects_missing_marker():
    frame = _FakeFrame(_FakeMarker(count=0))
    with pytest.raises(AssertionError, match="STEP3_PUBLIC_V9_MARKER_COUNT"):
        repair._validate_public_v9_marker(frame)


def test_public_v9_marker_contract_rejects_wrong_marker_text():
    frame = _FakeFrame(_FakeMarker(text="stale-marker"))
    with pytest.raises(AssertionError, match="STEP3_PUBLIC_V9_MARKER_TEXT"):
        repair._validate_public_v9_marker(frame)

