"""WNBA Rebounds V1.9 — Step 10 pace + expected shot volume.

Extends the verified V1.8.4 chain without changing Steps 1-9.

Step-10 rules:
- Use the same six-hour ESPN team-stat payload already shared by Steps 7-8.
- Parse direct pace/possessions when ESPN exposes it; otherwise estimate possessions
  from verified team FGA, FTA, OREB and TOV: FGA + 0.44*FTA - OREB + TOV.
- Put both teams on one matchup-pace baseline, then scale each side's season FGA
  and missed-FG volume to that common pace.
- Attach the verified team pace/shot-volume context to every Step-9 player.
- This layer is context only. It does not create a player rebound projection and
  does not multiply Step-7/8/9 indices together.
- Sportsbook and Monte Carlo remain off.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_schedule_v24 as schedule_v24
import wnba_schedule_v25 as schedule_v25
import wnba_rebounds_hub_v16 as step7mod
import wnba_rebounds_hub_v17 as step8mod
import wnba_rebounds_hub_v184 as base

MODEL_VERSION = "WNBA REBOUNDS V1.9 • STEP 10 PACE + EXPECTED SHOT VOLUME"
ESPN_TEAM_STATS = step7mod.ESPN_TEAM_STATS
POSSESSION_COEF_FTA = 0.44


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


def _pick(nodes, aliases):
    return step7mod._pick(nodes, aliases)


def _parse_pace_inputs(payload: dict, shooting: dict, rebounding: dict) -> dict:
    """Parse possession inputs from the same ESPN team-stat payload."""
    nodes = list(step7mod._walk_stat_nodes(payload or {}))

    fta = _num(_pick(nodes, [
        "avgFreeThrowsAttempted", "freeThrowsAttemptedPerGame",
        "freeThrowAttemptsPerGame", "freeThrowsAttempted",
        "freeThrowAttempts", "FTA",
    ]))
    tov = _num(_pick(nodes, [
        "avgTurnovers", "turnoversPerGame", "totalTurnoversPerGame",
        "turnovers", "turnoversTotal", "TOV", "TO",
    ]))
    direct_pace = _num(_pick(nodes, [
        "avgPace", "pacePerGame", "pace", "paceFactor",
        "avgPossessions", "possessionsPerGame", "possessions",
    ]))

    fga = _num((shooting or {}).get("FGA"))
    fgm = _num((shooting or {}).get("FGM"))
    misses = _num((shooting or {}).get("MISSED_FG"))
    oreb = _num((rebounding or {}).get("OREB"))

    if not np.isfinite(misses) and np.isfinite(fga) and np.isfinite(fgm):
        misses = max(0.0, fga - fgm)

    direct_ok = bool(np.isfinite(direct_pace) and 55.0 <= direct_pace <= 115.0)
    estimated = (
        fga + POSSESSION_COEF_FTA * fta - oreb + tov
        if all(np.isfinite(x) for x in (fga, fta, oreb, tov))
        else np.nan
    )
    estimated_ok = bool(np.isfinite(estimated) and 55.0 <= estimated <= 115.0)

    pace = direct_pace if direct_ok else (estimated if estimated_ok else np.nan)
    source = (
        "ESPN DIRECT PACE/POSSESSIONS"
        if direct_ok
        else "ESTIMATED • FGA + 0.44 FTA - OREB + TOV"
        if estimated_ok
        else "CHECK"
    )

    ok = bool(
        np.isfinite(pace) and pace > 0
        and np.isfinite(fga) and fga > 0
        and np.isfinite(misses) and misses >= 0
    )
    return {
        "ok": ok,
        "PACE": float(pace) if np.isfinite(pace) else np.nan,
        "PACE_SOURCE": source,
        "DIRECT_PACE": float(direct_pace) if np.isfinite(direct_pace) else np.nan,
        "EST_POSS": float(estimated) if np.isfinite(estimated) else np.nan,
        "FGA": float(fga) if np.isfinite(fga) else np.nan,
        "MISSED_FG": float(misses) if np.isfinite(misses) else np.nan,
        "FTA": float(fta) if np.isfinite(fta) else np.nan,
        "OREB": float(oreb) if np.isfinite(oreb) else np.nan,
        "TOV": float(tov) if np.isfinite(tov) else np.nan,
    }


@st.cache_data(ttl=21600, show_spinner=False, max_entries=64)
def _team_environment_pace_cached(team_id: int, day: str) -> dict:
    """One ESPN team-stat payload feeds Steps 7, 8 and 10."""
    slug = players.TEAM_SLUGS.get(int(team_id))
    if not slug:
        return {"ok": False, "error": "no ESPN team slug", "team_id": int(team_id)}

    try:
        payload, meta = schedule_v24._request_json(
            "ESPN WNBA team shooting/rebounding/pace stats",
            ESPN_TEAM_STATS.format(team=slug),
            params={"season": int(pd.to_datetime(day).year)},
            timeout=5,
            attempts=1,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc), "team_id": int(team_id)}

    if payload is None:
        return {
            "ok": False,
            "error": str((meta or {}).get("error") or "empty ESPN response"),
            "team_id": int(team_id),
        }

    shooting = step7mod._parse_team_shooting(payload)
    rebounding = step8mod._parse_team_rebounding(payload)
    pace = _parse_pace_inputs(payload, shooting, rebounding)

    return {
        "ok": bool(shooting.get("ok") or rebounding.get("ok") or pace.get("ok")),
        "shooting": shooting,
        "rebounding": rebounding,
        "pace": pace,
        "source": "ESPN WNBA team statistics",
        "team_id": int(team_id),
    }


def _shooting_from_pace_environment(team_id: int, day: str) -> dict:
    """Compatibility adapter so Steps 7-9 share the Step-10-enriched cache."""
    env = _team_environment_pace_cached(int(team_id), str(day))
    out = dict(env.get("shooting") or {})
    out["source"] = env.get("source") or "ESPN WNBA team statistics"
    out["team_id"] = int(team_id)
    if not out.get("ok") and not out.get("error"):
        out["error"] = env.get("error") or "shooting fields unavailable"
    return out


def _slate_side_maps(slate: pd.DataFrame):
    teams = {}
    opp = {}
    if slate is None or slate.empty:
        return teams, opp
    for _, r in slate.iterrows():
        away_id = int(r.get("away_team_id") or 0)
        home_id = int(r.get("home_team_id") or 0)
        away = str(r.get("away_team") or away_id or "")
        home = str(r.get("home_team") or home_id or "")
        if away_id and home_id:
            teams[away_id] = away
            teams[home_id] = home
            opp[away_id] = home_id
            opp[home_id] = away_id
    return teams, opp


@st.cache_data(ttl=21600, show_spinner=False, max_entries=16)
def _build_step10_cached(day: str, slate: pd.DataFrame):
    if slate is None or slate.empty:
        return pd.DataFrame(), {
            "ready": False, "teams": 0, "covered": 0,
            "reason": "no verified V2.5 slate",
        }

    team_names, opp_ids = _slate_side_maps(slate)
    ids = sorted(team_names)
    envs = {}

    # These calls should be cache hits because Steps 7/8 use the same function
    # earlier in this render. On a cold process there is still only one payload
    # request per slate team for Steps 7/8/10 combined.
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(ids)))) as pool:
        futures = {
            pool.submit(_team_environment_pace_cached, tid, str(day)): tid
            for tid in ids
        }
        for future in as_completed(futures):
            tid = futures[future]
            try:
                envs[tid] = future.result()
            except Exception as exc:
                envs[tid] = {"ok": False, "error": str(exc), "team_id": tid}

    rows = []
    for tid in ids:
        oid = int(opp_ids.get(tid) or 0)
        own = dict((envs.get(tid, {}) or {}).get("pace") or {})
        other = dict((envs.get(oid, {}) or {}).get("pace") or {})

        team_pace = _num(own.get("PACE"))
        opp_pace = _num(other.get("PACE"))
        team_fga = _num(own.get("FGA"))
        opp_fga = _num(other.get("FGA"))
        team_miss = _num(own.get("MISSED_FG"))
        opp_miss = _num(other.get("MISSED_FG"))

        matchup_pace = (
            0.5 * (team_pace + opp_pace)
            if np.isfinite(team_pace) and team_pace > 0
            and np.isfinite(opp_pace) and opp_pace > 0
            else np.nan
        )
        team_scale = (
            matchup_pace / team_pace
            if np.isfinite(matchup_pace) and np.isfinite(team_pace) and team_pace > 0
            else np.nan
        )
        opp_scale = (
            matchup_pace / opp_pace
            if np.isfinite(matchup_pace) and np.isfinite(opp_pace) and opp_pace > 0
            else np.nan
        )

        expected_team_fga = (
            team_fga * team_scale
            if np.isfinite(team_fga) and np.isfinite(team_scale)
            else np.nan
        )
        expected_opp_fga = (
            opp_fga * opp_scale
            if np.isfinite(opp_fga) and np.isfinite(opp_scale)
            else np.nan
        )
        expected_team_miss = (
            team_miss * team_scale
            if np.isfinite(team_miss) and np.isfinite(team_scale)
            else np.nan
        )
        expected_opp_miss = (
            opp_miss * opp_scale
            if np.isfinite(opp_miss) and np.isfinite(opp_scale)
            else np.nan
        )
        expected_total_miss = (
            expected_team_miss + expected_opp_miss
            if np.isfinite(expected_team_miss) and np.isfinite(expected_opp_miss)
            else np.nan
        )

        covered = bool(
            oid
            and np.isfinite(matchup_pace) and matchup_pace > 0
            and np.isfinite(expected_team_fga) and expected_team_fga > 0
            and np.isfinite(expected_opp_fga) and expected_opp_fga > 0
            and np.isfinite(expected_opp_miss) and expected_opp_miss >= 0
            and np.isfinite(expected_total_miss) and expected_total_miss >= 0
        )
        rows.append({
            "Team": team_names.get(tid, str(tid)),
            "Opponent": team_names.get(oid, str(oid) if oid else "—"),
            "Team pace": team_pace,
            "Opponent pace": opp_pace,
            "Matchup pace": matchup_pace,
            "Team pace source": str(own.get("PACE_SOURCE") or "CHECK"),
            "Opponent pace source": str(other.get("PACE_SOURCE") or "CHECK"),
            "Expected team FGA": expected_team_fga,
            "Expected opponent FGA": expected_opp_fga,
            "Expected opponent missed FG": expected_opp_miss,
            "Expected total missed FG": expected_total_miss,
            "State": "VERIFIED" if covered else "CHECK",
            "Error": "" if covered else str(
                (envs.get(tid, {}) or {}).get("error")
                or (envs.get(oid, {}) or {}).get("error")
                or "pace/FGA possession inputs incomplete"
            ),
        })

    frame = pd.DataFrame(rows)
    if not frame.empty:
        pace_vals = pd.to_numeric(frame["Matchup pace"], errors="coerce")
        miss_vals = pd.to_numeric(frame["Expected opponent missed FG"], errors="coerce")
        pace_avg = float(pace_vals.mean()) if pace_vals.notna().any() else np.nan
        miss_avg = float(miss_vals.mean()) if miss_vals.notna().any() else np.nan
        frame["Pace index"] = (
            pace_vals / pace_avg if np.isfinite(pace_avg) and pace_avg > 0 else np.nan
        )
        frame["Expected miss-volume index"] = (
            miss_vals / miss_avg if np.isfinite(miss_avg) and miss_avg > 0 else np.nan
        )
    else:
        frame["Pace index"] = np.nan
        frame["Expected miss-volume index"] = np.nan

    covered = int(frame["State"].eq("VERIFIED").sum()) if not frame.empty else 0
    ready = bool(len(ids) > 0 and covered == len(ids))
    direct_count = 0
    estimated_count = 0
    for env in envs.values():
        source = str(((env or {}).get("pace") or {}).get("PACE_SOURCE") or "")
        if source.startswith("ESPN DIRECT"):
            direct_count += 1
        elif source.startswith("ESTIMATED"):
            estimated_count += 1

    return frame, {
        "ready": ready,
        "teams": int(len(ids)),
        "covered": covered,
        "direct_pace_teams": direct_count,
        "estimated_pace_teams": estimated_count,
        "source": "shared six-hour ESPN WNBA team-stat payload",
        "formula": "FGA + 0.44*FTA - OREB + TOV when direct pace is unavailable",
    }


def _attach_step10_players(team_frame: pd.DataFrame):
    records = st.session_state.get("wnba_rebounds_step9_players") or []
    players9 = pd.DataFrame(records)
    if players9.empty or team_frame is None or team_frame.empty:
        return pd.DataFrame(), {"players": int(len(players9)), "covered": 0, "ready": False}

    team_map = {
        str(r.get("Team") or ""): r
        for _, r in team_frame.iterrows()
        if str(r.get("Team") or "")
    }
    rows = []
    for _, p in players9.iterrows():
        team = str(p.get("Team") or "")
        ctx = team_map.get(team, {})
        out = p.to_dict()
        out.update({
            "Step10 matchup pace": _num(ctx.get("Matchup pace")),
            "Step10 pace index": _num(ctx.get("Pace index")),
            "Step10 expected opponent FGA": _num(ctx.get("Expected opponent FGA")),
            "Step10 expected opponent missed FG": _num(ctx.get("Expected opponent missed FG")),
            "Step10 expected miss-volume index": _num(ctx.get("Expected miss-volume index")),
        })
        covered = bool(
            str(p.get("State") or "") == "VERIFIED"
            and str(ctx.get("State") or "") == "VERIFIED"
            and np.isfinite(out["Step10 matchup pace"])
            and np.isfinite(out["Step10 expected opponent FGA"])
            and np.isfinite(out["Step10 expected opponent missed FG"])
        )
        out["Step10 state"] = "VERIFIED" if covered else "CHECK"
        rows.append(out)

    out = pd.DataFrame(rows)
    covered = int(out["Step10 state"].eq("VERIFIED").sum()) if not out.empty else 0
    return out, {
        "players": int(len(out)),
        "covered": covered,
        "ready": bool(not out.empty and covered == len(out)),
    }


def _render_step10():
    day = str(
        st.session_state.get("wnba_rebounds_step1_day")
        or pd.Timestamp.now().strftime("%Y-%m-%d")
    )
    try:
        slate = schedule_v25.schedule_for_date(day)
    except Exception:
        slate = pd.DataFrame()

    teams, info = _build_step10_cached(day, slate)
    players10, pinfo = _attach_step10_players(teams)
    ready = bool(info.get("ready") and pinfo.get("ready"))

    st.session_state["wnba_rebounds_step10_ready"] = ready
    st.session_state["wnba_rebounds_step10_teams"] = (
        teams.to_dict("records") if not teams.empty else []
    )
    st.session_state["wnba_rebounds_step10_players"] = (
        players10.to_dict("records") if not players10.empty else []
    )

    st.markdown("## 🏃 Step 10 — Pace + Expected Shot Volume")
    st.caption(
        "This layer puts both teams on one matchup-possession baseline, then scales each side's verified "
        "season FGA and missed-FG volume to that pace. Direct ESPN pace/possessions is preferred; when "
        "it is absent, possessions are estimated from verified FGA, FTA, OREB and TOV. The output is "
        "rebound-opportunity context only — it is not yet a player rebound projection."
    )

    a, b, c, d = st.columns(4)
    a.metric("Team checks", f"{info.get('covered',0)}/{info.get('teams',0)}")
    b.metric("Player joins", f"{pinfo.get('covered',0)}/{pinfo.get('players',0)}")
    mean_pace = (
        pd.to_numeric(teams.get("Matchup pace"), errors="coerce").mean()
        if not teams.empty else np.nan
    )
    c.metric("Slate avg pace", f"{mean_pace:.1f}" if np.isfinite(mean_pace) else "—")
    d.metric("Team-stat cache", "SHARED 6H")

    if ready:
        st.success(
            "✅ STEP 10 PASSED • every slate side and every Step-9 player has verified pace-adjusted "
            "shot-volume context. Step 11 (lineup effects / rebound competition) is unlocked. "
            "No final rebound projection exists yet."
        )
    else:
        st.error(
            "⛔ STEP 10 CHECK • at least one slate side or player lacks verified pace/shot-volume context. "
            "Step 11 remains locked; missing possession inputs are not guessed."
        )

    if not teams.empty:
        show = teams.copy()
        for col in (
            "Team pace", "Opponent pace", "Matchup pace", "Pace index",
            "Expected team FGA", "Expected opponent FGA",
            "Expected opponent missed FG", "Expected total missed FG",
            "Expected miss-volume index",
        ):
            show[col] = pd.to_numeric(show[col], errors="coerce").round(3)
        st.dataframe(
            show[[
                "Team", "Opponent", "Team pace", "Opponent pace", "Matchup pace",
                "Pace index", "Expected opponent FGA", "Expected opponent missed FG",
                "Expected miss-volume index", "State",
            ]],
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("🏃 Step-10 methodology / diagnostics"):
        st.write({
            "date": day,
            "source": info.get("source"),
            "shared_payload_rule": "Steps 7, 8 and 10 use the same cached ESPN team-stat request",
            "direct_pace_teams": info.get("direct_pace_teams", 0),
            "estimated_pace_teams": info.get("estimated_pace_teams", 0),
            "possession_fallback": info.get("formula"),
            "matchup_pace": "average of the two verified team pace/possession baselines",
            "expected_FGA": "season FGA × matchup pace / team pace",
            "expected_misses": "season missed FG × matchup pace / team pace",
            "double_count_guard": (
                "Step 10 stores pace-adjusted volumes; later projection logic must not blindly multiply "
                "Step-7 miss index again on top of the same volume effect"
            ),
            "applied_to_player_projection": False,
            "sportsbook_used": False,
            "monte_carlo_used": False,
        })
        if not teams.empty and teams["State"].eq("CHECK").any():
            st.dataframe(
                teams.loc[teams["State"].eq("CHECK"), [
                    "Team", "Opponent", "Team pace source", "Opponent pace source", "Error"
                ]],
                hide_index=True,
                use_container_width=True,
            )
        if not players10.empty and players10["Step10 state"].eq("CHECK").any():
            st.dataframe(
                players10.loc[players10["Step10 state"].eq("CHECK"), [
                    "Player", "Team", "Opponent", "Step10 state"
                ]],
                hide_index=True,
                use_container_width=True,
            )

    st.markdown("## 🧱 Rebounds Build Order — Current")
    layers = [
        "Verified daily WNBA slate",
        "Current rosters + injuries/status",
        "Projected minutes + rotation",
        "Offensive/defensive rebound role",
        "Recent + season rebound form",
        "Rebound chances/opportunities",
        "Opponent missed-shot environment",
        "Opponent rebounding allowed",
        "Position matchup — Guard/Wing/Big",
        "Pace + expected shot volume",
        "Lineup effects / rebound competition",
    ]
    statuses = [
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ BASELINE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK",
        "➡️ NEXT" if ready else "🔒 LOCKED",
    ]
    st.dataframe(
        pd.DataFrame({"Step": range(1, 12), "Layer": layers, "Status": statuses}),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "⚡ V1.9 Step 10 only • Steps 1–9 preserved • one shared six-hour ESPN team-stat payload "
        "for Steps 7/8/10 • no sportsbook/Monte Carlo/final projected rebound output."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    # Patch the shared Step-7/8 environment only for this render so the same
    # network payload also carries Step-10 pace inputs. Restore immediately.
    old_env = step8mod._team_environment_cached
    old_shooting = step7mod._team_shooting_cached
    step8mod._team_environment_cached = _team_environment_pace_cached
    step7mod._team_shooting_cached = _shooting_from_pace_environment
    try:
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
        if st.session_state.get("wnba_rebounds_step9_ready"):
            _render_step10()
        else:
            st.info("Step 10 remains locked until Step 9 is verified.")
        return out
    finally:
        step8mod._team_environment_cached = old_env
        step7mod._team_shooting_cached = old_shooting


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
