from __future__ import annotations

from types import SimpleNamespace

import pytest

import cfb_top_picks_market_reasoning_v1 as reasoning
import cfb_top_picks_page_v9 as page_v9
from devsystem import cfb_top_picks_market_reasoning_repair_step3_v1 as repair
import streamlit_memory_lazy_router_cfb_top_picks_research_v2_step9 as router
import streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness as wnba_outer


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

def test_step9_router_propagates_v9_through_nested_page_owners(monkeypatch):
    owners = router._page_owner_chain()
    assert owners == (
        router.cfb_step8_parent,
        router.cfb_step7_parent,
        router.cfb_step6_parent,
    )

    original_pages = ("cfb_top_picks_page_v8", "cfb_top_picks_page_v7", "cfb_top_picks_page_v6")
    for owner, original in zip(owners, original_pages):
        monkeypatch.setattr(owner, "TOP_PICKS_PAGE", original)

    observed = {}

    def fake_render():
        observed["during_render"] = tuple(owner.TOP_PICKS_PAGE for owner in owners)
        return "rendered"

    monkeypatch.setattr(router.current_parent, "render_app", fake_render)

    assert router.render_app() == "rendered"
    assert observed["during_render"] == (router.TOP_PICKS_PAGE,) * 3
    assert tuple(owner.TOP_PICKS_PAGE for owner in owners) == original_pages


def test_step9_router_keeps_model_firewalls():
    assert router.TOP_PICKS_PAGE == "cfb_top_picks_page_v9"
    assert router.MAY_MODIFY_OTHER_SPORTS is False
    assert router.MAY_MODIFY_WNBA_SPEED_STEP4 is False
    assert router.MAY_MODIFY_TOP_PICKS_RANKING is False
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0



def test_step9_detail_route_guard_clears_competing_wnba_jump_and_reprimes_cfb(monkeypatch):
    query = {
        "ks_sport": "College Football",
        "ks_cfb_market": "Top Picks",
        "top_pick_detail": "401234567",
        "ks_jump_sport": "WNBA",
        "ks_jump_market": "PRA",
    }
    session = {
        "ks_sport_touch": "WNBA",
        "ks_cfb_market_touch": "Moneyline",
        "ks_wnba_market_touch": "PRA",
    }
    monkeypatch.setattr(router.st, "query_params", query)
    monkeypatch.setattr(router.st, "session_state", session)

    assert router._protect_cfb_detail_route() is True
    assert "ks_jump_sport" not in query
    assert "ks_jump_market" not in query
    assert session[router.top_picks_base.SPORT_KEY] == router.top_picks_base.CFB_SPORT_LABEL
    assert session[router.top_picks_base.CFB_MARKET_KEY] == router.top_picks_base.TOP_PICKS_MARKET
    assert session["ks_wnba_market_touch"] == "PRA"


def test_step9_detail_route_guard_does_not_touch_non_detail_route(monkeypatch):
    query = {
        "ks_sport": "College Football",
        "ks_cfb_market": "Top Picks",
        "ks_jump_sport": "WNBA",
        "ks_jump_market": "PRA",
    }
    session = {"ks_sport_touch": "WNBA"}
    monkeypatch.setattr(router.st, "query_params", query)
    monkeypatch.setattr(router.st, "session_state", session)

    assert router._protect_cfb_detail_route() is False
    assert query["ks_jump_sport"] == "WNBA"
    assert query["ks_jump_market"] == "PRA"
    assert session["ks_sport_touch"] == "WNBA"


def test_outer_wnba_shell_guard_yields_to_explicit_cfb_top_picks_detail(monkeypatch):
    query = {
        "ks_sport": "College Football",
        "ks_cfb_market": "Top Picks",
        "top_pick_detail": "401234567",
        "ks_jump_sport": "WNBA",
        "ks_jump_market": "PRA",
    }
    session = {
        "ks_sport_touch": "WNBA",
        "ks_cfb_market_touch": "Moneyline",
        "ks_wnba_market_touch": "PRA",
    }
    monkeypatch.setattr(wnba_outer.st, "query_params", query)
    monkeypatch.setattr(wnba_outer.st, "session_state", session)

    state = SimpleNamespace(page=wnba_outer.navigation.PAGE_GAME)
    assert wnba_outer._pin_deep_wnba_shell_route(state) is state

    assert "ks_jump_sport" not in query
    assert "ks_jump_market" not in query
    assert session["ks_sport_touch"] == "College Football"
    assert session["ks_cfb_market_touch"] == "Top Picks"
    assert session["ks_wnba_market_touch"] == "PRA"


def test_outer_wnba_shell_guard_keeps_real_wnba_game_pin(monkeypatch):
    query = {}
    session = {}
    monkeypatch.setattr(wnba_outer.st, "query_params", query)
    monkeypatch.setattr(wnba_outer.st, "session_state", session)

    state = SimpleNamespace(page=wnba_outer.navigation.PAGE_GAME)
    assert wnba_outer._pin_deep_wnba_shell_route(state) is state

    assert query["ks_jump_sport"] == "WNBA"
    assert query["ks_jump_market"] == "PRA"
    assert session["ks_sport_touch"] == "WNBA"
    assert session["ks_wnba_market_touch"] == "PRA"


def _real_v9_row() -> dict:
    return {
        "rank": 1,
        "event_id": "401234567",
        "away": "Away State",
        "home": "Home Tech",
        "time": "7:00 PM",
        "network": "ESPN",
        "market": "MONEYLINE",
        "pick": "Away State",
        "odds": "-115",
        "probability": 64,
        "toughness": 3,
        "toughness_label": "MEDIUM",
    }


def _real_v9_detail() -> dict:
    detail = _detail("MONEYLINE")
    detail.update(
        {
            "event_id": "401234567",
            "why": "Verified matchup context supports the selected market.",
            "benefit": "Legacy benefit input retained only for the V7 transformation.",
            "history_source": "ESPN exact-team schedule history",
            "history_status": "VERIFIED_HISTORY",
            "history_rows": [
                {"date": "2025-10-01", "away_points": 31, "home_points": 24}
            ],
            "meetings": 1,
            "source_count_verified": 1,
            "source_count_attempted": 1,
            "offense_research": {
                "status": "PARTIAL",
                "away": {},
                "home": {},
                "reasoning": ["Verified offense context remains read-only research."],
            },
            "defense_pace_research": {
                "status": "PARTIAL",
                "away": {},
                "home": {},
                "reasoning": ["Verified defense and pace context remains read-only research."],
            },
            "benefits_risks": {
                "status": "READY",
                "benefits": [
                    {
                        "text": "Verified matchup evidence supports this selection.",
                        "status": "VERIFIED",
                        "sources": ["verified source"],
                        "observed_at": "2026-10-03T20:00:00+00:00",
                    }
                ],
                "risks": [
                    {
                        "text": "Variance remains a verified risk.",
                        "status": "VERIFIED",
                        "sources": ["verified source"],
                        "observed_at": "2026-10-03T20:00:00+00:00",
                    }
                ],
            },
            "source_freshness_audit": {
                "status": "READY",
                "sources": [
                    {
                        "source": "verified source",
                        "material_fact_count": 6,
                        "observed_at": "2026-10-03T20:00:00+00:00",
                    }
                ],
                "material_fact_count": 6,
                "fallback_used_count": 0,
                "unavailable_field_count": 0,
                "violation_count": 0,
                "projection_weight": 0.0,
            },
        }
    )
    return detail


def test_real_v9_page_html_preserves_market_reasoning_exactly_once():
    row = _real_v9_row()
    detail = _real_v9_detail()
    diag = {"slate_date": "2026-10-03", "games_analyzed": 1}

    html = page_v9._page_html(
        [row],
        diag,
        "2026-10-03",
        row["event_id"],
        detail,
    )

    assert 'data-cfb-top-picks-visual="v5"' in html
    assert html.count('data-testid="cfb-top-picks-research-v2-step9-marker"') == 1
    assert 'data-expanded="true"' in html
    assert "Why This Pick" in html
    assert "Actual Matchup History" in html
    assert "Defense + Pace Research" in html
    assert "Benefits" in html
    assert "Risks" in html
    assert "Sources + Freshness" in html
    assert "Market-Aware Football Reasoning" in html
    assert html.count('data-testid="cfb-top-picks-market-reasoning-1"') == 1
    assert 'data-reasoning-status="READY"' in html
    assert "<h4>Market-Aware Football Reasoning</h4>" in html
    assert '<div class="tp4-audit">' not in html
    assert "&lt;div class=&quot;tp4-audit" not in html


def test_v9_reasoning_preservation_never_duplicates_existing_v6_surface():
    row = _real_v9_row()
    detail = _real_v9_detail()

    html = page_v9._detail_card(row, detail)

    assert html.count('data-testid="cfb-top-picks-market-reasoning-1"') == 1
    assert 'data-reasoning-status="READY"' in html
    assert "Sources + Freshness" in html
    assert '<div class="tp4-audit">' not in html
