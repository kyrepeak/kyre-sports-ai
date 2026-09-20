"""Universal sports website shell V1.

Presentation-only shell for Kyre Sports pages. It adds the reusable website
chrome (top bar, left navigation, spacing, typography, responsive collapse)
without touching any market/model/data logic.
"""
from __future__ import annotations

from html import escape
import streamlit as st

UNIVERSAL_SHELL_VERSION = "KYRE SPORTS UNIVERSAL SHELL V1"

_UNIVERSAL_SHELL_CSS = r"""
<style>
:root{
  --ks-nav-w:224px;
  --ks-top-h:72px;
  --ks-bg:#040b14;
  --ks-panel:#071524;
  --ks-panel-2:#0a1a2c;
  --ks-line:rgba(87,132,177,.24);
  --ks-text:#f7fbff;
  --ks-muted:#8fa5bb;
  --ks-blue:#60a5fa;
  --ks-cyan:#22d3ee;
  --ks-green:#34d399;
}
html,body,[data-testid="stAppViewContainer"]{
  background:
    radial-gradient(circle at 78% 0%,rgba(14,165,233,.08),transparent 28%),
    radial-gradient(circle at 8% 14%,rgba(59,130,246,.07),transparent 26%),
    var(--ks-bg)!important;
}
[data-testid="stHeader"]{background:transparent!important}
[data-testid="stAppViewContainer"] .main .block-container{
  max-width:1600px!important;
  padding-top:calc(var(--ks-top-h) + 30px)!important;
  padding-left:calc(var(--ks-nav-w) + 30px)!important;
  padding-right:28px!important;
}
.ks-shell,.ks-shell *{box-sizing:border-box}
.ks-topbar{
  position:fixed;z-index:9998;top:0;left:var(--ks-nav-w);right:0;height:var(--ks-top-h);
  display:flex;align-items:center;gap:16px;padding:0 24px;
  border-bottom:1px solid var(--ks-line);
  background:linear-gradient(180deg,rgba(4,11,20,.97),rgba(5,14,25,.94));
  backdrop-filter:blur(18px);
  box-shadow:0 10px 30px rgba(0,0,0,.18);
}
.ks-brand{
  display:flex;align-items:center;gap:10px;min-width:210px;color:var(--ks-text);
  font-weight:950;letter-spacing:-.03em;font-size:1.05rem;
}
.ks-brandmark{
  width:34px;height:34px;border-radius:11px;display:grid;place-items:center;
  border:1px solid rgba(96,165,250,.55);
  background:linear-gradient(145deg,#0c2b52,#07182c);
  box-shadow:0 0 20px rgba(59,130,246,.18);
}
.ks-brand span{color:var(--ks-cyan)}
.ks-breadcrumbs{display:flex;align-items:center;gap:8px;color:var(--ks-muted);font-size:.74rem;font-weight:800}
.ks-breadcrumbs b{color:#dcecff}
.ks-topspacer{flex:1}
.ks-topchip{
  display:inline-flex;align-items:center;gap:7px;min-height:34px;padding:0 12px;
  border-radius:999px;border:1px solid rgba(71,104,138,.45);
  background:rgba(8,24,41,.76);color:#c8d8e8;font-size:.67rem;font-weight:850;
}
.ks-live-dot{width:7px;height:7px;border-radius:50%;background:var(--ks-green);box-shadow:0 0 12px rgba(52,211,153,.8)}
.ks-sidebar{
  position:fixed;z-index:9999;left:0;top:0;bottom:0;width:var(--ks-nav-w);
  padding:18px 14px;border-right:1px solid var(--ks-line);
  background:linear-gradient(180deg,#06111f 0%,#050d17 100%);
  box-shadow:14px 0 34px rgba(0,0,0,.16);
}
.ks-sidebar-brand{display:flex;align-items:center;gap:10px;padding:4px 8px 22px;color:white;font-weight:950}
.ks-sidebar-brand .ks-brandmark{flex:0 0 34px}
.ks-navlabel{padding:12px 10px 7px;color:#58718b;font-size:.55rem;font-weight:950;letter-spacing:.14em;text-transform:uppercase}
.ks-navitem{
  display:flex;align-items:center;gap:11px;min-height:42px;margin:4px 0;padding:0 12px;
  border-radius:12px;border:1px solid transparent;color:#90a6bb;
  font-size:.73rem;font-weight:820;text-decoration:none!important;
}
.ks-navitem:hover{color:#eaf6ff;background:rgba(14,36,58,.72);border-color:rgba(69,112,151,.22)}
.ks-navitem.active{
  color:#eff8ff;border-color:rgba(59,130,246,.46);
  background:linear-gradient(90deg,rgba(30,64,175,.36),rgba(8,41,67,.82));
  box-shadow:inset 3px 0 0 #38bdf8,0 0 20px rgba(37,99,235,.08);
}
.ks-navicon{width:24px;text-align:center;font-size:.92rem}
.ks-shell-mobile-title{display:none}
@media(max-width:1000px){
  :root{--ks-nav-w:74px}
  .ks-sidebar{padding:18px 9px}
  .ks-sidebar-brand strong,.ks-navitem span:not(.ks-navicon),.ks-navlabel{display:none}
  .ks-navitem{justify-content:center;padding:0}
  .ks-brand{min-width:auto}
}
@media(max-width:720px){
  :root{--ks-nav-w:0px;--ks-top-h:64px}
  .ks-sidebar{display:none}
  .ks-topbar{left:0;padding:0 14px;gap:10px}
  .ks-brand{font-size:.9rem}.ks-breadcrumbs{display:none}
  .ks-topchip.secondary{display:none}
  [data-testid="stAppViewContainer"] .main .block-container{
    padding-top:calc(var(--ks-top-h) + 18px)!important;
    padding-left:14px!important;padding-right:14px!important;
  }
  .ks-shell-mobile-title{display:block;color:#8fa5bb;font-size:.62rem;font-weight:900}
}
</style>
"""

def _nav_item(icon: str, label: str, *, active: bool = False) -> str:
    cls = "ks-navitem active" if active else "ks-navitem"
    return f'<div class="{cls}"><span class="ks-navicon">{escape(icon)}</span><span>{escape(label)}</span></div>'

def shell_html(*, sport: str, market: str) -> str:
    nav = "".join([
        _nav_item("⌂", "Dashboard"),
        _nav_item("🏈", "Passing Yards", active=market.casefold() == "passing yards"),
        _nav_item("↗", "Rushing Yards"),
        _nav_item("◎", "Receiving Yards"),
        _nav_item("$", "Moneyline"),
        _nav_item("±", "Spread"),
        _nav_item("Σ", "Total"),
        _nav_item("★", "Favorites"),
    ])
    return (
        '<div class="ks-shell" data-universal-shell="v1">'
        '<aside class="ks-sidebar">'
        '<div class="ks-sidebar-brand"><div class="ks-brandmark">K</div><strong>KYRE SPORTS</strong></div>'
        '<div class="ks-navlabel">Markets</div>'
        f'{nav}'
        '</aside>'
        '<header class="ks-topbar">'
        '<div class="ks-brand"><div class="ks-brandmark">K</div>KYRE <span>SPORTS</span></div>'
        f'<div class="ks-breadcrumbs"><b>{escape(sport)}</b><span>›</span><span>{escape(market)}</span></div>'
        '<div class="ks-topspacer"></div>'
        '<div class="ks-topchip secondary">LIVE SLATE</div>'
        '<div class="ks-topchip"><span class="ks-live-dot"></span>DATA LIVE</div>'
        f'<div class="ks-shell-mobile-title">{escape(market)}</div>'
        '</header>'
        '</div>'
    )

def render_universal_shell(*, sport: str, market: str) -> None:
    st.markdown(_UNIVERSAL_SHELL_CSS, unsafe_allow_html=True)
    st.markdown(shell_html(sport=sport, market=market), unsafe_allow_html=True)

__all__ = [
    "UNIVERSAL_SHELL_VERSION",
    "_UNIVERSAL_SHELL_CSS",
    "shell_html",
    "render_universal_shell",
]
