from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

from engine import ET, actionable, clamp, odds
from spread_engine import build_game_model, recent_team_form, _stable_seed
from spread_history import h2h_last10

MODEL_VERSION = "V17"


def _verified_df(games_df):
    if games_df is None:
        return pd.DataFrame()
    if games_df.empty:
        return games_df.copy()
    if "verified" in games_df.columns:
        return games_df[games_df["verified"].fillna(False).astype(bool)].copy()
    return games_df.copy()


def _slate_date(games_df):
    df = _verified_df(games_df)
    if df.empty or "game_date" not in df.columns:
        return "NO_SLATE"
    values = df["game_date"].dropna().astype(str).unique().tolist()
    return values[0] if len(values) == 1 else "MIXED"


def _valid_pks(games_df):
    df = _verified_df(games_df)
    if df.empty or "game_pk" not in df.columns:
        return set()
    return set(pd.to_numeric(df["game_pk"], errors="coerce").dropna().astype(int).tolist())


def _available_rows(games_df, include_live=False):
    df = _verified_df(games_df)
    if df.empty:
        return []
    return [
        row
        for _, row in df.iterrows()
        if actionable(row.get("status"), include_live=include_live)
    ]


def _reset_stale_state(games_df):
    current_date = _slate_date(games_df)
    valid = _valid_pks(games_df)
    previous = st.session_state.get("v17_total_slate_date")
    stored = st.session_state.get("v17_total_slate") or []

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
            "v17_total_slate",
            "v17_total_scan_time",
            "v17_total_errors",
            "v17_total_game_result",
        ):
            st.session_state.pop(key, None)

    st.session_state["v17_total_slate_date"] = current_date
    return current_date, valid, changed or mismatch


def _record(form):
    if not form or not form.get("games"):
        return "N/A"
    games = int(form.get("games") or 0)
    wins = int(round(float(form.get("win_pct", 0) or 0) * games))
    wins = max(0, min(wins, games))
    return f"{wins}-{games - wins}"


def _recent5(team_id):
    try:
        return recent_team_form(int(team_id), 5)
    except Exception:
        return None


def _h2h_summary(away_id, home_id):
    try:
        games = h2h_last10(int(away_id), int(home_id), 10, 4)
    except Exception:
        games = []

    totals = [float(g.get("team_runs", 0) or 0) + float(g.get("opponent_runs", 0) or 0) for g in games]
    last5 = totals[:5]
    return {
        "games": games,
        "count": len(games),
        "avg_total_l10": float(np.mean(totals)) if totals else None,
        "avg_total_l5": float(np.mean(last5)) if last5 else None,
        "median_total_l10": float(np.median(totals)) if totals else None,
    }


def _history_total_adjustment(core_total, h2h):
    """Small H2H context adjustment, capped so old meetings cannot drive V17."""
    n = int((h2h or {}).get("count", 0) or 0)
    avg10 = (h2h or {}).get("avg_total_l10")
    avg5 = (h2h or {}).get("avg_total_l5")
    if not n or avg10 is None:
        return 0.0

    shrink = n / (n + 14.0)
    long_signal = (float(avg10) - float(core_total)) * shrink * 0.10
    short_signal = 0.0
    if avg5 is not None:
        short_signal = (float(avg5) - float(avg10)) * min(len((h2h or {}).get("games", [])[:5]) / 8.0, 0.625) * 0.04
    return clamp(long_signal + short_signal, -0.35, 0.35)


def _data_confidence(model, sim=None):
    score = int(model.get("data_score", 0) or 0)
    converged = True if sim is None else bool(sim.get("converged"))
    if score >= 8 and converged:
        return "HIGH"
    if score >= 6 and converged:
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


def _build_total_model(row):
    model = build_game_model(
        int(row["game_pk"]),
        int(row["away_team_id"]),
        int(row["home_team_id"]),
        row.get("away_pitcher_id"),
        row.get("home_pitcher_id"),
        row.get("venue_name", "Unknown"),
    )

    away_mean = float(model["away_model"]["expected_runs"])
    home_mean = float(model["home_model"]["expected_runs"])
    core_total = away_mean + home_mean
    h2h = _h2h_summary(row["away_team_id"], row["home_team_id"])
    history_adj = _history_total_adjustment(core_total, h2h)

    # Split the tiny history adjustment proportionally so projected team scores
    # still sum exactly to the adjusted game total.
    denom = max(core_total, 1e-9)
    away_share = away_mean / denom
    away_final = max(0.5, away_mean + history_adj * away_share)
    home_final = max(0.5, home_mean + history_adj * (1.0 - away_share))

    return {
        "game_pk": int(row["game_pk"]),
        "game_date": row.get("game_date"),
        "away_team": row["away_team"],
        "home_team": row["home_team"],
        "away_team_id": int(row["away_team_id"]),
        "home_team_id": int(row["home_team_id"]),
        "away_pitcher": row.get("away_pitcher", "TBD"),
        "home_pitcher": row.get("home_pitcher", "TBD"),
        "first_pitch": row.get("first_pitch_et", "TBD"),
        "status": row.get("status", "Unknown"),
        "venue": row.get("venue_name", "Unknown"),
        "away_mean_core": away_mean,
        "home_mean_core": home_mean,
        "core_total": core_total,
        "history_adjustment": history_adj,
        "away_mean": away_final,
        "home_mean": home_final,
        "projected_total": away_final + home_final,
        "h2h": h2h,
        "model": model,
        "data_score": int(model.get("data_score", 0) or 0),
        "confidence": _data_confidence(model),
    }


@st.cache_data(ttl=600, show_spinner=False)
def simulate_total(away_mean, home_mean, total_line, n, seed):
    n = int(n)
    rng = np.random.default_rng(int(seed))
    batch_size = 250_000
    done = 0

    over_count = under_count = push_count = 0
    total_sum = 0.0
    total_counts = {}
    batch_over = []

    while done < n:
        k = min(batch_size, n - done)
        shared = rng.lognormal(mean=-0.5 * 0.10**2, sigma=0.10, size=k)
        dispersion = 6.5
        away_lambda = rng.gamma(dispersion, away_mean / dispersion, size=k) * shared
        home_lambda = rng.gamma(dispersion, home_mean / dispersion, size=k) * shared
        away_runs = rng.poisson(away_lambda).astype(np.int16)
        home_runs = rng.poisson(home_lambda).astype(np.int16)

        # MLB totals generally include extra innings. Resolve regulation ties by
        # adding the deciding extra-inning run, matching the existing game model.
        tied = away_runs == home_runs
        if np.any(tied):
            home_extra_p = home_mean / max(home_mean + away_mean, 1e-6)
            home_wins_tie = rng.random(int(tied.sum())) < home_extra_p
            idx = np.flatnonzero(tied)
            home_runs[idx[home_wins_tie]] += 1
            away_runs[idx[~home_wins_tie]] += 1

        totals = away_runs + home_runs
        total_sum += float(totals.sum())
        over = totals > float(total_line) + 1e-9
        under = totals < float(total_line) - 1e-9
        push = np.abs(totals.astype(float) - float(total_line)) <= 1e-9

        over_count += int(over.sum())
        under_count += int(under.sum())
        push_count += int(push.sum())
        batch_over.append(float(over.mean()))

        vals, counts = np.unique(totals, return_counts=True)
        for v, c in zip(vals.tolist(), counts.tolist()):
            total_counts[int(v)] = total_counts.get(int(v), 0) + int(c)

        done += k

    p_over = over_count / done
    p_under = under_count / done
    p_push = push_count / done
    settled = max(1.0 - p_push, 1e-9)
    conditional_over = p_over / settled
    conditional_under = p_under / settled

    ordered = sorted(total_counts.items())
    cumulative = 0
    median_total = 0
    for total, count in ordered:
        cumulative += count
        if cumulative >= done / 2:
            median_total = total
            break
    mode_total = max(total_counts.items(), key=lambda x: x[1])[0] if total_counts else 0

    # Distribution percentile range from the discrete frequency table.
    def q_from_counts(q):
        target = q * done
        csum = 0
        for total, count in ordered:
            csum += count
            if csum >= target:
                return int(total)
        return int(ordered[-1][0]) if ordered else 0

    se = float(np.sqrt(max(p_over * (1 - p_over), 0.0) / done))
    spread = max(batch_over) - min(batch_over) if batch_over else 0.0

    return {
        "simulations": done,
        "seed": int(seed),
        "expected_total": total_sum / done,
        "p_over": p_over,
        "p_under": p_under,
        "p_push": p_push,
        "fair_over": odds(conditional_over),
        "fair_under": odds(conditional_under),
        "median_total": int(median_total),
        "mode_total": int(mode_total),
        "p10": q_from_counts(0.10),
        "p90": q_from_counts(0.90),
        "mc_se": se,
        "batch_spread": float(spread),
        "converged": bool(spread <= 0.006),
    }


def _scan_game(row):
    result = _build_total_model(row)
    model = result["model"]
    away5 = _recent5(result["away_team_id"])
    home5 = _recent5(result["home_team_id"])
    result["away_recent5"] = away5
    result["home_recent5"] = home5
    result["confidence"] = _data_confidence(model)
    return result


def _fmt_form(form):
    if not form:
        return "N/A"
    return (
        f'{_record(form)} • R/G {float(form.get("runs_per_game", 0) or 0):.2f} • '
        f'RA/G {float(form.get("runs_allowed_per_game", 0) or 0):.2f} • '
        f'Game total env {(float(form.get("runs_per_game", 0) or 0) + float(form.get("runs_allowed_per_game", 0) or 0)):.2f}'
    )


def _render_total_cards(results, status_info, team_logo, h):
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for rank, result in enumerate(results[:5], 1):
        status_label, status_css = status_info(result.get("status"))
        badge = _badge_class(result.get("confidence"))
        first = " ks-first" if rank == 1 else ""
        logos = f'{team_logo(result.get("away_team_id"))}{team_logo(result.get("home_team_id"))}'
        h2h = result.get("h2h") or {}
        avg10 = h2h.get("avg_total_l10")
        avg5 = h2h.get("avg_total_l5")
        avg10_text = f"{avg10:.1f}" if avg10 is not None else "N/A"
        avg5_text = f"{avg5:.1f}" if avg5 is not None else "N/A"
        away10 = (result.get("model") or {}).get("away_recent")
        home10 = (result.get("model") or {}).get("home_recent")

        card = (
            f'<div class="ks-pick-card{first}">'
            f'<div class="ks-rank">{medals.get(rank, "•")} #{rank}</div>'
            '<div class="ks-card-main"><div class="ks-player-row">'
            f'{logos}<div class="ks-player-copy">'
            f'<div class="ks-player">{h(result["away_team"])} @ {h(result["home_team"])}</div>'
            f'<div class="ks-matchup">Projected {result["away_mean"]:.1f} — {result["home_mean"]:.1f} • '
            f'{h(result.get("away_pitcher", "TBD"))} vs {h(result.get("home_pitcher", "TBD"))}</div>'
            '</div></div><div class="ks-meta-line">'
            f'<span class="ks-status {status_css}">{h(status_label)}</span>'
            f'<span class="ks-mini">🕒 {h(result["first_pitch"])} ET</span>'
            f'<span class="ks-mini">H2H avg L10 {h(avg10_text)}</span>'
            f'<span class="ks-mini">H2H avg L5 {h(avg5_text)}</span>'
            '</div><details class="ks-card-details"><summary>＋ Total history + recent form</summary>'
            '<div class="ks-detail-body">'
            f'Core projected total <b>{result["core_total"]:.2f}</b> • History adj <b>{result["history_adjustment"]:+.2f} runs</b><br>'
            f'{h(result["away_team"])} L10: <b>{h(_fmt_form(away10))}</b><br>'
            f'{h(result["away_team"])} L5: <b>{h(_fmt_form(result.get("away_recent5")))}</b><br>'
            f'{h(result["home_team"])} L10: <b>{h(_fmt_form(home10))}</b><br>'
            f'{h(result["home_team"])} L5: <b>{h(_fmt_form(result.get("home_recent5")))}</b><br>'
            f'H2H meetings used <b>{int(h2h.get("count", 0) or 0)}</b> • Data <b>{result["data_score"]}/9</b>'
            '</div></details></div>'
            '<div class="ks-right">'
            f'<div class="ks-prob">{result["projected_total"]:.1f}</div>'
            '<div class="ks-prob-label">Projected total</div>'
            '<div class="ks-card-meta">'
            f'<span class="ks-badge {badge}">DATA {h(result["confidence"])}</span>'
            '</div></div></div>'
        )
        st.markdown(card, unsafe_allow_html=True)


def _render_scanner(games_df, section_header, status_info, team_logo, h):
    current_date, valid, reset = _reset_stale_state(games_df)
    if reset:
        st.info(f"🔄 Game-total slate changed. Old results were cleared and rebound to the verified {current_date} schedule.")

    verified = _verified_df(games_df)
    if not verified.empty:
        st.caption(f"✅ Verified MLB slate: {len(verified)} game(s) • {current_date} • V17 can only model game IDs on this date.")

    section_header(
        "MLB Game Totals Scanner — V17",
        "Ranks the highest projected scoring environments independently of sportsbook total lines.",
    )
    st.markdown(
        '<div class="ks-note"><b>V17 rule:</b> the scanner does not assume every sportsbook uses the same total. '
        'It ranks games by the model’s projected combined runs. Use the O/U Analyzer to enter the actual total line and calculate Over/Under probability. '
        'H2H is a small capped context layer, not the core engine.</div>',
        unsafe_allow_html=True,
    )

    include_live = st.checkbox("⚠️ Include live games", value=False, key="v17_total_include_live")
    if include_live:
        st.warning("Live mode is only for testing. V17 still uses the pregame model and ignores the current score, inning, outs and in-game bullpen usage.")

    if st.button("🔥 SCAN V17 MLB GAME TOTALS", use_container_width=True, type="primary", key="v17_total_scan"):
        rows = _available_rows(verified, include_live=include_live)
        if not rows:
            st.info("No actionable verified MLB games are available for this date.")
        else:
            results = []
            errors = 0
            bar = st.progress(0, text="Building V17 game-total models...")
            for idx, row in enumerate(rows, 1):
                try:
                    result = _scan_game(row)
                    if int(result["game_pk"]) in valid:
                        results.append(result)
                except Exception:
                    errors += 1
                bar.progress(idx / len(rows), text=f"Modeling game {idx}/{len(rows)}")
            bar.empty()
            results.sort(key=lambda x: x["projected_total"], reverse=True)
            st.session_state["v17_total_slate"] = results
            st.session_state["v17_total_scan_time"] = datetime.now(ET).strftime("%I:%M:%S %p ET").lstrip("0")
            st.session_state["v17_total_errors"] = errors

    results = st.session_state.get("v17_total_slate") or []
    clean = []
    for result in results:
        try:
            if int(result.get("game_pk")) in valid:
                clean.append(result)
        except Exception:
            continue
    if len(clean) != len(results):
        results = clean
        st.session_state["v17_total_slate"] = clean
        st.warning("A stale/cross-date totals result was removed before display.")

    if not results:
        return

    section_header(
        "Selected Slate’s Highest Projected Game Totals",
        "Pure projected scoring environment — not sportsbook value.",
    )
    scan_time = st.session_state.get("v17_total_scan_time")
    if scan_time:
        st.markdown(f'<div class="ks-updated">↻ Last V17 scan {h(scan_time)}</div>', unsafe_allow_html=True)
    errors = int(st.session_state.get("v17_total_errors", 0) or 0)
    if errors:
        st.caption(f"{errors} game(s) could not be fully modeled and were skipped.")

    _render_total_cards(results, status_info, team_logo, h)

    with st.expander("📋 Full projected-total rankings"):
        table = []
        for rank, result in enumerate(results, 1):
            h2h = result.get("h2h") or {}
            table.append(
                {
                    "#": rank,
                    "Game": f'{result["away_team"]} @ {result["home_team"]}',
                    "Projected Total": f'{result["projected_total"]:.2f}',
                    "Core Total": f'{result["core_total"]:.2f}',
                    "History Adj": f'{result["history_adjustment"]:+.2f}',
                    "Away xR": f'{result["away_mean"]:.2f}',
                    "Home xR": f'{result["home_mean"]:.2f}',
                    "H2H L10 Avg": f'{h2h["avg_total_l10"]:.1f}' if h2h.get("avg_total_l10") is not None else "N/A",
                    "H2H L5 Avg": f'{h2h["avg_total_l5"]:.1f}' if h2h.get("avg_total_l5") is not None else "N/A",
                    "Data": f'{result["data_score"]}/9',
                    "Time": result["first_pitch"],
                }
            )
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

    st.divider()
    section_header(
        "Lowest Projected Scoring Environments",
        "Bottom five games on the selected verified slate.",
    )
    low = list(reversed(results[-5:]))
    low_table = pd.DataFrame(
        [
            {
                "Game": f'{r["away_team"]} @ {r["home_team"]}',
                "Projected Total": f'{r["projected_total"]:.2f}',
                "Projected Score": f'{r["away_mean"]:.1f}-{r["home_mean"]:.1f}',
                "Data": r["confidence"],
            }
            for r in low
        ]
    )
    st.dataframe(low_table, use_container_width=True, hide_index=True)


def _game_label(row):
    return f'{row["away_team"]} @ {row["home_team"]} • {row.get("first_pitch_et", "TBD")} • {row.get("status", "Unknown")}'


def _render_analyzer(games_df, section_header, status_info, team_logo, h):
    verified = _verified_df(games_df)
    section_header(
        "MLB Over / Under Analyzer — V17",
        "Enter the sportsbook game-total line after the model projects the scoring environment.",
    )
    st.markdown(
        '<div class="ks-note"><b>Market separation:</b> the sportsbook total is not used to create the projected score. '
        'It is applied afterward to calculate Over, Under and Push probabilities.</div>',
        unsafe_allow_html=True,
    )

    include_live = st.checkbox("⚠️ Include live games", value=False, key="v17_total_analyzer_live")
    rows = _available_rows(verified, include_live=include_live)
    if not rows:
        st.info("No actionable verified MLB games are available for this date.")
        return

    labels = [_game_label(row) for row in rows]
    choice = st.selectbox("Game", labels, key="v17_total_game")
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

    c1, c2 = st.columns(2)
    with c1:
        total_line = st.number_input(
            "Sportsbook game total",
            min_value=4.0,
            max_value=20.0,
            value=8.5,
            step=0.5,
            key="v17_total_line",
        )
    with c2:
        depth = st.selectbox(
            "Simulation size",
            ["Quick — 250K", "Standard — 1M", "Deep — 3M"],
            index=1,
            key="v17_total_depth",
        )
    sim_n = {"Quick — 250K": 250_000, "Standard — 1M": 1_000_000, "Deep — 3M": 3_000_000}[depth]

    if st.button("🔥 RUN V17 TOTAL PROJECTION", use_container_width=True, type="primary", key="v17_total_analyze"):
        with st.spinner("Building scoring model, history context and Monte Carlo total distribution..."):
            try:
                result = _scan_game(game)
                seed = _stable_seed(int(game["game_pk"]), 1700 + int(round(float(total_line) * 10)))
                sim = simulate_total(
                    result["away_mean"],
                    result["home_mean"],
                    float(total_line),
                    sim_n,
                    seed,
                )
                result["simulation"] = sim
                result["total_line"] = float(total_line)
                result["confidence"] = _data_confidence(result["model"], sim)
                st.session_state["v17_total_game_result"] = result
            except Exception as exc:
                st.error(f"V17 could not complete this matchup: {exc}")

    result = st.session_state.get("v17_total_game_result")
    if not result or int(result.get("game_pk", -1)) != int(game["game_pk"]):
        return

    sim = result["simulation"]
    line = float(result["total_line"])
    lean = "OVER" if sim["p_over"] >= sim["p_under"] else "UNDER"
    lean_prob = sim["p_over"] if lean == "OVER" else sim["p_under"]
    lean_odds = sim["fair_over"] if lean == "OVER" else sim["fair_under"]
    badge = _badge_class(result["confidence"])

    section_header(
        "V17 Game Total Projection",
        "Independent projected score + Over/Under settlement simulation.",
    )

    st.markdown(
        '<div class="ks-feature">'
        f'<div class="ks-eyebrow">MODEL LEAN • {h(lean)} {line:g}</div>'
        f'<div class="ks-feature-name">Projected score: {h(result["away_team"])} {result["away_mean"]:.1f} — {h(result["home_team"])} {result["home_mean"]:.1f}</div>'
        f'<div class="ks-feature-prob">{lean_prob * 100:.1f}%</div>'
        f'<div class="ks-feature-meta">Projected total {result["projected_total"]:.2f} • Fair {h(lean_odds)}</div>'
        f'<div style="margin-top:12px"><span class="ks-badge {badge}">DATA {h(result["confidence"])}</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    metrics = [
        ("Over", f'{sim["p_over"] * 100:.1f}%'),
        ("Under", f'{sim["p_under"] * 100:.1f}%'),
        ("Push", f'{sim["p_push"] * 100:.1f}%'),
        ("Expected Total", f'{sim["expected_total"]:.2f}'),
    ]
    for col, (label, value) in zip(cols, metrics):
        with col:
            st.metric(label, value)

    cols2 = st.columns(4)
    metrics2 = [
        ("Median Total", sim["median_total"]),
        ("Mode Total", sim["mode_total"]),
        ("80% Range", f'{sim["p10"]}–{sim["p90"]}'),
        ("Fair O / U", f'{sim["fair_over"]} / {sim["fair_under"]}'),
    ]
    for col, (label, value) in zip(cols2, metrics2):
        with col:
            st.metric(label, value)

    h2h = result.get("h2h") or {}
    away10 = (result.get("model") or {}).get("away_recent")
    home10 = (result.get("model") or {}).get("home_recent")
    with st.expander("📚 H2H + Last 10 / Last 5 scoring history"):
        history_rows = [
            {
                "Team": result["away_team"],
                "Last 10": _fmt_form(away10),
                "Last 5": _fmt_form(result.get("away_recent5")),
            },
            {
                "Team": result["home_team"],
                "Last 10": _fmt_form(home10),
                "Last 5": _fmt_form(result.get("home_recent5")),
            },
        ]
        st.dataframe(pd.DataFrame(history_rows), use_container_width=True, hide_index=True)
        st.caption(
            f'H2H L10 average combined runs: {h2h.get("avg_total_l10"):.2f}' if h2h.get("avg_total_l10") is not None
            else 'No usable H2H total history found.'
        )
        if h2h.get("avg_total_l5") is not None:
            st.caption(f'H2H L5 average combined runs: {h2h["avg_total_l5"]:.2f} • History adjustment: {result["history_adjustment"]:+.2f} runs.')

        games = h2h.get("games") or []
        if games:
            rows_hist = []
            for g in games[:10]:
                total = float(g.get("team_runs", 0) or 0) + float(g.get("opponent_runs", 0) or 0)
                rows_hist.append(
                    {
                        "Date": g.get("date"),
                        "Score": f'{int(g.get("team_runs", 0))}-{int(g.get("opponent_runs", 0))}',
                        "Combined Runs": int(total),
                        "Location": str(g.get("location", "")).title(),
                    }
                )
            st.dataframe(pd.DataFrame(rows_hist), use_container_width=True, hide_index=True)

    st.caption(
        f'Simulations {sim["simulations"]:,} • Seed {sim["seed"]} • '
        f'MC SE {sim["mc_se"] * 100:.3f} pts • Max batch spread {sim["batch_spread"] * 100:.2f} pts • '
        f'Convergence {"PASS" if sim["converged"] else "CHECK"} • Data {result["data_score"]}/9.'
    )


def render_totals_hub(games_df, section_header, status_info, team_logo, h):
    scanner_tab, analyzer_tab = st.tabs(["🔥 Totals Scanner", "🔎 O/U Analyzer"])
    with scanner_tab:
        _render_scanner(games_df, section_header, status_info, team_logo, h)
    with analyzer_tab:
        _render_analyzer(games_df, section_header, status_info, team_logo, h)
