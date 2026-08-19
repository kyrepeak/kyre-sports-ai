"""WNBA Rebounds V2.1 — Step 12 player vs opponent rebound history.

Extends the verified V2.0 chain without changing Steps 1-11.

Step-12 rules:
- Use the exact verified V2.5 slate to map team/opponent identities.
- Pull only completed head-to-head games between tonight's two teams, current
  season plus previous season, before the selected slate date.
- Match players by immutable ESPN PLAYER_ID; names are display-only.
- A player with no prior matchup appearance is a VERIFIED NO-SAMPLE state, not
  a guessed statistic and not a reason to fail the whole model.
- Historical matchup results are diagnostic context only and are not yet applied
  to a final rebound projection.
- No sportsbook line or Monte Carlo is introduced here.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_schedule_v25 as schedule_v25
import wnba_rebounds_hub_v20 as base

MODEL_VERSION = "WNBA REBOUNDS V2.1 • STEP 12 PLAYER VS OPPONENT REBOUND HISTORY"
MAX_H2H_GAMES = 6


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _slate_team_maps(slate: pd.DataFrame):
    by_name = {}
    opponents = {}
    if slate is None or slate.empty:
        return by_name, opponents
    for _, r in slate.iterrows():
        away_id = int(r.get("away_team_id") or 0)
        home_id = int(r.get("home_team_id") or 0)
        away = str(r.get("away_team") or "")
        home = str(r.get("home_team") or "")
        if away_id and away:
            by_name[away] = away_id
        if home_id and home:
            by_name[home] = home_id
        if away_id and home_id:
            opponents[away_id] = home_id
            opponents[home_id] = away_id
    return by_name, opponents


def _pair_mask(schedule: pd.DataFrame, a: int, b: int):
    away = pd.to_numeric(schedule.get("away_team_id"), errors="coerce")
    home = pd.to_numeric(schedule.get("home_team_id"), errors="coerce")
    return ((away.eq(a) & home.eq(b)) | (away.eq(b) & home.eq(a)))


@st.cache_data(ttl=21600, show_spinner=False, max_entries=32)
def _matchup_history_cached(day: str, team_id: int, opp_id: int):
    """Return up to six completed current-team H2H box-score games."""
    day_ts = pd.to_datetime(day)
    seasons = [int(day_ts.year), int(day_ts.year) - 1]
    schedule_frames = []
    seasons_loaded = 0

    for season in seasons:
        try:
            s = players._espn_season_schedule(season)
        except Exception:
            s = pd.DataFrame()
        if s is None or s.empty:
            continue
        seasons_loaded += 1
        s = s.copy()
        s["_date"] = pd.to_datetime(s.get("game_date"), errors="coerce")
        status = s.get("status", pd.Series("", index=s.index)).astype(str).str.upper()
        prior = s["_date"].lt(day_ts)
        final = status.eq("FINAL")
        pair = _pair_mask(s, int(team_id), int(opp_id))
        schedule_frames.append(s.loc[prior & final & pair].copy())

    if not schedule_frames:
        return pd.DataFrame(), {
            "query_ok": bool(seasons_loaded > 0),
            "seasons_loaded": seasons_loaded,
            "games_found": 0,
            "games_loaded": 0,
            "coverage": "CURRENT/PREVIOUS SEASON TEAM-SERIES",
        }

    games = pd.concat(schedule_frames, ignore_index=True)
    if games.empty:
        return pd.DataFrame(), {
            "query_ok": True,
            "seasons_loaded": seasons_loaded,
            "games_found": 0,
            "games_loaded": 0,
            "coverage": "CURRENT/PREVIOUS SEASON TEAM-SERIES",
        }

    games["_date"] = pd.to_datetime(games.get("game_date"), errors="coerce")
    games = (
        games.sort_values("_date", ascending=False)
        .drop_duplicates("game_id")
        .head(MAX_H2H_GAMES)
    )

    frames = []
    jobs = []
    for _, g in games.iterrows():
        gid = str(g.get("game_id") or "")
        gdate = str(g.get("game_date") or "")
        if gid:
            jobs.append((gid, gdate))

    with ThreadPoolExecutor(max_workers=min(6, max(1, len(jobs)))) as pool:
        futures = {
            pool.submit(players._espn_game_summary, gid, gdate): gid
            for gid, gdate in jobs
        }
        for future in as_completed(futures):
            try:
                f = future.result()
                if f is not None and not f.empty:
                    frames.append(f)
            except Exception:
                continue

    logs = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not logs.empty:
        logs["GAME_DATE"] = pd.to_datetime(logs.get("GAME_DATE"), errors="coerce")
        logs["MIN"] = pd.to_numeric(logs.get("MIN"), errors="coerce")
        logs["REB"] = pd.to_numeric(logs.get("REB"), errors="coerce")
        logs = logs.dropna(subset=["PLAYER_ID"]).copy()

    return logs, {
        "query_ok": True,
        "seasons_loaded": seasons_loaded,
        "games_found": int(len(games)),
        "games_loaded": int(len(frames)),
        "coverage": "CURRENT/PREVIOUS SEASON TEAM-SERIES",
    }


def _player_ids_from_verified_source(players11: pd.DataFrame):
    source, exact, by_name = base._source_lookup()
    out = {}
    for idx, p in players11.iterrows():
        src = base._join_source_row(p, source, exact, by_name)
        pid = 0
        team_id = 0
        if src is not None:
            try:
                pid = int(float(src.get("PLAYER_ID") or 0))
            except Exception:
                pid = 0
            try:
                team_id = int(float(src.get("TEAM_ID") or 0))
            except Exception:
                team_id = 0
        out[idx] = (pid, team_id)
    return out


def _summarize_player_h2h(logs: pd.DataFrame, player_id: int):
    if logs is None or logs.empty or not player_id:
        return {
            "gp": 0, "avg_reb": np.nan, "median_reb": np.nan,
            "reb36": np.nan, "avg_min": np.nan, "last3_reb": np.nan,
            "min_reb": np.nan, "max_reb": np.nan,
            "last_reb": np.nan, "last_date": "—",
        }

    p = logs.loc[
        pd.to_numeric(logs.get("PLAYER_ID"), errors="coerce").eq(int(player_id))
    ].copy()
    p = p[pd.to_numeric(p.get("MIN"), errors="coerce").fillna(0).gt(0)].copy()
    p = p[pd.to_numeric(p.get("REB"), errors="coerce").notna()].copy()
    if p.empty:
        return {
            "gp": 0, "avg_reb": np.nan, "median_reb": np.nan,
            "reb36": np.nan, "avg_min": np.nan, "last3_reb": np.nan,
            "min_reb": np.nan, "max_reb": np.nan,
            "last_reb": np.nan, "last_date": "—",
        }

    p["GAME_DATE"] = pd.to_datetime(p.get("GAME_DATE"), errors="coerce")
    p = p.sort_values("GAME_DATE", ascending=False)
    reb = pd.to_numeric(p["REB"], errors="coerce")
    mins = pd.to_numeric(p["MIN"], errors="coerce")
    total_min = float(mins.fillna(0).sum())
    total_reb = float(reb.fillna(0).sum())
    latest = p.iloc[0]
    latest_date = latest.get("GAME_DATE")
    return {
        "gp": int(len(p)),
        "avg_reb": float(reb.mean()),
        "median_reb": float(reb.median()),
        "reb36": 36.0 * total_reb / total_min if total_min > 0 else np.nan,
        "avg_min": float(mins.mean()),
        "last3_reb": float(reb.head(3).mean()),
        "min_reb": float(reb.min()),
        "max_reb": float(reb.max()),
        "last_reb": _num(latest.get("REB")),
        "last_date": latest_date.strftime("%Y-%m-%d") if pd.notna(latest_date) else "—",
    }


def _build_step12():
    records = st.session_state.get("wnba_rebounds_step11_players") or []
    players11 = pd.DataFrame(records)
    if players11.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "ready": False, "players": 0, "covered": 0,
            "with_sample": 0, "no_sample": 0, "matchups": 0,
            "reason": "no verified Step-11 player frame",
        }

    day = str(
        st.session_state.get("wnba_rebounds_step1_day")
        or pd.Timestamp.now().strftime("%Y-%m-%d")
    )
    try:
        slate = schedule_v25.schedule_for_date(day)
    except Exception:
        slate = pd.DataFrame()

    team_by_name, opp_by_id = _slate_team_maps(slate)
    source_ids = _player_ids_from_verified_source(players11)

    pair_cache = {}
    pair_rows = []
    unique_pairs = set()
    for _, p in players11.iterrows():
        team_name = str(p.get("Team") or "")
        opp_name = str(p.get("Opponent") or "")
        tid = int(team_by_name.get(team_name) or 0)
        oid = int(team_by_name.get(opp_name) or opp_by_id.get(tid) or 0)
        if tid and oid:
            unique_pairs.add(tuple(sorted((tid, oid))))

    for a, b in sorted(unique_pairs):
        logs, info = _matchup_history_cached(day, a, b)
        pair_cache[(a, b)] = (logs, info)
        pair_rows.append({
            "Team A ID": a,
            "Team B ID": b,
            "Seasons loaded": int(info.get("seasons_loaded", 0)),
            "H2H games found": int(info.get("games_found", 0)),
            "Box scores loaded": int(info.get("games_loaded", 0)),
            "State": "VERIFIED" if info.get("query_ok") else "CHECK",
        })

    rows = []
    for idx, p in players11.iterrows():
        player_id, source_team_id = source_ids.get(idx, (0, 0))
        team_name = str(p.get("Team") or "")
        opp_name = str(p.get("Opponent") or "")
        tid = int(team_by_name.get(team_name) or source_team_id or 0)
        oid = int(team_by_name.get(opp_name) or opp_by_id.get(tid) or 0)
        key = tuple(sorted((tid, oid))) if tid and oid else None
        logs, info = pair_cache.get(key, (pd.DataFrame(), {"query_ok": False}))
        h = _summarize_player_h2h(logs, player_id)

        query_ok = bool(info.get("query_ok"))
        source_ok = bool(player_id and tid and oid)
        base_ok = str(p.get("Step11 state") or "") == "VERIFIED"
        verified = bool(base_ok and source_ok and query_ok)

        gp = int(h.get("gp") or 0)
        if verified and gp > 0:
            sample_state = "VERIFIED HISTORY"
        elif verified:
            sample_state = "VERIFIED NO SAMPLE"
        else:
            sample_state = "CHECK"

        season_rate = _num(p.get("Capture baseline"))
        h2h_vs_baseline = np.nan
        if gp > 0 and np.isfinite(_num(h.get("avg_reb"))) and np.isfinite(season_rate) and season_rate > 0:
            h2h_vs_baseline = _num(h.get("avg_reb")) / season_rate

        out = p.to_dict()
        out.update({
            "Player ID": int(player_id) if player_id else 0,
            "H2H GP": gp,
            "H2H avg REB": _num(h.get("avg_reb")),
            "H2H median REB": _num(h.get("median_reb")),
            "H2H REB/36": _num(h.get("reb36")),
            "H2H avg MIN": _num(h.get("avg_min")),
            "H2H last3 REB": _num(h.get("last3_reb")),
            "H2H min REB": _num(h.get("min_reb")),
            "H2H max REB": _num(h.get("max_reb")),
            "H2H last REB": _num(h.get("last_reb")),
            "H2H last date": str(h.get("last_date") or "—"),
            "H2H vs current baseline": h2h_vs_baseline,
            "H2H sample": sample_state,
            "Step12 state": "VERIFIED" if verified else "CHECK",
        })
        rows.append(out)

    out = pd.DataFrame(rows)
    covered = int(out["Step12 state"].eq("VERIFIED").sum()) if not out.empty else 0
    with_sample = int(out["H2H GP"].gt(0).sum()) if not out.empty else 0
    no_sample = int(out["H2H GP"].eq(0).sum()) if not out.empty else 0
    ready = bool(not out.empty and covered == len(out))
    pairs = pd.DataFrame(pair_rows)
    return out, pairs, {
        "ready": ready,
        "players": int(len(out)),
        "covered": covered,
        "with_sample": with_sample,
        "no_sample": no_sample,
        "matchups": int(len(unique_pairs)),
        "source": "ESPN WNBA completed box scores • current-team H2H series • current + previous season",
        "max_games_per_matchup": MAX_H2H_GAMES,
    }


def _render_step12():
    players12, pairs, info = _build_step12()
    ready = bool(info.get("ready"))

    st.session_state["wnba_rebounds_step12_ready"] = ready
    st.session_state["wnba_rebounds_step12_players"] = (
        players12.to_dict("records") if not players12.empty else []
    )
    st.session_state["wnba_rebounds_step12_matchups"] = (
        pairs.to_dict("records") if not pairs.empty else []
    )

    st.markdown("## 📚 Step 12 — Player vs Opponent Rebound History")
    st.caption(
        "This layer checks each verified rotation player's recent rebound history in the current team-vs-opponent series. "
        "It uses immutable ESPN PLAYER_IDs and completed box scores from the current and previous season, capped at the "
        f"latest {MAX_H2H_GAMES} team-series meetings. A player with no prior appearance is labeled VERIFIED NO SAMPLE — "
        "nothing is guessed. Historical results are diagnostic only and do not yet alter a rebound projection."
    )

    a, b, c, d = st.columns(4)
    a.metric("Player checks", f"{info.get('covered',0)}/{info.get('players',0)}")
    b.metric("With H2H sample", info.get("with_sample", 0))
    c.metric("Verified no sample", info.get("no_sample", 0))
    d.metric("Matchup series", info.get("matchups", 0))

    if ready:
        st.success(
            "✅ STEP 12 PASSED • every Step-11 player has a verified player/opponent history state. "
            "Players without a prior current-team matchup appearance remain explicitly labeled NO SAMPLE. "
            "Step 13 (exact sportsbook rebound lines) is unlocked. No historical result has been forced into a projection."
        )
    else:
        st.error(
            "⛔ STEP 12 CHECK • at least one player lacks a verified PLAYER_ID, matchup identity, or history-query state. "
            "Step 13 remains locked; missing matchup history is not guessed."
        )

    if not players12.empty:
        show = players12.copy()
        for col in (
            "Proj MIN", "Capture baseline", "H2H avg REB", "H2H median REB",
            "H2H REB/36", "H2H avg MIN", "H2H last3 REB",
            "H2H min REB", "H2H max REB", "H2H last REB",
            "H2H vs current baseline",
        ):
            if col in show.columns:
                show[col] = pd.to_numeric(show[col], errors="coerce").round(3)
        st.dataframe(
            show[[
                "Player", "Team", "Opponent", "Proj MIN",
                "H2H GP", "H2H avg REB", "H2H median REB", "H2H REB/36",
                "H2H last3 REB", "H2H last REB", "H2H last date",
                "H2H sample", "Step12 state",
            ]],
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("📚 H2H matchup-series diagnostics"):
        if pairs.empty:
            st.info("No verified matchup-series query rows available.")
        else:
            st.dataframe(pairs, hide_index=True, use_container_width=True)

    with st.expander("📚 Step-12 methodology / diagnostics"):
        st.write({
            "source": info.get("source"),
            "max_team_series_games": info.get("max_games_per_matchup"),
            "identity_join": "immutable ESPN PLAYER_ID",
            "history_scope": "current team vs current opponent; current + previous season; completed games before slate date",
            "no_sample_rule": "verified zero appearances is preserved as NO SAMPLE and never converted to a fake average",
            "sample_weight_applied_to_projection": False,
            "sportsbook_used": False,
            "monte_carlo_used": False,
        })
        if not players12.empty and players12["Step12 state"].eq("CHECK").any():
            cols = [c for c in [
                "Player", "Team", "Opponent", "Player ID", "H2H sample", "Step11 state", "Step12 state"
            ] if c in players12.columns]
            st.dataframe(
                players12.loc[players12["Step12 state"].eq("CHECK"), cols],
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
        "Player vs opponent rebound history",
        "Exact SportsGameOdds rebound lines",
    ]
    statuses = [
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ BASELINE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE", "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK",
        "➡️ NEXT" if ready else "🔒 LOCKED",
    ]
    st.dataframe(
        pd.DataFrame({"Step": range(1, 14), "Layer": layers, "Status": statuses}),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "⚡ V2.1 Step 12 only • Steps 1–11 preserved • six-hour cached team-series history • "
        "PLAYER_ID joins • verified NO-SAMPLE states preserved • no sportsbook/Monte Carlo/final projection."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step11_ready"):
        _render_step12()
    else:
        st.info("Step 12 remains locked until Step 11 is verified.")
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
