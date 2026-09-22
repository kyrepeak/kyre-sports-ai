"""WNBA Points V1.9.8.4.6 — Top-5 player-vs-team history evidence cards.

Presentation/context-only wrapper over V1.9.8.4.5.

The protected Points projection, SportsGameOdds market transport, 5M/10M Monte
Carlo, calibration, candidate hierarchy, grading, persistence, Daily Picks,
PRA, Rebounds, Assists, Spread, Moneyline, Game Total, MLB and NFL math are
unchanged.

This layer upgrades only the visible Top-5 Player vs Team History section.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v19845 as prior
import wnba_points_hub_v195 as photos
import wnba_points_hub_v194 as h2h

MODEL_VERSION = "WNBA POINTS V1.9.8.4.6 • TOP-5 H2H EVIDENCE"
PRA_FROZEN_BRANCH = prior.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = prior.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = prior.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = prior.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = prior.POINTS_FROZEN_COMMIT


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _split(value, digits=1):
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}"


def _player_meetings(day: str, row) -> pd.DataFrame:
    try:
        team_id = int(_num(row.get("TEAM_ID"), 0))
        opp_id = int(_num(row.get("opponent_team_id"), 0))
        box = h2h._matchup_box_history(str(day), team_id, opp_id)
    except Exception:
        return pd.DataFrame()

    if box is None or box.empty:
        return pd.DataFrame()

    player_id = str(row.get("PLAYER_ID") or "").strip()
    player_name = str(row.get("Player") or row.get("PLAYER_NAME") or "")
    target_name = h2h._norm(player_name)

    match = pd.DataFrame()
    if player_id and "PLAYER_ID" in box.columns:
        match = box.loc[box["PLAYER_ID"].astype(str).eq(player_id)].copy()
    if match.empty and target_name and "PLAYER_NAME" in box.columns:
        match = box.loc[box["PLAYER_NAME"].map(h2h._norm).eq(target_name)].copy()
    if match.empty:
        return pd.DataFrame()

    match["PTS"] = pd.to_numeric(match.get("PTS"), errors="coerce")
    match["MIN"] = pd.to_numeric(match.get("MIN"), errors="coerce")
    match["_DATE"] = pd.to_datetime(match.get("_H2H_DATE"), errors="coerce")
    return (
        match.dropna(subset=["PTS"])
        .sort_values("_DATE", ascending=False)
        .drop_duplicates("_H2H_GAME_ID", keep="first")
        .head(10)
        .copy()
    )


def _meeting_summary(match: pd.DataFrame, line: float, projection: float) -> dict:
    if match is None or match.empty:
        return {
            "games": 0, "avg_pts": np.nan, "l3_pts": np.nan, "avg_min": np.nan,
            "hit_rate": np.nan, "over_hits": 0, "pushes": 0,
            "home_avg": np.nan, "away_avg": np.nan,
            "last_pts": np.nan, "last_min": np.nan, "last_date": "—",
            "avg_margin": np.nan, "proj_vs_h2h": np.nan,
            "range_low": np.nan, "range_high": np.nan,
            "last3_scores": "—", "sample": "NO PRIOR MEETINGS",
        }

    pts = pd.to_numeric(match["PTS"], errors="coerce").dropna()
    mins = pd.to_numeric(match.get("MIN"), errors="coerce")
    gp = int(len(pts))
    if gp == 0:
        return _meeting_summary(pd.DataFrame(), line, projection)

    home_mask = (
        match["_H2H_HOME"].astype(bool)
        if "_H2H_HOME" in match.columns
        else pd.Series(False, index=match.index)
    )
    home_pts = pd.to_numeric(match.loc[home_mask, "PTS"], errors="coerce").dropna()
    away_pts = pd.to_numeric(match.loc[~home_mask, "PTS"], errors="coerce").dropna()

    line_ok = pd.notna(line)
    overs = int((pts > line).sum()) if line_ok else 0
    pushes = int((pts == line).sum()) if line_ok else 0
    hit_rate = overs / gp if line_ok and gp else np.nan

    last = match.iloc[0]
    last_date = last.get("_DATE")
    avg_pts = float(pts.mean())

    return {
        "games": gp,
        "avg_pts": avg_pts,
        "l3_pts": float(pd.to_numeric(match.head(3)["PTS"], errors="coerce").mean()) if gp >= 3 else np.nan,
        "avg_min": float(mins.mean()) if mins.notna().any() else np.nan,
        "hit_rate": hit_rate,
        "over_hits": overs,
        "pushes": pushes,
        "home_avg": float(home_pts.mean()) if len(home_pts) else np.nan,
        "away_avg": float(away_pts.mean()) if len(away_pts) else np.nan,
        "last_pts": _num(last.get("PTS"), np.nan),
        "last_min": _num(last.get("MIN"), np.nan),
        "last_date": last_date.strftime("%b %d") if pd.notna(last_date) else "—",
        "avg_margin": avg_pts - line if line_ok else np.nan,
        "proj_vs_h2h": projection - avg_pts if pd.notna(projection) else np.nan,
        "range_low": float(pts.min()),
        "range_high": float(pts.max()),
        "last3_scores": " • ".join(
            f"{float(x):.0f}"
            for x in pd.to_numeric(match.head(3)["PTS"], errors="coerce").dropna()
        ),
        "sample": "USEFUL CONTEXT" if gp >= 3 else "SMALL SAMPLE",
    }


def _context_read(summary: dict, line: float) -> tuple[str, str]:
    gp = int(summary.get("games") or 0)
    avg = _num(summary.get("avg_pts"), np.nan)
    hit = _num(summary.get("hit_rate"), np.nan)

    if gp == 0:
        return "NO PRIOR MEETINGS", "neutral"
    if gp < 3:
        return "SMALL SAMPLE • NO ADJUSTMENT", "warn"
    if pd.notna(line) and pd.notna(avg) and pd.notna(hit):
        if avg >= line + 1.0 and hit >= 0.60:
            return "HISTORY SUPPORTS OVER • DESCRIPTIVE", "good"
        if avg <= line - 1.0 and hit <= 0.40:
            return "HISTORY CONCERN • DESCRIPTIVE", "bad"
    return "MIXED / NEUTRAL HISTORY", "neutral"


def _ledger_frame(match: pd.DataFrame, line: float) -> pd.DataFrame:
    if match is None or match.empty:
        return pd.DataFrame()

    rows = []
    for _, game in match.iterrows():
        pts = _num(game.get("PTS"), np.nan)
        mins = _num(game.get("MIN"), np.nan)
        date = game.get("_DATE")
        is_home = bool(game.get("_H2H_HOME")) if "_H2H_HOME" in match.columns else False

        if pd.notna(line) and pd.notna(pts):
            if pts > line:
                result = "OVER"
            elif pts < line:
                result = "UNDER"
            else:
                result = "PUSH"
            margin = pts - line
        else:
            result = "—"
            margin = np.nan

        rows.append({
            "Date": date.strftime("%b %d, %Y") if pd.notna(date) else "—",
            "Site": "HOME" if is_home else "AWAY",
            "PTS": round(pts, 1) if pd.notna(pts) else np.nan,
            "MIN": round(mins, 1) if pd.notna(mins) else np.nan,
            "Today line": round(line, 1) if pd.notna(line) else np.nan,
            "Vs line": round(margin, 1) if pd.notna(margin) else np.nan,
            "Result": result,
        })
    return pd.DataFrame(rows)


def _render_top5_h2h_evidence(day: str):
    context = h2h._candidate_order(day, h2h._history_context_rows(day))

    st.markdown("### 🆚 Top 5 — Player vs Team History")
    st.caption(
        "Verified current-season prior meetings between each player's current team and today's opponent. "
        "Descriptive evidence only — this never changes the protected Points projection, Monte Carlo, "
        "calibration, ranking or final decision."
    )
    st.caption(
        "📸 ESPN WNBA headshots • exact current Points line • current-team/current-season H2H • "
        "small samples are explicitly blocked from directional weighting"
    )

    if context is None or context.empty:
        st.info("Player-vs-team history is waiting on the verified Points projection + exact-market handoff.")
        return

    top = context.loc[
        ~context["Decision"].astype(str).str.contains("AVOID", na=False)
    ].head(5)
    if top.empty:
        top = context.head(5)

    cards = []
    ledgers = []
    full_rows = []

    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        player_raw = str(row.get("Player") or "WNBA Player")
        player = escape(player_raw)
        team = escape(str(row.get("team_name") or "Team"))
        opponent = escape(str(row.get("opponent") or "Opponent"))
        decision = escape(str(row.get("Decision") or "PREVIEW"))

        team_logo = escape(h2h._logo(row.get("TEAM_ID")), quote=True)
        opp_logo = escape(h2h._logo(row.get("opponent_team_id")), quote=True)
        team_img = f'<img src="{team_logo}" alt="team logo">' if team_logo else "🏀"
        opp_img = f'<img src="{opp_logo}" alt="opponent logo">' if opp_logo else "🏀"
        player_photo = photos._photo_html(
            row.get("PLAYER_ID"), row.get("TEAM_ID"), player_raw, "kyre-v19846-photo"
        )

        line = _num(row.get("line"), np.nan)
        projection = _num(row.get("Proj PTS"), np.nan)
        match = _player_meetings(str(day), row)
        summary = _meeting_summary(match, line, projection)
        label, label_class = _context_read(summary, line)

        gp = int(summary.get("games") or 0)
        avg = _split(summary.get("avg_pts"))
        l3 = _split(summary.get("l3_pts"))
        avg_min = _split(summary.get("avg_min"))
        hit_rate = _num(summary.get("hit_rate"), np.nan)
        hit_text = "—" if pd.isna(hit_rate) else f"{int(summary.get('over_hits') or 0)}/{gp} • {hit_rate*100:.0f}%"
        split = f"H {_split(summary.get('home_avg'))} • A {_split(summary.get('away_avg'))}"
        last = (
            "—"
            if gp == 0
            else f"{_split(summary.get('last_pts'),0)} PTS • {_split(summary.get('last_min'),1)} MIN • {summary.get('last_date','—')}"
        )
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
<div class="kyre-v19846-card">
  <div class="kyre-v19846-top"><span>🆚 H2H #{rank}</span><span>{decision}</span></div>
  <div class="kyre-v19846-id">
    <div class="kyre-v19846-photo-shell">{player_photo}</div>
    <div>
      <div class="kyre-v19846-player">{player}</div>
      <div class="kyre-v19846-match"><span>{team_img}{team}</span><b>vs</b><span>{opp_img}{opponent}</span></div>
    </div>
  </div>
  <div class="kyre-v19846-line">Today O {line_text} • Proj {proj_text}{(" • " + books) if books else ""}</div>
  <div class="kyre-v19846-read {label_class}">{escape(label)}</div>
  <div class="kyre-v19846-grid">
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
  <div class="kyre-v19846-sample {('good' if gp >= 3 else 'warn')}">{sample} • descriptive only</div>
</div>
""")

        ledger = _ledger_frame(match, line)
        ledgers.append((rank, player_raw, ledger, label))

        full_rows.append({
            "Rank": rank,
            "Player": player_raw,
            "Team": row.get("team_name"),
            "Opponent": row.get("opponent"),
            "Today line": round(line, 1) if pd.notna(line) else np.nan,
            "Proj PTS": round(projection, 2) if pd.notna(projection) else np.nan,
            "H2H GP": gp,
            "Avg PTS": round(_num(summary.get("avg_pts"), np.nan), 1)
            if pd.notna(_num(summary.get("avg_pts"), np.nan)) else np.nan,
            "L3 vs opp": round(_num(summary.get("l3_pts"), np.nan), 1)
            if pd.notna(_num(summary.get("l3_pts"), np.nan)) else np.nan,
            "Over today line": hit_text,
            "Avg margin": round(avg_margin, 1) if pd.notna(avg_margin) else np.nan,
            "PTS range": range_text,
            "Context read": label,
            "Sample": summary.get("sample"),
        })

    st.markdown(
        """
<style>
.kyre-v19846-wrap{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:8px 0 14px}
.kyre-v19846-card{background:linear-gradient(145deg,#0b2034,#081521);border:1px solid #315c78;border-radius:22px;padding:18px;box-shadow:0 8px 22px rgba(0,0,0,.18)}
.kyre-v19846-top{display:flex;justify-content:space-between;gap:8px;color:#64ddff;font-size:.67rem;font-weight:950;letter-spacing:.06em;text-transform:uppercase}
.kyre-v19846-id{display:flex;align-items:center;gap:14px;margin:12px 0 8px}
.kyre-v19846-photo-shell{width:76px;height:76px;min-width:76px;border-radius:50%;overflow:hidden;background:radial-gradient(circle at 50% 35%,#173650,#071522 72%);border:1px solid #326281;display:flex;align-items:center;justify-content:center}
.kyre-v19846-photo{width:100%;height:100%;object-fit:cover;object-position:center 18%}
.kyre-v19846-photo.fallback{object-fit:contain;padding:10px}
.kyre-player-placeholder{font-size:1.7rem}
.kyre-v19846-player{font-size:1.24rem;font-weight:950;color:white;margin:0 0 6px}
.kyre-v19846-match{display:flex;align-items:center;gap:8px;color:#a7bbca;font-size:.78rem;flex-wrap:wrap}
.kyre-v19846-match span{display:flex;align-items:center;gap:5px}
.kyre-v19846-match img{width:25px;height:25px;object-fit:contain}
.kyre-v19846-line{color:#8ea8bd;font-size:.72rem;margin:8px 0 11px}
.kyre-v19846-read{border-radius:11px;padding:8px 10px;font-size:.64rem;font-weight:950;letter-spacing:.035em;margin:0 0 11px}
.kyre-v19846-read.good{background:#0a3025;border:1px solid #1d7554;color:#75efb4}
.kyre-v19846-read.bad{background:#35171b;border:1px solid #7a3941;color:#ff9aa5}
.kyre-v19846-read.warn{background:#3a3009;border:1px solid #756313;color:#ffe17a}
.kyre-v19846-read.neutral{background:#10263a;border:1px solid #31526c;color:#9fd7fa}
.kyre-v19846-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.kyre-v19846-grid div{border:1px solid #244760;border-radius:11px;padding:9px;background:#091827}
.kyre-v19846-grid .wide{grid-column:span 2}
.kyre-v19846-grid small{display:block;color:#718ba0;font-size:.52rem;font-weight:900;letter-spacing:.05em}
.kyre-v19846-grid strong{display:block;color:#f6fbff;font-size:.89rem;margin-top:3px}
.kyre-v19846-sample{display:inline-block;margin-top:11px;border-radius:999px;padding:5px 8px;font-size:.59rem;font-weight:900;letter-spacing:.04em}
.kyre-v19846-sample.good{background:#0c3b2c;color:#72efb1;border:1px solid #217956}
.kyre-v19846-sample.warn{background:#3a3009;color:#ffe17a;border:1px solid #756313}
@media(max-width:760px){.kyre-v19846-wrap{grid-template-columns:1fr}.kyre-v19846-photo-shell{width:70px;height:70px;min-width:70px}}
</style>
<div class="kyre-v19846-wrap">""" + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### 🧾 Meeting-by-meeting audit")
    st.caption(
        "Every row below is a verified prior meeting used in the visible H2H summary. "
        "Result compares that historical point total to today's current Points line only."
    )
    for rank, player_name, ledger, label in ledgers:
        with st.expander(f"🆚 H2H #{rank} • {player_name} — meeting ledger", expanded=False):
            if ledger.empty:
                st.info("No prior current-season meeting is available for this player/current-team matchup.")
            else:
                st.dataframe(ledger, use_container_width=True, hide_index=True)
            st.caption(f"Context read: {label} • descriptive only • no model adjustment")

    with st.expander("📚 Top-5 player-vs-team history summary", expanded=False):
        st.dataframe(pd.DataFrame(full_rows), use_container_width=True, hide_index=True)
        st.caption(
            "Source: verified completed ESPN WNBA game summaries • current season/current team vs today's opponent • "
            "exact SportsGameOdds Points line used only for descriptive historical comparison."
        )


def _install() -> None:
    photos._render_h2h_cards_with_photos = _render_top5_h2h_evidence
    h2h._render_h2h_cards = _render_top5_h2h_evidence


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🆚 Points V1.9.8.4.6 • Top-5 player-vs-team history evidence ACTIVE • "
        "current-season H2H remains descriptive and cannot alter model math"
    )
    return prior.render_wnba_points_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH",
    "POINTS_FROZEN_BRANCH", "POINTS_FROZEN_COMMIT", "render_wnba_points_hub",
]
