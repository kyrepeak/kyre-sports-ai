"""NFL Prop Analytics Page 3 Visual Composition V2 Step 2 — Hero rebuild.

This is a real additive composition rebuild, not a skin over the old hero.
The frozen V1 hero remains in the DOM for backward contract verification but is
visually retired once this V2 hero is present. No navigation, data ownership,
market, history, slider, projection, probability, recommendation, or wager
semantics are changed.
"""
from __future__ import annotations

import html as html_lib
from typing import Any

import streamlit as st

MODEL_VERSION = "NFL PROP ANALYTICS PAGE 3 VISUAL COMPOSITION V2 • STEP 2 HERO V1"
VISUAL_SERIES = "v2"
VISUAL_STEP = 2
VISUAL_VERSION = "v1"
PRESENTATION_ONLY = True
REAL_COMPOSITION_REBUILD = True
FROZEN_PAGE3_BEHAVIOR_PROTECTED = True
FROZEN_V1_REDESIGN_PROTECTED = True
DATA_OWNERSHIP_CHANGED = False
INTERACTION_BEHAVIOR_CHANGED = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MIN_TOUCH_TARGET_PX = 44
CERTIFIED_VIEWPORTS = (390, 768, 1440)

# Authentic NFL primary/secondary accents used only as localized hero lighting.
NFL_TEAM_COLORS: dict[str, tuple[str, str]] = {
    "ARI": ("#97233F", "#000000"), "ATL": ("#A71930", "#000000"),
    "BAL": ("#241773", "#9E7C0C"), "BUF": ("#00338D", "#C60C30"),
    "CAR": ("#0085CA", "#101820"), "CHI": ("#0B162A", "#C83803"),
    "CIN": ("#FB4F14", "#000000"), "CLE": ("#311D00", "#FF3C00"),
    "DAL": ("#003594", "#869397"), "DEN": ("#FB4F14", "#002244"),
    "DET": ("#0076B6", "#B0B7BC"), "GB": ("#203731", "#FFB612"),
    "HOU": ("#03202F", "#A71930"), "IND": ("#002C5F", "#A2AAAD"),
    "JAX": ("#006778", "#D7A22A"), "KC": ("#E31837", "#FFB81C"),
    "LV": ("#000000", "#A5ACAF"), "LAC": ("#0080C6", "#FFC20E"),
    "LAR": ("#003594", "#FFA300"), "MIA": ("#008E97", "#FC4C02"),
    "MIN": ("#4F2683", "#FFC62F"), "NE": ("#002244", "#C60C30"),
    "NO": ("#D3BC8D", "#101820"), "NYG": ("#0B2265", "#A71930"),
    "NYJ": ("#125740", "#000000"), "PHI": ("#004C54", "#A5ACAF"),
    "PIT": ("#FFB612", "#101820"), "SEA": ("#002244", "#69BE28"),
    "SF": ("#AA0000", "#B3995D"), "TB": ("#D50A0A", "#34302B"),
    "TEN": ("#0C2340", "#4B92DB"), "WAS": ("#5A1414", "#FFB612"),
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _accent(team: str) -> tuple[str, str]:
    return NFL_TEAM_COLORS.get(_text(team).upper(), ("#0EA5E9", "#38BDF8"))


def render_visual_v2_hero(
    *,
    player_team: Any,
    player_team_name: Any,
    player_logo: Any,
    opponent: Any,
    opponent_name: Any,
    opponent_logo: Any,
    player_name: Any,
    position: Any,
    market_label: Any,
    headshot: Any,
    depth_role: Any,
    player_id: Any,
    gate_state: Any,
    display_date: Any,
    kickoff: Any,
    network: Any,
    venue: Any,
) -> dict[str, Any]:
    team = _text(player_team).upper()
    opp = _text(opponent).upper()
    team_primary, team_secondary = _accent(team)
    opp_primary, opp_secondary = _accent(opp)
    status_class = "open" if _text(gate_state).upper() == "OPEN" else "closed"

    st.markdown(
        f"""
<section class="ks-v2-hero"
 data-page3-visual-v2-step2="{VISUAL_VERSION}"
 data-page3-visual-v2-step2-state="ready"
 data-page3-visual-v2-step2-real-composition="true"
 data-page3-visual-v2-step2-player-team="{html_lib.escape(team)}"
 data-page3-visual-v2-step2-opponent="{html_lib.escape(opp)}"
 data-page3-visual-v2-step2-player-id="{html_lib.escape(_text(player_id))}"
 style="--v2-team-primary:{team_primary};--v2-team-secondary:{team_secondary};--v2-opp-primary:{opp_primary};--v2-opp-secondary:{opp_secondary};">
  <div class="ks-v2-hero-team ks-v2-hero-team-home">
    <div class="ks-v2-team-watermark"></div>
    <img src="{html_lib.escape(_text(player_logo))}" alt="{html_lib.escape(_text(player_team_name))} logo">
    <div>
      <span>{html_lib.escape(team)}</span>
      <strong>{html_lib.escape(_text(player_team_name))}</strong>
    </div>
  </div>

  <div class="ks-v2-hero-player">
    <div class="ks-v2-headshot-ring">
      <img class="ks-v2-headshot" src="{html_lib.escape(_text(headshot))}" alt="{html_lib.escape(_text(player_name))} headshot">
      <img class="ks-v2-headshot-team" src="{html_lib.escape(_text(player_logo))}" alt="">
    </div>
    <div class="ks-v2-player-copy">
      <div class="ks-v2-player-title">
        <span class="ks-v2-position">{html_lib.escape(_text(position))}</span>
        <h1>{html_lib.escape(_text(player_name))}</h1>
      </div>
      <p>{html_lib.escape(_text(market_label))}</p>
      <div class="ks-v2-player-pills">
        <span>{html_lib.escape(_text(depth_role))}</span>
        <span>ESPN ID {html_lib.escape(_text(player_id))}</span>
        <span class="ks-v2-gate ks-v2-gate-{status_class}"><i></i> ANALYSIS {html_lib.escape(_text(gate_state).upper())}</span>
      </div>
    </div>
  </div>

  <div class="ks-v2-hero-team ks-v2-hero-team-away">
    <div class="ks-v2-team-watermark"></div>
    <div>
      <span>{html_lib.escape(opp)}</span>
      <strong>{html_lib.escape(_text(opponent_name))}</strong>
    </div>
    <img src="{html_lib.escape(_text(opponent_logo))}" alt="{html_lib.escape(_text(opponent_name))} logo">
  </div>

  <div class="ks-v2-game-meta" aria-label="Game details">
    <span>{html_lib.escape(_text(display_date))}</span>
    <b aria-hidden="true">|</b>
    <span>{html_lib.escape(_text(kickoff))}</span>
    <b aria-hidden="true">|</b>
    <span>{html_lib.escape(_text(network))}</span>
    <b aria-hidden="true">|</b>
    <span>{html_lib.escape(_text(venue))}</span>
  </div>
</section>

<style data-page3-visual-v2-step2-css="{VISUAL_VERSION}">
/* V2 is a real replacement composition. Keep the frozen V1 hero in DOM only. */
.ks-pa3-hero{{display:none!important}}

.ks-v2-hero{{
  position:relative;isolation:isolate;overflow:hidden;
  display:grid;
  grid-template-columns:minmax(190px,.82fr) minmax(430px,1.8fr) minmax(190px,.82fr);
  grid-template-areas:"home player away" "meta meta meta";
  align-items:center;gap:18px;
  width:100%;min-width:0;min-height:228px;
  margin:6px 0 14px;padding:18px 20px 14px;
  border:1px solid rgba(125,211,252,.58);
  border-radius:16px;
  background:
    radial-gradient(circle at 15% 15%,color-mix(in srgb,var(--v2-team-primary) 38%,transparent),transparent 31%),
    radial-gradient(circle at 88% 16%,color-mix(in srgb,var(--v2-opp-primary) 34%,transparent),transparent 31%),
    linear-gradient(135deg,#061425 0%,#03101d 46%,#061321 100%);
  box-shadow:0 18px 46px rgba(0,0,0,.34),inset 0 1px 0 rgba(255,255,255,.04),0 0 0 1px rgba(56,189,248,.08);
}}
.ks-v2-hero::before{{
  content:"";position:absolute;z-index:-1;inset:0;
  background:
    linear-gradient(90deg,color-mix(in srgb,var(--v2-team-primary) 56%,transparent),transparent 30%),
    linear-gradient(270deg,color-mix(in srgb,var(--v2-opp-primary) 48%,transparent),transparent 30%);
  opacity:.34;
}}
.ks-v2-hero::after{{
  content:"";position:absolute;left:0;right:0;top:0;height:2px;
  background:linear-gradient(90deg,var(--v2-team-secondary),#38bdf8 48%,var(--v2-opp-secondary));
  box-shadow:0 0 18px rgba(56,189,248,.5);
}}

.ks-v2-hero-team{{
  position:relative;min-width:0;min-height:138px;
  display:flex;align-items:center;gap:13px;
  padding:15px 12px;
}}
.ks-v2-hero-team-home{{grid-area:home;justify-content:flex-start}}
.ks-v2-hero-team-away{{grid-area:away;justify-content:flex-end;text-align:right}}
.ks-v2-hero-team img:not(.ks-v2-team-watermark){{
  position:relative;z-index:2;width:82px;height:82px;flex:0 0 82px;object-fit:contain;
  filter:drop-shadow(0 10px 14px rgba(0,0,0,.42));
}}
.ks-v2-hero-team>div:not(.ks-v2-team-watermark){{
  position:relative;z-index:2;display:flex;flex-direction:column;gap:4px;min-width:0;
}}
.ks-v2-hero-team span{{color:#d6e8f5;font-size:.76rem;font-weight:850;letter-spacing:.04em}}
.ks-v2-hero-team strong{{color:#fff;font-size:1.15rem;line-height:1.04;letter-spacing:-.02em}}
.ks-v2-team-watermark{{
  position:absolute;inset:4px;border-radius:18px;opacity:.16;
  background:
    linear-gradient(135deg,rgba(255,255,255,.12),transparent 46%),
    repeating-linear-gradient(135deg,rgba(255,255,255,.06) 0 14px,transparent 14px 28px);
}}
.ks-v2-hero-team-home .ks-v2-team-watermark{{border-left:3px solid var(--v2-team-primary)}}
.ks-v2-hero-team-away .ks-v2-team-watermark{{border-right:3px solid var(--v2-opp-primary)}}

.ks-v2-hero-player{{
  grid-area:player;display:grid;grid-template-columns:156px minmax(0,1fr);
  align-items:center;gap:18px;min-width:0;
}}
.ks-v2-headshot-ring{{
  position:relative;width:148px;height:148px;border-radius:50%;padding:5px;
  background:conic-gradient(from 20deg,#38bdf8,var(--v2-team-secondary),#0ea5e9,#38bdf8);
  box-shadow:0 0 0 5px rgba(14,165,233,.08),0 0 34px rgba(14,165,233,.34);
}}
.ks-v2-headshot{{
  width:100%;height:100%;object-fit:cover;object-position:top center;border-radius:50%;
  background:#07111d;border:4px solid #061421;
}}
.ks-v2-headshot-team{{
  position:absolute;right:-8px;bottom:2px;width:47px;height:47px;object-fit:contain;
  filter:drop-shadow(0 6px 8px rgba(0,0,0,.55));
}}
.ks-v2-player-copy{{min-width:0}}
.ks-v2-player-title{{display:flex;align-items:center;gap:10px;min-width:0;flex-wrap:wrap}}
.ks-v2-position{{
  order:2;padding:5px 9px;border:1px solid rgba(125,211,252,.48);border-radius:999px;
  color:#d7f4ff;background:rgba(14,165,233,.09);font-size:.62rem;font-weight:950;letter-spacing:.07em;
}}
.ks-v2-player-title h1{{
  order:1;flex:1 1 auto;min-width:0;margin:0;color:#fff;
  font-size:clamp(2rem,4.2vw,3.15rem);line-height:.94;letter-spacing:-.045em;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;
}}
.ks-v2-player-copy>p{{margin:7px 0 0;color:#d2e6f4;font-size:1.08rem;letter-spacing:-.01em}}
.ks-v2-player-pills{{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-top:13px}}
.ks-v2-player-pills span{{
  display:inline-flex;align-items:center;gap:6px;min-height:28px;padding:5px 9px;
  border:1px solid rgba(125,211,252,.18);border-radius:999px;
  background:rgba(6,19,33,.78);color:#a8bdd1;font-size:.56rem;font-weight:900;letter-spacing:.03em;
}}
.ks-v2-player-pills .ks-v2-gate{{color:#c9f2ff;border-color:rgba(56,189,248,.34)}}
.ks-v2-gate i{{display:inline-block;width:7px;height:7px;border-radius:50%;background:#22c55e;box-shadow:0 0 10px #22c55e}}
.ks-v2-gate-closed i{{background:#ef4444;box-shadow:0 0 10px #ef4444}}

.ks-v2-game-meta{{
  grid-area:meta;display:flex;justify-content:center;align-items:center;flex-wrap:wrap;gap:10px;
  margin-top:2px;padding-top:12px;border-top:1px solid rgba(148,163,184,.14);
  color:#9cb0c4;font-size:.67rem;font-weight:700;
}}
.ks-v2-game-meta b{{color:#4b6076;font-weight:500}}

@media(max-width:900px){{
  .ks-v2-hero{{grid-template-columns:150px minmax(330px,1fr) 150px;gap:10px;padding:15px 14px 12px;min-height:206px}}
  .ks-v2-hero-team img:not(.ks-v2-team-watermark){{width:64px;height:64px;flex-basis:64px}}
  .ks-v2-hero-team strong{{font-size:.9rem}}
  .ks-v2-hero-player{{grid-template-columns:118px minmax(0,1fr);gap:14px}}
  .ks-v2-headshot-ring{{width:112px;height:112px}}
  .ks-v2-headshot-team{{width:38px;height:38px}}
  .ks-v2-player-copy>p{{font-size:.9rem}}
}}
@media(max-width:640px){{
  .ks-v2-hero{{
    grid-template-columns:1fr 1fr;
    grid-template-areas:"player player" "home away" "meta meta";
    gap:8px;min-height:0;padding:14px 11px 12px;border-radius:15px;
  }}
  .ks-v2-hero-player{{grid-template-columns:88px minmax(0,1fr);gap:12px}}
  .ks-v2-headshot-ring{{width:84px;height:84px;padding:3px}}
  .ks-v2-headshot-team{{width:30px;height:30px;right:-4px}}
  .ks-v2-player-title h1{{font-size:clamp(1.55rem,7.8vw,2.05rem)}}
  .ks-v2-player-copy>p{{font-size:.76rem;margin-top:4px}}
  .ks-v2-player-pills{{gap:5px;margin-top:8px}}
  .ks-v2-player-pills span{{min-height:26px;padding:4px 7px;font-size:.48rem}}
  .ks-v2-hero-team{{min-height:76px;padding:8px 5px;gap:7px}}
  .ks-v2-hero-team img:not(.ks-v2-team-watermark){{width:48px;height:48px;flex-basis:48px}}
  .ks-v2-hero-team-away{{flex-direction:row}}
  .ks-v2-hero-team span{{font-size:.58rem}}
  .ks-v2-hero-team strong{{font-size:.74rem}}
  .ks-v2-game-meta{{justify-content:flex-start;gap:6px;font-size:.56rem;padding-top:9px}}
}}
@media(prefers-reduced-motion:reduce){{
  .ks-v2-hero *{{transition:none!important;animation:none!important}}
}}
</style>
""",
        unsafe_allow_html=True,
    )
    return {
        "ready": True,
        "state": "ready",
        "version": VISUAL_VERSION,
        "real_composition_rebuild": True,
        "presentation_only": True,
        "player_team": team,
        "opponent": opp,
        "minimum_touch_target_px": MIN_TOUCH_TARGET_PX,
        "certified_viewports": CERTIFIED_VIEWPORTS,
        "data_ownership_changed": False,
        "interaction_behavior_changed": False,
        "projection_weight": 0.0,
    }
