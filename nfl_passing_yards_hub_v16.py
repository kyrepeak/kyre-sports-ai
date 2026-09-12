"""NFL Passing Yards V16 — cleanup step 4: matchup spotlight + why projection.

Presentation-only wrapper over certified V15. It adds a polished matchup strip with
team logos, QB-vs-defense pairing, and a compact "why this projection" summary
built entirely from already-computed certified Steps 1, 7, 8, 9 and 10 outputs.

No loader, projection, context, distribution, probability, market, grading, or
sportsbook-influence math changes. No new server-side data requests are made.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

import streamlit as st

import nfl_passing_yards_hub_v15 as prior
import nfl_passing_yards_hub_v8 as step7_ui
import nfl_passing_yards_hub_v9 as step8_ui
import nfl_passing_yards_hub_v10 as step9_ui
import nfl_passing_yards_hub_v11 as step10_ui

MODEL_VERSION = "NFL PASSING YARDS V16 • CLEANUP STEP 4 • MATCHUP SPOTLIGHT"

_CLEANUP_STEP4_CSS = r"""
<style>
.kpy15-head,.kpy15-center{display:none!important}
.kpy16-head{border:1px solid #31546d;background:linear-gradient(135deg,#06111b,#0b1e2d);border-radius:15px;padding:12px 13px;margin:3px 0 8px;box-shadow:0 9px 26px rgba(0,0,0,.18)}
.kpy16-headrow{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.kpy16-title{font-size:1.2rem;font-weight:950;color:#f8fbff;letter-spacing:-.025em;line-height:1.05}.kpy16-title span{color:#7ff2c2}.kpy16-sub{font-size:.58rem;color:#8498aa;line-height:1.45;margin-top:4px;max-width:760px}.kpy16-status{border:1px solid #34795b;background:#09271d;color:#81edb7;border-radius:999px;padding:5px 8px;font-size:.48rem;font-weight:950;white-space:nowrap}
.kpy16-match{border:1px solid #28475d;background:#06111b;border-radius:14px;padding:10px;margin:0 0 8px}.kpy16-matchhead{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px}.kpy16-matchtitle{font-size:.78rem;font-weight:950;color:#eef7fb}.kpy16-matchsub{font-size:.45rem;color:#738a9d;margin-top:2px}.kpy16-tag{font-size:.42rem;font-weight:950;color:#9ed3ff;border:1px solid #3b6380;background:#092132;border-radius:999px;padding:4px 6px;white-space:nowrap}
.kpy16-versus{display:grid;grid-template-columns:1fr auto 1fr;gap:7px;align-items:stretch}.kpy16-side{border:1px solid #315269;background:#081521;border-radius:12px;padding:9px;min-width:0}.kpy16-sidehead{display:flex;align-items:center;gap:8px;margin-bottom:7px}.kpy16-logo{width:40px;height:40px;object-fit:contain;flex:0 0 auto;filter:drop-shadow(0 4px 8px rgba(0,0,0,.28))}.kpy16-team{font-size:.76rem;font-weight:950;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy16-site{font-size:.42rem;color:#6f8799;text-transform:uppercase;margin-top:2px}.kpy16-qb{font-size:.67rem;font-weight:900;color:#dce9f1;margin-bottom:2px}.kpy16-vsdef{font-size:.47rem;color:#7f96a8;line-height:1.45}.kpy16-at{align-self:center;color:#7ff2c2;font-size:.72rem;font-weight:950;border:1px solid #2d5e50;background:#082019;border-radius:999px;padding:5px 7px}
.kpy16-minis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:7px}.kpy16-mini{border:1px solid #1d394d;background:#05101a;border-radius:8px;padding:6px;min-width:0}.kpy16-mini b{display:block;color:#fff;font-size:.7rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.kpy16-mini span{display:block;color:#6c8395;font-size:.36rem;text-transform:uppercase;margin-top:2px}
.kpy16-why{border:1px solid #28475d;background:#07131f;border-radius:14px;padding:10px;margin:0 0 10px}.kpy16-whyhead{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:7px}.kpy16-whytitle{font-size:.78rem;font-weight:950;color:#eef7fb}.kpy16-whysub{font-size:.44rem;color:#738a9d;margin-top:2px}.kpy16-whygrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.kpy16-whycard{border:1px solid #315269;background:#081521;border-radius:12px;padding:9px;min-width:0}.kpy16-whytop{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.kpy16-whyname{font-size:.76rem;font-weight:950;color:#fff}.kpy16-conf{font-size:.41rem;font-weight:950;border-radius:999px;padding:4px 6px;border:1px solid #405d72;color:#b7c7d3;white-space:nowrap}.kpy16-conf.high{color:#7cebbb;border-color:#32775b;background:#09261c}.kpy16-conf.medium{color:#9ed3ff;border-color:#416d8d;background:#0a2233}.kpy16-conf.low{color:#efc978;border-color:#766239;background:#292312}
.kpy16-reasons{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;margin-top:7px}.kpy16-reason{border:1px solid #1d394d;background:#05101a;border-radius:8px;padding:6px}.kpy16-reason b{display:block;color:#f3f8fb;font-size:.64rem}.kpy16-reason span{display:block;color:#6f8799;font-size:.38rem;text-transform:uppercase;margin-top:2px}.kpy16-final{margin-top:7px;padding-top:7px;border-top:1px solid #1b3449;display:flex;justify-content:space-between;align-items:center;gap:8px}.kpy16-proj{font-size:.62rem;color:#dce9f1;font-weight:950}.kpy16-market{font-size:.43rem;color:#7990a4;text-align:right;line-height:1.4}.kpy16-grade{font-size:.4rem;font-weight:950;border-radius:999px;padding:4px 6px;border:1px solid #415c70;color:#a8bbc9}.kpy16-grade.a{color:#6af0ad;border-color:#2d7c58;background:#09281c}.kpy16-grade.b{color:#8ee9bd;border-color:#39745b;background:#0b251c}.kpy16-grade.c{color:#f1ca72;border-color:#796538;background:#2a2412}.kpy16-grade.pass{color:#9ed3ff;border-color:#416d8d;background:#0b2234}
.kpy16-foot{font-size:.42rem;color:#688094;margin-top:7px;line-height:1.45}
@media(max-width:700px){.kpy16-head{padding:11px 10px}.kpy16-title{font-size:1.08rem}.kpy16-sub{font-size:.55rem}.kpy16-status{font-size:.43rem;padding:4px 6px}.kpy16-match,.kpy16-why{padding:8px}.kpy16-versus{grid-template-columns:1fr}.kpy16-at{justify-self:center;padding:4px 7px}.kpy16-whygrid{grid-template-columns:1fr}.kpy16-logo{width:36px;height:36px}.kpy16-minis{grid-template-columns:repeat(3,minmax(0,1fr))}.kpy16-reasons{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""

_HEADER = """
<section class="kpy16-head">
  <div class="kpy16-headrow">
    <div>
      <div class="kpy16-title">🏈 NFL <span>Passing Yards</span></div>
      <div class="kpy16-sub">Matchup first. See the quarterbacks, defenses, projection drivers, probability confidence, and market state before diving into the full certified Steps 1–10 evidence trail.</div>
    </div>
    <div class="kpy16-status">10 / 10 COMPLETE</div>
  </div>
</section>
"""


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    if not _finite(value):
        return "—"
    return f"{float(value):.{digits}f}{suffix}"


def _pct(value: Any) -> str:
    if not _finite(value):
        return "—"
    return f"{100.0 * float(value):.1f}%"


def _signed(value: Any, digits: int = 1, suffix: str = "") -> str:
    if not _finite(value):
        return "—"
    return f"{float(value):+.{digits}f}{suffix}"


def _confidence_class(value: Any) -> str:
    label = _safe(value, "CHECK").lower()
    return label if label in {"high", "medium", "low"} else ""


def _grade_class(value: Any) -> str:
    label = _safe(value, "CHECK").lower()
    return label if label in {"a", "b", "c", "pass"} else ""


def _logo_url(abbr: Any) -> str:
    token = _safe(abbr).lower()
    return f"https://a.espncdn.com/i/teamlogos/nfl/500/{token}.png" if token else ""


def _identity_side(ctx: dict, opponent: dict, baseline: dict, side_label: str) -> str:
    qb = ctx.get("qb1") or {}
    logo = _logo_url(ctx.get("abbr"))
    logo_html = f'<img class="kpy16-logo" src="{escape(logo)}" alt="{escape(_safe(ctx.get("team"), ctx.get("abbr")))} logo" loading="lazy">' if logo else ""
    defense_name = _safe(opponent.get("team"), opponent.get("abbr") or "Opponent")
    return (
        '<section class="kpy16-side">'
        '<div class="kpy16-sidehead">'
        f'{logo_html}<div><div class="kpy16-team">{escape(_safe(ctx.get("team"), ctx.get("abbr") or "Team"))}</div>'
        f'<div class="kpy16-site">{escape(side_label)}</div></div></div>'
        f'<div class="kpy16-qb">{escape(_safe(qb.get("name"), "Unresolved QB1"))}</div>'
        f'<div class="kpy16-vsdef">Quarterback vs <b>{escape(defense_name)}</b> pass defense • exact ESPN team/QB identity chain</div>'
        '<div class="kpy16-minis">'
        f'<div class="kpy16-mini"><b>{_fmt(baseline.get("expected_attempts"),1)}</b><span>Expected Att</span></div>'
        f'<div class="kpy16-mini"><b>{_fmt(baseline.get("expected_ypa"),2)}</b><span>Expected YPA</span></div>'
        f'<div class="kpy16-mini"><b>{_fmt(baseline.get("projection_yards"),1)}</b><span>Step 7 Base</span></div>'
        '</div></section>'
    )


def _matchup_html(identity_result: dict, baselines: list[dict]) -> str:
    if not identity_result:
        return ""
    away = identity_result.get("away") or {}
    home = identity_result.get("home") or {}
    if not away and not home:
        return ""
    away_base = baselines[0] if len(baselines) > 0 else {}
    home_base = baselines[1] if len(baselines) > 1 else {}
    ready = bool(identity_result.get("ready"))
    state = "IDENTITY VERIFIED" if ready else "IDENTITY CHECK"
    return (
        '<section class="kpy16-match">'
        '<div class="kpy16-matchhead">'
        '<div><div class="kpy16-matchtitle">🏟️ Matchup Spotlight</div>'
        '<div class="kpy16-matchsub">Quarterback vs opposing pass defense • logos are display-only ESPN team assets</div></div>'
        f'<div class="kpy16-tag">{escape(state)}</div></div>'
        '<div class="kpy16-versus">'
        f'{_identity_side(away, home, away_base, "AWAY")}'
        '<div class="kpy16-at">@</div>'
        f'{_identity_side(home, away, home_base, "HOME")}'
        '</div></section>'
    )


def _why_card(baseline: dict, context: dict, dist: dict, market: dict) -> str:
    name = _safe(dist.get("qb_name") or context.get("qb_name") or baseline.get("qb_name"), "Unresolved QB1")
    confidence = _safe(dist.get("confidence") or context.get("confidence"), "CHECK").upper()
    conf_css = _confidence_class(confidence)
    projection_yards = dist.get("location_yards") if _finite(dist.get("location_yards")) else context.get("context_projection_yards")
    if market.get("grade_ready"):
        lean = _safe(market.get("lean"), "PASS")
        grade = _safe(market.get("grade"), "PASS").upper()
        grade_css = _grade_class(grade)
        market_text = f"{lean} • line {_fmt(market.get('line'),1)} • O {_pct(market.get('model_over_probability'))} / U {_pct(market.get('model_under_probability'))}"
        grade_html = f'<span class="kpy16-grade {grade_css}">{escape(grade)}</span>'
    else:
        market_text = "MODEL READY • MARKET PENDING"
        grade_html = '<span class="kpy16-grade">CHECK</span>'
    return (
        '<section class="kpy16-whycard">'
        '<div class="kpy16-whytop">'
        f'<div class="kpy16-whyname">{escape(name)}</div>'
        f'<div class="kpy16-conf {conf_css}">{escape(confidence)}</div></div>'
        '<div class="kpy16-reasons">'
        f'<div class="kpy16-reason"><b>{_fmt(baseline.get("expected_attempts"),1)}</b><span>Volume</span></div>'
        f'<div class="kpy16-reason"><b>{_fmt(baseline.get("expected_ypa"),2)}</b><span>Efficiency</span></div>'
        f'<div class="kpy16-reason"><b>{_signed(context.get("pressure_adjustment_yards"),1)}</b><span>Pressure Adj</span></div>'
        f'<div class="kpy16-reason"><b>{escape(_safe(context.get("personnel_context"),"CHECK"))}</b><span>Personnel</span></div>'
        f'<div class="kpy16-reason"><b>{escape(_safe(context.get("weather_context"),"CHECK"))}</b><span>Weather</span></div>'
        f'<div class="kpy16-reason"><b>{_fmt(dist.get("sigma_yards"),1)}</b><span>Recent SD</span></div>'
        '</div>'
        '<div class="kpy16-final">'
        f'<div><div class="kpy16-proj">Projection: {_fmt(projection_yards,1)} yds</div><div class="kpy16-market">{escape(market_text)}</div></div>'
        f'{grade_html}'
        '</div></section>'
    )


def _why_html(baselines: list[dict], contexts: list[dict], distributions: list[dict], markets: list[dict]) -> str:
    count = max(len(baselines), len(contexts), len(distributions), len(markets))
    if count <= 0:
        return ""
    cards = []
    for idx in range(count):
        baseline = baselines[idx] if idx < len(baselines) else {}
        context = contexts[idx] if idx < len(contexts) else {}
        dist = distributions[idx] if idx < len(distributions) else {}
        market = markets[idx] if idx < len(markets) else {}
        cards.append(_why_card(baseline, context, dist, market))
    return (
        '<section class="kpy16-why">'
        '<div class="kpy16-whyhead">'
        '<div><div class="kpy16-whytitle">🧠 Why This Projection</div>'
        '<div class="kpy16-whysub">Fast read of the exact certified drivers already calculated below — no extra model pass</div></div>'
        '<div class="kpy16-tag">RESULT → REASONS</div></div>'
        f'<div class="kpy16-whygrid">{"".join(cards)}</div>'
        '<div class="kpy16-foot">Only the certified Step 8 pressure-opportunity treatment can numerically move the Step 7 baseline here. Personnel/weather remain visible context with their existing certified 0.0-yard numerical treatment. Sportsbook projection influence remains exactly 0.0%.</div>'
        '</section>'
    )


def render_nfl_passing_yards_hub() -> None:
    st.markdown(_CLEANUP_STEP4_CSS, unsafe_allow_html=True)
    st.markdown(_HEADER, unsafe_allow_html=True)
    matchup_slot = st.empty()
    why_slot = st.empty()
    identity_result: dict = {}
    baselines: list[dict] = []
    contexts: list[dict] = []
    distributions: list[dict] = []
    markets: list[dict] = []
    original_identity = step7_ui.identity.resolve_matchup_identity
    original_baseline = step7_ui.projection.build_baseline_projection
    original_context = step8_ui.context.build_context_projection
    original_distribution = step9_ui.distribution.build_distribution
    original_market_card = step10_ui._market_card

    def capture_identity(*args, **kwargs):
        nonlocal identity_result
        row = original_identity(*args, **kwargs)
        identity_result = dict(row or {})
        return row

    def capture_baseline(*args, **kwargs):
        row = original_baseline(*args, **kwargs)
        baselines.append(dict(row or {}))
        return row

    def capture_context(*args, **kwargs):
        row = original_context(*args, **kwargs)
        contexts.append(dict(row or {}))
        return row

    def capture_distribution(*args, **kwargs):
        row = original_distribution(*args, **kwargs)
        distributions.append(dict(row or {}))
        return row

    def capture_market_card(row: dict):
        markets.append(dict(row or {}))
        return original_market_card(row)

    step7_ui.identity.resolve_matchup_identity = capture_identity
    step7_ui.projection.build_baseline_projection = capture_baseline
    step8_ui.context.build_context_projection = capture_context
    step9_ui.distribution.build_distribution = capture_distribution
    step10_ui._market_card = capture_market_card
    try:
        prior.render_nfl_passing_yards_hub()
    finally:
        step7_ui.identity.resolve_matchup_identity = original_identity
        step7_ui.projection.build_baseline_projection = original_baseline
        step8_ui.context.build_context_projection = original_context
        step9_ui.distribution.build_distribution = original_distribution
        step10_ui._market_card = original_market_card

    matchup = _matchup_html(identity_result, baselines)
    reasons = _why_html(baselines, contexts, distributions, markets)
    if matchup:
        matchup_slot.markdown(matchup, unsafe_allow_html=True)
    if reasons:
        why_slot.markdown(reasons, unsafe_allow_html=True)


__all__ = ["MODEL_VERSION", "_CLEANUP_STEP4_CSS", "_logo_url", "_matchup_html", "_why_html", "render_nfl_passing_yards_hub"]
