"""KYRE Sports AI universal shell V1.

Step 2 NEW_BUILD artifact. Reuses the frozen Step 1 theme foundation and
provides a responsive website shell only. It is not mounted into production.
"""
from __future__ import annotations

from html import escape

from kyre_universal_theme_v1 import build_universal_theme_css

SHELL_VERSION = "KYRE UNIVERSAL SHELL V1 • BLACK + GLACIER BLUE"

NAV_ITEMS = (
    ("Dashboard", "⌂"),
    ("NFL", "🏈"),
    ("WNBA", "🏀"),
    ("MLB", "⚾"),
    ("Moneyline", "↗"),
    ("Passing Yards", "▥"),
    ("Game Totals", "∑"),
    ("Settings", "⚙"),
)

_SHELL_CSS = r"""
<style data-kyre-universal-shell-css="v1">
.kyre-universe-shell,.kyre-universe-shell *{box-sizing:border-box}
.kyre-universe-shell{
  min-height:100vh;
  background:
    radial-gradient(circle at 85% 0%,rgba(31,174,255,.08),transparent 28%),
    linear-gradient(180deg,var(--kyre-bg-0),var(--kyre-bg-1));
  color:var(--kyre-text-primary);
  display:grid;
  grid-template-columns:248px minmax(0,1fr);
  grid-template-rows:72px minmax(0,1fr);
  grid-template-areas:"sidebar topbar" "sidebar main";
  overflow:hidden;
}
.kyre-universe-sidebar{
  grid-area:sidebar;
  min-width:0;
  border-right:1px solid rgba(88,201,255,.14);
  background:linear-gradient(180deg,#05090e 0%,#07111a 100%);
  padding:20px 14px;
  display:flex;
  flex-direction:column;
  gap:20px;
}
.kyre-universe-brand{
  padding:6px 8px 14px;
  border-bottom:1px solid rgba(88,201,255,.12);
}
.kyre-universe-brandmark{
  font-size:1.05rem;
  font-weight:950;
  letter-spacing:.08em;
  color:var(--kyre-glacier-soft);
}
.kyre-universe-brandmark span{color:var(--kyre-glacier)}
.kyre-universe-brand-sub{
  margin-top:4px;
  color:var(--kyre-text-muted);
  font-size:.63rem;
  font-weight:700;
  letter-spacing:.12em;
  text-transform:uppercase;
}
.kyre-universe-nav{
  display:flex;
  flex-direction:column;
  gap:6px;
}
.kyre-universe-navlink{
  min-height:42px;
  display:flex;
  align-items:center;
  gap:10px;
  padding:0 11px;
  border-radius:var(--kyre-radius-md);
  color:var(--kyre-text-secondary);
  text-decoration:none;
  font-size:.8rem;
  font-weight:750;
  border:1px solid transparent;
}
.kyre-universe-navlink:hover{
  color:var(--kyre-text-primary);
  background:rgba(88,201,255,.06);
  border-color:rgba(88,201,255,.14);
}
.kyre-universe-navlink.active{
  color:var(--kyre-glacier-soft);
  background:linear-gradient(90deg,rgba(31,174,255,.18),rgba(31,174,255,.06));
  border-color:rgba(88,201,255,.34);
  box-shadow:inset 3px 0 0 var(--kyre-glacier),var(--kyre-glow-soft);
}
.kyre-universe-navicon{
  width:24px;
  height:24px;
  display:grid;
  place-items:center;
  border-radius:8px;
  background:rgba(88,201,255,.06);
  color:var(--kyre-glacier);
}
.kyre-universe-sidebar-foot{
  margin-top:auto;
  padding:12px;
  border:1px solid rgba(88,201,255,.16);
  border-radius:var(--kyre-radius-lg);
  background:linear-gradient(145deg,rgba(88,201,255,.08),rgba(255,255,255,.01));
}
.kyre-universe-sidebar-foot b{font-size:.74rem}
.kyre-universe-sidebar-foot p{
  margin:5px 0 0;
  color:var(--kyre-text-muted);
  font-size:.62rem;
  line-height:1.45;
}
.kyre-universe-topbar{
  grid-area:topbar;
  min-width:0;
  border-bottom:1px solid rgba(88,201,255,.12);
  background:rgba(3,6,10,.86);
  backdrop-filter:blur(16px);
  display:flex;
  align-items:center;
  gap:12px;
  padding:0 20px;
}
.kyre-universe-search{
  flex:1 1 420px;
  max-width:560px;
  min-height:40px;
  border:1px solid rgba(88,201,255,.16);
  border-radius:var(--kyre-radius-pill);
  background:#08131d;
  color:var(--kyre-text-muted);
  padding:0 15px;
  display:flex;
  align-items:center;
  gap:9px;
  font-size:.72rem;
}
.kyre-universe-topcontrols{
  margin-left:auto;
  display:flex;
  align-items:center;
  gap:8px;
}
.kyre-universe-chip{
  min-height:36px;
  display:inline-flex;
  align-items:center;
  gap:7px;
  padding:0 11px;
  border:1px solid rgba(88,201,255,.16);
  border-radius:var(--kyre-radius-pill);
  background:#091722;
  color:var(--kyre-text-secondary);
  font-size:.68rem;
  font-weight:800;
}
.kyre-universe-chip.live{
  color:var(--kyre-success);
  border-color:rgba(61,224,161,.30);
  background:rgba(61,224,161,.07);
}
.kyre-universe-main{
  grid-area:main;
  min-width:0;
  overflow:auto;
  padding:24px;
}
.kyre-universe-main-inner{
  width:min(1440px,100%);
  margin:0 auto;
}
.kyre-universe-content-slot{
  min-width:0;
  width:100%;
}
.kyre-universe-mobile-brand{display:none}

@media(max-width:980px){
  .kyre-universe-shell{
    grid-template-columns:84px minmax(0,1fr);
  }
  .kyre-universe-sidebar{padding:18px 10px}
  .kyre-universe-brandmark{font-size:.78rem}
  .kyre-universe-brand-sub,
  .kyre-universe-navlabel,
  .kyre-universe-sidebar-foot{display:none}
  .kyre-universe-navlink{
    justify-content:center;
    padding:0;
  }
  .kyre-universe-main{padding:18px}
}
@media(max-width:720px){
  .kyre-universe-shell{
    display:block;
    min-height:100vh;
    overflow:visible;
  }
  .kyre-universe-sidebar{display:none}
  .kyre-universe-topbar{
    position:sticky;
    top:0;
    z-index:20;
    min-height:64px;
    padding:10px 12px;
    flex-wrap:wrap;
  }
  .kyre-universe-mobile-brand{
    display:block;
    font-weight:950;
    color:var(--kyre-glacier-soft);
    letter-spacing:.04em;
  }
  .kyre-universe-search{
    order:3;
    flex-basis:100%;
    max-width:none;
    min-height:38px;
  }
  .kyre-universe-topcontrols{margin-left:auto}
  .kyre-universe-chip.optional{display:none}
  .kyre-universe-main{padding:14px 12px 22px}
}
@media(max-width:430px){
  .kyre-universe-topbar{gap:8px}
  .kyre-universe-chip{padding:0 9px;font-size:.61rem}
  .kyre-universe-main{padding:10px}
}
</style>
"""

def _nav_html(active_nav: str) -> str:
    rows = []
    for label, icon in NAV_ITEMS:
        active = " active" if label.casefold() == active_nav.casefold() else ""
        rows.append(
            f'<a class="kyre-universe-navlink{active}" href="#{escape(label.lower().replace(" ", "-"))}" '
            f'data-kyre-nav="{escape(label)}" aria-current="{"page" if active else "false"}">'
            f'<span class="kyre-universe-navicon">{escape(icon)}</span>'
            f'<span class="kyre-universe-navlabel">{escape(label)}</span></a>'
        )
    return "".join(rows)

def build_universal_shell(
    content_html: str = "",
    *,
    active_nav: str = "Dashboard",
    slate_label: str = "Current Slate",
    sport_label: str = "NFL",
) -> str:
    """Wrap page content in the reusable universal website shell."""
    return (
        build_universal_theme_css()
        + _SHELL_CSS
        + '<div class="kyre-universe-shell" data-kyre-universal-shell="v1">'
        + '<aside class="kyre-universe-sidebar" data-kyre-shell-sidebar="true">'
        + '<div class="kyre-universe-brand">'
        + '<div class="kyre-universe-brandmark">KYRE <span>SPORTS AI</span></div>'
        + '<div class="kyre-universe-brand-sub">Projection Intelligence</div></div>'
        + '<nav class="kyre-universe-nav" aria-label="Primary">'
        + _nav_html(active_nav)
        + '</nav>'
        + '<div class="kyre-universe-sidebar-foot"><b>Glacier Intelligence</b>'
        + '<p>Fast reads. Clean evidence. Smarter game-day decisions.</p></div>'
        + '</aside>'
        + '<header class="kyre-universe-topbar" data-kyre-shell-topbar="true">'
        + '<div class="kyre-universe-mobile-brand">KYRE</div>'
        + '<div class="kyre-universe-search" role="search">⌕ '
        + '<span>Search players, teams, or games…</span></div>'
        + '<div class="kyre-universe-topcontrols">'
        + f'<span class="kyre-universe-chip optional">◷ {escape(slate_label)}</span>'
        + f'<span class="kyre-universe-chip">{escape(sport_label)}</span>'
        + '<span class="kyre-universe-chip live">● LIVE DATA</span>'
        + '</div></header>'
        + '<main class="kyre-universe-main" data-kyre-shell-main="true">'
        + '<div class="kyre-universe-main-inner">'
        + '<div class="kyre-universe-content-slot" data-kyre-content-slot="true">'
        + content_html
        + '</div></div></main></div>'
    )

__all__ = [
    "NAV_ITEMS",
    "SHELL_VERSION",
    "build_universal_shell",
]
