from datetime import datetime

import pandas as pd
import streamlit as st

from engine import ET, actionable, odds
from spread_engine import build_game_model, render_spread_module, simulate_run_line, _stable_seed


def _data_confidence(model, sim):
    score = int(model.get("data_score", 0) or 0)
    if score >= 8 and sim.get("converged"):
        return "HIGH"
    if score >= 6 and sim.get("converged"):
        return "MEDIUM-HIGH"
    if score >= 5:
        return "MEDIUM"
    return "LOW"


def _badge_class(confidence):
    text = str(confidence or "").upper()
    if text == "HIGH":
        return "ks-high"
    if "MEDIUM" in text:
        return "ks-medium"
    return "ks-low"


def _actionable_rows(games_df, include_live=False):
    rows = []
    if games_df is None or games_df.empty:
        return rows
    for _, row in games_df.iterrows():
        if actionable(row.get("status"), include_live=include_live):
            rows.append(row)
    return rows


def _scan_game(row, simulations):
    game_pk = int(row["game_pk"])
    away_name = row["away_team"]
    home_name = row["home_team"]

    model = build_game_model(
        game_pk,
        int(row["away_team_id"]),
        int(row["home_team_id"]),
        row.get("away_pitcher_id"),
        row.get("home_pitcher_id"),
        row.get("venue_name", "Unknown"),
    )

    away_mean = float(model["away_model"]["expected_runs"])
    home_mean = float(model["home_model"]["expected_runs"])

    # V15 scanner uses one standard synthetic run-line pair per game:
    # model favorite -1.5 versus model underdog +1.5. This does NOT assume the
    # sportsbook favorite is identical to the model favorite.
    favorite_side = "home" if home_mean >= away_mean else "away"
    favorite_name = home_name if favorite_side == "home" else away_name
    underdog_side = "away" if favorite_side == "home" else "home"
    underdog_name = away_name if favorite_side == "home" else home_name

    seed = _stable_seed(game_pk, 1515)
    favorite_sim = simulate_run_line(
        away_mean,
        home_mean,
        int(simulations),
        seed,
        favorite_side,
        -1.5,
    )

    favorite_cover = float(favorite_sim["p_cover"])
    dog_cover = float(favorite_sim["p_opponent_cover"])

    if favorite_cover >= dog_cover:
        selected_side = favorite_side
        selected_team = favorite_name
        opponent = underdog_name
        line = -1.5
        cover = favorite_cover
        win_prob = float(favorite_sim["p_win"])
    else:
        selected_side = underdog_side
        selected_team = underdog_name
        opponent = favorite_name
        line = 1.5
        cover = dog_cover
        win_prob = 1.0 - float(favorite_sim["p_win"])

    selected_score = home_mean if selected_side == "home" else away_mean
    opponent_score = away_mean if selected_side == "home" else home_mean
    projected_margin = selected_score - opponent_score
    team_id = row["home_team_id"] if selected_side == "home" else row["away_team_id"]

    confidence = _data_confidence(model, favorite_sim)

    return {
        "game_pk": game_pk,
        "team": selected_team,
        "team_id": int(team_id),
        "opponent": opponent,
        "line": line,
        "cover": cover,
        "win_prob": win_prob,
        "projected_margin": projected_margin,
        "away_name": away_name,
        "home_name": home_name,
        "away_score": float(favorite_sim["away_score"]),
        "home_score": float(favorite_sim["home_score"]),
        "fair_odds": odds(cover),
        "one_run": float(favorite_sim["p_one_run"]),
        "blowout": float(favorite_sim["p_blowout"]),
        "confidence": confidence,
        "data_score": int(model.get("data_score", 0) or 0),
        "status": row.get("status", "Unknown"),
        "first_pitch": row.get("first_pitch_et", "TBD"),
        "venue": row.get("venue_name", "Unknown"),
        "away_pitcher": row.get("away_pitcher", "TBD"),
        "home_pitcher": row.get("home_pitcher", "TBD"),
        "simulations": int(favorite_sim["simulations"]),
        "mc_se": float(favorite_sim["mc_se"]),
        "batch_spread": float(favorite_sim["batch_spread"]),
        "converged": bool(favorite_sim["converged"]),
        "model": model,
    }


def _render_spread_cards(results, status_info, team_logo, h):
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for rank, result in enumerate(results[:5], 1):
        status_label, status_css = status_info(result.get("status"))
        badge = _badge_class(result.get("confidence"))
        first = " ks-first" if rank == 1 else ""
        logo = team_logo(result.get("team_id"))
        score = (
            f'{result["away_name"]} {result["away_score"]:.1f} — '
            f'{result["home_name"]} {result["home_score"]:.1f}'
        )
        card = (
            f'<div class="ks-pick-card{first}">'
            f'<div class="ks-rank">{medals.get(rank, "•")} #{rank}</div>'
            '<div class="ks-card-main">'
            '<div class="ks-player-row">'
            f'{logo}'
            '<div class="ks-player-copy">'
            f'<div class="ks-player">{h(result["team"])} {result["line"]:+.1f}</div>'
            f'<div class="ks-matchup">vs {h(result["opponent"])} • Projected {h(score)}</div>'
            '</div></div>'
            '<div class="ks-meta-line">'
            f'<span class="ks-status {status_css}">{h(status_label)}</span>'
            f'<span class="ks-mini">🕒 {h(result["first_pitch"])} ET</span>'
            f'<span class="ks-mini">xMargin {result["projected_margin"]:+.1f}</span>'
            '</div>'
            '<details class="ks-card-details">'
            '<summary>＋ Spread details</summary>'
            '<div class="ks-detail-body">'
            f'Win <b>{result["win_prob"] * 100:.1f}%</b> • '
            f'Fair cover odds <b>{h(result["fair_odds"])}</b><br>'
            f'One-run game <b>{result["one_run"] * 100:.1f}%</b> • '
            f'4+ run margin <b>{result["blowout"] * 100:.1f}%</b> • '
            f'Data <b>{result["data_score"]}/9</b>'
            '</div></details>'
            '</div>'
            '<div class="ks-right">'
            f'<div class="ks-prob">{result["cover"] * 100:.1f}%</div>'
            '<div class="ks-prob-label">Projected cover</div>'
            '<div class="ks-card-meta">'
            f'<span class="ks-badge {badge}">DATA {h(result["confidence"])}</span>'
            f'<span class="ks-mini">Fair {h(result["fair_odds"])}</span>'
            '</div></div></div>'
        )
        st.markdown(card, unsafe_allow_html=True)


def _render_scanner(games_df, section_header, status_info, team_logo, h):
    section_header(
        "Daily Spread Scanner — V15.1",
        "Scans every actionable MLB game and ranks the strongest standard run-line side by projected cover probability.",
    )

    st.markdown(
        '<div class="ks-note"><b>Scanner rule:</b> V15.1 first identifies its own projected favorite, then compares that team -1.5 against the model underdog +1.5. This is pure model probability — bookmaker odds/favorite designation are not inputs yet.</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1.4])
    with c1:
        include_live = st.checkbox(
            "⚠️ Include live games",
            value=False,
            key="spread_scan_live",
        )
    with c2:
        depth = st.selectbox(
            "Slate simulation depth",
            ["Fast — 50K/game", "Standard — 150K/game", "Deep — 300K/game"],
            index=1,
            key="spread_scan_depth",
        )

    if include_live:
        st.warning(
            "Live mode is only for testing. The scanner still uses the pregame run model and does not account for the current score, inning, outs, or in-game bullpen usage."
        )

    sim_n = {
        "Fast — 50K/game": 50_000,
        "Standard — 150K/game": 150_000,
        "Deep — 300K/game": 300_000,
    }[depth]

    if st.button(
        "🔥 SCAN TODAY'S MLB SPREADS",
        use_container_width=True,
        type="primary",
        key="spread_scan_button",
    ):
        rows = _actionable_rows(games_df, include_live)
        if not rows:
            st.info("No actionable MLB games are available for the selected mode.")
        else:
            results = []
            errors = 0
            bar = st.progress(0, text="Building spread models...")
            for i, row in enumerate(rows, 1):
                try:
                    results.append(_scan_game(row, sim_n))
                except Exception:
                    errors += 1
                bar.progress(i / len(rows), text=f"Modeling game {i}/{len(rows)}")
            bar.empty()

            results.sort(key=lambda x: x["cover"], reverse=True)
            st.session_state["v15_spread_slate"] = results
            st.session_state["v15_spread_scan_time"] = datetime.now(ET).strftime(
                "%I:%M:%S %p ET"
            ).lstrip("0")
            st.session_state["v15_spread_scan_errors"] = errors

    results = st.session_state.get("v15_spread_slate") or []
    if not results:
        return

    section_header(
        "Today's Strongest Spread Projections",
        "Ranked by V15.1 projected cover probability — not sportsbook value.",
    )
    scan_time = st.session_state.get("v15_spread_scan_time")
    if scan_time:
        st.markdown(
            f'<div class="ks-updated">↻ Last spread scan {h(scan_time)}</div>',
            unsafe_allow_html=True,
        )

    errors = int(st.session_state.get("v15_spread_scan_errors", 0) or 0)
    if errors:
        st.caption(f"{errors} game(s) could not be fully modeled and were skipped.")

    _render_spread_cards(results, status_info, team_logo, h)

    top = results[0]
    st.markdown(
        f'<div class="ks-note"><b>Current model #1:</b> {h(top["team"])} {top["line"]:+.1f} • '
        f'<b>{top["cover"] * 100:.1f}%</b> projected cover • Data confidence {h(top["confidence"])}.</div>',
        unsafe_allow_html=True,
    )

    with st.expander("📋 Full spread rankings"):
        rows = []
        for rank, result in enumerate(results, 1):
            rows.append(
                {
                    "#": rank,
                    "Side": f'{result["team"]} {result["line"]:+.1f}',
                    "Opponent": result["opponent"],
                    "Cover": f'{result["cover"] * 100:.1f}%',
                    "Win": f'{result["win_prob"] * 100:.1f}%',
                    "xMargin": f'{result["projected_margin"]:+.1f}',
                    "Score": f'{result["away_score"]:.1f}-{result["home_score"]:.1f}',
                    "Fair": result["fair_odds"],
                    "Data Conf": result["confidence"],
                    "Data": f'{result["data_score"]}/9',
                    "Time": result["first_pitch"],
                    "Status": result["status"],
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_spread_hub(games_df, section_header, status_info, team_logo, h):
    scanner_tab, analyzer_tab = st.tabs([
        "🏆 Spread Scanner",
        "🔎 Game Analyzer",
    ])

    with scanner_tab:
        _render_scanner(games_df, section_header, status_info, team_logo, h)

    with analyzer_tab:
        st.markdown(
            '<div class="ks-note"><b>Confidence label clarification:</b> the analyzer badge describes data completeness + simulation convergence. It is not saying the selected spread itself is a high-confidence bet.</div>',
            unsafe_allow_html=True,
        )
        render_spread_module(games_df, section_header, status_info, team_logo, h)
