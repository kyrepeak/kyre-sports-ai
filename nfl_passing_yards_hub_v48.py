"""NFL Passing Yards V48 — Steps 7-9 premium evidence board.

Presentation-only wrapper over frozen V47. Step 3 of the Passing Yards visual
upgrade. It reorganizes the already-captured Step 7 projection, Step 8 context,
and Step 9 distribution/probability payloads into a dedicated evidence board.

No analytical payload is recomputed or altered.
"""
from __future__ import annotations

import nfl_passing_yards_hub_v47 as prior
from kyre_universal_components_v1 import build_badge, build_components_css
from kyre_universal_responsive_v1 import build_responsive_css
from kyre_universal_theme_v1 import build_universal_theme_css

MODEL_VERSION = "NFL PASSING YARDS V48 • STEPS 7-9 EVIDENCE BOARD"
FROZEN_PRIOR = "nfl_passing_yards_hub_v47"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MAY_MODIFY_PROJECTION = False
PRESENTATION_ONLY = True

_EVIDENCE_CSS = r"""
<style data-passing-yards-evidence-polish="v48">
.ks-py48,.ks-py48 *{box-sizing:border-box}
.ks-py48{margin:.45rem 0 1.2rem;color:var(--kyre-text-primary)}
.ks-py48-head{
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  margin-bottom:.75rem;padding:.88rem 1rem;
  border:1px solid rgba(88,201,255,.22);border-radius:16px;
  background:linear-gradient(145deg,#091522,#07111a)
}
.ks-py48-head h2{margin:.18rem 0 0;font-size:1.45rem;line-height:1.1;font-weight:950}
.ks-py48-head p{margin:.32rem 0 0;color:var(--kyre-text-muted);font-size:.7rem;line-height:1.45}
.ks-py48-kicker{color:var(--kyre-glacier);font-size:.6rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase}
.ks-py48-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.82rem}
.ks-py48-player{
  min-width:0;overflow:hidden;border:1px solid rgba(88,201,255,.2);
  border-radius:18px;background:linear-gradient(155deg,#0b1b2a,#07111a);
  box-shadow:0 15px 38px rgba(0,0,0,.2)
}
.ks-py48-accent{height:3px;background:linear-gradient(90deg,var(--kyre-glacier),transparent)}
.ks-py48-playerhead{
  display:flex;align-items:center;justify-content:space-between;gap:10px;
  padding:.72rem .82rem;border-bottom:1px solid rgba(88,201,255,.12)
}
.ks-py48-playerhead b{
  color:var(--kyre-glacier-soft);font-size:.63rem;font-weight:950;
  letter-spacing:.08em;text-transform:uppercase
}
.ks-py48-body{padding:.78rem}
.ks-py48-identity{margin-bottom:.65rem}
.ks-py48-market{
  margin-bottom:.65rem;padding:.66rem;border:1px solid rgba(88,201,255,.15);
  border-radius:13px;background:rgba(5,16,25,.82)
}
.ks-py48-market strong{
  display:block;margin-bottom:.35rem;color:var(--kyre-glacier-soft);
  font-size:.57rem;font-weight:950;letter-spacing:.07em;text-transform:uppercase
}
.ks-py48-board-title{
  display:flex;align-items:center;justify-content:space-between;gap:8px;
  margin:.3rem 0 .48rem
}
.ks-py48-board-title b{
  color:var(--kyre-text-primary);font-size:.68rem;font-weight:950
}
.ks-py48-board-title span{
  color:var(--kyre-text-muted);font-size:.52rem;font-weight:750
}
.ks-py48-evidence{
  display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.52rem
}
.ks-py48-step{
  min-width:0;padding:.62rem;border:1px solid rgba(88,201,255,.14);
  border-radius:12px;background:rgba(255,255,255,.016)
}
.ks-py48-step[data-step="7"]{
  border-color:rgba(88,201,255,.28);
  background:linear-gradient(150deg,rgba(27,98,143,.14),rgba(5,16,25,.88))
}
.ks-py48-stepnum{
  display:inline-flex;align-items:center;justify-content:center;
  width:26px;height:26px;border-radius:9px;margin-bottom:.42rem;
  background:rgba(88,201,255,.12);color:var(--kyre-glacier);
  font-size:.58rem;font-weight:950
}
.ks-py48-step strong{
  display:block;color:var(--kyre-glacier-soft);font-size:.58rem;
  font-weight:950;letter-spacing:.045em;text-transform:uppercase;margin-bottom:.42rem
}
.ks-py48-support{
  display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.5rem;margin-top:.55rem
}
.ks-py48-support details{
  border:1px solid rgba(88,201,255,.11);border-radius:11px;padding:.55rem;
  background:rgba(255,255,255,.012)
}
.ks-py48-support summary{
  cursor:pointer;color:var(--kyre-glacier);font-size:.6rem;font-weight:900
}
.ks-py48-supportbody{margin-top:.5rem}
@media(max-width:980px){
  .ks-py48-grid{grid-template-columns:1fr}
}
@media(max-width:680px){
  .ks-py48-evidence{grid-template-columns:1fr}
  .ks-py48-support{grid-template-columns:1fr}
  .ks-py48-head{padding:.72rem}
}
</style>
"""

def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""

def _support(title: str, content: str) -> str:
    return (
        '<details><summary>' + title + '</summary>'
        '<div class="ks-py48-supportbody">' + (content or '<div>Unavailable</div>') + '</div>'
        '</details>'
    )

def _evidence_step(step: int, label: str, content: str) -> str:
    return (
        f'<section class="ks-py48-step" data-step="{step}">'
        f'<div class="ks-py48-stepnum">{step}</div>'
        f'<strong>{label}</strong>'
        f'{content or "<div>Unavailable</div>"}'
        '</section>'
    )

def _player(captured: dict[str, list[str]], index: int) -> str:
    identity = _piece(captured, "identity", index)
    projection = _piece(captured, "projection", index)
    context = _piece(captured, "context", index)
    distribution = _piece(captured, "distribution", index)
    market = _piece(captured, "market", index)

    profile = _piece(captured, "profile", index)
    defense = _piece(captured, "defense", index)
    pressure = _piece(captured, "pressure", index)
    personnel = _piece(captured, "personnel", index)
    environment = _piece(captured, "environment", index)

    return "".join([
        f'<article class="ks-py48-player" data-passing-player="{index}">',
        '<div class="ks-py48-accent"></div>',
        '<div class="ks-py48-playerhead"><b>Quarterback Analysis</b>',
        build_badge("STEPS 7-9 VERIFIED", tone="success"),
        '</div><div class="ks-py48-body">',
        '<div class="ks-py48-identity">',
        identity or '<div>Quarterback identity unavailable.</div>',
        '</div>',
        '<section class="ks-py48-market"><strong>Current Market + Edge</strong>',
        market or '<div>Unavailable</div>',
        '</section>',
        '<div class="ks-py48-board-title"><b>Steps 7–9 Evidence Board</b>',
        '<span>Frozen certified analytical payloads</span></div>',
        '<div class="ks-py48-evidence">',
        _evidence_step(7, "Baseline Projection", projection),
        _evidence_step(8, "Context + Uncertainty", context),
        _evidence_step(9, "Distribution + Probability", distribution),
        '</div>',
        '<div class="ks-py48-support">',
        _support("Matchup Drivers", (profile or "") + (defense or "")),
        _support("Conditions + Personnel", (pressure or "") + (personnel or "") + (environment or "")),
        '</div></div></article>',
    ])

def _steps_7_9_command_center_html(captured: dict[str, list[str]]) -> str:
    return (
        build_universal_theme_css()
        + build_components_css()
        + build_responsive_css()
        + _EVIDENCE_CSS
        + '<section class="ks-py48" data-passing-yards-evidence="v48">'
        + '<header class="ks-py48-head"><div>'
        + '<div class="ks-py48-kicker">PASSING YARDS • ANALYTICAL EVIDENCE</div>'
        + '<h2>Projection → Context → Probability</h2>'
        + '<p>Steps 7–9 are shown as one visual evidence chain while the certified calculations remain frozen underneath.</p>'
        + '</div>'
        + build_badge("MODEL FROZEN", tone="success")
        + '</header>'
        + '<div class="ks-py48-grid">'
        + _player(captured, 0)
        + _player(captured, 1)
        + '</div></section>'
    )

def render_nfl_passing_yards_hub() -> None:
    original_builder = prior._premium_command_center_html
    prior._premium_command_center_html = _steps_7_9_command_center_html
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._premium_command_center_html = original_builder

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V48 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_steps_7_9_command_center_html",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
