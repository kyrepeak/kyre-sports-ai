"""Passing Yards layered prototype — Step 4 quarterback identity cards.

NEW_BUILD only. Builds on frozen Steps 2–3 without changing production.
"""
from __future__ import annotations
from dataclasses import dataclass
from html import escape

STEP = 4
PROTOTYPE_VERSION = "PASSING YARDS LAYERED HUB • STEP 4 • QB CARDS"

QB_CARDS_CSS = r"""
<style data-py-step4-qb-cards-css="true">
.ks-qb-section{margin-top:18px}
.ks-qb-section-head{display:flex;align-items:end;justify-content:space-between;gap:12px;margin:0 2px 12px}
.ks-qb-section-kicker{color:#4dafff;font-size:.59rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase}
.ks-qb-section-title{margin:3px 0 0;color:#eff8ff;font-size:1.05rem;font-weight:950;letter-spacing:-.025em}
.ks-qb-count{border:1px solid #1d405a;background:#081927;color:#7f9db5;border-radius:999px;
 padding:6px 9px;font-size:.59rem;font-weight:900}
.ks-qb-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.ks-qb-card{position:relative;overflow:hidden;border:1px solid #173e59;border-radius:18px;padding:16px;
 background:linear-gradient(145deg,rgba(10,27,42,.98),rgba(7,18,29,.98));
 box-shadow:0 14px 34px rgba(0,0,0,.21);transition:transform .16s ease,border-color .16s ease}
.ks-qb-card:hover{transform:translateY(-1px);border-color:#276b96}
.ks-qb-card:before{content:"";position:absolute;inset:0 auto 0 0;width:3px;background:linear-gradient(#37a8ff,#3be0c0)}
.ks-qb-top{display:flex;align-items:center;gap:12px}
.ks-qb-avatar{width:48px;height:48px;flex:0 0 48px;border-radius:15px;display:grid;place-items:center;
 border:1px solid #285b7e;background:linear-gradient(145deg,#103b5e,#0a2439);color:#dff4ff;
 font-size:.9rem;font-weight:950;box-shadow:inset 0 1px 0 rgba(255,255,255,.045)}
.ks-qb-identity{min-width:0;flex:1}
.ks-qb-name{color:#f5fbff;font-size:1rem;font-weight:950;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ks-qb-meta{margin-top:4px;color:#7896ad;font-size:.66rem;font-weight:850;letter-spacing:.025em}
.ks-qb-status{flex:0 0 auto;border:1px solid #245747;background:#09271e;color:#6beab3;
 border-radius:999px;padding:6px 9px;font-size:.56rem;font-weight:950;text-transform:uppercase;letter-spacing:.05em}
.ks-qb-status.is-watch{border-color:#5a4d28;background:#2a220b;color:#f3d873}
.ks-qb-matchup{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:end;
 margin-top:15px;padding-top:13px;border-top:1px solid rgba(59,112,149,.22)}
.ks-qb-match-label{color:#57748b;font-size:.55rem;font-weight:950;letter-spacing:.13em;text-transform:uppercase}
.ks-qb-match{margin-top:3px;color:#dfeef8;font-size:.78rem;font-weight:900}
.ks-qb-kick{margin-top:3px;color:#6f8ca3;font-size:.62rem;font-weight:750}
.ks-qb-open{appearance:none;border:1px solid #235b83;background:#0d2f49;color:#8ed3ff;border-radius:10px;
 padding:8px 10px;font-size:.61rem;font-weight:950;white-space:nowrap}
.ks-qb-open:focus-visible{outline:2px solid #53bdff;outline-offset:2px}
@media (max-width:760px){
 .ks-qb-grid{grid-template-columns:1fr}
 .ks-qb-card{padding:15px;border-radius:16px}
}
@media (max-width:420px){
 .ks-qb-top{align-items:flex-start}
 .ks-qb-avatar{width:43px;height:43px;flex-basis:43px;border-radius:13px}
 .ks-qb-status{padding:5px 7px;font-size:.52rem}
 .ks-qb-matchup{grid-template-columns:1fr}
 .ks-qb-open{width:100%}
}
</style>
"""

@dataclass(frozen=True)
class QBCard:
    name: str
    team: str
    opponent: str
    side: str
    kickoff: str
    status: str = "Available"

def _initials(name: str) -> str:
    parts = [p for p in name.replace(".", " ").split() if p]
    return "".join(p[0].upper() for p in parts[:2]) or "QB"

def _card_html(card: QBCard) -> str:
    status_text = escape(card.status)
    status_class = "" if card.status.strip().lower() in {"available", "active", "confirmed"} else " is-watch"
    side = escape(card.side.upper())
    return (
        '<article class="ks-qb-card" data-qb-card="true">'
        + '<div class="ks-qb-top">'
        + f'<div class="ks-qb-avatar" aria-hidden="true">{escape(_initials(card.name))}</div>'
        + '<div class="ks-qb-identity" data-qb-identity="true">'
        + f'<div class="ks-qb-name">{escape(card.name)}</div>'
        + f'<div class="ks-qb-meta">{escape(card.team)} • QB • {side}</div></div>'
        + f'<span class="ks-qb-status{status_class}" data-qb-status="true">{status_text}</span></div>'
        + '<div class="ks-qb-matchup" data-qb-matchup="true"><div>'
        + '<div class="ks-qb-match-label">MATCHUP</div>'
        + f'<div class="ks-qb-match">{escape(card.team)} vs {escape(card.opponent)}</div>'
        + f'<div class="ks-qb-kick">{escape(card.kickoff)}</div></div>'
        + f'<button class="ks-qb-open" type="button" aria-label="Open {escape(card.name)} details">View QB →</button>'
        + '</div></article>'
    )

def build_qb_cards(cards: list[QBCard] | tuple[QBCard, ...]) -> str:
    rendered = "".join(_card_html(card) for card in cards)
    return (
        QB_CARDS_CSS
        + '<section class="ks-qb-section" data-py-step4-qb-section="true">'
        + '<div class="ks-qb-section-head"><div>'
        + '<div class="ks-qb-section-kicker">SLATE PLAYERS</div>'
        + '<h2 class="ks-qb-section-title">Quarterbacks</h2></div>'
        + f'<span class="ks-qb-count">{len(cards)} QBs</span></div>'
        + f'<div class="ks-qb-grid" data-qb-card-grid="true">{rendered}</div></section>'
    )

__all__ = ["STEP", "PROTOTYPE_VERSION", "QB_CARDS_CSS", "QBCard", "build_qb_cards"]
