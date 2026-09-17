"""CFB Game Total Clean Page V10 — V160 visual-parity presentation shell.

Presentation-only successor to frozen V159. V160 reuses V9's entire Game Total
schedule, evidence, model, distribution, qualification, and Top-5 flow while
substituting only the stylesheet during the frozen render call.
"""
from __future__ import annotations

import streamlit as st

import cfb_game_total_clean_page_v9 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V10 • V160 VISUAL PARITY"
MARKET = prior.MARKET
FROZEN_GAME_TOTAL_HUB = prior.FROZEN_GAME_TOTAL_HUB
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v9"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

ACTIVE_MARKER = "CFB GAME TOTAL • CLEAN PAGE V160 ACTIVE"
V160_REQUIRED_MARKERS = (
    ACTIVE_MARKER,
    "Matchup Foundation",
    "Game Total Answer",
    "Team Evidence",
    "Step 8 • DATA LIMITED",
    "Final Model Summary",
    "Top 5",
)

# The V159 DOM is intentionally preserved. V160 owns presentation only.
_V160_CSS = r"""
<style>
:root{--gt160-green:#58efb2;--gt160-teal:#3fd8ca;--gt160-blue:#6bbcff;--gt160-purple:#b48aff;--gt160-amber:#f0c96a;--gt160-red:#ff796f;--gt160-text:#f4f8fc;--gt160-muted:#8ca2b5}
.gt159-shell{margin:6px 0 12px;padding:10px;border:1px solid rgba(89,148,183,.20);border-radius:20px;background:radial-gradient(circle at 10% 0%,rgba(45,190,170,.08),transparent 34%),radial-gradient(circle at 100% 14%,rgba(151,92,255,.08),transparent 30%),linear-gradient(155deg,#041019,#06131e 48%,#08111d);box-shadow:0 16px 48px rgba(0,0,0,.24),inset 0 1px rgba(255,255,255,.02)}
.gt159-top{border:1px solid rgba(97,160,194,.22);border-left:3px solid var(--gt160-teal);border-right:2px solid rgba(180,138,255,.46);border-radius:16px;background:linear-gradient(118deg,#071c28,#071723 58%,#0d1226);box-shadow:inset 0 1px rgba(255,255,255,.025)}
.gt159-topline{padding:8px 12px 3px;color:#9cb2c5;letter-spacing:.11em}.gt159-topline span:last-child{color:var(--gt160-purple)}
.gt159-matchup{padding:10px 14px 13px;grid-template-columns:1fr 58px 1fr}.gt159-logo,.gt159-logo-fallback{width:64px;height:64px;flex-basis:64px}.gt159-logo{filter:drop-shadow(0 5px 10px rgba(0,0,0,.32))}.gt159-logo-fallback{background:#0d2635;border:1px solid rgba(107,188,255,.16)}.gt159-name{font-size:.82rem;letter-spacing:.01em}.gt159-record{color:#9db1c2}.gt159-conf{background:rgba(42,130,172,.13);border-color:rgba(89,170,209,.22)}.gt159-vs{width:44px;height:44px;background:#0b2230;border-color:rgba(86,151,187,.22);box-shadow:0 0 0 5px rgba(5,17,26,.35)}
.gt159-gamefacts{background:rgba(5,16,25,.38);border-top-color:rgba(86,151,187,.14)}.gt159-fact{padding:8px 11px}
.gt159-total{margin-top:9px;padding:11px;border:1px solid rgba(88,239,178,.23);border-left:3px solid var(--gt160-green);border-right:2px solid rgba(180,138,255,.48);border-radius:16px;background:linear-gradient(133deg,rgba(8,34,40,.96),rgba(7,20,31,.98) 62%,rgba(14,17,38,.98));box-shadow:0 10px 28px rgba(0,0,0,.13)}
.gt159-totalhead{color:#96dfc4;font-size:.36rem;letter-spacing:.12em}.gt159-cert{background:rgba(22,117,82,.15);border-color:rgba(88,239,178,.42);color:var(--gt160-green)}.gt159-totalgrid{margin-top:9px}.gt159-totalmetric{padding:7px 13px}.gt159-totalmetric.hero b{font-size:1.48rem;color:#fff}.gt159-totalmetric.lean b{color:var(--gt160-green)}
.gt159-badges{gap:6px;margin-top:8px}.gt159-badge{background:rgba(10,29,42,.80);border-color:rgba(91,155,190,.20)}.gt159-badge.green{background:rgba(23,112,78,.13);border-color:rgba(88,239,178,.28)}.gt159-badge.purple{background:rgba(89,54,129,.13);border-color:rgba(180,138,255,.28)}
.gt159-section{margin-top:9px;padding:10px;border:1px solid rgba(88,148,183,.20);border-radius:15px;background:linear-gradient(180deg,rgba(7,24,35,.98),rgba(5,17,26,.98))}.gt159-sectionhead b{font-size:.50rem;letter-spacing:.075em}
.gt159-teamgrid{gap:7px}.gt159-teamcard{padding:10px;border:1px solid rgba(87,151,187,.20);border-left:3px solid var(--gt160-red);border-radius:12px;background:linear-gradient(145deg,#091d2a,#0a1a27)}.gt159-teamcard.home{border-left-color:var(--gt160-blue)}.gt159-rec{background:rgba(104,71,185,.15);border-color:rgba(180,138,255,.22);color:#d6c3ff}.gt159-stat{background:#0c2635;border:1px solid rgba(102,168,202,.08)}
.gt159-stepgrid{gap:7px}.gt159-step{border:1px solid rgba(82,145,180,.20);border-left:3px solid var(--gt160-green);border-radius:11px;background:linear-gradient(145deg,#081b28,#091824)}.gt159-step.check,.gt159-step.gated{border-left-color:var(--gt160-amber)}.gt159-step summary{padding:8px 9px}.gt159-num{background:rgba(44,189,130,.14);color:var(--gt160-green)}.gt159-step.check .gt159-num,.gt159-step.gated .gt159-num{background:rgba(171,123,27,.14);color:var(--gt160-amber)}
.gt159-state{background:rgba(22,111,77,.13);border-color:rgba(88,239,178,.28);color:var(--gt160-green)}.gt159-state.check,.gt159-state.gated{background:rgba(112,81,16,.14);border-color:rgba(240,201,106,.30);color:var(--gt160-amber)}.gt159-chip{background:rgba(63,133,174,.10);border-color:rgba(95,162,197,.15);color:#a8d3e9}.gt159-limited{color:var(--gt160-amber);font-weight:850}
.gt159-final{margin-top:9px;padding:10px;border:1px solid rgba(180,138,255,.26);border-radius:15px;background:linear-gradient(140deg,#071a27,#0a1424 60%,#0d1226)}.gt159-finalhead b{color:#decaff;font-size:.48rem}.gt159-finalmetric{background:#09202e;border-color:rgba(88,150,184,.20)}.gt159-finalmetric b{font-size:.62rem}.gt159-note{background:rgba(21,105,74,.13);border-color:rgba(88,239,178,.27)}.gt159-note.concern{background:rgba(105,76,18,.14);border-color:rgba(240,201,106,.28)}
.gt159-top5{margin-top:9px;border:1px dashed rgba(180,138,255,.52);background:linear-gradient(115deg,rgba(91,47,135,.16),rgba(7,21,33,.96) 72%)}.gt159-top5 b{color:#d9c0ff}.gt159-top5 strong{border-color:rgba(180,138,255,.58);color:#dfc3ff;background:rgba(106,58,155,.10)}
.gt160-identity{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:2px 2px 7px;padding:5px 9px;border-radius:999px;border:1px solid rgba(88,239,178,.20);background:rgba(7,27,35,.72);color:#8ea5b8;font-size:.24rem;font-weight:850;letter-spacing:.055em}.gt160-identity b{color:var(--gt160-green);font-weight:950}.gt160-identity span:last-child{color:var(--gt160-purple)}
@media(max-width:760px){.gt159-matchup{grid-template-columns:1fr 36px 1fr;padding:8px 9px}.gt159-logo,.gt159-logo-fallback{width:48px;height:48px;flex-basis:48px}.gt159-name{font-size:.56rem}.gt159-totalgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-teamgrid{grid-template-columns:1fr}.gt159-gamefacts{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-finalgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-finalmetric:first-child{grid-column:1/-1}.gt159-notes{grid-template-columns:1fr}}
@media(max-width:420px){.gt159-shell{padding:7px;border-radius:15px}.gt159-stepgrid{grid-template-columns:1fr}.gt159-statgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-top5{flex-direction:column}.gt160-identity{border-radius:10px;align-items:flex-start;flex-direction:column}}
</style>
"""


def _render_v160_identity() -> None:
    st.markdown(
        '<div class="gt160-identity" data-testid="cfb-game-total-v160-active">'
        f'<b>{ACTIVE_MARKER}</b>'
        '<span>V159 math frozen • V160 presentation only • sportsbook 0.0%</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    # V9 embeds its stylesheet into the final dashboard HTML, so V160 swaps only
    # that presentation constant for the duration of the frozen render pass.
    original_css = prior._V159_CSS
    prior._V159_CSS = _V160_CSS
    try:
        _render_v160_identity()
        return prior.render_game_total_hub(section_header, status_info, team_logo, h)
    finally:
        prior._V159_CSS = original_css


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"V160 Game Total V10 page received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKER",
    "FROZEN_PRESENTATION",
    "MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "V160_REQUIRED_MARKERS",
    "_V160_CSS",
    "render_cfb_hub",
    "render_game_total_hub",
]
