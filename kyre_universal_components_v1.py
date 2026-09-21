"""KYRE Sports AI universal shared components V1.

Step 3 NEW_BUILD artifact. Consumes the frozen Step 1 design tokens and is
intended to render inside the frozen Step 2 universal shell. It is not wired
to production.
"""
from __future__ import annotations

from html import escape
from typing import Iterable

from kyre_universal_theme_v1 import THEME_VERSION

COMPONENT_VERSION = "KYRE UNIVERSAL COMPONENTS V1 • BLACK + GLACIER BLUE"
FOUNDATION_VERSION = THEME_VERSION

_COMPONENT_CSS = r"""
<style data-kyre-universal-components-css="v1">
.kyre-ui-stack{display:grid;gap:var(--kyre-space-4)}
.kyre-ui-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--kyre-space-4)}
.kyre-ui-card{
  min-width:0;padding:var(--kyre-space-5);
  border:1px solid rgba(88,201,255,.18);
  border-radius:var(--kyre-radius-xl);
  background:linear-gradient(145deg,var(--kyre-surface-raised),var(--kyre-surface));
  box-shadow:var(--kyre-shadow-card),var(--kyre-glow-soft);
  color:var(--kyre-text-primary);
}
.kyre-ui-card-eyebrow{
  color:var(--kyre-glacier);font-size:var(--kyre-font-xs);font-weight:900;
  letter-spacing:.12em;text-transform:uppercase
}
.kyre-ui-card-title{margin:5px 0 8px;font-size:var(--kyre-font-lg);font-weight:900}
.kyre-ui-card-body{color:var(--kyre-text-secondary);font-size:var(--kyre-font-sm);line-height:1.55}
.kyre-ui-button{
  min-height:40px;display:inline-flex;align-items:center;justify-content:center;gap:8px;
  border-radius:var(--kyre-radius-md);padding:0 14px;text-decoration:none;
  font-size:var(--kyre-font-sm);font-weight:850;cursor:pointer;
  border:1px solid rgba(88,201,255,.34)
}
.kyre-ui-button.primary{
  color:#001019;background:linear-gradient(135deg,var(--kyre-glacier-soft),var(--kyre-glacier));
  box-shadow:var(--kyre-glow-soft)
}
.kyre-ui-button.secondary{color:var(--kyre-glacier-soft);background:rgba(88,201,255,.08)}
.kyre-ui-button.ghost{color:var(--kyre-text-secondary);background:transparent;border-color:rgba(88,201,255,.15)}
.kyre-ui-badge{
  display:inline-flex;align-items:center;min-height:28px;padding:0 10px;
  border-radius:var(--kyre-radius-pill);font-size:var(--kyre-font-xs);font-weight:850;
  border:1px solid rgba(88,201,255,.24);background:rgba(88,201,255,.08);color:var(--kyre-glacier-soft)
}
.kyre-ui-badge.success{color:var(--kyre-success);border-color:rgba(61,224,161,.28);background:rgba(61,224,161,.07)}
.kyre-ui-badge.warning{color:var(--kyre-warning);border-color:rgba(242,198,109,.28);background:rgba(242,198,109,.07)}
.kyre-ui-badge.danger{color:var(--kyre-danger);border-color:rgba(255,102,122,.28);background:rgba(255,102,122,.07)}
.kyre-ui-tabs{
  display:flex;gap:7px;overflow-x:auto;scrollbar-width:none;padding:3px;
  border-bottom:1px solid rgba(88,201,255,.12)
}
.kyre-ui-tabs::-webkit-scrollbar{display:none}
.kyre-ui-tab{
  flex:0 0 auto;min-height:38px;display:inline-flex;align-items:center;padding:0 12px;
  border-radius:var(--kyre-radius-md);text-decoration:none;color:var(--kyre-text-muted);
  font-size:var(--kyre-font-sm);font-weight:800;border:1px solid transparent
}
.kyre-ui-tab.active{
  color:var(--kyre-glacier-soft);background:rgba(31,174,255,.13);
  border-color:rgba(88,201,255,.30);box-shadow:var(--kyre-glow-soft)
}
.kyre-ui-controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.kyre-ui-control{
  min-height:38px;display:inline-flex;align-items:center;gap:7px;padding:0 11px;
  border-radius:var(--kyre-radius-md);border:1px solid rgba(88,201,255,.16);
  background:#08131d;color:var(--kyre-text-secondary);font-size:var(--kyre-font-sm);font-weight:750
}
.kyre-ui-search{
  min-height:40px;display:flex;align-items:center;gap:8px;padding:0 13px;
  border:1px solid rgba(88,201,255,.18);border-radius:var(--kyre-radius-pill);
  background:#08131d;color:var(--kyre-text-muted);font-size:var(--kyre-font-sm)
}
.kyre-ui-stat{
  min-width:0;padding:14px;border:1px solid rgba(88,201,255,.16);
  border-radius:var(--kyre-radius-lg);background:rgba(255,255,255,.018)
}
.kyre-ui-stat-label{color:var(--kyre-text-muted);font-size:var(--kyre-font-xs);font-weight:850;text-transform:uppercase;letter-spacing:.08em}
.kyre-ui-stat-value{margin-top:5px;color:var(--kyre-text-primary);font-size:1.42rem;font-weight:950}
.kyre-ui-stat-meta{margin-top:3px;color:var(--kyre-glacier);font-size:var(--kyre-font-xs);font-weight:750}
.kyre-ui-accordion{
  border:1px solid rgba(88,201,255,.16);border-radius:var(--kyre-radius-lg);
  background:linear-gradient(145deg,var(--kyre-surface),#08111a);overflow:hidden
}
.kyre-ui-accordion summary{
  min-height:44px;display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:0 14px;cursor:pointer;color:var(--kyre-text-primary);font-size:var(--kyre-font-sm);font-weight:850
}
.kyre-ui-accordion-body{
  padding:0 14px 14px;color:var(--kyre-text-secondary);font-size:var(--kyre-font-sm);line-height:1.55
}
@media(max-width:900px){.kyre-ui-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){
  .kyre-ui-grid{grid-template-columns:1fr}
  .kyre-ui-card{padding:var(--kyre-space-4)}
  .kyre-ui-button{min-height:42px}
  .kyre-ui-control{min-height:40px}
}
</style>
"""

def build_components_css() -> str:
    return _COMPONENT_CSS

def build_card(title: str, body: str, *, eyebrow: str = "") -> str:
    eyebrow_html = f'<div class="kyre-ui-card-eyebrow">{escape(eyebrow)}</div>' if eyebrow else ""
    return (
        '<section class="kyre-ui-card" data-kyre-component="card">'
        + eyebrow_html
        + f'<h3 class="kyre-ui-card-title">{escape(title)}</h3>'
        + f'<div class="kyre-ui-card-body">{body}</div></section>'
    )

def build_button(label: str, *, variant: str = "primary", href: str = "#") -> str:
    if variant not in {"primary", "secondary", "ghost"}:
        raise ValueError("Unsupported button variant")
    return (
        f'<a class="kyre-ui-button {variant}" data-kyre-component="button" '
        f'href="{escape(href)}">{escape(label)}</a>'
    )

def build_badge(label: str, *, tone: str = "glacier") -> str:
    tone_class = "" if tone == "glacier" else tone
    if tone not in {"glacier", "success", "warning", "danger"}:
        raise ValueError("Unsupported badge tone")
    return f'<span class="kyre-ui-badge {tone_class}" data-kyre-component="badge">{escape(label)}</span>'

def build_tabs(labels: Iterable[str], *, active: str) -> str:
    tabs = []
    for label in labels:
        is_active = label.casefold() == active.casefold()
        active_class = " active" if is_active else ""
        tabs.append(
            f'<a class="kyre-ui-tab{active_class}" data-kyre-component="tab" '
            f'aria-selected="{"true" if is_active else "false"}" '
            f'href="#{escape(label.lower().replace(" ", "-"))}">{escape(label)}</a>'
        )
    return '<nav class="kyre-ui-tabs" role="tablist">' + "".join(tabs) + '</nav>'

def build_filter_control(label: str, value: str) -> str:
    return (
        '<span class="kyre-ui-control" data-kyre-component="filter">'
        f'<b>{escape(label)}</b><span>{escape(value)}</span><span>⌄</span></span>'
    )

def build_search_control(placeholder: str = "Search players, teams, or games…") -> str:
    return (
        '<div class="kyre-ui-search" data-kyre-component="search" role="search">'
        f'⌕ <span>{escape(placeholder)}</span></div>'
    )

def build_stat_tile(label: str, value: str, *, meta: str = "") -> str:
    meta_html = f'<div class="kyre-ui-stat-meta">{escape(meta)}</div>' if meta else ""
    return (
        '<div class="kyre-ui-stat" data-kyre-component="stat">'
        f'<div class="kyre-ui-stat-label">{escape(label)}</div>'
        f'<div class="kyre-ui-stat-value">{escape(value)}</div>'
        + meta_html
        + '</div>'
    )

def build_accordion(title: str, body: str, *, open_by_default: bool = False) -> str:
    open_attr = " open" if open_by_default else ""
    return (
        f'<details class="kyre-ui-accordion" data-kyre-component="accordion"{open_attr}>'
        f'<summary>{escape(title)}<span>⌄</span></summary>'
        f'<div class="kyre-ui-accordion-body">{body}</div></details>'
    )

def build_component_showcase() -> str:
    return (
        build_components_css()
        + '<section class="kyre-ui-stack" data-kyre-component-showcase="v1">'
        + build_tabs(("Overview", "Analysis", "Trends", "Deep Data"), active="Overview")
        + '<div class="kyre-ui-controls">'
        + build_search_control("Search quarterbacks…")
        + build_filter_control("Team", "All Teams")
        + build_filter_control("Game", "All Games")
        + build_badge("LIVE DATA", tone="success")
        + '</div>'
        + '<div class="kyre-ui-grid">'
        + build_card("Quarterback Analysis", "Reusable premium content card.", eyebrow="PLAYER")
        + build_card("Monster Projection", "Shared component styling using frozen theme tokens.", eyebrow="MODEL")
        + build_card("Market + Edge", "Consistent spacing, borders, glow, and hierarchy.", eyebrow="MARKET")
        + '</div>'
        + '<div class="kyre-ui-grid">'
        + build_stat_tile("Projection", "287.4", meta="Model")
        + build_stat_tile("Market Line", "279.5", meta="+7.9 edge")
        + build_stat_tile("Confidence", "High", meta="Verified")
        + '</div>'
        + '<div class="kyre-ui-controls">'
        + build_button("Primary Action", variant="primary")
        + build_button("Secondary", variant="secondary")
        + build_button("Ghost", variant="ghost")
        + build_badge("Glacier")
        + build_badge("Warning", tone="warning")
        + '</div>'
        + build_accordion("Methodology & Guardrails", "Reusable collapsible detail row for deeper evidence.")
        + '</section>'
    )

__all__ = [
    "COMPONENT_VERSION",
    "FOUNDATION_VERSION",
    "build_accordion",
    "build_badge",
    "build_button",
    "build_card",
    "build_component_showcase",
    "build_components_css",
    "build_filter_control",
    "build_search_control",
    "build_stat_tile",
    "build_tabs",
]
