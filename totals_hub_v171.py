from datetime import datetime

import pandas as pd
import streamlit as st

import totals_hub_v17 as base
from engine import ET
from spread_engine import _stable_seed

MODEL_VERSION = "V17.1"


def _conditional_prob(side_prob, push_prob):
    settled = max(1.0 - float(push_prob or 0.0), 1e-9)
    return float(side_prob or 0.0) / settled


def _reset_v171_state(games_df):
    current_date = base._slate_date(games_df)
    valid = base._valid_pks(games_df)
    previous = st.session_state.get("v171_ou_slate_date")
    stored = st.session_state.get("v171_ou_results") or []

    stored_pks = set()
    for result in stored:
        try:
            stored_pks.add(int(result.get("game_pk")))
        except Exception:
            pass

    changed = previous is not None and previous != current_date
    mismatch = bool(stored_pks - valid)
    if changed or mismatch:
        for key in (
            "v171_ou_results",
            "v171_ou_scan_time",
            "v171_ou_errors",
            "v171_market_lines",
        ):
            st.session_state.pop(key, None)

    st.session_state["v171_ou_slate_date"] = current_date
    return current_date, valid, changed or mismatch


def _default_market_lines(rows):
    previous = st.session_state.get("v171_market_lines") or {}
    data = []
    for row in rows:
        pk = int(row["game_pk"])
        data.append(
            {
                "game_pk": pk,
                "Game": f'{row["away_team"]} @ {row["home_team"]}',
                "Total Line": float(previous.get(pk, 8.5)),
                "Time": row.get("first_pitch_et", "TBD"),
                "Status": row.get("status", "Unknown"),
            }
        )
    return pd.DataFrame(data)


def _scan_ou_game(row, total_line, simulations):
    result = base._scan_game(row)
    line = float(total_line)
    seed = _stable_seed(int(row["game_pk"]), 1710 + int(round(line * 10)))
    sim = base.simulate_total(
        result["away_mean"],
        result["home_mean"],
        line,
        int(simulations),
        seed,
    )

    over_cond = _conditional_prob(sim["p_over"], sim["p_push"])
    under_cond = _conditional_prob(sim["p_under"], sim["p_push"])
    if over_cond >= under_cond:
        lean = "OVER"
        lean_prob = over_cond
        fair = sim["fair_over"]
    else:
        lean = "UNDER"
        lean_prob = under_cond
        fair = sim["fair_under"]

    result.update(
        {
            "total_line": line,
            "simulation": sim,
            "lean": lean,
            "lean_prob": lean_prob,
            "fair_lean": fair,
            "model_edge_runs": float(result["projected_total"] - line),
            "confidence": base._data_confidence(result["model"], sim),
        }
    )
    return result


def _render_ou_cards(results, status_info, team_logo, h):
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for rank, result in enumerate(results[:5], 1):
        sim = result["simulation"]
        status_label, status_css = status_info(result.get("status"))
        badge = base._badge_class(result.get("confidence"))
        first = " ks-first" if rank == 1 else ""
        logos = f'{team_logo(result.get("away_team_id"))}{team_logo(result.get("home_team_id"))}'
        h2h = result.get("h2h") or {}
        avg10 = h2h.get("avg_total_l10")
        avg5 = h2h.get("avg_total_l5")
        avg10_text = f"{avg10:.1f}" if avg10 is not None else "N/A"
        avg5_text = f"{avg5:.1f}" if avg5 is not None else "N/A"
        score = f'{result["away_mean"]:.1f} — {result["home_mean"]:.1f}'

        card = (
            f'<div class="ks-pick-card{first}">'
            f'<div class="ks-rank">{medals.get(rank, "•")} #{rank}</div>'
            '<div class="ks-card-main"><div class="ks-player-row">'
            f'{logos}<div class="ks-player-copy">'
            f'<div class="ks-player">{h(result["lean"])} {result["total_line"]:g} • {h(result["away_team"])} @ {h(result["home_team"])}</div>'
            f'<div class="ks-matchup">Projected total {result["projected_total"]:.2f} • Projected score {h(score)}</div>'
            '</div></div><div class="ks-meta-line">'
            f'<span class="ks-status {status_css}">{h(status_label)}</span>'
            f'<span class="ks-mini">🕒 {h(result["first_pitch"])} ET</span>'
            f'<span class="ks-mini">H2H avg L10 {h(avg10_text)}</span>'
            f'<span class="ks-mini">H2H avg L5 {h(avg5_text)}</span>'
            '</div><details class="ks-card-details"><summary>＋ O/U details</summary>'
            '<div class="ks-detail-body">'
            f'Over <b>{sim["p_over"] * 100:.1f}%</b> • Under <b>{sim["p_under"] * 100:.1f}%</b> • Push <b>{sim["p_push"] * 100:.1f}%</b><br>'
            f'Model total vs line <b>{result["model_edge_runs"]:+.2f} runs</b> • Core total <b>{result["core_total"]:.2f}</b> • History adj <b>{result["history_adjustment"]:+.2f}</b><br>'
            f'Median <b>{sim["median_total"]}</b> • Mode <b>{sim["mode_total"]}</b> • 80% range <b>{sim["p10"]}–{sim["p90"]}</b> • Data <b>{result["data_score"]}/9</b>'
            '</div></details></div>'
            '<div class="ks-right">'
            f'<div class="ks-prob">{result["lean_prob"] * 100:.1f}%</div>'
            f'<div class="ks-prob-label">{h(result["lean"])} probability</div>'
            '<div class="ks-card-meta">'
            f'<span class="ks-badge {badge}">DATA {h(result["confidence"])}</span>'
            f'<span class="ks-mini">Fair {h(result["fair_lean"])}</span>'
            '</div></div></div>'
        )
        st.markdown(card, unsafe_allow_html=True)


def _render_probability_scanner(games_df, section_header, status_info, team_logo, h):
    current_date, valid, reset = _reset_v171_state(games_df)
    if reset:
        st.info(f"🔄 O/U slate changed. Old rankings were cleared and rebound to the verified {current_date} schedule.")

    verified = base._verified_df(games_df)
    if not verified.empty:
        st.caption(f"✅ Verified MLB slate: {len(verified)} game(s) • {current_date} • V17.1 can only rank verified game IDs on this date.")

    section_header(
        "MLB O/U Probability Scanner — V17.1",
        "Enter the current sportsbook total for each game, then rank the strongest Over or Under by model probability.",
    )
    st.markdown(
        '<div class="ks-note"><b>V17.1 market rule:</b> sportsbook total lines are settlement inputs only. '
        'They do not alter the projected score. Edit the Total Line column to match the book you are checking, then run the scanner.</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1.4])
    with c1:
        include_live = st.checkbox("⚠️ Include live games", value=False, key="v171_ou_include_live")
    with c2:
        depth = st.selectbox(
            "Slate simulation depth",
            ["Fast — 50K/game", "Standard — 150K/game", "Deep — 300K/game"],
            index=1,
            key="v171_ou_depth",
        )
    if include_live:
        st.warning("Live mode is only for testing. V17.1 still uses the pregame model and ignores the current score, inning, outs and in-game bullpen usage.")

    rows = base._available_rows(verified, include_live=include_live)
    if not rows:
        st.info("No actionable verified MLB games are available for this date.")
        return

    st.subheader("Sportsbook Total Lines")
    st.caption("Defaults are 8.5 only as placeholders — change them to the actual totals you want graded.")
    line_df = _default_market_lines(rows)
    edited = st.data_editor(
        line_df,
        use_container_width=True,
        hide_index=True,
        disabled=["game_pk", "Game", "Time", "Status"],
        column_config={
            "game_pk": None,
            "Total Line": st.column_config.NumberColumn(
                "Total Line",
                min_value=4.0,
                max_value=20.0,
                step=0.5,
                format="%.1f",
                required=True,
            ),
        },
        key=f"v171_line_editor_{current_date}",
    )

    market_lines = {
        int(r["game_pk"]): float(r["Total Line"])
        for _, r in edited.iterrows()
        if pd.notna(r.get("game_pk")) and pd.notna(r.get("Total Line"))
    }
    st.session_state["v171_market_lines"] = market_lines

    sim_n = {
        "Fast — 50K/game": 50_000,
        "Standard — 150K/game": 150_000,
        "Deep — 300K/game": 300_000,
    }[depth]

    if st.button("🔥 SCAN V17.1 OVER / UNDERS", use_container_width=True, type="primary", key="v171_ou_scan"):
        results = []
        errors = 0
        bar = st.progress(0, text="Running V17.1 O/U probabilities...")
        for idx, row in enumerate(rows, 1):
            try:
                pk = int(row["game_pk"])
                line = market_lines[pk]
                result = _scan_ou_game(row, line, sim_n)
                if pk in valid:
                    results.append(result)
            except Exception:
                errors += 1
            bar.progress(idx / len(rows), text=f"Simulating game {idx}/{len(rows)}")
        bar.empty()
        results.sort(key=lambda x: x["lean_prob"], reverse=True)
        st.session_state["v171_ou_results"] = results
        st.session_state["v171_ou_scan_time"] = datetime.now(ET).strftime("%I:%M:%S %p ET").lstrip("0")
        st.session_state["v171_ou_errors"] = errors

    results = st.session_state.get("v171_ou_results") or []
    results = [r for r in results if int(r.get("game_pk", -1)) in valid]
    st.session_state["v171_ou_results"] = results
    if not results:
        return

    section_header(
        "Selected Slate’s Strongest O/U Projections",
        "Ranked by V17.1 model probability after applying your entered sportsbook totals.",
    )
    scan_time = st.session_state.get("v171_ou_scan_time")
    if scan_time:
        st.markdown(f'<div class="ks-updated">↻ Last V17.1 scan {h(scan_time)}</div>', unsafe_allow_html=True)
    errors = int(st.session_state.get("v171_ou_errors", 0) or 0)
    if errors:
        st.caption(f"{errors} game(s) could not be fully modeled and were skipped.")

    _render_ou_cards(results, status_info, team_logo, h)

    top = results[0]
    st.markdown(
        f'<div class="ks-note"><b>Current O/U #1:</b> {h(top["lean"])} {top["total_line"]:g} • '
        f'{h(top["away_team"])} @ {h(top["home_team"])} • <b>{top["lean_prob"] * 100:.1f}%</b> • '
        f'Projected total {top["projected_total"]:.2f} • Fair {h(top["fair_lean"])}.</div>',
        unsafe_allow_html=True,
    )

    with st.expander("📋 Full O/U rankings"):
        table = []
        for rank, result in enumerate(results, 1):
            sim = result["simulation"]
            table.append(
                {
                    "#": rank,
                    "Game": f'{result["away_team"]} @ {result["home_team"]}',
                    "Line": result["total_line"],
                    "Lean": result["lean"],
                    "Lean %": f'{result["lean_prob"] * 100:.1f}%',
                    "Over %": f'{sim["p_over"] * 100:.1f}%',
                    "Under %": f'{sim["p_under"] * 100:.1f}%',
                    "Push %": f'{sim["p_push"] * 100:.1f}%',
                    "Projected Total": f'{result["projected_total"]:.2f}',
                    "Model-Line": f'{result["model_edge_runs"]:+.2f}',
                    "Fair": result["fair_lean"],
                    "Data": result["confidence"],
                    "Time": result["first_pitch"],
                }
            )
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)


def render_totals_hub(games_df, section_header, status_info, team_logo, h):
    ou_tab, environment_tab, analyzer_tab = st.tabs(
        ["🏆 O/U Rankings", "🔥 Scoring Environments", "🔎 O/U Analyzer"]
    )
    with ou_tab:
        _render_probability_scanner(games_df, section_header, status_info, team_logo, h)
    with environment_tab:
        base._render_scanner(games_df, section_header, status_info, team_logo, h)
    with analyzer_tab:
        base._render_analyzer(games_df, section_header, status_info, team_logo, h)
