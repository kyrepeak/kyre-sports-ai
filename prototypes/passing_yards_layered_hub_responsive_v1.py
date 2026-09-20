"""Passing Yards layered prototype — Step 7 responsive polish.

NEW_BUILD only. Additive CSS layer; frozen Steps 1–6 remain untouched.
"""
from __future__ import annotations

STEP = 7
PROTOTYPE_VERSION = "PASSING YARDS LAYERED HUB • STEP 7 • RESPONSIVE POLISH"

RESPONSIVE_POLISH_CSS = r"""
<style data-py-step7-responsive-css="true">
/* Desktop rhythm */
.ks-shell-content{width:100%}
.ks-py-header,.ks-py-tabs-wrap,.ks-qb-section,.ks-py-preview-section{max-width:100%}
.ks-qb-card,.ks-py-preview-card{min-width:0}
.ks-py-title,.ks-qb-name,.ks-py-preview-copy{overflow-wrap:anywhere}

/* Tablet */
@media (max-width:1024px){
 .ks-shell-main{padding-left:20px;padding-right:20px}
 .ks-py-header{padding:20px}
 .ks-qb-grid{gap:10px}
 .ks-py-preview-grid{gap:10px}
}

/* Mobile */
@media (max-width:760px){
 .ks-shell-main{padding-left:12px;padding-right:12px}
 .ks-shell-slot{padding:10px}
 .ks-py-header{padding:16px}
 .ks-py-controls{align-items:stretch}
 .ks-py-filter,.ks-py-status{min-height:40px}
 .ks-py-tab{min-height:40px}
 .ks-qb-open{min-height:42px}
 .ks-qb-grid,.ks-py-preview-grid{grid-template-columns:1fr}
 .ks-py-preview-link{display:inline-flex;min-height:40px;align-items:center}
}

/* Small phones */
@media (max-width:430px){
 .ks-shell-main{padding-left:8px;padding-right:8px}
 .ks-shell-slot{padding:8px;border-radius:13px}
 .ks-py-header{padding:14px;border-radius:15px}
 .ks-py-title{font-size:1.85rem}
 .ks-py-subtitle{font-size:.76rem}
 .ks-py-controls{gap:6px}
 .ks-py-filter,.ks-py-status{font-size:.56rem;padding:7px 9px}
 .ks-qb-card,.ks-py-preview-card{border-radius:14px}
}

/* Overflow safety */
.ks-py-tabs,.ks-py-controls,.ks-qb-grid,.ks-py-preview-grid{max-width:100%}
.ks-py-tabs{overscroll-behavior-inline:contain}
img,svg,canvas{max-width:100%}
</style>
"""

def build_responsive_polish() -> str:
    return RESPONSONSIVE_POLISH_CSS if False else RESPONSIVE_POLISH_CSS

__all__=["STEP","PROTOTYPE_VERSION","RESPONSIVE_POLISH_CSS","build_responsive_polish"]
