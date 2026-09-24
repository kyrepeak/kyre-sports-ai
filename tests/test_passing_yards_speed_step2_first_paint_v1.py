from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import nfl_passing_yards_hub_v78 as v78
import streamlit_memory_lazy_router_v229 as v229


CAPTURED = {
    "identity": [
        '<div class="kpass29-name">Michael Penix Jr.</div><div class="kpass29-meta">ATL • QB</div>',
        '<div class="kpass29-name">Jordan Love</div><div class="kpass29-meta">GB • QB</div>',
    ],
    "projection": [
        '<div><b>241.2</b><span>Baseline Pass Yards</span><b>32.1</b><span>Expected Attempts</span><b>7.51</b><span>Expected YPA</span></div>',
        '<div><b>276.4</b><span>Baseline Pass Yards</span><b>34.8</b><span>Expected Attempts</span><b>7.94</b><span>Expected YPA</span></div>',
    ],
    "market": [
        '<div><b>239.5</b><span>Market Line</span><b>LEAN OVER</b><span>Final Lean</span></div>',
        '<div><b>274.5</b><span>Market Line</span><b>LEAN OVER</b><span>Final Lean</span></div>',
    ],
}


def test_speed_step2_is_presentation_only_over_frozen_v77() -> None:
    assert v78.FROZEN_PRIOR == "nfl_passing_yards_hub_v77"
    assert v78.SPEED_PHASE_STEP == 2
    assert v78.PRESENTATION_ONLY is True
    assert v78.MAY_MODIFY_PROJECTION is False
    assert v78.MAY_MODIFY_CONTEXT_MATH is False
    assert v78.MAY_MODIFY_PROBABILITY is False
    assert v78.MAY_MODIFY_MARKET_MATH is False
    assert v78.MAY_MODIFY_DATA_PROVIDER_BEHAVIOR is False
    assert v78.MAY_MODIFY_WIDGET_KEYS is False
    assert v78.MAY_MODIFY_NAVIGATION_STATE is False
    assert v78.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert v78.STAKE_SIZING_ENABLED is False


def test_speed_step2_builds_bounded_verified_preview_hints() -> None:
    summary = v78._summary_from_captured(CAPTURED, 1)
    assert summary["name"] == "Jordan Love"
    assert summary["meta"] == "GB • QB"
    assert summary["projection"] == "276.4"
    assert summary["attempts"] == "34.8"
    assert summary["ypa"] == "7.94"
    assert summary["line"] == "274.5"
    assert summary["lean"] == "LEAN OVER"

    href = v78._url_with_hints(
        "/?ks_jump_sport=NFL&ks_jump_market=Passing+Yards&ks_qb_slot=2",
        summary,
    )
    query = parse_qs(urlsplit(href).query)
    assert query["ks_qb_slot"] == ["2"]
    assert query["ks_py_hint_name"] == ["Jordan Love"]
    assert query["ks_py_hint_projection"] == ["276.4"]
    assert query["ks_py_hint_line"] == ["274.5"]


def test_speed_step2_first_paint_contains_key_stats_and_is_small() -> None:
    summary = v78._summary_from_captured(CAPTURED, 1)
    html = v78.build_fast_first_paint(2, summary)
    assert 'data-passing-yards-speed-first-paint="v78"' in html
    assert "Jordan Love" in html
    assert "276.4" in html
    assert "34.8" in html
    assert "7.94" in html
    assert "274.5" in html
    assert "LEAN OVER" in html
    assert len(html.encode("utf-8")) < 12000


def test_speed_step2_router_advances_only_passing_yards_and_fails_closed() -> None:
    assert v229.FROZEN_ROUTER == "streamlit_memory_lazy_router_v228"
    assert v229.PASSING_HUB == "nfl_passing_yards_hub_v78"
    assert v229.FALLBACK_HUB == "nfl_passing_yards_hub_v77"
    assert v229.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0

    calls = []

    def ok(name):
        calls.append(name)
        return object()

    def bad(name):
        calls.append(name)
        raise ImportError(name)

    assert v229._speed_hub_importable(ok) is True
    assert v229._speed_hub_importable(bad) is False
    assert calls == [v229.PASSING_HUB, v229.PASSING_HUB]
