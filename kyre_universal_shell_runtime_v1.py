"""KYRE Sports AI site-wide universal shell runtime V1.

Rollout Step 1. Presentation-only entrypoint activator over the frozen
black + glacier-blue design system. It does not own routing, models, data,
projections, markets, or page-specific controls.
"""
from __future__ import annotations

import streamlit as st

from kyre_universal_components_v1 import build_components_css
from kyre_universal_responsive_v1 import build_responsive_css
from kyre_universal_theme_v1 import build_universal_theme_css

SITEWIDE_SHELL_VERSION = "KYRE SITE-WIDE SHELL V1 • BLACK + GLACIER BLUE"

_RUNTIME_CSS = r"""
<style data-kyre-sitewide-shell="v1">
[data-testid="stAppViewContainer"]{
  background:
    radial-gradient(circle at 88% 0%,rgba(31,174,255,.07),transparent 28%),
    linear-gradient(180deg,var(--kyre-bg-0),var(--kyre-bg-1)) !important;
}
[data-testid="stHeader"]{
  background:rgba(3,6,10,.86) !important;
  border-bottom:1px solid rgba(88,201,255,.12) !important;
  backdrop-filter:blur(16px);
}
[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#05090e 0%,#07111a 100%) !important;
  border-right:1px solid rgba(88,201,255,.14) !important;
}
[data-testid="stSidebar"] *{color:var(--kyre-text-secondary)}
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] [data-baseweb="select"] *{color:var(--kyre-text-primary)}
[data-testid="stSidebar"] .stButton button{
  border:1px solid rgba(88,201,255,.18);
  border-radius:var(--kyre-radius-md);
  background:rgba(88,201,255,.07);
  color:var(--kyre-glacier-soft);
}
[data-testid="stSidebar"] [data-baseweb="select"]>div,
[data-testid="stSidebar"] [data-baseweb="input"]{
  background:#08131d;
  border-color:rgba(88,201,255,.16);
  border-radius:var(--kyre-radius-md);
}
.main .block-container{
  width:min(1500px,100%);
  max-width:1500px;
  padding-top:1.25rem;
  padding-left:1.35rem;
  padding-right:1.35rem;
}
.kyre-sitewide-top-shell{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
  margin:0 0 18px;
  padding:11px 14px;
  border:1px solid rgba(88,201,255,.16);
  border-radius:var(--kyre-radius-lg);
  background:linear-gradient(90deg,rgba(88,201,255,.07),rgba(255,255,255,.012));
  box-shadow:var(--kyre-glow-soft);
}
.kyre-sitewide-top-brand{
  font-size:.83rem;
  font-weight:950;
  letter-spacing:.09em;
  color:var(--kyre-glacier-soft);
}
.kyre-sitewide-top-brand span{color:var(--kyre-glacier)}
.kyre-sitewide-top-status{
  display:inline-flex;align-items:center;gap:7px;
  color:var(--kyre-success);
  font-size:.65rem;font-weight:850;
}
.kyre-sitewide-sidebar-brand{
  padding:8px 10px 16px;
  margin:0 0 10px;
  border-bottom:1px solid rgba(88,201,255,.13);
}
.kyre-sitewide-sidebar-brand b{
  display:block;
  color:var(--kyre-glacier-soft) !important;
  font-size:1rem;
  letter-spacing:.08em;
}
.kyre-sitewide-sidebar-brand b span{color:var(--kyre-glacier) !important}
.kyre-sitewide-sidebar-brand small{
  color:var(--kyre-text-muted) !important;
  font-size:.62rem;
  letter-spacing:.11em;
  text-transform:uppercase;
}
@media(max-width:720px){
  .main .block-container{padding: .8rem .75rem 1.2rem}
  .kyre-sitewide-top-shell{padding:10px 11px;margin-bottom:12px}
  .kyre-sitewide-top-status{font-size:.6rem}
}
</style>
"""

def build_sitewide_shell_css() -> str:
    return (
        build_universal_theme_css()
        + build_components_css()
        + build_responsive_css()
        + _RUNTIME_CSS
    )

def activate_universal_shell() -> None:
    """Mount the universal visual shell without altering route/page ownership."""
    st.markdown(build_sitewide_shell_css(), unsafe_allow_html=True)
    st.sidebar.markdown(
        '<div class="kyre-sitewide-sidebar-brand" data-kyre-sitewide-sidebar="v1">'
        '<b>KYRE <span>SPORTS AI</span></b>'
        '<small>Projection Intelligence</small></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="kyre-sitewide-top-shell" data-kyre-sitewide-topbar="v1">'
        '<div class="kyre-sitewide-top-brand">KYRE <span>SPORTS AI</span></div>'
        '<div class="kyre-sitewide-top-status">● UNIVERSAL THEME LIVE</div>'
        '</div>',
        unsafe_allow_html=True,
    )

__all__ = [
    "SITEWIDE_SHELL_VERSION",
    "activate_universal_shell",
    "build_sitewide_shell_css",
]
