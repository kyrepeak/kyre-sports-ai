"""NFL Moneyline universal black + glacier-blue presentation skin V1.

Pure presentation CSS. Reuses the frozen universal theme/component/responsive
layers and overrides only existing V9 Moneyline selectors.
"""
from __future__ import annotations

from kyre_universal_components_v1 import build_components_css
from kyre_universal_responsive_v1 import build_responsive_css
from kyre_universal_theme_v1 import build_universal_theme_css

MONEYLINE_THEME_VERSION = "NFL MONEYLINE UNIVERSAL THEME V1 • BLACK + GLACIER BLUE"

_OVERRIDES = r"""
<style data-kyre-moneyline-universal="v1">
.kml9-page{
  max-width:1380px;
  margin:0 auto;
  color:var(--kyre-text-primary);
}
.kml9-hero{
  border:1px solid rgba(88,201,255,.28)!important;
  border-radius:var(--kyre-radius-2xl)!important;
  background:
    radial-gradient(circle at 88% 0%,rgba(88,201,255,.15),transparent 31%),
    linear-gradient(145deg,#05090e,var(--kyre-bg-1))!important;
  box-shadow:var(--kyre-shadow-float),var(--kyre-glow-soft)!important;
  padding:var(--kyre-space-5)!important;
}
.kml9-title{
  color:var(--kyre-text-primary)!important;
  font-size:clamp(1.55rem,3vw,2.3rem)!important;
  letter-spacing:-.035em!important;
}
.kml9-title span{color:var(--kyre-glacier)!important}
.kml9-sub{color:var(--kyre-text-secondary)!important;font-size:var(--kyre-font-sm)!important}
.kml9-chip,
.kml9-health span,
.kml9-mini-status span{
  border-color:rgba(88,201,255,.22)!important;
  background:rgba(88,201,255,.07)!important;
  color:var(--kyre-glacier-soft)!important;
}
.kml9-summary>div,
.kml9-team-panel,
.kml9-stat,
.kml9-verdict{
  border-color:rgba(88,201,255,.16)!important;
  background:linear-gradient(145deg,var(--kyre-surface-raised),var(--kyre-surface))!important;
  box-shadow:var(--kyre-shadow-card)!important;
}
.kml9-matchup-card{
  border-color:rgba(88,201,255,.26)!important;
  border-radius:var(--kyre-radius-xl)!important;
  background:linear-gradient(150deg,var(--kyre-surface-raised),#07121c)!important;
  box-shadow:var(--kyre-shadow-card),var(--kyre-glow-soft)!important;
  padding:var(--kyre-space-4)!important;
}
.kml9-matchup-top{border-bottom-color:rgba(88,201,255,.14)!important}
.kml9-phase{color:var(--kyre-glacier)!important}
.kml9-matchup-top b,
.kml9-team-id b,
.kml9-stat b,
.kml9-verdict b,
.kml9-summary b{color:var(--kyre-text-primary)!important}
.kml9-matchup-top em,
.kml9-matchup-top small,
.kml9-team-id span,
.kml9-stat span,
.kml9-stat small,
.kml9-summary span,
.kml9-floor,
.kml9-verdict small{color:var(--kyre-text-muted)!important}
.kml9-stat.hero{
  border-color:rgba(88,201,255,.40)!important;
  background:linear-gradient(145deg,rgba(31,174,255,.10),rgba(88,201,255,.035))!important;
  box-shadow:var(--kyre-glow-soft)!important;
}
.kml9-stat.hero b{color:var(--kyre-glacier-soft)!important}
.kml9-grade{
  border-color:rgba(88,201,255,.24)!important;
  color:var(--kyre-glacier-soft)!important;
  background:rgba(88,201,255,.06)!important;
}
.kml9-verdict p{color:var(--kyre-text-secondary)!important}
.kml9-empty{
  border-color:rgba(88,201,255,.25)!important;
  background:var(--kyre-surface)!important;
  color:var(--kyre-text-secondary)!important;
}
@media(max-width:820px){
  .kml9-matchup-card{padding:14px!important}
}
@media(max-width:520px){
  .kml9-hero{padding:16px!important}
  .kml9-matchup-card{padding:12px!important}
  .kml9-title{font-size:1.5rem!important}
  .kml9-summary{grid-template-columns:1fr 1fr!important}
}
</style>
"""

def build_moneyline_theme_css(frozen_v9_css: str) -> str:
    return (
        build_universal_theme_css()
        + build_components_css()
        + build_responsive_css()
        + str(frozen_v9_css or "")
        + _OVERRIDES
    )

__all__ = ["MONEYLINE_THEME_VERSION","build_moneyline_theme_css"]
