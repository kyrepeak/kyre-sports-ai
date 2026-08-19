"""WNBA Rebounds V1.6 — Step 7 opponent missed-shot environment.

Extends the verified V1.5.5 fast path. This change adds ONE layer only:
team-level opponent missed-field-goal environment from ESPN WNBA team statistics.

Precision / performance rules:
- Steps 1-6 are unchanged and remain owned by V1.5.5.
- Step 7 never calls stats.nba.com or stats.wnba.com.
- Team-stat requests are concurrent, short-timeout and cached for six hours.
- No sportsbook line, player rebound projection, Monte Carlo, pace multiplier,
  rebounding-allowed factor or position adjustment is introduced here.
- If a team does not return trustworthy FGM/FGA (or FGA + FG%), Step 8 stays
  locked. Missing data is not guessed.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import re

import numpy as np
import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_schedule_v24 as schedule_v24
import wnba_rebounds_hub_v155 as base

MODEL_VERSION = "WNBA REBOUNDS V1.6 • STEP 7 OPPONENT MISSED-SHOT ENVIRONMENT"
ESPN_TEAM_STATS = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams/{team}/statistics"


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = value.replace("%", "").replace(",", "").strip()
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _key(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _walk_stat_nodes(obj):
    """Yield ESPN stat-like dictionaries from changing payload layouts."""
    if isinstance(obj, dict):
        keys = {_key(k) for k in obj.keys()}
        if keys.intersection({"name", "displayname", "abbreviation", "shortdisplayname"}) and keys.intersection({"value", "displayvalue", "pergamevalue", "avgvalue"}):
            yield obj
        for value in obj.values():
            yield from _walk_stat_nodes(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_stat_nodes(value)


def _node_names(node: dict) -> set[str]:
    names = set()
    for field in ("name", "displayName", "shortDisplayName", "abbreviation", "label"):
        if node.get(field) is not None:
            names.add(_key(node.get(field)))
    return names


def _node_value(node: dict):
    # Prefer numeric per-game fields when ESPN exposes them.
    for field in ("perGameValue", "avgValue", "value", "displayValue"):
        value = node.get(field)
        if value is not None and value != "":
            return value
    return np.nan


def _parse_made_attempt_pair(value):
    text = str(value or "").strip()
    # ESPN commonly renders made-attempted as 30.2-67.3.
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*[-/]\s*(-?\d+(?:\.\d+)?)", text)
    if not match:
        return np.nan, np.nan
    return _num(match.group(1)), _num(match.group(2))


def _pick(nodes, aliases):
    wanted = {_key(x) for x in aliases}
    for node in nodes:
        if _node_names(node).intersection(wanted):
            return _node_value(node)
    return np.nan


def _parse_team_shooting(payload: dict) -> dict:
    nodes = list(_walk_stat_nodes(payload or {}))

    fgm = _num(_pick(nodes, [
        "avgFieldGoalsMade", "fieldGoalsMadePerGame", "fieldGoalsMade", "FGM"
    ]))
    fga = _num(_pick(nodes, [
        "avgFieldGoalsAttempted", "fieldGoalsAttemptedPerGame", "fieldGoalsAttempted", "FGA"
    ]))
    fg_pct = _num(_pick(nodes, [
        "fieldGoalPct", "fieldGoalPercentage", "avgFieldGoalPct", "FG%", "FG PCT"
    ]))

    # Some ESPN layouts expose the made/attempted pair as one display field.
    if not (np.isfinite(fgm) and np.isfinite(fga)):
        pair = _pick(nodes, [
            "fieldGoalsMade-fieldGoalsAttempted", "avgFieldGoalsMade-avgFieldGoalsAttempted",
            "fieldGoals", "FG"
        ])
        pm, pa = _parse_made_attempt_pair(pair)
        if np.isfinite(pm) and np.isfinite(pa):
            fgm, fga = pm, pa

    # Normalize percent layouts and allow FGM reconstruction only when FGA and
    # an explicitly supplied ESPN FG% are present. This is arithmetic, not a guess.
    if np.isfinite(fg_pct) and fg_pct > 1.5:
        fg_pct = fg_pct / 100.0
    if not np.isfinite(fgm) and np.isfinite(fga) and np.isfinite(fg_pct):
        fgm = fga * fg_pct
    if not np.isfinite(fg_pct) and np.isfinite(fgm) and np.isfinite(fga) and fga > 0:
        fg_pct = fgm / fga

    misses = fga - fgm if np.isfinite(fga) and np.isfinite(fgm) else np.nan
    ok = bool(
        np.isfinite(fga) and fga > 0
        and np.isfinite(fgm) and fgm >= 0 and fgm <= fga
        and np.isfinite(misses) and misses >= 0
    )
    return {
        "ok": ok,
        "FGM": float(fgm) if np.isfinite(fgm) else np.nan,
        "FGA": float(fga) if np.isfinite(fga) else np.nan,
        "FG_PCT": float(fg_pct) if np.isfinite(fg_pct) else np.nan,
        "MISSED_FG": float(misses) if np.isfinite(misses) else np.nan,
    }


@st.cache_data(ttl=21600, show_spinner=False, max_entries=64)
def _team_shooting_cached(team_id: int, day: str) -> dict:
    slug = players.TEAM_SLUGS.get(int(team_id))
    if not slug:
        return {"ok": False, "error": "no ESPN team slug"}
    try:
        payload, meta = schedule_v24._request_json(
            "ESPN WNBA team shooting stats",
            ESPN_TEAM_STATS.format(team=slug),
            params={"season": int(pd.to_datetime(day).year)},
            timeout=5,
            attempts=1,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    if payload is None:
        return {"ok": False, "error": str((meta or {}).get("error") or "empty ESPN response")}
    parsed = _parse_team_shooting(payload)
    parsed["source"] = "ESPN WNBA team statistics"
    parsed["team_id"] = int(team_id)
    if not parsed.get("ok"):
        parsed["error"] = "FGM/FGA fields unavailable in ESPN team-stat payload"
    return parsed


@st.cache_data(ttl=21600, show_spinner=False, max_entries=16)
def _build_step7_cached(day: str, slate: pd.DataFrame):
    if slate is None or slate.empty:
        return pd.DataFrame(), {"ready": False, "teams": 0, "covered": 0, "reason": "no verified slate"}

    team_meta = {}
    opponent = {}
    for _, row in slate.iterrows():
        away_id = int(row.get("away_team_id") or 0)
        home_id = int(row.get("home_team_id") or 0)
        if away_id:
            team_meta[away_id] = str(row.get("away_team") or away_id)
            opponent[away_id] = home_id
        if home_id:
            team_meta[home_id] = str(row.get("home_team") or home_id)
            opponent[home_id] = away_id

    ids = sorted(team_meta)
    stats = {}
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(ids)))) as pool:
        future_map = {pool.submit(_team_shooting_cached, tid, str(day)): tid for tid in ids}
        for future in as_completed(future_map):
            tid = future_map[future]
            try:
                stats[tid] = future.result()
            except Exception as exc:
                stats[tid] = {"ok": False, "error": str(exc)}

    rows = []
    for team_id in ids:
        opp_id = opponent.get(team_id, 0)
        opp_stat = stats.get(opp_id, {})
        rows.append({
            "Team": team_meta.get(team_id, str(team_id)),
            "Opponent": team_meta.get(opp_id, str(opp_id) if opp_id else "—"),
            "Opp FGM/G": _num(opp_stat.get("FGM")),
            "Opp FGA/G": _num(opp_stat.get("FGA")),
            "Opp FG%": 100.0 * _num(opp_stat.get("FG_PCT")) if np.isfinite(_num(opp_stat.get("FG_PCT"))) else np.nan,
            "Opp Missed FG/G": _num(opp_stat.get("MISSED_FG")),
            "Source": str(opp_stat.get("source") or "ESPN WNBA team statistics"),
            "State": "VERIFIED" if bool(opp_stat.get("ok")) else "CHECK",
            "Error": str(opp_stat.get("error") or ""),
        })

    frame = pd.DataFrame(rows)
    covered = int(frame["State"].eq("VERIFIED").sum()) if not frame.empty else 0
    ready = bool(len(ids) > 0 and covered == len(ids))

    # Slate-relative context only; this is deliberately NOT a projection factor.
    if not frame.empty and frame["Opp Missed FG/G"].notna().any():
        avg = float(pd.to_numeric(frame["Opp Missed FG/G"], errors="coerce").mean())
        frame["Slate miss index"] = (
            pd.to_numeric(frame["Opp Missed FG/G"], errors="coerce") / avg
            if avg > 0 else np.nan
        )
    else:
        frame["Slate miss index"] = np.nan

    return frame, {
        "ready": ready,
        "teams": int(len(ids)),
        "covered": covered,
        "source": "ESPN WNBA team statistics",
    }


def _render_step7():
    day = str(st.session_state.get("wnba_rebounds_step1_day") or pd.Timestamp.now().strftime("%Y-%m-%d"))
    try:
        slate = schedule_v24.schedule_for_date(day)
    except Exception:
        slate = pd.DataFrame()

    frame, info = _build_step7_cached(day, slate)
    st.session_state["wnba_rebounds_step7_ready"] = bool(info.get("ready"))
    st.session_state["wnba_rebounds_step7_teams"] = frame.to_dict("records") if not frame.empty else []

    st.markdown("## 🎯 Step 7 — Opponent Missed-Shot Environment")
    st.caption(
        "This layer measures the opponent's field-goal miss environment before player rebound capture, competition, pace, sportsbook lines or simulation. "
        "It uses ESPN WNBA team shooting statistics. Pace is intentionally deferred to Step 10 so the same possession effect is not counted twice."
    )

    a, b, c, d = st.columns(4)
    a.metric("Team checks", f"{info.get('covered',0)}/{info.get('teams',0)}")
    b.metric("Verified opponents", info.get("covered", 0))
    mean_misses = pd.to_numeric(frame.get("Opp Missed FG/G"), errors="coerce").mean() if not frame.empty else np.nan
    c.metric("Slate avg opp misses", f"{mean_misses:.1f}" if np.isfinite(mean_misses) else "—")
    d.metric("Mode", "TEAM SHOOTING")

    if info.get("ready"):
        st.success(
            "✅ STEP 7 PASSED • every slate side has a verified opponent FGM/FGA shooting environment. "
            "Step 8 (opponent rebounding allowed) is unlocked. No player rebound projection has been created yet."
        )
    else:
        st.error(
            "⛔ STEP 7 CHECK • at least one opponent shooting environment is incomplete. Step 8 remains locked; missing shooting data is not guessed."
        )

    if not frame.empty:
        display = frame.copy()
        for col in ("Opp FGM/G", "Opp FGA/G", "Opp FG%", "Opp Missed FG/G"):
            display[col] = pd.to_numeric(display[col], errors="coerce").round(1)
        display["Slate miss index"] = pd.to_numeric(display["Slate miss index"], errors="coerce").round(3)
        st.dataframe(
            display[["Team", "Opponent", "Opp FGM/G", "Opp FGA/G", "Opp FG%", "Opp Missed FG/G", "Slate miss index", "State"]],
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("🎯 Step-7 methodology / diagnostics"):
        st.write({
            "date": day,
            "source": info.get("source"),
            "cache_ttl_hours": 6,
            "requests": "one short-timeout team-stat request per slate team, concurrent",
            "double_count_guard": "pace/expected shot volume deferred to Step 10",
            "sportsbook_used": False,
            "monte_carlo_used": False,
        })
        if not frame.empty and frame["State"].eq("CHECK").any():
            st.dataframe(frame.loc[frame["State"].eq("CHECK"), ["Team", "Opponent", "Error"]], hide_index=True, use_container_width=True)

    st.markdown("## 🧱 Rebounds Build Order — Current")
    ready = bool(info.get("ready"))
    layers = [
        "Verified daily WNBA slate",
        "Current rosters + injuries/status",
        "Projected minutes + rotation",
        "Offensive/defensive rebound role",
        "Recent + season rebound form",
        "Rebound chances/opportunities",
        "Opponent missed-shot environment",
        "Opponent rebounding allowed",
    ]
    statuses = ["✅ LIVE"] * 5 + ["✅ BASELINE", "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK", "➡️ NEXT" if ready else "🔒 LOCKED"]
    st.dataframe(pd.DataFrame({"Step": range(1, 9), "Layer": layers, "Status": statuses}), hide_index=True, use_container_width=True)
    st.caption("⚡ V1.6 Step 7 only • six-hour cached ESPN team shooting input • no Step-6 tracking calls • no sportsbook/Monte Carlo/projected rebound output.")


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step6_ready"):
        _render_step7()
    else:
        st.info("Step 7 remains locked until Step 6 is verified.")
    return out


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
