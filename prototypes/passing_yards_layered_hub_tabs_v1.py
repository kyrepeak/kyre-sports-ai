"""Passing Yards layered prototype — Step 5 layered navigation tabs.

NEW_BUILD only. Builds on frozen Steps 1–4 and does not add Step 6 preview content.
"""
from __future__ import annotations
from html import escape

STEP = 5
PROTOTYPE_VERSION = "PASSING YARDS LAYERED HUB • STEP 5 • LAYERED TABS"

TABS = (
    ("Overview", "py-overview"),
    ("Why", "py-why"),
    ("Matchup", "py-matchup"),
    ("Trends", "py-trends"),
    ("Market", "py-market"),
    ("Deep Data", "py-deep-data"),
)

TABS_CSS = r"""
<style data-py-step5-tabs-css="true">
.ks-py-tabs-wrap{position:relative;margin-top:16px}
.ks-py-tabs-label{margin:0 2px 7px;color:#55778f;font-size:.56rem;font-weight:950;
 letter-spacing:.14em;text-transform:uppercase}
.ks-py-tabs{display:flex;gap:7px;overflow-x:auto;overscroll-behavior-x:contain;
 scrollbar-width:none;padding:3px 2px 5px;scroll-snap-type:x proximity}
.ks-py-tabs::-webkit-scrollbar{display:none}
.ks-py-tab{scroll-snap-align:start;flex:0 0 auto;display:inline-flex;align-items:center;justify-content:center;
 min-height:36px;padding:8px 12px;border:1px solid #1c405a;border-radius:11px;background:#081927;
 color:#7f9db4;text-decoration:none;font-size:.64rem;font-weight:900;letter-spacing:.01em;
 transition:border-color .15s ease,background .15s ease,color .15s ease,transform .15s ease}
.ks-py-tab:hover{color:#dff3ff;border-color:#2d6d96;background:#0b2134;transform:translateY(-1px)}
.ks-py-tab.is-active{color:#f4fbff;border-color:#318fd0;
 background:linear-gradient(180deg,#103a5b,#0b2941);box-shadow:0 8px 24px rgba(0,0,0,.18)}
.ks-py-tab:focus-visible{outline:2px solid #55bdff;outline-offset:2px}
.ks-py-tabs-hint{display:none;color:#57748a;font-size:.54rem;font-weight:800;margin-top:4px}
@media (max-width:760px){
 .ks-py-tabs-wrap{margin-top:13px}
 .ks-py-tabs{margin-left:-2px;margin-right:-2px;padding-bottom:7px}
 .ks-py-tab{min-height:34px;padding:7px 10px;font-size:.61rem}
 .ks-py-tabs-hint{display:block}
}
</style>
"""

def build_layered_tabs(*, active: str = "Overview") -> str:
    valid = {label for label, _ in TABS}
    chosen = active if active in valid else "Overview"
    parts = []
    for label, anchor in TABS:
        is_active = label == chosen
        cls = "ks-py-tab is-active" if is_active else "ks-py-tab"
        selected = "true" if is_active else "false"
        parts.append(
            f'<a class="{cls}" role="tab" aria-selected="{selected}" '
            f'data-py-layer-tab="{escape(label)}" href="#{escape(anchor)}">{escape(label)}</a>'
        )
    return (
        TABS_CSS
        + '<nav class="ks-py-tabs-wrap" data-py-step5-tabs="true" aria-label="Passing Yards analysis sections">'
        + '<div class="ks-py-tabs-label">Analysis layers</div>'
        + '<div class="ks-py-tabs" role="tablist">'
        + "".join(parts)
        + '</div><div class="ks-py-tabs-hint">Swipe to explore analysis layers →</div></nav>'
    )

__all__ = ["STEP","PROTOTYPE_VERSION","TABS","TABS_CSS","build_layered_tabs"]
