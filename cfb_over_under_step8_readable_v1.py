"""Readable presentation-only adapter for frozen CFB O/U Step 8 turnover-volatility output."""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

MODEL_VERSION = "CFB O/U READABLE STEP 8 V1 • TURNOVER VOLATILITY"
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
        return f"{float(value):+.2f}"
    except Exception:
        return "—"


def _metric_line(title: str, metrics: Mapping[str, Any], defense: bool = False) -> str:
    if not metrics.get("ready"):
        return (
            f"<div class='to8-box'><b>{escape(title)}</b>"
            "<span>Direct NCAA turnover row unavailable.</span>"
            "<strong>UNAVAILABLE</strong></div>"
        )
    primary = metrics.get("takeaways_per_game") if defense else metrics.get("giveaways_per_game")
    primary_label = "Takeaways/game" if defense else "Giveaways/game"
    return (
        "<div class='to8-box'>"
        f"<b>{escape(title)}</b>"
        f"<span>{primary_label}: <strong>{_num(primary)}</strong><br>"
        f"Turnovers gained: <strong>{_num(metrics.get('turnovers_gained'), 0)}</strong><br>"
        f"Turnovers lost: <strong>{_num(metrics.get('turnovers_lost'), 0)}</strong><br>"
        f"Turnover margin: <strong>{_signed(metrics.get('turnover_margin'))}</strong><br>"
        f"Verified games: <strong>{_num(metrics.get('games'), 0)}</strong>"
        "</span></div>"
    )


def _side(side: Mapping[str, Any]) -> str:
    offense = side.get("offense") or {}
    defense = side.get("defense") or {}
    return f"""
<div class="to8-side">
  <div class="to8-sidehead">
    <div><b>{escape(_clean(side.get('offense_team')) or 'Offense')} ball security vs {escape(_clean(side.get('defense_team')) or 'Defense')} takeaways</b>
    <small>{escape(_clean(side.get('offense_division')))} offense • {escape(_clean(side.get('defense_division')))} defense</small></div>
    <div><strong>{escape(_clean(side.get('label')) or 'NEUTRAL TURNOVER VOLATILITY')}</strong><small>{_signed(side.get('shrunk_signal'))} volatility signal</small></div>
  </div>
  <div class="to8-grid">
    {_metric_line('Offense giveaway profile', offense, False)}
    {_metric_line('Opponent takeaway profile', defense, True)}
  </div>
  <div class="to8-context">
    <div><small>Expected giveaways</small><b>{_num(side.get('expected_giveaways_per_game'))}</b></div>
    <div><small>Division baseline</small><b>{_num(side.get('baseline_expected_giveaways_per_game'))}</b></div>
    <div><small>Evidence coverage</small><b>{_pct(side.get('coverage'))}</b></div>
    <div><small>Sample strength</small><b>{_pct(side.get('sample_factor'))}</b></div>
  </div>
</div>
"""


def render_step8(engine: Mapping[str, Any]) -> str:
    ready = (
        engine.get("model_ready") is True
        or engine.get("ready") is True
        and bool(engine.get("away_offense"))
        and bool(engine.get("home_offense"))
    )
    if not ready or engine.get("model_ready") is False:
        reason = escape(_clean(engine.get("reason")) or "Verified direct turnover evidence is incomplete")
        return f"""
<div class="to8-wrap">
<style>{_CSS}</style>
<div class="to8-title"><b>🟧 STEP 8 • TURNOVER VOLATILITY</b><span>GATED</span></div>
<div class="to8-gate">{reason}. The frozen model keeps the prior uncertainty profile instead of inventing turnover or field-position data.</div>
<div class="to8-foot">Projected-total mutation: <b>OFF</b> • sportsbook projection weight: <b>0.0%</b></div>
</div>
"""

    away = engine.get("away_offense") or {}
    home = engine.get("home_offense") or {}
    sigma = float(engine.get("sigma_adjustment") or 0.0)
    if sigma > 0:
        verdict = "TURNOVERS RAISE GAME VOLATILITY"
        explanation = "The frozen turnover engine widens the range of plausible game totals."
    elif sigma < 0:
        verdict = "TURNOVERS LOWER GAME VOLATILITY"
        explanation = "The frozen turnover engine slightly tightens the range of plausible game totals."
    else:
        verdict = "TURNOVER VOLATILITY IS NEUTRAL"
        explanation = "The frozen turnover engine does not change structural uncertainty for this matchup."

    return f"""
<div class="to8-wrap">
<style>{_CSS}</style>
<div class="to8-title"><b>🟧 STEP 8 • TURNOVER VOLATILITY</b><span>DIRECT NCAA EVIDENCE</span></div>
<div class="to8-why"><b>Why it matters:</b> turnovers can kill a drive or hand the opponent a short field. That makes the game less predictable, but without verified field-position and return data we should not pretend turnovers automatically mean Over or Under.</div>
<div class="to8-sides">{_side(away)}{_side(home)}</div>
<div class="to8-verdict"><small>TURNOVER VERDICT</small><strong>{verdict}</strong><span>{explanation}</span><b>Frozen structural sigma adjustment: {_signed(sigma)} pts</b><em>Projected total remains unchanged by Step 8.</em></div>
<div class="to8-note">Uses direct NCAA turnover-margin counts already produced by the frozen engine. Offense giveaways and opponent takeaways remain weighted 50/50, normalized inside the correct FBS/FCS pool, and shrunk by verified games. Cross-division rankings are never compared, and field-position point value is never fabricated.</div>
<div class="to8-foot">Projected-total mutation: <b>OFF</b> • sportsbook projection weight: <b>0.0%</b> • uncertainty-only adjustment</div>
</div>
"""


_CSS = """
.to8-wrap{margin:10px 0;border:1px solid rgba(255,187,72,.30);border-radius:16px;background:#101820;overflow:hidden;color:#eef6f8}
.to8-title{display:flex;justify-content:space-between;gap:8px;padding:10px 12px;border-bottom:1px solid rgba(255,187,72,.15)}
.to8-title b{color:#ffd28a}.to8-title span{font-size:.72rem;color:#ffe0a8}.to8-why,.to8-note,.to8-foot,.to8-gate{padding:9px 12px;color:#a6b2b8;font-size:.82rem;line-height:1.45}
.to8-sides{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;padding:10px}.to8-side{border:1px solid rgba(255,187,72,.15);border-radius:12px;background:#09151d;overflow:hidden}
.to8-sidehead{display:flex;justify-content:space-between;gap:8px;padding:9px}.to8-sidehead small{display:block;color:#81929b;margin-top:3px}.to8-sidehead strong{color:#ffd28a}
.to8-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:8px}.to8-box{padding:8px;border:1px solid rgba(255,187,72,.10);border-radius:9px;background:#071119}.to8-box b{display:block}.to8-box span{display:block;color:#94a4ac;font-size:.78rem;line-height:1.5;margin-top:4px}.to8-box strong{color:#f5fbfd}
.to8-context{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;padding:0 8px 8px}.to8-context div{padding:7px;border:1px solid rgba(255,187,72,.10);border-radius:8px;background:#08131a}.to8-context small{display:block;color:#7f919a}.to8-context b{display:block;margin-top:3px;color:#eef6f8}
.to8-verdict{margin:0 10px 10px;padding:10px;border:1px solid rgba(255,187,72,.18);border-radius:10px;background:#1e180d}.to8-verdict small,.to8-verdict span,.to8-verdict em{display:block;color:#9ca9af}.to8-verdict strong{display:block;color:#ffd28a;font-size:1rem;margin:3px 0}.to8-verdict b{display:block;margin-top:5px}.to8-verdict em{margin-top:5px;font-style:normal;color:#f2dcae}.to8-foot{border-top:1px solid rgba(255,187,72,.10)}.to8-gate{color:#ddc982;background:#29230d}
@media(max-width:760px){.to8-sides,.to8-grid,.to8-context{grid-template-columns:1fr}}
"""

__all__ = ["MAY_MODIFY_PROJECTION", "MODEL_VERSION", "PROJECTION_WEIGHT", "render_step8"]
