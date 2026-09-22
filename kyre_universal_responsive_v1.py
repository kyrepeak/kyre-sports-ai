"""KYRE Sports AI universal responsive overlay V1.

Step 5 NEW_BUILD artifact. Additive CSS only over the frozen theme, shell,
components, and Passing Yards V44 presentation. No production data/model logic.
"""
from __future__ import annotations

RESPONSIVE_VERSION = "KYRE UNIVERSAL RESPONSIVE V1 • DESKTOP + TABLET + MOBILE"

def build_responsive_css() -> str:
    return r"""
<style data-kyre-universal-responsive="v1">
/* Global overflow + sizing guardrails */
.kyre-universe-shell,
.kyre-universe-main,
.kyre-universe-main-inner,
.kyre-universe-content-slot,
.ks-v44-page,
.ks-v44-grid,
.ks-v44-player,
.ks-v44-body,
.ks-v44-result,
.ks-v44-previews,
.kyre-ui-grid,
.kyre-ui-card,
.kyre-ui-stat{
  min-width:0;
  max-width:100%;
}
.kyre-universe-content-slot,
.ks-v44-page,
.ks-v44-player,
.kyre-ui-card{
  overflow-wrap:anywhere;
}
img,svg,video,canvas{max-width:100%;height:auto}

/* Desktop: preserve density while preventing page-width spill */
@media(min-width:1200px){
  .kyre-universe-main{padding:28px 30px}
  .kyre-universe-main-inner{width:min(1500px,100%)}
  .ks-v44-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .ks-v44-previews{grid-template-columns:repeat(3,minmax(0,1fr))}
}

/* Compact desktop / large tablet */
@media(max-width:1100px){
  .kyre-universe-topbar{gap:10px;padding-left:16px;padding-right:16px}
  .kyre-universe-search{flex-basis:300px;max-width:420px}
  .ks-v44-hero{padding:var(--kyre-space-5)}
  .ks-v44-grid{gap:var(--kyre-space-3)}
  .ks-v44-player-head{flex-wrap:wrap}
}

/* Tablet */
@media(max-width:900px){
  .ks-v44-grid{grid-template-columns:1fr}
  .ks-v44-hero-row{flex-direction:column;align-items:flex-start}
  .ks-v44-result{grid-template-columns:repeat(2,minmax(0,1fr))}
  .ks-v44-previews{grid-template-columns:repeat(3,minmax(0,1fr))}
  .kyre-ui-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
  .kyre-ui-tabs{padding-bottom:6px}
}

/* Narrow tablet: top controls become two-row instead of squeezing */
@media(max-width:780px){
  .kyre-universe-topbar{flex-wrap:wrap;height:auto;min-height:64px;padding-top:9px;padding-bottom:9px}
  .kyre-universe-search{order:3;flex:1 0 100%;max-width:none}
  .kyre-universe-topcontrols{margin-left:auto}
  .ks-v44-previews{grid-template-columns:repeat(2,minmax(0,1fr))}
}

/* Mobile */
@media(max-width:620px){
  .kyre-universe-main{padding:12px}
  .kyre-universe-search,
  .kyre-ui-search,
  .kyre-ui-control,
  .kyre-ui-button,
  .kyre-ui-tab,
  .kyre-ui-accordion summary{
    min-height:44px;
  }
  .kyre-universe-chip{min-height:40px}
  .kyre-ui-tabs{gap:6px;overflow-x:auto;scroll-snap-type:x proximity}
  .kyre-ui-tab{scroll-snap-align:start;padding-left:13px;padding-right:13px}
  .ks-v44-hero{padding:18px;border-radius:var(--kyre-radius-xl)}
  .ks-v44-title{font-size:clamp(1.85rem,9vw,2.45rem);line-height:1.04}
  .ks-v44-sub{font-size:.82rem;line-height:1.55}
  .ks-v44-result,
  .ks-v44-previews,
  .kyre-ui-grid{grid-template-columns:1fr}
  .ks-v44-body{padding:14px}
  .ks-v44-player-head{padding:12px 14px}
  .ks-v44-panel,
  .ks-v44-preview,
  .kyre-ui-card,
  .kyre-ui-stat{padding:13px}
  .kyre-ui-accordion summary{padding-top:8px;padding-bottom:8px}
}

/* Small phones */
@media(max-width:430px){
  .kyre-universe-main{padding:9px}
  .kyre-universe-topbar{padding-left:9px;padding-right:9px}
  .kyre-universe-chip.optional{display:none}
  .ks-v44-hero{padding:15px}
  .ks-v44-kicker{font-size:.64rem;letter-spacing:.10em}
  .ks-v44-title{font-size:clamp(1.72rem,10vw,2.15rem)}
  .ks-v44-player-head{align-items:flex-start}
  .kyre-ui-badge{white-space:normal;text-align:center}
}

/* Extra-small safety */
@media(max-width:360px){
  .ks-v44-hero{padding:13px}
  .ks-v44-body{padding:11px}
  .ks-v44-panel,.ks-v44-preview{padding:11px}
  .kyre-ui-tab{padding-left:11px;padding-right:11px}
  .kyre-universe-chip{font-size:.58rem}
}

/* Touch devices: rely on visible active state instead of hover-only affordances */
@media(hover:none){
  .kyre-universe-navlink:hover,
  .kyre-ui-button:hover,
  .kyre-ui-tab:hover{filter:none}
}
</style>
"""

__all__ = ["RESPONSIVE_VERSION","build_responsive_css"]
