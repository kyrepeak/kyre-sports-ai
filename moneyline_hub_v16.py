from datetime import datetime

import pandas as pd
import streamlit as st

from engine import ET, actionable, clamp, odds
from spread_engine import build_game_model, simulate_run_line, _stable_seed
from spread_history import history_adjustment


MODEL_VERSION = "V16"


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


def _slate_date(games_df):
    if games_df is None or games_df.empty or "game_date" not in games_df.columns:
        return "NO_SLATE"
    values = games_df["game_date"].dropna().astype(str).unique().tolist()
    return values[0] if len(values) == 1 else "MIXED"


def _verified_df(games_df):
    if games_df is None:
        return pd.DataFrame()
    if games_df.empty:
        return games_df.copy()
    if "verified" in games_df.columns:
        return games_df[games_df["verified"].fillna(False).astype(bool)].copy()
    return games_df.copy()


def _verified_game_pks(games_df):
    df = _verified_df(games_df)
    if df.empty or "game_pk" not in df.columns:
        return set()
    return set(pd.to_numeric(df["game_pk"], errors="coerce").dropna().astype(int).tolist())


def _reset_stale_state(games_df):
    current_date = _slate_date(games_df)
    valid_pks = _verified_game_pks(games_df)
    previous_date = st.session_state.get("v16_ml_slate_date")
    stored = st.session_state.get("v16_moneyline_slate") or []

    stored_pks = set()
    for result in stored:
        try:
            stored_pks.add(int(result.get("game_pk")))
        except Exception:
            pass

    changed = previous_date is not None and previous_date != current_date
    mismatch = bool(stored_pks - valid_pks)
    if changed or mismatch:
        for key in (
            "v16_moneyline_slate",
            "v16_moneyline_scan_time",
            "v16_moneyline_errors",
            "v16_moneyline_game_result",
        ):
            st.session_state.pop(key, None)

    st.session_state["v16_ml_slate_date"] = current_date
    return current_date, valid_pks, changed or mismatch


def _available_rows(games_df, include_live=False):
    df = _verified_df(games_df)
    if df.empty:
        return []
    return [
        row
        for _, row in df.iterrows()
        if actionable(row.get("status"), include_live=include_live)
    ]


def _history_context(model, row, side):
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
        0.0,
        int(row["home_team_id"]),
        selected_recent,
        opponent_recent,
    )


def _moneyline_probabilities(core_home, home_context, away_context):
    """Apply a small symmetric history overlay while keeping probabilities summing to 100%."""
    home_adj = float((home_context or {}).get("adjustment", 0.0) or 0.0)
    away_adj = float((away_context or {}).get("adjustment", 0.0) or 0.0)

    # Difference-of-contexts prevents both sides from being independently
    # increased. The moneyline history layer is capped at +/-4 percentage pts.
    history_delta = clamp((home_adj - away_adj) / 2.0, -0.04, 0.04)
    final_home = clamp(float(core_home) + history_delta, 0.03, 0.97)
    return final_home, 1.0 - final_home, history_delta


def _scan_game(row, simulations):
    game_pk = int(row["game_pk"])
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
    seed = _stable_seed(game_pk, 1600)
    sim = simulate_run_line(
        away_mean,
        home_mean,
        int(simulations),
        seed,
        "home",
        0.0,
    )

    core_home = float(sim["p_win"])
    core_away = 1.0 - core_home
    home_history = _history_context(model, row, "home")
    away_history = _history_context(model, row, "away")
    final_home, final_away, history_delta = _moneyline_probabilities(
        core_home,
        home_history,
        away_history,
    )

    if final_home >= final_away:
        selected_side = "home"
        team = row["home_team"]
        team_id = int(row["home_team_id"])
        opponent = row["away_team"]
        core_prob = core_home
        final_prob = final_home
        selected_history = home_history
        history_effect = history_delta
        projected_margin = float(sim["home_score"] - sim["away_score"])
    else:
        selected_side = "away"
        team = row["away_team"]
        team_id = int(row["away_team_id"])
        opponent = row["home_team"]
        core_prob = core_away
        final_prob = final_away
        selected_history = away_history
        history_effect = -history_delta
        projected_margin = float(sim["away_score"] - sim["home_score"])

    return {
        "game_pk": game_pk,
        "game_date": row.get("game_date"),
        "selected_side": selected_side,
        "team": team,
        "team_id": team_id,
        "opponent": opponent,
        "away_name": row["away_team"],
        "home_name": row["home_team"],
        "away_team_id": int(row["away_team_id"]),
        "home_team_id": int(row["home_team_id"]),
        "away_score": float(sim["away_score"]),
        "home_score": float(sim["home_score"]),
        "core_prob": core_prob,
        "win_prob": final_prob,
        "history_effect": history_effect,
        "history": selected_history,
        "home_history": home_history,
        "away_history": away_history,
        "core_home": core_home,
        "core_away": core_away,
        "final_home": final_home,
        "final_away": final_away,
        "projected_margin": projected_margin,
        "fair_odds": odds(final_prob),
        "one_run": float(sim["p_one_run"]),
        "blowout": float(sim["p_blowout"]),
        "confidence": _data_confidence(model, sim),
        "data_score": int(model.get("data_score", 0) or 0),
        "status": row.get("status", "Unknown"),
        "first_pitch": row.get("first_pitch_et", "TBD"),
        "venue": row.get("venue_name", "Unknown"),
        "away_pitcher": row.get("away_pitcher", "TBD"),
        "home_pitcher": row.get("home_pitcher", "TBD"),
        "simulations": int(sim["simulations"]),
        "seed": int(sim["seed"]),
        "mc_se": float(sim["mc_se"]),
        "batch_spread": float(sim["batch_spread"]),
        "converged": bool(sim["converged"]),
        "model": model,
    }


def _render_cards(results, status_info, team_logo, h):
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for rank, result in enumerate(results[:5], 1):
        status_label, status_css = status_info(result.get("status"))
        badge = _badge_class(result.get("confidence"))
        first = " ks-first" if rank == 1 else ""
        logo = team_logo(result.get("team_id"))
        summary = (result.get("history") or {}).get("summary") or {}
        h2h_record = (
            f'{int(summary.get("wins", 0))}-{int(summary.get("losses", 0))}'
            if summary.get("games")
            else "N/A"
        )
        score = (
            f'{result["away_name"]} {result["away_score"]:.1f} — '
            f'{result["home_name"]} {result["home_score"]:.1f}'
        )

        card = (
            f'<div class="ks-pick-card{first}">'
            f'<div class="ks-rank">{medals.get(rank, "•")} #{rank}</div>'
            '<div class="ks-card-main"><div class="ks-player-row">'
            f'{logo}<div class="ks-player-copy">'
            f'<div class="ks-player">{h(result["team"])}</div>'
            f'<div class="ks-matchup">vs {h(result["opponent"])} • Projected {h(score)}</div>'
            '</div></div><div class="ks-meta-line">'
            f'<span class="ks-status {status_css}">{h(status_label)}</span>'
            f'<span class="ks-mini">🕒 {h(result["first_pitch"])} ET</span>'
            f'<span class="ks-mini">H2H L10 {h(h2h_record)}</span>'
            '</div><details class="ks-card-details"><summary>＋ Moneyline details</summary>'
            '<div class="ks-detail-body">'
            f'Core win <b>{result["core_prob"] * 100:.1f}%</b> • History adj <b>{result["history_effect"] * 100:+.1f} pts</b><br>'
            f'Projected margin <b>{result["projected_margin"]:+.1f}</b> • One-run game <b>{result["one_run"] * 100:.1f}%</b><br>'
            f'Projected score <b>{h(score)}</b> • Data <b>{result["data_score"]}/9</b>'
            '</div></details></div>'
            '<div class="ks-right">'
            f'<div class="ks-prob">{result["win_prob"] * 100:.1f}%</div>'
            '<div class="ks-prob-label">Projected win</div>'
            '<div class="ks-card-meta">'
            f'<span class="ks-badge {badge}">DATA {h(result["confidence"])}</span>'
            f'<span class="ks-mini">Fair {h(result["fair_odds"])}</span>'
            '</div></div></div>'
        )
        st.markdown(card, unsafe_allow_html=True)


def _render_scanner(games_df, section_header, status_info, team_logo, h):
    current_date, valid_pks, reset = _reset_stale_state(games_df)
    if reset:
        st.info(
            f"🔄 Moneyline slate changed. Old results were cleared and rebound to the verified {current_date} schedule."
        )

    verified = _verified_df(games_df)
    if not verified.empty:
        st.caption(
            f"✅ Verified MLB slate: {len(verified)} game(s) • {current_date} • V16 can only model game IDs on this date."
        )

    section_header(
        "Daily Moneyline Scanner — V16",
        "Independent team win probabilities from the run model + starters + bullpens + last-10 form + lineups + park/weather + small H2H context.",
    )
    st.markdown(
        '<div class="ks-note"><b>V16 rule:</b> sportsbook moneyline prices are not model inputs. '
        'The engine projects the game first, then converts its win probability to fair moneyline odds. '
        'H2H is capped as a small context layer.</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 1.4])
    with c1:
        include_live = st.checkbox(
            "⚠️ Include live games",
            value=False,
            key="v16_ml_include_live",
        )
    with c2:
        depth = st.selectbox(
            "Slate simulation depth",
            ["Fast — 50K/game", "Standard — 150K/game", "Deep — 300K/game"],
            index=1,
            key="v16_ml_depth",
        )

    if include_live:
        st.warning(
            "Live mode is only for testing. V16 still uses the pregame model and does not use the live score, inning, outs or current bullpen usage."
        )

    sim_n = {
        "Fast — 50K/game": 50_000,
        "Standard — 150K/game": 150_000,
        "Deep — 300K/game": 300_000,
    }[depth]

    if st.button(
        "🔥 SCAN V16 MLB MONEYLINES",
        use_container_width=True,
        type="primary",
        key="v16_ml_scan",
    ):
        rows = _available_rows(verified, include_live=include_live)
        if not rows:
            st.info("No actionable verified MLB games are available for this date.")
        else:
            results = []
            errors = 0
            bar = st.progress(0, text="Building V16 moneyline models...")
            for idx, row in enumerate(rows, 1):
                try:
                    result = _scan_game(row, sim_n)
                    if int(result["game_pk"]) in valid_pks:
                        results.append(result)
                except Exception:
                    errors += 1
                bar.progress(idx / len(rows), text=f"Modeling game {idx}/{len(rows)}")
            bar.empty()
            results.sort(key=lambda x: x["win_prob"], reverse=True)
            st.session_state["v16_moneyline_slate"] = results
            st.session_state["v16_moneyline_scan_time"] = datetime.now(ET).strftime("%I:%M:%S %p ET").lstrip("0")
            st.session_state["v16_moneyline_errors"] = errors

    results = st.session_state.get("v16_moneyline_slate") or []
    clean = []
    for result in results:
        try:
            if int(result.get("game_pk")) in valid_pks:
                clean.append(result)
        except Exception:
            continue
    if len(clean) != len(results):
        st.session_state["v16_moneyline_slate"] = clean
        results = clean
        st.warning("A stale/cross-date moneyline result was removed before display.")

    if not results:
        return

    section_header(
        "Today's Strongest Moneyline Projections",
        "Ranked by V16 projected win probability — not sportsbook value.",
    )
    scan_time = st.session_state.get("v16_moneyline_scan_time")
    if scan_time:
        st.markdown(
            f'<div class="ks-updated">↻ Last V16 scan {h(scan_time)}</div>',
            unsafe_allow_html=True,
        )
    errors = int(st.session_state.get("v16_moneyline_errors", 0) or 0)
    if errors:
        st.caption(f"{errors} game(s) could not be fully modeled and were skipped.")

    _render_cards(results, status_info, team_logo, h)
    top = results[0]
    st.markdown(
        f'<div class="ks-note"><b>Current model #1:</b> {h(top["team"])} • '
        f'<b>{top["win_prob"] * 100:.1f}%</b> projected win • Fair {h(top["fair_odds"])} • '
        f'Core {top["core_prob"] * 100:.1f}% • History {top["history_effect"] * 100:+.1f} pts.</div>',
        unsafe_allow_html=True,
    )

    with st.expander("📋 Full moneyline rankings"):
        table = []
        for rank, result in enumerate(results, 1):
            summary = (result.get("history") or {}).get("summary") or {}
            table.append(
                {
                    "#": rank,
                    "Team": result["team"],
                    "Opponent": result["opponent"],
                    "Win %": f'{result["win_prob"] * 100:.1f}%',
                    "Core": f'{result["core_prob"] * 100:.1f}%',
                    "History Adj": f'{result["history_effect"] * 100:+.1f} pts',
                    "Fair ML": result["fair_odds"],
                    "xMargin": f'{result["projected_margin"]:+.1f}',
                    "H2H L10": (
                        f'{int(summary.get("wins", 0))}-{int(summary.get("losses", 0))}'
                        if summary.get("games") else "N/A"
                    ),
                    "Data": f'{result["data_score"]}/9',
                    "Time": result["first_pitch"],
                }
            )
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)


def _game_label(row):
    return (
        f'{row["away_team"]} @ {row["home_team"]} • '
        f'{row.get("first_pitch_et", "TBD")} • {row.get("status", "Unknown")}'
    )


def _render_analyzer(games_df, section_header, status_info, team_logo, h):
    verified = _verified_df(games_df)
    section_header(
        "MLB Moneyline Analyzer — V16",
        "Choose one verified matchup and inspect both teams' projected win probabilities and fair odds.",
    )
    st.markdown(
        '<div class="ks-note"><b>DATA confidence</b> describes data completeness + Monte Carlo convergence. '
        'It does not mean the team is a guaranteed winner.</div>',
        unsafe_allow_html=True,
    )

    include_live = st.checkbox(
        "⚠️ Include live games",
        value=False,
        key="v16_ml_analyzer_live",
    )
    rows = _available_rows(verified, include_live=include_live)
    if not rows:
        st.info("No actionable verified MLB games are available for this date.")
        return

    labels = [_game_label(row) for row in rows]
    choice = st.selectbox("Game", labels, key="v16_ml_game")
    game = rows[labels.index(choice)]

    status_label, status_css = status_info(game.get("status"))
    logos = f'{team_logo(game.get("away_team_id"))}{team_logo(game.get("home_team_id"))}'
    st.markdown(
        '<div class="ks-feature">'
        f'<div class="ks-eyebrow">{h(status_label)} • {h(game.get("first_pitch_et", "TBD"))} ET</div>'
        f'<div class="ks-player-row" style="margin-top:8px">{logos}<div class="ks-player-copy">'
        f'<div class="ks-feature-name">{h(game["away_team"])} @ {h(game["home_team"])}</div>'
        f'<div class="ks-feature-meta">{h(game.get("venue_name", "Unknown"))} • '
        f'{h(game.get("away_pitcher", "TBD"))} vs {h(game.get("home_pitcher", "TBD"))}</div>'
        '</div></div></div>',
        unsafe_allow_html=True,
    )

    depth = st.selectbox(
        "Simulation size",
        ["Quick — 250K", "Standard — 1M", "Deep — 3M"],
        index=1,
        key="v16_ml_analyzer_depth",
    )
    sim_n = {
        "Quick — 250K": 250_000,
        "Standard — 1M": 1_000_000,
        "Deep — 3M": 3_000_000,
    }[depth]

    if st.button(
        "🔥 RUN V16 MONEYLINE PROJECTION",
        use_container_width=True,
        type="primary",
        key="v16_ml_analyze",
    ):
        with st.spinner("Building team profiles, pitcher/bullpen layers, H2H context and Monte Carlo..."):
            try:
                result = _scan_game(game, sim_n)
                st.session_state["v16_moneyline_game_result"] = result
            except Exception as exc:
                st.error(f"V16 could not complete this matchup: {exc}")

    result = st.session_state.get("v16_moneyline_game_result")
    if not result:
        return
    if int(result.get("game_pk", -1)) != int(game["game_pk"]):
        return

    section_header(
        "V16 Moneyline Projection",
        "Independent score projection + game-win simulation + small H2H context layer.",
    )

    score = f'{result["away_name"]} {result["away_score"]:.1f} — {result["home_name"]} {result["home_score"]:.1f}'
    confidence = result["confidence"]
    badge = _badge_class(confidence)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            '<div class="ks-feature">'
            f'<div class="ks-eyebrow">{h(result["away_name"])}</div>'
            f'<div class="ks-feature-prob">{result["final_away"] * 100:.1f}%</div>'
            f'<div class="ks-feature-meta">Projected win • Fair {h(odds(result["final_away"]))}</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div class="ks-feature">'
            f'<div class="ks-eyebrow">{h(result["home_name"])}</div>'
            f'<div class="ks-feature-prob">{result["final_home"] * 100:.1f}%</div>'
            f'<div class="ks-feature-meta">Projected win • Fair {h(odds(result["final_home"]))}</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<div class="ks-note"><b>Projected score:</b> {h(score)} • '
        f'One-run game {result["one_run"] * 100:.1f}% • 4+ run margin {result["blowout"] * 100:.1f}% • '
        f'<span class="ks-badge {badge}">DATA {h(confidence)}</span></div>',
        unsafe_allow_html=True,
    )

    home_summary = (result.get("home_history") or {}).get("summary") or {}
    away_summary = (result.get("away_history") or {}).get("summary") or {}
    with st.expander("🧠 Model + history details"):
        details = pd.DataFrame(
            [
                {
                    "Team": result["away_name"],
                    "Core Win": f'{result["core_away"] * 100:.1f}%',
                    "Final Win": f'{result["final_away"] * 100:.1f}%',
                    "Fair ML": odds(result["final_away"]),
                    "H2H L10": (
                        f'{int(away_summary.get("wins", 0))}-{int(away_summary.get("losses", 0))}'
                        if away_summary.get("games") else "N/A"
                    ),
                },
                {
                    "Team": result["home_name"],
                    "Core Win": f'{result["core_home"] * 100:.1f}%',
                    "Final Win": f'{result["final_home"] * 100:.1f}%',
                    "Fair ML": odds(result["final_home"]),
                    "H2H L10": (
                        f'{int(home_summary.get("wins", 0))}-{int(home_summary.get("losses", 0))}'
                        if home_summary.get("games") else "N/A"
                    ),
                },
            ]
        )
        st.dataframe(details, use_container_width=True, hide_index=True)
        st.caption(
            f'Simulations {result["simulations"]:,} • Seed {result["seed"]} • '
            f'MC SE {result["mc_se"] * 100:.3f} pts • Max batch spread {result["batch_spread"] * 100:.2f} pts • '
            f'Convergence {"PASS" if result["converged"] else "CHECK"} • Data {result["data_score"]}/9.'
        )


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    scanner_tab, analyzer_tab = st.tabs(
        [
            "🏆 Moneyline Scanner",
            "🔎 Game Analyzer",
        ]
    )
    with scanner_tab:
        _render_scanner(games_df, section_header, status_info, team_logo, h)
    with analyzer_tab:
        _render_analyzer(games_df, section_header, status_info, team_logo, h)
