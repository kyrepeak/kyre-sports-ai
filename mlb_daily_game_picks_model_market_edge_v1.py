"""Step 5.4 presentation-only model-vs-market edge layer for MLB Daily Picks.

Runs strictly on top of Step 5.3. For supported full-game markets (Moneyline,
Run Line, Total), it compares the existing production model probability with the
exact-ID FanDuel no-vig probability and displays model edge, model fair odds, and
expected value at the attached FanDuel price. It does not change model math,
Pick Strength, simulation, ranking, selection, risk logic, persistence, or wagering.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import mlb_daily_game_picks_market_probability_v1 as step53
import mlb_daily_game_picks_v217 as v217
import mlb_daily_game_picks_v212 as live
from sports_api.mlb_model_market_edge_v1 import (
    MLBModelMarketEdgeError,
    model_market_edge,
)

VERSION = "MLB DAILY PICKS STEP 5.4 • MODEL VS MARKET EDGE + FAIR ODDS + EV"
_STATE_KEY = "mlb_step5_4_model_market_edge_v1"


def _pct(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number * 100.0:.1f}%"


def _pp(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number * 100.0:+.1f} pp"


def _ev(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number * 100.0:+.1f}%"


def _odds(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    rounded = int(round(number))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _game_teams(games_df, candidate: Mapping[str, Any]) -> tuple[str | None, str | None]:
    try:
        row = live._game_row(games_df, candidate.get("game_pk"))
    except Exception:
        row = None
    if row is None:
        return None, None
    return str(row.get("away_team") or "") or None, str(row.get("home_team") or "") or None


def edge_context_for_candidate(candidate: Mapping[str, Any], games_df) -> Mapping[str, Any] | None:
    """Return one read-only Step 5.4 context or None when it cannot be proven safely."""
    try:
        market_context = step53._probability_context_for_candidate(candidate)
        if not isinstance(market_context, Mapping):
            return None
        away_team, home_team = _game_teams(games_df, candidate)
        context = model_market_edge(
            candidate,
            market_context,
            away_team=away_team,
            home_team=home_team,
        )
    except (MLBModelMarketEdgeError, Exception):
        return None
    return context


def _edge_board_html(context: Mapping[str, Any]) -> str:
    return (
        '<div style="border:1px solid #385f75;background:#081520;border-radius:10px;'
        'padding:8px 9px;margin-top:6px;display:flex;flex-direction:column;gap:4px">'
        '<div style="font-size:8px;font-weight:950;color:#9bd6ff">MODEL vs MARKET • STEP 5.4</div>'
        '<div style="font-size:8px;color:#e0edf6;font-weight:800">'
        f'Model {_pct(context.get("model_probability"))} • '
        f'FanDuel no-vig {_pct(context.get("market_no_vig_probability"))} • '
        f'Edge {escape(_pp(context.get("edge_probability")))}</div>'
        '<div style="font-size:8px;color:#e0edf6;font-weight:800">'
        f'FanDuel {escape(_odds(context.get("market_odds")))} • '
        f'Model fair {escape(_odds(context.get("model_fair_american_odds")))} • '
        f'EV {escape(_ev(context.get("expected_value_per_unit")))}</div>'
        '<div style="font-size:7px;color:#82a8bd">Comparison only • production model probability, Pick Strength and ranking unchanged</div>'
        '</div>'
    )


def _decision_card_step5_4(c, rank, games_df, ts, snap, baseline, risk):
    html = step53._decision_card_step5_3(c, rank, games_df, ts, snap, baseline, risk)
    context = edge_context_for_candidate(c, games_df)
    if context is None:
        return html
    board = _edge_board_html(context)
    marker = '<div class="kui-score">'
    if marker in html:
        return html.replace(marker, board + marker, 1)
    return html + board


def _why_sections_step5_4(c, games_df, snap, ts, baseline, risk):
    sections = [
        (title, list(lines or []))
        for title, lines in step53._why_sections_step5_3(c, games_df, snap, ts, baseline, risk)
    ]
    context = edge_context_for_candidate(c, games_df)
    market = str(c.get("market") or "")
    if context is None:
        if market in {"Moneyline", "Run Line", "Total"}:
            line = (
                "Step 5.4 model-vs-market edge is unavailable because the selected side could not be proven against the exact-ID FanDuel context. "
                "No edge, fair odds, or EV is fabricated."
            )
        else:
            line = (
                "Step 5.4 currently compares only full-game Moneyline, Run Line, and Total because those are the markets with certified exact-ID FanDuel prices. "
                "Player-prop edge remains intentionally absent until an equally certified prop-price feed exists."
            )
    else:
        line = (
            f"Step 5.4 comparison: production model {_pct(context.get('model_probability'))} versus "
            f"FanDuel no-vig {_pct(context.get('market_no_vig_probability'))}, creating a "
            f"{_pp(context.get('edge_probability'))} model-minus-market edge. "
            f"Exact FanDuel price {_odds(context.get('market_odds'))}; model fair price "
            f"{_odds(context.get('model_fair_american_odds'))}; expected value {_ev(context.get('expected_value_per_unit'))} per unit staked. "
            "These are comparison outputs only and do not alter the production probability or Pick Strength."
        )

    out = []
    inserted = False
    for title, lines in sections:
        if title == "📈 Market context":
            lines.append(line)
            inserted = True
        out.append((title, lines))
    if not inserted:
        out.insert(1, ("📈 Market context", [line]))
    return out


def install_model_market_edge_layer(
    games_df,
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Install Step 5.4 downstream of Step 5.3 without touching selection state."""
    step53_state = step53.install_market_probability_layer(games_df, payload=payload)
    state = {
        "data_type": "mlb_model_market_edge_presentation_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "comparison_only": True,
        "step5_3_available": bool(step53_state.get("available")),
        "derived_market_context_count": int(step53_state.get("derived_context_count") or 0),
    }
    st.session_state[_STATE_KEY] = state
    v217._decision_card_v217 = _decision_card_step5_4
    v217._why_sections = _why_sections_step5_4
    return state


__all__ = [
    "VERSION",
    "edge_context_for_candidate",
    "install_model_market_edge_layer",
]
