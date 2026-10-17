"""KYRE Sports AI universal shell runtime V2.

Additive production shell over V1. Owns persistent brand visibility and the
universal scroll-to-top control only; models, data, projections, markets and
page-specific controls remain delegated to existing route modules.
"""
from __future__ import annotations

import streamlit as st

import kyre_universal_shell_runtime_v1 as prior

SITEWIDE_SHELL_VERSION = "KYRE SITE-WIDE SHELL V2 • STICKY BRAND + TOP"

_V2_CSS = r"""
<style data-kyre-sitewide-shell="v2">
html{scroll-behavior:smooth;}
.kyre-universal-shell-v2{
  position:sticky;
  top:.45rem;
  z-index:999990;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:14px;
  margin:0 0 16px;
  padding:12px 15px;
  border:1px solid rgba(88,201,255,.22);
  border-radius:16px;
  background:rgba(5,11,18,.94);
  box-shadow:0 12px 34px rgba(0,0,0,.26),0 0 22px rgba(88,201,255,.06);
  backdrop-filter:blur(18px);
}
.kyre-universal-shell-v2__brand{
  font-size:.92rem;
  font-weight:950;
  letter-spacing:.11em;
  color:#d8f3ff;
  white-space:nowrap;
}
.kyre-universal-shell-v2__brand span{color:#58c9ff;}
.kyre-universal-shell-v2__status{
  font-size:.63rem;
  font-weight:850;
  letter-spacing:.04em;
  color:#7ee2b8;
  white-space:nowrap;
}
.kyre-universal-top-v2{
  position:fixed;
  right:18px;
  bottom:88px;
  z-index:999999;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  min-width:58px;
  height:44px;
  padding:0 13px;
  border:1px solid rgba(88,201,255,.34);
  border-radius:999px;
  background:rgba(7,17,28,.94);
  color:#d8f3ff !important;
  text-decoration:none !important;
  font-size:.75rem;
  font-weight:900;
  letter-spacing:.02em;
  box-shadow:0 12px 28px rgba(0,0,0,.30),0 0 20px rgba(88,201,255,.08);
  backdrop-filter:blur(14px);
}
.kyre-universal-top-v2:hover,
.kyre-universal-top-v2:focus{
  border-color:rgba(88,201,255,.7);
  background:#0a2132;
  color:white !important;
}
#kyre-universal-top-anchor{scroll-margin-top:5.5rem;}
@media(max-width:720px){
  .kyre-universal-shell-v2{top:.25rem;padding:10px 12px;margin-bottom:12px;}
  .kyre-universal-shell-v2__brand{font-size:.78rem;}
  .kyre-universal-shell-v2__status{display:none;}
  .kyre-universal-top-v2{right:12px;bottom:76px;min-width:52px;height:42px;padding:0 11px;}
}
</style>
"""


def build_universal_shell_v2_css() -> str:
    return prior.build_sitewide_shell_css() + _V2_CSS


def build_universal_shell_v2_html() -> str:
    return (
        '<div id="kyre-universal-top-anchor"></div>'
        '<div class="kyre-universal-shell-v2" data-kyre-sitewide-topbar="v2">'
        '<div class="kyre-universal-shell-v2__brand">KYRE <span>SPORTS AI</span></div>'
        '<div class="kyre-universal-shell-v2__status">● LIVE SPORTS INTELLIGENCE</div>'
        '</div>'
        '<a class="kyre-universal-top-v2" href="#kyre-universal-top-anchor" '
        'aria-label="Back to top" title="Back to top">↑ Top</a>'
    )


def activate_universal_shell() -> None:
    """Mount the permanent universal brand shell before route rendering."""
    prior.activate_step3_page()
    st.markdown(build_universal_shell_v2_css(), unsafe_allow_html=True)
    st.sidebar.markdown(
        '<div class="kyre-sitewide-sidebar-brand" data-kyre-sitewide-sidebar="v2">'
        '<b>KYRE <span>SPORTS AI</span></b>'
        '<small>Projection Intelligence</small></div>',
        unsafe_allow_html=True,
    )
    st.markdown(build_universal_shell_v2_html(), unsafe_allow_html=True)


__all__ = [
    "SITEWIDE_SHELL_VERSION",
    "activate_universal_shell",
    "build_universal_shell_v2_css",
    "build_universal_shell_v2_html",
]
