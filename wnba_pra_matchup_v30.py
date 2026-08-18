"""WNBA PRA V3.0 — Step 7 matchup/pace adjustment + exact market grading.

WNBA-only. MLB V2.1.7 remains frozen.

This layer keeps Step 5 minutes/role projections and Step 6 exact SportsGameOdds
market verification, then adds modest, capped matchup adjustments from the
already-verified WNBA context layer:
- expected pace from both teams' recent pace;
- opponent recent defensive rating (PA fallback if advanced sample unavailable);
- separate PTS/REB/AST multipliers so PRA is not adjusted as one blunt number;
- confirmed starter/lineup state remains a risk flag and is never inferred.

Sportsbook prices never alter projections. H2H is display-only and is NOT used as
a projection multiplier. Final production 5M/10M Monte Carlo remains the next step.
"""
from __future__ import annotations

from statistics import NormalDist

import numpy as np
import pandas as pd
import streamlit as st

import wnba_context_v26 as context
import wnba_pra_market_v29 as step6
import wnba_role_v282 as role
import wnba_sportsgameodds_v1 as sgo

MODEL_VERSION = "PRA V3.0 STEP 7"


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _mean_valid(values):
    vals = [float(v) for v in values if pd.notna(v) and np.isfinite(float(v))]
    return float(np.mean(vals)) if vals else np.nan


def _baseline_from_contexts(contexts):
    pace, drtg, pa = [], [], []
    for game_ctx in (contexts or {}).values():
        for side in ("away", "home"):
            obj = (game_ctx or {}).get(side) or {}
            p = _num(obj.get("PACE_L10"), np.nan)
            d = _num(obj.get("DRTG_L10"), np.nan)
            a = _num(obj.get("L10_PA"), np.nan)
            if pd.notna(p) and p > 0:
                pace.append(p)
            if pd.notna(d) and d > 0:
                drtg.append(d)
            if pd.notna(a) and a > 0:
                pa.append(a)
    return {
        "pace": _mean_valid(pace),
        "drtg": _mean_valid(drtg),
        "pa": _mean_valid(pa),
        "pace_n": len(pace),
        "drtg_n": len(drtg),
    }


def _context_quality(team_ctx, opp_ctx):
    ta = int(_num((team_ctx or {}).get("ADV_GAMES"), 0))
    oa = int(_num((opp_ctx or {}).get("ADV_GAMES"), 0))
    if ta >= 8 and oa >= 8:
        return 1.0
    if ta >= 5 and oa >= 5:
        return 0.90
    if ta >= 3 and oa >= 3:
        return 0.78
    if ta or oa:
        return 0.64
    return 0.50


def _matchup_factors(team_ctx, opp_ctx, baseline):
    team_pace = _num((team_ctx or {}).get("PACE_L10"), np.nan)
    opp_pace = _num((opp_ctx or {}).get("PACE_L10"), np.nan)
    expected_pace = _mean_valid([team_pace, opp_pace])
    pace_base = _num((baseline or {}).get("pace"), np.nan)

    if pd.notna(expected_pace) and pd.notna(pace_base) and pace_base > 0:
        pace_factor = float(np.clip(expected_pace / pace_base, 0.955, 1.045))
        pace_source = "L10 pace"
    else:
        pace_factor = 1.0
        pace_source = "neutral"

    opp_drtg = _num((opp_ctx or {}).get("DRTG_L10"), np.nan)
    drtg_base = _num((baseline or {}).get("drtg"), np.nan)
    opp_pa = _num((opp_ctx or {}).get("L10_PA"), np.nan)
    pa_base = _num((baseline or {}).get("pa"), np.nan)

    if pd.notna(opp_drtg) and pd.notna(drtg_base) and drtg_base > 0:
        raw_def = opp_drtg / drtg_base
        defense_factor = float(np.clip(raw_def ** 0.55, 0.945, 1.055))
        defense_source = "opp L10 DRTG"
    elif pd.notna(opp_pa) and pd.notna(pa_base) and pa_base > 0:
        raw_def = opp_pa / pa_base
        defense_factor = float(np.clip(raw_def ** 0.30, 0.955, 1.045))
        defense_source = "opp L10 PA fallback"
    else:
        defense_factor = 1.0
        defense_source = "neutral"

    pts_factor = float(np.clip((pace_factor ** 0.90) * (defense_factor ** 0.85), 0.92, 1.08))
    reb_factor = float(np.clip((pace_factor ** 0.65) * (defense_factor ** 0.10), 0.95, 1.05))
    ast_factor = float(np.clip((pace_factor ** 0.75) * (defense_factor ** 0.35), 0.94, 1.06))

    return {
        "expected_pace": expected_pace,
        "pace_factor": pace_factor,
        "defense_factor": defense_factor,
        "pts_factor": pts_factor,
        "reb_factor": reb_factor,
        "ast_factor": ast_factor,
        "pace_source": pace_source,
        "defense_source": defense_source,
        "opp_drtg_l10": opp_drtg,
        "opp_pa_l10": opp_pa,
        "context_quality": _context_quality(team_ctx, opp_ctx),
    }


def matchup_projection_frame(day):
    schedule = role.schedule_for_date(day)
    stats = role.player_form_table()
    if schedule is None or schedule.empty or stats is None or stats.empty:
        return pd.DataFrame(), {"schedule": schedule, "context_diag": {}, "availability_diag": {}}

    contexts, context_diag = context.slate_context(pd.to_datetime(day).strftime("%Y-%m-%d"))
    baseline = _baseline_from_contexts(contexts)
    try:
        availability_diag = role.availability_diagnostics(day)
    except Exception:
        availability_diag = {}

    rows = []
    for _, game in schedule.iterrows():
        status = str(game.get("status") or game.get("status_text") or "").upper()
        if "FINAL" in status:
            continue

        game_id = str(game.get("game_id") or "")
        game_ctx = contexts.get(game_id) or context.game_context(game, day) or {}
        result = role.role_projection_for_game(game, stats)

        for team_id, frame in (result.get("teams") or {}).items():
            if frame is None or frame.empty:
                continue

            is_away = int(team_id) == int(game.get("away_team_id") or 0)
            team_side, opp_side = ("away", "home") if is_away else ("home", "away")
            team_ctx = game_ctx.get(team_side) or {}
            opp_ctx = game_ctx.get(opp_side) or {}
            factors = _matchup_factors(team_ctx, opp_ctx, baseline)

            team_name = game.get("away_team") if is_away else game.get("home_team")
            opponent = game.get("home_team") if is_away else game.get("away_team")

            for _, p in frame.iterrows():
                name = str(p.get("PLAYER_NAME") or "").strip()
                if not name:
                    continue

                raw_pts = max(0.0, _num(p.get("PROJ_PTS"), 0.0))
                raw_reb = max(0.0, _num(p.get("PROJ_REB"), 0.0))
                raw_ast = max(0.0, _num(p.get("PROJ_AST"), 0.0))
                raw_pra = raw_pts + raw_reb + raw_ast

                adj_pts = raw_pts * factors["pts_factor"]
                adj_reb = raw_reb * factors["reb_factor"]
                adj_ast = raw_ast * factors["ast_factor"]
                adj_pra = adj_pts + adj_reb + adj_ast

                row = p.to_dict()
                row.update({
                    "game_id": game_id,
                    "game_status": status,
                    "team_name": str(team_name or ""),
                    "opponent": str(opponent or ""),
                    "player_key": sgo._norm(name),
                    "RAW_PROJ_PTS": raw_pts,
                    "RAW_PROJ_REB": raw_reb,
                    "RAW_PROJ_AST": raw_ast,
                    "RAW_PROJ_PRA": raw_pra,
                    "PROJ_PTS": adj_pts,
                    "PROJ_REB": adj_reb,
                    "PROJ_AST": adj_ast,
                    "PROJ_PRA": adj_pra,
                    **factors,
                })
                rows.append(row)

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.drop_duplicates(subset=["game_id", "player_key"], keep="first")
    return out, {
        "schedule": schedule,
        "context_diag": context_diag,
        "availability_diag": availability_diag,
        "baseline": baseline,
    }


def grade_matchup_pra(day):
    projections, pmeta = matchup_projection_frame(day)
    pairs, snap = step6._paired_pra_markets(day)
    if projections.empty or pairs.empty:
        return pd.DataFrame(), {"snapshot": snap, "projections": len(projections), "pairs": len(pairs), **pmeta}

    by_key = {
        (str(p.get("game_id") or ""), str(p.get("player_key") or "")): p
        for _, p in projections.iterrows()
    }

    rows = []
    unmatched = set()
    for _, m in pairs.iterrows():
        key = (str(m.get("game_id") or ""), str(m.get("player_key") or ""))
        proj = by_key.get(key)
        if proj is None:
            unmatched.add(str(m.get("player_name") or "Player"))
            continue

        line = _num(m.get("line"), np.nan)
        mu = _num(proj.get("PROJ_PRA"), np.nan)
        raw_mu = _num(proj.get("RAW_PROJ_PRA"), np.nan)
        if pd.isna(line) or pd.isna(mu) or mu <= 0:
            continue

        sd, hist_games, data_quality, variance_source = step6._pra_sd(proj)
        dist = NormalDist(mu=float(mu), sigma=max(float(sd), 0.5))
        p_over = float(np.clip(1.0 - dist.cdf(float(line)), 0.01, 0.99))
        p_under = 1.0 - p_over

        nv_over, nv_under = step6._no_vig(m.get("over_odds"), m.get("under_odds"))
        edge = p_over - nv_over if pd.notna(nv_over) else np.nan
        profit = step6._profit_per_dollar(m.get("over_odds"))
        ev100 = ((p_over * profit - (1.0 - p_over)) * 100.0) if pd.notna(profit) else np.nan
        fresh_label, fresh_score = step6._freshness(m.get("market_age"))

        role_label = str(proj.get("ROLE_LABEL") or "ACTIVE")
        status = "READY"
        if role_label == "STATUS UNCERTAIN":
            status = "MONITOR"
        if fresh_label == "AGING" and status == "READY":
            status = "MONITOR"
        if fresh_label == "STALE":
            status = "STALE"
        if _num(proj.get("context_quality"), 0.0) < 0.60 and status == "READY":
            status = "MONITOR"

        rows.append({
            "player": str(proj.get("PLAYER_NAME") or m.get("player_name") or "Player"),
            "team": str(proj.get("team_name") or ""),
            "opponent": str(proj.get("opponent") or ""),
            "game_id": str(m.get("game_id") or ""),
            "book": str(m.get("book") or ""),
            "line": float(line),
            "raw_projection": float(raw_mu),
            "projection": float(mu),
            "matchup_delta": float(mu - raw_mu),
            "line_delta": float(mu - line),
            "proj_pts": _num(proj.get("PROJ_PTS"), np.nan),
            "proj_reb": _num(proj.get("PROJ_REB"), np.nan),
            "proj_ast": _num(proj.get("PROJ_AST"), np.nan),
            "pace_factor": _num(proj.get("pace_factor"), 1.0),
            "defense_factor": _num(proj.get("defense_factor"), 1.0),
            "expected_pace": _num(proj.get("expected_pace"), np.nan),
            "opp_drtg_l10": _num(proj.get("opp_drtg_l10"), np.nan),
            "context_quality": _num(proj.get("context_quality"), 0.5),
            "sd_pra": float(sd),
            "model_over": p_over,
            "model_under": p_under,
            "no_vig_over": nv_over,
            "no_vig_under": nv_under,
            "edge": edge,
            "over_odds": m.get("over_odds"),
            "under_odds": m.get("under_odds"),
            "fair_over": step6._fair_american(p_over),
            "fair_under": step6._fair_american(p_under),
            "ev100": ev100,
            "market_age": _num(m.get("market_age"), np.nan),
            "freshness": fresh_label,
            "fresh_score": fresh_score,
            "data_quality": data_quality,
            "hist_games": hist_games,
            "variance_source": variance_source,
            "proj_min": _num(proj.get("PROJ_MIN"), np.nan),
            "role_label": role_label,
            "status": status,
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out, {"snapshot": snap, "projections": len(projections), "pairs": len(pairs), "unmatched_players": sorted(unmatched), **pmeta}

    out["_price_sort"] = pd.to_numeric(out["over_odds"], errors="coerce").fillna(-100000)
    out["eligible"] = (
        out["no_vig_over"].notna()
        & out["edge"].notna()
        & out["model_over"].ge(0.54)
        & out["edge"].ge(0.030)
        & out["proj_min"].fillna(0).ge(10.0)
        & out["freshness"].ne("STALE")
        & out["context_quality"].ge(0.60)
        & out["role_label"].ne("OUT")
    )
    out["matchup_grade"] = 100.0 * (
        0.50 * out["model_over"]
        + 0.24 * (0.50 + out["edge"].fillna(0.0)).clip(0.0, 1.0)
        + 0.10 * out["data_quality"].clip(0.0, 1.0)
        + 0.08 * out["context_quality"].clip(0.0, 1.0)
        + 0.08 * out["fresh_score"].clip(0.0, 1.0)
    )
    out = out.sort_values(["eligible", "matchup_grade", "edge", "_price_sort"], ascending=[False, False, False, False]).reset_index(drop=True)

    return out.drop(columns=["_price_sort"]), {
        "snapshot": snap,
        "projections": len(projections),
        "pairs": len(pairs),
        "unmatched_players": sorted(unmatched),
        **pmeta,
    }


def _pct(value):
    try:
        return f"{100.0 * float(value):.1f}%"
    except Exception:
        return "—"


def _factor(value):
    try:
        return f"{float(value):.3f}×"
    except Exception:
        return "—"


def render_matchup_grade(day):
    st.markdown("### 🧭 Step 7 — WNBA Matchup + Pace Adjustment")
    st.caption(
        "Step-5 minutes/role → verified recent pace + opponent defense → exact PRA line. "
        "P/R/A are adjusted separately; H2H remains descriptive only. Sportsbook price never changes the projection."
    )

    with st.spinner("🧭 Applying verified WNBA matchup context to PRA projections…"):
        graded, meta = grade_matchup_pra(day)

    cdiag = meta.get("context_diag") or {}
    adiag = meta.get("availability_diag") or {}
    baseline = meta.get("baseline") or {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Context teams", f"{cdiag.get('advanced_teams',0)}/{cdiag.get('teams',0)}")
    c2.metric("Advanced samples", int(cdiag.get("advanced_games", 0) or 0))
    c3.metric("Lineups confirmed", f"{adiag.get('lineups_confirmed',0)}/{adiag.get('teams',0)}")
    c4.metric("Exact PRA matches", 0 if graded is None else len(graded))

    pace_base = _num(baseline.get("pace"), np.nan)
    drtg_base = _num(baseline.get("drtg"), np.nan)
    pace_text = "—" if pd.isna(pace_base) else f"{pace_base:.1f}"
    drtg_text = "—" if pd.isna(drtg_base) else f"{drtg_base:.1f}"
    st.caption(
        f"Dynamic slate baseline • Pace {pace_text} • DRTG {drtg_text} when available. "
        "All matchup multipliers are deliberately capped to prevent one context feed from overpowering the player model."
    )

    if int(adiag.get("lineups_confirmed", 0) or 0) < int(adiag.get("teams", 0) or 0):
        st.warning(
            "⚠️ Confirmed starting fives are still pending for part/all of this slate. "
            "Step 7 does not infer starters. Any current ranking remains pre-lineup and will be rechecked when explicit starters publish."
        )

    if graded is None or graded.empty:
        st.info("No exact PRA projection/market matches are available for Step 7 right now.")
        return

    eligible = graded.loc[graded["eligible"].eq(True)].copy()
    if not eligible.empty:
        best = eligible.sort_values(["matchup_grade", "edge"], ascending=[False, False]).drop_duplicates(subset=["player"], keep="first").head(5)
        st.markdown("#### 🏆 Step 7 Qualified PRA Overs")
        for rank, (_, r) in enumerate(best.iterrows(), start=1):
            st.markdown(
                f"**#{rank} {r['player']} — OVER {r['line']:.1f} ({r['book']})**  \n"
                f"Raw {r['raw_projection']:.1f} → Matchup {r['projection']:.1f} ({r['matchup_delta']:+.1f}) • "
                f"Model {_pct(r['model_over'])} • No-vig {_pct(r['no_vig_over'])} • "
                f"Edge {100.0*r['edge']:+.1f} pp • Fair {step6._fmt_odds(r['fair_over'])} • Status {r['status']}"
            )
    else:
        st.info(
            "No PRA overs clear the Step-7 matchup + probability + no-vig + freshness gates. "
            "That is a valid result; no pick is forced."
        )

    with st.expander("🧾 All Step-7 PRA model-vs-market matches", expanded=True):
        show = graded.copy()
        show["Model Over"] = show["model_over"].map(_pct)
        show["No-vig Over"] = show["no_vig_over"].map(_pct)
        show["Edge"] = show["edge"].map(lambda x: "—" if pd.isna(x) else f"{100.0*x:+.1f} pp")
        show["Raw PRA"] = show["raw_projection"].map(lambda x: f"{x:.2f}")
        show["Adj PRA"] = show["projection"].map(lambda x: f"{x:.2f}")
        show["Matchup Δ"] = show["matchup_delta"].map(lambda x: f"{x:+.2f}")
        show["Pace"] = show["pace_factor"].map(_factor)
        show["Opp D"] = show["defense_factor"].map(_factor)
        show["Price"] = show["over_odds"].map(step6._fmt_odds)
        show["Fair"] = show["fair_over"].map(step6._fmt_odds)
        show["Fresh"] = show["market_age"].map(step6._age)
        st.dataframe(
            show[["player", "book", "line", "Raw PRA", "Adj PRA", "Matchup Δ", "Pace", "Opp D", "Model Over", "No-vig Over", "Edge", "Price", "Fair", "Fresh", "status"]].rename(columns={"player":"Player","book":"Book","line":"Line","status":"Status"}),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Step 7 adjustment rules", expanded=False):
        st.write({
            "pace": "Average of both teams' recent verified pace vs dynamic slate baseline; capped.",
            "opponent_defense": "Opponent recent DRTG vs dynamic slate baseline; L10 PA fallback; capped.",
            "points": "Most sensitive to pace + defense.",
            "rebounds": "Mostly possession-volume sensitive; defense influence kept small.",
            "assists": "Moderate pace + defense sensitivity.",
            "H2H": "Display-only. No projection multiplier.",
            "sportsbook_price_in_projection": False,
            "starters_inferred": False,
            "final_5M_10M_monte_carlo_active": False,
            "mlb_files_touched": False,
        })


__all__ = ["MODEL_VERSION", "matchup_projection_frame", "grade_matchup_pra", "render_matchup_grade"]
