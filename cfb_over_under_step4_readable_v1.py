"""Readable College Football Over/Under Step 4 pace presentation.

Presentation-only adapter for the already-certified frozen pace engine output.
It never recomputes projections, changes pace math, touches sportsbook data, or
changes wager selection. It translates existing Step 4 evidence into a readable
football explanation for the Streamlit page.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

MODEL_VERSION = "CFB O/U READABLE STEP 4 V1 • PACE / EXPECTED POSSESSIONS"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False

_CSS = r"""
<style>
.cfb-s4{border:1px solid rgba(199,210,220,.24);border-radius:14px;background:linear-gradient(145deg,#10161d,#09151c 72%);margin-top:8px;overflow:hidden;box-shadow:inset 3px 0 0 #c7d2dc}
.cfb-s4-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:9px 10px;border-bottom:1px solid rgba(199,210,220,.10)}
.cfb-s4-head b{color:#e7eef4;font-size:.50rem;letter-spacing:.06em}.cfb-s4-badge{border:1px solid rgba(199,210,220,.25);border-radius:999px;padding:4px 7px;color:#cbd8e1;font-size:.31rem;font-weight:950;white-space:nowrap}
.cfb-s4-intro{padding:8px 10px;color:#95a8b3;font-size:.35rem;line-height:1.45;border-bottom:1px solid rgba(199,210,220,.08)}
.cfb-s4-teams{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;padding:8px}
.cfb-s4-team{border:1px solid rgba(199,210,220,.13);border-radius:11px;background:#08141b;padding:8px}.cfb-s4-team strong{display:block;color:#f0f6fa;font-size:.57rem}.cfb-s4-team small{display:block;color:#708793;font-size:.28rem;margin-top:2px}
.cfb-s4-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px;margin-top:7px}.cfb-s4-m{border:1px solid rgba(199,210,220,.09);border-radius:8px;background:#071219;padding:6px}.cfb-s4-m b{display:block;color:#d9e8f1;font-size:.48rem}.cfb-s4-m span{display:block;color:#637986;font-size:.24rem;text-transform:uppercase;margin-top:2px}
.cfb-s4-core{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:0 8px 8px}.cfb-s4-core div{border:1px solid rgba(116,220,170,.12);border-radius:9px;background:#071711;padding:7px}.cfb-s4-core b{display:block;color:#dcf9ea;font-size:.54rem}.cfb-s4-core span{display:block;color:#69877a;font-size:.25rem;text-transform:uppercase;margin-top:2px}
.cfb-s4-verdict{margin:0 8px 8px;border-radius:10px;padding:8px 9px;border:1px solid rgba(255,255,255,.09)}.cfb-s4-verdict small{display:block;font-size:.25rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.cfb-s4-verdict strong{display:block;font-size:.57rem;margin-top:3px}.cfb-s4-verdict p{margin:4px 0 0;color:#9aaeb8;font-size:.31rem;line-height:1.42}
.cfb-s4-verdict.over{background:rgba(65,205,133,.07);border-color:rgba(65,205,133,.23)}.cfb-s4-verdict.over small,.cfb-s4-verdict.over strong{color:#9be8bd}.cfb-s4-verdict.under{background:rgba(98,186,255,.07);border-color:rgba(98,186,255,.23)}.cfb-s4-verdict.under small,.cfb-s4-verdict.under strong{color:#9ed6ff}.cfb-s4-verdict.neutral{background:rgba(199,210,220,.06)}.cfb-s4-verdict.neutral small,.cfb-s4-verdict.neutral strong{color:#d0dbe3}
.cfb-s4-foot{padding:8px 10px;border-top:1px solid rgba(199,210,220,.08);color:#718893;font-size:.29rem;line-height:1.45}.cfb-s4-gate{padding:10px;color:#e4c77e;font-size:.36rem;line-height:1.45;background:#2a230d}
@media(max-width:760px){.cfb-s4-teams{grid-template-columns:1fr}.cfb-s4-core{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.0f}%"
    except Exception:
        return "—"


def _seconds(value: Any) -> str:
    try:
        return f"{float(value):.1f}s"
    except Exception:
        return "—"


def _team(team: Mapping[str, Any]) -> str:
    name = escape(_clean(team.get("team")) or "Team")
    division = escape(_clean(team.get("division")) or "Division unavailable")
    return f"""
<div class="cfb-s4-team">
  <strong>{name}</strong><small>{division} pace evidence</small>
  <div class="cfb-s4-metrics">
    <div class="cfb-s4-m"><b>{_num(team.get('plays_per_game'))}</b><span>Plays / game</span></div>
    <div class="cfb-s4-m"><b>{_seconds(team.get('seconds_per_offensive_play'))}</b><span>Seconds / play</span></div>
    <div class="cfb-s4-m"><b>{_num(team.get('pace_index'), 2)}</b><span>Pace index</span></div>
  </div>
</div>"""


def _verdict(adjustment: Any) -> tuple[str, str, str]:
    try:
        value = float(adjustment)
    except Exception:
        return "neutral", "PACE EFFECT UNCLEAR", "Verified pace adjustment is unavailable."
    if value > 0:
        return (
            "over",
            "PACE FAVORS MORE SCORING OPPORTUNITY",
            "The certified pace engine adds points to the frozen baseline because this matchup projects extra play volume. That supports the Over side from pace alone.",
        )
    if value < 0:
        return (
            "under",
            "PACE FAVORS FEWER SCORING OPPORTUNITIES",
            "The certified pace engine removes points from the frozen baseline because this matchup projects reduced play volume. That supports the Under side from pace alone.",
        )
    return (
        "neutral",
        "PACE IS NEUTRAL",
        "The certified pace engine is not moving the frozen baseline total in either direction.",
    )


def render_step4(engine: Mapping[str, Any]) -> str:
    """Render frozen Step 4 engine output without changing any model value."""
    if not isinstance(engine, Mapping):
        engine = {}

    ready = engine.get("model_ready") is True or engine.get("ready") is True
    if not ready:
        reason = escape(
            _clean(engine.get("reason"))
            or "Verified pace evidence is below the engine's existing readiness requirement."
        )
        return _CSS + f"""
<div class="cfb-s4">
  <div class="cfb-s4-head"><b>STEP 4 • PACE / EXPECTED POSSESSIONS</b><span class="cfb-s4-badge">GATED</span></div>
  <div class="cfb-s4-gate">⚠️ {reason} The frozen model falls back safely rather than inventing pace data.</div>
</div>"""

    adjustment = engine.get("total_points_adjustment")
    verdict_class, verdict_title, verdict_text = _verdict(adjustment)
    label = escape(_clean(engine.get("pace_label")) or "PACE READY")
    direct_possessions = (
        _num(engine.get("expected_combined_possessions"))
        if engine.get("direct_possessions_available") is True
        else "—"
    )
    try:
        adj = float(adjustment)
        adj_text = f"{adj:+.2f}"
    except Exception:
        adj_text = "—"

    return _CSS + f"""
<div class="cfb-s4">
  <div class="cfb-s4-head"><b>STEP 4 • PACE / EXPECTED POSSESSIONS</b><span class="cfb-s4-badge">{label}</span></div>
  <div class="cfb-s4-intro">⏱️ <b>Why this matters:</b> faster games usually create more offensive plays and scoring chances; slower games create fewer. These are the existing frozen Step 4 pace outputs — no sportsbook line enters this math.</div>
  <div class="cfb-s4-teams">{_team(engine.get('away') or {})}{_team(engine.get('home') or {})}</div>
  <div class="cfb-s4-core">
    <div><b>{_num(engine.get('expected_combined_plays'))}</b><span>Expected total plays</span></div>
    <div><b>{_num(engine.get('division_baseline_combined_plays'))}</b><span>Normal baseline plays</span></div>
    <div><b>{direct_possessions}</b><span>Direct possessions</span></div>
    <div><b>{adj_text}</b><span>Points from pace</span></div>
  </div>
  <div class="cfb-s4-verdict {verdict_class}"><small>PACE VERDICT</small><strong>{escape(verdict_title)}</strong><p>{escape(verdict_text)}</p></div>
  <div class="cfb-s4-foot">Historical combined plays {_num(engine.get('historical_combined_plays_per_game'))} • clock-implied combined plays {_num(engine.get('clock_implied_combined_plays'))} • sample strength {_pct(engine.get('sample_factor'))} • evidence coverage {_pct(engine.get('coverage'))}. Direct drive/possession counts remain unavailable when the certified source does not provide them. Projection mutation: <b>OFF</b> • sportsbook projection weight: <b>0.0%</b>.</div>
</div>"""


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PROJECTION_WEIGHT",
    "render_step4",
]
