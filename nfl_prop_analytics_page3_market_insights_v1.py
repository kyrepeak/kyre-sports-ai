"""NFL Prop Analytics Page 3 Step 7 — market + insights.

Adds the agreed Page 3 market/insight surface after frozen Step 6:
- Over / Under side selection;
- alternate analysis thresholds around the frozen Step 4 line;
- fresh exact-ID FanDuel odds when an already-certified Kyre Sports API
  market client exists for the selected prop;
- compact Statistics / Supporting Stats / Insights / Key Notes views.

Safety contract:
- PENDING availability keeps this entire Step 7 live-analysis surface LOCKED;
- no sportsbook request is made while the frozen prop-analysis gate is closed;
- sportsbook data is context only and has 0.0% projection influence;
- alternate thresholds are never represented as sportsbook alternate prices;
- unsupported/missing/stale market data fails closed;
- no projections, probabilities, recommendations, staking, or wager actions.
"""
from __future__ import annotations

import html as html_lib
import math
from statistics import mean
from typing import Any

import streamlit as st

import nfl_passing_yards_market_api_v2 as passing_market
import nfl_receiving_yards_market_api_v1 as receiving_market
import nfl_rushing_yards_market_api_v1 as rushing_market

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 STEP 7 • MARKET + INSIGHTS V1"
PAGE3_MARKET_INSIGHTS_STEP = 7
PAGE3_MARKET_INSIGHTS_VERSION = "v1"

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_LOGIC = False
PROBABILITY_LOGIC = False
RECOMMENDATION_LOGIC = False
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS = False
LIVE_ANALYTICS_REQUIRES_AVAILABLE = True
ALT_LINES_ARE_SPORTSBOOK_PRICES = False

VERIFIED_MARKET_CLIENTS = {
    "passing_yards": passing_market,
    "receiving_yards": receiving_market,
    "rushing_yards": rushing_market,
}

SECTION_OPTIONS = ("STATISTICS", "SUPPORTING STATS", "INSIGHTS", "KEY NOTES")


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _number(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _fmt_number(value: Any, digits: int = 1) -> str:
    number = _number(value)
    if number is None:
        return "—"
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.{digits}f}"


def _fmt_odds(value: Any) -> str:
    number = _number(value)
    if number is None or abs(number) < 100 or not float(number).is_integer():
        return "—"
    return f"{int(number):+d}"


def _line_step(market_key: str) -> float:
    key = _text(market_key)
    if key in {"passing_yards", "rushing_yards", "receiving_yards", "longest_reception"}:
        return 5.0
    if key in {"attempts", "completions", "carries", "receptions"}:
        return 1.0
    return 0.5


def build_alternate_lines(
    anchor_line: Any,
    market_key: str,
    *,
    verified_market_line: Any = None,
) -> list[float]:
    """Build deterministic analysis thresholds; never fabricate sportsbook prices."""
    anchor = _number(anchor_line)
    if anchor is None or anchor <= 0:
        return []
    step = _line_step(market_key)
    values = {
        round(anchor + (offset * step), 1)
        for offset in (-2, -1, 0, 1, 2)
        if anchor + (offset * step) > 0
    }
    market_line = _number(verified_market_line)
    if market_line is not None and market_line > 0:
        values.add(round(market_line, 1))
    return sorted(values)


def historical_side_summary(
    games: list[dict[str, Any]],
    *,
    line: Any,
    side: str,
) -> dict[str, Any]:
    threshold = _number(line)
    side = _text(side).upper()
    values = [
        float(value)
        for value in (_number((row or {}).get("value")) for row in games or [])
        if value is not None
    ]
    if threshold is None or threshold < 0 or side not in {"OVER", "UNDER"} or not values:
        return {
            "ready": False,
            "sample_size": len(values),
            "decisive_count": 0,
            "hit_count": 0,
            "push_count": 0,
            "hit_rate_pct": None,
        }

    push_count = sum(1 for value in values if abs(value - threshold) < 1e-9)
    decisive = [value for value in values if abs(value - threshold) >= 1e-9]
    if side == "OVER":
        hits = sum(1 for value in decisive if value > threshold)
    else:
        hits = sum(1 for value in decisive if value < threshold)
    return {
        "ready": bool(decisive),
        "sample_size": len(values),
        "decisive_count": len(decisive),
        "hit_count": hits,
        "push_count": push_count,
        "hit_rate_pct": (100.0 * hits / len(decisive)) if decisive else None,
        "average": mean(values),
        "recent3_average": mean(values[:3]) if values[:3] else None,
    }


def load_verified_market(
    *,
    official_event_id: str,
    official_athlete_id: str,
    market_key: str,
    gate_open: bool,
) -> dict[str, Any]:
    event_id = _text(official_event_id)
    athlete_id = _text(official_athlete_id)
    key = _text(market_key)

    if not gate_open:
        return {
            "ready": False,
            "state": "locked",
            "reason": "frozen player availability gate is closed",
            "projection_weight": 0.0,
            "market_context_only": True,
        }

    client = VERIFIED_MARKET_CLIENTS.get(key)
    if client is None:
        return {
            "ready": False,
            "state": "unsupported",
            "reason": "no certified exact-ID sportsbook client exists for this prop",
            "projection_weight": 0.0,
            "market_context_only": True,
        }
    if not event_id.isdigit() or not athlete_id.isdigit():
        return {
            "ready": False,
            "state": "unavailable",
            "reason": "official event + athlete IDs are required",
            "projection_weight": 0.0,
            "market_context_only": True,
        }

    try:
        event_market = client.fetch_event_market(event_id)
        athlete_market = client.market_for_athlete(event_market, athlete_id)
    except Exception as exc:
        return {
            "ready": False,
            "state": "unavailable",
            "reason": f"verified market read failed: {type(exc).__name__}",
            "projection_weight": 0.0,
            "market_context_only": True,
        }

    if athlete_market.get("ready") is not True:
        return {
            "ready": False,
            "state": "unavailable",
            "reason": _text(athlete_market.get("reason")) or "fresh exact-ID market unavailable",
            "projection_weight": 0.0,
            "market_context_only": True,
        }

    if (
        athlete_market.get("projection_weight") != 0.0
        or athlete_market.get("market_context_only") is not True
    ):
        return {
            "ready": False,
            "state": "unavailable",
            "reason": "sportsbook safety contract failed closed",
            "projection_weight": 0.0,
            "market_context_only": True,
        }

    line = _number(athlete_market.get("line"))
    over_odds = _number(athlete_market.get("over_odds"))
    under_odds = _number(athlete_market.get("under_odds"))
    sportsbook = _text(athlete_market.get("sportsbook")) or _text(event_market.get("sportsbook")) or "FanDuel"
    if line is None or line <= 0 or over_odds is None or under_odds is None:
        return {
            "ready": False,
            "state": "unavailable",
            "reason": "verified two-way market is incomplete",
            "projection_weight": 0.0,
            "market_context_only": True,
        }

    return {
        "ready": True,
        "state": "verified",
        "reason": "",
        "official_event_id": event_id,
        "official_athlete_id": athlete_id,
        "market_key": key,
        "line": line,
        "over_odds": over_odds,
        "under_odds": under_odds,
        "sportsbook": sportsbook,
        "captured_at_utc": _text(athlete_market.get("captured_at_utc")),
        "age_seconds": _number(athlete_market.get("age_seconds")),
        "projection_weight": 0.0,
        "market_context_only": True,
    }


def build_insights(
    *,
    games: list[dict[str, Any]],
    selected_line: Any,
    side: str,
    history_summary: dict[str, Any],
) -> list[dict[str, str]]:
    side_summary = historical_side_summary(games, line=selected_line, side=side)
    line = _number(selected_line)
    avg = _number(history_summary.get("average"))
    med = _number(history_summary.get("median"))
    cards: list[dict[str, str]] = []

    if side_summary.get("ready"):
        cards.append({
            "title": "THRESHOLD FREQUENCY",
            "value": f"{float(side_summary['hit_rate_pct']):.0f}%",
            "note": (
                f"{side_summary['hit_count']}/{side_summary['decisive_count']} "
                f"decisive games finished {_text(side).upper()} {_fmt_number(line)}"
            ),
        })

    if line is not None and avg is not None:
        delta = avg - line
        cards.append({
            "title": "AVERAGE VS LINE",
            "value": f"{delta:+.1f}",
            "note": f"Window average {_fmt_number(avg)} vs selected analysis threshold {_fmt_number(line)}",
        })

    if line is not None and med is not None:
        delta = med - line
        cards.append({
            "title": "MEDIAN VS LINE",
            "value": f"{delta:+.1f}",
            "note": f"Window median {_fmt_number(med)} vs selected analysis threshold {_fmt_number(line)}",
        })

    recent = _number(side_summary.get("recent3_average"))
    full = _number(side_summary.get("average"))
    if recent is not None and full is not None:
        cards.append({
            "title": "RECENT 3 VS WINDOW",
            "value": f"{(recent-full):+.1f}",
            "note": f"Recent 3 average {_fmt_number(recent)} vs full-window average {_fmt_number(full)}",
        })
    return cards[:4]


def _locked_markup(availability_state: str) -> str:
    return f"""
<section class="ks-pa7mi ks-pa7mi-locked"
         data-prop-page3-step7-market-insights="{PAGE3_MARKET_INSIGHTS_VERSION}"
         data-prop-page3-step7-state="locked"
         data-prop-page3-step7-gate="CLOSED"
         data-prop-page3-step7-availability="{html_lib.escape(_text(availability_state).upper())}"
         data-prop-page3-step7-odds-state="locked"
         data-prop-page3-step7-projection-weight="0.0">
  <div class="ks-pa7mi-head">
    <div><span>MARKET + INSIGHTS</span><strong>Live analysis locked</strong></div>
    <em>AVAILABILITY GATE CLOSED</em>
  </div>
  <p>Player navigation remains available, but live market + insight analysis waits for verified game-day AVAILABLE status.</p>
</section>
"""


def render_market_insights(
    *,
    games: list[dict[str, Any]],
    line: Any,
    history_summary: dict[str, Any],
    supporting_stats: dict[str, Any],
    official_event_id: str,
    official_athlete_id: str,
    market_key: str,
    market_label: str,
    history_key: str,
    history_label: str,
    gate_open: bool,
    availability_state: str,
) -> dict[str, Any]:
    """Render Step 7 only after frozen upstream data is present and gate is open."""
    if not gate_open:
        st.markdown(_locked_markup(availability_state), unsafe_allow_html=True)
        return {
            "ready": False,
            "state": "locked",
            "reason": "frozen player availability gate is closed",
            "projection_weight": 0.0,
        }

    anchor = _number(line)
    if anchor is None or anchor <= 0 or supporting_stats.get("ready") is not True:
        reason = (
            "verified Step 4 analysis line is required"
            if anchor is None or anchor <= 0
            else "verified Step 6 supporting stats are required"
        )
        st.markdown(
            f"""
<section class="ks-pa7mi ks-pa7mi-unavailable"
         data-prop-page3-step7-market-insights="{PAGE3_MARKET_INSIGHTS_VERSION}"
         data-prop-page3-step7-state="unavailable"
         data-prop-page3-step7-gate="OPEN"
         data-prop-page3-step7-odds-state="unavailable"
         data-prop-page3-step7-projection-weight="0.0">
  <div class="ks-pa7mi-head"><div><span>MARKET + INSIGHTS</span><strong>Input unavailable</strong></div><em>FAIL CLOSED</em></div>
  <p>{html_lib.escape(reason)}</p>
</section>
""",
            unsafe_allow_html=True,
        )
        return {"ready": False, "state": "unavailable", "reason": reason, "projection_weight": 0.0}

    verified_market = load_verified_market(
        official_event_id=official_event_id,
        official_athlete_id=official_athlete_id,
        market_key=market_key,
        gate_open=True,
    )
    verified_line = verified_market.get("line") if verified_market.get("ready") else None
    alt_lines = build_alternate_lines(anchor, market_key, verified_market_line=verified_line)

    side = st.segmented_control(
        "Over / Under",
        options=["OVER", "UNDER"],
        default="OVER",
        selection_mode="single",
        key="nfl_prop_analytics_page3_step7_side_v1",
    )
    side = side if side in {"OVER", "UNDER"} else "OVER"

    line_labels = [_fmt_number(value) for value in alt_lines]
    default_line_label = _fmt_number(anchor)
    if default_line_label not in line_labels and line_labels:
        default_line_label = line_labels[len(line_labels) // 2]
    selected_label = st.segmented_control(
        "Alternate analysis line",
        options=line_labels,
        default=default_line_label if line_labels else None,
        selection_mode="single",
        key="nfl_prop_analytics_page3_step7_alt_line_v1",
    )
    if selected_label not in line_labels:
        selected_label = default_line_label
    selected_line = next(
        (value for value in alt_lines if _fmt_number(value) == selected_label),
        anchor,
    )

    section = st.segmented_control(
        "Analysis section",
        options=list(SECTION_OPTIONS),
        default="INSIGHTS",
        selection_mode="single",
        key="nfl_prop_analytics_page3_step7_section_v1",
    )
    section = section if section in SECTION_OPTIONS else "INSIGHTS"

    side_summary = historical_side_summary(games, line=selected_line, side=side)
    insights = build_insights(
        games=games,
        selected_line=selected_line,
        side=side,
        history_summary=history_summary,
    )
    odds_state = "verified" if verified_market.get("ready") else _text(verified_market.get("state")) or "unavailable"

    market_html = ""
    if verified_market.get("ready"):
        market_html = f"""
  <div class="ks-pa7mi-market" data-prop-page3-step7-verified-market="true">
    <div><span>VERIFIED SPORTSBOOK</span><strong>{html_lib.escape(_text(verified_market.get("sportsbook")))}</strong></div>
    <div><span>MAIN LINE</span><strong>{_fmt_number(verified_market.get("line"))}</strong></div>
    <div><span>OVER</span><strong>{_fmt_odds(verified_market.get("over_odds"))}</strong></div>
    <div><span>UNDER</span><strong>{_fmt_odds(verified_market.get("under_odds"))}</strong></div>
  </div>
"""
    else:
        market_html = f"""
  <div class="ks-pa7mi-market ks-pa7mi-market-off" data-prop-page3-step7-verified-market="false">
    <div><span>VERIFIED SPORTSBOOK</span><strong>UNAVAILABLE</strong></div>
    <p>{html_lib.escape(_text(verified_market.get("reason")) or "No fresh exact-ID market is available.")}</p>
  </div>
"""

    body_html = ""
    if section == "STATISTICS":
        rate = (
            f"{float(side_summary['hit_rate_pct']):.0f}%"
            if side_summary.get("hit_rate_pct") is not None
            else "—"
        )
        body_html = f"""
  <div class="ks-pa7mi-grid">
    <article><span>SAMPLE</span><strong>{int(side_summary.get("sample_size") or 0)}</strong><small>{html_lib.escape(history_label)}</small></article>
    <article><span>{html_lib.escape(side)} RATE</span><strong>{rate}</strong><small>DECISIVE GAMES</small></article>
    <article><span>AVERAGE</span><strong>{_fmt_number(history_summary.get("average"))}</strong><small>{html_lib.escape(market_label.upper())}</small></article>
    <article><span>MEDIAN</span><strong>{_fmt_number(history_summary.get("median"))}</strong><small>WINDOW MEDIAN</small></article>
  </div>
"""
    elif section == "SUPPORTING STATS":
        metrics = list(supporting_stats.get("metrics") or [])[:6]
        body_html = '<div class="ks-pa7mi-grid">' + "".join(
            f"<article data-prop-page3-step7-support-metric=\"{html_lib.escape(_text(row.get('key')))}\"><span>{html_lib.escape(_text(row.get('label')))}</span><strong>{_fmt_number(row.get('value'))}</strong><small>{html_lib.escape(_text(row.get('unit')) or 'VERIFIED')}</small></article>"
            for row in metrics
        ) + "</div>"
    elif section == "INSIGHTS":
        body_html = '<div class="ks-pa7mi-insights">' + "".join(
            f"<article><span>{html_lib.escape(card['title'])}</span><strong>{html_lib.escape(card['value'])}</strong><p>{html_lib.escape(card['note'])}</p></article>"
            for card in insights
        ) + "</div>"
    else:
        source = (
            f"{_text(verified_market.get('sportsbook'))} exact-ID live market"
            if verified_market.get("ready")
            else "verified sportsbook unavailable / fail closed"
        )
        body_html = f"""
  <div class="ks-pa7mi-notes">
    <p><strong>Identity:</strong> ESPN event {html_lib.escape(_text(official_event_id))} • athlete {html_lib.escape(_text(official_athlete_id))}</p>
    <p><strong>Selected threshold:</strong> {html_lib.escape(side)} {_fmt_number(selected_line)} • analysis threshold, not a fabricated sportsbook alternate.</p>
    <p><strong>Market source:</strong> {html_lib.escape(source)}</p>
    <p><strong>Safety:</strong> sportsbook projection influence 0.0% • no projection, probability, recommendation, stake sizing, or wager action.</p>
  </div>
"""

    st.markdown(
        f"""
<section class="ks-pa7mi"
         data-prop-page3-step7-market-insights="{PAGE3_MARKET_INSIGHTS_VERSION}"
         data-prop-page3-step7-state="ready"
         data-prop-page3-step7-gate="OPEN"
         data-prop-page3-step7-availability="{html_lib.escape(_text(availability_state).upper())}"
         data-prop-page3-step7-market="{html_lib.escape(_text(market_key))}"
         data-prop-page3-step7-history="{html_lib.escape(_text(history_key))}"
         data-prop-page3-step7-side="{html_lib.escape(side.lower())}"
         data-prop-page3-step7-line="{_fmt_number(selected_line)}"
         data-prop-page3-step7-alt-count="{len(alt_lines)}"
         data-prop-page3-step7-section="{html_lib.escape(section.lower().replace(' ', '-'))}"
         data-prop-page3-step7-odds-state="{html_lib.escape(odds_state)}"
         data-prop-page3-step7-projection-weight="0.0"
         data-prop-page3-step7-recommendations="0"
         data-prop-page3-step7-wager-actions="0">
  <div class="ks-pa7mi-head">
    <div><span>MARKET + INSIGHTS</span><strong>{html_lib.escape(market_label)} • {html_lib.escape(history_label)}</strong></div>
    <em>HISTORICAL + VERIFIED MARKET CONTEXT</em>
  </div>
  <div class="ks-pa7mi-selected">
    <div><span>SELECTED SIDE</span><strong>{html_lib.escape(side)}</strong></div>
    <div><span>ANALYSIS LINE</span><strong>{_fmt_number(selected_line)}</strong></div>
    <div><span>ALT THRESHOLDS</span><strong>{len(alt_lines)}</strong></div>
  </div>
  {market_html}
  <div class="ks-pa7mi-section"><span>{html_lib.escape(section)}</span></div>
  {body_html}
  <div class="ks-pa7mi-foot">Alternate lines are analysis thresholds only. Verified sportsbook odds appear only when a fresh exact-ID certified market exists.</div>
</section>

<style data-prop-page3-step7-css="v1">
.ks-pa7mi{{width:100%;max-width:100%;min-width:0;overflow-x:clip;margin:12px 0 18px;padding:clamp(12px,2vw,18px);border:1px solid rgba(125,211,252,.18);border-radius:18px;background:linear-gradient(150deg,rgba(4,11,20,.99),rgba(7,19,32,.97));box-shadow:0 18px 45px rgba(0,0,0,.17)}}
.ks-pa7mi-head{{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding-bottom:10px;border-bottom:1px solid rgba(148,163,184,.09)}}
.ks-pa7mi-head div{{display:flex;flex-direction:column;gap:3px}}.ks-pa7mi-head span{{color:#7dd3fc;font-size:.58rem;font-weight:950;letter-spacing:.13em}}.ks-pa7mi-head strong{{color:#f0f9ff;font-size:.88rem}}.ks-pa7mi-head em{{color:#60758d;font-size:.48rem;font-style:normal;font-weight:850;text-align:right}}
.ks-pa7mi-selected,.ks-pa7mi-market,.ks-pa7mi-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:10px}}
.ks-pa7mi-selected>div,.ks-pa7mi-market>div,.ks-pa7mi-grid article,.ks-pa7mi-insights article{{min-width:0;padding:9px;border:1px solid rgba(125,211,252,.10);border-radius:11px;background:rgba(7,17,29,.72)}}
.ks-pa7mi-selected span,.ks-pa7mi-market span,.ks-pa7mi-grid span,.ks-pa7mi-insights span{{display:block;color:#6f879f;font-size:.48rem;font-weight:900;letter-spacing:.08em}}.ks-pa7mi-selected strong,.ks-pa7mi-market strong,.ks-pa7mi-grid strong,.ks-pa7mi-insights strong{{display:block;margin-top:3px;color:#e6f7ff;font-size:.78rem}}
.ks-pa7mi-grid small{{display:block;margin-top:2px;color:#587087;font-size:.43rem}}.ks-pa7mi-market-off{{grid-template-columns:1fr}}.ks-pa7mi-market-off p,.ks-pa7mi-locked p,.ks-pa7mi-unavailable p{{margin:5px 0 0;color:#71869c;font-size:.6rem;line-height:1.45}}
.ks-pa7mi-section{{margin-top:11px;padding-top:9px;border-top:1px solid rgba(148,163,184,.08)}}.ks-pa7mi-section span{{color:#bae6fd;font-size:.58rem;font-weight:950;letter-spacing:.1em}}
.ks-pa7mi-insights{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;margin-top:8px}}.ks-pa7mi-insights p{{margin:4px 0 0;color:#71869c;font-size:.53rem;line-height:1.4}}
.ks-pa7mi-notes{{display:grid;gap:5px;margin-top:8px}}.ks-pa7mi-notes p{{margin:0;padding:7px 8px;border:1px solid rgba(148,163,184,.08);border-radius:9px;color:#8196ad;font-size:.56rem;line-height:1.4}}.ks-pa7mi-notes strong{{color:#cceeff}}
.ks-pa7mi-foot{{margin-top:10px;color:#526a82;font-size:.48rem;line-height:1.45}}
.ks-pa7mi-locked{{border-color:rgba(251,191,36,.18)}}.ks-pa7mi-unavailable{{border-color:rgba(248,113,113,.15)}}
@media(max-width:620px){{.ks-pa7mi-head{{flex-direction:column}}.ks-pa7mi-head em{{text-align:left}}.ks-pa7mi-selected,.ks-pa7mi-market,.ks-pa7mi-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.ks-pa7mi-insights{{grid-template-columns:1fr}}}}
</style>
""",
        unsafe_allow_html=True,
    )

    return {
        "ready": True,
        "state": "ready",
        "side": side.lower(),
        "line": selected_line,
        "alternate_lines": alt_lines,
        "section": section,
        "history": side_summary,
        "insights": insights,
        "market": verified_market,
        "odds_state": odds_state,
        "projection_weight": 0.0,
        "recommendations": False,
        "wager_actions": False,
    }


__all__ = [
    "ALT_LINES_ARE_SPORTSBOOK_PRICES",
    "LIVE_ANALYTICS_REQUIRES_AVAILABLE",
    "MODEL_VERSION",
    "PAGE3_MARKET_INSIGHTS_STEP",
    "PAGE3_MARKET_INSIGHTS_VERSION",
    "PROBABILITY_LOGIC",
    "PROJECTION_LOGIC",
    "RECOMMENDATION_LOGIC",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "VERIFIED_MARKET_CLIENTS",
    "WAGER_ACTIONS",
    "build_alternate_lines",
    "build_insights",
    "historical_side_summary",
    "load_verified_market",
    "render_market_insights",
]
