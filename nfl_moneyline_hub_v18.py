"""NFL Moneyline V18 — visual upgrade Step 5: responsive polish + final surface.

Presentation-only wrapper over frozen V17. It adds the final responsive CSS layer
for tablet/mobile layouts while preserving every frozen Step 1-4 component and
all Moneyline analytical ownership.
"""
from __future__ import annotations

import nfl_moneyline_hub_v17 as prior

MODEL_VERSION = "NFL MONEYLINE V18 • VISUAL STEP 5 • RESPONSIVE FINAL"
FROZEN_PRIOR = "nfl_moneyline_hub_v17"
VISUAL_UPGRADE_STEP = 5
PRESENTATION_ONLY = True
DISPLAY_ONLY = True
RESPONSIVE_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_MARKET_MATH = False
SPORTSBOOK_MODEL_INFLUENCE = 0.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MONTE_CARLO_SIMULATIONS = 5_000_000

_FROZEN_STEP4_CSS = prior._step4_css

_STEP5_CSS = r"""
<style data-nfl-moneyline-visual-step="5">
/* Final responsive-only layer. No analytical ownership. */
.kml9-page,
.kml15-card,
.kml16-analysis,
.kml17-market{
  min-width:0;
  max-width:100%;
}
.kml15-card,
.kml15-team,
.kml16-panel,
.kml16-team-snapshot,
.kml17-side,
.kml17-board{
  overflow:hidden;
}
.kml15-card img,
.kml16-analysis img,
.kml17-market img{
  max-width:100%;
}
.kml15-matchup,
.kml15-meta,
.kml15-verdict p,
.kml16-fact b,
.kml16-factor div b,
.kml16-snap-head b,
.kml16-note,
.kml17-side-head b,
.kml17-foot{
  overflow-wrap:anywhere;
}
@media(max-width:900px){
  .kml9-page{width:100%!important}
  .kml9-summary{grid-template-columns:repeat(2,minmax(0,1fr))!important}
  .kml15-top{
    flex-direction:column;
    align-items:stretch;
  }
  .kml15-health{justify-content:flex-start}
  .kml15-grid{grid-template-columns:1fr}
  .kml15-primary{grid-template-columns:1.15fr .85fr .85fr}
  .kml16-overview{grid-template-columns:1fr}
  .kml16-snapshots{grid-template-columns:1fr}
  .kml16-evidence{grid-template-columns:repeat(3,minmax(0,1fr))}
  .kml17-health{grid-template-columns:repeat(2,minmax(0,1fr))}
  .kml17-grid{grid-template-columns:1fr}
}
@media(max-width:640px){
  [data-testid="stAppViewContainer"] .main .block-container{
    padding-left:.7rem!important;
    padding-right:.7rem!important;
  }
  .kml9-summary{grid-template-columns:1fr 1fr!important;gap:6px!important}
  .kml9-summary>div{padding:7px 8px!important}
  .kml15-card{border-radius:14px}
  .kml15-top{padding:.68rem}
  .kml15-grid{padding:.65rem;gap:.62rem}
  .kml15-team{border-radius:13px}
  .kml15-team-head{padding:.65rem}
  .kml15-id img{width:34px!important;height:34px!important}
  .kml15-primary{
    grid-template-columns:1fr 1fr;
    gap:.4rem;
    padding:0 .65rem .62rem;
  }
  .kml15-tile.hero{grid-column:1/-1}
  .kml15-secondary{
    grid-template-columns:repeat(2,minmax(0,1fr));
    padding:0 .65rem .65rem;
  }
  .kml15-floor{
    display:grid;
    grid-template-columns:1fr;
    gap:.28rem;
  }
  .kml15-verdict{
    grid-template-columns:1fr;
    gap:.35rem;
    margin:.65rem;
  }
  .kml15-verdict small{grid-column:auto}
  .kml16-analysis{margin:0 .65rem .65rem}
  .kml16-section-title{
    align-items:flex-start;
    flex-direction:column;
    gap:3px;
  }
  .kml16-factor{grid-template-columns:1fr}
  .kml16-snap-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .kml16-evidence{grid-template-columns:repeat(2,minmax(0,1fr))}
  .kml17-market{margin:0 .65rem .68rem}
  .kml17-title{
    align-items:flex-start;
    flex-direction:column;
    gap:3px;
  }
  .kml17-health{grid-template-columns:1fr 1fr}
  .kml17-price-grid{grid-template-columns:1fr 1fr}
  .kml17-board{padding:.5rem}
  .kml17-board-head{display:none}
  .kml17-book-row{
    grid-template-columns:1fr 1fr;
    gap:.3rem .55rem;
    padding:.48rem .35rem;
  }
  .kml17-book-row>*:nth-child(4),
  .kml17-book-row>*:nth-child(5){display:none}
}
@media(max-width:430px){
  .kml9-summary{grid-template-columns:1fr!important}
  .kml15-primary{grid-template-columns:1fr}
  .kml15-tile.hero{grid-column:auto}
  .kml15-secondary{grid-template-columns:1fr 1fr}
  .kml16-evidence{grid-template-columns:1fr 1fr}
  .kml17-health{grid-template-columns:1fr 1fr}
  .kml17-price-grid{grid-template-columns:1fr}
  .kml17-book-row{grid-template-columns:1fr 1fr}
}
</style>
"""


def _step5_css(base: str) -> str:
    return str(base or "") + _STEP5_CSS


def render_nfl_hub(market: str = "Moneyline"):
    if str(market or "Moneyline") != "Moneyline":
        raise RuntimeError("Moneyline V18 direct handler is Moneyline only.")

    original_step4_css = prior._step4_css
    prior._step4_css = lambda base: _step5_css(original_step4_css(base))
    try:
        return prior.render_nfl_hub(market)
    finally:
        prior._step4_css = original_step4_css


__all__ = [
    "DISPLAY_ONLY",
    "FROZEN_PRIOR",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "MONTE_CARLO_SIMULATIONS",
    "PRESENTATION_ONLY",
    "RESPONSIVE_ONLY",
    "SPORTSBOOK_MODEL_INFLUENCE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "VISUAL_UPGRADE_STEP",
    "_step5_css",
    "render_nfl_hub",
]
