"""CFB Top Picks Step 3 — live ranked board.

Uses the frozen Step-2 card visual system with real Top Picks engine output.
Step 4 owns accordion Why/History/Benefits content; Step 5 owns final visual parity.
"""
from __future__ import annotations

import streamlit as st

import cfb_top_picks_engine_v1 as engine
import cfb_top_picks_page_v2 as prior

MODEL_VERSION = "CFB TOP PICKS V3 • STEP 3 LIVE RANKING"
PAGE_MARKER = "CFB_TOP_PICKS_STEP3_LIVE_RANKING_ACTIVE"
LAYOUT_PREVIEW = False

CSS = prior.CSS + r"""
<style>
.tp3-live{
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  margin:0 2px 10px;padding:8px 11px;border:1px solid rgba(109,198,255,.13);
  border-radius:10px;background:rgba(6,16,26,.76);color:#8fa6ba;
  font-size:.72rem;font-weight:760
}
.tp3-live strong{color:#78d3ff}
.tp3-empty{padding:18px;border:1px solid rgba(255,193,7,.22);border-radius:12px;background:#10151d;color:#d6e0ea}
</style>
"""


def render_top_picks_page() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    with st.spinner("Building the verified College Football Top 10..."):
        picks, diag = engine.build_top_picks(limit=10)

    slate_day = str(diag.get("slate_date") or "Today")
    cards = "".join(prior._card(row) for row in picks)

    st.markdown(
        f"""
        <section data-testid="cfb-top-picks-step3-root">
          <div class="tp2-step-marker" data-testid="cfb-top-picks-step1-marker">CFB_TOP_PICKS_STEP1_SHELL_ACTIVE</div>
          <div class="tp2-step-marker" data-testid="cfb-top-picks-step2-marker">CFB_TOP_PICKS_STEP2_COMPACT_CARDS_ACTIVE</div>
          <div class="tp2-step-marker" data-testid="cfb-top-picks-step3-marker">{PAGE_MARKER}</div>
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
                <span class="tp1-date-icon">▣</span><span>{slate_day}</span><span>⌄</span>
              </div>
            </div>
          </div>
          <div class="tp3-live" data-testid="cfb-top-picks-live-status">
            <span><strong>LIVE MODEL BOARD</strong> • {int(diag.get("games_analyzed") or 0)} games analyzed • {len(picks)} picks ranked</span>
            <span>Market thresholds: 0.0% projection weight</span>
          </div>
          <div class="tp2-board" data-testid="cfb-top-picks-card-board">{cards}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    if not picks:
        st.markdown(
            '<div class="tp3-empty">No verified Top Picks are available for the current seven-day CFB slate window. Nothing was fabricated.</div>',
            unsafe_allow_html=True,
        )


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if str(market or "").strip() != "Top Picks":
        raise RuntimeError("CFB Top Picks Step 3 owns only the Top Picks route.")
    render_top_picks_page()


__all__ = ["CSS","LAYOUT_PREVIEW","MODEL_VERSION","PAGE_MARKER","render_cfb_hub","render_top_picks_page"]
