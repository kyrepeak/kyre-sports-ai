"""CFB Game Total Clean Page V10 — V160 live Monster visual-parity shell.

Presentation-only successor to frozen V159. V160 reuses V9's entire Game Total
schedule, evidence, model, distribution, qualification, and Top-5 flow while
layering a complete Monster Sports Intelligence presentation over the frozen
V159 DOM. No projection, probability, qualification, ranking, API, or
sportsbook-influence behavior is changed.
"""
from __future__ import annotations

import streamlit as st

import cfb_game_total_clean_page_v9 as prior

MODEL_VERSION = "CFB GAME TOTAL CLEAN PAGE V10 • V160 LIVE MONSTER VISUAL PARITY"
MARKET = prior.MARKET
FROZEN_GAME_TOTAL_HUB = prior.FROZEN_GAME_TOTAL_HUB
FROZEN_PRESENTATION = "cfb_game_total_clean_page_v9"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

ACTIVE_MARKER = "CFB GAME TOTAL • CLEAN PAGE V160 ACTIVE"
BRAND_MARKER = "MONSTER SPORTS INTELLIGENCE"
V160_REQUIRED_MARKERS = (
    ACTIVE_MARKER,
    BRAND_MARKER,
    "Matchup Foundation",
    "Game Total Answer",
    "Team Evidence",
    "Step 8 • DATA LIMITED",
    "Final Model Summary",
    "Top 5",
)

# IMPORTANT: V159 owns the complete structural stylesheet. Earlier V160 builds
# accidentally replaced it with a partial override sheet, dropping critical
# display:grid / display:flex / display:block rules. Compose instead of replace:
# keep the frozen V159 structure intact, then append V160 presentation overrides.
_V160_OVERRIDES = r"""

/* ---------- V160 Monster Sports Intelligence presentation layer ---------- */
html,body,[data-testid="stAppViewContainer"]{background:#020a13!important}
[data-testid="stAppViewContainer"]{background:radial-gradient(circle at 20% 0%,rgba(0,226,185,.045),transparent 28%),radial-gradient(circle at 90% 12%,rgba(150,73,255,.05),transparent 30%),#020a13!important}
[data-testid="stHeader"]{background:rgba(2,10,19,.96)!important}
[data-testid="stDecoration"]{display:none!important}
.block-container{max-width:1180px!important;padding-top:.8rem!important;padding-left:1rem!important;padding-right:1rem!important}

.gt160-masthead{max-width:1160px;margin:0 auto 10px;padding:10px 14px;display:flex;align-items:center;justify-content:space-between;gap:18px;border-bottom:1px solid rgba(85,155,194,.18);background:linear-gradient(90deg,rgba(4,18,31,.98),rgba(3,12,24,.98));border-radius:14px 14px 8px 8px;box-shadow:0 12px 32px rgba(0,0,0,.22)}
.gt160-brand{display:flex;align-items:center;gap:9px;min-width:220px}.gt160-mark{width:34px;height:34px;display:grid;place-items:center;border-radius:7px;background:linear-gradient(145deg,#59f2b6,#1bbcae);color:#03221e;font-size:1rem;font-weight:1000;clip-path:polygon(0 0,50% 38%,100% 0,100% 100%,0 100%)}.gt160-brandcopy b{display:block;color:#f6fbff;font-size:.83rem;line-height:1;font-weight:1000;letter-spacing:.04em}.gt160-brandcopy span{display:block;margin-top:3px;color:#9fc8e6;font-size:.28rem;font-weight:850;letter-spacing:.12em}
.gt160-nav{display:flex;align-items:center;justify-content:center;gap:24px;flex:1}.gt160-nav span{color:#9cb0c2;font-size:.37rem;font-weight:900;letter-spacing:.07em}.gt160-nav .active{color:var(--gt160-green);position:relative}.gt160-nav .active:after{content:"";position:absolute;left:0;right:0;bottom:-7px;height:2px;border-radius:999px;background:var(--gt160-green);box-shadow:0 0 9px rgba(88,239,178,.65)}.gt160-actions{display:flex;align-items:center;gap:12px;color:#e5eef6;font-size:.68rem}.gt160-actions span{width:28px;height:28px;display:grid;place-items:center;border-left:1px solid rgba(113,161,191,.16)}

.gt160-identity{max-width:1160px;display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 auto 6px;padding:3px 8px;border-radius:999px;border:1px solid rgba(88,239,178,.14);background:rgba(7,27,35,.50);color:#7890a4;font-size:.19rem;font-weight:850;letter-spacing:.055em}.gt160-identity b{color:#72dcb5;font-weight:950}.gt160-identity span:last-child{color:#a88bd6}

.gt159-shell{max-width:1160px;margin:0 auto 14px;padding:8px;border:1px solid rgba(77,143,181,.18);border-radius:18px;background:radial-gradient(circle at 8% 0%,rgba(45,190,170,.055),transparent 33%),radial-gradient(circle at 100% 15%,rgba(151,92,255,.055),transparent 30%),linear-gradient(155deg,#03101a,#06131e 48%,#08111d);box-shadow:0 16px 48px rgba(0,0,0,.28),inset 0 1px rgba(255,255,255,.018)}
.gt159-top{border:1px solid rgba(80,156,196,.28);border-left:2px solid var(--gt160-teal);border-right:2px solid rgba(180,138,255,.58);border-radius:14px;background:linear-gradient(118deg,#061b28,#071723 58%,#0c1126);box-shadow:0 0 22px rgba(63,216,202,.035),inset 0 1px rgba(255,255,255,.025)}
.gt159-topline{padding:7px 11px 3px;color:#a0b5c7;font-size:.31rem;letter-spacing:.105em}.gt159-topline span:last-child{color:var(--gt160-purple)}
.gt159-matchup{grid-template-columns:1fr 46px 1fr;gap:7px;padding:7px 12px 10px}.gt159-team{gap:9px}.gt159-logo,.gt159-logo-fallback{width:54px;height:54px;flex-basis:54px}.gt159-logo{filter:drop-shadow(0 5px 10px rgba(0,0,0,.32))}.gt159-logo-fallback{background:#0d2635;border:1px solid rgba(107,188,255,.16)}.gt159-name{font-size:.72rem;letter-spacing:.005em}.gt159-record{font-size:.31rem;color:#9db1c2}.gt159-conf{margin-top:4px;padding:2px 7px;font-size:.22rem;background:rgba(42,130,172,.13);border-color:rgba(89,170,209,.24)}.gt159-vs{width:36px;height:36px;background:#0b2230;border-color:rgba(86,151,187,.24);box-shadow:0 0 0 4px rgba(5,17,26,.32);font-size:.31rem}
.gt159-gamefacts{grid-template-columns:repeat(4,minmax(0,1fr));background:rgba(5,16,25,.42);border-top-color:rgba(86,151,187,.16)}.gt159-fact{position:relative;padding:7px 8px 7px 28px}.gt159-fact:before{position:absolute;left:9px;top:9px;color:#9fc6df;font-size:.44rem;line-height:1}.gt159-fact:nth-child(1):before{content:"▣"}.gt159-fact:nth-child(2):before{content:"☀";color:var(--gt160-amber)}.gt159-fact:nth-child(3):before{content:"≋";color:#9bd7ff}.gt159-fact:nth-child(4):before{content:"▦";color:#c6d9ea}.gt159-fact b{font-size:.31rem}.gt159-fact span{font-size:.21rem}

.gt159-total{margin-top:8px;padding:9px;border:1px solid rgba(88,239,178,.30);border-left:3px solid var(--gt160-green);border-right:2px solid rgba(180,138,255,.58);border-radius:14px;background:linear-gradient(133deg,rgba(6,32,38,.98),rgba(6,19,31,.99) 62%,rgba(13,16,38,.99));box-shadow:0 0 28px rgba(88,239,178,.045),0 10px 28px rgba(0,0,0,.14)}
.gt159-totalhead{color:#a6e7d0;font-size:.31rem;letter-spacing:.115em}.gt159-cert{padding:3px 8px;background:rgba(22,117,82,.16);border-color:rgba(88,239,178,.50);color:var(--gt160-green);font-size:.23rem}.gt159-totalgrid{grid-template-columns:repeat(4,minmax(0,1fr));margin-top:7px}.gt159-totalmetric{position:relative;padding:6px 10px;min-height:66px;display:flex;flex-direction:column;justify-content:center}.gt159-totalmetric span{font-size:.23rem}.gt159-totalmetric b{font-size:.72rem;margin-top:3px}.gt159-totalmetric.hero b{font-size:1.38rem;color:#fff}.gt159-totalmetric.lean b{font-size:.65rem;color:var(--gt160-green)}.gt159-totalmetric small{font-size:.20rem}.gt159-totalmetric:last-child{padding-right:55px}.gt159-totalmetric:last-child:after{content:"";position:absolute;right:10px;top:50%;transform:translateY(-50%);width:35px;height:35px;border-radius:50%;background:radial-gradient(circle at center,#071925 55%,transparent 57%),conic-gradient(var(--gt160-green) 0 73%,rgba(69,116,143,.23) 73% 100%);box-shadow:0 0 12px rgba(88,239,178,.20)}.gt159-grade{margin-top:3px;padding:2px 7px;font-size:.21rem}
.gt159-badges{grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:7px}.gt159-badge{padding:7px 9px;border-radius:9px;background:rgba(9,29,42,.88);border-color:rgba(91,155,190,.22);font-size:.25rem;line-height:1.42}.gt159-badge strong{font-size:.27rem}.gt159-badge.green{background:rgba(23,112,78,.14);border-color:rgba(88,239,178,.32)}.gt159-badge.purple{background:rgba(89,54,129,.15);border-color:rgba(180,138,255,.34)}

.gt159-section{margin-top:8px;padding:8px;border:1px solid rgba(88,148,183,.22);border-radius:13px;background:linear-gradient(180deg,rgba(6,23,34,.99),rgba(4,16,25,.99))}.gt159-sectionhead{margin-bottom:6px}.gt159-sectionhead b{font-size:.42rem;letter-spacing:.07em}.gt159-sectionhead span{font-size:.22rem}
.gt159-teamgrid{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.gt159-teamcard{padding:7px;border:1px solid rgba(87,151,187,.22);border-left:3px solid var(--gt160-red);border-radius:10px;background:linear-gradient(145deg,#081c29,#091925)}.gt159-teamcard.home{border-left-color:var(--gt160-blue)}.gt159-teamcardtop b{font-size:.38rem}.gt159-rec{padding:2px 7px;font-size:.21rem;background:rgba(104,71,185,.15);border-color:rgba(180,138,255,.25);color:#d6c3ff}.gt159-statgrid{grid-template-columns:repeat(4,minmax(0,1fr));gap:4px;margin-top:5px}.gt159-stat{padding:5px;border-radius:7px;background:#0b2635;border:1px solid rgba(102,168,202,.08)}.gt159-stat b{font-size:.34rem}.gt159-stat span{font-size:.17rem}

.gt159-stepgrid{grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.gt159-step{border:1px solid rgba(82,145,180,.22);border-left:3px solid var(--gt160-green);border-radius:9px;background:linear-gradient(145deg,#071b28,#081824)}.gt159-step.check,.gt159-step.gated{border-left-color:var(--gt160-amber)}.gt159-step summary{grid-template-columns:25px minmax(0,1fr) auto;gap:6px;padding:6px 7px}.gt159-num{width:24px;height:24px;border-radius:7px;background:rgba(44,189,130,.15);color:var(--gt160-green);font-size:.30rem}.gt159-stepcopy b{font-size:.32rem}.gt159-stepcopy span{font-size:.19rem}.gt159-state{padding:2px 6px;font-size:.17rem;background:rgba(22,111,77,.14);border-color:rgba(88,239,178,.32);color:var(--gt160-green)}.gt159-state.check,.gt159-state.gated{background:rgba(112,81,16,.15);border-color:rgba(240,201,106,.34);color:var(--gt160-amber)}.gt159-stepbody{padding:0 7px 7px 38px;font-size:.20rem}.gt159-chip{font-size:.18rem}.gt159-limited{color:var(--gt160-amber);font-weight:900}

.gt159-final{margin-top:8px;padding:8px;border:1px solid rgba(180,138,255,.32);border-radius:13px;background:linear-gradient(140deg,#061a27,#091424 60%,#0c1126)}.gt159-finalhead b{color:#decaff;font-size:.40rem}.gt159-finalhead span{font-size:.21rem}.gt159-finalgrid{grid-template-columns:repeat(5,minmax(0,1fr));gap:5px;margin-top:6px}.gt159-finalmetric{padding:7px 4px;border-radius:8px;background:#08202e;border-color:rgba(88,150,184,.22)}.gt159-finalmetric b{font-size:.53rem}.gt159-finalmetric span{font-size:.17rem}.gt159-notes{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-top:6px}.gt159-note{padding:7px 9px;font-size:.22rem;line-height:1.45;background:linear-gradient(130deg,rgba(12,90,64,.36),rgba(7,34,31,.72));border-color:rgba(88,239,178,.35)}.gt159-note.concern{background:linear-gradient(130deg,rgba(99,72,15,.30),rgba(32,30,17,.68));border-color:rgba(240,201,106,.38)}.gt159-note b{font-size:.25rem}
.gt159-top5{margin-top:8px;padding:8px 10px;border:1px dashed rgba(180,138,255,.60);border-radius:12px;background:linear-gradient(115deg,rgba(91,47,135,.18),rgba(6,20,32,.98) 72%)}.gt159-top5 b{color:#d9c0ff;font-size:.35rem}.gt159-top5 span{font-size:.21rem}.gt159-top5 strong{padding:4px 10px;border-color:rgba(180,138,255,.68);color:#ead2ff;background:rgba(106,58,155,.15);box-shadow:0 0 14px rgba(153,75,255,.12);font-size:.21rem}

@media(max-width:760px){
  .block-container{padding-left:.55rem!important;padding-right:.55rem!important}
  .gt160-masthead{padding:8px 9px;gap:8px}.gt160-brand{min-width:0}.gt160-mark{width:28px;height:28px}.gt160-brandcopy b{font-size:.63rem}.gt160-brandcopy span{font-size:.20rem}.gt160-nav{gap:12px}.gt160-nav span{font-size:.28rem}.gt160-actions{gap:5px}.gt160-actions span{width:21px;height:21px;font-size:.52rem}
  .gt159-shell{padding:6px;border-radius:14px}.gt159-matchup{grid-template-columns:1fr 32px 1fr;padding:6px 7px 8px;gap:4px}.gt159-logo,.gt159-logo-fallback{width:42px;height:42px;flex-basis:42px}.gt159-team{gap:5px}.gt159-name{font-size:.53rem}.gt159-record{font-size:.25rem}.gt159-conf{font-size:.18rem}.gt159-vs{width:28px;height:28px;font-size:.25rem}
  .gt159-gamefacts{grid-template-columns:repeat(4,minmax(0,1fr))}.gt159-fact{padding:6px 4px 6px 20px}.gt159-fact:before{left:6px;top:8px;font-size:.34rem}.gt159-fact b{font-size:.24rem}.gt159-fact span{font-size:.17rem}
  .gt159-totalgrid{grid-template-columns:repeat(4,minmax(0,1fr))}.gt159-totalmetric{padding:5px 6px;min-height:58px}.gt159-totalmetric.hero b{font-size:1.03rem}.gt159-totalmetric b{font-size:.55rem}.gt159-totalmetric.lean b{font-size:.46rem}.gt159-totalmetric span{font-size:.18rem}.gt159-totalmetric small{font-size:.16rem}.gt159-totalmetric:last-child{padding-right:39px}.gt159-totalmetric:last-child:after{right:5px;width:27px;height:27px}.gt159-grade{font-size:.16rem;padding:2px 5px}
  .gt159-badges{grid-template-columns:repeat(3,minmax(0,1fr))}.gt159-badge{padding:5px;font-size:.19rem}.gt159-badge strong{font-size:.20rem}
  .gt159-teamgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-teamcard{padding:6px}.gt159-statgrid{grid-template-columns:repeat(4,minmax(0,1fr))}.gt159-stat{padding:4px 3px}.gt159-stat b{font-size:.28rem}.gt159-stat span{font-size:.14rem}
  .gt159-stepgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-step summary{grid-template-columns:22px minmax(0,1fr) auto;gap:4px;padding:5px}.gt159-num{width:21px;height:21px;font-size:.25rem}.gt159-stepcopy b{font-size:.26rem}.gt159-stepcopy span{font-size:.16rem}.gt159-state{font-size:.14rem;padding:2px 4px}.gt159-stepbody{padding:0 5px 6px 31px;font-size:.17rem}
  .gt159-finalgrid{grid-template-columns:repeat(5,minmax(0,1fr))}.gt159-finalmetric{padding:5px 2px}.gt159-finalmetric b{font-size:.42rem}.gt159-finalmetric span{font-size:.14rem}.gt159-notes{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-note{font-size:.18rem;padding:6px}.gt159-top5{padding:7px 8px}.gt159-top5 b{font-size:.29rem}.gt159-top5 span,.gt159-top5 strong{font-size:.17rem}
}
@media(max-width:520px){
  .gt160-nav{gap:8px}.gt160-nav span:nth-child(3),.gt160-nav span:nth-child(4),.gt160-nav span:nth-child(5){display:none}.gt160-brandcopy span{display:none}
  .gt159-topline{font-size:.22rem}.gt159-gamefacts{grid-template-columns:repeat(4,minmax(0,1fr))}.gt159-totalgrid{grid-template-columns:repeat(4,minmax(0,1fr))}.gt159-badges{grid-template-columns:repeat(3,minmax(0,1fr))}.gt159-teamgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-stepgrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gt159-finalgrid{grid-template-columns:repeat(5,minmax(0,1fr))}.gt159-notes{grid-template-columns:repeat(2,minmax(0,1fr))}
  .gt159-sectionhead{align-items:flex-start}.gt159-sectionhead span{max-width:48%}.gt159-stepcopy span{max-width:100%}.gt159-totalmetric:last-child:after{display:none}.gt159-totalmetric:last-child{padding-right:4px}
}
"""

_V160_CSS = prior._V159_CSS.replace("</style>", _V160_OVERRIDES + "\n</style>")


def _render_v160_masthead() -> None:
    st.markdown(
        f'''
<div class="gt160-masthead" data-testid="cfb-game-total-monster-masthead" aria-label="{BRAND_MARKER}">
  <div class="gt160-brand"><div class="gt160-mark">M</div><div class="gt160-brandcopy"><b>MONSTER</b><span>SPORTS INTELLIGENCE</span></div></div>
  <div class="gt160-nav" aria-label="Sports navigation"><span>NFL</span><span class="active">CFB</span><span>MLB</span><span>NBA</span><span>NHL</span></div>
  <div class="gt160-actions" aria-hidden="true"><span>⌕</span><span>☰</span></div>
</div>''',
        unsafe_allow_html=True,
    )


def _render_v160_identity() -> None:
    st.markdown(
        '<div class="gt160-identity" data-testid="cfb-game-total-v160-active">'
        f'<b>{ACTIVE_MARKER}</b>'
        '<span>V159 math frozen • V160 presentation only • sportsbook 0.0%</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    # V9 owns all real values and the full dashboard DOM. V160 swaps in a
    # composed stylesheet only; no model/data/ranking call is altered here.
    original_css = prior._V159_CSS
    prior._V159_CSS = _V160_CSS
    try:
        _render_v160_masthead()
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
    "BRAND_MARKER",
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
