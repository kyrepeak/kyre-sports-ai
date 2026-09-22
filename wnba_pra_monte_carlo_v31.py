"""WNBA PRA V3.1 — Step 8 production Monte Carlo engine.

WNBA-only module. MLB V2.1.7 remains frozen.

Step 8 takes the Step-7 matchup-adjusted PTS/REB/AST means and exact verified
SportsGameOdds PRA markets, then executes an actual batched correlated Monte
Carlo simulation. The sportsbook never changes the projection distribution; it
is used only after simulation for no-vig/edge/EV grading.

Simulation policy:
- standard: 5,000,000 simulations per unique game+player+PRA line;
- final/close finalists: 10,000,000 simulations per unique finalist line;
- identical player/line markets across books reuse one simulated distribution;
- random seed, batch count, Monte Carlo SE, max batch spread and convergence are
  reported; no simulation count is displayed unless it actually completed;
- confirmed starting fives are never inferred. Pending lineups widen uncertainty
  and prevent a pick from being labeled FINAL READY.
"""
from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd
import streamlit as st

import wnba_pra_matchup_v30 as step7
import wnba_pra_market_v29 as step6
import wnba_role_v282 as role
import wnba_sportsgameodds_v1 as sgo

MODEL_VERSION = "PRA V3.1 STEP 8 MC"
STANDARD_SIMS = 5_000_000
FINAL_SIMS = 10_000_000
BATCH_SIZE = 250_000
CONVERGENCE_BATCH_SPREAD = 0.006


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _stable_seed(day, game_id, player_key, line, sims):
    token = f"{MODEL_VERSION}|{day}|{game_id}|{player_key}|{float(line):.3f}|{int(sims)}"
    raw = hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]
    return int(raw, 16)


def _nearest_psd(cov):
    a = np.asarray(cov, dtype=float)
    a = (a + a.T) / 2.0
    vals, vecs = np.linalg.eigh(a)
    vals = np.clip(vals, 1e-6, None)
    out = (vecs * vals) @ vecs.T
    return (out + out.T) / 2.0


def _component_distribution(proj, lineup_ready=False):
    means = np.asarray([
        max(0.0, _num(proj.get("PROJ_PTS"), 0.0)),
        max(0.0, _num(proj.get("PROJ_REB"), 0.0)),
        max(0.0, _num(proj.get("PROJ_AST"), 0.0)),
    ], dtype=float)

    try:
        profile = step6._empirical_for_player(proj.get("PLAYER_ID")) or {}
    except Exception:
        profile = {}
    games = int(profile.get("games") or 0)

    if games >= 5:
        sds = np.asarray([
            max(1.25, _num(profile.get("sd_pts"), 2.8)),
            max(0.90, _num(profile.get("sd_reb"), 1.8)),
            max(0.80, _num(profile.get("sd_ast"), 1.6)),
        ], dtype=float)
        corr = np.asarray([
            [1.0, float(np.clip(_num(profile.get("corr_pr"), 0.0), -0.75, 0.75)), float(np.clip(_num(profile.get("corr_pa"), 0.0), -0.75, 0.75))],
            [float(np.clip(_num(profile.get("corr_pr"), 0.0), -0.75, 0.75)), 1.0, float(np.clip(_num(profile.get("corr_ra"), 0.0), -0.75, 0.75))],
            [float(np.clip(_num(profile.get("corr_pa"), 0.0), -0.75, 0.75)), float(np.clip(_num(profile.get("corr_ra"), 0.0), -0.75, 0.75)), 1.0],
        ], dtype=float)
        source = "EMPIRICAL CORRELATED"
        quality = min(1.0, 0.58 + min(games, 30) / 30.0 * 0.34)
    else:
        sds = np.asarray([
            max(2.4, math.sqrt(max(means[0], 1.0)) * 1.20),
            max(1.5, math.sqrt(max(means[1], 1.0)) * 1.10),
            max(1.3, math.sqrt(max(means[2], 1.0)) * 1.12),
        ], dtype=float)
        corr = np.eye(3, dtype=float)
        source = "FALLBACK INDEPENDENT"
        quality = 0.48

    # Widen uncertainty rather than changing the mean when context/lineup/role is
    # unresolved. This makes the risk layer honest without contaminating projection.
    context_q = float(np.clip(_num(proj.get("context_quality"), 0.5), 0.0, 1.0))
    role_label = str(proj.get("ROLE_LABEL") or "ACTIVE").upper()
    uncertainty_mult = 1.0 + 0.08 * (1.0 - context_q)
    if not lineup_ready:
        uncertainty_mult += 0.08
    if "UNCERTAIN" in role_label:
        uncertainty_mult += 0.10
    if _num(proj.get("PROJ_MIN"), 0.0) < 15.0:
        uncertainty_mult += 0.04
    sds = sds * uncertainty_mult

    cov = corr * np.outer(sds, sds)
    cov = _nearest_psd(cov)
    return means, cov, {
        "hist_games": games,
        "variance_source": source,
        "data_quality": quality,
        "uncertainty_mult": float(uncertainty_mult),
        "component_sd_pts": float(math.sqrt(cov[0, 0])),
        "component_sd_reb": float(math.sqrt(cov[1, 1])),
        "component_sd_ast": float(math.sqrt(cov[2, 2])),
    }


def _lineup_map(day, schedule, stats):
    result = {}
    if schedule is None or schedule.empty:
        return result
    for _, game in schedule.iterrows():
        gid = str(game.get("game_id") or "")
        status = str(game.get("status") or game.get("status_text") or "").upper()
        if "FINAL" in status:
            continue
        ready = False
        try:
            av = role.availability_for_game(game, stats)
            counts = av.get("starter_counts") or {}
            away = int(game.get("away_team_id") or 0)
            home = int(game.get("home_team_id") or 0)
            ready = int(counts.get(away, 0)) >= 5 and int(counts.get(home, 0)) >= 5
        except Exception:
            ready = False
        result[gid] = bool(ready)
    return result


def _hist_quantile(hist, q):
    if hist is None or len(hist) == 0:
        return np.nan
    total = int(np.sum(hist))
    if total <= 0:
        return np.nan
    target = max(1, int(math.ceil(float(q) * total)))
    return float(np.searchsorted(np.cumsum(hist), target, side="left"))


@st.cache_data(ttl=900, show_spinner=False, max_entries=256)
def _simulate_distribution_cached(day, game_id, player_key, line, means_tuple, cov_tuple, sims, seed, batch_size):
    means = np.asarray(means_tuple, dtype=float)
    cov = np.asarray(cov_tuple, dtype=float).reshape(3, 3)
    n_sims = int(sims)
    batch_size = int(max(10_000, batch_size))
    rng = np.random.default_rng(int(seed))

    completed = 0
    over = under = push = 0
    total_sum = total_sq = 0.0
    hist = np.zeros(128, dtype=np.int64)
    batch_ps = []
    batches = 0
    started = time.perf_counter()

    line_float = float(line)
    integer_line = abs(line_float - round(line_float)) < 1e-9

    while completed < n_sims:
        n = min(batch_size, n_sims - completed)
        draws = rng.multivariate_normal(mean=means, cov=cov, size=n, check_valid="ignore")
        draws = np.rint(np.clip(draws, 0.0, None)).astype(np.int16, copy=False)
        pra = draws.sum(axis=1, dtype=np.int32)

        if integer_line:
            target = int(round(line_float))
            o = int(np.count_nonzero(pra > target))
            u = int(np.count_nonzero(pra < target))
            p = n - o - u
        else:
            o = int(np.count_nonzero(pra > line_float))
            u = n - o
            p = 0

        over += o; under += u; push += p
        completed += n; batches += 1
        total_sum += float(pra.sum(dtype=np.int64))
        total_sq += float(np.square(pra.astype(np.float64)).sum())
        bc = np.bincount(np.minimum(pra, len(hist) - 1), minlength=len(hist))
        hist += bc[:len(hist)]
        resolved = o + u
        batch_ps.append(o / resolved if resolved > 0 else 0.5)

    resolved = over + under
    p_over_resolved = over / resolved if resolved else 0.5
    p_under_resolved = under / resolved if resolved else 0.5
    p_push = push / completed if completed else 0.0
    p_over_raw = over / completed if completed else 0.0
    p_under_raw = under / completed if completed else 0.0
    mc_se = math.sqrt(max(p_over_resolved * (1.0 - p_over_resolved), 0.0) / max(resolved, 1))
    batch_spread = (max(batch_ps) - min(batch_ps)) if len(batch_ps) > 1 else 0.0
    mean_pra = total_sum / completed if completed else np.nan
    var_pra = max(total_sq / completed - mean_pra * mean_pra, 0.0) if completed else np.nan
    mode = float(np.argmax(hist)) if hist.sum() else np.nan

    return {
        "sims": int(completed),
        "batches": int(batches),
        "seed": int(seed),
        "p_over": float(p_over_resolved),
        "p_under": float(p_under_resolved),
        "p_over_raw": float(p_over_raw),
        "p_under_raw": float(p_under_raw),
        "p_push": float(p_push),
        "mc_se": float(mc_se),
        "max_batch_diff": float(batch_spread),
        "converged": bool(batch_spread <= CONVERGENCE_BATCH_SPREAD and mc_se <= 0.0005),
        "mean_pra": float(mean_pra),
        "sd_pra": float(math.sqrt(var_pra)) if np.isfinite(var_pra) else np.nan,
        "median_pra": _hist_quantile(hist, 0.50),
        "mode_pra": mode,
        "p10": _hist_quantile(hist, 0.10),
        "p90": _hist_quantile(hist, 0.90),
        "elapsed_s": float(time.perf_counter() - started),
    }


def _prepare(day):
    projections, pmeta = step7.matchup_projection_frame(day)
    pairs, snap = step6._paired_pra_markets(day)
    schedule = pmeta.get("schedule")
    stats = role.player_form_table()
    lineups = _lineup_map(day, schedule, stats)
    return projections, pairs, snap, pmeta, lineups


def _market_rows(day, sim_count=STANDARD_SIMS, progress=None):
    projections, pairs, snap, pmeta, lineups = _prepare(day)
    if projections is None or projections.empty or pairs is None or pairs.empty:
        return pd.DataFrame(), {"snapshot": snap, "pairs": 0, **pmeta}

    pmap = {
        (str(r.get("game_id") or ""), str(r.get("player_key") or "")): r
        for _, r in projections.iterrows()
    }
    unique_units = pairs[["game_id", "player_key", "player_name", "line"]].drop_duplicates().reset_index(drop=True)
    sim_map = {}
    meta_map = {}
    total_units = len(unique_units)

    for i, unit in unique_units.iterrows():
        gid = str(unit.get("game_id") or "")
        pkey = str(unit.get("player_key") or "")
        line = _num(unit.get("line"), np.nan)
        proj = pmap.get((gid, pkey))
        if proj is None or pd.isna(line):
            continue
        lineup_ready = bool(lineups.get(gid, False))
        means, cov, dist_meta = _component_distribution(proj, lineup_ready=lineup_ready)
        seed = _stable_seed(day, gid, pkey, line, sim_count)
        result = _simulate_distribution_cached(
            str(day), gid, pkey, float(line), tuple(means.tolist()), tuple(cov.reshape(-1).tolist()),
            int(sim_count), int(seed), int(BATCH_SIZE)
        )
        key = (gid, pkey, float(line))
        sim_map[key] = result
        meta_map[key] = {**dist_meta, "lineup_ready": lineup_ready, "proj": proj}
        if progress is not None:
            try:
                progress.progress((i + 1) / max(total_units, 1), text=f"Simulated {i+1}/{total_units} unique player/line distributions")
            except Exception:
                pass

    rows = []
    for _, m in pairs.iterrows():
        gid = str(m.get("game_id") or "")
        pkey = str(m.get("player_key") or "")
        line = _num(m.get("line"), np.nan)
        if pd.isna(line):
            continue
        key = (gid, pkey, float(line))
        sim = sim_map.get(key)
        dmeta = meta_map.get(key)
        if sim is None or dmeta is None:
            continue
        proj = dmeta["proj"]
        nv_over, nv_under = step6._no_vig(m.get("over_odds"), m.get("under_odds"))
        edge = sim["p_over"] - nv_over if pd.notna(nv_over) else np.nan
        profit = step6._profit_per_dollar(m.get("over_odds"))
        ev100 = (sim["p_over_raw"] * profit - sim["p_under_raw"]) * 100.0 if pd.notna(profit) else np.nan
        fresh_label, fresh_score = step6._freshness(m.get("market_age"))
        context_q = float(np.clip(_num(proj.get("context_quality"), 0.5), 0.0, 1.0))
        data_q = float(np.clip(dmeta.get("data_quality", 0.48), 0.0, 1.0))
        role_label = str(proj.get("ROLE_LABEL") or "ACTIVE")
        lineup_ready = bool(dmeta.get("lineup_ready"))

        model_qualified = (
            pd.notna(nv_over)
            and pd.notna(edge)
            and sim["p_over"] >= 0.55
            and edge >= 0.030
            and _num(proj.get("PROJ_MIN"), 0.0) >= 10.0
            and fresh_label != "STALE"
            and context_q >= 0.60
            and role_label.upper() != "OUT"
            and sim["converged"]
        )
        final_ready = bool(model_qualified and lineup_ready)
        if fresh_label == "STALE" or role_label.upper() == "OUT":
            status = "AVOID"
        elif final_ready:
            status = "FINAL READY"
        elif model_qualified:
            status = "MONITOR LINEUP"
        else:
            status = "NO EDGE"

        rows.append({
            "player": str(proj.get("PLAYER_NAME") or m.get("player_name") or "Player"),
            "player_key": pkey,
            "game_id": gid,
            "team": str(proj.get("team_name") or ""),
            "opponent": str(proj.get("opponent") or ""),
            "book": str(m.get("book") or ""),
            "line": float(line),
            "raw_projection": _num(proj.get("RAW_PROJ_PRA"), np.nan),
            "projection": _num(proj.get("PROJ_PRA"), np.nan),
            "sim_mean": sim["mean_pra"],
            "sim_median": sim["median_pra"],
            "sim_mode": sim["mode_pra"],
            "p10": sim["p10"],
            "p90": sim["p90"],
            "model_over": sim["p_over"],
            "model_under": sim["p_under"],
            "push": sim["p_push"],
            "no_vig_over": nv_over,
            "edge": edge,
            "over_odds": m.get("over_odds"),
            "under_odds": m.get("under_odds"),
            "fair_over": step6._fair_american(sim["p_over"]),
            "ev100": ev100,
            "freshness": fresh_label,
            "fresh_score": fresh_score,
            "market_age": _num(m.get("market_age"), np.nan),
            "context_quality": context_q,
            "data_quality": data_q,
            "hist_games": int(dmeta.get("hist_games") or 0),
            "variance_source": str(dmeta.get("variance_source") or ""),
            "uncertainty_mult": _num(dmeta.get("uncertainty_mult"), 1.0),
            "lineup_ready": lineup_ready,
            "proj_min": _num(proj.get("PROJ_MIN"), np.nan),
            "role_label": role_label,
            "sims": sim["sims"],
            "batches": sim["batches"],
            "seed": sim["seed"],
            "mc_se": sim["mc_se"],
            "max_batch_diff": sim["max_batch_diff"],
            "converged": sim["converged"],
            "elapsed_s": sim["elapsed_s"],
            "model_qualified": bool(model_qualified),
            "final_ready": final_ready,
            "status": status,
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out, {"snapshot": snap, "pairs": len(pairs), **pmeta}
    out["mc_grade"] = 100.0 * (
        0.52 * out["model_over"]
        + 0.24 * (0.50 + out["edge"].fillna(0.0)).clip(0.0, 1.0)
        + 0.08 * out["data_quality"]
        + 0.08 * out["context_quality"]
        + 0.08 * out["fresh_score"]
    )
    out["_price"] = pd.to_numeric(out["over_odds"], errors="coerce").fillna(-100000)
    out = out.sort_values(["final_ready", "model_qualified", "mc_grade", "edge", "_price"], ascending=[False, False, False, False, False]).drop(columns=["_price"]).reset_index(drop=True)
    return out, {"snapshot": snap, "pairs": len(pairs), "lineups": lineups, **pmeta}


def run_standard(day, progress=None):
    return _market_rows(day, STANDARD_SIMS, progress=progress)


def run_final(day, standard_rows, progress=None):
    if standard_rows is None or standard_rows.empty:
        return pd.DataFrame(), {}
    # Final pass only for unique player/line candidates that cleared the model
    # gate or are very close to it. This is the user's 10M final/close-call rule.
    close = standard_rows[
        standard_rows["model_qualified"].fillna(False)
        | ((standard_rows["model_over"] >= 0.53) & (standard_rows["edge"].fillna(-1) >= 0.015))
    ].copy()
    if close.empty:
        return pd.DataFrame(), {"reason": "NO_FINALISTS"}

    # Reuse the normal market pipeline at 10M and then retain only close/finalist keys.
    all_final, meta = _market_rows(day, FINAL_SIMS, progress=progress)
    wanted = set(zip(close["game_id"].astype(str), close["player_key"].astype(str), close["line"].astype(float)))
    if all_final.empty:
        return all_final, meta
    mask = [
        (str(r.game_id), str(r.player_key), float(r.line)) in wanted
        for r in all_final.itertuples(index=False)
    ]
    return all_final.loc[mask].reset_index(drop=True), meta


def _pct(v):
    try:
        return f"{100*float(v):.1f}%"
    except Exception:
        return "—"


def _pp(v):
    try:
        return f"{100*float(v):+.1f} pp"
    except Exception:
        return "—"


def _fmt_odds(v):
    return step6._fmt_odds(v)


def _display_table(rows):
    if rows is None or rows.empty:
        return pd.DataFrame()
    d = rows.copy()
    d["Player"] = d["player"]
    d["Book"] = d["book"]
    d["Line"] = d["line"].map(lambda x: f"{x:g}")
    d["Adj PRA"] = d["projection"].map(lambda x: f"{x:.2f}")
    d["MC Mean"] = d["sim_mean"].map(lambda x: f"{x:.2f}")
    d["Median"] = d["sim_median"].map(lambda x: f"{x:g}")
    d["Range 10–90"] = d.apply(lambda r: f"{r['p10']:g}–{r['p90']:g}", axis=1)
    d["P(Over)"] = d["model_over"].map(_pct)
    d["Push"] = d["push"].map(_pct)
    d["No-vig O"] = d["no_vig_over"].map(_pct)
    d["Edge"] = d["edge"].map(_pp)
    d["Price"] = d["over_odds"].map(_fmt_odds)
    d["Fair"] = d["fair_over"].map(_fmt_odds)
    d["MC SE"] = d["mc_se"].map(lambda x: f"{100*x:.3f} pp")
    d["Batch Δ"] = d["max_batch_diff"].map(lambda x: f"{100*x:.2f} pp")
    d["Conv"] = d["converged"].map(lambda x: "✅" if bool(x) else "⚠️")
    d["Lineups"] = d["lineup_ready"].map(lambda x: "✅" if bool(x) else "PENDING")
    d["Status"] = d["status"]
    return d[["Player","Book","Line","Adj PRA","MC Mean","Median","Range 10–90","P(Over)","Push","No-vig O","Edge","Price","Fair","MC SE","Batch Δ","Conv","Lineups","Status"]]


def render_monte_carlo(day):
    st.markdown("### 🎲 Step 8 — Production WNBA PRA Monte Carlo")
    st.caption(
        "Actual correlated PTS/REB/AST simulation from the Step-7 matchup-adjusted means. "
        "Sportsbook lines grade the completed simulation only; they never move the projection. "
        "5M standard • 10M finalists/close calls • identical player/line markets across books reuse one simulation."
    )

    key = f"wnba_pra_v31_standard::{pd.to_datetime(day).strftime('%Y-%m-%d')}"
    final_key = f"wnba_pra_v31_final::{pd.to_datetime(day).strftime('%Y-%m-%d')}"

    if st.button("🚀 RUN 5,000,000 STANDARD SIMS", key=f"run_v31_std_{day}", use_container_width=True):
        bar = st.progress(0.0, text="Starting production Monte Carlo…")
        try:
            rows, meta = run_standard(day, progress=bar)
            st.session_state[key] = {"rows": rows, "meta": meta, "ran_at": pd.Timestamp.now()}
        finally:
            bar.empty()

    stored = st.session_state.get(key)
    if not stored:
        st.info("Step 8 is armed but has not claimed any simulations yet. Tap RUN 5,000,000 STANDARD SIMS to execute the production pass.")
        return

    rows = stored.get("rows")
    meta = stored.get("meta") or {}
    if rows is None or rows.empty:
        st.warning("No exact PRA markets were available to simulate. Nothing was fabricated.")
        return

    unique_distributions = rows[["game_id","player_key","line"]].drop_duplicates().shape[0]
    completed_sims = int(rows.groupby(["game_id","player_key","line"])["sims"].first().sum())
    converged = int(rows.groupby(["game_id","player_key","line"])["converged"].first().sum())
    model_qualified = int(rows["model_qualified"].sum())
    final_ready = int(rows["final_ready"].sum())
    cols = st.columns(5)
    cols[0].metric("Unique distributions", unique_distributions)
    cols[1].metric("Actual sims completed", f"{completed_sims:,}")
    cols[2].metric("Converged", f"{converged}/{unique_distributions}")
    cols[3].metric("Model-qualified", model_qualified)
    cols[4].metric("Final-ready", final_ready)

    if not all((meta.get("lineups") or {}).values()) if (meta.get("lineups") or {}) else True:
        st.warning("⚠️ Confirmed starting fives are still pending for at least one active game. Simulations widen uncertainty and any otherwise-qualified result stays MONITOR until explicit lineups publish.")

    best = rows.drop_duplicates(subset=["game_id","player_key","line"], keep="first")
    best = best.sort_values(["model_qualified","mc_grade"], ascending=[False,False])
    qualified = best[best["model_qualified"]].head(5)
    if qualified.empty:
        st.info("No PRA overs clear the 5M production probability + no-vig + freshness + convergence gates. No 10M final pass is required right now.")
    else:
        st.markdown("#### 🏆 5M Production Candidates")
        st.dataframe(_display_table(qualified), use_container_width=True, hide_index=True)
        if st.button("🏁 RUN 10,000,000 FINAL / CLOSE-CALL SIMS", key=f"run_v31_final_{day}", use_container_width=True):
            bar = st.progress(0.0, text="Starting 10M finalist simulation…")
            try:
                frows, fmeta = run_final(day, rows, progress=bar)
                st.session_state[final_key] = {"rows": frows, "meta": fmeta, "ran_at": pd.Timestamp.now()}
            finally:
                bar.empty()

    final_stored = st.session_state.get(final_key)
    if final_stored:
        frows = final_stored.get("rows")
        if frows is not None and not frows.empty:
            st.markdown("#### 🏁 10M Final / Close-Call Board")
            st.dataframe(_display_table(frows), use_container_width=True, hide_index=True)
            uniq = frows.drop_duplicates(subset=["game_id","player_key","line"], keep="first")
            st.caption(
                f"Executed {int(uniq['sims'].sum()):,} total finalist simulations across {len(uniq)} unique distributions. "
                "Each row reports its own deterministic seed, MC standard error and batch convergence in the diagnostics below."
            )

    with st.expander("📋 All 5M Monte Carlo model-vs-market matches", expanded=False):
        st.dataframe(_display_table(rows), use_container_width=True, hide_index=True)

    with st.expander("🧪 Monte Carlo diagnostics", expanded=False):
        diag = rows.drop_duplicates(subset=["game_id","player_key","line"], keep="first").copy()
        diag["Player"] = diag["player"]
        diag["Line"] = diag["line"]
        diag["Sims"] = diag["sims"].map(lambda x: f"{int(x):,}")
        diag["Batches"] = diag["batches"].astype(int)
        diag["Seed"] = diag["seed"].astype(int)
        diag["MC SE"] = diag["mc_se"].map(lambda x: f"{100*x:.4f} pp")
        diag["Max batch Δ"] = diag["max_batch_diff"].map(lambda x: f"{100*x:.3f} pp")
        diag["Converged"] = diag["converged"].map(lambda x: "YES" if bool(x) else "CHECK")
        diag["Variance"] = diag["variance_source"]
        diag["Hist GP"] = diag["hist_games"].astype(int)
        diag["Unc ×"] = diag["uncertainty_mult"].map(lambda x: f"{x:.3f}×")
        st.dataframe(diag[["Player","Line","Sims","Batches","Seed","MC SE","Max batch Δ","Converged","Variance","Hist GP","Unc ×"]], use_container_width=True, hide_index=True)


__all__ = [
    "MODEL_VERSION", "STANDARD_SIMS", "FINAL_SIMS", "run_standard", "run_final", "render_monte_carlo"
]
