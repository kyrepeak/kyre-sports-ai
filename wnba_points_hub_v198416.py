"""WNBA Points V1.9.8.4.16 — Step 7 verified shooting transport fallback.

Presentation/context-only wrapper over V1.9.8.4.15. The protected V1.9.8.4.5
Points projection, sportsbook transport, Monte Carlo, calibration, candidate
hierarchy, persistence, readiness gates and sanity quarantine remain unchanged.

V1.9.8.4.15 preferred WNBA/NBA Stats Base tables for FGA/3PA/FTA and shooting
percentages. On Streamlit Cloud those stats hosts can return an empty/blocked
response, leaving Step 7 entirely blank. V1.9.8.4.16 keeps that official Base
path first, then fail-soft rebuilds season/L10/L5 shooting volume and efficiency
from verified ESPN WNBA final-game box scores before the selected slate date.
No shooting value is inferred when neither source publishes it.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198415 as prior
import wnba_points_v13 as roster_mod
import wnba_players_v25 as players
import wnba_schedule_v24 as schedule_v24

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points

MODEL_VERSION = "WNBA POINTS V1.9.8.4.16 • STEP 7 ESPN VERIFIED SHOOTING FALLBACK"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

_ORIGINAL_STEP7_BLOCK = prior._step7_block


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _fmt(value, digits=1, suffix="") -> str:
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}{suffix}"


def _pct(value, digits=1) -> str:
    x = _num(value, np.nan)
    if pd.isna(x):
        return "—"
    if abs(x) <= 1.5:
        x *= 100.0
    return f"{x:.{digits}f}%"


def _made_attempted(value):
    """Parse ESPN basketball made-attempted cells such as 6-14."""
    if isinstance(value, dict):
        made = _num(value.get("made"), np.nan)
        att = _num(value.get("attempted"), np.nan)
        return made, att
    text = str(value or "").strip().replace("–", "-").replace("—", "-")
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", text)
    if not m:
        return np.nan, np.nan
    return _num(m.group(1), np.nan), _num(m.group(2), np.nan)


def _pick(stats: dict, aliases):
    for alias in aliases:
        key = str(alias).upper()
        if key in stats and stats[key] not in (None, ""):
            return stats[key]
    return None


def _pair_from_stats(stats: dict, pair_aliases, made_aliases, att_aliases):
    raw = _pick(stats, pair_aliases)
    made, att = _made_attempted(raw)
    if pd.notna(made) and pd.notna(att):
        return made, att
    made = _num(_pick(stats, made_aliases), np.nan)
    att = _num(_pick(stats, att_aliases), np.nan)
    return made, att


@st.cache_data(ttl=1800, show_spinner=False, max_entries=256)
def _espn_raw_summary(game_id: str):
    try:
        payload, _meta = schedule_v24._request_json(
            "ESPN WNBA Step-7 shooting fallback",
            players.ESPN_SUMMARY,
            params={"event": str(game_id)},
            timeout=8,
            attempts=2,
        )
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _shooting_row_from_payload(payload: dict, team_id: int, player_id: int, game_date="") -> dict:
    if not isinstance(payload, dict):
        return {}
    wanted_team = int(team_id)
    wanted_player = int(player_id)
    for team_block in (payload.get("boxscore") or {}).get("players", []) or []:
        team = team_block.get("team") or {}
        try:
            tid = int(players._team_id(team) or 0)
        except Exception:
            tid = 0
        if tid != wanted_team:
            continue
        for group in team_block.get("statistics", []) or []:
            athletes = group.get("athletes") or []
            if not athletes:
                continue
            for item in athletes:
                athlete = item.get("athlete") or {}
                try:
                    pid = int(athlete.get("id") or 0)
                except Exception:
                    pid = 0
                if pid != wanted_player or bool(item.get("didNotPlay")):
                    continue
                stats = players._summary_stat_map(group, item)
                fgm, fga = _pair_from_stats(
                    stats,
                    ["FG", "FGM-A", "FIELDGOALSMADE-FIELDGOALSATTEMPTED", "FIELD GOALS"],
                    ["FGM", "FIELDGOALSMADE"],
                    ["FGA", "FIELDGOALSATTEMPTED"],
                )
                fg3m, fg3a = _pair_from_stats(
                    stats,
                    ["3PT", "3PM-A", "FG3M-A", "THREEPOINTFIELDGOALSMADE-THREEPOINTFIELDGOALSATTEMPTED", "3-PT"],
                    ["3PM", "FG3M", "THREEPOINTFIELDGOALSMADE"],
                    ["3PA", "FG3A", "THREEPOINTFIELDGOALSATTEMPTED"],
                )
                ftm, fta = _pair_from_stats(
                    stats,
                    ["FT", "FTM-A", "FREETHROWSMADE-FREETHROWSATTEMPTED", "FREE THROWS"],
                    ["FTM", "FREETHROWSMADE"],
                    ["FTA", "FREETHROWSATTEMPTED"],
                )
                pts = _num(_pick(stats, ["PTS", "POINTS"]), np.nan)
                mins = players._minutes(_pick(stats, ["MIN", "MINUTES"]))
                if pd.isna(fga) and pd.isna(fg3a) and pd.isna(fta):
                    return {}
                return {
                    "GAME_DATE": pd.to_datetime(game_date, errors="coerce"),
                    "FGM": fgm, "FGA": fga,
                    "FG3M": fg3m, "FG3A": fg3a,
                    "FTM": ftm, "FTA": fta,
                    "PTS": pts, "MIN": mins,
                }
            # The first athlete-bearing group is the normal box-score group.
            if athletes:
                break
    return {}


@st.cache_data(ttl=1800, show_spinner=False, max_entries=128)
def _espn_player_shooting_history(day_str: str, team_id: int, player_id: int) -> pd.DataFrame:
    """Season-to-date verified shooting log for one player before day_str."""
    try:
        day_str = pd.to_datetime(day_str).strftime("%Y-%m-%d")
        tid = int(team_id)
        pid = int(player_id)
    except Exception:
        return pd.DataFrame()
    if not tid or not pid:
        return pd.DataFrame()

    try:
        history = roster_mod._season_history(day_str, {tid})
    except Exception:
        history = pd.DataFrame()
    if history is None or history.empty:
        return pd.DataFrame()

    games = history.loc[
        history["away_team_id"].astype(int).eq(tid)
        | history["home_team_id"].astype(int).eq(tid)
    ].copy()
    if games.empty:
        return pd.DataFrame()
    games["_DATE"] = pd.to_datetime(games.get("game_date"), errors="coerce")
    games = (
        games.sort_values("_DATE", ascending=False)
        .drop_duplicates("game_id", keep="first")
    )

    jobs = [
        (str(r.get("game_id") or ""), str(r.get("game_date") or ""))
        for _, r in games.iterrows()
        if str(r.get("game_id") or "")
    ]
    rows = []
    # Game summaries are cached by game id, so shared-team Top-5 players reuse
    # the same network payloads after the first card.
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(jobs)))) as pool:
        futures = {
            pool.submit(_espn_raw_summary, gid): (gid, gdate)
            for gid, gdate in jobs
        }
        for future in as_completed(futures):
            gid, gdate = futures[future]
            try:
                payload = future.result()
                row = _shooting_row_from_payload(payload, tid, pid, gdate)
            except Exception:
                row = {}
            if row:
                row["GAME_ID"] = gid
                rows.append(row)

    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame["GAME_DATE"] = pd.to_datetime(frame.get("GAME_DATE"), errors="coerce")
    for col in ("FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "PTS", "MIN"):
        frame[col] = pd.to_numeric(frame.get(col), errors="coerce")
    return (
        frame.dropna(subset=["FGA"], how="all")
        .sort_values("GAME_DATE", ascending=False)
        .drop_duplicates("GAME_ID", keep="first")
        .reset_index(drop=True)
    )


def _aggregate_profile(frame: pd.DataFrame, n: int | None = None) -> dict:
    if frame is None or frame.empty:
        return {}
    part = frame.head(int(n)) if n else frame.copy()
    if part.empty:
        return {}
    out = {"GP": int(len(part))}
    for col in ("FGA", "FG3A", "FTA", "PTS", "MIN"):
        vals = pd.to_numeric(part.get(col), errors="coerce")
        out[col] = float(vals.mean()) if vals.notna().any() else np.nan
    for made_col, att_col, pct_col in (
        ("FGM", "FGA", "FG_PCT"),
        ("FG3M", "FG3A", "FG3_PCT"),
        ("FTM", "FTA", "FT_PCT"),
    ):
        made = pd.to_numeric(part.get(made_col), errors="coerce").sum(min_count=1)
        att = pd.to_numeric(part.get(att_col), errors="coerce").sum(min_count=1)
        out[made_col] = float(pd.to_numeric(part.get(made_col), errors="coerce").mean()) if pd.to_numeric(part.get(made_col), errors="coerce").notna().any() else np.nan
        out[pct_col] = float(made / att) if pd.notna(made) and pd.notna(att) and att > 0 else np.nan
    fga = _num(out.get("FGA"), np.nan)
    fta = _num(out.get("FTA"), np.nan)
    fgm = _num(out.get("FGM"), np.nan)
    fg3m = float(pd.to_numeric(part.get("FG3M"), errors="coerce").mean()) if pd.to_numeric(part.get("FG3M"), errors="coerce").notna().any() else np.nan
    pts = _num(out.get("PTS"), np.nan)
    if pd.notna(fga) and fga > 0 and pd.notna(fgm):
        out["EFG_PCT"] = (fgm + 0.5 * (fg3m if pd.notna(fg3m) else 0.0)) / fga
        out["FG3_SHARE"] = _num(out.get("FG3A"), np.nan) / fga if pd.notna(_num(out.get("FG3A"), np.nan)) else np.nan
        out["FTA_RATE"] = fta / fga if pd.notna(fta) else np.nan
    else:
        out["EFG_PCT"] = out["FG3_SHARE"] = out["FTA_RATE"] = np.nan
    denom = 2.0 * (fga + 0.44 * fta) if pd.notna(fga) and pd.notna(fta) else np.nan
    out["TS_PCT"] = pts / denom if pd.notna(pts) and pd.notna(denom) and denom > 0 else np.nan
    out["SHOT_OPP"] = fga + 0.44 * fta if pd.notna(fga) and pd.notna(fta) else np.nan
    out["SOURCE"] = f"ESPN WNBA verified box-score fallback • {len(part)} games"
    return out


def _official_profiles(day: str, player_id: int):
    try:
        season = int(pd.to_datetime(day).year)
        tables = prior._shooting_tables(season)
        season_p = prior._profile(prior._player_row(tables.get("season", pd.DataFrame()), player_id))
        l10_p = prior._profile(prior._player_row(tables.get("l10", pd.DataFrame()), player_id))
        l5_p = prior._profile(prior._player_row(tables.get("l5", pd.DataFrame()), player_id))
        return season_p, l10_p, l5_p
    except Exception:
        return {}, {}, {}


def _render_step7(season_p: dict, l10_p: dict, l5_p: dict, source_note: str) -> str:
    grade, grade_class, verdict, score, evidence_n, volume_trend, eff_trend = prior._grade(season_p, l10_p, l5_p)
    source = escape(str(source_note or l5_p.get("SOURCE") or l10_p.get("SOURCE") or season_p.get("SOURCE") or "VERIFIED SHOOTING FEED UNAVAILABLE"))
    html = f"""
<style>
.kyre-v198416-step7{{background:#171a25;border:1px solid #6b6f98;border-radius:15px;padding:12px;margin-top:10px}}
.kyre-v198416-head{{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#b8bfff;font-size:.61rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:9px}}
.kyre-v198416-grade{{border-radius:999px;padding:5px 8px;white-space:nowrap;font-size:.55rem}}
.kyre-v198416-grade.elite,.kyre-v198416-grade.strong{{background:#0b422f;color:#7df2ba;border:1px solid #237a59}}
.kyre-v198416-grade.neutral{{background:#3a3009;color:#ffe17a;border:1px solid #756313}}
.kyre-v198416-grade.tough{{background:#3a2616;color:#ffc984;border:1px solid #7c5832}}
.kyre-v198416-grade.hard{{background:#35171b;color:#ff9aa5;border:1px solid #7a3941}}
.kyre-v198416-grade.limited{{background:#1b2836;color:#a8c3d8;border:1px solid #405b70}}
.kyre-v198416-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}
.kyre-v198416-grid div{{border:1px solid #4e5275;border-radius:10px;padding:8px;background:#0d1019}}
.kyre-v198416-grid small{{display:block;color:#8d93bb;font-size:.48rem;font-weight:900;letter-spacing:.045em}}
.kyre-v198416-grid strong{{display:block;color:#f5f6ff;font-size:.84rem;margin-top:3px}}
.kyre-v198416-detail{{background:#0d1019;border:1px solid #4e5275;border-radius:10px;padding:8px 9px;color:#dcdef2;font-size:.68rem;line-height:1.55;margin-top:8px}}
.kyre-v198416-detail b{{color:#b8bfff}}
.kyre-v198416-verdict{{margin-top:8px;border-radius:10px;padding:8px 9px;background:#171b2d;border:1px solid #6b6f98;color:#f1f2ff;font-size:.68rem;font-weight:850}}
.kyre-v198416-note{{color:#8185a0;font-size:.57rem;line-height:1.4;margin-top:7px}}
@media(max-width:760px){{.kyre-v198416-head{{align-items:flex-start;flex-direction:column}}}}
</style>
<div class="kyre-v198416-step7">
<div class="kyre-v198416-head"><span>STEP 7 • SHOT VOLUME + SCORING EFFICIENCY</span><span class="kyre-v198416-grade {grade_class}">{escape(grade)}</span></div>
<div class="kyre-v198416-grid">
<div><small>SEASON FGA</small><strong>{_fmt(season_p.get('FGA'))}</strong></div><div><small>L10 FGA</small><strong>{_fmt(l10_p.get('FGA'))}</strong></div>
<div><small>L5 FGA</small><strong>{_fmt(l5_p.get('FGA'))}</strong></div><div><small>L5 SHOT OPPORTUNITY</small><strong>{_fmt(l5_p.get('SHOT_OPP'))}</strong></div>
<div><small>SEASON 3PA</small><strong>{_fmt(season_p.get('FG3A'))}</strong></div><div><small>L10 3PA</small><strong>{_fmt(l10_p.get('FG3A'))}</strong></div>
<div><small>L5 3PA</small><strong>{_fmt(l5_p.get('FG3A'))}</strong></div><div><small>L5 3PA SHARE</small><strong>{_pct(l5_p.get('FG3_SHARE'))}</strong></div>
<div><small>SEASON FTA</small><strong>{_fmt(season_p.get('FTA'))}</strong></div><div><small>L10 FTA</small><strong>{_fmt(l10_p.get('FTA'))}</strong></div>
<div><small>L5 FTA</small><strong>{_fmt(l5_p.get('FTA'))}</strong></div><div><small>L5 FTA RATE</small><strong>{_pct(l5_p.get('FTA_RATE'))}</strong></div>
<div><small>SEASON FG%</small><strong>{_pct(season_p.get('FG_PCT'))}</strong></div><div><small>L10 FG%</small><strong>{_pct(l10_p.get('FG_PCT'))}</strong></div>
<div><small>L5 FG%</small><strong>{_pct(l5_p.get('FG_PCT'))}</strong></div><div><small>L5 3P%</small><strong>{_pct(l5_p.get('FG3_PCT'))}</strong></div>
<div><small>L5 eFG%</small><strong>{_pct(l5_p.get('EFG_PCT'))}</strong></div><div><small>L5 TS%</small><strong>{_pct(l5_p.get('TS_PCT'))}</strong></div>
</div>
<div class="kyre-v198416-detail"><b>Volume trend</b> • {escape(volume_trend)}<br><b>Efficiency trend</b> • {escape(eff_trend)}<br><b>Scoring-profile audit</b> • {evidence_n}/4 available trend signals • score {score:+d}<br><b>Source</b> • {source}<br><b>Shot-location split</b> • rim/midrange location data is not inferred when neither verified feed exposes it</div>
<div class="kyre-v198416-verdict">Scoring profile • {escape(verdict)}</div>
<div class="kyre-v198416-note">Audit/context only • official WNBA/NBA Stats Base is preferred; verified ESPN WNBA final-game box scores are used only as a fail-soft transport fallback. Step 7 does not add or re-apply shot-volume/efficiency weight to the protected Points projection, Monte Carlo probability or Top-5 ordering.</div>
</div>
"""
    return prior.prior._compact_html(html)


def _step7_block(day: str, data: dict) -> str:
    try:
        player_id = int(float(data.get("PLAYER_ID")))
        team_id = int(float(data.get("TEAM_ID")))
    except Exception:
        player_id = team_id = 0

    season_p, l10_p, l5_p = _official_profiles(day, player_id) if player_id else ({}, {}, {})
    # Treat the official path as healthy only when it actually exposes attempt
    # volume for this player; percentages alone are insufficient for Step 7.
    if pd.notna(_num(l5_p.get("FGA"), np.nan)) or pd.notna(_num(l10_p.get("FGA"), np.nan)):
        source = str(l5_p.get("SOURCE") or l10_p.get("SOURCE") or season_p.get("SOURCE") or "WNBA Stats Base")
        return _render_step7(season_p, l10_p, l5_p, source)

    logs = _espn_player_shooting_history(day, team_id, player_id) if team_id and player_id else pd.DataFrame()
    if logs is not None and not logs.empty:
        season_p = _aggregate_profile(logs, None)
        l10_p = _aggregate_profile(logs, 10)
        l5_p = _aggregate_profile(logs, 5)
        source = str(l5_p.get("SOURCE") or "ESPN WNBA verified box-score fallback")
        return _render_step7(season_p, l10_p, l5_p, source)

    # Preserve the original transparent DATA LIMITED behavior if both verified
    # transports are unavailable.
    return _ORIGINAL_STEP7_BLOCK(day, data)


def _install() -> None:
    # V1.9.8.4.15's Step-6 combiner resolves its module-global _step7_block at
    # render time, so replacing this seam is enough to repair Step 7 only.
    prior._step7_block = _step7_block


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🎯 Points V1.9.8.4.16 • Step 7 verified shooting fallback ACTIVE • "
        "WNBA Stats primary → ESPN WNBA box-score fallback • protected model/ranking unchanged"
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
