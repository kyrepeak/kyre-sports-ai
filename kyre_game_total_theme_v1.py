"""CFB Game Total universal black + glacier-blue presentation skin V1.

Presentation-only CSS over the frozen V33 navigation + V28/V27 Game Total
surface. No data, model, grading, market, or step logic is owned here.
"""
from __future__ import annotations

from kyre_universal_components_v1 import build_components_css
from kyre_universal_responsive_v1 import build_responsive_css
from kyre_universal_theme_v1 import build_universal_theme_css

GAME_TOTAL_THEME_VERSION = "CFB GAME TOTAL UNIVERSAL THEME V1 • BLACK + GLACIER BLUE"

_OVERRIDES = r"""
<style data-kyre-game-total-universal="v1">
.gt229-sportnav,
.gt225-hero,
.gt226-wrap,
.gt227-section{
  color:var(--kyre-text-primary)!important;
}
.gt229-sportnav{
  border:1px solid rgba(88,201,255,.18)!important;
  border-radius:var(--kyre-radius-2xl)!important;
  background:
    radial-gradient(circle at 90% 0%,rgba(88,201,255,.12),transparent 30%),
    linear-gradient(145deg,#05090e,var(--kyre-bg-1))!important;
  box-shadow:var(--kyre-shadow-card),var(--kyre-glow-soft)!important;
}
.gt229-title b,
.gt229-brand b,
.gt225-name,
.gt226-title b,
.gt227-name,
.gt227-head b{
  color:var(--kyre-text-primary)!important;
}
.gt229-title em,
.gt229-brand span,
.gt225-topline,
.gt226-label,
.gt227-meta{
  color:var(--kyre-glacier)!important;
}
.gt229-title span,
.gt225-record,
.gt226-title span,
.gt227-head span,
.gt227-foot{
  color:var(--kyre-text-muted)!important;
}
.gt229-card,
.gt232-dropdown,
.gt232-category,
.gt233-category{
  border-color:rgba(88,201,255,.17)!important;
  background:linear-gradient(145deg,var(--kyre-surface-raised),var(--kyre-surface))!important;
}
.gt229-card[data-selected="true"],
.gt232-sport.cfb .gt229-card{
  border-color:rgba(88,201,255,.42)!important;
  box-shadow:var(--kyre-glow-active)!important;
  background:linear-gradient(145deg,rgba(31,174,255,.13),rgba(88,201,255,.04))!important;
}
.gt229-icon,
.gt229-arrow,
.gt233-category:after,
.gt232-sport.cfb .gt233-category:after{
  color:var(--kyre-glacier)!important;
}
.gt232-category,
.gt233-category{
  color:var(--kyre-text-secondary)!important;
}
.gt233-category:hover{
  border-color:rgba(88,201,255,.45)!important;
  background:rgba(31,174,255,.09)!important;
}
.gt225-hero,
.gt226-wrap,
.gt227-section{
  border-color:rgba(88,201,255,.22)!important;
  background:
    radial-gradient(circle at 88% 0%,rgba(88,201,255,.09),transparent 34%),
    linear-gradient(150deg,var(--kyre-surface-raised),#07121c)!important;
  box-shadow:var(--kyre-shadow-card),var(--kyre-glow-soft)!important;
}
.gt226-card,
.gt226-progress,
.gt226-badge,
.gt227-card,
.gt227-stat{
  border-color:rgba(88,201,255,.16)!important;
  background:linear-gradient(145deg,var(--kyre-surface-raised),var(--kyre-surface))!important;
}
.gt226-card.primary,
.gt226-card.lean,
.gt227-card.away,
.gt227-card.home{
  background:
    radial-gradient(circle at 90% 0%,rgba(88,201,255,.06),transparent 38%),
    linear-gradient(150deg,#081521,#091824)!important;
}
.gt226-gauge,
.gt227-vs,
.gt225-vs{
  box-shadow:0 0 0 5px rgba(5,18,28,.22),var(--kyre-glow-soft)!important;
}
.gt226-cert,
.gt225-conf,
.gt227-record,
.gt226-grade{
  border-color:rgba(88,201,255,.22)!important;
  color:var(--kyre-glacier-soft)!important;
}
.gt160-masthead{
  border-bottom:1px solid rgba(88,201,255,.18)!important;
  background:linear-gradient(90deg,#05090e,#07121c)!important;
}
@media(max-width:760px){
  .gt229-sportnav,
  .gt225-hero,
  .gt226-wrap,
  .gt227-section{border-radius:var(--kyre-radius-xl)!important}
}
@media(max-width:560px){
  .gt229-sportnav{padding:12px!important}
  .gt225-hero,
  .gt226-wrap,
  .gt227-section{margin-top:10px!important}
}
</style>
"""

def build_game_total_theme_css() -> str:
    return (
        build_universal_theme_css()
        + build_components_css()
        + build_responsive_css()
        + _OVERRIDES
    )

__all__ = ["GAME_TOTAL_THEME_VERSION","build_game_total_theme_css"]
