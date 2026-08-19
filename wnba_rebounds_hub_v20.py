"""WNBA Rebounds V2.0 — Step 11 lineup effects / rebound competition.

Extends the verified V1.9 chain without changing Steps 1-10.

Step-11 rules:
- Reuse only already-verified Step-3/5/6/9/10 player infrastructure.
- Measure active-rotation teammate rebound competition from projected minutes and
  verified rebound-capture baselines; add zero normal-load network requests.
- Keep same-position competition separate from total-team competition.
- Do NOT invent exact five-player lineup overlap or on/off splits when an official
  lineup feed is not present. This is explicitly a rotation-composition context.
- This layer is diagnostic context only. It does not create a final rebound
  projection, use sportsbook lines, or run Monte Carlo.
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v19 as base

MODEL_VERSION = "WNBA REBOUNDS V2.0 • STEP 11 LINEUP EFFECTS / REBOUND COMPETITION"


def _num(value, default=np.nan):
    try:
        if value is None or value == "":
            return default
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _key(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _capture_baseline(row: pd.Series):
    """Return already-verified minute-scaled rebound baseline and source."""
    for key, source in (
        ("STEP6_MIN_SCALED_REB", "STEP 6 MIN-SCALED BASELINE"),
        ("OPP_BASELINE_MIN_SCALED_REB", "STEP 6 COMPAT BASELINE"),
    ):
        value = _num(row.get(key))
        if np.isfinite(value) and value >= 0:
            return float(value), source

    rate = _num(row.get("STEP6_BASELINE_REB36"))
    if not np.isfinite(rate):
        rate = _num(row.get("FORM_STABILIZED_REB36"))
    mins = _num(row.get("PROJ_MIN"), 0.0)
    if np.isfinite(rate) and rate >= 0 and np.isfinite(mins) and mins > 0:
        return float(rate * mins / 36.0), "VERIFIED REB/36 × PROJECTED MIN"
    return np.nan, "CHECK"


def _source_lookup():
    records = (
        st.session_state.get("wnba_rebounds_step6_players")
        or st.session_state.get("wnba_rebounds_step5_players")
        or []
    )
    frame = pd.DataFrame(records)
    exact = {}
    by_name = {}
    if frame.empty:
        return frame, exact, by_name

    for idx, row in frame.iterrows():
        name = _key(row.get("PLAYER_NAME"))
        team = _key(row.get("TEAM_NAME"))
        if name and team:
            exact[(name, team)] = idx
        if name:
            by_name.setdefault(name, []).append(idx)
    return frame, exact, by_name


def _join_source_row(player: pd.Series, source: pd.DataFrame, exact: dict, by_name: dict):
    name = _key(player.get("Player"))
    team = _key(player.get("Team"))
    idx = exact.get((name, team))
    if idx is not None:
        return source.loc[idx]
    # Name-only fallback is allowed only when the name is unique on the entire
    # verified slate. This avoids silently joining a player to the wrong team.
    hits = by_name.get(name, [])
    if len(hits) == 1:
        return source.loc[hits[0]]
    return None


def _build_step11():
    step10_records = st.session_state.get("wnba_rebounds_step10_players") or []
    players10 = pd.DataFrame(step10_records)
    if players10.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "ready": False, "players": 0, "covered": 0,
            "teams": 0, "ready_teams": 0,
            "reason": "no verified Step-10 player frame",
        }

    source, exact, by_name = _source_lookup()
    rows = []
    for _, p in players10.iterrows():
        src = _join_source_row(p, source, exact, by_name)
        baseline, baseline_source = (
            _capture_baseline(src) if src is not None else (np.nan, "CHECK")
        )
        proj_min = _num(
            src.get("PROJ_MIN") if src is not None else p.get("Proj MIN"),
            _num(p.get("Proj MIN"), 0.0),
        )
        bucket = str(p.get("Position bucket") or "CHECK")
        step10_ok = str(p.get("Step10 state") or "") == "VERIFIED"
        source_ok = bool(
            src is not None
            and np.isfinite(proj_min) and proj_min >= 5.0
            and np.isfinite(baseline) and baseline >= 0
            and bucket in {"Guard", "Wing", "Big"}
        )
        rows.append({
            "Player": str(p.get("Player") or "Player"),
            "Team": str(p.get("Team") or ""),
            "Opponent": str(p.get("Opponent") or ""),
            "Position bucket": bucket,
            "Proj MIN": proj_min,
            "Capture baseline": baseline,
            "Capture source": baseline_source,
            "Step10 state": str(p.get("Step10 state") or "CHECK"),
            "Source joined": bool(src is not None),
            "_BASE_READY": bool(step10_ok and source_ok),
        })

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame, pd.DataFrame(), {
            "ready": False, "players": 0, "covered": 0,
            "teams": 0, "ready_teams": 0,
        }

    # Build team and team-position totals from verified modeled rotation players.
    team_totals = {}
    team_bucket_totals = {}
    team_player_rows = {}
    team_rows = []
    for team, part in frame.groupby("Team", sort=False):
        valid = part[part["_BASE_READY"]].copy()
        all_ready = bool(len(part) > 0 and len(valid) == len(part))
        total_capture = float(pd.to_numeric(valid["Capture baseline"], errors="coerce").sum()) if not valid.empty else np.nan
        total_min = float(pd.to_numeric(valid["Proj MIN"], errors="coerce").sum()) if not valid.empty else np.nan
        bucket_capture = {}
        bucket_minutes = {}
        for bucket in ("Guard", "Wing", "Big"):
            b = valid[valid["Position bucket"].eq(bucket)]
            bucket_capture[bucket] = float(pd.to_numeric(b["Capture baseline"], errors="coerce").sum()) if not b.empty else 0.0
            bucket_minutes[bucket] = float(pd.to_numeric(b["Proj MIN"], errors="coerce").sum()) if not b.empty else 0.0

        team_totals[team] = {"capture": total_capture, "minutes": total_min}
        team_bucket_totals[team] = {"capture": bucket_capture, "minutes": bucket_minutes}
        team_player_rows[team] = valid.copy()

        guard_share = bucket_capture["Guard"] / total_capture if np.isfinite(total_capture) and total_capture > 0 else np.nan
        wing_share = bucket_capture["Wing"] / total_capture if np.isfinite(total_capture) and total_capture > 0 else np.nan
        big_share = bucket_capture["Big"] / total_capture if np.isfinite(total_capture) and total_capture > 0 else np.nan
        team_ready = bool(
            all_ready
            and np.isfinite(total_capture) and total_capture > 0
            and np.isfinite(total_min) and total_min > 0
            and all(np.isfinite(x) for x in (guard_share, wing_share, big_share))
        )
        team_rows.append({
            "Team": team,
            "Rotation players ≥5 MIN": int(len(part)),
            "Modeled MIN": total_min,
            "Team capture baseline": total_capture,
            "Guard capture share": guard_share,
            "Wing capture share": wing_share,
            "Big capture share": big_share,
            "State": "VERIFIED" if team_ready else "CHECK",
        })

    teams = pd.DataFrame(team_rows)

    # First pass: raw teammate competition context.
    player_rows = []
    for _, p in frame.iterrows():
        team = str(p.get("Team") or "")
        bucket = str(p.get("Position bucket") or "CHECK")
        own = _num(p.get("Capture baseline"))
        own_min = _num(p.get("Proj MIN"), 0.0)
        totals = team_totals.get(team, {})
        bucket_totals = team_bucket_totals.get(team, {})
        team_capture = _num(totals.get("capture"))
        team_minutes = _num(totals.get("minutes"))
        bucket_capture = _num((bucket_totals.get("capture") or {}).get(bucket), 0.0)
        bucket_minutes = _num((bucket_totals.get("minutes") or {}).get(bucket), 0.0)

        teammate_capture = (
            max(0.0, team_capture - own)
            if np.isfinite(team_capture) and np.isfinite(own)
            else np.nan
        )
        same_bucket_teammate_capture = (
            max(0.0, bucket_capture - own)
            if np.isfinite(bucket_capture) and np.isfinite(own)
            else np.nan
        )
        own_share = own / team_capture if np.isfinite(own) and np.isfinite(team_capture) and team_capture > 0 else np.nan
        teammate_share = teammate_capture / team_capture if np.isfinite(teammate_capture) and np.isfinite(team_capture) and team_capture > 0 else np.nan
        same_bucket_share = same_bucket_teammate_capture / team_capture if np.isfinite(same_bucket_teammate_capture) and np.isfinite(team_capture) and team_capture > 0 else np.nan
        same_bucket_minute_share = (
            max(0.0, bucket_minutes - own_min) / team_minutes
            if np.isfinite(bucket_minutes) and np.isfinite(own_min)
            and np.isfinite(team_minutes) and team_minutes > 0
            else np.nan
        )

        teammates = team_player_rows.get(team, pd.DataFrame())
        others = teammates[~teammates["Player"].eq(str(p.get("Player") or ""))].copy() if not teammates.empty else pd.DataFrame()
        top_name, top_value = "—", np.nan
        if not others.empty:
            vals = pd.to_numeric(others["Capture baseline"], errors="coerce")
            if vals.notna().any():
                idx = vals.idxmax()
                top_name = str(others.loc[idx, "Player"])
                top_value = _num(others.loc[idx, "Capture baseline"])

        same_others = others[others["Position bucket"].eq(bucket)].copy() if not others.empty else pd.DataFrame()
        same_name, same_value = "—", np.nan
        if not same_others.empty:
            vals = pd.to_numeric(same_others["Capture baseline"], errors="coerce")
            if vals.notna().any():
                idx = vals.idxmax()
                same_name = str(same_others.loc[idx, "Player"])
                same_value = _num(same_others.loc[idx, "Capture baseline"])

        out = p.to_dict()
        out.update({
            "Team capture baseline": team_capture,
            "Own team capture share": own_share,
            "Teammate capture baseline": teammate_capture,
            "Teammate capture share": teammate_share,
            "Same-bucket teammate capture": same_bucket_teammate_capture,
            "Same-bucket teammate share": same_bucket_share,
            "Same-bucket teammate minute share": same_bucket_minute_share,
            "Top rebound teammate": top_name,
            "Top teammate capture": top_value,
            "Top same-bucket teammate": same_name,
            "Top same-bucket capture": same_value,
            "Rotation players": int(len(teammates)),
        })
        player_rows.append(out)

    out = pd.DataFrame(player_rows)

    # Slate-relative indices. A real zero same-bucket competition is valid and
    # remains 0.000; it is not treated as missing data.
    bucket_avg = {}
    for bucket, part in out.groupby("Position bucket"):
        vals = pd.to_numeric(part["Same-bucket teammate share"], errors="coerce")
        bucket_avg[bucket] = float(vals.mean()) if vals.notna().any() else np.nan
    overall_vals = pd.to_numeric(out["Teammate capture share"], errors="coerce")
    overall_avg = float(overall_vals.mean()) if overall_vals.notna().any() else np.nan

    states = []
    same_indices = []
    overall_indices = []
    lineup_indices = []
    for _, r in out.iterrows():
        same = _num(r.get("Same-bucket teammate share"))
        avg_same = _num(bucket_avg.get(str(r.get("Position bucket") or "")))
        overall = _num(r.get("Teammate capture share"))

        if np.isfinite(same) and np.isfinite(avg_same):
            if avg_same > 0:
                same_idx = same / avg_same
            elif same == 0:
                same_idx = 1.0
            else:
                same_idx = np.nan
        else:
            same_idx = np.nan

        overall_idx = (
            overall / overall_avg
            if np.isfinite(overall) and np.isfinite(overall_avg) and overall_avg > 0
            else np.nan
        )
        lineup_idx = (
            0.65 * same_idx + 0.35 * overall_idx
            if np.isfinite(same_idx) and np.isfinite(overall_idx)
            else np.nan
        )

        team_state = "CHECK"
        if not teams.empty:
            hit = teams[teams["Team"].eq(str(r.get("Team") or ""))]
            if not hit.empty:
                team_state = str(hit.iloc[0].get("State") or "CHECK")

        covered = bool(
            bool(r.get("_BASE_READY"))
            and team_state == "VERIFIED"
            and np.isfinite(_num(r.get("Own team capture share")))
            and np.isfinite(same_idx)
            and np.isfinite(overall_idx)
            and np.isfinite(lineup_idx)
        )
        same_indices.append(same_idx)
        overall_indices.append(overall_idx)
        lineup_indices.append(lineup_idx)
        states.append("VERIFIED" if covered else "CHECK")

    out["Same-bucket competition index"] = same_indices
    out["Overall teammate competition index"] = overall_indices
    out["Lineup competition index"] = lineup_indices
    out["Step11 state"] = states

    covered = int(out["Step11 state"].eq("VERIFIED").sum()) if not out.empty else 0
    ready_teams = int(teams["State"].eq("VERIFIED").sum()) if not teams.empty else 0
    ready = bool(
        not out.empty and covered == len(out)
        and not teams.empty and ready_teams == len(teams)
    )
    return out, teams, {
        "ready": ready,
        "players": int(len(out)),
        "covered": covered,
        "teams": int(len(teams)),
        "ready_teams": ready_teams,
        "source": "verified projected rotation + Step-6 rebound baseline + Step-10 player gate",
        "network_requests": 0,
    }


def _render_step11():
    players11, teams, info = _build_step11()
    ready = bool(info.get("ready"))

    st.session_state["wnba_rebounds_step11_ready"] = ready
    st.session_state["wnba_rebounds_step11_players"] = (
        players11.to_dict("records") if not players11.empty else []
    )
    st.session_state["wnba_rebounds_step11_teams"] = (
        teams.to_dict("records") if not teams.empty else []
    )

    st.markdown("## 🧩 Step 11 — Lineup Effects / Rebound Competition")
    st.caption(
        "This layer measures teammate rebound competition inside the verified active rotation. It combines projected "
        "minutes with the already-verified Step-6 rebound-capture baseline, separating same-position competition from "
        "overall teammate competition. Exact five-player on/off overlap is NOT invented when no official lineup feed is "
        "present. These indices are diagnostic context only and do not yet alter a player rebound projection."
    )

    a, b, c, d = st.columns(4)
    a.metric("Player checks", f"{info.get('covered',0)}/{info.get('players',0)}")
    b.metric("Team checks", f"{info.get('ready_teams',0)}/{info.get('teams',0)}")
    c.metric("Exact lineup feed", "NOT CLAIMED")
    d.metric("New network", "NONE")

    if ready:
        st.success(
            "✅ STEP 11 PASSED • every modeled Step-10 player has verified active-rotation rebound-competition context. "
            "Step 12 (player vs opponent rebound history) is unlocked. No final rebound projection exists yet."
        )
    else:
        st.error(
            "⛔ STEP 11 CHECK • at least one modeled player or team lacks verified rotation-competition context. "
            "Step 12 remains locked; lineup overlap or missing rebound data is not guessed."
        )

    if not players11.empty:
        show = players11.copy()
        for col in (
            "Proj MIN", "Capture baseline", "Own team capture share",
            "Same-bucket teammate capture", "Same-bucket teammate share",
            "Same-bucket teammate minute share", "Same-bucket competition index",
            "Overall teammate competition index", "Lineup competition index",
            "Top teammate capture", "Top same-bucket capture",
        ):
            show[col] = pd.to_numeric(show[col], errors="coerce").round(3)
        st.dataframe(
            show[[
                "Player", "Team", "Position bucket", "Proj MIN", "Capture baseline",
                "Own team capture share", "Same-bucket teammate share",
                "Same-bucket competition index", "Overall teammate competition index",
                "Lineup competition index", "Top rebound teammate",
                "Top same-bucket teammate", "Step11 state",
            ]],
            hide_index=True,
            use_container_width=True,
        )

    with st.expander("🧩 Team rotation rebound-composition board"):
        if teams.empty:
            st.info("No verified team rotation profile available.")
        else:
            t = teams.copy()
            for col in (
                "Modeled MIN", "Team capture baseline", "Guard capture share",
                "Wing capture share", "Big capture share",
            ):
                t[col] = pd.to_numeric(t[col], errors="coerce").round(3)
            st.dataframe(t, hide_index=True, use_container_width=True)

    with st.expander("🧩 Step-11 methodology / diagnostics"):
        st.write({
            "source": info.get("source"),
            "new_network_requests": 0,
            "same_bucket_competition": (
                "same-position teammate capture share / slate average for that position bucket"
            ),
            "overall_competition": (
                "all-teammate capture share / slate average all-teammate capture share"
            ),
            "lineup_competition_index": (
                "0.65 × same-position competition index + 0.35 × overall teammate competition index"
            ),
            "structural_zero_rule": "true zero same-position competition remains 0.000 and is valid",
            "exact_five_player_overlap_claimed": False,
            "injury_rotation_effects": "already enter through verified Step-2 status and Step-3 projected minutes",
            "applied_to_player_projection": False,
            "sportsbook_used": False,
            "monte_carlo_used": False,
        })
        if not players11.empty and players11["Step11 state"].eq("CHECK").any():
            cols = [c for c in [
                "Player", "Team", "Position bucket", "Proj MIN", "Capture source",
                "Source joined", "Step10 state", "Step11 state"
            ] if c in players11.columns]
            st.dataframe(
                players11.loc[players11["Step11 state"].eq("CHECK"), cols],
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
    ]
    statuses = [
        "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ BASELINE", "✅ LIVE", "✅ LIVE", "✅ LIVE", "✅ LIVE",
        "✅ LIVE" if ready else "⚠️ ACTIVE / CHECK",
        "➡️ NEXT" if ready else "🔒 LOCKED",
    ]
    st.dataframe(
        pd.DataFrame({"Step": range(1, 13), "Layer": layers, "Status": statuses}),
        hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "⚡ V2.0 Step 11 only • Steps 1–10 preserved • zero new Step-11 network requests • "
        "rotation-composition competition only • no guessed five-player overlap • no sportsbook/Monte Carlo/final projection."
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step10_ready"):
        _render_step11()
    else:
        st.info("Step 11 remains locked until Step 10 is verified.")
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
