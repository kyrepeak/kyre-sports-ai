"""WNBA Points V1.9.8.4.9 — Top-5 H2H cards with embedded Step 3.

Presentation-only wrapper over V1.9.8.4.8. The validated V1.9.8.4.5 Points
projection, SportsGameOdds transport, 5M/10M Monte Carlo, calibration,
candidate hierarchy, persistence, readiness gates and player-level sanity
quarantine are unchanged.

V1.9.8.4.8 rendered Step 3 after the full five-card H2H section. This wrapper
changes only presentation order so every Top-5 player card flows directly from
Step 2 Player-vs-Team History into Step 3 Minutes + Role + Usage.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v19848 as prior

# Existing presentation/runtime modules already loaded by the clean chain.
evidence = prior.evidence
h2h = prior.h2h
photos = evidence.photos
base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.9 • EMBEDDED STEP 3 TOP-5 CARDS"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _split(value, digits=1):
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}"


def _step3_block(data: dict) -> str:
    grade, grade_class = prior._opportunity_grade(data)
    trend = escape(prior._minute_trend(data))
    role_text = escape(prior._role_text(data))

    proj_min = prior._fmt(data.get("PROJ_MIN"))
    l3_team = prior._fmt(data.get("RECENT_TEAM_L3_MIN"))
    l5_team = prior._fmt(data.get("RECENT_TEAM_L5_MIN"))
    l10_min = prior._fmt(data.get("L10_MIN"))
    l5_min = prior._fmt(data.get("L5_MIN"))
    season_min = prior._fmt(data.get("MIN"))
    usg = prior._pct(data.get("USG_PCT"))
    l10_usg = prior._pct(data.get("L10_USG_PCT"))
    l5_usg = prior._pct(data.get("L5_USG_PCT"))

    usage_ratio = _num(data.get("USG_RATIO"), np.nan)
    usage_ratio_text = "—" if pd.isna(usage_ratio) else f"{usage_ratio:.2f}×"
    min_delta = _num(data.get("MIN_DELTA"), np.nan)
    min_delta_text = "—" if pd.isna(min_delta) else f"{min_delta:+.1f}"
    pts_rate = _num(data.get("PTS_RATE"), np.nan)
    pts_rate_text = "—" if pd.isna(pts_rate) else f"{pts_rate:.3f} PTS/min"
    source = escape(str(data.get("MINUTES_SOURCE") or "Existing Points rotation/minutes engine"))

    return f"""
  <div class="kyre-v19849-step3">
    <div class="kyre-v19849-step-head">
      <span>STEP 3 • MINUTES + ROLE + USAGE</span>
      <span class="kyre-v19849-grade {grade_class}">{escape(grade)}</span>
    </div>
    <div class="kyre-v19849-role"><b>Role</b> • {role_text}<br><b>Minutes trend</b> • {trend}</div>
    <div class="kyre-v19849-p3grid">
      <div><small>PROJECTED MIN</small><strong>{proj_min}</strong></div>
      <div><small>SEASON MIN</small><strong>{season_min}</strong></div>
      <div><small>TEAM ROTATION L3</small><strong>{l3_team}</strong></div>
      <div><small>TEAM ROTATION L5</small><strong>{l5_team}</strong></div>
      <div><small>PLAYER L10 MIN</small><strong>{l10_min}</strong></div>
      <div><small>PLAYER L5 MIN</small><strong>{l5_min}</strong></div>
      <div><small>SEASON USAGE</small><strong>{usg}</strong></div>
      <div><small>L10 USAGE</small><strong>{l10_usg}</strong></div>
      <div><small>L5 USAGE</small><strong>{l5_usg}</strong></div>
      <div><small>USAGE RATIO</small><strong>{usage_ratio_text}</strong></div>
      <div><small>MIN DELTA VS BASE</small><strong>{min_delta_text}</strong></div>
      <div><small>BASE SCORING RATE</small><strong>{pts_rate_text}</strong></div>
    </div>
    <div class="kyre-v19849-source">Minutes source • {source}</div>
    <div class="kyre-v19849-note">Audit/context only • these are existing protected Points-engine values • no new probability adjustment or reranking.</div>
  </div>
"""


def _render_top5_h2h_with_embedded_step3(day: str) -> None:
    top = prior._same_top5(day)
    projections = prior._production_projection_frame(day)

    st.markdown("### 🆚 Top 5 — Player vs Team History")
    st.caption(
        "Each Top-5 card now keeps Step 2 history and Step 3 minutes/role/usage together. "
        "All fields are audit context only; protected Points model math and ranking remain unchanged."
    )

    if top.empty:
        st.info("Top-5 Points history is waiting on the verified projection + exact-market handoff.")
        return

    cards = []
    ledgers = []
    full_rows = []

    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        player_raw = str(row.get("Player") or row.get("PLAYER_NAME") or "WNBA Player")
        player = escape(player_raw)
        team = escape(str(row.get("team_name") or "Team"))
        opponent = escape(str(row.get("opponent") or "Opponent"))
        decision = escape(str(row.get("Decision") or "PREVIEW"))

        team_logo = escape(h2h._logo(row.get("TEAM_ID")), quote=True)
        opp_logo = escape(h2h._logo(row.get("opponent_team_id")), quote=True)
        team_img = f'<img src="{team_logo}" alt="team logo">' if team_logo else "🏀"
        opp_img = f'<img src="{opp_logo}" alt="opponent logo">' if opp_logo else "🏀"
        player_photo = photos._photo_html(
            row.get("PLAYER_ID"), row.get("TEAM_ID"), player_raw, "kyre-v19849-photo"
        )

        line = _num(row.get("line"), np.nan)
        projection = _num(row.get("Proj PTS"), np.nan)
        match = evidence._player_meetings(str(day), row)
        summary = evidence._meeting_summary(match, line, projection)
        label, label_class = evidence._context_read(summary, line)
        data = prior._match_projection(projections, row)

        gp = int(summary.get("games") or 0)
        avg = _split(summary.get("avg_pts"))
        l3 = _split(summary.get("l3_pts"))
        avg_min = _split(summary.get("avg_min"))
        hit_rate = _num(summary.get("hit_rate"), np.nan)
        hit_text = "—" if pd.isna(hit_rate) else f"{int(summary.get('over_hits') or 0)}/{gp} • {hit_rate*100:.0f}%"
        split = f"H {_split(summary.get('home_avg'))} • A {_split(summary.get('away_avg'))}"
        last = "—" if gp == 0 else f"{_split(summary.get('last_pts'),0)} PTS • {_split(summary.get('last_min'),1)} MIN • {summary.get('last_date','—')}"
        avg_margin = _num(summary.get("avg_margin"), np.nan)
        margin_text = "—" if pd.isna(avg_margin) else f"{avg_margin:+.1f}"
        proj_vs = _num(summary.get("proj_vs_h2h"), np.nan)
        proj_vs_text = "—" if pd.isna(proj_vs) else f"{proj_vs:+.1f}"
        lo = _num(summary.get("range_low"), np.nan)
        hi = _num(summary.get("range_high"), np.nan)
        range_text = "—" if pd.isna(lo) or pd.isna(hi) else f"{lo:.0f}–{hi:.0f}"
        recent_scores = escape(str(summary.get("last3_scores") or "—"))
        sample = escape(str(summary.get("sample") or "SMALL SAMPLE"))
        books = escape(str(row.get("books") or ""))
        line_text = "—" if pd.isna(line) else f"{line:.1f}"
        proj_text = "—" if pd.isna(projection) else f"{projection:.2f}"

        cards.append(f"""
<div class="kyre-v19849-card">
  <div class="kyre-v19849-top"><span>🆚 H2H #{rank}</span><span>{decision}</span></div>
  <div class="kyre-v19849-id">
    <div class="kyre-v19849-photo-shell">{player_photo}</div>
    <div>
      <div class="kyre-v19849-player">{player}</div>
      <div class="kyre-v19849-match"><span>{team_img}{team}</span><b>vs</b><span>{opp_img}{opponent}</span></div>
    </div>
  </div>
  <div class="kyre-v19849-line">Today O {line_text} • Proj {proj_text}{(" • " + books) if books else ""}</div>

  <div class="kyre-v19849-step2">
    <div class="kyre-v19849-step-title">STEP 2 • PLAYER VS TEAM HISTORY</div>
    <div class="kyre-v19849-read {label_class}">{escape(label)}</div>
    <div class="kyre-v19849-grid">
      <div><small>H2H GP</small><strong>{gp}</strong></div>
      <div><small>AVG PTS</small><strong>{avg}</strong></div>
      <div><small>L3 VS OPP</small><strong>{l3}</strong></div>
      <div><small>AVG MIN</small><strong>{avg_min}</strong></div>
      <div><small>OVER TODAY LINE</small><strong>{hit_text}</strong></div>
      <div><small>AVG MARGIN VS LINE</small><strong>{margin_text}</strong></div>
      <div><small>PROJ VS H2H AVG</small><strong>{proj_vs_text}</strong></div>
      <div><small>PTS RANGE</small><strong>{range_text}</strong></div>
      <div><small>HOME / AWAY</small><strong>{split}</strong></div>
      <div><small>LAST 3 SCORES</small><strong>{recent_scores}</strong></div>
      <div class="wide"><small>LAST MEETING</small><strong>{last}</strong></div>
    </div>
    <div class="kyre-v19849-sample {('good' if gp >= 3 else 'warn')}">{sample} • descriptive only</div>
  </div>

  {_step3_block(data)}
</div>
""")

        ledger = evidence._ledger_frame(match, line)
        ledgers.append((rank, player_raw, ledger, label))
        full_rows.append({
            "Rank": rank,
            "Player": player_raw,
            "Team": row.get("team_name"),
            "Opponent": row.get("opponent"),
            "Today line": round(line, 1) if pd.notna(line) else np.nan,
            "Proj PTS": round(projection, 2) if pd.notna(projection) else np.nan,
            "H2H GP": gp,
            "Avg PTS": round(_num(summary.get("avg_pts"), np.nan), 1) if pd.notna(_num(summary.get("avg_pts"), np.nan)) else np.nan,
            "Over today line": hit_text,
            "Context read": label,
            "Projected MIN": round(_num(data.get("PROJ_MIN"), np.nan), 1) if pd.notna(_num(data.get("PROJ_MIN"), np.nan)) else np.nan,
            "L3 rotation MIN": round(_num(data.get("RECENT_TEAM_L3_MIN"), np.nan), 1) if pd.notna(_num(data.get("RECENT_TEAM_L3_MIN"), np.nan)) else np.nan,
            "L5 rotation MIN": round(_num(data.get("RECENT_TEAM_L5_MIN"), np.nan), 1) if pd.notna(_num(data.get("RECENT_TEAM_L5_MIN"), np.nan)) else np.nan,
            "Usage": prior._pct(data.get("USG_PCT")),
        })

    st.markdown(
        """
<style>
.kyre-v19849-wrap{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:8px 0 14px}
.kyre-v19849-card{background:linear-gradient(145deg,#0b2034,#081521);border:1px solid #315c78;border-radius:22px;padding:18px;box-shadow:0 8px 22px rgba(0,0,0,.18)}
.kyre-v19849-top{display:flex;justify-content:space-between;gap:8px;color:#64ddff;font-size:.67rem;font-weight:950;letter-spacing:.06em;text-transform:uppercase}
.kyre-v19849-id{display:flex;align-items:center;gap:14px;margin:12px 0 8px}.kyre-v19849-photo-shell{width:76px;height:76px;min-width:76px;border-radius:50%;overflow:hidden;background:#0a1b2a;border:1px solid #326281;display:flex;align-items:center;justify-content:center}.kyre-v19849-photo{width:100%;height:100%;object-fit:cover;object-position:center 18%}.kyre-v19849-photo.fallback{object-fit:contain;padding:10px}.kyre-player-placeholder{font-size:1.7rem}
.kyre-v19849-player{font-size:1.24rem;font-weight:950;color:white;margin:0 0 6px}.kyre-v19849-match{display:flex;align-items:center;gap:8px;color:#a7bbca;font-size:.78rem;flex-wrap:wrap}.kyre-v19849-match span{display:flex;align-items:center;gap:5px}.kyre-v19849-match img{width:25px;height:25px;object-fit:contain}.kyre-v19849-line{color:#8ea8bd;font-size:.72rem;margin:8px 0 12px}
.kyre-v19849-step2,.kyre-v19849-step3{border-radius:15px;padding:12px;margin-top:10px}.kyre-v19849-step2{background:#091827;border:1px solid #294b64}.kyre-v19849-step3{background:#10182b;border:1px solid #4f5f8a}.kyre-v19849-step-title,.kyre-v19849-step-head{color:#79d8ff;font-size:.61rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:9px}.kyre-v19849-step-head{display:flex;justify-content:space-between;align-items:center;gap:8px}
.kyre-v19849-read{border-radius:10px;padding:8px 9px;font-size:.62rem;font-weight:950;margin-bottom:9px}.kyre-v19849-read.good{background:#0a3025;border:1px solid #1d7554;color:#75efb4}.kyre-v19849-read.bad{background:#35171b;border:1px solid #7a3941;color:#ff9aa5}.kyre-v19849-read.warn{background:#3a3009;border:1px solid #756313;color:#ffe17a}.kyre-v19849-read.neutral{background:#10263a;border:1px solid #31526c;color:#9fd7fa}
.kyre-v19849-grid,.kyre-v19849-p3grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.kyre-v19849-grid div,.kyre-v19849-p3grid div{border:1px solid #244760;border-radius:10px;padding:8px;background:#071522}.kyre-v19849-grid .wide{grid-column:span 2}.kyre-v19849-grid small,.kyre-v19849-p3grid small{display:block;color:#718ba0;font-size:.48rem;font-weight:900;letter-spacing:.045em}.kyre-v19849-grid strong,.kyre-v19849-p3grid strong{display:block;color:#f6fbff;font-size:.84rem;margin-top:3px}
.kyre-v19849-sample{display:inline-block;margin-top:9px;border-radius:999px;padding:5px 8px;font-size:.57rem;font-weight:900}.kyre-v19849-sample.good{background:#0c3b2c;color:#72efb1;border:1px solid #217956}.kyre-v19849-sample.warn{background:#3a3009;color:#ffe17a;border:1px solid #756313}
.kyre-v19849-grade{border-radius:999px;padding:5px 8px;white-space:nowrap;font-size:.55rem}.kyre-v19849-grade.elite{background:#0b422f;color:#7df2ba;border:1px solid #237a59}.kyre-v19849-grade.strong{background:#103a32;color:#7ce7c2;border:1px solid #2c7463}.kyre-v19849-grade.normal{background:#3a3009;color:#ffe17a;border:1px solid #756313}.kyre-v19849-grade.limited{background:#34202a;color:#ffb1c0;border:1px solid #724457}.kyre-v19849-role{background:#0a1b2a;border:1px solid #294b64;border-radius:10px;padding:8px 9px;color:#dce9f4;font-size:.68rem;line-height:1.5;margin-bottom:8px}.kyre-v19849-role b{color:#86d9ff}.kyre-v19849-source{color:#91a9bb;font-size:.61rem;margin-top:9px}.kyre-v19849-note{color:#72899b;font-size:.57rem;line-height:1.4;margin-top:4px}
@media(max-width:760px){.kyre-v19849-wrap{grid-template-columns:1fr}.kyre-v19849-photo-shell{width:70px;height:70px;min-width:70px}.kyre-v19849-step-head{align-items:flex-start;flex-direction:column}}
</style>
<div class="kyre-v19849-wrap">""" + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### 🧾 Meeting-by-meeting audit")
    for rank, player_name, ledger, label in ledgers:
        with st.expander(f"🆚 H2H #{rank} • {player_name} — meeting ledger", expanded=False):
            if ledger.empty:
                st.info("No prior current-season meeting is available for this player/current-team matchup.")
            else:
                st.dataframe(ledger, use_container_width=True, hide_index=True)
            st.caption(f"Context read: {label} • descriptive only • no model adjustment")

    with st.expander("📚 Top-5 Step 2 + Step 3 audit summary", expanded=False):
        st.dataframe(pd.DataFrame(full_rows), use_container_width=True, hide_index=True)


def _install() -> None:
    # V1.9.8.4.8's renderer installs its `_render_h2h_plus_step3` symbol into
    # V1.9.8.4.6 at render time. Replace that symbol only; model/data hooks stay intact.
    prior._render_h2h_plus_step3 = _render_top5_h2h_with_embedded_step3


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🏀 Points V1.9.8.4.9 • Step 2 + Step 3 embedded inside each same Top-5 card • "
        "presentation audit only • protected model/ranking unchanged"
    )
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    try:
        return getattr(prior, name)
    except AttributeError:
        return getattr(base, name)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "v171", "ui", "points",
    "render_wnba_points_hub",
]
