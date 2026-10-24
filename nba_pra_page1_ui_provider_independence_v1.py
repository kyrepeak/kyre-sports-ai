"""Presentation overlay for NBA PRA provider-independence semantics."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Mapping, Sequence

from nba_pra_page1_ui_v2 import *  # noqa: F403
import nba_pra_page1_ui_v2 as prior


def dashboard_kpis(items: Sequence[Mapping[str, Any]], *, now_utc: datetime | None = None) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    over_edges = [
        float((item.get("grade") or {})["edge"])
        for item in items
        if (item.get("grade") or {}).get("lean") == "OVER" and (item.get("grade") or {}).get("edge") is not None
    ]
    under_edges = [
        float((item.get("grade") or {})["edge"])
        for item in items
        if (item.get("grade") or {}).get("lean") == "UNDER" and (item.get("grade") or {}).get("edge") is not None
    ]
    market_items = [item for item in items if (item.get("featured_quote") or {}).get("line") is not None]
    fresh = 0
    for item in market_items:
        _label, state = prior.freshness_label((item.get("featured_quote") or {}).get("observed_at_utc"), now)
        if state == "fresh":
            fresh += 1
    return {
        "players_tracked": len(items),
        "markets_verified": len(market_items),
        "best_over_edge": max(over_edges) if over_edges else None,
        "best_under_edge": min(under_edges) if under_edges else None,
        "fresh_quotes": fresh,
    }


def build_kpi_strip_html(kpis: Mapping[str, Any]) -> str:
    over = f"+{float(kpis['best_over_edge']):.1f}" if kpis.get("best_over_edge") is not None else "—"
    under = f"{float(kpis['best_under_edge']):.1f}" if kpis.get("best_under_edge") is not None else "—"
    players = int(kpis.get("players_tracked") or 0)
    markets = int(kpis.get("markets_verified") or 0)
    freshness = f"{int(kpis.get('fresh_quotes') or 0)}/{markets}" if markets else "0/0"
    return (
        '<div class="np3-kpi-strip">'
        f'<div><small>PLAYERS</small><b>{players}</b><span>tracked</span></div>'
        f'<div><small>MARKETS</small><b>{markets}</b><span>verified PRA</span></div>'
        f'<div><small>BEST OVER</small><b>{over}</b><span>model edge</span></div>'
        f'<div><small>BEST UNDER</small><b>{under}</b><span>model edge</span></div>'
        f'<div><small>FRESH</small><b>{freshness}</b><span>≤120 sec</span></div>'
        '</div>'
    )


def _market_state_label(value: Any) -> str:
    state = str(value or "").strip().upper()
    labels = {
        "NO_APPROVED_PROVIDER_CURRENTLY_OFFERS_PRA": "No approved provider currently offers PRA",
        "MARKET_NOT_POSTED_YET": "Market not posted yet",
        "MARKET_NOT_OFFERED": "Market not offered",
        "LINE_CURRENTLY_OFF_BOARD": "Line currently off board",
        "MARKET_SUSPENDED": "Market suspended",
        "MARKET_CLOSED": "Market closed",
    }
    return labels.get(state, "No verified sportsbook PRA quote")


def build_market_row_html(item: Mapping[str, Any], *, now_utc: datetime | None = None) -> str:
    html = prior.build_market_row_html(item, now_utc=now_utc)
    if item.get("quotes"):
        return html
    label = escape(_market_state_label(item.get("market_state")))
    return html.replace("No verified sportsbook quote", label)


__all__ = [name for name in dir(prior) if not name.startswith("_")] + [
    "dashboard_kpis",
    "build_kpi_strip_html",
    "build_market_row_html",
]
