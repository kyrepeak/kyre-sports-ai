"""MLB Moneyline V17.7 — Step 11 market intelligence + price context.

Additive evidence wrapper over permanently frozen V17.6 Step 10.

Step 11 consumes the existing exact-official-game-ID Kyre Sports API FanDuel
Moneyline snapshot and compares it with the already-produced frozen Moneyline
model probability. It adds read-only market intelligence:

- selected and opponent FanDuel prices from the same exact game snapshot,
- raw implied probabilities,
- two-way no-vig market probability,
- sportsbook hold/overround,
- model-vs-market probability gap,
- price EV per $1 risked using the frozen model probability,
- model fair price vs market price,
- strict snapshot freshness and identity gates.

Critical boundaries:
- FanDuel price is NEVER fed back into the Moneyline model in Step 11.
- No probability, simulation, history adjustment, ranking, candidate selection,
  fair-odds generation, production exposure, wagering, or Step 5L live math
  changes.
- No fuzzy game matching is introduced. Only the already-certified exact MLB
  game ID context is accepted.
- No line-movement claim is made from a single snapshot.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any, Mapping

import streamlit as st

import mlb_moneyline_hub_v176 as prior
import mlb_moneyline_hub_v170 as pregame
import mlb_moneyline_hub_v165 as market_source
from sports_api.mlb_step7c_moneyline_api_integration_v1 import (
    API_CONNECTED,
    MATCH_METHOD,
)

MODEL_VERSION = "V17.7 • MONEYLINE STEP 11 • MARKET INTELLIGENCE + PRICE CONTEXT"
FROZEN_MONEYLINE_PRESENTATION = "mlb_moneyline_hub_v176"
FROZEN_MODEL_CHAIN = prior.FROZEN_MODEL_CHAIN
SEASON = prior.SEASON

MIN_MARKET_DATA_SCORE = 90
MAX_SNAPSHOT_AGE_SECONDS = 60.0

_STEP11_CSS = r"""
<style>
.ml177-step11{grid-area:identity;margin-top:7px;padding:10px 11px;border:1px solid rgba(255,203,84,.30);border-radius:13px;background:linear-gradient(145deg,rgba(39,29,8,.97),rgba(9,17,27,.97));box-shadow:inset 3px 0 #ffcb54}
.ml177-head{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:8px}
.ml177-title{font-size:.58rem;font-weight:950;letter-spacing:.08em;text-transform:uppercase;color:#ffe29a}
.ml177-grade{display:inline-flex;align-items:center;border-radius:999px;padding:5px 8px;font-size:.50rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase;border:1px solid #6c6042;background:#2a2414;color:#f3dfad}
.ml177-grade.value{border-color:#34775d;background:#0d3025;color:#9ce9c1}.ml177-grade.strong{border-color:#21865f;background:#073823;color:#83efb7}.ml177-grade.aligned{border-color:#75621e;background:#30290d;color:#f4dc78}.ml177-grade.market{border-color:#70484a;background:#30191b;color:#f0b0b3}.ml177-grade.limited{border-color:#555e65;background:#20272c;color:#c8d0d5}
.ml177-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.ml177-cell{border:1px solid rgba(255,203,84,.16);border-radius:9px;background:#091722;padding:7px 5px;text-align:center}.ml177-cell b{display:block;color:#f4f7f9;font-size:.63rem}.ml177-cell span{display:block;color:#758894;font-size:.40rem;margin-top:2px;text-transform:uppercase}
.ml177-price{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:8px}.ml177-side{border:1px solid rgba(255,203,84,.17);border-radius:10px;background:rgba(12,20,28,.84);padding:8px}.ml177-side.home{text-align:right}.ml177-side h4{margin:0;color:#f4f7f9;font-size:.64rem}.ml177-side small{color:#788b97;font-size:.43rem}.ml177-odds{display:inline-flex;margin-top:5px;border-radius:999px;padding:4px 7px;border:1px solid #756125;background:#30270d;color:#f4dc78;font-size:.47rem;font-weight:950}
.ml177-note{margin-top:7px;border:1px solid rgba(255,203,84,.14);border-radius:8px;padding:6px 7px;background:#1b180d;color:#bcb7a7;font-size:.45rem;line-height:1.42}.ml177-note b{color:#f1e6c7}
.ml177-pills{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}.ml177-pill{display:inline-flex;border-radius:999px;padding:4px 7px;border:1px solid rgba(255,203,84,.22);background:#2a220d;color:#f2d989;font-size:.46rem;font-weight:850}.ml177-source{margin-top:6px;color:#708696;font-size:.43rem;line-height:1.4}
@media(max-width:640px){.ml177-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ml177-price{grid-template-columns:1fr}.ml177-side.home{text-align:left}.ml177-step11{padding:9px}}
</style>
"""


def _f(value: Any) -> float | None:
    try:
        out = float(value)
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _american(value: Any) -> int | None:
    x = _f(value)
    if x is None or x == 0 or not float(x).is_integer():
        return None
    return int(x)


def _implied_probability(american: Any) -> float | None:
    price = _american(american)
    if price is None:
        return None
    if price > 0:
        return 100.0 / (price + 100.0)
    return (-price) / ((-price) + 100.0)


def _decimal_odds(american: Any) -> float | None:
    price = _american(american)
    if price is None:
        return None
    if price > 0:
        return 1.0 + price / 100.0
    return 1.0 + 100.0 / (-price)


def _prob_to_american(probability: Any) -> int | None:
    p = _f(probability)
    if p is None or not 0.0 < p < 1.0:
        return None
    if p >= 0.5:
        return int(round(-100.0 * p / (1.0 - p)))
    return int(round(100.0 * (1.0 - p) / p))


def _odds_text(value: Any) -> str:
    price = _american(value)
    if price is None:
        return "N/A"
    return f"+{price}" if price > 0 else str(price)


def _pct(value: Any, digits: int = 1) -> str:
    x = _f(value)
    return "N/A" if x is None else f"{100.0 * x:.{digits}f}%"


def _market_grade(edge: Any, ev: Any) -> tuple[str, str]:
    gap = _f(edge)
    value = _f(ev)
    if gap is None or value is None:
        return "MARKET DATA LIMITED / PENDING", "limited"
    if gap >= 0.050 and value >= 0.050:
        return "STRONG MODEL PRICE EDGE", "strong"
    if gap >= 0.025 and value > 0:
        return "MODEL PRICE EDGE", "value"
    if gap <= -0.050:
        return "MARKET STRONGLY MORE BULLISH", "market"
    if gap <= -0.025:
        return "MARKET MORE BULLISH", "market"
    return "MODEL + MARKET ALIGNED", "aligned"


def _build_market_context(result: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    """Build exact-ID two-way FanDuel context for one frozen Moneyline result."""
    row = dict(result or {})
    market = dict(state or {})
    failures: list[str] = []

    if market.get("integration_status") != API_CONNECTED or market.get("api_integration_active") is not True:
        failures.append("exact_id_market_feed_inactive")
    if market.get("match_method") != MATCH_METHOD or market.get("fallback_matching_used") is not False:
        failures.append("exact_id_contract_not_satisfied")
    if market.get("feed_fresh") is not True:
        failures.append("market_snapshot_not_fresh")

    age = _f(market.get("snapshot_age_seconds"))
    if age is None or age < 0 or age > MAX_SNAPSHOT_AGE_SECONDS:
        failures.append("market_snapshot_age_out_of_bounds")

    game_pk = _i(row.get("game_pk"))
    team_id = _i(row.get("team_id"))
    away_id = _i(row.get("away_team_id"))
    home_id = _i(row.get("home_team_id"))
    if not game_pk or not team_id or not away_id or not home_id:
        failures.append("model_game_or_team_identity_missing")

    contexts = market.get("contexts_by_game_id")
    game_context = dict(contexts.get(game_pk) or {}) if isinstance(contexts, Mapping) and game_pk else {}
    if _i(game_context.get("official_game_id")) != game_pk:
        failures.append("official_game_id_mismatch")

    if team_id == away_id:
        selected_side, opponent_side = "away", "home"
    elif team_id == home_id:
        selected_side, opponent_side = "home", "away"
    else:
        selected_side, opponent_side = "", ""
        failures.append("selected_team_identity_mismatch")

    selected_odds = _american(game_context.get(f"{selected_side}_odds")) if selected_side else None
    opponent_odds = _american(game_context.get(f"{opponent_side}_odds")) if opponent_side else None
    if selected_odds is None or opponent_odds is None:
        failures.append("two_way_moneyline_prices_missing")

    selected_implied = _implied_probability(selected_odds)
    opponent_implied = _implied_probability(opponent_odds)
    overround = (
        selected_implied + opponent_implied - 1.0
        if selected_implied is not None and opponent_implied is not None
        else None
    )
    denominator = (
        selected_implied + opponent_implied
        if selected_implied is not None and opponent_implied is not None
        else None
    )
    no_vig = (
        selected_implied / denominator
        if denominator is not None and denominator > 0
        else None
    )

    model_prob = _f(row.get("win_prob"))
    if model_prob is None or not 0.0 < model_prob < 1.0:
        failures.append("frozen_model_probability_missing")

    decimal_price = _decimal_odds(selected_odds)
    ev = (
        model_prob * decimal_price - 1.0
        if model_prob is not None and decimal_price is not None
        else None
    )
    edge = (
        model_prob - no_vig
        if model_prob is not None and no_vig is not None
        else None
    )

    data_score = 0
    data_score += 25 if not any(x in failures for x in ("exact_id_market_feed_inactive", "exact_id_contract_not_satisfied")) else 0
    data_score += 25 if not any(x in failures for x in ("market_snapshot_not_fresh", "market_snapshot_age_out_of_bounds")) else 0
    data_score += 25 if not any(x in failures for x in ("official_game_id_mismatch", "model_game_or_team_identity_missing", "selected_team_identity_mismatch")) else 0
    data_score += 25 if selected_odds is not None and opponent_odds is not None and no_vig is not None else 0

    ready = not failures and data_score >= MIN_MARKET_DATA_SCORE
    grade, grade_cls = _market_grade(edge, ev) if ready else ("MARKET DATA LIMITED / PENDING", "limited")

    selected_name = str(row.get("team") or "Selected side")
    opponent_name = str(row.get("opponent") or "Opponent")
    fair_market = _prob_to_american(no_vig)

    return {
        "status": "VERIFIED" if ready else "PENDING",
        "data_score": data_score,
        "failures": failures,
        "game_pk": game_pk or None,
        "source": str(market.get("source") or "FanDuel"),
        "selected_side": selected_side or None,
        "selected_name": selected_name,
        "opponent_name": opponent_name,
        "selected_odds": selected_odds,
        "opponent_odds": opponent_odds,
        "selected_implied": selected_implied,
        "opponent_implied": opponent_implied,
        "no_vig_probability": no_vig,
        "market_fair_odds": fair_market,
        "overround": overround,
        "model_probability": model_prob,
        "model_fair_odds": row.get("fair_odds"),
        "model_market_edge": edge,
        "ev_per_dollar": ev,
        "snapshot_age_seconds": age,
        "collected_at_utc": market.get("collected_at_utc"),
        "grade": grade,
        "grade_cls": grade_cls,
        "model_math_impact": False,
        "probability_impact": False,
        "ranking_impact": False,
        "selection_impact": False,
        "fair_odds_impact": False,
        "sportsbook_price_model_input": False,
        "wagering_impact": False,
    }


def _html(context: Mapping[str, Any]) -> str:
    failures = list(context.get("failures") or [])
    reason = " • ".join(str(x).replace("_", " ") for x in failures[:3])
    edge = _f(context.get("model_market_edge"))
    edge_text = "N/A" if edge is None else f"{edge * 100:+.1f} pts"
    ev = _f(context.get("ev_per_dollar"))
    ev_text = "N/A" if ev is None else f"{ev * 100:+.1f}%"
    hold = _f(context.get("overround"))
    hold_text = "N/A" if hold is None else f"{hold * 100:.1f}%"
    age = _f(context.get("snapshot_age_seconds"))
    age_text = "N/A" if age is None else f"{age:.0f}s"

    return (
        '<div class="ml177-step11">'
        '<div class="ml177-head">'
        '<span class="ml177-title">STEP 11 • MARKET INTELLIGENCE + PRICE CONTEXT</span>'
        f'<span class="ml177-grade {escape(str(context.get("grade_cls") or "limited"))}">{escape(str(context.get("grade") or "MARKET DATA LIMITED / PENDING"))}</span>'
        '</div>'
        '<div class="ml177-grid">'
        f'<div class="ml177-cell"><b>{escape(_pct(context.get("model_probability")))}</b><span>Frozen model win</span></div>'
        f'<div class="ml177-cell"><b>{escape(_pct(context.get("no_vig_probability")))}</b><span>FanDuel no-vig</span></div>'
        f'<div class="ml177-cell"><b>{escape(edge_text)}</b><span>Model - market</span></div>'
        f'<div class="ml177-cell"><b>{escape(ev_text)}</b><span>EV per $1 at quote</span></div>'
        '</div>'
        '<div class="ml177-price">'
        '<div class="ml177-side">'
        f'<h4>{escape(str(context.get("selected_name") or "Selected side"))}</h4>'
        f'<small>Raw implied {escape(_pct(context.get("selected_implied")))} • no-vig fair {_odds_text(context.get("market_fair_odds"))}</small>'
        f'<div class="ml177-odds">FANDUEL {_odds_text(context.get("selected_odds"))}</div>'
        '</div>'
        '<div class="ml177-side home">'
        f'<h4>{escape(str(context.get("opponent_name") or "Opponent"))}</h4>'
        f'<small>Raw implied {escape(_pct(context.get("opponent_implied")))} • book hold {escape(hold_text)}</small>'
        f'<div class="ml177-odds">FANDUEL {_odds_text(context.get("opponent_odds"))}</div>'
        '</div>'
        '</div>'
        '<div class="ml177-note">'
        f'<b>Price read:</b> model fair {escape(str(context.get("model_fair_odds") or "N/A"))} • '
        f'FanDuel no-vig fair {_odds_text(context.get("market_fair_odds"))} • '
        f'snapshot age {escape(age_text)}. '
        'This is one exact-ID snapshot; Step 11 does not claim opening-line or movement history.'
        '</div>'
        '<div class="ml177-pills">'
        f'<span class="ml177-pill">DATA QUALITY • {int(context.get("data_score") or 0)}/100</span>'
        '<span class="ml177-pill">EXACT MLB GAME ID ONLY</span>'
        '<span class="ml177-pill">TWO-WAY NO-VIG</span>'
        '<span class="ml177-pill">PRICE NOT A MODEL INPUT</span>'
        '<span class="ml177-pill">NO PROBABILITY ADJUSTMENT</span>'
        '</div>'
        f'<div class="ml177-source">Source: {escape(str(context.get("source") or "FanDuel"))} via the certified Kyre Sports API exact-ID Moneyline contract. '
        f'{escape(reason)}</div>'
        '</div>'
    )


def _inject(card: str, html: str) -> str:
    text = str(card or "")
    if not html or "ks-pick-card" not in text or "ml177-step11" in text:
        return text
    return text[:-6] + html + "</div>" if text.endswith("</div>") else text + html


_FROZEN_STEP10_RENDERER = prior._renderer


def _renderer(original, rows, lineups):
    step10_renderer = _FROZEN_STEP10_RENDERER(original, rows, lineups)

    def wrapped(results, status_info, team_logo, h):
        ordered = list(results or [])[:5]
        try:
            state = market_source._cached_moneyline_api_state(market_source._api_base_url())
        except Exception:
            state = {
                "integration_status": "FROZEN_MONEYLINE_PRESENTATION_FALLBACK",
                "api_integration_active": False,
                "source": "FanDuel",
                "match_method": MATCH_METHOD,
                "fallback_matching_used": False,
                "feed_fresh": False,
                "failures": ["market_state_unavailable"],
            }

        contexts = [_build_market_context(result, state) for result in ordered]
        cursor = {"i": 0}
        original_markdown = st.markdown

        def capture(body: Any, *args: Any, **kwargs: Any):
            text = str(body or "")
            if "ks-pick-card" in text and cursor["i"] < len(contexts):
                text = _inject(text, _html(contexts[cursor["i"]]))
                cursor["i"] += 1
            return original_markdown(text, *args, **kwargs)

        st.markdown = capture
        try:
            return step10_renderer(results, status_info, team_logo, h)
        finally:
            st.markdown = original_markdown

    return wrapped


def _render_pregame_with_step11(games_df, section_header, status_info, team_logo, h):
    original_renderer = pregame._renderer
    pregame._renderer = _renderer
    try:
        return pregame.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        pregame._renderer = original_renderer


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    """Preserve frozen Step 5L live mode while extending only pregame market evidence."""
    st.markdown(_STEP11_CSS, unsafe_allow_html=True)
    original_step10_pregame = prior._render_pregame_with_step10
    prior._render_pregame_with_step10 = _render_pregame_with_step11
    try:
        return prior.render_moneyline_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        prior._render_pregame_with_step10 = original_step10_pregame


__all__ = [
    "FROZEN_MODEL_CHAIN",
    "FROZEN_MONEYLINE_PRESENTATION",
    "MAX_SNAPSHOT_AGE_SECONDS",
    "MIN_MARKET_DATA_SCORE",
    "MODEL_VERSION",
    "_american",
    "_build_market_context",
    "_decimal_odds",
    "_implied_probability",
    "_market_grade",
    "_prob_to_american",
    "render_moneyline_hub",
]
