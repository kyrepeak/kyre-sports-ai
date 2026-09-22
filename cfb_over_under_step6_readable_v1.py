"""Readable presentation-only adapter for frozen CFB O/U Step 6 red-zone output."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

MODEL_VERSION = "CFB O/U READABLE STEP 6 V1 • RED ZONE"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _signed(value: Any) -> str:
    try:
        number = float(value)
    except Exception:
        return "—"
    return f"{number:+.2f}"


def _metric_line(title: str, metrics: Mapping[str, Any], defense: bool = False) -> str:
    if not metrics.get("ready"):
        return f"<div class='rz6-box'><b>{escape(title)}</b><span>Direct NCAA red-zone row unavailable.</span><strong>UNAVAILABLE</strong></div>"
    allowed = " allowed" if defense else ""
    return (
        "<div class='rz6-box'>"
        f"<b>{escape(title)}</b>"
        f"<span>TD rate{allowed}: <strong>{_pct(metrics.get('touchdown_rate'))}</strong><br>"
        f"Scoring rate{allowed}: <strong>{_pct(metrics.get('scoring_rate'))}</strong><br>"
        f"Points per trip{allowed}: <strong>{_num(metrics.get('points_per_trip'))}</strong><br>"
        f"Verified trips: <strong>{_num(metrics.get('attempts'), 0)}</strong>"
        "</span></div>"
    )


def _side(side: Mapping[str, Any]) -> str:
    offense = side.get("offense") or {}
    defense = side.get("defense") or {}
    return f"""
<div class="rz6-side">
  <div class="rz6-sidehead">
    <div><b>{escape(_clean(side.get('offense_team')) or 'Offense')} offense vs {escape(_clean(side.get('defense_team')) or 'Defense')} defense</b>
    <small>{escape(_clean(side.get('offense_division')))} offense • {escape(_clean(side.get('defense_division')))} defense</small></div>
    <div><strong>{escape(_clean(side.get('label')) or 'BALANCED')}</strong><small>{_signed(side.get('points_adjustment'))} projected pts</small></div>
  </div>
  <div class="rz6-grid">
    {_metric_line('Offensive red-zone finishing', offense, False)}
    {_metric_line('Opponent red-zone defense', defense, True)}
  </div>
  <div class="rz6-mini">Evidence coverage <b>{_pct(side.get('coverage'))}</b> • sample strength <b>{_pct(side.get('sample_factor'))}</b></div>
</div>
"""


def render_step6(engine: Mapping[str, Any]) -> str:
    ready = engine.get("model_ready") is True or engine.get("ready") is True and bool(engine.get("away_offense")) and bool(engine.get("home_offense"))
    if not ready or engine.get("model_ready") is False:
        reason = escape(_clean(engine.get("reason")) or "Verified direct red-zone evidence is incomplete")
        return f"""
<div class="rz6-wrap">
<style>{_CSS}</style>
<div class="rz6-title"><b>🟥 STEP 6 • RED ZONE</b><span>GATED</span></div>
<div class="rz6-gate">{reason}. The frozen model falls back safely instead of inventing red-zone data.</div>
<div class="rz6-foot">Projection mutation: <b>OFF</b> • sportsbook projection weight: <b>0.0%</b></div>
</div>
"""

    away = engine.get("away_offense") or {}
    home = engine.get("home_offense") or {}
    net = float(away.get("points_adjustment") or 0.0) + float(home.get("points_adjustment") or 0.0)
    if net > 0:
        verdict = "RED ZONE FAVORS MORE SCORING"
        explanation = "The existing frozen red-zone adjustments add scoring pressure to this matchup."
    elif net < 0:
        verdict = "RED ZONE FAVORS FEWER POINTS"
        explanation = "The existing frozen red-zone adjustments suppress scoring in this matchup."
    else:
        verdict = "RED ZONE IS NEUTRAL"
        explanation = "The existing frozen red-zone adjustments do not move the matchup either direction."

    return f"""
<div class="rz6-wrap">
<style>{_CSS}</style>
<div class="rz6-title"><b>🟥 STEP 6 • RED ZONE</b><span>DIRECT NCAA EVIDENCE</span></div>
<div class="rz6-why"><b>Why it matters:</b> yards can get a team close, but red-zone finishing decides whether drives become touchdowns, field goals, or empty possessions.</div>
<div class="rz6-sides">{_side(away)}{_side(home)}</div>
<div class="rz6-verdict"><small>RED-ZONE VERDICT</small><strong>{verdict}</strong><span>{explanation}</span><b>Net frozen red-zone adjustment: {_signed(net)} pts</b></div>
<div class="rz6-note">Uses direct NCAA red-zone attempts/outcomes already produced by the frozen engine. Touchdown conversion is the primary signal and points per trip is secondary; FBS/FCS normalization and sample shrinkage remain frozen. No ranking proxy is substituted for missing direct data.</div>
<div class="rz6-foot">Projection mutation: <b>OFF</b> • sportsbook projection weight: <b>0.0%</b></div>
</div>
"""


_CSS = """
.rz6-wrap{margin:10px 0;border:1px solid rgba(255,100,100,.28);border-radius:16px;background:#101820;overflow:hidden;color:#eef6f8}
.rz6-title{display:flex;justify-content:space-between;gap:8px;padding:10px 12px;border-bottom:1px solid rgba(255,100,100,.14)}
.rz6-title b{color:#ffaaaa}.rz6-title span{font-size:.72rem;color:#ffbcbc}.rz6-why,.rz6-note,.rz6-foot,.rz6-gate{padding:9px 12px;color:#a6b2b8;font-size:.82rem;line-height:1.45}
.rz6-sides{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}.rz6-side{border:1px solid rgba(255,100,100,.14);border-radius:12px;background:#09151d;overflow:hidden}
.rz6-sidehead{display:flex;justify-content:space-between;gap:8px;padding:9px}.rz6-sidehead small{display:block;color:#81929b;margin-top:3px}.rz6-sidehead strong{color:#ffb0b0}
.rz6-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:8px}.rz6-box{padding:8px;border:1px solid rgba(255,100,100,.10);border-radius:9px;background:#071119}.rz6-box b{display:block}.rz6-box span{display:block;color:#94a4ac;font-size:.78rem;line-height:1.5;margin-top:4px}.rz6-box strong{color:#f5fbfd}.rz6-mini{padding:0 9px 9px;color:#7f919a;font-size:.75rem}
.rz6-verdict{margin:0 10px 10px;padding:10px;border:1px solid rgba(255,100,100,.18);border-radius:10px;background:#151111}.rz6-verdict small,.rz6-verdict span{display:block;color:#9ca9af}.rz6-verdict strong{display:block;color:#ffb2b2;font-size:1rem;margin:3px 0}.rz6-verdict b{display:block;margin-top:5px}.rz6-foot{border-top:1px solid rgba(255,100,100,.10)}.rz6-gate{color:#ddc982;background:#29230d}
@media(max-width:760px){.rz6-sides,.rz6-grid{grid-template-columns:1fr}}
"""

__all__ = ["MAY_MODIFY_PROJECTION", "MODEL_VERSION", "PROJECTION_WEIGHT", "render_step6"]
