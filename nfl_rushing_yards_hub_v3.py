"""NFL Rushing Yards V3 — Step 4 exact-ID live market context.

Additive presentation wrapper over certified Rushing Yards V2. V2 remains the
owner of Steps 1-3 and the frozen market-blind projection. V3 adds only a
post-projection FanDuel market comparison from ``nfl_rushing_yards_market_api_v1``.

Permanent separation:
- the V2 projection finishes before any market request is evaluated;
- sportsbook projection influence remains exactly 0.0%;
- exact ESPN event/team/athlete identity is required;
- missing/stale/ambiguous market data fails closed;
- probability, fair odds, EV, value grading, ranking, recommendation, stake
  sizing and wager actions remain OFF because Rushing Yards does not yet have a
  certified probability distribution.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_rushing_yards_hub_v2 as prior
import nfl_rushing_yards_market_api_v1 as market_api

MODEL_VERSION = "NFL RUSHING YARDS V3 • STEP 4 EXACT-ID LIVE MARKET CONTEXT"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v2"

_ORIGINAL_STEP3_RENDER = prior._render_step3_projection
_ORIGINAL_ADVANCE_COPY = prior._advance_step3_copy
_ORIGINAL_MARKDOWN = st.markdown

_STEP4_CSS = r'''
<style>
.krush-fill{width:100%!important}
.krush-mkt-banner{border:1px solid #3d5f78;border-radius:14px;background:#0b1821;padding:10px 12px;margin:10px 0;color:#a8cae1;font-size:.63rem;line-height:1.5}
.krush-mkt-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px;margin:8px 0 12px}
.krush-mkt{border:1px solid #324e63;background:#07131d;border-radius:15px;padding:11px;min-width:0}
.krush-mkt.off{border-color:#4b4b43;background:#16150f}
.krush-mkt-top{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}
.krush-mkt-name{color:#f2f8fb;font-size:.78rem;font-weight:950}.krush-mkt-sub{color:#71889a;font-size:.52rem;margin-top:3px;line-height:1.4}
.krush-mkt-state{font-size:.49rem;font-weight:950;border:1px solid #41677e;border-radius:999px;padding:4px 7px;color:#9dd7f3;white-space:nowrap}
.krush-mkt-state.off{color:#d1bc7b;border-color:#796a3d;background:#282313}
.krush-mkt-hero{display:grid;grid-template-columns:1.15fr repeat(2,minmax(0,1fr));gap:6px;margin-top:9px}
.krush-mkt-metric{border-top:1px solid #20394a;padding-top:7px}.krush-mkt-metric b{display:block;color:#f5fbff;font-size:.92rem}.krush-mkt-metric span{display:block;color:#687f90;font-size:.46rem;text-transform:uppercase;font-weight:900;margin-top:2px}
.krush-mkt-price{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-top:8px}.krush-mkt-price>div{border:1px solid #1e3545;border-radius:9px;padding:7px;background:#091722}.krush-mkt-price b{display:block;color:#e8f4fb;font-size:.72rem}.krush-mkt-price span{color:#6d8495;font-size:.46rem;text-transform:uppercase;font-weight:900}
.krush-mkt-note{margin-top:8px;padding-top:7px;border-top:1px solid #1d3342;color:#7f97a8;font-size:.51rem;line-height:1.55}
@media(max-width:760px){.krush-mkt-grid{grid-template-columns:1fr}.krush-mkt-hero{grid-template-columns:1fr 1fr}.krush-mkt-hero>div:first-child{grid-column:1/-1}}
</style>
'''


def _safe(value: Any, default: str = "—") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _number(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _fmt(value: Any, digits: int = 1) -> str:
    number = _number(value)
    if not math.isfinite(number):
        return "—"
    rendered = f"{number:.{digits}f}"
    return rendered.rstrip("0").rstrip(".") if digits > 0 else rendered


def _american(value: Any) -> str:
    number = _number(value)
    if not math.isfinite(number):
        return "—"
    return f"{number:+.0f}"


def _signed_yards(value: Any) -> str:
    number = _number(value)
    if not math.isfinite(number):
        return "—"
    return f"{number:+.1f}"


@st.cache_data(ttl=20, show_spinner=False)
def _load_rushing_market(event_id: str) -> dict:
    return market_api.fetch_event_market(str(event_id))


def _advance_step4_copy(body: Any) -> Any:
    """Apply frozen V2 copy first, then advance only the Step 4 build labels."""
    out = _ORIGINAL_ADVANCE_COPY(body)
    if not isinstance(out, str):
        return out
    replacements = (
        (
            "Step 3 adds a transparent market-blind rushing-yards baseline on top of verified current-roster workload and opponent run-front context. Live market, probability, EV, grading and staking remain locked for Step 4.",
            "Step 4 adds fresh exact-ID FanDuel Rushing Yards market context only after the frozen Step 3 projection is complete. Probability, fair odds, EV, value grading and staking remain locked until a certified Rushing Yards distribution exists.",
        ),
        (
            '<span class="krush-chip">✅ PROJECTION ENGINE</span>',
            '<span class="krush-chip">✅ LIVE MARKET CONTEXT</span>',
        ),
        (
            '<div class="krush-tool"><div class="icon">🎯</div><b>Market Edge</b><span>Verified line, probability and grade come later.</span></div>',
            '<div class="krush-tool live"><div class="icon">🎯</div><b>Live Market ✅</b><span>Fresh exact-ID FanDuel line + two-way price. Value grade remains locked.</span></div>',
        ),
        ("3 OF 4 • PROJECTION LIVE", "4 OF 4 • MARKET LIVE • GRADE LOCKED"),
        (
            '<span class="krush-stage">4 • LIVE MARKET + FINAL GRADE</span>',
            '<span class="krush-stage on">4 • LIVE MARKET ✅ • GRADE LOCKED</span>',
        ),
        (
            "🧊 <b>Frozen-line guard:</b> Step 3 adds only the isolated Rushing Yards market-blind baseline projection. The certified Passing Yards chain, FanDuel transport, probability, live market, EV, grading, ranking, recommendation, staking and every CFB surface remain untouched. Sportsbook projection influence remains 0.0%.",
            "🧊 <b>Frozen-line guard:</b> Step 4 adds only fresh post-projection Rushing Yards market context. The Step 3 projection math is unchanged and receives 0.0% sportsbook influence. Passing Yards, probability, fair odds, EV, grading, ranking, recommendation, staking and every CFB surface remain untouched.",
        ),
    )
    for old, new in replacements:
        out = out.replace(old, new)
    return out


def _market_card(projection_row: dict[str, Any], market_row: dict[str, Any]) -> str:
    player = escape(_safe(projection_row.get("player_name"), "Unknown rusher"))
    athlete_id = escape(_safe(projection_row.get("official_athlete_id")))
    team_id = escape(_safe(projection_row.get("official_team_id")))
    projection = _number(projection_row.get("projection_yards"))

    if not market_row.get("ready"):
        reason = escape(_safe(market_row.get("reason"), "fresh exact-ID market unavailable"))
        return f'''
        <article class="krush-mkt off">
          <div class="krush-mkt-top">
            <div>
              <div class="krush-mkt-name">{player} • Market Context</div>
              <div class="krush-mkt-sub">ESPN athlete {athlete_id} • ESPN team {team_id}</div>
            </div>
            <span class="krush-mkt-state off">MARKET CHECK</span>
          </div>
          <div class="krush-mkt-note">{reason}<br>No line, price, probability, value grade or recommendation was invented.</div>
        </article>
        '''

    line = _number(market_row.get("line"))
    gap = projection - line if math.isfinite(projection) and math.isfinite(line) else math.nan
    age = _number(market_row.get("age_seconds"))
    freshness = f"{max(0.0, age):.0f}s old" if math.isfinite(age) else "freshness verified"
    captured = escape(_safe(market_row.get("captured_at_utc"), "timestamp verified"))
    return f'''
    <article class="krush-mkt">
      <div class="krush-mkt-top">
        <div>
          <div class="krush-mkt-name">{player} • FanDuel Market Context</div>
          <div class="krush-mkt-sub">ESPN athlete {athlete_id} • ESPN team {team_id} • {escape(freshness)}</div>
        </div>
        <span class="krush-mkt-state">EXACT-ID LIVE</span>
      </div>
      <div class="krush-mkt-hero">
        <div class="krush-mkt-metric"><b>{escape(_fmt(projection, 1))}</b><span>Frozen Projection</span></div>
        <div class="krush-mkt-metric"><b>{escape(_fmt(line, 1))}</b><span>Market Line</span></div>
        <div class="krush-mkt-metric"><b>{escape(_signed_yards(gap))}</b><span>Projection − Line</span></div>
      </div>
      <div class="krush-mkt-price">
        <div><b>{escape(_american(market_row.get('over_odds')))}</b><span>Over Price</span></div>
        <div><b>{escape(_american(market_row.get('under_odds')))}</b><span>Under Price</span></div>
      </div>
      <div class="krush-mkt-note">
        Captured {captured}. Projection gap is descriptive comparison only—not a probability, value grade or betting recommendation.<br>
        Sportsbook projection influence: <b>0.0%</b> • probability/fair odds/EV/grading/staking: <b>OFF</b>
      </div>
    </article>
    '''


def _render_step4_market(context: dict[str, Any], event_id: str) -> None:
    """Render fresh post-projection market context without changing Step 3 math."""
    projection_result = prior.projection.build_event_projections(context)
    if not projection_result.get("ready"):
        return

    _ORIGINAL_MARKDOWN(
        '<div class="krush-section"><h3>🎯 Step 4 • Live Market Context</h3><span>FANDUEL • EXACT ESPN IDs • POST-PROJECTION</span></div>',
        unsafe_allow_html=True,
    )
    _ORIGINAL_MARKDOWN(
        '<div class="krush-mkt-banner">✅ The Step 3 projection is already finished before Step 4 reads any sportsbook data. Step 4 may display a fresh exact-ID FanDuel line and two-way price beside that frozen number, but it cannot modify the projection. Probability, fair odds, EV and final value grading remain locked until a certified Rushing Yards distribution exists.</div>',
        unsafe_allow_html=True,
    )

    event_market = _load_rushing_market(event_id)
    if not event_market.get("ready"):
        st.warning(
            "Step 4 market context failed closed. The Step 3 projection remains valid and unchanged. "
            f"Reason: {event_market.get('reason') or 'fresh verified market unavailable'}"
        )
        return
    if not event_market.get("market_available"):
        st.info("FanDuel returned no fresh canonical two-way Rushing Yards market for this exact event. No market line or price was fabricated.")
        return

    cards: list[str] = []
    matched = 0
    for row in projection_result.get("projections") or []:
        market_row = market_api.market_for_athlete(
            event_market,
            _safe(row.get("official_athlete_id"), ""),
            _safe(row.get("official_team_id"), ""),
        )
        if market_row.get("ready"):
            matched += 1
        cards.append(_market_card(row, market_row))

    _ORIGINAL_MARKDOWN(f'<div class="krush-mkt-grid">{"".join(cards)}</div>', unsafe_allow_html=True)
    st.caption(
        f"✅ {matched} fresh exact-ID market match(es) • ESPN event {event_id} • "
        f"FanDuel • max freshness {market_api.MAX_MARKET_AGE_SECONDS}s • projection influence 0.0% • "
        "probability/fair odds/EV/value grading/staking OFF"
    )


def _render_step3_and_step4(context: dict[str, Any], event_id: str) -> None:
    _ORIGINAL_STEP3_RENDER(context, event_id)
    _render_step4_market(context, event_id)


def render_nfl_rushing_yards_hub() -> None:
    """Render frozen Steps 1-3 plus isolated Step 4 live market context."""
    _ORIGINAL_MARKDOWN(_STEP4_CSS, unsafe_allow_html=True)
    original_step3 = prior._render_step3_projection
    original_copy = prior._advance_step3_copy
    prior._render_step3_projection = _render_step3_and_step4
    prior._advance_step3_copy = _advance_step4_copy
    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        prior._render_step3_projection = original_step3
        prior._advance_step3_copy = original_copy


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V3 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "_advance_step4_copy",
    "_load_rushing_market",
    "_market_card",
    "_render_step3_and_step4",
    "_render_step4_market",
    "render_nfl_hub",
    "render_nfl_rushing_yards_hub",
]
