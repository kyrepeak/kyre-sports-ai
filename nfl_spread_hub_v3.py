"""NFL Spread V3 — independent fair line + certified 5M Monte Carlo.

V3 is additive over the certified V2 matchup board. Frozen Spread V1 still owns
verified NFL slate identity, Kyre Sports API market transport, and fail-closed
sportsbook context. V3 adds only the independent Step 7B football margin model
and Step 7C deterministic Monte Carlo analytics.

Sportsbook spread values are settlement/comparison context only and never enter
football projection math or simulated-margin generation. Rankings, staking, and
wager actions remain disabled.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
import math
from typing import Any

import pandas as pd
import streamlit as st

import nfl_spread_hub_v1 as frozen
import nfl_spread_hub_v2 as prior
import nfl_spread_mc_v1 as spread_mc


MODEL_VERSION = "NFL SPREAD V3 • INDEPENDENT FAIR LINE + CERTIFIED 5M MONTE CARLO"
FROZEN_PRESENTATION = "nfl_spread_hub_v2"
FROZEN_TRANSPORT = "nfl_spread_hub_v1"
PROJECTION_MODEL_ENABLED = True
MONTE_CARLO_ENABLED = True
CERTIFIED_SIMULATIONS = spread_mc.CERTIFIED_SIMULATIONS
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MARKET_LINE_ROLE = "settlement_only"
RANKINGS_ENABLED = False
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False


def _safe(value: Any, default: str = "") -> str:
    return prior._safe(value, default)


def _num(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except (TypeError, ValueError):
        return math.nan


def _pct(value: Any) -> str:
    number = _num(value)
    return f"{100.0 * number:.1f}%" if math.isfinite(number) else "—"


def _spread(value: Any) -> str:
    number = _num(value)
    return frozen.market_api.fmt_spread(number) if math.isfinite(number) else "—"


def _margin(value: Any) -> str:
    number = _num(value)
    return f"{number:+.1f}" if math.isfinite(number) else "—"


def _first_book(market: dict[str, Any]) -> dict[str, Any]:
    if not market.get("ready"):
        return {}
    books = market.get("books") or []
    return books[0] if books else {}


@st.cache_data(ttl=1800, show_spinner=False)
def _cached_game_mc(
    game: dict[str, Any],
    day_str: str,
    market_away_spread: float | None,
) -> dict[str, Any]:
    """Cache only the small MC summary; generated margins stay inside the engine."""
    return spread_mc.simulate_game_spread(
        game,
        day_str,
        market_away_spread,
        simulations=spread_mc.CERTIFIED_SIMULATIONS,
        seed=spread_mc.DEFAULT_SEED,
        batch_size=spread_mc.DEFAULT_BATCH_SIZE,
    )


def _analytics_for_game(
    game: dict[str, Any],
    market: dict[str, Any],
    day_str: str,
) -> dict[str, Any]:
    if _safe(game.get("state"), "pre").lower() != "pre":
        return {
            "ready": False,
            "error": "Pregame model/Monte Carlo only.",
            "runtime_stage": "pregame gate",
            "sportsbook_projection_influence": 0.0,
        }

    book = _first_book(market)
    line = _num(book.get("away_spread"))
    market_away_spread = float(line) if math.isfinite(line) else None
    result = _cached_game_mc(game, day_str, market_away_spread)

    influence = _num(result.get("sportsbook_projection_influence", 0.0))
    if result.get("ready") and (
        not math.isfinite(influence) or abs(influence) > 1e-12
    ):
        return {
            "ready": False,
            "error": "Sportsbook/model firewall violation detected.",
            "runtime_stage": "sportsbook firewall",
            "sportsbook_projection_influence": influence,
        }
    return result


def _analytics_card(
    game: dict[str, Any],
    market: dict[str, Any],
    analytics: dict[str, Any],
) -> str:
    event_id = _safe(game.get("game_id"))
    away = _safe(game.get("away_team"), "Away")
    home = _safe(game.get("home_team"), "Home")

    if not analytics.get("ready"):
        reason = _safe(analytics.get("error"), "Independent analytics unavailable.")
        return f"""
        <section class="ksp3-analysis bad" data-event-id="{escape(event_id, quote=True)}">
          <div class="ksp3-analysis-head">
            <div><span>MODEL + MONTE CARLO</span><b>UNAVAILABLE</b></div>
            <em>0.0% MARKET → MODEL</em>
          </div>
          <small>{escape(reason)}</small>
        </section>
        """

    book = _first_book(market)
    market_ready = bool(market.get("ready")) and bool(book)
    projected_away = _num(analytics.get("projected_away_margin"))
    fair_away = -projected_away if math.isfinite(projected_away) else math.nan
    fair_home = projected_away if math.isfinite(projected_away) else math.nan

    away_cover = analytics.get("away_cover_probability") if market_ready else math.nan
    home_cover = analytics.get("home_cover_probability") if market_ready else math.nan
    push = analytics.get("push_probability") if market_ready else math.nan
    q = analytics.get("margin_quantiles") or {}
    quality = _safe(analytics.get("model_quality"), "LOW")
    certified = bool(analytics.get("certified_run"))
    converged = bool(analytics.get("converged"))
    sims = int(analytics.get("simulations") or 0)
    mc_se = _num(
        analytics.get("away_cover_mc_se")
        if market_ready
        else analytics.get("away_win_mc_se")
    )
    mc_se_text = f"{mc_se:.6f}" if math.isfinite(mc_se) else "—"
    status = "5M CERTIFIED" if certified else ("MC CONVERGED" if converged else "MC CHECK")
    status_class = "good" if certified else ("watch" if converged else "bad")

    return f"""
    <section class="ksp3-analysis {status_class}" data-event-id="{escape(event_id, quote=True)}">
      <div class="ksp3-analysis-head">
        <div>
          <span>INDEPENDENT MODEL + MONTE CARLO</span>
          <b>{escape(away)} @ {escape(home)}</b>
        </div>
        <div class="ksp3-badges">
          <em class="{status_class}">{escape(status)}</em>
          <em>MODEL {escape(quality)}</em>
          <em>{sims:,} SIMS</em>
          <em>0.0% MARKET → MODEL</em>
        </div>
      </div>

      <div class="ksp3-grid">
        <div><span>AWAY FAIR SPREAD</span><b>{escape(_spread(fair_away))}</b></div>
        <div><span>HOME FAIR SPREAD</span><b>{escape(_spread(fair_home))}</b></div>
        <div><span>PROJECTED AWAY MARGIN</span><b>{escape(_margin(projected_away))}</b></div>
        <div><span>5M MEAN / MEDIAN</span><b>{escape(_margin(analytics.get('simulated_away_margin_mean')))} / {escape(_margin(analytics.get('simulated_away_margin_median')))}</b></div>
        <div><span>AWAY COVER</span><b>{escape(_pct(away_cover))}</b></div>
        <div><span>HOME COVER</span><b>{escape(_pct(home_cover))}</b></div>
        <div><span>PUSH</span><b>{escape(_pct(push))}</b></div>
        <div><span>AWAY WIN</span><b>{escape(_pct(analytics.get('away_win_probability')))}</b></div>
        <div><span>MIDDLE 50% MARGIN</span><b>{escape(_margin(q.get('p25')))} to {escape(_margin(q.get('p75')))}</b></div>
        <div><span>MC STANDARD ERROR</span><b>{escape(mc_se_text)}</b></div>
      </div>

      <small>Market line role: settlement only • deterministic seed {int(analytics.get('seed') or 0)} • no rankings, stake sizing, or wager actions</small>
    </section>
    """


def _summary_html(
    *,
    games: int,
    upcoming: int,
    market_ready: int,
    model_ready: int,
    mc_certified: int,
) -> str:
    return f"""
    <div class="ksp3-summary">
      <div><span>GAMES</span><b>{games}</b><small>{upcoming} pregame</small></div>
      <div><span>MARKET</span><b>{market_ready}/{upcoming}</b><small>certified</small></div>
      <div><span>MODEL</span><b>{model_ready}/{upcoming}</b><small>football-only</small></div>
      <div><span>MONTE CARLO</span><b>{mc_certified}/{upcoming}</b><small>full 5M certified</small></div>
      <div><span>FIREWALL</span><b>0.0%</b><small>sportsbook → projection</small></div>
    </div>
    """


_CSS_V3 = r"""
<style>
.ksp3-summary{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin:10px auto 13px;max-width:1180px}.ksp3-summary>div{border:1px solid #24506b;border-radius:12px;background:linear-gradient(180deg,#0a1724,#08131e);padding:10px 11px;min-width:0}.ksp3-summary span,.ksp3-analysis span{display:block;color:#7089a0;font-size:.49rem;font-weight:950;letter-spacing:.07em}.ksp3-summary b{display:block;color:#f5f9fd;font-size:.88rem;margin-top:3px}.ksp3-summary small{display:block;color:#61798f;font-size:.50rem;margin-top:2px}.ksp3-analysis{max-width:1180px;margin:-5px auto 14px;border:1px solid #2b6679;border-radius:16px;background:linear-gradient(180deg,#081b25,#07151e);padding:11px 12px;box-shadow:0 10px 26px rgba(0,0,0,.12)}.ksp3-analysis.bad{border-color:#65414a;background:rgba(77,28,38,.12)}.ksp3-analysis-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.ksp3-analysis-head b{display:block;color:#e9f8f2;font-size:.79rem;margin-top:3px}.ksp3-badges{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}.ksp3-badges em,.ksp3-analysis-head>em{font-style:normal;border:1px solid #315568;border-radius:999px;padding:4px 7px;color:#9dc8d8;font-size:.49rem;font-weight:900}.ksp3-badges em.good{color:#79efbd;border-color:#397d68}.ksp3-badges em.watch{color:#f2d77b;border-color:#806d2e}.ksp3-badges em.bad{color:#f5a0ac;border-color:#65414a}.ksp3-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:7px;margin-top:9px}.ksp3-grid>div{border:1px solid #1e4255;border-radius:10px;background:#07131c;padding:7px 8px;min-width:0}.ksp3-grid b{display:block;color:#dff9ee;font-size:.65rem;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ksp3-analysis>small{display:block;color:#657f8d;font-size:.50rem;margin-top:8px}.ksp3-analysis.bad small{color:#c08e99}
@media(max-width:760px){.ksp3-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.ksp3-analysis-head{flex-direction:column}.ksp3-badges{justify-content:flex-start}.ksp3-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def render_nfl_hub(market: str = "Spread") -> None:
    if str(market or "") != "Spread":
        raise RuntimeError("NFL Spread V3 only owns the Spread route.")

    st.markdown(prior._CSS, unsafe_allow_html=True)
    st.markdown(_CSS_V3, unsafe_allow_html=True)
    st.markdown(
        '<div class="ksp2-page"><section class="ksp2-hero">'
        '<div class="ksp2-eyebrow">NFL • independent spread intelligence</div>'
        '<div class="ksp2-title">🎯 NFL Spread <span>Model + 5M Monte Carlo</span></div>'
        '<div class="ksp2-sub">Verified ESPN identity • certified FanDuel context • independent football fair line • deterministic 5,000,000-simulation margin engine. Sportsbook influence on projection math remains exactly 0.0%.</div>'
        '<div class="ksp2-chips">'
        '<span class="ksp2-chip">PREGAME ONLY</span>'
        '<span class="ksp2-chip">KYRE SPORTS API</span>'
        '<span class="ksp2-chip">FANDUEL</span>'
        '<span class="ksp2-chip">MODEL ON</span>'
        '<span class="ksp2-chip">5M MC ON</span>'
        '<span class="ksp2-chip">0.0% MARKET → MODEL</span>'
        '</div></section></div>',
        unsafe_allow_html=True,
    )

    if "nfl_v1_date" not in st.session_state:
        st.session_state["nfl_v1_date"] = datetime.now(frozen.base.ET).date()
    selected = st.date_input(
        "📅 NFL Spread date",
        value=st.session_state["nfl_v1_date"],
        key="nfl_spread_v3_date_input",
    )
    st.session_state["nfl_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")

    with st.spinner("🏈 Verifying NFL slate…"):
        games, diag = frozen.base.load_nfl_slate(day_str)

    if not diag.get("request_ok"):
        st.error(
            "NFL schedule provider did not return a usable slate. Spread stays fail-closed and no fake games, lines, or projections are created. "
            f"Provider: {diag.get('provider')} • HTTP: {diag.get('http') or '—'}"
        )
        return

    with st.spinner("🔌 Loading certified NFL Spread markets…"):
        markets = frozen._fetch_markets(games)

    analytics_by_event: dict[str, dict[str, Any]] = {}
    if not games.empty:
        with st.spinner("🧠 Running independent fair-line model + certified 5M Monte Carlo…"):
            for _, row in games.iterrows():
                game = row.to_dict()
                event_id = _safe(game.get("game_id"))
                market_state = markets.get(event_id) or {
                    "ready": False,
                    "reason": "Pregame Spread market was not requested for this game state.",
                    "books": [],
                    "projection_weight": 0.0,
                }
                analytics_by_event[event_id] = _analytics_for_game(
                    game, market_state, day_str
                )

    pregame_ids = set()
    if not games.empty and "state" in games.columns and "game_id" in games.columns:
        pregame_ids = set(
            games.loc[
                games["state"].astype(str) == "pre", "game_id"
            ].astype(str)
        )
    upcoming = len(pregame_ids)
    market_ready = sum(
        1 for event_id, item in markets.items()
        if str(event_id) in pregame_ids and item.get("ready")
    )
    model_ready = sum(
        1 for event_id in pregame_ids
        if (analytics_by_event.get(str(event_id)) or {}).get("ready")
    )
    mc_certified = sum(
        1 for event_id in pregame_ids
        if (analytics_by_event.get(str(event_id)) or {}).get("certified_run")
    )

    st.markdown(
        _summary_html(
            games=int(len(games)),
            upcoming=upcoming,
            market_ready=market_ready,
            model_ready=model_ready,
            mc_certified=mc_certified,
        ),
        unsafe_allow_html=True,
    )
    st.caption(
        f"✅ Verified NFL schedule • {day_str} • {diag.get('provider')} • {len(games)} game(s) • "
        f"{market_ready}/{upcoming} market(s) • {model_ready}/{upcoming} independent model(s) • "
        f"{mc_certified}/{upcoming} certified 5M simulation(s) • sportsbook projection influence 0.0%"
    )

    try:
        st.session_state["nfl_spread_v3_last"] = {
            "version": MODEL_VERSION,
            "date": day_str,
            "games": int(len(games)),
            "pregame_games": upcoming,
            "market_ready": market_ready,
            "model_ready": model_ready,
            "mc_certified": mc_certified,
            "frozen_transport": FROZEN_TRANSPORT,
            "frozen_presentation": FROZEN_PRESENTATION,
            "projection_model_enabled": True,
            "monte_carlo_enabled": True,
            "certified_simulations": CERTIFIED_SIMULATIONS,
            "sportsbook_projection_influence": 0.0,
            "market_line_role": MARKET_LINE_ROLE,
            "rankings_enabled": False,
            "stake_sizing_enabled": False,
            "wager_actions_enabled": False,
        }
    except Exception:
        pass

    if games.empty:
        st.info("No verified NFL games were returned for this date.")
        return

    cards: list[str] = []
    for _, row in games.iterrows():
        game = row.to_dict()
        event_id = _safe(game.get("game_id"))
        market_state = markets.get(event_id) or {
            "ready": False,
            "reason": "Pregame Spread market was not requested for this game state.",
            "books": [],
            "projection_weight": 0.0,
        }
        analytics = analytics_by_event.get(event_id) or {
            "ready": False,
            "error": "Independent analytics were not produced for this game.",
            "sportsbook_projection_influence": 0.0,
        }
        cards.append(prior._matchup_card(game, market_state))
        cards.append(_analytics_card(game, market_state, analytics))

    st.markdown(
        '<div class="ksp2-page">' + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )

    with st.expander("🔒 Spread V3 model + Monte Carlo contract", expanded=False):
        st.write(
            {
                "page_version": MODEL_VERSION,
                "frozen_presentation": FROZEN_PRESENTATION,
                "frozen_transport": FROZEN_TRANSPORT,
                "verified_slate_owner": frozen.FROZEN_SLATE_OWNER,
                "market_owner": frozen.MARKET_OWNER,
                "official_event_identity": "ESPN game_id only",
                "fuzzy_matching": False,
                "synthetic_event_ids": False,
                "projection_model": "ON — independent football-only fair margin",
                "monte_carlo": f"ON — deterministic {CERTIFIED_SIMULATIONS:,}",
                "market_line_role": MARKET_LINE_ROLE,
                "sportsbook_projection_influence": 0.0,
                "rankings_recommendations": "OFF",
                "stake_sizing": "OFF",
                "wager_actions": "OFF",
            }
        )


__all__ = [
    "CERTIFIED_SIMULATIONS",
    "FROZEN_PRESENTATION",
    "FROZEN_TRANSPORT",
    "MARKET_LINE_ROLE",
    "MODEL_VERSION",
    "MONTE_CARLO_ENABLED",
    "PROJECTION_MODEL_ENABLED",
    "RANKINGS_ENABLED",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_analytics_card",
    "_analytics_for_game",
    "_cached_game_mc",
    "_first_book",
    "_summary_html",
    "render_nfl_hub",
]
