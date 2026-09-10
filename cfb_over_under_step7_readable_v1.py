"""Readable presentation-only adapter for frozen CFB O/U Step 7 third-down output."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

MODEL_VERSION = "CFB O/U READABLE STEP 7 V1 • THIRD DOWN"
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
        return (
            f"<div class='td7-box'><b>{escape(title)}</b>"
            "<span>Direct NCAA third-down row unavailable.</span>"
            "<strong>UNAVAILABLE</strong></div>"
        )
    suffix = " allowed" if defense else ""
    return (
        "<div class='td7-box'>"
        f"<b>{escape(title)}</b>"
        f"<span>Conversion rate{suffix}: <strong>{_pct(metrics.get('conversion_rate'))}</strong><br>"
        f"Conversions{suffix}: <strong>{_num(metrics.get('conversions'), 0)}</strong><br>"
        f"Attempts{suffix}: <strong>{_num(metrics.get('attempts'), 0)}</strong><br>"
        f"Third downs/game{suffix}: <strong>{_num(metrics.get('attempts_per_game'))}</strong>"
        "</span></div>"
    )


def _side(side: Mapping[str, Any]) -> str:
    offense = side.get("offense") or {}
    defense = side.get("defense") or {}
    return f"""
<div class="td7-side">
  <div class="td7-sidehead">
    <div><b>{escape(_clean(side.get('offense_team')) or 'Offense')} offense vs {escape(_clean(side.get('defense_team')) or 'Defense')} defense</b>
    <small>{escape(_clean(side.get('offense_division')))} offense • {escape(_clean(side.get('defense_division')))} defense</small></div>
    <div><strong>{escape(_clean(side.get('label')) or 'BALANCED')}</strong><small>{_signed(side.get('points_adjustment'))} projected pts</small></div>
  </div>
  <div class="td7-grid">
    {_metric_line('Offensive third-down conversion', offense, False)}
    {_metric_line('Opponent third-down defense', defense, True)}
  </div>
  <div class="td7-context">
    <div><small>Blended matchup conversion</small><b>{_pct(side.get('matchup_conversion_rate'))}</b></div>
    <div><small>Expected 3rd-down tries</small><b>{_num(side.get('expected_third_down_attempts_per_game'))}</b></div>
    <div><small>Expected conversions</small><b>{_num(side.get('expected_third_down_conversions_per_game'))}</b></div>
  </div>
  <div class="td7-mini">Evidence coverage <b>{_pct(side.get('coverage'))}</b> • sample strength <b>{_pct(side.get('sample_factor'))}</b></div>
</div>
"""


def render_step7(engine: Mapping[str, Any]) -> str:
    ready = (
        engine.get("model_ready") is True
        or engine.get("ready") is True
        and bool(engine.get("away_offense"))
        and bool(engine.get("home_offense"))
    )
    if not ready or engine.get("model_ready") is False:
        reason = escape(_clean(engine.get("reason")) or "Verified direct third-down evidence is incomplete")
        return f"""
<div class="td7-wrap">
<style>{_CSS}</style>
<div class="td7-title"><b>🟪 STEP 7 • THIRD DOWN</b><span>GATED</span></div>
<div class="td7-gate">{reason}. The frozen model falls back safely instead of inventing third-down data.</div>
<div class="td7-foot">Projection mutation: <b>OFF</b> • sportsbook projection weight: <b>0.0%</b></div>
</div>
"""

    away = engine.get("away_offense") or {}
    home = engine.get("home_offense") or {}
    net = float(away.get("points_adjustment") or 0.0) + float(home.get("points_adjustment") or 0.0)
    if net > 0:
        verdict = "THIRD DOWN FAVORS LONGER DRIVES / MORE SCORING CHANCES"
        explanation = "The existing frozen third-down adjustments increase drive-sustain pressure in this matchup."
    elif net < 0:
        verdict = "THIRD DOWN FAVORS MORE DRIVE STOPS / FEWER SCORING CHANCES"
        explanation = "The existing frozen third-down adjustments increase drive-suppression pressure in this matchup."
    else:
        verdict = "THIRD DOWN IS NEUTRAL"
        explanation = "The existing frozen third-down adjustments do not move the matchup either direction."

    return f"""
<div class="td7-wrap">
<style>{_CSS}</style>
<div class="td7-title"><b>🟪 STEP 7 • THIRD DOWN</b><span>DIRECT NCAA EVIDENCE</span></div>
<div class="td7-why"><b>Why it matters:</b> third down decides whether a drive keeps moving or the offense gives the ball back. More conversions create extra plays, field position, and scoring opportunities.</div>
<div class="td7-sides">{_side(away)}{_side(home)}</div>
<div class="td7-verdict"><small>THIRD-DOWN VERDICT</small><strong>{verdict}</strong><span>{explanation}</span><b>Net frozen third-down adjustment: {_signed(net)} pts</b></div>
<div class="td7-note">Uses direct NCAA third-down attempts and conversions already produced by the frozen engine. Offense and opponent-allowed conversion quality remain weighted 50/50, normalized inside the correct FBS/FCS pool, and shrunk by verified attempt sample. Cross-division ranking numbers are never compared.</div>
<div class="td7-foot">Projection mutation: <b>OFF</b> • sportsbook projection weight: <b>0.0%</b></div>
</div>
"""


_CSS = """
.td7-wrap{margin:10px 0;border:1px solid rgba(155,126,255,.30);border-radius:16px;background:#101820;overflow:hidden;color:#eef6f8}
.td7-title{display:flex;justify-content:space-between;gap:8px;padding:10px 12px;border-bottom:1px solid rgba(155,126,255,.15)}
.td7-title b{color:#c9bcff}.td7-title span{font-size:.72rem;color:#d6ceff}.td7-why,.td7-note,.td7-foot,.td7-gate{padding:9px 12px;color:#a6b2b8;font-size:.82rem;line-height:1.45}
.td7-sides{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}.td7-side{border:1px solid rgba(155,126,255,.15);border-radius:12px;background:#09151d;overflow:hidden}
.td7-sidehead{display:flex;justify-content:space-between;gap:8px;padding:9px}.td7-sidehead small{display:block;color:#81929b;margin-top:3px}.td7-sidehead strong{color:#c9bcff}
.td7-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:8px}.td7-box{padding:8px;border:1px solid rgba(155,126,255,.10);border-radius:9px;background:#071119}.td7-box b{display:block}.td7-box span{display:block;color:#94a4ac;font-size:.78rem;line-height:1.5;margin-top:4px}.td7-box strong{color:#f5fbfd}
.td7-context{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;padding:0 8px 8px}.td7-context div{padding:7px;border:1px solid rgba(155,126,255,.10);border-radius:8px;background:#08131a}.td7-context small{display:block;color:#7f919a}.td7-context b{display:block;margin-top:3px;color:#eef6f8}.td7-mini{padding:0 9px 9px;color:#7f919a;font-size:.75rem}
.td7-verdict{margin:0 10px 10px;padding:10px;border:1px solid rgba(155,126,255,.18);border-radius:10px;background:#121020}.td7-verdict small,.td7-verdict span{display:block;color:#9ca9af}.td7-verdict strong{display:block;color:#cfc4ff;font-size:1rem;margin:3px 0}.td7-verdict b{display:block;margin-top:5px}.td7-foot{border-top:1px solid rgba(155,126,255,.10)}.td7-gate{color:#ddc982;background:#29230d}
@media(max-width:760px){.td7-sides,.td7-grid,.td7-context{grid-template-columns:1fr}}
"""

__all__ = ["MAY_MODIFY_PROJECTION", "MODEL_VERSION", "PROJECTION_WEIGHT", "render_step7"]
