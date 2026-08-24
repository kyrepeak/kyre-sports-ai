"""WNBA Points V1.9.8.4.22 — Step 9 opponent shot-profile defense matchup.

Presentation/context-only wrapper over V1.9.8.4.21. This adds a ninth audit
layer to the same Top-5 Points cards. It compares the player's verified recent
scoring-method profile (3PA share / free-throw pressure / efficiency) with the
opponent's verified season and L10 shooting profile allowed from ESPN WNBA final
box scores before the selected slate date.

Important firewall: Step 9 does not add a new multiplier, reweight the protected
Points projection, alter Monte Carlo probability, calibration, sportsbook data
or Top-5 order. Rim/midrange shot-location defense is never inferred when the
connected verified feeds do not publish it.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from html import escape
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_hub_v198421 as prior
import wnba_points_hub_v198418 as step8mod
import wnba_points_hub_v198416 as shooting
import wnba_players_v25 as players

base = prior.base
v171 = base.v171
ui = base.ui
points = base.points
v416 = step8mod.v416

MODEL_VERSION = "WNBA POINTS V1.9.8.4.22 • STEP 9 OPPONENT SHOT-PROFILE DEFENSE AUDIT"
PRA_FROZEN_BRANCH = base.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = base.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = base.MLB_FROZEN_BRANCH
POINTS_FROZEN_BRANCH = base.POINTS_FROZEN_BRANCH
POINTS_FROZEN_COMMIT = base.POINTS_FROZEN_COMMIT

# Use the genuine Step-7+8 combiner from V1.9.8.4.18. Its _step8_block global is
# still resolved at runtime, so V1.9.8.4.19-.21 repairs remain active.
_BASE_STEP7_PLUS_8 = step8mod._step7_plus_step8


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _fmt(value, digits=1, signed=False, suffix=""):
    x = _num(value, np.nan)
    if pd.isna(x):
        return "—"
    text = f"{x:+.{digits}f}" if signed else f"{x:.{digits}f}"
    return text + suffix


def _pct(value, digits=1, signed=False):
    x = _num(value, np.nan)
    if pd.isna(x):
        return "—"
    if abs(x) <= 1.5:
        x *= 100.0
    return f"{x:+.{digits}f}%" if signed else f"{x:.{digits}f}%"


def _compact_html(html: str) -> str:
    return re.sub(r">\s+<", "><", str(html or "").strip())


def _text(data: dict, keys, default=""):
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip() not in ("", "nan", "None"):
            return str(value).strip()
    return default


def _made_attempted(stats: dict, pair_aliases, made_aliases, att_aliases):
    return shooting._pair_from_stats(stats, pair_aliases, made_aliases, att_aliases)


def _team_shooting_from_payload(payload: dict, offense_team_id: int, game_date="") -> dict:
    """Aggregate one team's verified ESPN player box score into team totals."""
    if not isinstance(payload, dict):
        return {}
    try:
        wanted_team = int(offense_team_id)
    except Exception:
        return {}

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
            totals = {k: 0.0 for k in ("FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "PTS")}
            seen_any = False
            for item in athletes:
                if bool(item.get("didNotPlay")):
                    continue
                stats = players._summary_stat_map(group, item)
                fgm, fga = _made_attempted(
                    stats,
                    ["FG", "FGM-A", "FIELDGOALSMADE-FIELDGOALSATTEMPTED", "FIELD GOALS"],
                    ["FGM", "FIELDGOALSMADE"],
                    ["FGA", "FIELDGOALSATTEMPTED"],
                )
                fg3m, fg3a = _made_attempted(
                    stats,
                    ["3PT", "3PM-A", "FG3M-A", "THREEPOINTFIELDGOALSMADE-THREEPOINTFIELDGOALSATTEMPTED", "3-PT"],
                    ["3PM", "FG3M", "THREEPOINTFIELDGOALSMADE"],
                    ["3PA", "FG3A", "THREEPOINTFIELDGOALSATTEMPTED"],
                )
                ftm, fta = _made_attempted(
                    stats,
                    ["FT", "FTM-A", "FREETHROWSMADE-FREETHROWSATTEMPTED", "FREE THROWS"],
                    ["FTM", "FREETHROWSMADE"],
                    ["FTA", "FREETHROWSATTEMPTED"],
                )
                pts = _num(shooting._pick(stats, ["PTS", "POINTS"]), np.nan)
                values = {"FGM": fgm, "FGA": fga, "FG3M": fg3m, "FG3A": fg3a, "FTM": ftm, "FTA": fta, "PTS": pts}
                if any(pd.notna(_num(v, np.nan)) for v in values.values()):
                    seen_any = True
                for key, value in values.items():
                    x = _num(value, np.nan)
                    if pd.notna(x):
                        totals[key] += x
            if seen_any and totals["FGA"] > 0:
                totals["GAME_DATE"] = pd.to_datetime(game_date, errors="coerce")
                return totals
            break
    return {}


@st.cache_data(ttl=1800, show_spinner=False, max_entries=64)
def _opponent_shooting_allowed_history(day_str: str, defense_team_id: int) -> pd.DataFrame:
    """Verified season-to-date opponent shooting allowed before day_str."""
    try:
        day_str = pd.to_datetime(day_str).strftime("%Y-%m-%d")
        tid = int(defense_team_id)
    except Exception:
        return pd.DataFrame()
    if not tid:
        return pd.DataFrame()

    try:
        history = shooting.roster_mod._season_history(day_str, {tid})
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
    games = games.sort_values("_DATE", ascending=False).drop_duplicates("game_id", keep="first")

    jobs = []
    for _, row in games.iterrows():
        gid = str(row.get("game_id") or "")
        if not gid:
            continue
        away = int(_num(row.get("away_team_id"), 0))
        home = int(_num(row.get("home_team_id"), 0))
        offense_tid = home if away == tid else away
        if offense_tid:
            jobs.append((gid, str(row.get("game_date") or ""), offense_tid))

    rows = []
    with ThreadPoolExecutor(max_workers=min(10, max(1, len(jobs)))) as pool:
        futures = {pool.submit(shooting._espn_raw_summary, gid): (gid, gdate, oid) for gid, gdate, oid in jobs}
        for future in as_completed(futures):
            gid, gdate, offense_tid = futures[future]
            try:
                payload = future.result()
                row = _team_shooting_from_payload(payload, offense_tid, gdate)
            except Exception:
                row = {}
            if row:
                row["GAME_ID"] = gid
                rows.append(row)

    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    frame["GAME_DATE"] = pd.to_datetime(frame.get("GAME_DATE"), errors="coerce")
    for col in ("FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "PTS"):
        frame[col] = pd.to_numeric(frame.get(col), errors="coerce")
    return frame.sort_values("GAME_DATE", ascending=False).drop_duplicates("GAME_ID", keep="first").reset_index(drop=True)


def _aggregate_allowed(frame: pd.DataFrame, n: int | None = None) -> dict:
    if frame is None or frame.empty:
        return {}
    part = frame.head(int(n)) if n else frame.copy()
    if part.empty:
        return {}
    out = {"GP": int(len(part))}
    for col in ("FGA", "FG3A", "FTA", "PTS"):
        vals = pd.to_numeric(part.get(col), errors="coerce")
        out[col] = float(vals.mean()) if vals.notna().any() else np.nan

    fgm = pd.to_numeric(part.get("FGM"), errors="coerce").sum(min_count=1)
    fga = pd.to_numeric(part.get("FGA"), errors="coerce").sum(min_count=1)
    fg3m = pd.to_numeric(part.get("FG3M"), errors="coerce").sum(min_count=1)
    fg3a = pd.to_numeric(part.get("FG3A"), errors="coerce").sum(min_count=1)
    ftm = pd.to_numeric(part.get("FTM"), errors="coerce").sum(min_count=1)
    fta = pd.to_numeric(part.get("FTA"), errors="coerce").sum(min_count=1)
    pts = pd.to_numeric(part.get("PTS"), errors="coerce").sum(min_count=1)

    out["FG_PCT"] = fgm / fga if pd.notna(fgm) and pd.notna(fga) and fga > 0 else np.nan
    out["FG3_PCT"] = fg3m / fg3a if pd.notna(fg3m) and pd.notna(fg3a) and fg3a > 0 else np.nan
    out["FT_PCT"] = ftm / fta if pd.notna(ftm) and pd.notna(fta) and fta > 0 else np.nan
    out["EFG_PCT"] = (fgm + 0.5 * fg3m) / fga if pd.notna(fgm) and pd.notna(fg3m) and pd.notna(fga) and fga > 0 else np.nan
    out["FG3_SHARE"] = fg3a / fga if pd.notna(fg3a) and pd.notna(fga) and fga > 0 else np.nan
    out["FTA_RATE"] = fta / fga if pd.notna(fta) and pd.notna(fga) and fga > 0 else np.nan
    denom = 2.0 * (fga + 0.44 * fta) if pd.notna(fga) and pd.notna(fta) else np.nan
    out["TS_PCT"] = pts / denom if pd.notna(pts) and pd.notna(denom) and denom > 0 else np.nan
    return out


def _player_profiles(day: str, data: dict):
    try:
        pid = int(float(data.get("PLAYER_ID")))
        tid = int(float(data.get("TEAM_ID")))
    except Exception:
        pid = tid = 0
    season_p, l10_p, l5_p = shooting._official_profiles(day, pid) if pid else ({}, {}, {})
    if pd.notna(_num(l5_p.get("FGA"), np.nan)) or pd.notna(_num(l10_p.get("FGA"), np.nan)):
        source = str(l5_p.get("SOURCE") or l10_p.get("SOURCE") or season_p.get("SOURCE") or "WNBA Stats Base")
        return season_p, l10_p, l5_p, source
    logs = shooting._espn_player_shooting_history(day, tid, pid) if tid and pid else pd.DataFrame()
    if logs is not None and not logs.empty:
        season_p = shooting._aggregate_profile(logs, None)
        l10_p = shooting._aggregate_profile(logs, 10)
        l5_p = shooting._aggregate_profile(logs, 5)
        source = f"ESPN WNBA verified box-score fallback • season {len(logs)} G • L10 {min(10,len(logs))} G • L5 {min(5,len(logs))} G"
        return season_p, l10_p, l5_p, source
    return {}, {}, {}, "VERIFIED PLAYER SHOOTING PROFILE UNAVAILABLE"


def _method_label(l5_p: dict) -> str:
    share = _num(l5_p.get("FG3_SHARE"), np.nan)
    ftr = _num(l5_p.get("FTA_RATE"), np.nan)
    if pd.notna(share) and share >= 0.45 and pd.notna(ftr) and ftr >= 0.30:
        return "PERIMETER + FT PRESSURE"
    if pd.notna(share) and share >= 0.45:
        return "PERIMETER-HEAVY"
    if pd.notna(ftr) and ftr >= 0.35:
        return "FREE-THROW PRESSURE"
    if pd.notna(share) and share <= 0.25:
        return "TWO-POINT HEAVY"
    if pd.notna(share) or pd.notna(ftr):
        return "BALANCED"
    return "DATA LIMITED"


def _grade_matchup(l5_p: dict, season_a: dict, l10_a: dict):
    score = 0
    evidence = 0
    reasons = []
    method = _method_label(l5_p)

    efg_s = _num(season_a.get("EFG_PCT"), np.nan)
    efg_10 = _num(l10_a.get("EFG_PCT"), np.nan)
    if pd.notna(efg_s) and pd.notna(efg_10):
        evidence += 1
        d = efg_10 - efg_s
        if d >= 0.015:
            score += 1; reasons.append("L10 eFG allowed is looser")
        elif d <= -0.015:
            score -= 1; reasons.append("L10 eFG allowed is tighter")
        else:
            reasons.append("eFG allowed is stable")

    share_s = _num(season_a.get("FG3_SHARE"), np.nan)
    share_10 = _num(l10_a.get("FG3_SHARE"), np.nan)
    p3_s = _num(season_a.get("FG3_PCT"), np.nan)
    p3_10 = _num(l10_a.get("FG3_PCT"), np.nan)
    if method in ("PERIMETER-HEAVY", "PERIMETER + FT PRESSURE") and pd.notna(share_s) and pd.notna(share_10):
        evidence += 1
        share_d = share_10 - share_s
        pct_d = p3_10 - p3_s if pd.notna(p3_s) and pd.notna(p3_10) else 0.0
        if share_d >= 0.03 or pct_d >= 0.02:
            score += 1; reasons.append("recent perimeter allowance supports profile")
        elif share_d <= -0.03 and pct_d <= -0.01:
            score -= 1; reasons.append("recent perimeter allowance suppresses profile")
        else:
            reasons.append("perimeter allowance is near neutral")

    ftr_s = _num(season_a.get("FTA_RATE"), np.nan)
    ftr_10 = _num(l10_a.get("FTA_RATE"), np.nan)
    if method in ("FREE-THROW PRESSURE", "PERIMETER + FT PRESSURE") and pd.notna(ftr_s) and pd.notna(ftr_10):
        evidence += 1
        d = ftr_10 - ftr_s
        if d >= 0.04:
            score += 1; reasons.append("recent foul/FTA allowance supports profile")
        elif d <= -0.04:
            score -= 1; reasons.append("recent foul/FTA allowance suppresses profile")
        else:
            reasons.append("FTA allowance is near neutral")

    if evidence < 1:
        return "DATA LIMITED", "limited", "NEUTRAL", score, evidence, reasons, method
    if score >= 2:
        return "ELITE METHOD MATCHUP", "elite", "SUPPORTS SCORER", score, evidence, reasons, method
    if score == 1:
        return "FAVORABLE", "favorable", "SUPPORTS SCORER", score, evidence, reasons, method
    if score <= -2:
        return "HARD METHOD MATCHUP", "hard", "HURTS SCORER", score, evidence, reasons, method
    if score == -1:
        return "TOUGH", "tough", "HURTS SCORER", score, evidence, reasons, method
    return "NEUTRAL", "neutral", "NEUTRAL", score, evidence, reasons, method


def _step9_block(day: str, data: dict) -> str:
    try:
        opp_id = int(float(data.get("opponent_team_id")))
    except Exception:
        opp_id = 0
    opponent = _text(data, ["opponent", "OPPONENT", "opponent_name"], "Opponent")

    season_p, l10_p, l5_p, player_source = _player_profiles(day, data)
    allowed_logs = _opponent_shooting_allowed_history(day, opp_id) if opp_id else pd.DataFrame()
    season_a = _aggregate_allowed(allowed_logs, None)
    l10_a = _aggregate_allowed(allowed_logs, 10)

    grade, grade_class, verdict, score, evidence, reasons, method = _grade_matchup(l5_p, season_a, l10_a)
    reason_text = " • ".join(reasons) if reasons else "Verified method-specific comparison unavailable"

    efg_delta = (_num(l10_a.get("EFG_PCT"), np.nan) - _num(season_a.get("EFG_PCT"), np.nan))
    share_delta = (_num(l10_a.get("FG3_SHARE"), np.nan) - _num(season_a.get("FG3_SHARE"), np.nan))
    ftr_delta = (_num(l10_a.get("FTA_RATE"), np.nan) - _num(season_a.get("FTA_RATE"), np.nan))

    html = f"""
<style>
.kyre-v198422-step9{{background:#151a16;border:1px solid #65734d;border-radius:15px;padding:12px;margin-top:10px}}
.kyre-v198422-head{{display:flex;justify-content:space-between;align-items:center;gap:8px;color:#d5e99b;font-size:.61rem;font-weight:950;letter-spacing:.055em;text-transform:uppercase;margin-bottom:9px}}
.kyre-v198422-grade{{border-radius:999px;padding:5px 8px;white-space:nowrap;font-size:.55rem}}
.kyre-v198422-grade.elite,.kyre-v198422-grade.favorable{{background:#0b422f;color:#7df2ba;border:1px solid #237a59}}
.kyre-v198422-grade.neutral{{background:#3a3009;color:#ffe17a;border:1px solid #756313}}
.kyre-v198422-grade.tough{{background:#3a2616;color:#ffc984;border:1px solid #7c5832}}
.kyre-v198422-grade.hard{{background:#35171b;color:#ff9aa5;border:1px solid #7a3941}}
.kyre-v198422-grade.limited{{background:#1b2836;color:#a8c3d8;border:1px solid #405b70}}
.kyre-v198422-profile{{background:#0d130e;border:1px solid #4b5c3b;border-radius:10px;padding:9px;color:#e6efdd;font-size:.68rem;line-height:1.55;margin-bottom:8px}}
.kyre-v198422-profile b{{color:#d5e99b}}
.kyre-v198422-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}}
.kyre-v198422-grid div{{border:1px solid #46563a;border-radius:10px;padding:8px;background:#0b100c}}
.kyre-v198422-grid small{{display:block;color:#91a87d;font-size:.48rem;font-weight:900;letter-spacing:.045em}}
.kyre-v198422-grid strong{{display:block;color:#f4f8ef;font-size:.82rem;margin-top:3px;word-break:break-word}}
.kyre-v198422-detail{{background:#0d130e;border:1px solid #4b5c3b;border-radius:10px;padding:9px;color:#dde8d6;font-size:.66rem;line-height:1.52;margin-top:8px}}
.kyre-v198422-detail b{{color:#d5e99b}}
.kyre-v198422-verdict{{margin-top:8px;border-radius:10px;padding:8px 9px;background:#18221a;border:1px solid #65734d;color:#f4faef;font-size:.68rem;font-weight:850}}
.kyre-v198422-note{{color:#849079;font-size:.57rem;line-height:1.42;margin-top:7px}}
@media(max-width:760px){{.kyre-v198422-head{{align-items:flex-start;flex-direction:column}}}}
</style>
<div class="kyre-v198422-step9">
<div class="kyre-v198422-head"><span>STEP 9 • OPPONENT SHOT-PROFILE DEFENSE + SCORING METHOD</span><span class="kyre-v198422-grade {grade_class}">{escape(grade)}</span></div>
<div class="kyre-v198422-profile"><b>Player scoring-method profile</b> • {escape(method)}<br><b>Opponent</b> • {escape(opponent)}<br><b>Verified player source</b> • {escape(player_source)}</div>
<div class="kyre-v198422-grid">
<div><small>PLAYER L5 3PA SHARE</small><strong>{_pct(l5_p.get('FG3_SHARE'))}</strong></div><div><small>PLAYER L5 FTA RATE</small><strong>{_pct(l5_p.get('FTA_RATE'))}</strong></div>
<div><small>PLAYER L5 eFG%</small><strong>{_pct(l5_p.get('EFG_PCT'))}</strong></div><div><small>PLAYER L5 TS%</small><strong>{_pct(l5_p.get('TS_PCT'))}</strong></div>
<div><small>OPP SEASON eFG% ALLOWED</small><strong>{_pct(season_a.get('EFG_PCT'))}</strong></div><div><small>OPP L10 eFG% ALLOWED</small><strong>{_pct(l10_a.get('EFG_PCT'))}</strong></div>
<div><small>OPP SEASON 3PA SHARE</small><strong>{_pct(season_a.get('FG3_SHARE'))}</strong></div><div><small>OPP L10 3PA SHARE</small><strong>{_pct(l10_a.get('FG3_SHARE'))}</strong></div>
<div><small>OPP SEASON FTA RATE</small><strong>{_pct(season_a.get('FTA_RATE'))}</strong></div><div><small>OPP L10 FTA RATE</small><strong>{_pct(l10_a.get('FTA_RATE'))}</strong></div>
<div><small>OPP L10 3P% ALLOWED</small><strong>{_pct(l10_a.get('FG3_PCT'))}</strong></div><div><small>DEFENSE SAMPLE</small><strong>{int(season_a.get('GP') or 0)} season • {int(l10_a.get('GP') or 0)} L10</strong></div>
</div>
<div class="kyre-v198422-detail"><b>Recent eFG allowance Δ</b> • {_pct(efg_delta, signed=True)} vs season<br><b>Recent 3PA-share allowance Δ</b> • {_pct(share_delta, signed=True)} vs season<br><b>Recent FTA-rate allowance Δ</b> • {_pct(ftr_delta, signed=True)} vs season<br><b>Evidence</b> • {evidence} scored method signals • score {score:+d}<br><b>Read</b> • {escape(reason_text)}<br><b>Opponent source</b> • ESPN WNBA verified final-game box scores before slate date<br><b>Shot-location firewall</b> • rim/midrange defense is NOT SCORED because no verified location split is exposed by the connected feed</div>
<div class="kyre-v198422-verdict">Scoring-method matchup • {escape(verdict)}</div>
<div class="kyre-v198422-note">Audit/context only • Step 9 compares verified recent scoring method with verified opponent shooting allowed. It does not add a second defense/shot-profile multiplier or change projection, Monte Carlo probability, calibration or Top-5 ordering.</div>
</div>
"""
    return _compact_html(html)


def _step7_plus_step8_plus_step9(day: str, data: dict) -> str:
    return _BASE_STEP7_PLUS_8(day, data) + _step9_block(day, data)


def _install() -> None:
    # Preserve all V1.9.8.4.21 identity/usage repairs, then append Step 9 at the
    # established Top-5 card seam. No projection/simulation object is replaced.
    prior._install()
    v416._step7_block = _step7_plus_step8_plus_step9


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _install()
    st.caption(
        "🎯 Points V1.9.8.4.22 • Step 9 opponent shot-profile defense audit ACTIVE • "
        "verified ESPN box scores • no inferred rim/midrange split • model/ranking unchanged"
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
