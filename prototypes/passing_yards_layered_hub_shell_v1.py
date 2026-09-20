"""Passing Yards layered prototype — Step 2 universal website shell.

NEW_BUILD only. This module is intentionally separate from every certified
Passing Yards production renderer.
"""
from __future__ import annotations

from html import escape

STEP = 2
PROTOTYPE_VERSION = "PASSING YARDS LAYERED HUB • STEP 2 • UNIVERSAL SHELL"

SHELL_CSS = r"""
<style data-py-layered-shell-css="true">
:root{
  --ks-bg:#040a12;--ks-panel:#081321;--ks-panel2:#0b1928;--ks-line:#173149;
  --ks-text:#f7fbff;--ks-muted:#8fa6bb;--ks-blue:#38a7ff;--ks-teal:#38e0c0;
  --ks-rail:232px;--ks-top:72px;
}
*{box-sizing:border-box}
#ks-shell-menu-toggle{position:fixed;opacity:0;pointer-events:none}
.ks-shell{min-height:100vh;background:
 radial-gradient(circle at 76% 4%,rgba(43,139,255,.16),transparent 28rem),
 linear-gradient(180deg,#050b13 0%,#07101b 100%);color:var(--ks-text);
 font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.ks-shell-topbar{position:fixed;z-index:120;top:0;left:var(--ks-rail);right:0;height:var(--ks-top);
 display:flex;align-items:center;gap:16px;padding:0 24px;border-bottom:1px solid var(--ks-line);
 background:rgba(4,10,18,.90);backdrop-filter:blur(18px)}
.ks-shell-brand{display:flex;align-items:center;gap:10px;font-weight:950;letter-spacing:-.03em;font-size:1.05rem}
.ks-shell-brandmark{width:31px;height:31px;border-radius:10px;display:grid;place-items:center;
 background:linear-gradient(145deg,#1769ff,#36d4d0);box-shadow:0 0 24px rgba(56,167,255,.25)}
.ks-shell-context{display:flex;gap:8px;align-items:center;margin-left:auto}
.ks-shell-pill{border:1px solid #23445f;background:#091827;color:#d7e9f8;border-radius:12px;
 padding:8px 11px;font-size:.73rem;font-weight:800;white-space:nowrap}
.ks-shell-live{color:#71efb6;border-color:#235d49;background:#09271e}
.ks-mobile-menu{display:none;cursor:pointer;width:38px;height:38px;border:1px solid #27465f;
 border-radius:11px;align-items:center;justify-content:center;font-size:1.05rem;background:#0a1826}
.ks-shell-rail{position:fixed;z-index:130;inset:0 auto 0 0;width:var(--ks-rail);padding:20px 14px;
 background:linear-gradient(180deg,#06101b,#081522);border-right:1px solid var(--ks-line);
 transition:transform .22s ease}
.ks-rail-brand{height:52px;display:flex;align-items:center;gap:10px;padding:0 10px 14px;
 font-size:1rem;font-weight:950;border-bottom:1px solid #13283b;margin-bottom:14px}
.ks-rail-brand b{color:#52baff}
.ks-rail-label{padding:10px 10px 7px;color:#557089;font-size:.58rem;font-weight:950;
 letter-spacing:.14em;text-transform:uppercase}
.ks-rail-item{display:flex;align-items:center;gap:10px;min-height:42px;padding:9px 11px;margin:4px 0;
 border-radius:11px;color:#9cb0c3;text-decoration:none;font-size:.76rem;font-weight:800}
.ks-rail-item:hover{background:#0d2133;color:#eef8ff}
.ks-rail-item.is-active{color:#f5fbff;background:linear-gradient(90deg,rgba(39,135,255,.22),rgba(56,224,192,.06));
 border:1px solid rgba(56,167,255,.26);box-shadow:inset 3px 0 0 #38a7ff}
.ks-rail-icon{width:24px;text-align:center;opacity:.9}
.ks-shell-main{min-height:100vh;margin-left:var(--ks-rail);padding:calc(var(--ks-top) + 24px) 28px 40px}
.ks-shell-content{max-width:1440px;margin:0 auto}
.ks-shell-slot{min-height:440px;border:1px dashed rgba(95,148,188,.26);border-radius:18px;
 background:linear-gradient(180deg,rgba(10,24,38,.46),rgba(5,13,22,.28));padding:18px}
.ks-shell-slotnote{display:flex;align-items:center;justify-content:center;min-height:400px;
 color:#55728a;font-size:.72rem;font-weight:800;letter-spacing:.04em}
.ks-shell-overlay{display:none}

@media (max-width:900px){
  :root{--ks-top:64px}
  .ks-shell-topbar{left:0;padding:0 14px;gap:10px}
  .ks-mobile-menu{display:flex}
  .ks-shell-brand .ks-brand-long{display:none}
  .ks-shell-context .ks-desktop-only{display:none}
  .ks-shell-rail{transform:translateX(-103%);box-shadow:24px 0 50px rgba(0,0,0,.36)}
  #ks-shell-menu-toggle:checked ~ .ks-shell-rail{transform:translateX(0)}
  .ks-shell-main{margin-left:0;padding:calc(var(--ks-top) + 16px) 14px 28px}
  .ks-shell-overlay{display:none;position:fixed;z-index:125;inset:0;background:rgba(0,0,0,.54)}
  #ks-shell-menu-toggle:checked ~ .ks-shell-overlay{display:block}
}
@media (max-width:560px){
  .ks-shell-context .ks-shell-pill:not(.ks-shell-live){display:none}
  .ks-shell-topbar{gap:8px}
  .ks-shell-main{padding-left:10px;padding-right:10px}
  .ks-shell-slot{padding:12px;border-radius:15px}
}
</style>
"""

NAV_ITEMS = (
    ("⌂", "Dashboard"),
    ("🏈", "Passing Yards"),
    ("↗", "Rushing Yards"),
    ("◎", "Receiving Yards"),
    ("$", "Moneyline"),
    ("±", "Spread"),
    ("Σ", "Total"),
)

def build_universal_shell(content_html: str = "", *, active_nav: str = "Passing Yards") -> str:
    nav = []
    for icon, label in NAV_ITEMS:
        active = " is-active" if label == active_nav else ""
        nav.append(
            f'<a class="ks-rail-item{active}" href="#" data-nav-label="{escape(label)}">'
            f'<span class="ks-rail-icon">{escape(icon)}</span><span>{escape(label)}</span></a>'
        )
    body = content_html.strip() or (
        '<div class="ks-shell-slotnote" data-step2-content-placeholder="true">'
        'Hub content begins in Step 3 — shell only'
        '</div>'
    )
    return (
        SHELL_CSS
        + '<div class="ks-shell" data-py-layered-shell="true" data-shell-step="2">'
        + '<input id="ks-shell-menu-toggle" type="checkbox" aria-label="Toggle navigation">'
        + '<header class="ks-shell-topbar" data-universal-topbar="true">'
        + '<label class="ks-mobile-menu" for="ks-shell-menu-toggle" aria-label="Open navigation">☰</label>'
        + '<div class="ks-shell-brand"><span class="ks-shell-brandmark">K</span>'
          '<span class="ks-brand-long">Kyre Sports AI</span></div>'
        + '<div class="ks-shell-context">'
          '<span class="ks-shell-pill ks-desktop-only">NFL</span>'
          '<span class="ks-shell-pill ks-desktop-only">Passing Yards</span>'
          '<span class="ks-shell-pill ks-shell-live">● LIVE DATA</span>'
          '</div></header>'
        + '<aside class="ks-shell-rail" data-universal-sidebar="true">'
          '<div class="ks-rail-brand"><span class="ks-shell-brandmark">K</span><span>KYRE <b>SPORTS</b></span></div>'
          '<div class="ks-rail-label">Markets</div>'
        + "".join(nav)
        + '</aside>'
        + '<main class="ks-shell-main" data-universal-main="true">'
          '<div class="ks-shell-content"><section class="ks-shell-slot" data-shell-content-slot="true">'
        + body
        + '</section></div></main>'
        + '<label class="ks-shell-overlay" for="ks-shell-menu-toggle" aria-label="Close navigation"></label>'
        + '</div>'
    )

__all__ = ["STEP", "PROTOTYPE_VERSION", "SHELL_CSS", "NAV_ITEMS", "build_universal_shell"]
