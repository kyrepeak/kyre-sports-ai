"""WNBA Points V1.9.4 — visual Step 2: player-vs-team history.

Presentation/data-context wrapper over the validated V1.9.2/V1.9.3 Points stack.
Adds current-season player-vs-current-opponent history to the visual command
center. H2H is descriptive only: it does not alter minutes, usage, matchup
factors, projections, SportsGameOdds grading, Monte Carlo, calibration, or the
final decision hierarchy.

History source: verified completed ESPN WNBA game summaries for prior meetings
between the player's current team and today's opponent before the selected slate
date. Small samples are explicitly labeled. Frozen WNBA PRA V3.2.1 and MLB
V2.1.7 remain untouched.
"""
from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v193 as visual
import wnba_points_v19 as points
import wnba_points_v13 as roster_mod
import wnba_players_v25 as players
import wnba_sportsgameodds_v1 as sgo1

MODEL_VERSION = "WNBA POINTS V1.9.4 • PLAYER VS TEAM HISTORY"
PRA_FROZEN_BRANCH = visual.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = visual.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = visual.MLB_FROZEN_BRANCH
core = visual.core


def _day(value) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _norm(value) -> str:
    try:
        return sgo1._norm(value)
    except Exception:
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _logo(team_id):
    return visual._logo(team_id)


@st.cache_data(ttl=1800, show_spinner=False, max_entries=64)
def _matchup_box_history(day_str: str, team_id: int, opponent_team_id: int):
    """Verified current-season prior H2H box rows for one current-team matchup."""
    day_str = _day(day_str)
    tid = int(team_id or 0)
    oid = int(opponent_team_id or 0)
    if not tid or not oid or tid == oid:
        return pd.DataFrame()

    try:
        history = roster_mod._season_history(day_str, {tid, oid})
    except Exception:
        history = pd.DataFrame()
    if history is None or history.empty:
        return pd.DataFrame()

    away = pd.to_numeric(history.get("away_team_id"), errors="coerce").fillna(0).astype(int)
    home = pd.to_numeric(history.get("home_team_id"), errors="coerce").fillna(0).astype(int)
    h2h = history.loc[((away.eq(tid) & home.eq(oid)) | (away.eq(oid) & home.eq(tid)))].copy()
    if h2h.empty:
        return pd.DataFrame()
    h2h["_d"] = pd.to_datetime(h2h.get("game_date"), errors="coerce")
    h2h = h2h.sort_values("_d", ascending=False).drop_duplicates("game_id").head(10)

    frames = []
    for _, game in h2h.iterrows():
        gid = str(game.get("game_id") or "")
        gdate = str(game.get("game_date") or "")
        if not gid:
            continue
        try:
            box = players._espn_game_summary(gid, gdate)
        except Exception:
            box = pd.DataFrame()
        if box is None or box.empty or "TEAM_ID" not in box.columns:
            continue
        part = box.loc[pd.to_numeric(box["TEAM_ID"], errors="coerce").eq(tid)].copy()
        if part.empty:
            continue
        part["_H2H_GAME_ID"] = gid
        part["_H2H_DATE"] = gdate
        part["_H2H_HOME"] = bool(int(_num(game.get("home_team_id"), 0)) == tid)
        frames.append(part)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    return out


def _player_h2h_profile(day_str, player_id, player_name, team_id, opponent_team_id, today_line):
    box = _matchup_box_history(_day(day_str), int(team_id or 0), int(opponent_team_id or 0))
    if box is None or box.empty:
        return {"games": 0, "sample": "NO PRIOR MEETINGS"}

    target_id = str(player_id or "").strip()
    target_name = _norm(player_name)
    match = pd.DataFrame()
    if target_id and "PLAYER_ID" in box.columns:
        match = box.loc[box["PLAYER_ID"].astype(str).eq(target_id)].copy()
    if match.empty and target_name and "PLAYER_NAME" in box.columns:
        match = box.loc[box["PLAYER_NAME"].map(_norm).eq(target_name)].copy()
    if match.empty:
        return {"games": 0, "sample": "NO PRIOR MEETINGS"}

    match["PTS"] = pd.to_numeric(match.get("PTS"), errors="coerce")
    match["MIN"] = pd.to_numeric(match.get("MIN"), errors="coerce")
    match["_DATE"] = pd.to_datetime(match.get("_H2H_DATE"), errors="coerce")
    match = match.dropna(subset=["PTS"]).sort_values("_DATE", ascending=False)
    match = match.drop_duplicates("_H2H_GAME_ID", keep="first").head(10)
    if match.empty:
        return {"games": 0, "sample": "NO PRIOR MEETINGS"}

    gp = int(len(match))
    line = _num(today_line, np.nan)
    if pd.notna(line):
        overs = int((match["PTS"] > line).sum())
        pushes = int((match["PTS"] == line).sum())
        hit_rate = overs / gp if gp else np.nan
    else:
        overs = pushes = 0
        hit_rate = np.nan

    home_pts = match.loc[match.get("_H2H_HOME", False).astype(bool), "PTS"] if "_H2H_HOME" in match.columns else pd.Series(dtype=float)
    away_pts = match.loc[~match.get("_H2H_HOME", False).astype(bool), "PTS"] if "_H2H_HOME" in match.columns else pd.Series(dtype=float)
    last = match.iloc[0]
    last_date = last.get("_DATE")
    return {
        "games": gp,
        "avg_pts": float(match["PTS"].mean()),
        "l3_pts": float(match.head(3)["PTS"].mean()) if gp >= 3 else np.nan,
        "avg_min": float(match["MIN"].mean()) if match["MIN"].notna().any() else np.nan,
        "over_hits": overs,
        "pushes": pushes,
        "hit_rate": hit_rate,
        "home_avg": float(home_pts.mean()) if len(home_pts) else np.nan,
        "away_avg": float(away_pts.mean()) if len(away_pts) else np.nan,
        "last_pts": float(last.get("PTS")),
        "last_min": _num(last.get("MIN"), np.nan),
        "last_date": last_date.strftime("%b %d") if pd.notna(last_date) else "—",
        "sample": "USEFUL CONTEXT" if gp >= 3 else "SMALL SAMPLE",
    }


def _consensus_line_rows(pairs: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(pairs, pd.DataFrame) or pairs.empty:
        return pd.DataFrame()
    work = pairs.copy()
    for col in ("game_id", "player_key", "player", "book"):
        if col not in work.columns:
            work[col] = ""
    work["line"] = pd.to_numeric(work.get("line"), errors="coerce")
    work = work.dropna(subset=["line"])
    if work.empty:
        return pd.DataFrame()

    rows = []
    for (gid, pkey), grp in work.groupby(["game_id", "player_key"], dropna=False):
        counts = grp["line"].value_counts(dropna=True)
        if counts.empty:
            continue
        max_count = int(counts.max())
        tied = sorted(float(x) for x in counts[counts.eq(max_count)].index)
        if len(tied) == 1:
            line = tied[0]
        else:
            med = float(grp["line"].median())
            line = min(tied, key=lambda x: abs(x - med))
        chosen = grp.loc[grp["line"].eq(line)].copy()
        books = ", ".join(sorted({str(x) for x in chosen["book"] if str(x).strip()}))
        name = str(chosen.iloc[0].get("player") or "")
        rows.append({
            "game_id": str(gid), "player_key": str(pkey), "player": name,
            "line": float(line), "books": books, "book_count": int(len(chosen)),
        })
    return pd.DataFrame(rows)


def _history_context_rows(day: str):
    try:
        projections, pairs, _, _, _ = points._prepare(day)
    except Exception:
        return pd.DataFrame()
    if not isinstance(projections, pd.DataFrame) or projections.empty:
        return pd.DataFrame()
    market = _consensus_line_rows(pairs)
    if market.empty:
        return pd.DataFrame()

    p = projections.copy()
    p["game_id"] = p.get("game_id", "").astype(str)
    p["player_key"] = p.get("player_key", "").astype(str)
    keep = [
        "game_id", "player_key", "PLAYER_ID", "PLAYER_NAME", "TEAM_ID", "team_name",
        "opponent_team_id", "opponent", "PROJ_PTS", "PROJ_MIN", "POSITION",
    ]
    for col in keep:
        if col not in p.columns:
            p[col] = np.nan if col not in {"game_id", "player_key", "PLAYER_NAME", "team_name", "opponent", "POSITION"} else ""
    p = p[keep].drop_duplicates(["game_id", "player_key"], keep="first")
    merged = market.merge(p, on=["game_id", "player_key"], how="inner")
    if merged.empty:
        return merged
    merged["Proj PTS"] = pd.to_numeric(merged.get("PROJ_PTS"), errors="coerce")
    merged["Proj MIN"] = pd.to_numeric(merged.get("PROJ_MIN"), errors="coerce")
    merged["Delta"] = merged["Proj PTS"] - pd.to_numeric(merged.get("line"), errors="coerce")
    merged["Player"] = merged["PLAYER_NAME"].astype(str).where(merged["PLAYER_NAME"].astype(str).str.len().gt(0), merged["player"].astype(str))
    return merged


def _candidate_order(day: str, context: pd.DataFrame) -> pd.DataFrame:
    if context.empty:
        return context
    work = context.copy()
    work["_rank"] = pd.to_numeric(work.get("Delta"), errors="coerce").fillna(-999.0)
    work["Decision"] = "PREVIEW"
    try:
        sims = points.combined_rows(day)
    except Exception:
        sims = pd.DataFrame()
    if isinstance(sims, pd.DataFrame) and not sims.empty and {"game_id", "player_key", "line"}.issubset(sims.columns):
        s = sims.copy()
        s["line"] = pd.to_numeric(s.get("line"), errors="coerce")
        s["model_over"] = pd.to_numeric(s.get("model_over"), errors="coerce")
        s["edge"] = pd.to_numeric(s.get("edge"), errors="coerce")
        s["sims"] = pd.to_numeric(s.get("sims"), errors="coerce").fillna(0)
        s = s.sort_values(["sims", "model_over", "edge"], ascending=[False, False, False])
        s = s.drop_duplicates(["game_id", "player_key", "line"], keep="first")
        try:
            s["Decision"] = s.apply(core._calibrated_decision_tier, axis=1)
            vals = s.apply(core._calibrated_values, axis=1, result_type="expand")
            vals.columns = ["_raw", "_buf", "_floor", "_cedge"]
            s["_rank"] = vals["_floor"] * 100.0 + vals["_cedge"].fillna(-1.0) * 10.0
        except Exception:
            s["Decision"] = np.where(s.get("model_qualified", False), "⚠️ MONITOR", "⛔ AVOID")
            s["_rank"] = s["model_over"].fillna(0) * 100.0 + s["edge"].fillna(-1.0) * 10.0
        sim_keep = s[["game_id", "player_key", "line", "Decision", "_rank"]].copy()
        work = work.merge(sim_keep, on=["game_id", "player_key", "line"], how="left", suffixes=("", "_sim"))
        if "Decision_sim" in work.columns:
            work["Decision"] = work["Decision_sim"].fillna(work["Decision"])
        if "_rank_sim" in work.columns:
            work["_rank"] = work["_rank_sim"].fillna(work["_rank"])
    return work.sort_values("_rank", ascending=False)


def _split_text(value):
    return "—" if pd.isna(value) else f"{float(value):.1f}"


def _render_h2h_cards(day: str):
    context = _candidate_order(day, _history_context_rows(day))
    st.markdown("### 🆚 Player vs Team History")
    st.caption(
        "Current-season prior meetings between the player's current team and today's opponent. "
        "Descriptive context only — H2H does not change the Points projection or Monte Carlo."
    )
    if context.empty:
        st.info("Player-vs-team history is waiting on the verified Points projection + exact-market handoff.")
        return

    detailed = []
    top = context.loc[~context["Decision"].astype(str).str.contains("AVOID", na=False)].head(5)
    if top.empty:
        top = context.head(5)

    cards = []
    for rank, (_, row) in enumerate(top.iterrows(), start=1):
        profile = _player_h2h_profile(
            day, row.get("PLAYER_ID"), row.get("Player"), int(_num(row.get("TEAM_ID"), 0)),
            int(_num(row.get("opponent_team_id"), 0)), row.get("line"),
        )
        team_logo = escape(_logo(row.get("TEAM_ID")), quote=True)
        opp_logo = escape(_logo(row.get("opponent_team_id")), quote=True)
        team_img = f'<img src="{team_logo}" alt="team logo">' if team_logo else "🏀"
        opp_img = f'<img src="{opp_logo}" alt="opponent logo">' if opp_logo else "🏀"
        gp = int(profile.get("games") or 0)
        avg = _split_text(profile.get("avg_pts"))
        l3 = _split_text(profile.get("l3_pts"))
        mins = _split_text(profile.get("avg_min"))
        hit = "—" if pd.isna(profile.get("hit_rate", np.nan)) else f"{profile.get('hit_rate')*100:.0f}%"
        split = f"H {_split_text(profile.get('home_avg'))} • A {_split_text(profile.get('away_avg'))}"
        last = "—" if gp == 0 else f"{profile.get('last_pts',0):.0f} PTS • {profile.get('last_date','—')}"
        sample = str(profile.get("sample") or "SMALL SAMPLE")
        decision = escape(str(row.get("Decision") or "PREVIEW"))
        player = escape(str(row.get("Player") or "Player"))
        team = escape(str(row.get("team_name") or ""))
        opp = escape(str(row.get("opponent") or ""))
        books = escape(str(row.get("books") or ""))
        line = _num(row.get("line"), np.nan)
        proj = _num(row.get("Proj PTS"), np.nan)
        sample_class = "good" if gp >= 3 else "warn"
        cards.append(f"""
<div class="kyre-h2h-card">
  <div class="kyre-h2h-top"><span>🆚 H2H #{rank}</span><span>{decision}</span></div>
  <div class="kyre-h2h-player">{player}</div>
  <div class="kyre-h2h-match"><span>{team_img} {team}</span><b>vs</b><span>{opp_img} {opp}</span></div>
  <div class="kyre-h2h-line">Today O {line:g} • Proj {proj:.2f} • {books}</div>
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
        """)

    st.markdown(
        """
<style>
.kyre-h2h-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin:8px 0 14px}
.kyre-h2h-card{background:linear-gradient(145deg,#0b2034,#081521);border:1px solid #29526d;border-radius:20px;padding:17px;box-shadow:0 8px 22px rgba(0,0,0,.18)}
.kyre-h2h-top{display:flex;justify-content:space-between;gap:8px;color:#64ddff;font-size:.67rem;font-weight:900;letter-spacing:.06em;text-transform:uppercase}
.kyre-h2h-player{font-size:1.22rem;font-weight:950;color:white;margin:10px 0 8px}
.kyre-h2h-match{display:flex;align-items:center;gap:8px;color:#a7bbca;font-size:.78rem;flex-wrap:wrap}.kyre-h2h-match span{display:flex;align-items:center;gap:5px}.kyre-h2h-match img{width:25px;height:25px;object-fit:contain}
.kyre-h2h-line{color:#88a2b8;font-size:.72rem;margin:8px 0 12px}
.kyre-h2h-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.kyre-h2h-metrics div{border:1px solid #244760;border-radius:11px;padding:9px;background:#091827}.kyre-h2h-metrics .wide{grid-column:span 3}.kyre-h2h-metrics small{display:block;color:#718ba0;font-size:.55rem;font-weight:850;letter-spacing:.05em}.kyre-h2h-metrics strong{display:block;color:#f6fbff;font-size:.92rem;margin-top:3px}
.kyre-h2h-sample{display:inline-block;margin-top:11px;border-radius:999px;padding:5px 8px;font-size:.59rem;font-weight:900;letter-spacing:.04em}.kyre-h2h-sample.good{background:#0c3b2c;color:#72efb1;border:1px solid #217956}.kyre-h2h-sample.warn{background:#3a3009;color:#ffe17a;border:1px solid #756313}
@media(max-width:760px){.kyre-h2h-grid{grid-template-columns:1fr}.kyre-h2h-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.kyre-h2h-metrics .wide{grid-column:span 2}}
</style>
<div class="kyre-h2h-grid">""" + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )

    # Full exact-market history board remains collapsed to keep the page clean.
    for _, row in context.iterrows():
        profile = _player_h2h_profile(
            day, row.get("PLAYER_ID"), row.get("Player"), int(_num(row.get("TEAM_ID"), 0)),
            int(_num(row.get("opponent_team_id"), 0)), row.get("line"),
        )
        detailed.append({
            "Player": row.get("Player"), "Team": row.get("team_name"), "Opponent": row.get("opponent"),
            "Today line": row.get("line"), "Proj PTS": round(_num(row.get("Proj PTS"), np.nan), 2),
            "H2H GP": int(profile.get("games") or 0),
            "Avg PTS": round(_num(profile.get("avg_pts"), np.nan), 1) if pd.notna(_num(profile.get("avg_pts"), np.nan)) else np.nan,
            "L3 vs opp": round(_num(profile.get("l3_pts"), np.nan), 1) if pd.notna(_num(profile.get("l3_pts"), np.nan)) else np.nan,
            "Avg MIN": round(_num(profile.get("avg_min"), np.nan), 1) if pd.notna(_num(profile.get("avg_min"), np.nan)) else np.nan,
            "Over line": "—" if pd.isna(profile.get("hit_rate", np.nan)) else f"{profile.get('over_hits',0)}/{profile.get('games',0)} ({profile.get('hit_rate')*100:.0f}%)",
            "Last": "—" if not profile.get("games") else f"{profile.get('last_pts',0):.0f} • {profile.get('last_date','—')}",
            "Sample": profile.get("sample"),
        })
    with st.expander("📚 Full player-vs-team history board", expanded=False):
        st.dataframe(pd.DataFrame(detailed), use_container_width=True, hide_index=True)
        st.caption("Source: verified completed ESPN WNBA game summaries • current season/current team vs today's opponent • exact SportsGameOdds Points line used only for the descriptive hit-rate comparison.")


def _visual_header_v194(day, slate):
    visual._visual_header(day, slate)
    _render_h2h_cards(_day(day))


# Route-proof hook: V1.9.1 resets this function on every rerun, so V1.9.4 owns
# the same inherited header hook and delegates directly to the V1.9.2 core.
core.clean._clean_header = _visual_header_v194


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    core.clean._clean_header = _visual_header_v194
    return core.render_wnba_points_hub(section_header, status_info, team_logo, h)


__all__ = [
    "MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT",
    "MLB_FROZEN_BRANCH", "render_wnba_points_hub",
]
