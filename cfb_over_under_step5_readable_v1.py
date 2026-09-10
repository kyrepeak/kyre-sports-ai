"""Readable College Football Over/Under Step 5 explosive-play presentation.

Presentation-only adapter for the already-certified explosive engine output.
It never recomputes projections, changes explosive math, touches sportsbook data,
or changes wager selection.
"""
from __future__ import annotations

from html import escape
from typing import Any, Mapping

MODEL_VERSION = "CFB O/U READABLE STEP 5 V1 • EXPLOSIVE PLAY PROFILE"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False

_CSS = r"""
<style>
.cfb-s5{border:1px solid rgba(255,154,82,.27);border-radius:14px;background:linear-gradient(145deg,#17110b,#0b151a 72%);margin-top:8px;overflow:hidden;box-shadow:inset 3px 0 0 #ff9a52}
.cfb-s5-head{display:flex;justify-content:space-between;gap:8px;align-items:center;padding:9px 10px;border-bottom:1px solid rgba(255,154,82,.12)}
.cfb-s5-head b{color:#ffc18d;font-size:.50rem;letter-spacing:.06em}.cfb-s5-badge{border:1px solid rgba(255,154,82,.25);border-radius:999px;padding:4px 7px;color:#ffc18d;font-size:.31rem;font-weight:950;white-space:nowrap}
.cfb-s5-intro{padding:8px 10px;color:#9aa8ae;font-size:.35rem;line-height:1.45;border-bottom:1px solid rgba(255,154,82,.08)}
.cfb-s5-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px;padding:8px}.cfb-s5-side{border:1px solid rgba(255,154,82,.14);border-radius:11px;background:#08141b;padding:8px}
.cfb-s5-side strong{display:block;color:#f6fbfd;font-size:.56rem}.cfb-s5-side small{display:block;color:#748690;font-size:.28rem;margin-top:2px}.cfb-s5-dims{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;margin-top:7px}.cfb-s5-dim{border:1px solid rgba(255,154,82,.09);border-radius:8px;background:#071219;padding:6px}.cfb-s5-dim b{display:block;color:#ffd4b0;font-size:.42rem}.cfb-s5-dim span{display:block;color:#6f8189;font-size:.25rem;line-height:1.4;margin-top:3px}
.cfb-s5-core{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;padding:0 8px 8px}.cfb-s5-core div{border:1px solid rgba(255,154,82,.11);border-radius:9px;background:#0b151a;padding:7px}.cfb-s5-core b{display:block;color:#fff3e8;font-size:.53rem}.cfb-s5-core span{display:block;color:#7b8589;font-size:.25rem;text-transform:uppercase;margin-top:2px}
.cfb-s5-verdict{margin:0 8px 8px;border-radius:10px;padding:8px 9px;border:1px solid rgba(255,154,82,.18);background:rgba(255,154,82,.06)}.cfb-s5-verdict small{display:block;color:#f5a867;font-size:.25rem;font-weight:950;letter-spacing:.05em;text-transform:uppercase}.cfb-s5-verdict strong{display:block;color:#ffe1c7;font-size:.56rem;margin-top:3px}.cfb-s5-verdict p{margin:4px 0 0;color:#9ca9af;font-size:.31rem;line-height:1.42}
.cfb-s5-foot{padding:8px 10px;border-top:1px solid rgba(255,154,82,.08);color:#76858c;font-size:.29rem;line-height:1.45}.cfb-s5-gate{padding:10px;color:#e4c77e;font-size:.36rem;line-height:1.45;background:#2a230d}
@media(max-width:760px){.cfb-s5-grid{grid-template-columns:1fr}.cfb-s5-core{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
"""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return "—"


def _pct(value: Any) -> str:
    try:
        return f"{100.0 * float(value):.0f}%"
    except Exception:
        return "—"


def _dimension(dim: Mapping[str, Any], kind: str) -> str:
    if kind == "pass":
        text = (
            f"Offense Y/A {_num(dim.get('offense_yards_per_attempt'))} vs allowed {_num(dim.get('defense_yards_per_attempt_allowed'))}<br>"
            f"Offense Y/C {_num(dim.get('offense_yards_per_completion'))} vs allowed {_num(dim.get('defense_yards_per_completion_allowed'))}"
        )
        title = "Pass chunk efficiency"
    else:
        text = f"Offense Y/Rush {_num(dim.get('offense_yards_per_rush'))} vs allowed {_num(dim.get('defense_yards_per_rush_allowed'))}"
        title = "Rush chunk efficiency"
    signal = _num(dim.get("signal"), 3) if dim.get("ready") else "Unavailable"
    return f'<div class="cfb-s5-dim"><b>{title}</b><span>{text}<br>Signal: {signal}</span></div>'


def _side(side: Mapping[str, Any]) -> str:
    offense = escape(_clean(side.get("offense_team")) or "Offense")
    defense = escape(_clean(side.get("defense_team")) or "Defense")
    label = escape(_clean(side.get("label")) or "BALANCED")
    adjustment = float(side.get("points_adjustment") or 0.0)
    sign = "+" if adjustment > 0 else ""
    return f"""
<div class="cfb-s5-side">
  <strong>{offense} offense vs {defense} defense</strong>
  <small>{label} • projected-points adjustment {sign}{adjustment:.2f}</small>
  <div class="cfb-s5-dims">
    {_dimension(side.get('pass') or {}, 'pass')}
    {_dimension(side.get('rush') or {}, 'rush')}
  </div>
</div>
"""


def _verdict(total_adjustment: float) -> tuple[str, str]:
    if total_adjustment > 0:
        return "EXPLOSIVE PROFILE FAVORS MORE SCORING POTENTIAL", "The frozen explosive engine adds points because the matchup shows stronger chunk-play efficiency."
    if total_adjustment < 0:
        return "EXPLOSIVE PROFILE FAVORS FEWER SCORING OPPORTUNITIES", "The frozen explosive engine removes points because the matchup suppresses chunk-play efficiency."
    return "EXPLOSIVE PROFILE IS NEUTRAL", "The frozen explosive engine makes no net scoring adjustment for this matchup."


def render_step5(engine: Mapping[str, Any]) -> str:
    if not isinstance(engine, Mapping) or not engine.get("model_ready"):
        reason = escape(_clean(engine.get("reason")) if isinstance(engine, Mapping) else "") or "Verified explosive evidence is unavailable"
        return _CSS + f"""
<div class="cfb-s5"><div class="cfb-s5-head"><b>💥 STEP 5 • EXPLOSIVE PLAY PROFILE</b><span class="cfb-s5-badge">GATED</span></div>
<div class="cfb-s5-gate">{reason}. Step 5 falls back safely to the frozen prior projection.</div></div>
"""

    away = engine.get("away_offense") or {}
    home = engine.get("home_offense") or {}
    away_adj = float(away.get("points_adjustment") or 0.0)
    home_adj = float(home.get("points_adjustment") or 0.0)
    total_adj = away_adj + home_adj
    title, explanation = _verdict(total_adj)
    return _CSS + f"""
<div class="cfb-s5">
  <div class="cfb-s5-head"><b>💥 STEP 5 • EXPLOSIVE PLAY PROFILE</b><span class="cfb-s5-badge">READABLE • FROZEN ENGINE</span></div>
  <div class="cfb-s5-intro">Pass yards/attempt, pass yards/completion and rush yards/carry are matched against opponent-allowed rates. FBS/FCS evidence stays division-normalized; true 20+ pass and 10+ rush rates are never fabricated.</div>
  <div class="cfb-s5-grid">{_side(away)}{_side(home)}</div>
  <div class="cfb-s5-core">
    <div><b>{_pct(away.get('coverage'))}</b><span>Away coverage</span></div>
    <div><b>{_pct(home.get('coverage'))}</b><span>Home coverage</span></div>
    <div><b>{_pct(away.get('sample_factor'))}</b><span>Away sample</span></div>
    <div><b>{_pct(home.get('sample_factor'))}</b><span>Home sample</span></div>
  </div>
  <div class="cfb-s5-verdict"><small>Explosive verdict</small><strong>{title}</strong><p>{explanation} Net frozen explosive adjustment: {total_adj:+.2f} total points.</p></div>
  <div class="cfb-s5-foot">Presentation only • sportsbook projection weight: <b>0.0%</b> • no new thresholds • no fuzzy matching • no synthetic IDs.</div>
</div>
"""


__all__ = ["MODEL_VERSION", "PROJECTION_WEIGHT", "MAY_MODIFY_PROJECTION", "render_step5"]
