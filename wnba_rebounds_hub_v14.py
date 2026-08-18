"""WNBA Rebounds V1.4 — Step 5 recent + season rebound form.

Extends the verified V1.3.2 Steps 1-4 stack. Step 5 measures rebound form from
verified completed WNBA games before any sportsbook line, final rebound
projection, or Monte Carlo is allowed to exist.

Precision rules:
- Season/L10/L5 baselines come from the existing current-roster player pool.
- L3/L5/L10 game-level rebound rates are rebuilt from verified ESPN summaries.
- PLAYER_ID follows recent acquisitions across teams when necessary.
- Form is minute-normalized and regression-protected; one spike game cannot
  become a projection by itself.
- The stabilized form rate is descriptive infrastructure only. It is NOT the
  final rebound projection and does not use sportsbook information.
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_rebounds_hub_v13 as role
import wnba_rebounds_hub_v132 as prior

MODEL_VERSION = "WNBA REBOUNDS V1.4 • STEP 5 VERIFIED RECENT + SEASON FORM"

_ORIGINAL_STEP4 = role._render_step4
_ORIGINAL_TRACKER = role._tracker
_ORIGINAL_V132_MARKDOWN = prior._versioned_markdown_132
_ORIGINAL_V132_CAPTION = prior._caption_132
_ORIGINAL_SUCCESS = st.success


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _norm_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


@st.cache_data(ttl=1800, show_spinner=False, max_entries=64)
def _recent_player_rebound_logs(day_str: str, team_id: int, player_ids: tuple[int, ...]) -> pd.DataFrame:
    """Return each requested player's latest verified rebound games.

    Start with recent games involving the current team, then follow immutable
    PLAYER_ID across earlier league games only for players who still need a
    three-game sample. This mirrors the verified Step-4 acquisition repair.
    """
    day = pd.to_datetime(day_str).strftime("%Y-%m-%d")
    tid = int(team_id or 0)
    ids = tuple(sorted({int(x) for x in player_ids if int(x) > 0}))
    if not tid or not ids:
        return pd.DataFrame()

    try:
        season = players._espn_season_schedule(pd.to_datetime(day).year)
    except Exception:
        season = pd.DataFrame()
    if season is None or season.empty:
        return pd.DataFrame()

    season = season.copy()
    season["_d"] = pd.to_datetime(season.get("game_date"), errors="coerce")
    final = season.get("status", pd.Series("", index=season.index)).astype(str).str.upper().eq("FINAL")
    before = season["_d"] < pd.to_datetime(day)
    games = season.loc[before & final].sort_values("_d", ascending=False).drop_duplicates("game_id")
    team_mask = (
        pd.to_numeric(games.get("away_team_id"), errors="coerce").eq(tid)
        | pd.to_numeric(games.get("home_team_id"), errors="coerce").eq(tid)
    )
    current = games.loc[team_mask].head(24)

    frames = []
    scanned = set()
    for _, game in current.iterrows():
        gid = str(game.get("game_id") or "")
        if not gid:
            continue
        scanned.add(gid)
        f = prior._player_components_any_team(gid, str(game.get("game_date") or ""), ids)
        if f is not None and not f.empty:
            frames.append(f)

    hist = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    counts = hist.groupby("PLAYER_ID")["GAME_ID"].nunique().to_dict() if not hist.empty else {}
    missing = {pid for pid in ids if int(counts.get(pid, 0)) < 3}

    if missing:
        for _, game in games.iterrows():
            gid = str(game.get("game_id") or "")
            if not gid or gid in scanned:
                continue
            f = prior._player_components_any_team(gid, str(game.get("game_date") or ""), tuple(sorted(missing)))
            if f is not None and not f.empty:
                frames.append(f)
                hist = pd.concat(frames, ignore_index=True)
                counts = hist.groupby("PLAYER_ID")["GAME_ID"].nunique().to_dict()
                missing = {pid for pid in missing if int(counts.get(pid, 0)) < 3}
                if not missing:
                    break

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["_d"] = pd.to_datetime(out.get("GAME_DATE"), errors="coerce")
    for col in ("MIN", "OREB", "DREB", "REB"):
        out[col] = pd.to_numeric(out.get(col), errors="coerce")
    out = out[out["MIN"].gt(0) & out["OREB"].notna() & out["DREB"].notna()].copy()
    out["REB"] = out["OREB"] + out["DREB"]
    out = out.sort_values("_d", ascending=False).drop_duplicates(["PLAYER_ID", "GAME_ID"])
    return out


def _window_stats(p: pd.DataFrame, n: int) -> dict:
    if p is None or p.empty:
        return {"gp": 0}
    x = p.sort_values("_d", ascending=False).head(int(n)).copy()
    mins = pd.to_numeric(x["MIN"], errors="coerce").fillna(0.0)
    reb = pd.to_numeric(x["REB"], errors="coerce").fillna(0.0)
    oreb = pd.to_numeric(x["OREB"], errors="coerce").fillna(0.0)
    dreb = pd.to_numeric(x["DREB"], errors="coerce").fillna(0.0)
    total_min = float(mins.sum())
    total_reb = float(reb.sum())
    total_oreb = float(oreb.sum())
    total_dreb = float(dreb.sum())
    game_rates = np.where(mins.to_numpy() > 0, 36.0 * reb.to_numpy() / mins.to_numpy(), np.nan)
    return {
        "gp": int(len(x)),
        "reb": float(reb.mean()) if len(x) else np.nan,
        "min": float(mins.mean()) if len(x) else np.nan,
        "reb36": 36.0 * total_reb / total_min if total_min > 0 else np.nan,
        "oreb36": 36.0 * total_oreb / total_min if total_min > 0 else np.nan,
        "dreb36": 36.0 * total_dreb / total_min if total_min > 0 else np.nan,
        "vol36": float(np.nanstd(game_rates, ddof=1)) if len(x) >= 3 else np.nan,
    }


def _season_lookup(day: str) -> pd.DataFrame:
    """Use the already-verified current-roster season/L10/L5 player pool."""
    try:
        frame, diag = players._build_selected_player_pool(pd.to_datetime(day).strftime("%Y-%m-%d"))
    except Exception:
        frame, diag = pd.DataFrame(), {}
    if frame is None:
        frame = pd.DataFrame()
    frame = frame.copy()
    if not frame.empty:
        frame["_NAME_KEY"] = frame.get("PLAYER_NAME", pd.Series("", index=frame.index)).map(_norm_name)
        frame["_PID"] = pd.to_numeric(frame.get("PLAYER_ID"), errors="coerce")
    frame.attrs["diagnostics"] = diag or {}
    return frame


def _match_season_row(pool: pd.DataFrame, row: pd.Series):
    if pool is None or pool.empty:
        return None
    pid = pd.to_numeric(pd.Series([row.get("PLAYER_ID")]), errors="coerce").iloc[0]
    if pd.notna(pid):
        hit = pool[pd.to_numeric(pool.get("_PID"), errors="coerce").eq(float(pid))]
        if not hit.empty:
            return hit.iloc[0]
    key = _norm_name(row.get("PLAYER_NAME"))
    hit = pool[pool.get("_NAME_KEY", pd.Series("", index=pool.index)).eq(key)]
    if "TEAM_NAME" in hit.columns and row.get("TEAM_NAME"):
        team_hit = hit[hit["TEAM_NAME"].astype(str).eq(str(row.get("TEAM_NAME")))]
        if not team_hit.empty:
            hit = team_hit
    return hit.iloc[0] if not hit.empty else None


def _stabilized_form_rate(season36, l10, l5, l3, season_gp):
    """Descriptive, regression-protected form rate — never a final projection."""
    s = _num(season36)
    vals, weights = [], []
    for value, weight in ((l10, 0.50), (l5, 0.30), (l3, 0.20)):
        v = _num(value)
        if pd.notna(v):
            vals.append(v)
            weights.append(weight)
    if not vals:
        return s, np.nan, np.nan
    recent = float(np.average(vals, weights=weights))
    if pd.isna(s) or s <= 0:
        return recent, recent, np.nan

    # Cap raw recent movement to ±20% of the season baseline before blending.
    # This prevents one heater/crash from taking over the future model layer.
    capped = float(np.clip(recent, 0.80 * s, 1.20 * s))
    gp = max(0.0, _num(season_gp, 0.0))
    recent_weight = min(0.35, 0.15 + 0.02 * min(gp, 10.0))
    stabilized = (1.0 - recent_weight) * s + recent_weight * capped
    return stabilized, recent, capped


def _build_step5_form(step4_players: pd.DataFrame, day: str, slate: pd.DataFrame):
    if step4_players is None or step4_players.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "no Step-4 rows"}

    pool = _season_lookup(day)
    frame = step4_players.copy()
    frame["PROJ_MIN"] = pd.to_numeric(frame.get("PROJ_MIN"), errors="coerce").fillna(0.0)
    frame["TEAM_ID_NUM"] = pd.to_numeric(frame.get("TEAM_ID"), errors="coerce").fillna(0).astype(int)
    outputs = []

    for tid, part in frame.groupby("TEAM_ID_NUM", sort=False):
        ids = []
        for value in part.get("PLAYER_ID", pd.Series(dtype=float)):
            try:
                ids.append(int(float(value)))
            except Exception:
                pass
        logs = _recent_player_rebound_logs(day, int(tid), tuple(ids))
        for _, row in part.iterrows():
            try:
                pid = int(float(row.get("PLAYER_ID")))
            except Exception:
                pid = 0
            p = logs[pd.to_numeric(logs.get("PLAYER_ID"), errors="coerce").eq(pid)].copy() if not logs.empty else pd.DataFrame()
            w3, w5, w10 = _window_stats(p, 3), _window_stats(p, 5), _window_stats(p, 10)
            srow = _match_season_row(pool, row)

            season_gp = int(_num(srow.get("GP"), 0)) if srow is not None else 0
            season_min = _num(srow.get("MIN"), np.nan) if srow is not None else np.nan
            season_reb = _num(srow.get("REB"), np.nan) if srow is not None else np.nan
            season36 = (36.0 * season_reb / season_min) if pd.notna(season_min) and season_min > 0 and pd.notna(season_reb) else np.nan

            # Prefer game-level verified windows. Existing pool values remain a
            # cross-check/fallback when provider summaries are temporarily sparse.
            l10_reb = _num(w10.get("reb"), _num(srow.get("L10_REB"), np.nan) if srow is not None else np.nan)
            l10_min = _num(w10.get("min"), _num(srow.get("L10_MIN"), np.nan) if srow is not None else np.nan)
            l10_36 = _num(w10.get("reb36"), (36.0 * l10_reb / l10_min) if pd.notna(l10_min) and l10_min > 0 else np.nan)
            l5_reb = _num(w5.get("reb"), _num(srow.get("L5_REB"), np.nan) if srow is not None else np.nan)
            l5_min = _num(w5.get("min"), _num(srow.get("L5_MIN"), np.nan) if srow is not None else np.nan)
            l5_36 = _num(w5.get("reb36"), (36.0 * l5_reb / l5_min) if pd.notna(l5_min) and l5_min > 0 else np.nan)
            l3_36 = _num(w3.get("reb36"), np.nan)

            stabilized, raw_recent, capped_recent = _stabilized_form_rate(season36, l10_36, l5_36, l3_36, season_gp)
            trend_pct = 100.0 * (stabilized / season36 - 1.0) if pd.notna(season36) and season36 > 0 and pd.notna(stabilized) else np.nan
            trend = "STEADY"
            if pd.notna(trend_pct):
                if trend_pct >= 4.0:
                    trend = "UP"
                elif trend_pct <= -4.0:
                    trend = "DOWN"

            out = row.to_dict()
            out.update({
                "FORM_SEASON_GP": season_gp,
                "FORM_SEASON_REB": season_reb,
                "FORM_SEASON_MIN": season_min,
                "FORM_SEASON_REB36": season36,
                "FORM_L10_GP": int(w10.get("gp") or 0),
                "FORM_L10_REB": l10_reb,
                "FORM_L10_REB36": l10_36,
                "FORM_L5_GP": int(w5.get("gp") or 0),
                "FORM_L5_REB": l5_reb,
                "FORM_L5_REB36": l5_36,
                "FORM_L3_GP": int(w3.get("gp") or 0),
                "FORM_L3_REB": _num(w3.get("reb"), np.nan),
                "FORM_L3_REB36": l3_36,
                "FORM_L5_OREB36": _num(w5.get("oreb36"), np.nan),
                "FORM_L5_DREB36": _num(w5.get("dreb36"), np.nan),
                "FORM_VOL_REB36": _num(w10.get("vol36"), np.nan),
                "FORM_RAW_RECENT36": raw_recent,
                "FORM_CAPPED_RECENT36": capped_recent,
                "FORM_STABILIZED_REB36": stabilized,
                "FORM_TREND_PCT": trend_pct,
                "FORM_TREND": trend,
            })
            out["FORM_SAMPLE"] = "VERIFIED" if season_gp >= 3 and int(w3.get("gp") or 0) >= 3 else "SHORT/CHECK"
            outputs.append(out)

    players_out = pd.DataFrame(outputs)
    modeled = players_out[pd.to_numeric(players_out.get("PROJ_MIN"), errors="coerce").fillna(0).ge(5.0)].copy() if not players_out.empty else pd.DataFrame()
    if not modeled.empty:
        covered_mask = (
            pd.to_numeric(modeled.get("FORM_SEASON_GP"), errors="coerce").fillna(0).ge(3)
            & pd.to_numeric(modeled.get("FORM_L3_GP"), errors="coerce").fillna(0).ge(3)
            & pd.to_numeric(modeled.get("FORM_SEASON_REB36"), errors="coerce").notna()
            & pd.to_numeric(modeled.get("FORM_L10_REB36"), errors="coerce").notna()
            & pd.to_numeric(modeled.get("FORM_STABILIZED_REB36"), errors="coerce").notna()
        )
        modeled["_COVERED"] = covered_mask
    else:
        covered_mask = pd.Series(dtype=bool)

    team_rows = []
    for team_name, part in modeled.groupby("TEAM_NAME", sort=False) if not modeled.empty else []:
        covered = int(part["_COVERED"].sum())
        total = int(len(part))
        team_rows.append({
            "Team": team_name,
            "Modeled ≥5 MIN": total,
            "Form covered": covered,
            "State": "VERIFIED" if total > 0 and covered == total else "CHECK",
        })
    teams_out = pd.DataFrame(team_rows)
    team_count = int(teams_out["Team"].nunique()) if not teams_out.empty else 0
    ready_teams = int(teams_out["State"].eq("VERIFIED").sum()) if not teams_out.empty else 0
    covered_players = int(modeled["_COVERED"].sum()) if not modeled.empty else 0
    ready = bool(team_count > 0 and ready_teams == team_count and covered_players == len(modeled))
    diag = pool.attrs.get("diagnostics", {}) if hasattr(pool, "attrs") else {}
    return players_out, teams_out, {
        "ready": ready,
        "teams": team_count,
        "ready_teams": ready_teams,
        "modeled_players": int(len(modeled)),
        "covered_players": covered_players,
        "season_source": str((diag or {}).get("source") or "verified WNBA player pool"),
    }


def _render_step5(day: str, step4_players: pd.DataFrame):
    players_out, teams_out, info = _build_step5_form(step4_players, day, pd.DataFrame())
    st.markdown("## 📈 Step 5 — Recent + Season Rebound Form")
    st.caption(
        "Verified season + L10/L5/L3 rebound form, normalized for minutes. The stabilized rate uses "
        "regression protection: recent form is capped to ±20% of the season REB/36 baseline before "
        "a limited recency blend. It is descriptive model infrastructure, not tonight's rebound projection."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Team form checks", f"{info.get('ready_teams',0)}/{info.get('teams',0)}")
    c2.metric("Modeled ≥5 MIN", info.get("modeled_players", 0))
    c3.metric("Form covered", info.get("covered_players", 0))
    c4.metric("Regression guard", "±20% cap")

    if info.get("ready"):
        st.success("✅ STEP 5 PASSED • every modeled rotation player has verified recent + season rebound form. Step 6 (rebound chances/opportunities) is unlocked.")
    else:
        st.error("⛔ STEP 5 CHECK • at least one modeled player lacks a verified recent/season rebound sample. Step 6 remains locked; nothing is guessed.")

    if not teams_out.empty:
        st.dataframe(teams_out, hide_index=True, use_container_width=True)

    if not players_out.empty:
        show = players_out[pd.to_numeric(players_out.get("PROJ_MIN"), errors="coerce").fillna(0).ge(5.0)].copy()
        show["Player"] = show.get("PLAYER_NAME", pd.Series("Player", index=show.index)).astype(str)
        show["Team"] = show.get("TEAM_NAME", pd.Series("", index=show.index)).astype(str)
        show["Proj MIN"] = pd.to_numeric(show.get("PROJ_MIN"), errors="coerce").round(1)
        show["Season GP"] = pd.to_numeric(show.get("FORM_SEASON_GP"), errors="coerce").fillna(0).astype(int)
        show["Season REB"] = pd.to_numeric(show.get("FORM_SEASON_REB"), errors="coerce").round(1)
        show["Season /36"] = pd.to_numeric(show.get("FORM_SEASON_REB36"), errors="coerce").round(2)
        show["L10 REB"] = pd.to_numeric(show.get("FORM_L10_REB"), errors="coerce").round(1)
        show["L5 REB"] = pd.to_numeric(show.get("FORM_L5_REB"), errors="coerce").round(1)
        show["L3 REB"] = pd.to_numeric(show.get("FORM_L3_REB"), errors="coerce").round(1)
        show["L5 OREB/36"] = pd.to_numeric(show.get("FORM_L5_OREB36"), errors="coerce").round(2)
        show["L5 DREB/36"] = pd.to_numeric(show.get("FORM_L5_DREB36"), errors="coerce").round(2)
        show["Stable /36"] = pd.to_numeric(show.get("FORM_STABILIZED_REB36"), errors="coerce").round(2)
        show["Vol /36"] = pd.to_numeric(show.get("FORM_VOL_REB36"), errors="coerce").round(2)
        show["Trend"] = show.get("FORM_TREND", pd.Series("", index=show.index)).astype(str)
        show["Sample"] = show.get("FORM_SAMPLE", pd.Series("", index=show.index)).astype(str)
        with st.expander("📊 Player recent + season rebound-form board", expanded=False):
            st.dataframe(
                show[["Player", "Team", "Proj MIN", "Season GP", "Season REB", "Season /36", "L10 REB", "L5 REB", "L3 REB", "L5 OREB/36", "L5 DREB/36", "Stable /36", "Vol /36", "Trend", "Sample"]],
                hide_index=True,
                use_container_width=True,
            )
            st.caption("Stable /36 is a guarded form descriptor only. Step 6 will add actual rebound chances/opportunities; later layers still handle opponent environment, lineup competition and market/simulation logic.")

    st.session_state["wnba_rebounds_step5_ready"] = bool(info.get("ready"))
    st.session_state["wnba_rebounds_step5_players"] = players_out.to_dict("records") if not players_out.empty else []
    st.session_state["wnba_rebounds_step5_team_checks"] = teams_out.to_dict("records") if not teams_out.empty else []
    return info


def _render_step4_plus_form(slate: pd.DataFrame, day: str, minute_players: pd.DataFrame):
    step4 = _ORIGINAL_STEP4(slate, day, minute_players)
    if not bool((step4 or {}).get("ready")):
        st.session_state["wnba_rebounds_step5_ready"] = False
        st.info("🔒 Step 5 remains locked until the verified Step-4 OREB/DREB role gate passes.")
        return step4
    records = st.session_state.get("wnba_rebounds_step4_players") or []
    _render_step5(day, pd.DataFrame(records))
    return step4


def _tracker(step1_ok: bool, step2_info: dict):
    step2_ok = bool((step2_info or {}).get("ready"))
    step3_ok = bool((step2_info or {}).get("step3_ready"))
    step4_ok = bool(st.session_state.get("wnba_rebounds_step4_ready", False))
    step5_ok = bool(st.session_state.get("wnba_rebounds_step5_ready", False))
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
        if n == "1": status = "✅ LIVE" if step1_ok else "⛔ CHECK"
        elif n == "2": status = "✅ LIVE" if step2_ok else ("⚠️ ACTIVE / CHECK" if step1_ok else "🔒 LOCKED")
        elif n == "3": status = "✅ LIVE" if step3_ok else ("➡️ NEXT" if step2_ok else "🔒 LOCKED")
        elif n == "4": status = "✅ LIVE" if step4_ok else ("⚠️ ACTIVE / CHECK" if step3_ok else "🔒 LOCKED")
        elif n == "5": status = "✅ LIVE" if step5_ok else ("⚠️ ACTIVE / CHECK" if step4_ok else "🔒 LOCKED")
        elif n == "6" and step5_ok: status = "➡️ NEXT"
        else: status = "🔒 LOCKED"
        rows.append({"Step": n, "Layer": label, "Status": status})
    return pd.DataFrame(rows)


def _versioned_markdown_14(body, *args, **kwargs):
    text = str(body)
    text = text.replace("WNBA Rebounds Command Center — V1.1", "WNBA Rebounds Command Center — V1.4")
    text = text.replace("WNBA Rebounds Command Center — V1.2", "WNBA Rebounds Command Center — V1.4")
    text = text.replace("WNBA Rebounds Command Center — V1.3.2", "WNBA Rebounds Command Center — V1.4")
    text = text.replace("WNBA Rebounds Command Center — V1.3", "WNBA Rebounds Command Center — V1.4")
    return role.impl._ORIGINAL_MARKDOWN(text, *args, **kwargs)


def _caption_14(body, *args, **kwargs):
    text = str(body)
    if text.startswith(("🧲 WNBA Rebounds V1.3.2", "🧲 WNBA Rebounds V1.3", "⏱️ WNBA Rebounds V1.2")):
        text = "📈 WNBA Rebounds V1.4 • Steps 1–5 active • verified recent + season form with regression protection • no rebound projection/market/simulation yet"
    return role._ORIGINAL_CAPTION(text, *args, **kwargs)


def _success_filter(body, *args, **kwargs):
    text = str(body)
    if text.startswith("✅ STEPS 1–2 VERIFIED") or text.startswith("✅ STEPS 1–4 VERIFIED"):
        return None
    return _ORIGINAL_SUCCESS(body, *args, **kwargs)


def render_wnba_rebounds_hub(*args, **kwargs):
    old_step4 = role._render_step4
    old_tracker = role._tracker
    old_v132_markdown = prior._versioned_markdown_132
    old_v132_caption = prior._caption_132
    old_success = st.success

    role._render_step4 = _render_step4_plus_form
    role._tracker = _tracker
    prior._versioned_markdown_132 = _versioned_markdown_14
    prior._caption_132 = _caption_14
    st.success = _success_filter
    try:
        out = prior.render_wnba_rebounds_hub(*args, **kwargs)
    finally:
        role._render_step4 = old_step4
        role._tracker = old_tracker
        prior._versioned_markdown_132 = old_v132_markdown
        prior._caption_132 = old_v132_caption
        st.success = old_success

    if st.session_state.get("wnba_rebounds_step5_ready"):
        st.success("✅ STEPS 1–5 VERIFIED • Step 6 (rebound chances/opportunities) is now the next unlocked development layer. No sportsbook line, final projection, or Monte Carlo input is active.")
    else:
        st.info("Step 5 is active. Step 6 remains locked until recent + season rebound-form coverage passes for every modeled rotation player.")
    return out


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
