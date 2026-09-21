"""NFL Passing Yards V47 — premium matchup command center.

Presentation-only wrapper over frozen V46. Step 2 of the Passing Yards visual
upgrade. It replaces only the final responsive player-card composition with a
clean two-quarterback command center while preserving every captured identity,
projection, market, matchup, and evidence payload from the frozen pipeline.
"""
from __future__ import annotations

from html import escape

import nfl_passing_yards_hub_v45 as responsive
import nfl_passing_yards_hub_v46 as prior
from kyre_universal_components_v1 import build_badge, build_components_css
from kyre_universal_responsive_v1 import build_responsive_css
from kyre_universal_theme_v1 import build_universal_theme_css

MODEL_VERSION = "NFL PASSING YARDS V47 • PREMIUM MATCHUP COMMAND CENTER"
FROZEN_PRIOR = "nfl_passing_yards_hub_v46"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MAY_MODIFY_PROJECTION = False
PRESENTATION_ONLY = True

_CORE_CSS = r"""
<style data-passing-yards-core-polish="v47">
.ks-py47,.ks-py47 *{box-sizing:border-box}
.ks-py47{margin:.45rem 0 1.15rem;color:var(--kyre-text-primary)}
.ks-py47-head{
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  margin:0 0 .72rem;padding:.9rem 1rem;
  border:1px solid rgba(88,201,255,.22);border-radius:16px;
  background:
    radial-gradient(circle at 90% 0%,rgba(88,201,255,.11),transparent 30%),
    linear-gradient(145deg,#091522,#07111a);
  box-shadow:0 12px 32px rgba(0,0,0,.18),0 0 22px rgba(46,168,255,.05)
}
.ks-py47-kicker{
  color:var(--kyre-glacier);font-size:.62rem;font-weight:950;
  letter-spacing:.13em;text-transform:uppercase
}
.ks-py47-title{
  margin:.18rem 0 0;font-size:clamp(1.2rem,2vw,1.7rem);
  line-height:1.1;font-weight:950;letter-spacing:-.025em
}
.ks-py47-sub{
  margin:.34rem 0 0;color:var(--kyre-text-muted);font-size:.72rem;line-height:1.45
}
.ks-py47-grid{
  display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.8rem
}
.ks-py47-player{
  min-width:0;overflow:hidden;border:1px solid rgba(88,201,255,.20);
  border-radius:18px;background:
    linear-gradient(155deg,rgba(12,28,42,.98),rgba(6,15,23,.99));
  box-shadow:0 16px 38px rgba(0,0,0,.20)
}
.ks-py47-accent{
  height:3px;background:linear-gradient(90deg,var(--kyre-glacier),rgba(88,201,255,.08))
}
.ks-py47-playerhead{
  display:flex;align-items:center;justify-content:space-between;gap:10px;
  padding:.7rem .82rem;border-bottom:1px solid rgba(88,201,255,.12);
  background:linear-gradient(90deg,rgba(88,201,255,.06),transparent)
}
.ks-py47-playerhead b{
  color:var(--kyre-glacier-soft);font-size:.64rem;font-weight:950;
  letter-spacing:.09em;text-transform:uppercase
}
.ks-py47-body{padding:.78rem}
.ks-py47-identity{
  min-width:0;margin-bottom:.68rem;padding:.15rem 0 .35rem
}
.ks-py47-primary{
  display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.58rem
}
.ks-py47-tile{
  min-width:0;padding:.7rem;border:1px solid rgba(88,201,255,.16);
  border-radius:14px;background:rgba(6,17,27,.88)
}
.ks-py47-tile strong{
  display:block;margin-bottom:.4rem;color:var(--kyre-glacier-soft);
  font-size:.58rem;font-weight:950;letter-spacing:.07em;text-transform:uppercase
}
.ks-py47-evidence{
  display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.5rem;
  margin-top:.6rem
}
.ks-py47-detail{
  min-width:0;border:1px solid rgba(88,201,255,.13);
  border-radius:12px;background:rgba(255,255,255,.015);padding:.58rem
}
.ks-py47-detail summary{
  cursor:pointer;list-style:none;color:var(--kyre-glacier);
  font-size:.62rem;font-weight:900
}
.ks-py47-detail summary::-webkit-details-marker{display:none}
.ks-py47-detail summary span{
  display:block;margin-top:.16rem;color:var(--kyre-text-muted);
  font-size:.52rem;font-weight:700;line-height:1.35
}
.ks-py47-detailbody{margin-top:.55rem}
@media(max-width:900px){
  .ks-py47-grid{grid-template-columns:1fr}
}
@media(max-width:620px){
  .ks-py47-head{padding:.75rem;border-radius:14px}
  .ks-py47-primary,.ks-py47-evidence{grid-template-columns:1fr}
  .ks-py47-player{border-radius:15px}
}
</style>
"""

def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""

def _detail(title: str, subtitle: str, content: str) -> str:
    return (
        '<details class="ks-py47-detail">'
        f'<summary>{escape(title)}<span>{escape(subtitle)}</span></summary>'
        f'<div class="ks-py47-detailbody">{content or "<div>Unavailable</div>"}</div>'
        '</details>'
    )

def _premium_player(captured: dict[str, list[str]], index: int) -> str:
    identity = _piece(captured, "identity", index)
    projection = _piece(captured, "projection", index)
    market = _piece(captured, "market", index)
    profile = _piece(captured, "profile", index)
    defense = _piece(captured, "defense", index)
    pressure = _piece(captured, "pressure", index)
    personnel = _piece(captured, "personnel", index)
    environment = _piece(captured, "environment", index)
    context = _piece(captured, "context", index)
    distribution = _piece(captured, "distribution", index)

    return "".join([
        f'<article class="ks-py47-player" data-passing-player="{index}">',
        '<div class="ks-py47-accent"></div>',
        '<div class="ks-py47-playerhead"><b>Quarterback Analysis</b>',
        build_badge("LIVE VERIFIED", tone="success"),
        '</div><div class="ks-py47-body">',
        '<div class="ks-py47-identity">',
        identity or '<div>Quarterback identity unavailable.</div>',
        '</div>',
        '<div class="ks-py47-primary">',
        '<section class="ks-py47-tile"><strong>Monster Projection</strong>',
        projection or '<div>Unavailable</div>',
        '</section>',
        '<section class="ks-py47-tile"><strong>Market + Edge</strong>',
        market or '<div>Unavailable</div>',
        '</section></div>',
        '<div class="ks-py47-evidence">',
        _detail("Matchup", "Profile + opponent defense", (profile or "") + (defense or "")),
        _detail("Conditions", "Pressure + personnel + environment", (pressure or "") + (personnel or "") + (environment or "")),
        _detail("Deep Data", "Context + distribution", (context or "") + (distribution or "")),
        '</div></div></article>',
    ])

def _premium_command_center_html(captured: dict[str, list[str]]) -> str:
    return (
        build_universal_theme_css()
        + build_components_css()
        + build_responsive_css()
        + _CORE_CSS
        + '<section class="ks-py47" data-passing-yards-core="v47">'
        + '<header class="ks-py47-head"><div>'
        + '<div class="ks-py47-kicker">PASSING YARDS • MATCHUP COMMAND CENTER</div>'
        + '<h2 class="ks-py47-title">Quarterback Battle Board</h2>'
        + '<p class="ks-py47-sub">Projection, market edge, matchup context, and deeper evidence — organized around the two verified starting quarterbacks.</p>'
        + '</div>'
        + build_badge("2 QB • LIVE ANALYSIS", tone="success")
        + '</header>'
        + '<div class="ks-py47-grid">'
        + _premium_player(captured, 0)
        + _premium_player(captured, 1)
        + '</div></section>'
    )

def render_nfl_passing_yards_hub() -> None:
    original_builder = responsive._responsive_player_cards_html
    responsive._responsive_player_cards_html = _premium_command_center_html
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        responsive._responsive_player_cards_html = original_builder

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V47 only renders Passing Yards.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_premium_command_center_html",
    "_premium_player",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
