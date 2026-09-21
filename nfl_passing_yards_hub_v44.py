"""NFL Passing Yards V44 — universal black + glacier-blue presentation.

Step 4 of the universal website theme rollout. V44 is presentation-only over
frozen V43. It replaces only V43's final layered HTML composition while
preserving the certified Passing Yards model/data pipeline unchanged.
"""
from __future__ import annotations

from html import escape

import nfl_passing_yards_hub_v43 as prior
from kyre_universal_components_v1 import (
    build_badge,
    build_components_css,
    build_tabs,
)
from kyre_universal_theme_v1 import build_universal_theme_css

MODEL_VERSION = "NFL PASSING YARDS V44 • UNIVERSAL BLACK + GLACIER BLUE"
FROZEN_PRIOR = "nfl_passing_yards_hub_v43"
DISPLAY_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_V44_CSS = r"""
<style data-passing-yards-universal-theme="v44">
.ks-v44-page,.ks-v44-page *{box-sizing:border-box}
.ks-v44-page{
  color:var(--kyre-text-primary);
  margin:var(--kyre-space-2) 0 var(--kyre-space-6);
}
.ks-v44-hero{
  position:relative;overflow:hidden;
  border:1px solid rgba(88,201,255,.30);
  border-radius:var(--kyre-radius-2xl);
  padding:var(--kyre-space-6);
  background:
    radial-gradient(circle at 88% 0%,rgba(88,201,255,.16),transparent 32%),
    radial-gradient(circle at 18% 110%,rgba(31,174,255,.08),transparent 30%),
    linear-gradient(145deg,#05090e 0%,var(--kyre-bg-1) 58%,#0a1c29 100%);
  box-shadow:var(--kyre-shadow-float),var(--kyre-glow-soft);
}
.ks-v44-hero-row{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--kyre-space-5)}
.ks-v44-kicker{
  color:var(--kyre-glacier);font-size:var(--kyre-font-xs);font-weight:950;
  letter-spacing:.14em;text-transform:uppercase
}
.ks-v44-title{
  margin:6px 0 0;color:var(--kyre-text-primary);font-size:var(--kyre-font-display);
  line-height:1;font-weight:950;letter-spacing:-.045em
}
.ks-v44-sub{
  max-width:760px;margin-top:10px;color:var(--kyre-text-secondary);
  font-size:var(--kyre-font-sm);line-height:1.6
}
.ks-v44-nav{margin:var(--kyre-space-4) 0}
.ks-v44-grid{
  display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--kyre-space-4)
}
.ks-v44-player{
  min-width:0;border:1px solid rgba(88,201,255,.18);
  border-radius:var(--kyre-radius-xl);
  background:linear-gradient(150deg,var(--kyre-surface-raised),#07121c);
  box-shadow:var(--kyre-shadow-card),var(--kyre-glow-soft);overflow:hidden
}
.ks-v44-player-head{
  display:flex;align-items:center;justify-content:space-between;gap:10px;
  padding:14px 16px;border-bottom:1px solid rgba(88,201,255,.14);
  background:linear-gradient(90deg,rgba(31,174,255,.07),transparent)
}
.ks-v44-player-head b{
  color:var(--kyre-glacier-soft);font-size:var(--kyre-font-xs);
  letter-spacing:.1em;text-transform:uppercase
}
.ks-v44-body{padding:var(--kyre-space-4)}
.ks-v44-result{
  display:grid;grid-template-columns:repeat(2,minmax(0,1fr));
  gap:var(--kyre-space-3);margin-top:var(--kyre-space-3)
}
.ks-v44-panel{
  min-width:0;padding:var(--kyre-space-3);
  border:1px solid rgba(88,201,255,.16);
  border-radius:var(--kyre-radius-lg);
  background:linear-gradient(145deg,#07121c,#091823)
}
.ks-v44-panel strong{
  display:block;margin-bottom:7px;color:var(--kyre-glacier-soft);
  font-size:var(--kyre-font-xs);font-weight:900;letter-spacing:.07em;text-transform:uppercase
}
.ks-v44-previews{
  display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
  gap:var(--kyre-space-3);margin-top:var(--kyre-space-3)
}
.ks-v44-preview{
  min-width:0;padding:var(--kyre-space-3);
  border:1px solid rgba(88,201,255,.14);
  border-radius:var(--kyre-radius-lg);
  background:rgba(255,255,255,.018)
}
.ks-v44-preview b{display:block;color:var(--kyre-text-primary);font-size:var(--kyre-font-sm);margin-bottom:4px}
.ks-v44-preview span{color:var(--kyre-text-muted);font-size:var(--kyre-font-xs);line-height:1.4}
.ks-v44-deep{margin-top:8px}
.ks-v44-deep summary{
  cursor:pointer;color:var(--kyre-glacier);font-size:var(--kyre-font-xs);font-weight:850
}
.ks-v44-deep-body{margin-top:8px}
.ks-v44-accent{height:2px;background:linear-gradient(90deg,var(--kyre-glacier-strong),transparent);opacity:.8}

@media(max-width:900px){
  .ks-v44-grid{grid-template-columns:1fr}
  .ks-v44-hero-row{flex-direction:column}
}
@media(max-width:620px){
  .ks-v44-hero{padding:var(--kyre-space-4);border-radius:var(--kyre-radius-xl)}
  .ks-v44-result,.ks-v44-previews{grid-template-columns:1fr}
  .ks-v44-title{font-size:2rem}
}
</style>
"""

def _piece(captured: dict[str, list[str]], key: str, index: int) -> str:
    rows = captured.get(key) or []
    if key == "environment":
        return rows[0] if rows else ""
    return rows[index] if index < len(rows) else ""

def _deep_preview(title: str, subtitle: str, content: str) -> str:
    return (
        '<section class="ks-v44-preview">'
        f'<b>{escape(title)}</b><span>{escape(subtitle)}</span>'
        '<details class="ks-v44-deep"><summary>Open Full Breakdown →</summary>'
        f'<div class="ks-v44-deep-body">{content or "<div>Unavailable</div>"}</div>'
        '</details></section>'
    )

def _player(captured: dict[str, list[str]], index: int) -> str:
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
        f'<article class="ks-v44-player" data-universal-passing-qb="{index}">',
        '<div class="ks-v44-accent"></div>',
        '<div class="ks-v44-player-head"><b>Quarterback Analysis</b>',
        build_badge("LIVE CERTIFIED DATA", tone="success"),
        '</div><div class="ks-v44-body">',
        identity or '<div>Quarterback identity unavailable.</div>',
        '<div class="ks-v44-result">',
        '<section class="ks-v44-panel"><strong>Monster Projection</strong>',
        projection or '<div>Unavailable</div>',
        '</section>',
        '<section class="ks-v44-panel"><strong>Market + Edge</strong>',
        market or '<div>Unavailable</div>',
        '</section></div>',
        '<div class="ks-v44-previews">',
        _deep_preview("Why", "Profile + matchup drivers", (profile or "") + (defense or "")),
        _deep_preview("Trends", "Pressure + personnel + environment", (pressure or "") + (personnel or "") + (environment or "")),
        _deep_preview("Deep Data", "Context + distribution", (context or "") + (distribution or "")),
        '</div></div></article>',
    ])

def _universal_player_cards_html(captured: dict[str, list[str]]) -> str:
    tabs = build_tabs(
        ("Overview", "Why", "Matchup", "Trends", "Market", "Deep Data"),
        active="Overview",
    )
    return (
        build_universal_theme_css()
        + build_components_css()
        + _V44_CSS
        + '<section class="ks-v44-page" data-passing-yards-universal="v44">'
        + '<header class="ks-v44-hero"><div class="ks-v44-hero-row"><div>'
        + '<div class="ks-v44-kicker">NFL PLAYER PROPS • UNIVERSAL THEME</div>'
        + '<h1 class="ks-v44-title">Passing Yards</h1>'
        + '<div class="ks-v44-sub">Premium quarterback projections, matchup context, market intelligence, and deep evidence — powered by the existing frozen Passing Yards model.</div>'
        + '</div>'
        + build_badge("LIVE DATA • MODEL FROZEN", tone="success")
        + '</div></header>'
        + '<div class="ks-v44-nav">' + tabs + '</div>'
        + '<div class="ks-v44-grid">'
        + _player(captured, 0)
        + _player(captured, 1)
        + '</div></section>'
    )

def render_nfl_passing_yards_hub() -> None:
    """Run frozen V43 and replace only its final presentation builder."""
    original_builder = prior._layered_player_cards_html
    prior._layered_player_cards_html = _universal_player_cards_html
    try:
        return prior.render_nfl_passing_yards_hub()
    finally:
        prior._layered_player_cards_html = original_builder

def render_nfl_hub(market: str = "Passing Yards") -> None:
    if str(market or "Passing Yards") != "Passing Yards":
        raise ValueError("NFL Passing Yards V44 only renders the Passing Yards market.")
    return render_nfl_passing_yards_hub()

__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_universal_player_cards_html",
    "render_nfl_hub",
    "render_nfl_passing_yards_hub",
]
