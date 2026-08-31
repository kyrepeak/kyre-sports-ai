"""Step 5.3 presentation-only FanDuel market probability layer for MLB Daily Picks.

Builds on Step 5.2's exact-ID raw market context. It derives raw implied probability,
two-way hold, and proportional no-vig fair probability for Moneyline, Run Line, and
Total. It never changes the production model probability, projection, Pick Strength,
simulation, ranking, selection, persistence, or wagering behavior.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import mlb_daily_game_picks_live_market_context_v1 as step52
import mlb_daily_game_picks_v217 as v217
from sports_api.mlb_market_probability_v1 import derive_market_probability_contexts
from sports_api.mlb_official_game_id_join_v1 import canonical_official_game_id

VERSION = "MLB DAILY PICKS STEP 5.3 • FANDUEL IMPLIED + NO-VIG MARKET PROBABILITY"
_STATE_KEY = "mlb_step5_3_market_probability_v1"


def _pct(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number * 100.0:.1f}%"


def refresh_market_probability_layer(
    games_df,
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Refresh Step 5.2 first, then derive Step 5.3 without mutating model state."""
    step52_state = step52.install_live_market_context(games_df, payload=payload)
    try:
        derived = derive_market_probability_contexts(step52_state)
        derived["available"] = bool(step52_state.get("available"))
        derived["collected_at_utc"] = step52_state.get("collected_at_utc")
    except Exception as exc:
        derived = {
            "available": False,
            "data_type": "mlb_market_probability_context_v1",
            "schema_version": 1,
            "source": "FanDuel",
            "probability_method": "proportional_two_way_no_vig",
            "match_method": "official_mlb_game_id_exact",
            "fallback_matching_used": False,
            "contexts_by_game_id": {},
            "error_type": type(exc).__name__,
        }
    st.session_state[_STATE_KEY] = derived
    return derived


def _probability_context_for_candidate(candidate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    state = st.session_state.get(_STATE_KEY) or {}
    contexts = state.get("contexts_by_game_id") or {}
    try:
        game_id = canonical_official_game_id(candidate.get("game_pk"))
    except Exception:
        return None
    context = contexts.get(game_id)
    return context if isinstance(context, Mapping) else None


def _probability_board_html(context: Mapping[str, Any]) -> str:
    ml = context.get("moneyline") or {}
    rl = context.get("run_line") or {}
    total = context.get("total") or {}
    game_id = escape(str(context.get("official_game_id") or ""))

    ml_away = ml.get("away") or {}
    ml_home = ml.get("home") or {}
    rl_away = rl.get("away") or {}
    rl_home = rl.get("home") or {}
    tot_over = total.get("over") or {}
    tot_under = total.get("under") or {}

    return (
        '<div style="border:1px solid #31506a;background:#07121d;border-radius:10px;'
        'padding:8px 9px;margin-top:6px;display:flex;flex-direction:column;gap:4px">'
        '<div style="font-size:8px;font-weight:950;color:#9bd6ff">MARKET PROBABILITY • '
        f'NO-VIG • MLB GAME {game_id}</div>'
        '<div style="font-size:8px;color:#e0edf6;font-weight:800">'
        f'ML no-vig: Away {escape(_pct(ml_away.get("no_vig_probability")))} • '
        f'Home {escape(_pct(ml_home.get("no_vig_probability")))} • '
        f'Hold {escape(_pct(ml.get("hold_probability")))}</div>'
        '<div style="font-size:8px;color:#e0edf6;font-weight:800">'
        f'RL no-vig: Away {escape(_pct(rl_away.get("no_vig_probability")))} • '
        f'Home {escape(_pct(rl_home.get("no_vig_probability")))} • '
        f'Hold {escape(_pct(rl.get("hold_probability")))}</div>'
        '<div style="font-size:8px;color:#e0edf6;font-weight:800">'
        f'Total no-vig: Over {escape(_pct(tot_over.get("no_vig_probability")))} • '
        f'Under {escape(_pct(tot_under.get("no_vig_probability")))} • '
        f'Hold {escape(_pct(total.get("hold_probability")))}</div>'
        '<div style="font-size:7px;color:#82a8bd">Derived from attached FanDuel odds only • model probability and Pick Strength unchanged</div>'
        '</div>'
    )


def _decision_card_step5_3(c, rank, games_df, ts, snap, baseline, risk):
    html = step52._decision_card_step5_2(c, rank, games_df, ts, snap, baseline, risk)
    context = _probability_context_for_candidate(c)
    if context is None:
        return html
    board = _probability_board_html(context)
    marker = '<div class="kui-score">'
    if marker in html:
        return html.replace(marker, board + marker, 1)
    return html + board


def _why_sections_step5_3(c, games_df, snap, ts, baseline, risk):
    sections = [
        (title, list(lines or []))
        for title, lines in step52._why_sections_step5_2(c, games_df, snap, ts, baseline, risk)
    ]
    context = _probability_context_for_candidate(c)
    if context is None:
        line = (
            "Step 5.3 no-vig market probability is unavailable for this game right now. "
            "The raw Step 5.2 FanDuel board remains display-only and no probability is fabricated."
        )
    else:
        ml = context.get("moneyline") or {}
        rl = context.get("run_line") or {}
        total = context.get("total") or {}
        line = (
            f"FanDuel no-vig market probability (MLB game {context.get('official_game_id')}): "
            f"Moneyline away {_pct((ml.get('away') or {}).get('no_vig_probability'))} / "
            f"home {_pct((ml.get('home') or {}).get('no_vig_probability'))} "
            f"(hold {_pct(ml.get('hold_probability'))}); "
            f"Run Line away {_pct((rl.get('away') or {}).get('no_vig_probability'))} / "
            f"home {_pct((rl.get('home') or {}).get('no_vig_probability'))} "
            f"(hold {_pct(rl.get('hold_probability'))}); "
            f"Total over {_pct((total.get('over') or {}).get('no_vig_probability'))} / "
            f"under {_pct((total.get('under') or {}).get('no_vig_probability'))} "
            f"(hold {_pct(total.get('hold_probability'))}). "
            "These probabilities are derived from the sportsbook prices only and do not rewrite the production model."
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


def install_market_probability_layer(
    games_df,
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Install Step 5.3 on top of the certified Step 5.2 presentation layer."""
    state = refresh_market_probability_layer(games_df, payload=payload)
    v217._decision_card_v217 = _decision_card_step5_3
    v217._why_sections = _why_sections_step5_3
    return state


__all__ = [
    "VERSION",
    "install_market_probability_layer",
    "refresh_market_probability_layer",
]
