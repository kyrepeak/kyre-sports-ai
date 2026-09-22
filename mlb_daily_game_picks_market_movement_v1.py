"""Step 5.6 presentation-only MLB market movement + snapshot age layer.

Runs strictly downstream of Step 5.5. It keeps only the latest two certified FanDuel
observations per exact official-game/market/side identity in Streamlit session state.
That history is ephemeral: no database writes and no durable persistence.

If the line is unchanged, Step 5.6 shows whether the exact FanDuel price improved or
became more expensive, the no-vig market-probability move, and price-only EV change
using the current production model probability for both prices. If a Run Line or
Total line changes, the UI reports the line move but suppresses direct price/EV
comparison because different lines are not apples-to-apples.

Model math, Pick Strength, simulations, ranking, selection, risk, persistence, and
wagering remain untouched.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import mlb_daily_game_picks_market_probability_v1 as step53
import mlb_daily_game_picks_price_discipline_v1 as step55
import mlb_daily_game_picks_v217 as v217
from sports_api.mlb_market_movement_v1 import (
    MLBMarketMovementError,
    build_market_observation,
    compare_market_observations,
    observation_identity_key,
    parse_utc_timestamp,
)

VERSION = "MLB DAILY PICKS STEP 5.6 • FANDUEL MARKET MOVEMENT + SNAPSHOT AGE"
_STATE_KEY = "mlb_step5_6_market_movement_v1"
_HISTORY_KEY = "mlb_step5_6_ephemeral_market_history_v1"


def _pp(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number * 100.0:+.1f} pp"


def _ev_delta(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number * 100.0:+.1f} pp"


def _odds(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    rounded = int(round(number))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _line(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "—"
    number = float(value)
    if not math.isfinite(number):
        return "—"
    return f"{number:+g}"


def _age(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "age unavailable"
    seconds = max(0.0, float(value))
    if seconds < 60:
        return f"{seconds:.0f}s old"
    if seconds < 3600:
        return f"{seconds / 60.0:.1f}m old"
    return f"{seconds / 3600.0:.1f}h old"


def _movement_label(status: Any) -> str:
    text = str(status or "")
    return {
        "NO_PRIOR_OBSERVATION": "🆕 BASELINE CAPTURED",
        "NO_NEW_OBSERVATION": "⏸ NO NEW SNAPSHOT",
        "BETTER_PRICE": "✅ BETTER PRICE",
        "MORE_EXPENSIVE": "⚠️ MORE EXPENSIVE",
        "UNCHANGED": "➖ PRICE UNCHANGED",
        "LINE_CHANGED": "↕️ LINE MOVED",
    }.get(text, "MARKET MOVEMENT")


def _collected_at_utc() -> str | None:
    state = st.session_state.get(step53._STATE_KEY) or {}
    value = state.get("collected_at_utc")
    return str(value) if value else None


def _same_timestamp(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    try:
        return parse_utc_timestamp(a.get("collected_at_utc")) == parse_utc_timestamp(b.get("collected_at_utc"))
    except Exception:
        return False


def _record_observation(observation: Mapping[str, Any]) -> tuple[Mapping[str, Any], Mapping[str, Any] | None]:
    """Keep at most latest + previous in ephemeral Streamlit session state."""
    key = observation_identity_key(observation)
    history = dict(st.session_state.get(_HISTORY_KEY) or {})
    entry = dict(history.get(key) or {})
    latest = entry.get("latest")
    previous = entry.get("previous")

    if not isinstance(latest, Mapping):
        entry = {"latest": dict(observation), "previous": None}
        history[key] = entry
        st.session_state[_HISTORY_KEY] = history
        return entry["latest"], None

    current_dt = parse_utc_timestamp(observation.get("collected_at_utc"))
    latest_dt = parse_utc_timestamp(latest.get("collected_at_utc"))
    if current_dt < latest_dt:
        raise MLBMarketMovementError("received an out-of-order market observation")

    if current_dt == latest_dt:
        # Validates that the same timestamp is not carrying contradictory prices.
        compare_market_observations(observation, latest)
        return observation, previous if isinstance(previous, Mapping) else None

    entry = {"latest": dict(observation), "previous": dict(latest)}
    history[key] = entry
    st.session_state[_HISTORY_KEY] = history
    return entry["latest"], entry["previous"]


def movement_context_for_candidate(candidate: Mapping[str, Any], games_df) -> Mapping[str, Any] | None:
    """Build/compare one exact-identity market observation, failing closed on any ambiguity."""
    try:
        price_context = step55.price_context_for_candidate(candidate, games_df)
        if not isinstance(price_context, Mapping):
            return None
        collected_at = _collected_at_utc()
        if not collected_at:
            return None
        observation = build_market_observation(price_context, collected_at_utc=collected_at)
        current, previous = _record_observation(observation)
        return compare_market_observations(
            current,
            previous,
            as_of_utc=datetime.now(timezone.utc).isoformat(),
        )
    except (MLBMarketMovementError, Exception):
        return None


def _movement_board_html(context: Mapping[str, Any]) -> str:
    status = str(context.get("movement_status") or "")
    label = escape(_movement_label(status))
    age = escape(_age(context.get("snapshot_age_seconds")))

    if status in {"NO_PRIOR_OBSERVATION", "NO_NEW_OBSERVATION"}:
        body = (
            f'<div style="font-size:8px;color:#dbe9f1;font-weight:800">FanDuel {_odds(context.get("current_market_odds"))} • {age}</div>'
            '<div style="font-size:7px;color:#82a8bd">Waiting for a newer certified snapshot before claiming line or price movement.</div>'
        )
    elif status == "LINE_CHANGED":
        body = (
            '<div style="font-size:8px;color:#dbe9f1;font-weight:800">'
            f'Line {_line(context.get("previous_market_line"))} → {_line(context.get("current_market_line"))} • {age}</div>'
            '<div style="font-size:8px;color:#dbe9f1;font-weight:800">'
            f'Previous odds {_odds(context.get("previous_market_odds"))} • Current {_odds(context.get("current_market_odds"))}</div>'
            '<div style="font-size:7px;color:#82a8bd">Different lines are not directly price-comparable, so Step 5.6 suppresses price/EV movement instead of fabricating an apples-to-apples comparison.</div>'
        )
    else:
        body = (
            '<div style="font-size:8px;color:#dbe9f1;font-weight:800">'
            f'FanDuel {_odds(context.get("previous_market_odds"))} → {_odds(context.get("current_market_odds"))} • {age}</div>'
            '<div style="font-size:8px;color:#dbe9f1;font-weight:800">'
            f'Break-even move {escape(_pp(context.get("raw_break_even_probability_delta")))} • '
            f'No-vig move {escape(_pp(context.get("no_vig_probability_delta")))}</div>'
            '<div style="font-size:8px;color:#dbe9f1;font-weight:800">'
            f'Price-only EV move {escape(_ev_delta(context.get("price_only_ev_delta")))} using the current model probability for both prices</div>'
        )

    return (
        '<div style="border:1px solid #436b80;background:#07131c;border-radius:10px;'
        'padding:8px 9px;margin-top:6px;display:flex;flex-direction:column;gap:4px">'
        '<div style="font-size:8px;font-weight:950;color:#a9e7ff">MARKET MOVEMENT • STEP 5.6</div>'
        f'<div style="font-size:8px;font-weight:900;color:#eef7fb">{label}</div>'
        f'{body}'
        '<div style="font-size:7px;color:#82a8bd">Ephemeral session history only • no model, Pick Strength, ranking, selection, risk, persistence, or wagering changes</div>'
        '</div>'
    )


def _decision_card_step5_6(c, rank, games_df, ts, snap, baseline, risk):
    html = step55._decision_card_step5_5(c, rank, games_df, ts, snap, baseline, risk)
    context = movement_context_for_candidate(c, games_df)
    if context is None:
        return html
    board = _movement_board_html(context)
    marker = '<div class="kui-score">'
    if marker in html:
        return html.replace(marker, board + marker, 1)
    return html + board


def _why_sections_step5_6(c, games_df, snap, ts, baseline, risk):
    sections = [
        (title, list(lines or []))
        for title, lines in step55._why_sections_step5_5(c, games_df, snap, ts, baseline, risk)
    ]
    context = movement_context_for_candidate(c, games_df)
    market = str(c.get("market") or "")
    if context is None:
        if market in {"Moneyline", "Run Line", "Total"}:
            line = (
                "Step 5.6 market movement is unavailable because a certified current timestamp/price observation could not be proven. "
                "No movement is fabricated."
            )
        else:
            line = (
                "Step 5.6 remains limited to full-game Moneyline, Run Line, and Total because only those markets have certified exact-ID FanDuel prices. "
                "Player-prop movement remains unavailable until a certified prop-price feed exists."
            )
    else:
        status = str(context.get("movement_status") or "")
        if status in {"NO_PRIOR_OBSERVATION", "NO_NEW_OBSERVATION"}:
            line = (
                f"Step 5.6 captured the current FanDuel snapshot ({_age(context.get('snapshot_age_seconds'))}) but has no newer-vs-older certified pair yet. "
                "It waits for a later observation rather than inventing market movement."
            )
        elif status == "LINE_CHANGED":
            line = (
                f"Step 5.6 detected a line change from {_line(context.get('previous_market_line'))} to {_line(context.get('current_market_line'))}. "
                "Because the betting line changed, direct price and EV movement is intentionally suppressed; prices at different lines are not treated as equivalent."
            )
        else:
            line = (
                f"Step 5.6 exact-price movement: FanDuel moved from {_odds(context.get('previous_market_odds'))} to {_odds(context.get('current_market_odds'))}. "
                f"The selected side's raw break-even probability moved {_pp(context.get('raw_break_even_probability_delta'))}, "
                f"while no-vig market probability moved {_pp(context.get('no_vig_probability_delta'))}. "
                f"Holding today's production model probability fixed for both prices, the price-only EV move is {_ev_delta(context.get('price_only_ev_delta'))}. "
                "This remains market context only and does not modify the model or Final Card logic."
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


def install_market_movement_layer(
    games_df,
    *,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Install Step 5.6 downstream of Step 5.5 without touching selection state."""
    step55_state = step55.install_price_discipline_layer(games_df, payload=payload)
    collected_at = _collected_at_utc()
    state = {
        "data_type": "mlb_market_movement_presentation_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "comparison_only": True,
        "ephemeral_session_history": True,
        "durable_persistence": False,
        "selection_impact": False,
        "ranking_impact": False,
        "wagering_impact": False,
        "step5_5_available": bool(step55_state.get("step5_4_available")),
        "derived_market_context_count": int(step55_state.get("derived_market_context_count") or 0),
        "collected_at_utc": collected_at,
    }
    st.session_state[_STATE_KEY] = state
    v217._decision_card_v217 = _decision_card_step5_6
    v217._why_sections = _why_sections_step5_6
    return state


__all__ = [
    "VERSION",
    "install_market_movement_layer",
    "movement_context_for_candidate",
]
