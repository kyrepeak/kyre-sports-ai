from datetime import datetime

import pandas as pd
import streamlit as st

from engine import ET, actionable, odds
from spread_engine import build_game_model, render_spread_module, simulate_run_line, _stable_seed
from spread_history import adjusted_probability, history_adjustment


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
    if games_df is None or games_df.empty:
        return []
    return [row for _, row in games_df.iterrows() if actionable(row.get("status"), include_live=include_live)]


def _history_for_side(model, row, side, line):
    if side == "home":
        team_id = int(row["home_team_id"])
        opponent_id = int(row["away_team_id"])
        selected_recent = model.get("home_recent")
        opponent_recent = model.get("away_recent")
    else:
        team_id = int(row["away_team_id"])
        opponent_id = int(row["home_team_id"])
        selected_recent = model.get("away_recent")
        opponent_recent = model.get("home_recent")

    return history_adjustment(
        team_id,
        opponent_id,
        float(line),
        int(row["home_team_id"]),
        selected_recent,
        opponent_recent,
    )


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
    favorite_side = "home" if home_mean >= away_mean else "away"
    dog_side = "away" if favorite_side == "home" else "home"

    seed = _stable_seed(game_pk, 1520)
    sim = simulate_run_line(
        away_mean,
        home_mean,
        int(simulations),
        seed,
        favorite_side,
        -1.5,
    )

    core_fav = float(sim["p_cover"])
    core_dog = float(sim["p_opponent_cover"])
    fav_history = _history_for_side(model, row, favorite_side, -1.5)
    dog_history = _history_for_side(model, row, dog_side, 1.5)
    final_fav = adjusted_probability(core_fav, fav_history)
    final_dog = adjusted_probability(core_dog, dog_history)

    if final_fav >= final_dog:
        side = favorite_side
        line = -1.5
        core_cover = core_fav
        final_cover = final_fav
        context = fav_history
        win_prob = float(sim["p_win"])
    else:
        side = dog_side
        line = 1.5
        core_cover = core_dog
        final_cover = final_dog
        context = dog_history
        win_prob = 1.0 - float(sim["p_win"])

    team = home_name if side == "home" else away_name
    opponent = away_name if side == "home" else home_name
    team_id = int(row["home_team_id"] if side == "home" else row["away_team_id"])
    selected_score = float(sim["home_score"] if side == "home" else sim["away_score"])
    opponent_score = float(sim["away_score"] if side == "home" else sim["home_score"])

    return {
        "game_pk": game_pk,
        "team": team,
        "team_id": team_id,
        "opponent": opponent,
        "line": line,
        "core_cover": core_cover,
        "cover": final_cover,
        "history_adjustment": float(context.get("adjustment", 0.0)),
        "history": context,
        "win_prob": win_prob,
        "projected_margin": selected_score - opponent_score,
        "away_name": away_name,
        "home_name": home_name,
        "away_score": float(sim["away_score"]),
        "home_score": float(sim["home_score"]),
        "fair_odds": odds(final_cover),
        "one_run": float(sim["p_one_run"]),
        "blowout": float(sim["p_blowout"]),
        "confidence": _data_confidence(model, sim),
        "data_score": int(model.get("data_score", 0) or 0),
        "status": row.get("status", "Unknown"),
        "first_pitch": row.get("first_pitch_et", "TBD"),
        "venue": row.get("venue_name", "Unknown"),
        "simulations": int(sim["simulations"]),
        "mc_se": float(sim["mc_se"]),
        "batch_spread": float(sim["batch_spread"]),
        "converged": bool(sim["converged"]),
        "model": model,
    }


def _render_cards(results, status_info, team_logo, h):
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for rank, r in enumerate(results[:5], 1):
        status_label, status_css = status_info(r.get("status"))
        badge = _badge_class(r.get("confidence"))
        first = " ks-first" if rank == 1 else ""
        logo = team_logo(r.get("team_id"))
        summary = r["history"]["summary"]
        h2h_text = f'{summary["wins"]}-{summary["losses"]}' if summary["games"] else "N/A"
        h2h_cover = summary.get("raw_cover_rate")
        h2h_cover_text = f"{h2h_cover * 100:.0f}%" if h2h_cover is not None else "N/A"
        score = f'{r["away_name"]} {r["away_score"]:.1f} — {r["home_name"]} {r["home_score"]:.1f}'

        card = (
            f'<div class="ks-pick-card{first}">'
            f'<div class="ks-rank">{medals.get(rank, "•")} #{rank}</div>'
            '<div class="ks-card-main"><div class="ks-player-row">'
            f'{logo}<div class="ks-player-copy">'
            f'<div class="ks-player">{h(r["team"])} {r["line"]:+.1f}</div>'
            f'<div class="ks-matchup">vs {h(r["opponent"])} • Projected {h(score)}</div>'
            '</div></div><div class="ks-meta-line">'
            f'<span class="ks-status {status_css}">{h(status_label)}</span>'
            f'<span class="ks-mini">🕒 {h(r["first_pitch"])} ET</span>'
            f'<span class="ks-mini">H2H L10 {h2h_text}</span>'
            '</div><details class="ks-card-details"><summary>＋ History + spread details</summary>'
            '<div class="ks-detail-body">'
            f'Core cover <b>{r["core_cover"] * 100:.1f}%</b> • History adj <b>{r["history_adjustment"] * 100:+.1f} pts</b><br>'
            f'H2H cover at {r["line"]:+.1f}: <b>{h2h_cover_text}</b> • Avg H2H margin <b>{summary.get("avg_margin") or 0:+.1f}</b><br>'
            f'Current-season H2H <b>{h(summary.get("current_season_record", "0-0"))}</b> • Venue H2H <b>{h(summary.get("venue_record", "0-0"))}</b><br>'
            f'Win <b>{r["win_prob"] * 100:.1f}%</b> • One-run <b>{r["one_run"] * 100:.1f}%</b> • Data <b>{r["data_score"]}/9</b>'
            '</div></details></div>'
            '<div class="ks-right">'
            f'<div class="ks-prob">{r["cover"] * 100:.1f}%</div>'
            '<div class="ks-prob-label">History-adjusted cover</div>'
            '<div class="ks-card-meta">'
            f'<span class="ks-badge {badge}">DATA {h(r["confidence"])}</span>'
            f'<span class="ks-mini">Fair {h(r["fair_odds"])}</span>'
            '</div></div></div>'
        )
        st.markdown(card, unsafe_allow_html=True)


def _render_scanner(games_df, section_header, status_info, team_logo, h):
    section_header(
        "Daily Spread Scanner — V15.2",
        "Core V15 run model + last-10 team form + shrinkage-weighted last-10 head-to-head history.",
    )
    st.markdown(
        '<div class="ks-note"><b>V15.2 history rule:</b> H2H is a small context layer, not the engine. Current-season meetings get extra weight, older games decay, venue history is included, and the total history adjustment is capped at ±5 percentage points. Today\'s game is excluded.</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1.4])
    with c1:
        include_live = st.checkbox("⚠️ Include live games", value=False, key="spread_scan_live_v152")
    with c2:
        depth = st.selectbox(
            "Slate simulation depth",
            ["Fast — 50K/game", "Standard — 150K/game", "Deep — 300K/game"],
            index=1,
            key="spread_scan_depth_v152",
        )
    if include_live:
        st.warning("Live mode is only for testing. The score/inning/outs are not part of this pregame model.")

    sim_n = {"Fast — 50K/game": 50_000, "Standard — 150K/game": 150_000, "Deep — 300K/game": 300_000}[depth]

    if st.button("🔥 SCAN V15.2 SPREADS + H2H", use_container_width=True, type="primary", key="spread_scan_v152"):
        rows = _actionable_rows(games_df, include_live)
        if not rows:
            st.info("No actionable MLB games are available for this mode.")
        else:
            results, errors = [], 0
            bar = st.progress(0, text="Building V15.2 spread + history models...")
            for i, row in enumerate(rows, 1):
                try:
                    results.append(_scan_game(row, sim_n))
                except Exception:
                    errors += 1
                bar.progress(i / len(rows), text=f"Modeling game {i}/{len(rows)}")
            bar.empty()
            results.sort(key=lambda x: x["cover"], reverse=True)
            st.session_state["v152_spread_slate"] = results
            st.session_state["v152_spread_scan_time"] = datetime.now(ET).strftime("%I:%M:%S %p ET").lstrip("0")
            st.session_state["v152_spread_errors"] = errors

    results = st.session_state.get("v152_spread_slate") or []
    if not results:
        return

    section_header("Today's Strongest Spread Projections", "Ranked by V15.2 history-adjusted cover probability — not sportsbook value.")
    scan_time = st.session_state.get("v152_spread_scan_time")
    if scan_time:
        st.markdown(f'<div class="ks-updated">↻ Last V15.2 scan {h(scan_time)}</div>', unsafe_allow_html=True)
    errors = int(st.session_state.get("v152_spread_errors", 0) or 0)
    if errors:
        st.caption(f"{errors} game(s) could not be fully modeled and were skipped.")

    _render_cards(results, status_info, team_logo, h)
    top = results[0]
    st.markdown(
        f'<div class="ks-note"><b>Current model #1:</b> {h(top["team"])} {top["line"]:+.1f} • '
        f'<b>{top["cover"] * 100:.1f}%</b> final cover • Core {top["core_cover"] * 100:.1f}% • '
        f'History {top["history_adjustment"] * 100:+.1f} pts.</div>',
        unsafe_allow_html=True,
    )

    with st.expander("📋 Full spread rankings"):
        rows = []
        for rank, r in enumerate(results, 1):
            s = r["history"]["summary"]
            rows.append({
                "#": rank,
                "Side": f'{r["team"]} {r["line"]:+.1f}',
                "Opponent": r["opponent"],
                "Core": f'{r["core_cover"] * 100:.1f}%',
                "History Adj": f'{r["history_adjustment"] * 100:+.1f} pts',
                "Final": f'{r["cover"] * 100:.1f}%',
                "H2H L10": f'{s["wins"]}-{s["losses"]}' if s["games"] else "N/A",
                "H2H Cover": f'{s["raw_cover_rate"] * 100:.0f}%' if s.get("raw_cover_rate") is not None else "N/A",
                "xMargin": f'{r["projected_margin"]:+.1f}',
                "Fair": r["fair_odds"],
                "Data": f'{r["data_score"]}/9',
                "Time": r["first_pitch"],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_history_overlay(games_df, section_header):
    result = st.session_state.get("v15_spread_result")
    if not result or games_df is None or games_df.empty:
        return
    game_pk = int(result.get("game_pk", 0) or 0)
    match = games_df[games_df["game_pk"].astype(int) == game_pk]
    if match.empty:
        return
    row = match.iloc[0]
    selected_team = result.get("selected_team")
    side = "home" if selected_team == row["home_team"] else "away"
    line = float(result.get("line", 0.0))
    core = float((result.get("sim") or {}).get("p_cover", 0.0))
    model = result.get("model") or {}
    context = _history_for_side(model, row, side, line)
    final = adjusted_probability(core, context)
    s = context["summary"]

    section_header("V15.2 Team History + H2H Overlay", "Use this final probability after the core V15 analyzer result above.")
    st.markdown(
        f'<div class="ks-feature"><div class="ks-eyebrow">{selected_team} {line:+.1f} • HISTORY-ADJUSTED</div>'
        f'<div class="ks-feature-prob">{final * 100:.1f}%</div>'
        f'<div class="ks-feature-meta">Core {core * 100:.1f}% • History adjustment {context["adjustment"] * 100:+.1f} pts • Fair {odds(final)}</div></div>',
        unsafe_allow_html=True,
    )

    from engine import metric_grid
    metric_grid([
        ("H2H Last 10", f'{s["wins"]}-{s["losses"]}' if s["games"] else "N/A"),
        ("H2H Cover", f'{s["raw_cover_rate"] * 100:.0f}%' if s.get("raw_cover_rate") is not None else "N/A"),
        ("Avg H2H Margin", f'{s["avg_margin"]:+.1f}' if s.get("avg_margin") is not None else "N/A"),
        ("One-Run H2H", f'{s["one_run_rate"] * 100:.0f}%' if s.get("one_run_rate") is not None else "N/A"),
        ("Current Season", s.get("current_season_record", "0-0")),
        ("At Today's Venue", s.get("venue_record", "0-0")),
        ("H2H Component", f'{context["h2h_adjustment"] * 100:+.1f} pts'),
        ("Venue Component", f'{context["venue_adjustment"] * 100:+.1f} pts'),
    ])
    st.caption("Last-10 H2H only uses completed games before today. Recent team form is already in V15 core, so V15.2 only gives it a tiny tie-breaker weight to avoid double-counting.")


def render_spread_hub(games_df, section_header, status_info, team_logo, h):
    scanner_tab, analyzer_tab = st.tabs(["🏆 Spread Scanner", "🔎 Game Analyzer"])
    with scanner_tab:
        _render_scanner(games_df, section_header, status_info, team_logo, h)
    with analyzer_tab:
        st.markdown(
            '<div class="ks-note"><b>DATA confidence</b> describes completeness + convergence, not whether a spread itself is guaranteed.</div>',
            unsafe_allow_html=True,
        )
        render_spread_module(games_df, section_header, status_info, team_logo, h)
        _render_history_overlay(games_df, section_header)
