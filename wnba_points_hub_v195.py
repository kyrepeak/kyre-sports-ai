"""WNBA Points V1.9.5 — visual Step 2.1: player headshots.

Presentation-only wrapper over V1.9.4. Adds ESPN WNBA player headshots to the
player-facing Points visual layer, with a team-logo fallback when an image is
unavailable. Projection, SportsGameOdds, calibration, Monte Carlo, persistence,
H2H calculations and decision math remain unchanged. Frozen WNBA PRA V3.2.1
and MLB V2.1.7 remain untouched.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v194 as base
import wnba_points_hub_v19 as hierarchy
import wnba_points_v19 as points

MODEL_VERSION = "WNBA POINTS V1.9.5 • PLAYER HEADSHOTS"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
core = base.core


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _player_id(value) -> str:
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text if text.isdigit() else ""


def _espn_headshot(player_id) -> str:
    pid = _player_id(player_id)
    if not pid:
        return ""
    return f"https://a.espncdn.com/i/headshots/wnba/players/full/{pid}.png"


def _photo_html(player_id, team_id, player_name, css_class="kyre-player-photo") -> str:
    headshot = escape(_espn_headshot(player_id), quote=True)
    fallback = escape(base._logo(team_id), quote=True)
    alt = escape(str(player_name or "WNBA player"), quote=True)
    if headshot:
        onerror = f"this.onerror=null;this.src='{fallback}';" if fallback else "this.style.display='none';"
        return f'<img class="{css_class}" src="{headshot}" alt="{alt}" onerror="{onerror}">'
    if fallback:
        return f'<img class="{css_class} fallback" src="{fallback}" alt="{alt}">'
    return '<div class="kyre-player-placeholder">🏀</div>'


def _split_text(value):
    return "—" if pd.isna(value) else f"{float(value):.1f}"


def _render_h2h_cards_with_photos(day: str):
    context = base._candidate_order(day, base._history_context_rows(day))
    st.markdown("### 🆚 Player vs Team History")
    st.caption(
        "Current-season prior meetings between the player's current team and today's opponent. "
        "Descriptive context only — H2H does not change the Points projection or Monte Carlo."
    )
    st.caption("📸 Player photos: ESPN WNBA headshots • verified player ID first • team-logo fallback")
    if context.empty:
        st.info("Player-vs-team history is waiting on the verified Points projection + exact-market handoff.")
        return

    detailed = []
    top = context.loc[~context["Decision"].astype(str).str.contains("AVOID", na=False)].head(5)
    if top.empty:
        top = context.head(5)

    cards = []
    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        profile = base._player_h2h_profile(
            day,
            row.get("PLAYER_ID"),
            row.get("Player"),
            int(_num(row.get("TEAM_ID"), 0)),
            int(_num(row.get("opponent_team_id"), 0)),
            row.get("line"),
        )
        team_logo = escape(base._logo(row.get("TEAM_ID")), quote=True)
        opp_logo = escape(base._logo(row.get("opponent_team_id")), quote=True)
        team_img = f'<img src="{team_logo}" alt="team logo">' if team_logo else "🏀"
        opp_img = f'<img src="{opp_logo}" alt="opponent logo">' if opp_logo else "🏀"
        player = escape(str(row.get("Player") or "WNBA Player"))
        player_photo = _photo_html(row.get("PLAYER_ID"), row.get("TEAM_ID"), row.get("Player"))
        gp = int(profile.get("games") or 0)
        avg = _split_text(profile.get("avg_pts"))
        l3 = _split_text(profile.get("l3_pts"))
        mins = _split_text(profile.get("avg_min"))
        hit = "—" if pd.isna(profile.get("hit_rate", np.nan)) else f"{profile.get('hit_rate')*100:.0f}%"
        split = f"H {_split_text(profile.get('home_avg'))} • A {_split_text(profile.get('away_avg'))}"
        last = "—" if gp == 0 else f"{profile.get('last_pts',0):.0f} PTS • {profile.get('last_date','—')}"
        sample = str(profile.get("sample") or "SMALL SAMPLE")
        sample_class = "good" if gp >= 3 else "warn"
        team = escape(str(row.get("team_name") or "Team"))
        opp = escape(str(row.get("opponent") or "Opponent"))
        books = escape(str(row.get("books") or ""))
        line = _num(row.get("line"), np.nan)
        proj = _num(row.get("Proj PTS"), np.nan)
        line_text = "—" if pd.isna(line) else f"{line:.1f}"
        proj_text = "—" if pd.isna(proj) else f"{proj:.2f}"
        cards.append(
            f"""
<div class="kyre-h2h-card">
  <div class="kyre-h2h-top"><span>🆚 H2H #{rank}</span><span>PREVIEW</span></div>
  <div class="kyre-player-id-row">
    <div class="kyre-photo-shell">{player_photo}</div>
    <div>
      <div class="kyre-h2h-player">{player}</div>
      <div class="kyre-h2h-match">
        <span>{team_img}{team}</span><b>vs</b><span>{opp_img}{opp}</span>
      </div>
    </div>
  </div>
  <div class="kyre-h2h-line">Today O {line_text} • Proj {proj_text}{(' • ' + books) if books else ''}</div>
  <div class="kyre-h2h-metrics">
    <div><small>H2H GP</small><strong>{gp}</strong></div>
    <div><small>AVG PTS</small><strong>{avg}</strong></div>
    <div><small>L3 VS OPP</small><strong>{l3}</strong></div>
    <div><small>AVG MIN</small><strong>{mins}</strong></div>
    <div><small>OVER TODAY LINE</small><strong>{hit}</strong></div>
    <div><small>HOME / AWAY</small><strong>{split}</strong></div>
    <div class="wide"><small>LAST MEETING</small><strong>{last}</strong></div>
  </div>
  <div class="kyre-h2h-sample {sample_class}">{sample} • descriptive only</div>
</div>
            """
        )

    st.markdown(
        """
<style>
.kyre-h2h-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:8px 0 14px}
.kyre-h2h-card{background:linear-gradient(145deg,#0b2034,#081521);border:1px solid #29526d;border-radius:20px;padding:17px;box-shadow:0 8px 22px rgba(0,0,0,.18)}
.kyre-h2h-top{display:flex;justify-content:space-between;gap:8px;color:#64ddff;font-size:.67rem;font-weight:900;letter-spacing:.06em;text-transform:uppercase}
.kyre-player-id-row{display:flex;align-items:center;gap:13px;margin:10px 0 8px}.kyre-photo-shell{width:74px;height:74px;min-width:74px;border-radius:50%;overflow:hidden;background:radial-gradient(circle at 50% 35%,#173650,#071522 72%);border:1px solid #326281;display:flex;align-items:center;justify-content:center}.kyre-player-photo{width:100%;height:100%;object-fit:cover;object-position:center 18%}.kyre-player-photo.fallback{object-fit:contain;padding:10px}.kyre-player-placeholder{font-size:1.7rem}
.kyre-h2h-player{font-size:1.22rem;font-weight:950;color:white;margin:0 0 6px}.kyre-h2h-match{display:flex;align-items:center;gap:8px;color:#a7bbca;font-size:.78rem;flex-wrap:wrap}.kyre-h2h-match span{display:flex;align-items:center;gap:5px}.kyre-h2h-match img{width:25px;height:25px;object-fit:contain}
.kyre-h2h-line{color:#88a2b8;font-size:.72rem;margin:8px 0 12px}.kyre-h2h-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.kyre-h2h-metrics div{border:1px solid #244760;border-radius:11px;padding:9px;background:#091827}.kyre-h2h-metrics .wide{grid-column:span 3}.kyre-h2h-metrics small{display:block;color:#718ba0;font-size:.55rem;font-weight:850;letter-spacing:.05em}.kyre-h2h-metrics strong{display:block;color:#f6fbff;font-size:.92rem;margin-top:3px}
.kyre-h2h-sample{display:inline-block;margin-top:11px;border-radius:999px;padding:5px 8px;font-size:.59rem;font-weight:900;letter-spacing:.04em}.kyre-h2h-sample.good{background:#0c3b2c;color:#72efb1;border:1px solid #217956}.kyre-h2h-sample.warn{background:#3a3009;color:#ffe17a;border:1px solid #756313}
@media(max-width:760px){.kyre-h2h-grid{grid-template-columns:1fr}.kyre-h2h-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.kyre-h2h-metrics .wide{grid-column:span 2}.kyre-photo-shell{width:68px;height:68px;min-width:68px}}
</style>
<div class="kyre-h2h-grid">""" + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )

    for _, row in context.iterrows():
        profile = base._player_h2h_profile(
            day,
            row.get("PLAYER_ID"),
            row.get("Player"),
            int(_num(row.get("TEAM_ID"), 0)),
            int(_num(row.get("opponent_team_id"), 0)),
            row.get("line"),
        )
        detailed.append({
            "Photo": _espn_headshot(row.get("PLAYER_ID")),
            "Player": row.get("Player"),
            "Team": row.get("team_name"),
            "Opponent": row.get("opponent"),
            "Today line": row.get("line"),
            "Proj PTS": round(_num(row.get("Proj PTS"), np.nan), 2),
            "H2H GP": int(profile.get("games") or 0),
            "Avg PTS": round(_num(profile.get("avg_pts"), np.nan), 1) if pd.notna(_num(profile.get("avg_pts"), np.nan)) else np.nan,
            "L3 vs opp": round(_num(profile.get("l3_pts"), np.nan), 1) if pd.notna(_num(profile.get("l3_pts"), np.nan)) else np.nan,
            "Avg MIN": round(_num(profile.get("avg_min"), np.nan), 1) if pd.notna(_num(profile.get("avg_min"), np.nan)) else np.nan,
            "Over line": "—" if pd.isna(profile.get("hit_rate", np.nan)) else f"{profile.get('over_hits',0)}/{profile.get('games',0)} ({profile.get('hit_rate')*100:.0f}%)",
            "Last": "—" if not profile.get("games") else f"{profile.get('last_pts',0):.0f} • {profile.get('last_date','—')}",
            "Sample": profile.get("sample"),
        })
    with st.expander("📚 Full player-vs-team history board", expanded=False):
        board = pd.DataFrame(detailed)
        st.dataframe(
            board,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Photo": st.column_config.ImageColumn("Player", width="small"),
            },
        )
        st.caption("Source: verified completed ESPN WNBA game summaries • current season/current team vs today's opponent • exact SportsGameOdds Points line used only for descriptive hit-rate comparison.")


def _projection_meta(day: str) -> pd.DataFrame:
    try:
        projections, _, _, _, _ = points._prepare(day)
    except Exception:
        return pd.DataFrame()
    if not isinstance(projections, pd.DataFrame) or projections.empty:
        return pd.DataFrame()
    work = projections.copy()
    for col in ("game_id", "player_key", "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "team_name", "opponent_team_id", "opponent", "PROJ_MIN", "USG_PCT"):
        if col not in work.columns:
            work[col] = np.nan if col not in {"game_id", "player_key", "PLAYER_NAME", "team_name", "opponent"} else ""
    return work[["game_id", "player_key", "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "team_name", "opponent_team_id", "opponent", "PROJ_MIN", "USG_PCT"]].drop_duplicates(["game_id", "player_key"], keep="first")


def _render_final_points_board_with_photos(day):
    rows = points.combined_rows(day)
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return
    work = rows.copy()
    for col in ("model_over", "edge", "data_quality", "market_age"):
        work[col] = pd.to_numeric(work.get(col), errors="coerce")
    work["Decision"] = work.apply(core._calibrated_decision_tier, axis=1)
    work["_tier"] = work["Decision"].map({
        "🔥 BEST BET": 0,
        "✅ STRONG": 1,
        "⚠️ MONITOR": 2,
        "⛔ AVOID": 3,
    }).fillna(9)

    cal = work.apply(core._calibrated_values, axis=1, result_type="expand")
    cal.columns = ["_raw", "_buffer", "_floor", "_cedge"]
    for col in cal.columns:
        work[col] = cal[col].values
    work = work.sort_values(["_tier", "_floor", "_cedge", "data_quality"], ascending=[True, False, False, False])
    best = work.drop_duplicates(["player_key", "line"], keep="first").copy()
    qualified = best[best["Decision"].isin(["🔥 BEST BET", "✅ STRONG", "⚠️ MONITOR"])].head(5)

    st.markdown("### 🏆 Top Points Candidates")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("BEST BET", int((best["Decision"] == "🔥 BEST BET").sum()))
    c2.metric("STRONG", int((best["Decision"] == "✅ STRONG").sum()))
    c3.metric("MONITOR", int((best["Decision"] == "⚠️ MONITOR").sum()))
    c4.metric("AVOID", int((best["Decision"] == "⛔ AVOID").sum()))

    if qualified.empty:
        st.info("No qualified Points candidate currently clears the calibrated final hierarchy. Nothing is forced.")
        return

    meta = _projection_meta(day)
    if not meta.empty:
        qualified = qualified.merge(meta, on=["game_id", "player_key"], how="left")

    cards = []
    for rank, (_, row) in enumerate(qualified.iterrows(), start=1):
        player = escape(str(row.get("player") or row.get("PLAYER_NAME") or "WNBA Player"))
        team_id = row.get("TEAM_ID")
        opp_id = row.get("opponent_team_id")
        team = escape(str(row.get("team_name") or "Team"))
        opp = escape(str(row.get("opponent") or "Opponent"))
        photo = _photo_html(row.get("PLAYER_ID"), team_id, player, "kyre-candidate-photo")
        team_logo = escape(base._logo(team_id), quote=True)
        opp_logo = escape(base._logo(opp_id), quote=True)
        team_img = f'<img src="{team_logo}" alt="team logo">' if team_logo else "🏀"
        opp_img = f'<img src="{opp_logo}" alt="opponent logo">' if opp_logo else "🏀"
        decision = escape(str(row.get("Decision") or "⚠️ MONITOR"))
        line = _num(row.get("line"), np.nan)
        projection = _num(row.get("projection"), np.nan)
        sim_mean = _num(row.get("sim_mean"), np.nan)
        raw = _num(row.get("_raw"), np.nan)
        floor = _num(row.get("_floor"), np.nan)
        cedge = _num(row.get("_cedge"), np.nan)
        no_vig = _num(row.get("no_vig_over"), np.nan)
        mins = _num(row.get("PROJ_MIN"), np.nan)
        usage = _num(row.get("USG_PCT"), np.nan)
        book = escape(str(row.get("book") or "Sportsbook"))
        pass_source = escape(str(row.get("pass_source") or "5M"))
        lineup = "CONFIRMED" if bool(row.get("lineup_ready")) else "LINEUP PENDING"
        cards.append(
            f"""
<div class="kyre-candidate-card">
  <div class="kyre-candidate-rank"><span>🏅 RANK {rank}</span><span>{decision}</span></div>
  <div class="kyre-candidate-id">
    <div class="kyre-candidate-photo-shell">{photo}</div>
    <div>
      <div class="kyre-candidate-name">{player}</div>
      <div class="kyre-candidate-match"><span>{team_img}{team}</span><b>vs</b><span>{opp_img}{opp}</span></div>
      <div class="kyre-candidate-book">O {line:.1f} • {book} • {pass_source}</div>
    </div>
  </div>
  <div class="kyre-candidate-prob">{floor*100:.1f}% <small>CALIBRATED FLOOR</small></div>
  <div class="kyre-candidate-stats">
    <div><small>PROJ PTS</small><strong>{projection:.2f}</strong></div>
    <div><small>MC MEAN</small><strong>{sim_mean:.2f}</strong></div>
    <div><small>RAW P(OVER)</small><strong>{raw*100:.1f}%</strong></div>
    <div><small>NO-VIG O</small><strong>{no_vig*100:.1f}%</strong></div>
    <div><small>CAL EDGE</small><strong>{cedge*100:+.1f} pp</strong></div>
    <div><small>PROJ MIN</small><strong>{mins:.1f}</strong></div>
    <div><small>USAGE</small><strong>{usage:.1f}%</strong></div>
    <div><small>STATUS</small><strong>{lineup}</strong></div>
  </div>
</div>
            """
        )

    st.markdown(
        """
<style>
.kyre-candidate-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:10px 0 14px}.kyre-candidate-card{background:linear-gradient(145deg,#0b2034,#071421);border:1px solid #2b5673;border-radius:21px;padding:17px;box-shadow:0 8px 24px rgba(0,0,0,.18)}.kyre-candidate-rank{display:flex;justify-content:space-between;gap:8px;color:#64ddff;font-size:.66rem;font-weight:900;letter-spacing:.055em}.kyre-candidate-id{display:flex;align-items:center;gap:13px;margin:12px 0}.kyre-candidate-photo-shell{width:84px;height:84px;min-width:84px;border-radius:50%;overflow:hidden;background:radial-gradient(circle at 50% 35%,#183b59,#071522 72%);border:1px solid #376a8a;display:flex;align-items:center;justify-content:center}.kyre-candidate-photo{width:100%;height:100%;object-fit:cover;object-position:center 18%}.kyre-candidate-photo.fallback{object-fit:contain;padding:11px}.kyre-candidate-name{font-size:1.22rem;font-weight:950;color:#fff}.kyre-candidate-match{display:flex;align-items:center;gap:7px;flex-wrap:wrap;color:#9fb5c6;font-size:.72rem;margin-top:5px}.kyre-candidate-match span{display:flex;align-items:center;gap:4px}.kyre-candidate-match img{width:22px;height:22px;object-fit:contain}.kyre-candidate-book{color:#7f9ab0;font-size:.68rem;margin-top:5px}.kyre-candidate-prob{font-size:2.15rem;font-weight:1000;color:#72e6ff;margin:10px 0}.kyre-candidate-prob small{font-size:.55rem;color:#7893a8;letter-spacing:.045em}.kyre-candidate-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px}.kyre-candidate-stats div{background:#091827;border:1px solid #244760;border-radius:10px;padding:8px}.kyre-candidate-stats small{display:block;color:#6f889d;font-size:.49rem;font-weight:850;letter-spacing:.045em}.kyre-candidate-stats strong{display:block;color:#f5fbff;font-size:.78rem;margin-top:3px}@media(max-width:760px){.kyre-candidate-grid{grid-template-columns:1fr}.kyre-candidate-stats{grid-template-columns:repeat(2,minmax(0,1fr))}.kyre-candidate-photo-shell{width:76px;height:76px;min-width:76px}}
</style>
<div class="kyre-candidate-grid">""" + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )
    if (qualified["Decision"] == "⚠️ MONITOR").any():
        st.warning("⚠️ Starting fives are still pending for one or more qualified players. MONITOR candidates are not Final Ready until explicit lineup confirmation publishes.")
    st.caption("📸 ESPN WNBA player photos are presentation-only. Points remains isolated from the shared WNBA Daily Master Card until the Points layer is validated and frozen.")


# Replace only presentation functions. V1.9.4 keeps H2H math/data intact.
base._render_h2h_cards = _render_h2h_cards_with_photos
hierarchy._render_final_points_board = _render_final_points_board_with_photos


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    base._render_h2h_cards = _render_h2h_cards_with_photos
    hierarchy._render_final_points_board = _render_final_points_board_with_photos
    return base.render_wnba_points_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MODEL_VERSION",
    "PRA_FROZEN_BRANCH",
    "PRA_FROZEN_COMMIT",
    "MLB_FROZEN_BRANCH",
    "render_wnba_points_hub",
]
