"""Passing Yards layered prototype — Step 3 polished page header.

NEW_BUILD only. Imports the frozen Step 2 shell without modifying it.
"""
from __future__ import annotations
from html import escape

STEP = 3
PROTOTYPE_VERSION = "PASSING YARDS LAYERED HUB • STEP 3 • HEADER"

HEADER_CSS = r"""
<style data-py-step3-header-css="true">
.ks-py-header{position:relative;overflow:hidden;border:1px solid rgba(76,165,234,.30);
 border-radius:22px;padding:24px;background:
 linear-gradient(135deg,rgba(12,31,49,.96),rgba(7,19,31,.96) 58%,rgba(8,39,48,.88));
 box-shadow:0 22px 70px rgba(0,0,0,.26),inset 0 1px 0 rgba(255,255,255,.035)}
.ks-py-header:after{content:"";position:absolute;width:320px;height:320px;right:-110px;top:-170px;
 border-radius:50%;background:radial-gradient(circle,rgba(47,165,255,.22),transparent 67%);pointer-events:none}
.ks-py-header-main{position:relative;z-index:1;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:26px;align-items:start}
.ks-py-eyebrow{display:flex;align-items:center;gap:8px;color:#5bc1ff;font-size:.64rem;font-weight:950;
 letter-spacing:.15em;text-transform:uppercase;margin-bottom:9px}
.ks-py-dot{width:7px;height:7px;border-radius:50%;background:#39e2bd;box-shadow:0 0 14px rgba(57,226,189,.74)}
.ks-py-title{margin:0;color:#f8fbff;font-size:clamp(1.9rem,4vw,3.35rem);line-height:.98;letter-spacing:-.055em;font-weight:950}
.ks-py-subtitle{max-width:760px;margin:12px 0 0;color:#9eb4c8;font-size:.88rem;line-height:1.55;font-weight:650}
.ks-py-slate{min-width:232px;border:1px solid #1d435f;border-radius:16px;padding:14px 16px;
 background:linear-gradient(180deg,rgba(9,28,44,.95),rgba(7,22,35,.95))}
.ks-py-slate-label{color:#67849d;font-size:.56rem;font-weight:950;letter-spacing:.14em;text-transform:uppercase}
.ks-py-slate-date{margin-top:5px;color:#eef8ff;font-size:.95rem;font-weight:900;letter-spacing:-.02em}
.ks-py-slate-context{margin-top:3px;color:#6d8aa3;font-size:.68rem;font-weight:750}
.ks-py-controls{position:relative;z-index:1;display:flex;align-items:center;gap:8px;flex-wrap:wrap;
 margin-top:22px;padding-top:16px;border-top:1px solid rgba(69,129,170,.22)}
.ks-py-filter{appearance:none;border:1px solid #244963;background:#091b2a;color:#9eb8cd;border-radius:999px;
 padding:8px 12px;font-size:.66rem;font-weight:900;letter-spacing:.01em}
.ks-py-filter.is-active{color:#f5fbff;border-color:#2b8dde;background:linear-gradient(180deg,#123c60,#0c2b46);
 box-shadow:0 0 0 1px rgba(53,163,255,.07),0 8px 22px rgba(0,0,0,.18)}
.ks-py-status{margin-left:auto;display:flex;align-items:center;gap:7px;border:1px solid #255b4c;
 background:#0a281f;color:#7af0bb;border-radius:999px;padding:8px 11px;font-size:.62rem;font-weight:950;
 letter-spacing:.05em;text-transform:uppercase}
.ks-py-status-dot{width:7px;height:7px;border-radius:50%;background:#50e3a4;box-shadow:0 0 12px rgba(80,227,164,.72)}
@media (max-width:760px){
 .ks-py-header{padding:18px;border-radius:18px}
 .ks-py-header-main{grid-template-columns:1fr;gap:16px}
 .ks-py-slate{min-width:0;width:100%;display:grid;grid-template-columns:1fr auto;column-gap:12px;align-items:end}
 .ks-py-slate-context{grid-column:1/-1}
 .ks-py-controls{margin-top:16px;padding-top:14px}
 .ks-py-status{margin-left:0}
}
@media (max-width:460px){
 .ks-py-header{padding:15px}
 .ks-py-title{font-size:2rem}
 .ks-py-subtitle{font-size:.78rem}
 .ks-py-controls{gap:6px}
 .ks-py-filter,.ks-py-status{padding:7px 9px;font-size:.58rem}
}
</style>
"""

def build_passing_yards_header(
    *,
    slate_label: str = "NFL • PASSING YARDS",
    date_label: str = "CURRENT SLATE",
    slate_context: str = "Quarterback projection board",
    status_label: str = "Live data",
) -> str:
    return (
        HEADER_CSS
        + '<section class="ks-py-header" data-py-step3-header="true">'
        + '<div class="ks-py-header-main">'
        + '<div><div class="ks-py-eyebrow"><span class="ks-py-dot"></span>NFL PLAYER PROPS</div>'
        + '<h1 class="ks-py-title">Passing Yards</h1>'
        + '<p class="ks-py-subtitle">Quarterback projection hub built for fast matchup scanning, '
          'clear model context, and a clean path from slate to player detail.</p></div>'
        + '<aside class="ks-py-slate" data-py-slate-area="true">'
        + f'<div class="ks-py-slate-label">{escape(slate_label)}</div>'
        + f'<div class="ks-py-slate-date">{escape(date_label)}</div>'
        + f'<div class="ks-py-slate-context">{escape(slate_context)}</div></aside></div>'
        + '<div class="ks-py-controls" data-py-header-controls="true">'
        + '<button class="ks-py-filter is-active" type="button">ALL QBs</button>'
        + '<button class="ks-py-filter" type="button">HOME</button>'
        + '<button class="ks-py-filter" type="button">AWAY</button>'
        + '<button class="ks-py-filter" type="button">AVAILABLE</button>'
        + f'<span class="ks-py-status"><span class="ks-py-status-dot"></span>{escape(status_label)}</span>'
        + '</div></section>'
    )

__all__ = ["STEP", "PROTOTYPE_VERSION", "HEADER_CSS", "build_passing_yards_header"]
