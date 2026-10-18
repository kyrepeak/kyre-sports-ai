"""MONSTER CFB Game Total Page 2 — same-book market completeness R1.

Additive successor above frozen Visual Cleanup R4. It preserves exact selected-game
identity and all frozen model/probability/recommendation behavior while carrying
one verified complete sportsbook quote (moneyline + spread + total) onto Page 2.
A quote is accepted only when the existing R5 market owner can prove all three
market families for the same named book. Partial books are never stitched.
"""
from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

import streamlit as st

import cfb_game_total_page2_complete_repair_r1 as base
import cfb_game_total_page2_visual_cleanup_r4 as prior
import streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1 as cfb_router

MODEL_VERSION = "MONSTER CFB GAME TOTAL PAGE2 MARKET COMPLETENESS R1"
ACTIVE_MARKER = "MONSTER_CFB_GAME_TOTAL_PAGE2_MARKET_COMPLETENESS_R1_ACTIVE"
FREEZE_TOKEN = "MONSTER_CFB_GAME_TOTAL_PAGE2_MARKET_COMPLETENESS_R1_FROZEN"
FROZEN_PARENT = "cfb_game_total_page2_visual_cleanup_r4"
SAME_PAGE_ROUTE = "cfb_game_total_page2_market_completeness_r1"
MARKET = prior.MARKET
SELECTED_GAME_ONLY = True
MULTI_SOURCE_REQUIRED = True
SAME_BOOK_COMPLETE_QUOTE_REQUIRED = True
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS_ADDED = 0

_BASE_APPLY_FEATURED_MARKET = base._apply_featured_market
_BASE_RENDER_SOURCE_STRIP = base._render_source_strip

_MARKET_CSS = """
<style id="gtp2-market-completeness-r1-css">
.gtp2mcr1{max-width:1180px;margin:0 auto 18px;padding:13px;border:1px solid rgba(83,198,255,.30);border-radius:16px;background:linear-gradient(180deg,rgba(7,28,43,.96),rgba(5,18,29,.98));color:#f7fbff}.gtp2mcr1-head{display:flex;align-items:end;justify-content:space-between;gap:10px;margin-bottom:10px}.gtp2mcr1-head span{display:block;color:#78ddff;font-size:8px;font-weight:1000;letter-spacing:.12em;text-transform:uppercase}.gtp2mcr1-head strong{display:block;margin-top:3px;font-size:16px}.gtp2mcr1-head small{color:#86a7b9;font-size:7px;font-weight:850}.gtp2mcr1-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px}.gtp2mcr1-cell{padding:10px 8px;border:1px solid rgba(84,163,196,.17);border-radius:10px;background:rgba(7,29,43,.76);text-align:center}.gtp2mcr1-cell span{display:block;color:#7798aa;font-size:6px;font-weight:950;letter-spacing:.08em;text-transform:uppercase}.gtp2mcr1-cell b{display:block;margin-top:5px;color:#f8fdff;font-size:13px}.gtp2mcr1-note{margin-top:9px;color:#809eaf;font-size:7px;font-weight:760;line-height:1.45}@media(max-width:700px){.gtp2mcr1-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.gtp2mcr1-head{align-items:start;flex-direction:column}.gtp2mcr1-cell:last-child{grid-column:1/-1}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _american(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "Unavailable"
    shown: int | float = int(number) if number.is_integer() else number
    return f"+{shown}" if number > 0 else str(shown)


def _spread(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "Unavailable"
    return f"{number:+g}"


def _total(value: Any) -> str:
    number = _num(value)
    return "Unavailable" if number is None else f"{number:g}"


def _apply_complete_market(
    display_game: Mapping[str, Any],
    selected_game: Mapping[str, Any],
) -> dict[str, Any]:
    """Preserve frozen R1 enrichment, then promote one complete same-book quote."""
    inherited = _BASE_APPLY_FEATURED_MARKET(display_game, selected_game)
    out = dict(inherited) if isinstance(inherited, Mapping) else dict(display_game)
    observations = [
        row
        for row in selected_game.get("market_observations") or []
        if isinstance(row, Mapping)
    ]
    quote, quotes = base.market_truth.select_featured_book_quote(observations)
    if quote is None:
        return out

    out.update(
        {
            "market_sportsbook": quote.get("book"),
            "verified_total_market_provider": quote.get("book"),
            "away_moneyline": quote.get("away_moneyline"),
            "home_moneyline": quote.get("home_moneyline"),
            "away_spread": quote.get("away_spread"),
            "home_spread": quote.get("home_spread"),
            "market_total": quote.get("total"),
            "verified_market_total": quote.get("total"),
            "market_observed_at_utc": quote.get("observed_at_utc"),
            "market_transports": list(quote.get("transports") or []),
            "market_quote_count": len(quotes),
            "market_books": sorted(quotes),
            "market_complete_same_book": True,
            "market_identity_verified": True,
            "market_projection_weight": 0.0,
            "market_context_only": True,
            "market_may_modify_projection": False,
            "market_source": "R5 same-book complete quote over existing Action Network + ESPN/Kyre observations",
        }
    )
    return out


def _market_snapshot_html(display_game: Mapping[str, Any]) -> str:
    complete = display_game.get("market_complete_same_book") is True
    if complete:
        book = _clean(display_game.get("market_sportsbook")) or "Verified named book"
        quote_count = int(display_game.get("market_quote_count") or 0)
        observed = _clean(display_game.get("market_observed_at_utc")) or "timestamp unavailable"
        away_moneyline = display_game.get("away_moneyline")
        home_moneyline = display_game.get("home_moneyline")
        away_spread = display_game.get("away_spread")
        home_spread = display_game.get("home_spread")
        market_total = display_game.get("market_total")
        note = f"{quote_count} complete same-book quote{'s' if quote_count != 1 else ''} verified • {observed}"
    else:
        book = "No complete named book"
        away_moneyline = None
        home_moneyline = None
        away_spread = None
        home_spread = None
        market_total = None
        note = "No single named sportsbook currently has verified moneyline + spread + total together; fields remain unavailable rather than mixing books."

    return (
        _MARKET_CSS
        + '<section class="gtp2mcr1" data-testid="gtp2-market-complete-r1">'
        + '<div class="gtp2mcr1-head"><div><span>Verified Market Snapshot</span><strong>'
        + escape(book)
        + '</strong></div><small>SAME-BOOK ML + SPREAD + TOTAL</small></div>'
        + '<div class="gtp2mcr1-grid">'
        + '<div class="gtp2mcr1-cell"><span>Away ML</span><b>'
        + escape(_american(away_moneyline))
        + '</b></div>'
        + '<div class="gtp2mcr1-cell"><span>Home ML</span><b>'
        + escape(_american(home_moneyline))
        + '</b></div>'
        + '<div class="gtp2mcr1-cell"><span>Away Spread</span><b>'
        + escape(_spread(away_spread))
        + '</b></div>'
        + '<div class="gtp2mcr1-cell"><span>Home Spread</span><b>'
        + escape(_spread(home_spread))
        + '</b></div>'
        + '<div class="gtp2mcr1-cell"><span>O/U Total</span><b>'
        + escape(_total(market_total))
        + '</b></div></div>'
        + '<div class="gtp2mcr1-note">'
        + escape(note)
        + ' • sportsbook data remains context-only with 0.0% projection influence.</div></section>'
    )


def _render_source_strip_with_market_snapshot(display_game: Mapping[str, Any]) -> None:
    _BASE_RENDER_SOURCE_STRIP(display_game)
    st.markdown(_market_snapshot_html(display_game), unsafe_allow_html=True)


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    """Delegate to frozen R4 while temporarily installing completeness hooks."""
    original_apply = base._apply_featured_market
    original_strip = base._render_source_strip
    base._apply_featured_market = _apply_complete_market
    base._render_source_strip = _render_source_strip_with_market_snapshot
    try:
        return prior.render_game_total_hub(section_header, status_info, team_logo, h)
    finally:
        base._apply_featured_market = original_apply
        base._render_source_strip = original_strip


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None):
    if market != MARKET:
        raise ValueError(f"Page 2 Market Completeness R1 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


def render_selected_in_shared_shell():
    """Keep this successor as the selected-game owner through the shared-shell hop."""
    with cfb_router._ROUTE_POINTER_LOCK:
        original_page1 = cfb_router.PAGE1_NATIVE_ROUTE
        cfb_router.PAGE1_NATIVE_ROUTE = SAME_PAGE_ROUTE
        try:
            return cfb_router._render_page1_in_shared_shell()
        finally:
            cfb_router.PAGE1_NATIVE_ROUTE = original_page1


def build_stage7_clean_html(*args, **kwargs):
    return prior.build_stage7_clean_html(*args, **kwargs)


__all__ = [
    "ACTIVE_MARKER",
    "FREEZE_TOKEN",
    "FROZEN_PARENT",
    "MARKET",
    "MODEL_VERSION",
    "MULTI_SOURCE_REQUIRED",
    "SAME_BOOK_COMPLETE_QUOTE_REQUIRED",
    "SAME_PAGE_ROUTE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_apply_complete_market",
    "_market_snapshot_html",
    "_render_source_strip_with_market_snapshot",
    "build_stage7_clean_html",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_selected_in_shared_shell",
]
