"""WNBA Rebounds V1.3 — Step 4 offensive/defensive rebound role.

Extends the verified Steps 1-3 stack without changing frozen Points/PRA/MLB.
Step 4 separates offensive and defensive rebounding using completed WNBA box
scores before any rebound projection, market line, or Monte Carlo exists.

Important: OREB share / DREB share are composition measures (share of a
player's rebounds), not official OREB%/DREB% opportunity rates. True
opportunity/chance denominators are intentionally deferred to Step 6.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_rebounds_hub_v111 as impl

MODEL_VERSION = "WNBA REBOUNDS V1.3 • STEP 4 OREB/DREB ROLE"

_ORIGINAL_RENDER_STEP3 = impl._render_step3
_ORIGINAL_TRACKER = impl._tracker
_ORIGINAL_VERSIONED_MARKDOWN = impl._versioned_markdown
_ORIGINAL_CAPTION = st.caption


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _pick_stat(stat_map: dict, names, default=np.nan):
    for name in names:
        key = str(name).upper()
        if key in stat_map:
            return stat_map[key]
    return default


@st.cache_data(ttl=1800, show_spinner=False, max_entries=256)
def _game_rebound_components(game_id: str, game_date: str, team_id: int) -> pd.DataFrame:
    """Parse OREB/DREB/REB directly from ESPN's game-summary stat group."""
    try:
        payload, _ = players.schedule_v24._request_json(
            "ESPN WNBA rebound-role summary",
            players.ESPN_SUMMARY,
            params={"event": str(game_id)},
            timeout=8,
            attempts=2,
        )
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return pd.DataFrame()

    rows = []
    for team_block in (payload.get("boxscore") or {}).get("players", []) or []:
        team = team_block.get("team") or {}
        tid = int(players._team_id(team) or 0)
        if tid != int(team_id):
            continue
        for group in team_block.get("statistics", []) or []:
            athletes = group.get("athletes") or []
            if not athletes:
                continue
            for item in athletes:
                athlete = item.get("athlete") or {}
                if not athlete.get("id"):
                    continue
                stats = players._summary_stat_map(group, item)
                mins = players._minutes(_pick_stat(stats, ["MIN", "MINUTES"], np.nan))
                oreb = _num(_pick_stat(
                    stats,
                    ["OREB", "OFFENSIVEREBOUNDS", "OFFENSIVE REBOUNDS", "OFFREBOUNDS"],
                    np.nan,
                ))
                dreb = _num(_pick_stat(
                    stats,
                    ["DREB", "DEFENSIVEREBOUNDS", "DEFENSIVE REBOUNDS", "DEFREBOUNDS"],
                    np.nan,
                ))
                reb = _num(_pick_stat(
                    stats,
                    ["REB", "REBOUNDS", "REBOUNDSTOTAL", "TOTALREBOUNDS", "TOTAL REBOUNDS"],
                    np.nan,
                ))
                # Only derive a missing component when the other component + total
                # are provider-verified. Never invent both components from total REB.
                if pd.isna(oreb) and not pd.isna(reb) and not pd.isna(dreb):
                    oreb = max(0.0, reb - dreb)
                if pd.isna(dreb) and not pd.isna(reb) and not pd.isna(oreb):
                    dreb = max(0.0, reb - oreb)
                if pd.isna(reb) and not pd.isna(oreb) and not pd.isna(dreb):
                    reb = oreb + dreb
                rows.append({
                    "GAME_DATE": str(game_date),
                    "PLAYER_ID": int(athlete.get("id")),
                    "MIN": _num(mins, 0.0),
                    "OREB": oreb,
                    "DREB": dreb,
                    "REB": reb,
                })
            break
    return pd.DataFrame(rows)


@st.cache_data(ttl=1800, show_spinner=False, max_entries=64)
def _recent_rebound_role(day_str: str, team_id: int, player_ids: tuple[int, ...]):
    """Last-10 completed team games with verified OREB + DREB components."""
    day = pd.to_datetime(day_str).strftime("%Y-%m-%d")
    tid = int(team_id or 0)
    ids = tuple(sorted({int(x) for x in player_ids if int(x) > 0}))
    if not tid or not ids:
        return {}, 0, 0

    try:
        season = players._espn_season_schedule(pd.to_datetime(day).year)
    except Exception:
        season = pd.DataFrame()
    if season is None or season.empty:
        return {}, 0, 0

    before = pd.to_datetime(season.get("game_date"), errors="coerce") < pd.to_datetime(day)
    final = season.get("status", pd.Series("", index=season.index)).astype(str).str.upper().eq("FINAL")
    team_mask = (
        pd.to_numeric(season.get("away_team_id"), errors="coerce").eq(tid)
        | pd.to_numeric(season.get("home_team_id"), errors="coerce").eq(tid)
    )
    games = season.loc[before & final & team_mask].copy()
    if games.empty:
        return {}, 0, 0
    games["_d"] = pd.to_datetime(games["game_date"], errors="coerce")
    games = games.sort_values("_d", ascending=False).drop_duplicates("game_id").head(10)

    game_frames = []
    valid_component_games = 0
    for _, game in games.iterrows():
        gid = str(game.get("game_id") or "")
        gdate = str(game.get("game_date") or "")
        if not gid:
            continue
        frame = _game_rebound_components(gid, gdate, tid)
        if frame.empty:
            continue
        if frame[["OREB", "DREB"]].notna().any(axis=None):
            valid_component_games += 1
        game_frames.append(frame)

    if not game_frames:
        return {}, len(games), 0
    hist = pd.concat(game_frames, ignore_index=True)

    result = {}
    for pid in ids:
        p = hist.loc[pd.to_numeric(hist["PLAYER_ID"], errors="coerce").eq(pid)].copy()
        # DNP/current-roster absences are implicitly zero-minute games and do not
        # dilute per-minute rates; role sample counts only played, component-valid games.
        p = p[p["MIN"].fillna(0).gt(0)].copy()
        valid = p["OREB"].notna() & p["DREB"].notna()
        pv = p.loc[valid].copy()
        mins = float(pd.to_numeric(pv["MIN"], errors="coerce").fillna(0).sum())
        oreb = float(pd.to_numeric(pv["OREB"], errors="coerce").fillna(0).sum())
        dreb = float(pd.to_numeric(pv["DREB"], errors="coerce").fillna(0).sum())
        reb = oreb + dreb
        result[pid] = {
            "gp": int(len(pv)),
            "minutes": mins,
            "oreb": oreb,
            "dreb": dreb,
            "reb": reb,
            "oreb36": (36.0 * oreb / mins) if mins > 0 else np.nan,
            "dreb36": (36.0 * dreb / mins) if mins > 0 else np.nan,
            "reb36": (36.0 * reb / mins) if mins > 0 else np.nan,
            "oreb_share": (oreb / reb) if reb > 0 else np.nan,
            "dreb_share": (dreb / reb) if reb > 0 else np.nan,
            "reb_per_min": (reb / mins) if mins > 0 else np.nan,
        }
    return result, len(games), valid_component_games


def _role_label(reb36, oreb36, dreb36, oshare, position):
    """Transparent descriptive classification; never used as a projection itself."""
    r = _num(reb36, 0.0)
    o = _num(oreb36, 0.0)
    d = _num(dreb36, 0.0)
    s = _num(oshare, 0.0)
    pos = str(position or "").upper()
    if r >= 9.0 and d >= 6.0:
        return "GLASS ANCHOR"
    if o >= 2.6 and s >= 0.30:
        return "OFFENSIVE GLASS"
    if d >= 5.5 and r >= 7.0:
        return "DEFENSIVE GLASS"
    if r >= 5.0:
        return "SECONDARY REBOUNDER"
    if pos in {"C", "F-C", "C-F"} and r >= 3.5:
        return "LOW BIG ROLE"
    return "LOW REBOUND ROLE"


def _build_step4_role(slate: pd.DataFrame, day: str, minute_players: pd.DataFrame):
    if minute_players is None or minute_players.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "no Step-3 player rows"}

    frame = minute_players.copy()
    frame["TEAM_ID_NUM"] = pd.to_numeric(frame.get("TEAM_ID"), errors="coerce").fillna(0).astype(int)
    frame["PROJ_MIN"] = pd.to_numeric(frame.get("PROJ_MIN"), errors="coerce").fillna(0.0)
    outputs = []
    team_rows = []
    meta = impl.base._team_meta(slate)

    for tid, team_meta in meta.items():
        part = frame.loc[frame["TEAM_ID_NUM"].eq(int(tid))].copy()
        ids = []
        for value in part.get("PLAYER_ID", pd.Series(dtype=str)):
            try:
                ids.append(int(float(value)))
            except Exception:
                pass
        role_map, team_games, component_games = _recent_rebound_role(day, int(tid), tuple(ids))
        rows = []
        for _, row in part.iterrows():
            try:
                pid = int(float(row.get("PLAYER_ID")))
            except Exception:
                pid = 0
            info = role_map.get(pid) or {}
            out = row.to_dict()
            out.update({
                "REB_ROLE_GP": int(info.get("gp") or 0),
                "REB_ROLE_MIN": _num(info.get("minutes"), 0.0),
                "OREB_L10_TOTAL": _num(info.get("oreb"), np.nan),
                "DREB_L10_TOTAL": _num(info.get("dreb"), np.nan),
                "REB_L10_TOTAL": _num(info.get("reb"), np.nan),
                "OREB36": _num(info.get("oreb36"), np.nan),
                "DREB36": _num(info.get("dreb36"), np.nan),
                "REB36": _num(info.get("reb36"), np.nan),
                "OREB_SHARE": _num(info.get("oreb_share"), np.nan),
                "DREB_SHARE": _num(info.get("dreb_share"), np.nan),
                "REB_PER_MIN": _num(info.get("reb_per_min"), np.nan),
            })
            out["REB_ROLE"] = _role_label(
                out["REB36"], out["OREB36"], out["DREB36"], out["OREB_SHARE"], row.get("POSITION")
            )
            rows.append(out)
        p = pd.DataFrame(rows)
        outputs.append(p)

        modeled = p[p["PROJ_MIN"].ge(5.0)].copy()
        covered = modeled[
            modeled["REB_ROLE_GP"].ge(3)
            & modeled["OREB36"].notna()
            & modeled["DREB36"].notna()
        ]
        team_ready = bool(
            component_games >= 3
            and len(modeled) > 0
            and len(covered) == len(modeled)
        )
        team_rows.append({
            "Team": team_meta.get("name") or str(tid),
            "Modeled ≥5 MIN": len(modeled),
            "Role covered": len(covered),
            "Team games": team_games,
            "OREB/DREB games": component_games,
            "State": "VERIFIED" if team_ready else "CHECK",
        })

    players_out = pd.concat(outputs, ignore_index=True) if outputs else pd.DataFrame()
    teams_out = pd.DataFrame(team_rows)
    expected = len(meta)
    ready_teams = int(teams_out["State"].eq("VERIFIED").sum()) if not teams_out.empty else 0
    ready = bool(expected > 0 and ready_teams == expected and not players_out.empty)
    modeled_all = players_out[players_out["PROJ_MIN"].ge(5.0)] if not players_out.empty else pd.DataFrame()
    covered_all = modeled_all[
        modeled_all["REB_ROLE_GP"].ge(3)
        & modeled_all["OREB36"].notna()
        & modeled_all["DREB36"].notna()
    ] if not modeled_all.empty else pd.DataFrame()

    return players_out, teams_out, {
        "ready": ready,
        "teams": expected,
        "ready_teams": ready_teams,
        "modeled_players": len(modeled_all),
        "covered_players": len(covered_all),
        "source": "ESPN WNBA completed box scores • verified OREB + DREB components",
    }


def _render_step4(slate: pd.DataFrame, day: str, minute_players: pd.DataFrame):
    players_out, teams_out, info = _build_step4_role(slate, day, minute_players)
    st.markdown("## 🧲 Step 4 — Offensive / Defensive Rebound Role")
    st.caption(
        "This layer separates offensive and defensive glass work before any rebound projection exists. "
        "OREB/DREB come from completed WNBA box scores. Per-36 rates are minute-normalized; "
        "OREB share/DREB share describe rebound composition, not official opportunity percentages."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Team role checks", f"{info.get('ready_teams',0)}/{info.get('teams',0)}")
    c2.metric("Modeled ≥5 MIN", info.get("modeled_players", 0))
    c3.metric("OREB/DREB covered", info.get("covered_players", 0))
    c4.metric("Minimum sample", "3 GP")

    if info.get("ready"):
        st.success(
            "✅ STEP 4 PASSED • every ≥5 projected-minute player has a verified multi-game "
            "OREB/DREB role sample. Step 5 (recent + season rebound form) is unlocked."
        )
    else:
        st.error(
            "⛔ STEP 4 CHECK • at least one modeled rotation player or team lacks a ≥3-game "
            "verified OREB/DREB component sample. Step 5 remains locked."
        )

    if not teams_out.empty:
        st.dataframe(teams_out, hide_index=True, use_container_width=True)

    if not players_out.empty:
        show = players_out[players_out["PROJ_MIN"].ge(5.0)].copy()
        show["Player"] = show.get("PLAYER_NAME", pd.Series("Player", index=show.index)).astype(str)
        show["Team"] = show.get("TEAM_NAME", pd.Series("", index=show.index)).astype(str)
        show["Pos"] = show.get("POSITION", pd.Series("", index=show.index)).astype(str)
        show["Proj MIN"] = pd.to_numeric(show["PROJ_MIN"], errors="coerce").round(1)
        show["GP"] = pd.to_numeric(show["REB_ROLE_GP"], errors="coerce").fillna(0).astype(int)
        show["OREB/36"] = pd.to_numeric(show["OREB36"], errors="coerce").round(2)
        show["DREB/36"] = pd.to_numeric(show["DREB36"], errors="coerce").round(2)
        show["REB/36"] = pd.to_numeric(show["REB36"], errors="coerce").round(2)
        show["OREB share"] = (100 * pd.to_numeric(show["OREB_SHARE"], errors="coerce")).round(1).astype("Float64")
        show["DREB share"] = (100 * pd.to_numeric(show["DREB_SHARE"], errors="coerce")).round(1).astype("Float64")
        show["Role"] = show["REB_ROLE"].astype(str)
        with st.expander("🧲 Player OREB / DREB role board", expanded=False):
            st.dataframe(
                show[["Player", "Team", "Pos", "Proj MIN", "GP", "OREB/36", "DREB/36", "REB/36",
                      "OREB share", "DREB share", "Role"]],
                hide_index=True,
                use_container_width=True,
            )
            st.caption(
                "Composition shares answer 'where do this player's rebounds come from?' "
                "True rebound chances/opportunities are intentionally deferred to Step 6."
            )

    st.session_state["wnba_rebounds_step4_ready"] = bool(info.get("ready"))
    st.session_state["wnba_rebounds_step4_players"] = (
        players_out.to_dict("records") if not players_out.empty else []
    )
    st.session_state["wnba_rebounds_step4_team_checks"] = (
        teams_out.to_dict("records") if not teams_out.empty else []
    )
    return info


def _render_step3_plus_role(slate: pd.DataFrame, day: str, merged: pd.DataFrame):
    step3 = _ORIGINAL_RENDER_STEP3(slate, day, merged)
    step3_ready = bool((step3 or {}).get("ready"))
    if not step3_ready:
        st.info("🔒 Step 4 remains locked until the Step-3 projected-minute gate passes.")
        out = dict(step3 or {})
        out["step4_ready"] = False
        return out

    records = st.session_state.get("wnba_rebounds_step3_players") or []
    minute_players = pd.DataFrame(records)
    step4 = _render_step4(slate, day, minute_players)
    out = dict(step3 or {})
    out["step4_ready"] = bool(step4.get("ready"))
    out["step4_info"] = step4
    return out


def _tracker(step1_ok: bool, step2_info: dict):
    step2_ok = bool((step2_info or {}).get("ready"))
    step3_ok = bool((step2_info or {}).get("step3_ready"))
    step4_ok = bool(st.session_state.get("wnba_rebounds_step4_ready", False))
    labels = [
        ("1", "Verified daily WNBA slate"), ("2", "Current rosters + injuries/status"),
        ("3", "Projected minutes + rotation"), ("4", "Offensive/defensive rebound role"),
        ("5", "Recent + season rebound form"), ("6", "Rebound chances/opportunities"),
        ("7", "Opponent missed-shot environment"), ("8", "Opponent rebounding allowed"),
        ("9", "Position matchup — Guard/Wing/Big"), ("10", "Pace + expected shot volume"),
        ("11", "Lineup effects / rebound competition"), ("12", "Player vs opponent rebound history"),
        ("13", "Exact SportsGameOdds rebound lines"), ("14", "Same-book no-vig"),
        ("15", "Empirical rebound variance"), ("16", "Real 5M Monte Carlo"),
        ("17", "Selective 10M finalist pass"), ("18", "BEST / STRONG / MONITOR / AVOID"),
        ("19", "Top Rebound Candidates"), ("20", "Rich cards + Why this pick?"),
        ("21", "Out-of-sample calibration ledger"), ("22", "WNBA Daily Master Card handoff"),
    ]
    rows = []
    for n, label in labels:
        if n == "1":
            status = "✅ LIVE" if step1_ok else "⛔ CHECK"
        elif n == "2":
            status = "✅ LIVE" if step2_ok else ("⚠️ ACTIVE / CHECK" if step1_ok else "🔒 LOCKED")
        elif n == "3":
            status = "✅ LIVE" if step3_ok else ("➡️ NEXT" if step2_ok else "🔒 LOCKED")
        elif n == "4":
            status = "✅ LIVE" if step4_ok else ("⚠️ ACTIVE / CHECK" if step3_ok else "🔒 LOCKED")
        elif n == "5" and step4_ok:
            status = "➡️ NEXT"
        else:
            status = "🔒 LOCKED"
        rows.append({"Step": n, "Layer": label, "Status": status})
    return pd.DataFrame(rows)


def _versioned_markdown(body, *args, **kwargs):
    text = str(body)
    if "WNBA Rebounds Command Center — V1.1" in text:
        text = text.replace(
            "WNBA Rebounds Command Center — V1.1",
            "WNBA Rebounds Command Center — V1.3",
        )
        text = text.replace(
            "Steps 1–2 only: verify the Eastern-date slate, then verify current roster identity and player availability before any rebound projection is allowed to exist.",
            "Steps 1–4: verified Eastern-date slate, current roster/availability, rotation-aware minutes, and separated offensive/defensive rebound role. No final rebound projection, sportsbook input, or simulation is active yet.",
        )
    elif "WNBA Rebounds Command Center — V1.2" in text:
        text = text.replace(
            "WNBA Rebounds Command Center — V1.2",
            "WNBA Rebounds Command Center — V1.3",
        )
    return impl._ORIGINAL_MARKDOWN(text, *args, **kwargs)


def _caption_v13(body, *args, **kwargs):
    text = str(body)
    if text.startswith("⏱️ WNBA Rebounds V1.2"):
        text = (
            "🧲 WNBA Rebounds V1.3 • Steps 1–4 active • verified schedule + availability + "
            "rotation minutes + OREB/DREB role • no rebound projection/market/simulation yet"
        )
    return _ORIGINAL_CAPTION(text, *args, **kwargs)


def render_wnba_rebounds_hub(section_header=None, status_info=None, _unused=None, h=None):
    # Patch only the Rebounds implementation namespace for this render.
    impl._render_step3 = _render_step3_plus_role
    impl._tracker = _tracker
    impl._versioned_markdown = _versioned_markdown

    old_caption = st.caption
    st.caption = _caption_v13
    try:
        impl.render_wnba_rebounds_hub(section_header, status_info, _unused, h)
    finally:
        st.caption = old_caption

    # Tracker is rendered inside the base page after Step 4, so session state
    # reflects the current pass. Fix the stale bottom status message with a
    # precise post-render state summary.
    if st.session_state.get("wnba_rebounds_step4_ready"):
        st.success(
            "✅ STEPS 1–4 VERIFIED • Step 5 (recent + season rebound form) is now the next "
            "unlocked development layer. No sportsbook or Monte Carlo input is active."
        )
    else:
        st.info(
            "Step 4 is active. Step 5 stays locked until every modeled rotation player has "
            "verified OREB/DREB role coverage."
        )


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
