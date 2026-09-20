"""Passing Yards layered prototype — Step 6 hub preview content.

NEW_BUILD only. Adds compact Why, Trends, and Market previews with drill-down
actions while leaving full breakdown content for later screens.
"""
from __future__ import annotations
from dataclasses import dataclass
from html import escape

STEP = 6
PROTOTYPE_VERSION = "PASSING YARDS LAYERED HUB • STEP 6 • HUB PREVIEWS"

PREVIEW_CSS = r"""
<style data-py-step6-preview-css="true">
.ks-py-preview-section{margin-top:18px}
.ks-py-preview-head{display:flex;align-items:end;justify-content:space-between;gap:12px;margin:0 2px 11px}
.ks-py-preview-kicker{color:#53b9f8;font-size:.58rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase}
.ks-py-preview-title{margin:3px 0 0;color:#eef8ff;font-size:1rem;font-weight:950;letter-spacing:-.025em}
.ks-py-preview-note{color:#5f7e95;font-size:.59rem;font-weight:800;text-align:right}
.ks-py-preview-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:11px}
.ks-py-preview-card{position:relative;display:flex;flex-direction:column;min-height:180px;overflow:hidden;
 border:1px solid #173d58;border-radius:17px;padding:15px;background:
 linear-gradient(145deg,rgba(10,28,43,.98),rgba(7,18,29,.98));box-shadow:0 14px 34px rgba(0,0,0,.2)}
.ks-py-preview-card:after{content:"";position:absolute;width:130px;height:130px;right:-64px;top:-62px;
 border-radius:50%;background:radial-gradient(circle,rgba(47,157,235,.14),transparent 68%);pointer-events:none}
.ks-py-preview-icon{width:34px;height:34px;border:1px solid #255777;border-radius:11px;display:grid;place-items:center;
 background:#0b263c;color:#8fd5ff;font-size:.92rem}
.ks-py-preview-label{margin-top:11px;color:#f2f9ff;font-size:.84rem;font-weight:950}
.ks-py-preview-copy{margin-top:6px;color:#819db2;font-size:.68rem;line-height:1.5;font-weight:720}
.ks-py-preview-chip{display:inline-flex;align-items:center;width:max-content;max-width:100%;margin-top:10px;
 border:1px solid #244c67;background:#0a2032;color:#7fb8dc;border-radius:999px;padding:6px 8px;
 font-size:.54rem;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ks-py-preview-action{margin-top:auto;padding-top:14px}
.ks-py-preview-link{display:inline-flex;align-items:center;gap:5px;color:#71c8ff;text-decoration:none;
 font-size:.61rem;font-weight:950}
.ks-py-preview-link:hover{text-decoration:underline}
.ks-py-preview-link:focus-visible{outline:2px solid #55bdff;outline-offset:3px;border-radius:5px}
@media (max-width:900px){
 .ks-py-preview-grid{grid-template-columns:1fr}
 .ks-py-preview-card{min-height:0}
}
@media (max-width:520px){
 .ks-py-preview-head{align-items:start;flex-direction:column}
 .ks-py-preview-note{text-align:left}
 .ks-py-preview-card{padding:14px;border-radius:15px}
}
</style>
"""

@dataclass(frozen=True)
class HubPreview:
    kind: str
    title: str
    summary: str
    chip: str
    target: str
    icon: str

def default_previews() -> tuple[HubPreview, ...]:
    return (
        HubPreview(
            kind="why",
            title="Why it matters",
            summary="Fast read on the main matchup and context drivers before opening the full player analysis.",
            chip="Driver snapshot",
            target="py-why",
            icon="✦",
        ),
        HubPreview(
            kind="trends",
            title="Trend snapshot",
            summary="Recent-form direction and usage context in a compact scan instead of a wall of game logs.",
            chip="Recent form",
            target="py-trends",
            icon="↗",
        ),
        HubPreview(
            kind="market",
            title="Market snapshot",
            summary="Quick line and market-context preview with deeper pricing detail kept on the full breakdown.",
            chip="Line context",
            target="py-market",
            icon="$",
        ),
    )

def _render_preview(card: HubPreview) -> str:
    return (
        f'<article class="ks-py-preview-card" id="{escape(card.target)}" '
        f'data-py-step6-preview="{escape(card.kind)}">'
        + f'<div class="ks-py-preview-icon" aria-hidden="true">{escape(card.icon)}</div>'
        + f'<div class="ks-py-preview-label">{escape(card.title)}</div>'
        + f'<div class="ks-py-preview-copy">{escape(card.summary)}</div>'
        + f'<div class="ks-py-preview-chip">{escape(card.chip)}</div>'
        + '<div class="ks-py-preview-action">'
        + f'<a class="ks-py-preview-link" href="#full-{escape(card.kind)}" '
          f'aria-label="Open full {escape(card.kind)} breakdown">Open Full Breakdown →</a>'
        + '</div></article>'
    )

def build_hub_previews(cards: tuple[HubPreview, ...] | list[HubPreview] | None = None) -> str:
    items = tuple(cards) if cards is not None else default_previews()
    return (
        PREVIEW_CSS
        + '<section class="ks-py-preview-section" id="py-overview" data-py-step6-preview-section="true">'
        + '<div class="ks-py-preview-head"><div>'
        + '<div class="ks-py-preview-kicker">QUICK READ</div>'
        + '<h2 class="ks-py-preview-title">Hub previews</h2></div>'
        + '<div class="ks-py-preview-note">Scan here • open deeper only when needed</div></div>'
        + '<div class="ks-py-preview-grid">'
        + "".join(_render_preview(card) for card in items)
        + '</div></section>'
    )

__all__=["STEP","PROTOTYPE_VERSION","PREVIEW_CSS","HubPreview","default_previews","build_hub_previews"]
