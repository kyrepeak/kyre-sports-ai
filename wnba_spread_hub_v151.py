"""WNBA Spread V1.5.1 — Step-6 UI integrity repair.

Preserves V1.5 probability math exactly and fixes only the probability-audit display
contract: V1.5 renamed book/state only inside the first dataframe expression, then
later selected non-existent `Book` / `State` columns from the unrenamed audit frame.
That would raise a KeyError as soon as Step 6 had real rows. V1.5.1 materializes
those display columns before the audit table is selected.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_spread_hub_v15 as base

MODEL_VERSION = "WNBA SPREAD V1.5.1 • STEP-6 UI INTEGRITY"


def _render_step6(day_str, pregame, projected, ready_lines, model_ready):
    st.markdown("### 📈 Step 6 — Cover Probability + Fair Spread")
    st.caption(
        "Analytical pre-Monte-Carlo layer • Step-5 projected margin stays fixed. Date-cut empirical team/league margin variance "
        "sets uncertainty; the verified Step-4 spread is only the cover threshold. Integer lines receive explicit push probability."
    )

    if pregame is None or pregame.empty:
        st.info("ℹ️ STEP 6 NOT APPLICABLE • no clock-safe pregame games remain.")
        return pd.DataFrame(), {"state":"N/A", "games":0, "covered_games":0, "rows":0, "model_ready":False}
    if not model_ready:
        st.warning("🔒 STEP 6 LOCKED • every pregame game must have a trustworthy independent Step-5 margin first.")
        return pd.DataFrame(), {"state":"LOCKED", "games":int(len(pregame)), "covered_games":0, "rows":0, "model_ready":False}
    if ready_lines is None or ready_lines.empty:
        st.warning("🔒 STEP 6 LOCKED • no current exact Step-4 sportsbook spread pairs are available for comparison.")
        return pd.DataFrame(), {"state":"LOCKED", "games":int(len(pregame)), "covered_games":0, "rows":0, "model_ready":False}

    with st.spinner("📈 Converting independent margins into analytical cover probabilities…"):
        board, meta = base.probability.probability_board(day_str, pregame, projected, ready_lines)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Game coverage", f"{int(meta.get('covered_games',0))}/{int(meta.get('games',0))}")
    c2.metric("Probability rows", int(meta.get("rows",0)))
    c3.metric("READY", int(meta.get("ready",0)))
    c4.metric("MONITOR", int(meta.get("monitor",0)))

    prob_ready = bool(meta.get("model_ready", False))
    if prob_ready:
        st.success("✅ STEP 6 PASSED • every pregame game has a cover distribution, fair spread and fair odds without changing the Step-5 projected margin.")
        if int(meta.get("monitor", 0)):
            st.info(f"🟦 {int(meta.get('monitor',0))} book-row probability result(s) are MONITOR because of short-sample or upstream uncertainty. Step 7 must retain those flags.")
    else:
        st.warning("⚠️ STEP 6 CHECK • at least one pregame game lacks a trustworthy empirical margin distribution. 5M remains locked.")

    if board is not None and not board.empty:
        show = board.copy()
        show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
        show["Book"] = show["book"].astype(str)
        show["State"] = show["state"].astype(str)
        show["Market"] = show.apply(
            lambda r: f"{r.get('away_team')} {base._fmt_line(r.get('away_spread'))} / {r.get('home_team')} {base._fmt_line(r.get('home_spread'))}", axis=1
        )
        show["Fair spread"] = show.apply(
            lambda r: f"{r.get('away_team')} {base._fmt_line(r.get('fair_away_spread'))} / {r.get('home_team')} {base._fmt_line(r.get('fair_home_spread'))}", axis=1
        )
        show["Away cover"] = show["away_cover"].map(base._fmt_pct)
        show["Home cover"] = show["home_cover"].map(base._fmt_pct)
        show["Push"] = show["push"].map(base._fmt_pct)
        show["Margin σ"] = show["sigma"].map(lambda x: base._fmt(x,1))
        show["80% margin range"] = show.apply(
            lambda r: f"{base._fmt(r.get('margin_low80'),1)} to {base._fmt(r.get('margin_high80'),1)} home margin", axis=1
        )
        st.dataframe(
            show[["Game", "first_tip_et", "Book", "Market", "Fair spread", "Away cover", "Home cover", "Push", "Margin σ", "State"]].rename(
                columns={"first_tip_et":"Tip ET"}
            ),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("🧮 Step 6 probability audit — fair odds + no-vig comparison", expanded=False):
            audit = show.copy()
            audit["Away fair odds"] = audit["away_fair_odds"].map(base._fmt_odds)
            audit["Home fair odds"] = audit["home_fair_odds"].map(base._fmt_odds)
            audit["Away no-vig mkt"] = audit["away_market_novig"].map(base._fmt_pct)
            audit["Home no-vig mkt"] = audit["home_market_novig"].map(base._fmt_pct)
            audit["Away model no-push"] = audit["away_no_push"].map(base._fmt_pct)
            audit["Home model no-push"] = audit["home_no_push"].map(base._fmt_pct)
            audit["Away edge"] = audit["away_edge_pp"].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1f} pp")
            audit["Home edge"] = audit["home_edge_pp"].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1f} pp")
            audit["Margin sample"] = audit.apply(
                lambda r: f"away {int(r.get('away_margin_games',0) or 0)} / home {int(r.get('home_margin_games',0) or 0)} / league {int(r.get('league_margin_games',0) or 0)}", axis=1
            )
            st.dataframe(
                audit[[
                    "Game", "Book", "Away fair odds", "Home fair odds",
                    "Away model no-push", "Home model no-push", "Away no-vig mkt", "Home no-vig mkt",
                    "Away edge", "Home edge", "Margin sample", "80% margin range", "State",
                ]],
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "Fair odds use model cover probability normalized for pushes. Market no-vig probability uses only the same-book two-sided prices. "
                "These comparisons do not feed back into the projected margin. Step 6 is analytical; 5M Monte Carlo remains OFF."
            )

        st.session_state["wnba_spread_v15_probability_board"] = board.copy()
        st.session_state["wnba_spread_v15_probability_date"] = str(day_str)

    meta = dict(meta)
    meta["model_ready"] = prob_ready
    return board, meta


# V1.5's renderer resolves this helper from its own module globals at call time.
base._render_step6 = _render_step6


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return base.render_wnba_spread_hub(section_header, status_info, team_logo, h)


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub", "_render_step6"]
