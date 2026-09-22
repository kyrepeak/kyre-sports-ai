"""WNBA PRA V3.6 — Step 7 matchup/pace calibration repair.

This is a PRA-only runtime patch over the proven V3.0 Step-7 engine. It keeps
Step 1-6 player/minutes/usage/variance work, SportsGameOdds grading, injury
integrity, lineup gates and 5M/10M Monte Carlo counts unchanged.

V3.6 fixes two calibration weaknesses in the original matchup factors:
1) pace is now relative to the PLAYER TEAM'S recent pace, not the other teams
   that happen to be on that day's slate;
2) scoring efficiency blends the team's recent ORTG with the opponent's recent
   DRTG (L10 PF/PA fallback), then shrinks the adjustment toward neutral when
   advanced context coverage is thin.

PTS/REB/AST remain separate. Rebounds no longer inherit a positive opponent-
defense multiplier merely because an opponent allows efficient scoring; without
an explicit missed-shot/rebound environment in PRA Step 7, rebounds are adjusted
mainly by possession volume. H2H stays descriptive only. Sportsbook price never
moves a projection.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_pra_matchup_v30 as base
import wnba_pra_market_v29 as step6

MODEL_VERSION = "PRA V3.6 STEP 7 • TEAM-RELATIVE PACE + OFF/DEF EFFICIENCY BLEND"


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _mean_valid(values):
    vals = [float(v) for v in values if pd.notna(v) and np.isfinite(float(v))]
    return float(np.mean(vals)) if vals else np.nan


def _shrink_weight(context_quality: float) -> float:
    """Map existing Step-7 context quality to conservative multiplier strength."""
    q = float(np.clip(_num(context_quality, 0.5), 0.0, 1.0))
    # q=0.50 => ~9% of the raw effect; q=0.78 => 60%; q=1.00 => 100%.
    return float(np.clip((q - 0.45) / 0.55, 0.0, 1.0))


def matchup_factors_v36(team_ctx, opp_ctx, _legacy_baseline=None):
    """Team-relative pace + offense/opponent-defense blend with quality shrinkage."""
    q = float(base._context_quality(team_ctx, opp_ctx))
    shrink = _shrink_weight(q)

    team_pace = _num((team_ctx or {}).get("PACE_L10"), np.nan)
    opp_pace = _num((opp_ctx or {}).get("PACE_L10"), np.nan)
    expected_pace = _mean_valid([team_pace, opp_pace])

    # A player's Step-5 baseline was produced inside the player's own team
    # environment. Therefore matchup pace should move relative to THAT team's
    # normal recent pace, not a slate-average pace that changes with today's card.
    if pd.notna(expected_pace) and pd.notna(team_pace) and team_pace > 0:
        raw_pace = float(np.clip(expected_pace / team_pace, 0.955, 1.045))
        pace_factor = float(1.0 + shrink * (raw_pace - 1.0))
        pace_source = "team-relative L10 pace blend"
    else:
        pace_factor = 1.0
        pace_source = "neutral"

    team_ortg = _num((team_ctx or {}).get("ORTG_L10"), np.nan)
    opp_drtg = _num((opp_ctx or {}).get("DRTG_L10"), np.nan)
    team_pf = _num((team_ctx or {}).get("L10_PF"), np.nan)
    opp_pa = _num((opp_ctx or {}).get("L10_PA"), np.nan)

    # Blend the offense the player normally lives in with the defense it faces.
    # This is team-relative: a strong offense facing a merely average defense is
    # not boosted just because another game on the slate happens to be defensive.
    if pd.notna(team_ortg) and pd.notna(opp_drtg) and team_ortg > 0 and opp_drtg > 0:
        expected_eff = _mean_valid([team_ortg, opp_drtg])
        raw_eff = float(np.clip(expected_eff / team_ortg, 0.945, 1.055))
        efficiency_factor = float(1.0 + shrink * (raw_eff - 1.0))
        defense_source = "team L10 ORTG + opponent L10 DRTG"
    elif pd.notna(team_pf) and pd.notna(opp_pa) and team_pf > 0 and opp_pa > 0:
        expected_eff = _mean_valid([team_pf, opp_pa])
        raw_eff = float(np.clip(expected_eff / team_pf, 0.955, 1.045))
        efficiency_factor = float(1.0 + shrink * (raw_eff - 1.0))
        defense_source = "team L10 PF + opponent L10 PA fallback"
    else:
        efficiency_factor = 1.0
        defense_source = "neutral"

    # P/R/A stay separate. Efficiency meaningfully affects scoring, modestly
    # affects assists, and is intentionally excluded from rebounds here because
    # PRA Step 7 does not yet own an explicit missed-shot/rebound-opportunity feed.
    pts_factor = float(np.clip((pace_factor ** 0.90) * (efficiency_factor ** 0.85), 0.93, 1.07))
    reb_factor = float(np.clip(pace_factor ** 0.72, 0.96, 1.04))
    ast_factor = float(np.clip((pace_factor ** 0.78) * (efficiency_factor ** 0.45), 0.95, 1.05))

    return {
        "expected_pace": expected_pace,
        "pace_factor": pace_factor,
        # Compatibility name retained because downstream grading/fingerprints
        # already consume defense_factor. In V3.6 it means the team-relative
        # offense-vs-opponent-defense efficiency matchup factor.
        "defense_factor": efficiency_factor,
        "pts_factor": pts_factor,
        "reb_factor": reb_factor,
        "ast_factor": ast_factor,
        "pace_source": pace_source,
        "defense_source": defense_source,
        "opp_drtg_l10": opp_drtg,
        "opp_pa_l10": opp_pa,
        "context_quality": q,
        "context_shrink": shrink,
    }


def render_matchup_grade_v36(day):
    st.markdown("### 🧭 Step 7 — WNBA Matchup + Pace Adjustment")
    st.caption(
        "Step-5 minutes/role → team-relative recent pace + team offense vs opponent defense → exact PRA line. "
        "P/R/A are adjusted separately; low-sample context is shrunk toward neutral; H2H remains descriptive only. "
        "Sportsbook price never changes the projection."
    )

    with st.spinner("🧭 Applying calibrated WNBA matchup context to PRA projections…"):
        graded, meta = base.grade_matchup_pra(day)

    cdiag = meta.get("context_diag") or {}
    adiag = meta.get("availability_diag") or {}

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Context teams", f"{cdiag.get('advanced_teams',0)}/{cdiag.get('teams',0)}")
    c2.metric("Advanced samples", int(cdiag.get("advanced_games", 0) or 0))
    c3.metric("Lineups confirmed", f"{adiag.get('lineups_confirmed',0)}/{adiag.get('teams',0)}")
    c4.metric("Exact PRA matches", 0 if graded is None else len(graded))

    st.caption(
        "V3.6 calibration • pace is measured against each player's own team environment, not a slate-average baseline • "
        "scoring efficiency blends team L10 ORTG with opponent L10 DRTG (PF/PA fallback) • context quality shrinks weak samples toward 1.000× • "
        "REB uses possession-volume adjustment only until a verified missed-shot/rebound-opportunity layer exists."
    )

    if int(adiag.get("lineups_confirmed", 0) or 0) < int(adiag.get("teams", 0) or 0):
        st.warning(
            "⚠️ Confirmed starting fives are still pending for part/all of this slate. "
            "Step 7 does not infer starters. Current rankings remain pre-lineup and will be rechecked when explicit starters publish."
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
                f"Model {base._pct(r['model_over'])} • No-vig {base._pct(r['no_vig_over'])} • "
                f"Edge {100.0*r['edge']:+.1f} pp • Fair {step6._fmt_odds(r['fair_over'])} • Status {r['status']}"
            )
    else:
        st.info(
            "No PRA overs clear the Step-7 matchup + probability + no-vig + freshness gates. "
            "That is a valid result; no pick is forced."
        )

    with st.expander("🧾 All Step-7 PRA model-vs-market matches", expanded=True):
        show = graded.copy()
        show["Model Over"] = show["model_over"].map(base._pct)
        show["No-vig Over"] = show["no_vig_over"].map(base._pct)
        show["Edge"] = show["edge"].map(lambda x: "—" if pd.isna(x) else f"{100.0*x:+.1f} pp")
        show["Raw PRA"] = show["raw_projection"].map(lambda x: f"{x:.2f}")
        show["Adj PRA"] = show["projection"].map(lambda x: f"{x:.2f}")
        show["Matchup Δ"] = show["matchup_delta"].map(lambda x: f"{x:+.2f}")
        show["Pace vs team"] = show["pace_factor"].map(base._factor)
        show["Off/Def Eff"] = show["defense_factor"].map(base._factor)
        show["Price"] = show["over_odds"].map(step6._fmt_odds)
        show["Fair"] = show["fair_over"].map(step6._fmt_odds)
        show["Fresh"] = show["market_age"].map(step6._age)
        st.dataframe(
            show[["player", "book", "line", "Raw PRA", "Adj PRA", "Matchup Δ", "Pace vs team", "Off/Def Eff", "Model Over", "No-vig Over", "Edge", "Price", "Fair", "Fresh", "status"]].rename(columns={"player":"Player","book":"Book","line":"Line","status":"Status"}),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("Step 7 V3.6 adjustment rules", expanded=False):
        st.write({
            "pace": "Average of team + opponent L10 pace, measured relative to the player's own team L10 pace; capped and quality-shrunk.",
            "offense_vs_defense": "Blend team L10 ORTG with opponent L10 DRTG relative to team ORTG; L10 PF/PA fallback; capped and quality-shrunk.",
            "points": "Pace + efficiency sensitive.",
            "rebounds": "Pace/possession sensitive only in this PRA layer; no unsupported defense-sign shortcut.",
            "assists": "Pace sensitive with modest efficiency sensitivity.",
            "context_shrink": "Thin advanced samples are pulled toward neutral rather than receiving a full-strength matchup multiplier.",
            "H2H": "Display-only. No projection multiplier.",
            "sportsbook_price_in_projection": False,
            "starters_inferred": False,
            "5M_10M_counts_changed": False,
            "rebounds_module_touched": False,
            "mlb_files_touched": False,
        })


def install():
    if getattr(base, "_v36_matchup_calibration_installed", False):
        return
    base._matchup_factors = matchup_factors_v36
    base.render_matchup_grade = render_matchup_grade_v36
    base._v36_matchup_calibration_installed = True


__all__ = ["MODEL_VERSION", "install", "matchup_factors_v36", "render_matchup_grade_v36"]
