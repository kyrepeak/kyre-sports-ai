"""Page 3 Visual Composition V2 Step 2 — exact hero composition rebuild.

This module owns only the new visible hero composition. It consumes already-resolved
Page 3 identity/matchup values and does not own routing, data fetches, analytics,
market selection, history selection, projections, probabilities, or wagering.
"""
from __future__ import annotations

import html
from typing import Any
import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 VISUAL COMPOSITION V2 • STEP 2 HERO V1"
VISUAL_COMPOSITION_V2_STEP = 2
VISUAL_VERSION = "v1"
PRESENTATION_ONLY = True
DATA_OWNERSHIP_CHANGED = False
INTERACTION_BEHAVIOR_CHANGED = False
CERTIFIED_VIEWPORTS = (390, 768, 1440)
MIN_TOUCH_TARGET_PX = 44

_TEAM_ACCENTS = {
    "ARI":"#97233F","ATL":"#A71930","BAL":"#241773","BUF":"#00338D",
    "CAR":"#0085CA","CHI":"#0B162A","CIN":"#FB4F14","CLE":"#311D00",
    "DAL":"#003594","DEN":"#FB4F14","DET":"#0076B6","GB":"#203731",
    "HOU":"#03202F","IND":"#002C5F","JAX":"#00A5B5","KC":"#E31837",
    "LV":"#A5ACAF","LAC":"#0080C6","LAR":"#003594","MIA":"#008E97",
    "MIN":"#4F2683","NE":"#002244","NO":"#D3BC8D","NYG":"#0B2265",
    "NYJ":"#125740","PHI":"#004C54","PIT":"#FFB612","SEA":"#69BE28",
    "SF":"#AA0000","TB":"#D50A0A","TEN":"#4B92DB","WAS":"#5A1414",
}

def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))

def _accent(team: str) -> str:
    return _TEAM_ACCENTS.get(str(team or "").upper(), "#38BDF8")

def render_visual_composition_v2_hero(
    *,
    player_team: str,
    player_team_name: str,
    player_logo: str,
    opponent: str,
    opponent_name: str,
    opponent_logo: str,
    player_name: str,
    position: str,
    prop_label: str,
    depth_role: str,
    player_id: str,
    gate_state: str,
    headshot: str,
    display_date: str,
    kickoff: str,
    network: str,
    venue: str,
) -> dict[str, Any]:
    team_accent=_accent(player_team)
    opp_accent=_accent(opponent)
    st.markdown(
        f"""
<section class="ks-v2-hero"
 data-prop-page3-visual-composition-v2-step2="{VISUAL_VERSION}"
 data-prop-page3-visual-v2-region="hero"
 data-prop-page3-visual-v2-composition="rebuilt"
 data-prop-page3-visual-v2-presentation-only="true"
 data-prop-page3-visual-v2-data-owner-change="false"
 style="--team-accent:{team_accent};--opp-accent:{opp_accent}">
  <div class="ks-v2-hero-team ks-v2-hero-team-left">
    <div class="ks-v2-team-mark">
      <img src="{_e(player_logo)}" alt="{_e(player_team_name)} logo">
    </div>
    <div class="ks-v2-team-copy">
      <span>{_e(player_team)}</span>
      <strong>{_e(player_team_name)}</strong>
    </div>
  </div>

  <div class="ks-v2-hero-player">
    <div class="ks-v2-portrait-ring">
      <img class="ks-v2-portrait" src="{_e(headshot)}" alt="{_e(player_name)} headshot">
      <img class="ks-v2-portrait-team" src="{_e(player_logo)}" alt="">
    </div>
    <div class="ks-v2-player-copy">
      <span class="ks-v2-position">{_e(position)}</span>
      <h1>{_e(player_name)}</h1>
      <div class="ks-v2-prop">{_e(prop_label)}</div>
      <div class="ks-v2-player-pills">
        <span>{_e(depth_role)}</span>
        <span>ESPN ID {_e(player_id)}</span>
        <span class="ks-v2-analysis-pill">● ANALYSIS {_e(gate_state)}</span>
      </div>
    </div>
  </div>

  <div class="ks-v2-hero-team ks-v2-hero-team-right">
    <div class="ks-v2-team-copy">
      <span>{_e(opponent)}</span>
      <strong>{_e(opponent_name)}</strong>
    </div>
    <div class="ks-v2-team-mark">
      <img src="{_e(opponent_logo)}" alt="{_e(opponent_name)} logo">
    </div>
  </div>

  <div class="ks-v2-game-meta" aria-label="Game information">
    <span>{_e(display_date)}</span><i></i>
    <strong>{_e(kickoff)}</strong><i></i>
    <span>{_e(network)}</span><i></i>
    <span>{_e(venue)}</span>
  </div>
</section>

<style data-prop-page3-visual-composition-v2-step2-css="{VISUAL_VERSION}">
.ks-v2-hero{{
  position:relative;isolation:isolate;overflow:hidden;
  display:grid;grid-template-columns:minmax(155px,.72fr) minmax(410px,1.8fr) minmax(155px,.72fr);
  grid-template-rows:minmax(154px,auto) auto;align-items:center;gap:10px 18px;
  width:100%;max-width:100%;margin:10px 0 14px;padding:18px 22px 13px;
  border:1px solid rgba(94,207,255,.72);border-radius:16px;
  background:
    linear-gradient(90deg,color-mix(in srgb,var(--team-accent) 30%,transparent),transparent 27%,transparent 72%,color-mix(in srgb,var(--opp-accent) 26%,transparent)),
    radial-gradient(circle at 50% -20%,rgba(56,189,248,.12),transparent 43%),
    linear-gradient(180deg,#07111e 0%,#030914 100%);
  box-shadow:0 0 0 1px rgba(56,189,248,.05),0 18px 44px rgba(0,0,0,.28),inset 0 1px 0 rgba(255,255,255,.035);
}}
.ks-v2-hero::before,.ks-v2-hero::after{{
  content:"";position:absolute;top:0;width:34%;height:3px;z-index:2;
}}
.ks-v2-hero::before{{left:0;background:linear-gradient(90deg,var(--team-accent),#38bdf8,transparent)}}
.ks-v2-hero::after{{right:0;background:linear-gradient(270deg,var(--opp-accent),#fb7185,transparent)}}
.ks-v2-hero-team{{display:flex;align-items:center;gap:12px;min-width:0}}
.ks-v2-hero-team-right{{justify-content:flex-end;text-align:right}}
.ks-v2-team-mark{{
  width:82px;height:82px;flex:0 0 82px;border-radius:18px;display:grid;place-items:center;
  border:1px solid color-mix(in srgb,currentColor 35%,transparent);
  background:rgba(5,14,26,.60);box-shadow:inset 0 1px 0 rgba(255,255,255,.04);
}}
.ks-v2-hero-team-left .ks-v2-team-mark{{box-shadow:-3px 0 0 var(--team-accent),inset 0 1px 0 rgba(255,255,255,.04)}}
.ks-v2-hero-team-right .ks-v2-team-mark{{box-shadow:3px 0 0 var(--opp-accent),inset 0 1px 0 rgba(255,255,255,.04)}}
.ks-v2-team-mark img{{width:66px;height:66px;object-fit:contain;filter:drop-shadow(0 7px 13px rgba(0,0,0,.35))}}
.ks-v2-team-copy{{display:flex;flex-direction:column;gap:4px;min-width:0}}
.ks-v2-team-copy span{{color:#a8dcf5;font-size:.68rem;font-weight:900;letter-spacing:.08em}}
.ks-v2-team-copy strong{{color:#f3f8fd;font-size:1.06rem;line-height:1.02}}
.ks-v2-hero-player{{display:grid;grid-template-columns:142px minmax(0,1fr);align-items:center;gap:19px;min-width:0}}
.ks-v2-portrait-ring{{
  position:relative;width:142px;height:142px;border-radius:50%;padding:5px;
  background:conic-gradient(from 190deg,var(--team-accent),#38bdf8 34%,#38bdf8 62%,var(--team-accent));
  box-shadow:0 0 0 5px rgba(56,189,248,.06),0 0 30px rgba(14,165,233,.22);
}}
.ks-v2-portrait{{width:100%;height:100%;border-radius:50%;object-fit:cover;object-position:top center;background:#06101c}}
.ks-v2-portrait-team{{
  position:absolute;right:-5px;bottom:2px;width:43px;height:43px;object-fit:contain;
  padding:4px;border-radius:50%;background:#06101c;border:1px solid rgba(125,211,252,.28);
  filter:drop-shadow(0 4px 8px rgba(0,0,0,.42));
}}
.ks-v2-player-copy{{min-width:0}}
.ks-v2-position{{
  display:inline-flex;padding:4px 9px;border:1px solid rgba(125,211,252,.55);border-radius:999px;
  color:#dff6ff;background:rgba(14,165,233,.09);font-size:.61rem;font-weight:950;letter-spacing:.08em;
}}
.ks-v2-player-copy h1{{
  margin:8px 0 3px;color:#fff;font-size:clamp(1.8rem,3.3vw,2.55rem);line-height:.94;
  letter-spacing:-.045em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}}
.ks-v2-prop{{color:#c1d6e7;font-size:1rem;font-weight:700}}
.ks-v2-player-pills{{display:flex;flex-wrap:wrap;gap:7px;margin-top:12px}}
.ks-v2-player-pills span{{
  padding:6px 10px;border:1px solid rgba(125,211,252,.17);border-radius:999px;
  color:#a9bed1;background:rgba(7,20,35,.64);font-size:.54rem;font-weight:850;
}}
.ks-v2-player-pills .ks-v2-analysis-pill{{color:#b9f6d2;border-color:rgba(52,211,153,.26);background:rgba(16,185,129,.07)}}
.ks-v2-game-meta{{
  grid-column:1/-1;display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:10px;
  padding-top:11px;border-top:1px solid rgba(148,163,184,.10);
  color:#8fa8bf;font-size:.67rem;font-weight:700;
}}
.ks-v2-game-meta strong{{color:#e4f5ff;font-weight:850}}
.ks-v2-game-meta i{{width:1px;height:12px;background:rgba(148,163,184,.24)}}

@media(max-width:900px){{
  .ks-v2-hero{{grid-template-columns:minmax(128px,.65fr) minmax(350px,1.65fr) minmax(128px,.65fr);padding-left:15px;padding-right:15px;gap:10px}}
  .ks-v2-team-mark{{width:68px;height:68px;flex-basis:68px}} .ks-v2-team-mark img{{width:55px;height:55px}}
  .ks-v2-hero-player{{grid-template-columns:116px minmax(0,1fr);gap:14px}}
  .ks-v2-portrait-ring{{width:116px;height:116px}}
}}
@media(max-width:700px){{
  .ks-v2-hero{{grid-template-columns:1fr 1fr;grid-template-rows:auto auto auto;padding:14px 13px 11px}}
  .ks-v2-hero-player{{grid-column:1/-1;grid-row:1;grid-template-columns:92px minmax(0,1fr)}}
  .ks-v2-portrait-ring{{width:92px;height:92px}} .ks-v2-portrait-team{{width:34px;height:34px}}
  .ks-v2-hero-team{{grid-row:2;margin-top:5px}} .ks-v2-hero-team-right{{justify-content:flex-end}}
  .ks-v2-team-mark{{width:56px;height:56px;flex-basis:56px;border-radius:14px}} .ks-v2-team-mark img{{width:44px;height:44px}}
  .ks-v2-team-copy strong{{font-size:.82rem}} .ks-v2-player-copy h1{{font-size:1.65rem}}
  .ks-v2-game-meta{{grid-row:3;gap:7px;font-size:.58rem}}
}}
@media(max-width:430px){{
  .ks-v2-player-pills span{{padding:5px 7px;font-size:.49rem}}
  .ks-v2-game-meta{{justify-content:flex-start}}
  .ks-v2-game-meta i{{display:none}}
}}
@media(prefers-reduced-motion:reduce){{.ks-v2-hero *{{scroll-behavior:auto!important;transition:none!important}}}}
</style>
""",
        unsafe_allow_html=True,
    )
    return {
        "ready": True,
        "version": VISUAL_VERSION,
        "composition": "rebuilt",
        "presentation_only": True,
        "data_ownership_changed": False,
        "interaction_behavior_changed": False,
        "certified_viewports": CERTIFIED_VIEWPORTS,
    }
