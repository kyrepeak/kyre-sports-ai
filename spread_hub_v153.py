import math

import pandas as pd
import streamlit as st

from engine import actionable, metric_grid
import spread_hub_v152 as base
from spread_backtest import (
    grade_spread_games,
    load_spread_history,
    merge_uploaded_spread_history,
    save_spread_scan,
    spread_calibration_table,
    spread_history_download_bytes,
    spread_metrics,
    spread_rank_performance,
    top_spread_performance,
)


def _pct(value):
    try:
        if value is None or math.isnan(float(value)):
            return "N/A"
        return f"{float(value) * 100:.1f}%"
    except Exception:
        return "N/A"


def _num(value, digits=3):
    try:
        if value is None or math.isnan(float(value)):
            return "N/A"
        return f"{float(value):.{digits}f}"
    except Exception:
        return "N/A"


def _pregame_results(results):
    if not results:
        return False
    return all(actionable(r.get("status"), include_live=False) for r in results)


def _slate_date(games_df):
    if games_df is None or games_df.empty or "game_date" not in games_df.columns:
        return "NO_SLATE"
    values = games_df["game_date"].dropna().astype(str).unique().tolist()
    return values[0] if len(values) == 1 else "MIXED"


def _verified_game_pks(games_df):
    if games_df is None or games_df.empty or "game_pk" not in games_df.columns:
        return set()
    df = games_df
    if "verified" in df.columns:
        df = df[df["verified"].fillna(False).astype(bool)]
    return set(pd.to_numeric(df["game_pk"], errors="coerce").dropna().astype(int).tolist())


def _reset_stale_spread_state(games_df):
    """Never allow a scan from another date/game list to appear on this slate."""
    current_date = _slate_date(games_df)
    valid_pks = _verified_game_pks(games_df)
    previous_date = st.session_state.get("v153_verified_slate_date")
    stored = st.session_state.get("v152_spread_slate") or []

    stored_pks = set()
    for result in stored:
        try:
            stored_pks.add(int(result.get("game_pk")))
        except Exception:
            pass

    date_changed = previous_date is not None and previous_date != current_date
    game_mismatch = bool(stored_pks - valid_pks)

    if date_changed or game_mismatch:
        for key in (
            "v152_spread_slate",
            "v152_spread_scan_time",
            "v152_spread_errors",
            "v15_spread_result",
        ):
            st.session_state.pop(key, None)

    st.session_state["v153_verified_slate_date"] = current_date
    return current_date, valid_pks, date_changed or game_mismatch


def _render_scanner_with_history(games_df, section_header, status_info, team_logo, h):
    current_date, valid_pks, reset = _reset_stale_spread_state(games_df)

    if reset:
        st.info(
            f"🔄 Slate changed or a stale matchup was detected. Scanner results were cleared and rebound to the verified {current_date} MLB schedule."
        )

    if games_df is not None and not games_df.empty and "verified" in games_df.columns:
        verified_count = int(games_df["verified"].fillna(False).astype(bool).sum())
        st.caption(
            f"✅ Verified MLB slate: {verified_count} game(s) • {current_date} • scanner cards can only use game IDs on this date."
        )

    # Keep V15.2 projection math and cards intact, but only feed it the
    # verified schedule for the selected date.
    verified_df = games_df
    if games_df is not None and not games_df.empty and "verified" in games_df.columns:
        verified_df = games_df[games_df["verified"].fillna(False).astype(bool)].copy()

    base._render_scanner(verified_df, section_header, status_info, team_logo, h)

    results = st.session_state.get("v152_spread_slate") or []
    if not results:
        return

    # Final integrity guard in case a component ever writes an unexpected
    # game into session state.
    clean_results = []
    for result in results:
        try:
            if int(result.get("game_pk")) in valid_pks:
                clean_results.append(result)
        except Exception:
            continue

    if len(clean_results) != len(results):
        st.session_state["v152_spread_slate"] = clean_results
        results = clean_results
        st.warning("A stale/cross-date spread result was removed before display/backtest storage.")

    if not results:
        return

    if _pregame_results(results):
        added, total, scan_id = save_spread_scan(results, model_version="V15.3.1")
        if added:
            st.success(
                f"📈 V15.3.1 backtest saved {added} clean pregame spread projection(s). "
                f"History now contains {total} record(s)."
            )
    else:
        st.caption(
            "Live/final spread scans are not saved to the backtest. "
            "Only clean pregame scans are recorded."
        )


def _render_backtest(section_header):
    section_header(
        "V15.3.1 Spread Backtest",
        "Tracks clean pregame run-line projections, grades finished games, and tests whether the H2H layer actually improves calibration.",
    )

    st.markdown(
        '<div class="ks-note"><b>Backtest integrity:</b> only pregame scanner results from the verified selected MLB slate are saved. '
        'Live/final scans are excluded. Repeated scans do not create duplicate records for the same game/model version.</div>',
        unsafe_allow_html=True,
    )

    st.warning(
        "Free Streamlit storage can reset after redeploys/restarts. "
        "Download the spread-history CSV periodically and restore it here if needed."
    )

    if st.button(
        "🔄 GRADE FINISHED SPREAD GAMES",
        use_container_width=True,
        type="primary",
        key="grade_spread_history",
    ):
        with st.spinner("Pulling official MLB final scores and grading saved spread projections..."):
            summary = grade_spread_games()
        st.success(
            f"Graded {summary['graded']} • Push {summary['push']} • "
            f"Void {summary['void']} • Still pending {summary['still_pending']} • "
            f"Errors {summary['errors']}"
        )

    history = load_spread_history()
    if history.empty:
        st.info(
            "No spread prediction history yet. Run the Spread Scanner before games start; "
            "V15.3.1 will automatically save the clean pregame slate."
        )
    else:
        metrics = spread_metrics(history)
        perf = top_spread_performance(history)

        record = (
            f"{metrics['wins']}-{metrics['losses']}"
            + (f"-{metrics['pushes']}P" if metrics["pushes"] else "")
        )

        metric_grid(
            [
                ("Settled Picks", metrics["graded"]),
                ("ATS Record", record),
                ("Cover Rate", _pct(metrics["cover_rate"])),
                ("Avg Projected", _pct(metrics["avg_prediction"])),
                ("Final Brier", _num(metrics["brier_final"])),
                ("Core Brier", _num(metrics["brier_core"])),
                ("Calibration Gap", (
                    f"{metrics['calibration_gap'] * 100:+.1f} pts"
                    if pd.notna(metrics["calibration_gap"])
                    else "N/A"
                )),
                ("Log Loss", _num(metrics["log_loss"])),
            ]
        )

        delta = metrics.get("h2h_brier_delta")
        if pd.notna(delta):
            if delta > 0.002:
                verdict = (
                    f"✅ H2H/history is helping so far: final Brier is lower than the core model "
                    f"by {delta:.3f}."
                )
            elif delta < -0.002:
                verdict = (
                    f"⚠️ H2H/history is hurting so far: final Brier is higher than the core model "
                    f"by {abs(delta):.3f}."
                )
            else:
                verdict = (
                    f"➖ H2H/history is roughly neutral so far: Brier change {delta:+.3f}."
                )
            st.markdown(
                f'<div class="ks-note"><b>Does H2H help?</b> {verdict}</div>',
                unsafe_allow_html=True,
            )

        if metrics["graded"] < 50:
            st.caption(
                "Small-sample warning: do not tune the history weight aggressively yet. "
                "A few dozen MLB games can swing ATS percentages a lot."
            )

        c1, c2 = st.columns(2)
        with c1:
            st.metric(
                "Top-5 Spread Cover Rate",
                _pct(perf["top5_rate"]),
                help=f"{perf['top5']} settled Top-5 projections",
            )
        with c2:
            st.metric(
                "#1 Spread Cover Rate",
                _pct(perf["number1_rate"]),
                help=f"{perf['number1']} settled #1 projections",
            )

        cal = spread_calibration_table(history)
        if not cal.empty:
            st.subheader("Probability Calibration")
            st.dataframe(cal, use_container_width=True, hide_index=True)

        ranks = spread_rank_performance(history)
        if not ranks.empty:
            st.subheader("Performance by Scanner Rank")
            st.dataframe(ranks, use_container_width=True, hide_index=True)

        with st.expander("📋 Full Spread Prediction History"):
            show = history.sort_values(
                ["created_at_et", "rank"],
                ascending=[False, True],
            ).copy()
            st.dataframe(show, use_container_width=True, hide_index=True)

        st.download_button(
            "⬇️ DOWNLOAD SPREAD HISTORY CSV",
            data=spread_history_download_bytes(),
            file_name="kyre_spread_history.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.divider()
    st.subheader("♻️ Restore Spread History Backup")
    uploaded = st.file_uploader(
        "Upload a previous V15.3/V15.3.1 spread-history CSV",
        type=["csv"],
        key="spread_history_upload",
    )
    if uploaded is not None:
        if st.button(
            "MERGE SPREAD HISTORY BACKUP",
            use_container_width=True,
            key="merge_spread_history",
        ):
            added, total = merge_uploaded_spread_history(uploaded)
            st.success(f"Merged {added} new record(s). Spread history now contains {total} record(s).")


def render_spread_hub(games_df, section_header, status_info, team_logo, h):
    scanner_tab, analyzer_tab, backtest_tab = st.tabs(
        [
            "🏆 Spread Scanner",
            "🔎 Game Analyzer",
            "📈 Backtest",
        ]
    )

    with scanner_tab:
        _render_scanner_with_history(
            games_df,
            section_header,
            status_info,
            team_logo,
            h,
        )

    with analyzer_tab:
        st.markdown(
            '<div class="ks-note"><b>DATA confidence</b> describes completeness + convergence, '
            'not whether a spread itself is guaranteed.</div>',
            unsafe_allow_html=True,
        )
        verified_df = games_df
        if games_df is not None and not games_df.empty and "verified" in games_df.columns:
            verified_df = games_df[games_df["verified"].fillna(False).astype(bool)].copy()
        base.render_spread_module(verified_df, section_header, status_info, team_logo, h)
        base._render_history_overlay(verified_df, section_header)

    with backtest_tab:
        _render_backtest(section_header)
