"""CFB Top Picks Step 1 — visual shell only.

This page owns presentation for the new College Football -> Top Picks section.
Step 1 intentionally contains no pick selection, probability, toughness,
matchup-history, or model logic. Those are later steps.
"""
from __future__ import annotations

import streamlit as st

MODEL_VERSION = "CFB TOP PICKS V1 • STEP 1 SHELL"
PAGE_MARKER = "CFB_TOP_PICKS_STEP1_SHELL_ACTIVE"

CSS = r"""
<style>
:root{
  --tp-bg:#03080e;
  --tp-panel:#07111b;
  --tp-panel-2:#091522;
  --tp-line:rgba(109,198,255,.20);
  --tp-line-hot:#119dff;
  --tp-blue:#119dff;
  --tp-blue-soft:#78d3ff;
  --tp-white:#f7fbff;
  --tp-muted:#91a4b8;
}
[data-testid="cfb-top-picks-step1-root"]{
  width:100%;
  max-width:1500px;
  margin:0 auto;
  padding:4px 2px 14px;
  color:var(--tp-white);
}
.tp1-hero{
  display:grid;
  grid-template-columns:minmax(0,1fr) auto;
  gap:24px;
  align-items:end;
  padding:8px 2px 16px;
}
.tp1-title{
  margin:0;
  font-size:clamp(2.35rem,4.1vw,4.35rem);
  line-height:.95;
  font-weight:950;
  letter-spacing:-.055em;
  color:var(--tp-white);
}
.tp1-title span{color:var(--tp-blue)}
.tp1-subtitle{
  margin-top:10px;
  color:#a7bad0;
  font-size:clamp(1rem,1.55vw,1.45rem);
  font-weight:540;
  letter-spacing:-.015em;
}
.tp1-actions{
  display:flex;
  align-items:center;
  justify-content:flex-end;
  gap:14px;
  flex-wrap:wrap;
}
.tp1-segmented{
  display:flex;
  align-items:center;
  gap:0;
  padding:3px;
  border:1px solid var(--tp-line);
  border-radius:13px;
  background:#06101a;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.012);
}
.tp1-chip{
  min-width:112px;
  padding:10px 16px;
  border-radius:10px;
  color:#afc2d7;
  text-align:center;
  font-size:.9rem;
  font-weight:760;
  line-height:1;
}
.tp1-chip.active{
  color:#fff;
  background:linear-gradient(180deg,#1376dc,#0764c7);
  border:1px solid #1db1ff;
  box-shadow:0 0 0 1px rgba(17,157,255,.12),0 0 18px rgba(17,157,255,.20);
}
.tp1-date{
  display:flex;
  align-items:center;
  gap:9px;
  min-height:42px;
  padding:0 14px;
  border:1px solid var(--tp-line);
  border-radius:11px;
  background:#07111d;
  color:#f5f9ff;
  font-weight:760;
  font-size:.9rem;
}
.tp1-date-icon{
  color:var(--tp-blue-soft);
  font-size:1rem;
}
.tp1-board-frame{
  width:100%;
  height:1px;
  margin-top:2px;
  background:linear-gradient(90deg,rgba(17,157,255,.48),rgba(17,157,255,.10),transparent);
}
.tp1-step-marker{
  position:absolute;
  width:1px;
  height:1px;
  overflow:hidden;
  opacity:.001;
  pointer-events:none;
}
@media(max-width:900px){
  .tp1-hero{grid-template-columns:1fr;align-items:start}
  .tp1-actions{justify-content:flex-start}
}
@media(max-width:640px){
  .tp1-actions{display:grid;grid-template-columns:1fr}
  .tp1-segmented{width:100%;overflow:auto}
  .tp1-chip{min-width:102px}
  .tp1-date{width:max-content}
}
</style>
"""


def render_top_picks_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown(
        """
        <section data-testid="cfb-top-picks-step1-root">
          <div class="tp1-step-marker" data-testid="cfb-top-picks-step1-marker">
            CFB_TOP_PICKS_STEP1_SHELL_ACTIVE
          </div>
          <div class="tp1-hero">
            <div>
              <h1 class="tp1-title">Top <span>Picks</span></h1>
              <div class="tp1-subtitle">10 Best Daily College Football Picks</div>
            </div>
            <div class="tp1-actions">
              <div class="tp1-segmented" data-testid="cfb-top-picks-market-tabs">
                <div class="tp1-chip active">Moneyline</div>
                <div class="tp1-chip">Spread</div>
                <div class="tp1-chip">Over/Under</div>
              </div>
              <div class="tp1-date" data-testid="cfb-top-picks-date">
                <span class="tp1-date-icon">▣</span><span>Today</span><span>⌄</span>
              </div>
            </div>
          </div>
          <div class="tp1-board-frame" data-testid="cfb-top-picks-board-frame"></div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if str(market or "").strip() != "Top Picks":
        raise RuntimeError("CFB Top Picks Step 1 owns only the Top Picks route.")
    render_top_picks_page()


__all__ = [
    "CSS",
    "MODEL_VERSION",
    "PAGE_MARKER",
    "render_cfb_hub",
    "render_top_picks_page",
]
