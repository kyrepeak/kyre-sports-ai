"""WNBA Rebounds V1.7 — Step 8 opponent rebounding allowed/capture environment.

Extends the verified V1.6 Step-7 build without changing Steps 1-7.

Step-8 rules:
- Reuse the same six-hour ESPN team-stat payload for Step 7 and Step 8 when a
  fresh deployment needs both layers, avoiding duplicate normal-load requests.
- Prefer direct opponent-rebounds-allowed fields when ESPN exposes them.
- If ESPN does not expose a direct allowed field, use a clearly labeled,
  verified opponent rebounding-capture proxy (REB/OREB/DREB). Proxy values are
  never mislabeled as direct rebounds allowed.
- Step 8 is context only. It does not create a player rebound projection or
  apply pace, position, sportsbook, or Monte Carlo adjustments.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np
import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_schedule_v24 as schedule_v24
import wnba_rebounds_hub_v16 as base

MODEL_VERSION = "WNBA REBOUNDS V1.7 • STEP 8 OPPONENT REBOUNDING ALLOWED"
ESPN_TEAM_STATS = base.ESPN_TEAM_STATS


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
    return base._pick(nodes, aliases)


def _parse_team_rebounding(payload: dict) -> dict:
    """Parse direct allowed fields first, then own rebound-capture stats."""
    nodes = list(base._walk_stat_nodes(payload or {}))

    reb = _num(_pick(nodes, [
        "avgRebounds", "reboundsPerGame", "totalReboundsPerGame",
        "rebounds", "totalRebounds", "REB",
    ]))
    oreb = _num(_pick(nodes, [
        "avgOffensiveRebounds", "offensiveReboundsPerGame",
        "offensiveRebounds", "OREB",
    ]))
    dreb = _num(_pick(nodes, [
        "avgDefensiveRebounds", "defensiveReboundsPerGame",
        "defensiveRebounds", "DREB",
    ]))

    # Some payloads omit total rebounds but expose both components.
    if not np.isfinite(reb) and np.isfinite(oreb) and np.isfinite(dreb):
        reb = oreb + dreb

    direct_reb_allowed = _num(_pick(nodes, [
        "avgOpponentRebounds", "opponentReboundsPerGame",
        "opponentTotalReboundsPerGame", "opponentRebounds",
        "reboundsAllowedPerGame", "reboundsAllowed",
        "OPP REB", "Opponent Rebounds", "Opponent Total Rebounds",
    ]))
    direct_oreb_allowed = _num(_pick(nodes, [
        "avgOpponentOffensiveRebounds", "opponentOffensiveReboundsPerGame",
        "opponentOffensiveRebounds", "offensiveReboundsAllowedPerGame",
        "offensiveReboundsAllowed", "OPP OREB",
    ]))
    direct_dreb_allowed = _num(_pick(nodes, [
        "avgOpponentDefensiveRebounds", "opponentDefensiveReboundsPerGame",
        "opponentDefensiveRebounds", "defensiveReboundsAllowedPerGame",
        "defensiveReboundsAllowed", "OPP DREB",
    ]))

    direct = bool(np.isfinite(direct_reb_allowed) and direct_reb_allowed >= 0)
    proxy = bool(
        np.isfinite(reb) and reb >= 0
        and np.isfinite(oreb) and oreb >= 0
        and np.isfinite(dreb) and dreb >= 0
    )
    ok = bool(direct or proxy)

    return {
        "ok": ok,
        "direct": direct,
        "proxy": proxy,
        "REB": float(reb) if np.isfinite(reb) else np.nan,
        "OREB": float(oreb) if np.isfinite(oreb) else np.nan,
        "DREB": float(dreb) if np.isfinite(dreb) else np.nan,
        "REB_ALLOWED": float(direct_reb_allowed) if np.isfinite(direct_reb_allowed) else np.nan,
        "OREB_ALLOWED": float(direct_oreb_allowed) if np.isfinite(direct_oreb_allowed) else np.nan,
        "DREB_ALLOWED": float(direct_dreb_allowed) if np.isfinite(direct_dreb_allowed) else np.nan,
    }


@st.cache_data(ttl=21600, show_spinner=False, max_entries=64)
def _team_environment_cached(team_id: int, day: str) -> dict:
    """One ESPN payload feeds both Step 7 shooting and Step 8 rebounding."""
    slug = players.TEAM_SLUGS.get(int(team_id))
    if not slug:
        return {"ok": False, "error": "no ESPN team slug", "team_id": int(team_id)}

    try:
        payload, meta = schedule_v24._request_json(
            "ESPN WNBA team shooting/rebounding stats",
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

    shooting = base._parse_team_shooting(payload)
    rebounding = _parse_team_rebounding(payload)
    return {
        "ok": bool(shooting.get("ok") or rebounding.get("ok")),
        "shooting": shooting,
        "rebounding": rebounding,
        "source": "ESPN WNBA team statistics",
        "team_id": int(team_id),
    }


def _shooting_from_environment(team_id: int, day: str) -> dict:
    """Compatibility adapter so a cold Step 7 can share Step 8's payload cache."""
    env = _team_environment_cached(int(team_id), str(day))
    out = dict(env.get("shooting") or {})
    out["source"] = env.get("source") or "ESPN WNBA team statistics"
    out["team_id"] = int(team_id)
    if not out.get("ok") and not out.get("error"):
        out["error"] = env.get("error") or "shooting fields unavailable"
    return out


@st.cache_data(ttl=21600, show_spinner=False, max_entries=16)
def _build_step8_cached(day: str, slate: pd.DataFrame):
    if slate is None or slate.empty:
        return pd.DataFrame(), {
            "ready": False, "teams": 0, "covered": 0,
            "direct": 0, "proxy": 0, "reason": "no verified slate",
        }

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
        future_map = {
            pool.submit(_team_environment_cached, tid, str(day)): tid
            for tid in ids
        }
        for future in as_completed(future_map):
            tid = future_map[future]
            try:
                stats[tid] = future.result()
            except Exception as exc:
                stats[tid] = {"ok": False, "error": str(exc)}

    rows = []
    for team_id in ids:
        opp_id = opponent.get(team_id, 0)
        env = stats.get(opp_id, {})
        reb = dict(env.get("rebounding") or {})
        direct = bool(reb.get("direct"))
        proxy = bool(reb.get("proxy"))
        covered = bool(direct or proxy)

        rows.append({
            "Team": team_meta.get(team_id, str(team_id)),
            "Opponent": team_meta.get(opp_id, str(opp_id) if opp_id else "—"),
            "REB allowed/G": _num(reb.get("REB_ALLOWED")),
            "OREB allowed/G": _num(reb.get("OREB_ALLOWED")),
            "DREB allowed/G": _num(reb.get("DREB_ALLOWED")),
            "Opponent REB/G": _num(reb.get("REB")),
            "Opponent OREB/G": _num(reb.get("OREB")),
            "Opponent DREB/G": _num(reb.get("DREB")),
            "Mode": "DIRECT ALLOWED" if direct else ("CAPTURE PROXY" if proxy else "CHECK"),
            "State": "VERIFIED" if covered else "CHECK",
            "Error": str(
                reb.get("error")
                or env.get("error")
                or ("" if covered else "rebounding fields unavailable")
            ),
        })

    frame = pd.DataFrame(rows)

    # Direct allowed index uses the literal allowed field. Proxy index is the
    # inverse of opponent total rebound capture and is explicitly labeled.
    direct_vals = pd.to_numeric(frame.get("REB allowed/G"), errors="coerce")
    proxy_vals = pd.to_numeric(frame.get("Opponent REB/G"), errors="coerce")
    direct_avg = float(direct_vals.mean()) if direct_vals.notna().any() else np.nan
    proxy_avg = float(proxy_vals.mean()) if proxy_vals.notna().any() else np.nan

    allowed_index = []
    for _, row in frame.iterrows():
        if row.get("Mode") == "DIRECT ALLOWED":
            val = _num(row.get("REB allowed/G"))
            idx = val / direct_avg if np.isfinite(val) and np.isfinite(direct_avg) and direct_avg > 0 else np.nan
        elif row.get("Mode") == "CAPTURE PROXY":
            val = _num(row.get("Opponent REB/G"))
            idx = proxy_avg / val if np.isfinite(val) and val > 0 and np.isfinite(proxy_avg) and proxy_avg > 0 else np.nan
        else:
            idx = np.nan
        allowed_index.append(idx)
    frame["Rebound-allowed index"] = allowed_index

    covered_count = int(frame["State"].eq("VERIFIED").sum()) if not frame.empty else 0
    direct_count = int(frame["Mode"].eq("DIRECT ALLOWED").sum()) if not frame.empty else 0
    proxy_count = int(frame["Mode"].eq("CAPTURE PROXY").sum()) if not frame.empty else 0
    ready = bool(len(ids) > 0 and covered_count == len(ids))

    return frame, {
        "ready": ready,
        "teams": int(len(ids)),
        "covered": covered_count,
        "direct": direct_count,
        "proxy": proxy_count,
        "source": "ESPN WNBA team statistics",
    }


def _render_step8():
    day = str(
        st.session_state.get("wnba_rebounds_step1_day")
        or pd.Timestamp.now().strftime("%Y-%m-%d")
    )
    try:
        slate = schedule_v24.schedule_for_date(day)
    except Exception:
        slate = pd.DataFrame()

    frame, info = _build_step8_cached(day, slate)
    st.session_state["wnba_rebounds_step8_ready"] = bool(info.get("ready"))
    st.session_state["wnba_rebounds_step8_teams"] = (
        frame.to_dict("records") if not frame.empty else []
    )

    st.markdown("## 🧱 Step 8 — Opponent Rebounding Allowed")
    st.caption(
        "This layer measures how friendly or suppressive the opponent is to rebound capture. "
        "Direct opponent-rebounds-allowed fields are preferred. When ESPN does not expose a direct "
        "allowed field, the app uses verified opponent REB/OREB/DREB as a clearly labeled capture proxy. "
        "The proxy is never presented as a literal rebounds-allowed statistic, and no player projection is created here."
    )

    a, b, c, d = st.columns(4)
    a.metric("Team checks", f"{info.get('covered',0)}/{info.get('teams',0)}")
    b.metric("Direct allowed", info.get("direct", 0))
    c.metric("Verified proxies", info.get("proxy", 0))
    d.metric("Cache", "6 HOURS")

    if info.get("ready"):
        if info.get("proxy", 0):
            st.success(
                "✅ STEP 8 BASELINE PASSED • every slate side has verified opponent rebounding context. "
                "Direct allowed data is used where available; remaining rows use a labeled capture proxy. "
                "Step 9 (position matchup — Guard/Wing/Big) is unlocked. No player rebound projection exists yet."
            )
        else:
            st.success(
                "✅ STEP 8 PASSED • every slate side has direct verified opponent rebounds-allowed data. "
                "Step 9 (position matchup — Guard/Wing/Big) is unlocked. No player rebound projection exists yet."
            )
    else:
        st.error(
            "⛔ STEP 8 CHECK • at least one opponent lacks both direct rebounds-allowed data and "
            "verified rebound-capture statistics. Step 9 remains locked; missing values are not guessed."
        )

    if not frame.empty:
        display = frame.copy()
        numeric_cols = [
            "REB allowed/G", "OREB allowed/G", "DREB allowed/G",
            "Opponent REB/G", "Opponent OREB/G", "Opponent DREB/G",
        ]
        for col in numeric_cols:
            display[col] = pd.to_numeric(display[col], errors="coerce").round(1)
        display["Rebound-allowed index"] = pd.to_numeric(
            display["Rebound-allowed index"], errors="coerce"
        ).round(3)
        st.dataframe(
            display[[
                "Team", "Opponent", "REB allowed/G",
                "Opponent REB/G", "Opponent OREB/G", "Opponent DREB/G",
                "Rebound-allowed index", "Mode", "State",
            ]],
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("🧱 Step-8 methodology / diagnostics"):
        st.write({
            "date": day,
            "source": info.get("source"),
            "cache_ttl_hours": 6,
            "normal_load_network": "shared ESPN team-stat payload; concurrent slate-team requests",
            "direct_rows": info.get("direct", 0),
            "proxy_rows": info.get("proxy", 0),
            "proxy_definition": (
                "inverse slate-relative opponent total rebound capture; "
                "context only, not a literal rebounds-allowed value"
            ),
            "double_count_guard": (
                "Step 8 does not alter a player projection; pace remains deferred to Step 10"
            ),
            "sportsbook_used": False,
            "monte_carlo_used": False,
            "player_projection_created": False,
        })
        if not frame.empty and frame["State"].eq("CHECK").any():
            st.dataframe(
                frame.loc[
                    frame["State"].eq("CHECK"),
                    ["Team", "Opponent", "Error"],
                ],
                hide_index=True,
                use_container_width=True,
            )

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
        "Position matchup — Guard/Wing/Big",
    ]
    statuses = (
        ["✅ LIVE"] * 5
        + ["✅ BASELINE", "✅ LIVE", "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK",
           "➡️ NEXT" if ready else "🔒 LOCKED"]
    )
    st.dataframe(
        pd.DataFrame({
            "Step": range(1, 10),
            "Layer": layers,
            "Status": statuses,
        }),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "⚡ V1.7 Step 8 only • shared six-hour ESPN team-stat cache • "
        "Steps 1–7 preserved • no sportsbook/Monte Carlo/projected rebound output."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    # On a cold deployment, Step 7 and Step 8 share one cached ESPN payload.
    old_shooting = base._team_shooting_cached
    base._team_shooting_cached = _shooting_from_environment
    try:
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
    finally:
        base._team_shooting_cached = old_shooting

    if st.session_state.get("wnba_rebounds_step7_ready"):
        _render_step8()
    else:
        st.info("Step 8 remains locked until Step 7 is verified.")
    return out


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
