"""Step 5.2 presentation-only FanDuel market context for MLB Daily Picks V2.1.7.

The seven production models, probabilities, Pick Strength, simulations, selection
rules, and persisted state are untouched. This module reads the existing live-odds
API and decorates a Daily Picks game only after the Step 5.1 exact official MLB
game-ID join succeeds.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

import streamlit as st

import mlb_daily_game_picks_v217 as v217
from mlb_live_odds_streamlit_v1 import (
    MLBLiveOddsUIError,
    fetch_live_mlb_odds,
    format_american_odds,
    format_line,
)
from sports_api.mlb_live_market_context_v1 import attach_live_market_context
from sports_api.mlb_official_game_id_join_v1 import canonical_official_game_id

VERSION = "MLB DAILY PICKS STEP 5.2 • EXACT-ID LIVE FANDUEL MARKET CONTEXT"
_STATE_KEY = "mlb_step5_2_live_market_context_v1"

_BASE_CARD = getattr(v217, "_step5_2_base_decision_card", v217._decision_card_v217)
_BASE_WHY = getattr(v217, "_step5_2_base_why_sections", v217._why_sections)
v217._step5_2_base_decision_card = _BASE_CARD
v217._step5_2_base_why_sections = _BASE_WHY


@st.cache_data(ttl=30, show_spinner=False)
def _live_payload() -> dict[str, Any]:
    return fetch_live_mlb_odds(max_events=30)


def _model_identity_rows(games_df) -> list[dict[str, Any]]:
    """Snapshot only official model game IDs; no display field participates in join."""
    if games_df is None:
        return []
    records = None
    to_dict = getattr(games_df, "to_dict", None)
    if callable(to_dict):
        try:
            records = to_dict(orient="records")
        except TypeError:
            try:
                records = to_dict("records")
            except Exception:
                records = None
        except Exception:
            records = None
    if records is None and isinstance(games_df, (list, tuple)):
        records = list(games_df)
    if not isinstance(records, list):
        return []

    out = []
    for row in records:
        if not isinstance(row, Mapping):
            continue
        out.append({"game_pk": row.get("game_pk")})
    return out


def refresh_live_market_context(games_df, *, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Refresh presentation context; any transport/schema/join problem fails closed."""
    try:
        live_payload = dict(payload) if payload is not None else _live_payload()
        if live_payload.get("data_type") != "mlb_live_odds_api_response_v1":
            raise MLBLiveOddsUIError("unexpected MLB live-odds data_type")
        if live_payload.get("schema_version") != 1 or live_payload.get("source") != "FanDuel":
            raise MLBLiveOddsUIError("unexpected MLB live-odds schema/source")
        market_games = live_payload.get("games")
        if not isinstance(market_games, list):
            raise MLBLiveOddsUIError("MLB live-odds games is not a list")

        result = attach_live_market_context(_model_identity_rows(games_df), market_games)
        result["available"] = True
        result["collected_at_utc"] = live_payload.get("collected_at_utc")
        result["api_data_type"] = live_payload.get("data_type")
    except Exception as exc:
        result = {
            "available": False,
            "source": "FanDuel",
            "match_method": "official_mlb_game_id_exact",
            "fallback_matching_used": False,
            "contexts_by_game_id": {},
            "error_type": type(exc).__name__,
        }
    st.session_state[_STATE_KEY] = result
    return result


def _context_for_candidate(candidate: Mapping[str, Any]) -> Mapping[str, Any] | None:
    state = st.session_state.get(_STATE_KEY) or {}
    contexts = state.get("contexts_by_game_id") or {}
    try:
        game_id = canonical_official_game_id(candidate.get("game_pk"))
    except Exception:
        return None
    context = contexts.get(game_id)
    return context if isinstance(context, Mapping) else None


def _market_board_html(context: Mapping[str, Any]) -> str:
    ml = context.get("moneyline") or {}
    rl = context.get("run_line") or {}
    total = context.get("total") or {}
    game_id = escape(str(context.get("official_game_id") or ""))
    return (
        '<div style="border:1px solid #2a6079;background:#071a27;border-radius:10px;'
        'padding:8px 9px;margin-top:8px;display:flex;flex-direction:column;gap:4px">'
        '<div style="font-size:8px;font-weight:950;color:#6edfff">FANDUEL LIVE BOARD • '
        f'EXACT MLB GAME {game_id}</div>'
        '<div style="font-size:8px;color:#d9ecf8;font-weight:800">'
        f'ML: Away {escape(format_american_odds(ml.get("away_odds")))} • '
        f'Home {escape(format_american_odds(ml.get("home_odds")))}</div>'
        '<div style="font-size:8px;color:#d9ecf8;font-weight:800">'
        f'RL: Away {escape(format_line(rl.get("away_line"), signed=True))} '
        f'({escape(format_american_odds(rl.get("away_odds")))}) • '
        f'Home {escape(format_line(rl.get("home_line"), signed=True))} '
        f'({escape(format_american_odds(rl.get("home_odds")))})</div>'
        '<div style="font-size:8px;color:#d9ecf8;font-weight:800">'
        f'Total {escape(format_line(total.get("line")))} • '
        f'Over {escape(format_american_odds(total.get("over_odds")))} • '
        f'Under {escape(format_american_odds(total.get("under_odds")))}</div>'
        '<div style="font-size:7px;color:#82a8bd">Market context only • projection and Pick Strength unchanged</div>'
        '</div>'
    )


def _decision_card_step5_2(c, rank, games_df, ts, snap, baseline, risk):
    html = _BASE_CARD(c, rank, games_df, ts, snap, baseline, risk)
    context = _context_for_candidate(c)
    if context is None:
        return html
    board = _market_board_html(context)
    marker = '<div class="kui-score">'
    if marker in html:
        return html.replace(marker, board + marker, 1)
    return html + board


def _why_sections_step5_2(c, games_df, snap, ts, baseline, risk):
    sections = [(title, list(lines or [])) for title, lines in _BASE_WHY(c, games_df, snap, ts, baseline, risk)]
    context = _context_for_candidate(c)
    if context is None:
        line = (
            "Live FanDuel board is not attached to this game right now. Step 5.2 fails closed: "
            "no team-name, date/time, or fuzzy fallback is permitted."
        )
    else:
        ml = context.get("moneyline") or {}
        rl = context.get("run_line") or {}
        total = context.get("total") or {}
        line = (
            f"Exact-ID FanDuel board (MLB game {context.get('official_game_id')}): "
            f"ML away {format_american_odds(ml.get('away_odds'))} / home {format_american_odds(ml.get('home_odds'))}; "
            f"RL away {format_line(rl.get('away_line'), signed=True)} ({format_american_odds(rl.get('away_odds'))}) / "
            f"home {format_line(rl.get('home_line'), signed=True)} ({format_american_odds(rl.get('home_odds'))}); "
            f"Total {format_line(total.get('line'))}, over {format_american_odds(total.get('over_odds'))}, "
            f"under {format_american_odds(total.get('under_odds'))}. "
            "This live board is display/context only and does not rewrite the production projection or Pick Strength."
        )

    inserted = False
    out = []
    for title, lines in sections:
        if title == "📈 Market context":
            lines.append(line)
            inserted = True
        out.append((title, lines))
    if not inserted:
        out.insert(1, ("📈 Market context", [line]))
    return out


def install_live_market_context(games_df, *, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Install Step 5.2 at the V2.1.7 presentation boundary for this rerun."""
    state = refresh_live_market_context(games_df, payload=payload)
    v217._decision_card_v217 = _decision_card_step5_2
    v217._why_sections = _why_sections_step5_2
    return state


__all__ = [
    "VERSION",
    "install_live_market_context",
    "refresh_live_market_context",
]
