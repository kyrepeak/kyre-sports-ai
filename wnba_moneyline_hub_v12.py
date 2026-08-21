"""WNBA Moneyline V1.2 — Step 5 independent win probability.

Preserves Moneyline V1.1 Steps 1-4 and adds Step 5 only.

Step 5 uses verified, date-cut team data to create a market-independent expected
score/margin, then converts that margin into an analytical win probability using
date-cut empirical team/league margin dispersion. The exact Step-4 sportsbook
Moneyline is an upstream freshness/coverage gate only; sportsbook prices are NOT
accepted by the Step-5 probability engine and cannot move the projected mean,
variance or win probability.

Inputs to Step 5:
- season scoring offense/defense;
- L10 scoring offense/defense;
- road/home venue splits;
- recent pace + ORTG/DRTG when sufficiently sampled;
- verified exact-day availability / OUT-player impact;
- date-cut empirical team/league game-margin variance.

H2H remains descriptive only. No no-vig comparison, fair odds, Monte Carlo,
final grading/ranking or Daily Picks payload is produced in V1.2.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_moneyline_hub_v11 as prior
import wnba_spread_projection_v14 as score_model
import wnba_spread_probability_v15 as uncertainty

MODEL_VERSION = "WNBA MONEYLINE V1.2 • INDEPENDENT WIN PROBABILITY"
ET = prior.ET
foundation = prior.foundation
clock = prior.clock
spread_current = prior.spread_current


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _fmt(value, digits=1):
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}"


def _fmt_pct(value, digits=1):
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{100.0 * x:.{digits}f}%"


def _independent_win_board(day_str: str, pregame: pd.DataFrame, contexts: dict):
    """Build one market-independent win distribution per pregame game."""
    empty_meta = {
        "state": "N/A",
        "games": int(len(pregame) if isinstance(pregame, pd.DataFrame) else 0),
        "covered_games": 0,
        "rows": 0,
        "ready": 0,
        "monitor": 0,
        "blocked": 0,
        "sportsbook_inputs": 0,
        "model_ready": False,
        "league_margin_games": 0,
    }
    if pregame is None or pregame.empty:
        return pd.DataFrame(), empty_meta

    projected, proj_meta = score_model.project_slate(day_str, pregame, contexts)
    if projected is None or projected.empty:
        meta = dict(empty_meta)
        meta.update({"state": "CHECK", "blocked": int(len(pregame))})
        return pd.DataFrame(), meta

    history = score_model._history_before(day_str)
    league_vals = uncertainty._league_margin_sample(history)
    league_var = uncertainty._sample_var(league_vals)
    if not np.isfinite(league_var) or league_var <= 0:
        meta = dict(empty_meta)
        meta.update({
            "state": "CHECK",
            "blocked": int(len(pregame)),
            "league_margin_games": int(len(league_vals)),
        })
        return pd.DataFrame(), meta

    games = {str(r.get("game_id") or ""): r for _, r in pregame.iterrows()}
    projs = {str(r.get("game_id") or ""): r for _, r in projected.iterrows()}
    rows = []
    covered_ids = set()

    for gid, game in games.items():
        proj = projs.get(gid)
        if proj is None:
            continue
        proj_state = str(proj.get("state") or "BLOCKED").upper()
        if proj_state == "BLOCKED":
            continue

        mean_home = _num(proj.get("home_margin"), np.nan)
        sigma_info = uncertainty._game_sigma(day_str, game, proj, history, league_var)
        sigma = _num(sigma_info.get("sigma"), np.nan)
        if not np.isfinite(mean_home) or not np.isfinite(sigma) or sigma <= 0:
            continue

        # WNBA games are resolved to a winner. Using a continuous final-margin
        # distribution at the zero threshold yields complementary win probabilities
        # with no artificial push/tie mass.
        away_win = uncertainty._norm_cdf(0.0, mean_home, sigma)
        home_win = 1.0 - away_win if np.isfinite(away_win) else np.nan
        if not np.isfinite(away_win) or not np.isfinite(home_win):
            continue
        away_win = float(np.clip(away_win, 0.0, 1.0))
        home_win = float(np.clip(home_win, 0.0, 1.0))
        total = away_win + home_win
        if total <= 0:
            continue
        away_win /= total
        home_win /= total

        short_sample = (
            int(sigma_info.get("away_n", 0) or 0) < uncertainty.MIN_TEAM_MARGIN_GAMES
            or int(sigma_info.get("home_n", 0) or 0) < uncertainty.MIN_TEAM_MARGIN_GAMES
        )
        state = "MONITOR" if proj_state == "MONITOR" or short_sample else "READY"
        reasons = []
        if proj_state == "MONITOR":
            reasons.append(str(proj.get("reason") or "upstream projection monitor"))
        if short_sample:
            reasons.append("short team-margin sample; league shrinkage active")

        rows.append({
            "game_id": gid,
            "away_team": str(game.get("away_team") or proj.get("away_team") or "Away"),
            "home_team": str(game.get("home_team") or proj.get("home_team") or "Home"),
            "first_tip_et": str(game.get("first_tip_et") or proj.get("first_tip_et") or "—"),
            "away_score": _num(proj.get("away_score"), np.nan),
            "home_score": _num(proj.get("home_score"), np.nan),
            "projected_home_margin": float(mean_home),
            "away_win_prob": float(away_win),
            "home_win_prob": float(home_win),
            "sigma": float(sigma),
            "margin_low80": float(mean_home - 1.2815515655 * sigma),
            "margin_high80": float(mean_home + 1.2815515655 * sigma),
            "components": str(proj.get("components") or ""),
            "component_count": int(_num(proj.get("component_count"), 0) or 0),
            "season_away": _num(proj.get("season_away"), np.nan),
            "season_home": _num(proj.get("season_home"), np.nan),
            "recent_away": _num(proj.get("recent_away"), np.nan),
            "recent_home": _num(proj.get("recent_home"), np.nan),
            "venue_away": _num(proj.get("venue_away"), np.nan),
            "venue_home": _num(proj.get("venue_home"), np.nan),
            "advanced_away": _num(proj.get("advanced_away"), np.nan),
            "advanced_home": _num(proj.get("advanced_home"), np.nan),
            "away_road_gp": int(_num(proj.get("away_road_gp"), 0) or 0),
            "home_home_gp": int(_num(proj.get("home_home_gp"), 0) or 0),
            "away_out_impact": _num(proj.get("away_out_impact"), 0.0),
            "home_out_impact": _num(proj.get("home_out_impact"), 0.0),
            "hard_out": int(_num(proj.get("hard_out"), 0) or 0),
            "uncertain": int(_num(proj.get("uncertain"), 0) or 0),
            "away_margin_games": int(sigma_info.get("away_n", 0) or 0),
            "home_margin_games": int(sigma_info.get("home_n", 0) or 0),
            "league_margin_games": int(len(league_vals)),
            "sigma_source": str(sigma_info.get("source") or ""),
            "component_margin_sd": _num(sigma_info.get("component_sd"), np.nan),
            "projection_state": proj_state,
            "state": state,
            "reason": "; ".join(r for r in reasons if r),
            "sportsbook_inputs": 0,
            "h2h_weight": 0.0,
            "probability_method": "independent projected margin + date-cut empirical sigma; zero-margin win threshold",
        })
        covered_ids.add(gid)

    frame = pd.DataFrame(rows)
    game_ids = set(games)
    states = frame.get("state", pd.Series(dtype=object)).astype(str).str.upper() if not frame.empty else pd.Series(dtype=object)
    ready = int(states.eq("READY").sum()) if not frame.empty else 0
    monitor = int(states.eq("MONITOR").sum()) if not frame.empty else 0
    blocked = int(len(game_ids - covered_ids))
    state = "READY" if game_ids and game_ids.issubset(covered_ids) else "CHECK"
    meta = {
        "state": state,
        "games": int(len(game_ids)),
        "covered_games": int(len(game_ids & covered_ids)),
        "rows": int(len(frame)),
        "ready": ready,
        "monitor": monitor,
        "blocked": blocked,
        "sportsbook_inputs": 0,
        "model_ready": bool(state == "READY"),
        "projection_state": str((proj_meta or {}).get("state") or "CHECK"),
        "league_margin_games": int(len(league_vals)),
        "league_sigma": float(np.sqrt(league_var)),
    }
    return frame, meta


def _render_step5(day_str: str, pregame: pd.DataFrame, contexts: dict, market_ready: bool):
    st.markdown("### 🧠 Step 5 — Independent Win Probability")
    st.caption(
        "Verified team data only • season + L10 scoring matchup + road/home splits + recent pace/efficiency + "
        "exact-day availability + date-cut empirical margin variance. H2H weight = 0%. Sportsbook prices are an upstream gate only and model input = ZERO."
    )

    if pregame is None or pregame.empty:
        st.info("ℹ️ STEP 5 NOT APPLICABLE • no clock-safe pregame games remain.")
        return pd.DataFrame(), {
            "state": "N/A", "games": 0, "covered_games": 0, "rows": 0,
            "ready": 0, "monitor": 0, "blocked": 0,
            "sportsbook_inputs": 0, "model_ready": False,
        }
    if not market_ready:
        st.warning(
            "🔒 STEP 5 LOCKED • exact current sportsbook Moneyline coverage must pass Step 4 first. "
            "Those prices still do not enter the win-probability math."
        )
        return pd.DataFrame(), {
            "state": "LOCKED", "games": int(len(pregame)), "covered_games": 0,
            "rows": 0, "ready": 0, "monitor": 0, "blocked": 0,
            "sportsbook_inputs": 0, "model_ready": False,
        }

    with st.spinner("🧠 Building market-independent WNBA win probabilities…"):
        board, meta = _independent_win_board(day_str, pregame, contexts)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Game coverage", f"{int(meta.get('covered_games', 0))}/{int(meta.get('games', 0))}")
    c2.metric("READY", int(meta.get("ready", 0)))
    c3.metric("MONITOR", int(meta.get("monitor", 0)))
    c4.metric("Sportsbook inputs", int(meta.get("sportsbook_inputs", 0)))

    model_ready = bool(meta.get("model_ready", False))
    if model_ready:
        st.success(
            "✅ STEP 5 PASSED • every pregame game has an independent win distribution; sportsbook Moneyline prices did not change the projected margin, uncertainty or probability."
        )
        if int(meta.get("monitor", 0)):
            st.info(
                f"🟦 {int(meta.get('monitor', 0))} game(s) are MONITOR because of short-sample or availability/data-layer uncertainty. "
                "The flag must carry forward to later grading."
            )
    else:
        st.warning(
            "⚠️ STEP 5 CHECK • at least one pregame game cannot produce a trustworthy independent win distribution. Step 6 remains locked."
        )

    if board is not None and not board.empty:
        show = board.copy()
        show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
        show["Projected score"] = show.apply(
            lambda r: f"{r.get('away_team')} {_fmt(r.get('away_score'))} — {r.get('home_team')} {_fmt(r.get('home_score'))}", axis=1
        )
        show["Projected margin"] = show.apply(
            lambda r: (
                "Even"
                if abs(_num(r.get("projected_home_margin"), 0.0)) < 0.05
                else (
                    f"{r.get('home_team')} by {_fmt(r.get('projected_home_margin'))}"
                    if _num(r.get("projected_home_margin"), 0.0) > 0
                    else f"{r.get('away_team')} by {_fmt(abs(_num(r.get('projected_home_margin'), 0.0)))}"
                )
            ),
            axis=1,
        )
        show["Away win"] = show["away_win_prob"].map(_fmt_pct)
        show["Home win"] = show["home_win_prob"].map(_fmt_pct)
        show["Margin σ"] = show["sigma"].map(lambda x: _fmt(x, 1))
        st.dataframe(
            show[[
                "Game", "first_tip_et", "Projected score", "Projected margin",
                "Away win", "Home win", "Margin σ", "state",
            ]].rename(columns={"first_tip_et": "Tip ET", "state": "State"}),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("🔬 Step 5 win-probability audit — model components", expanded=False):
            audit = show.copy()
            audit["Season matchup"] = audit.apply(
                lambda r: f"{_fmt(r.get('season_away'))} / {_fmt(r.get('season_home'))}", axis=1
            )
            audit["L10 matchup"] = audit.apply(
                lambda r: f"{_fmt(r.get('recent_away'))} / {_fmt(r.get('recent_home'))}", axis=1
            )
            audit["Venue matchup"] = audit.apply(
                lambda r: f"{_fmt(r.get('venue_away'))} / {_fmt(r.get('venue_home'))}", axis=1
            )
            audit["Advanced matchup"] = audit.apply(
                lambda r: f"{_fmt(r.get('advanced_away'))} / {_fmt(r.get('advanced_home'))}", axis=1
            )
            audit["Venue samples"] = audit.apply(
                lambda r: f"road {int(r.get('away_road_gp', 0) or 0)} / home {int(r.get('home_home_gp', 0) or 0)}", axis=1
            )
            audit["OUT / uncertain"] = audit.apply(
                lambda r: f"{int(r.get('hard_out', 0) or 0)} / {int(r.get('uncertain', 0) or 0)}", axis=1
            )
            audit["Margin sample"] = audit.apply(
                lambda r: f"away {int(r.get('away_margin_games', 0) or 0)} / home {int(r.get('home_margin_games', 0) or 0)} / league {int(r.get('league_margin_games', 0) or 0)}", axis=1
            )
            audit["Sportsbook inputs"] = audit.get("sportsbook_inputs", 0)
            audit["H2H weight"] = "0%"
            st.dataframe(
                audit[[
                    "Game", "Season matchup", "L10 matchup", "Venue matchup",
                    "Advanced matchup", "Venue samples", "OUT / uncertain",
                    "Margin sample", "Sportsbook inputs", "H2H weight", "State",
                ]],
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "The exact Step-4 Moneyline is not passed into this engine. Step 5 uses the same verified team-information family as the independent spread-score model, "
                "then estimates win probability from date-cut empirical game-margin uncertainty. No-vig and fair-odds comparison remains Step 6."
            )

        st.session_state["wnba_moneyline_v12_win_board"] = board.copy()
        st.session_state["wnba_moneyline_v12_win_date"] = str(day_str)
        st.session_state["wnba_moneyline_v12_win_meta"] = dict(meta)

    return board, {**dict(meta), "model_ready": model_ready}


def render_wnba_moneyline_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 💰 WNBA Moneyline Command Center")
    st.caption(
        "V1.2 • verified slate → clock-safe pregame guard → team context → exact-day availability → exact sportsbook Moneyline → "
        "independent win probability. No-vig/fair odds and Monte Carlo remain OFF."
    )

    default_day = st.session_state.get("wnba_moneyline_v1_date") or pd.Timestamp.now(tz=ET).date()
    selected = st.date_input(
        "Moneyline slate date",
        value=pd.to_datetime(default_day).date(),
        key="wnba_moneyline_v1_date_picker",
    )
    st.session_state["wnba_moneyline_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    now_et = pd.Timestamp.now(tz=ET)

    with st.spinner("📅 Verifying WNBA Moneyline slate + clock-safe pregame eligibility…"):
        schedule = foundation._schedule(day_str)
        pregame = clock._pregame_schedule(schedule, now_et=now_et)
        excluded = clock._excluded_schedule(schedule, now_et=now_et)

    teams = 0
    if not schedule.empty:
        team_ids = set()
        for col in ("away_team_id", "home_team_id"):
            if col in schedule.columns:
                team_ids.update(pd.to_numeric(schedule[col], errors="coerce").dropna().astype(int).tolist())
        teams = len(team_ids)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", int(len(schedule)))
    c2.metric("Pregame eligible", int(len(pregame)))
    c3.metric("Excluded / locked", int(len(excluded)))
    c4.metric("Model state", "STEP 5")
    st.caption(f"Pregame eligibility clock • {now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')}")

    if schedule.empty:
        st.warning("No verified WNBA games were returned for this Eastern-date slate. Nothing is projected or fabricated.")
        return

    st.success(f"✅ STEP 1 PASSED • verified WNBA slate loaded for {day_str}.")
    if len(pregame):
        st.success(f"✅ PREGAME ELIGIBILITY PASSED • {len(pregame)} game(s) are still before scheduled tip and provider-safe.")
    else:
        st.info("ℹ️ No games on this slate remain pregame-eligible. Passed-tip/live/final/uncertain-tip games are locked out.")

    if not excluded.empty:
        with st.expander("🚫 Games excluded from Moneyline pregame production", expanded=False):
            cols = [c for c in [
                "away_team", "home_team", "first_tip_et", "scheduled_tip_guard_et",
                "status", "status_text", "exclusion_reason",
            ] if c in excluded.columns]
            st.dataframe(excluded[cols] if cols else excluded, use_container_width=True, hide_index=True)

    with st.spinner("📊 Building verified team form + matchup context…"):
        try:
            contexts, cdiag = foundation.context.slate_context(day_str)
        except Exception as exc:
            contexts, cdiag = {}, {"state": "CHECK", "reason": type(exc).__name__}

    context_state = str(cdiag.get("state") or "CHECK").upper()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Context state", context_state)
    d2.metric("Records verified", f"{int(cdiag.get('records_verified', 0) or 0)}/{int(cdiag.get('teams', teams) or teams)}")
    d3.metric("Advanced teams", int(cdiag.get("advanced_teams", 0) or 0))
    d4.metric("H2H samples", int(cdiag.get("h2h_samples", 0) or 0))
    if context_state == "VERIFIED":
        st.success("✅ STEP 2 PASSED • team records/recent form are verified; advanced pace/ratings are used only where real samples exist.")
    else:
        st.warning("⚠️ STEP 2 CHECK • some team context is incomplete. Missing advanced fields remain neutral/missing; nothing is invented.")

    with st.spinner("🩺 Verifying exact-day current team availability for pregame-eligible games…"):
        av = spread_current._availability_snapshot_exact_day(day_str, pregame)
    av_map = {str(r.get("game_id") or ""): r.to_dict() for _, r in av.iterrows()} if not av.empty else {}

    covered = int(pd.to_numeric(av.get("covered_teams", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0
    expected_coverage = int(2 * len(pregame))
    unverified = int(pd.to_numeric(av.get("unverified", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Availability coverage", f"{covered}/{expected_coverage}" if expected_coverage else "0/0")
    a2.metric("Hard OUT", int(pd.to_numeric(av.get("hard_out", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0)
    a3.metric("Status uncertain", int(pd.to_numeric(av.get("uncertain", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0)
    a4.metric("Unverified players", unverified)

    availability_ready = bool(expected_coverage > 0 and covered == expected_coverage and unverified == 0)
    if availability_ready:
        st.success("✅ STEP 3 PASSED • current availability coverage is complete for every pregame-eligible game.")
    elif expected_coverage == 0:
        st.info("ℹ️ STEP 3 NOT APPLICABLE • there are no remaining pregame-eligible games on this slate.")
    else:
        st.warning("⚠️ STEP 3 CHECK • availability is not fully verified for every pregame-eligible game. Future Moneyline production remains locked.")

    st.markdown("### 🧩 Pregame-Eligible Moneyline Foundation")
    if pregame.empty:
        st.info("No pregame-eligible games remain to display.")
    else:
        for _, game in pregame.iterrows():
            prior.prior._render_game_context(game, contexts, av_map)

    foundation_ready = bool(len(pregame) and context_state == "VERIFIED" and availability_ready)
    ready_ml, market_meta = prior._render_step4(day_str, pregame, foundation_ready)
    market_ready = bool(market_meta.get("market_ready"))

    win_board, step5 = _render_step5(day_str, pregame, contexts, market_ready)
    win_ready = bool(step5.get("model_ready", False))

    st.session_state["wnba_moneyline_v1_day"] = day_str
    st.session_state["wnba_moneyline_v1_foundation_ready"] = foundation_ready
    st.session_state["wnba_moneyline_v1_schedule"] = schedule.to_dict("records")
    st.session_state["wnba_moneyline_v1_pregame"] = pregame.to_dict("records")
    st.session_state["wnba_moneyline_v1_availability"] = av.to_dict("records") if not av.empty else []
    st.session_state["wnba_moneyline_v11_market_ready"] = market_ready
    st.session_state["wnba_moneyline_v11_market_rows"] = ready_ml.to_dict("records") if not ready_ml.empty else []
    st.session_state["wnba_moneyline_v11_market_meta"] = market_meta
    st.session_state["wnba_moneyline_v12_model_ready"] = win_ready

    st.markdown("### 🔒 Moneyline Production Locks")
    locks = pd.DataFrame([
        {"Layer": "Verified slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Clock-safe pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Team context", "State": "READY" if context_state == "VERIFIED" else "CHECK"},
        {"Layer": "Current availability", "State": "READY" if availability_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Exact sportsbook moneyline", "State": "READY" if market_ready else ("CHECK" if foundation_ready else "LOCKED")},
        {"Layer": "Independent win probability", "State": "READY" if win_ready else ("CHECK" if market_ready else "LOCKED")},
        {"Layer": "No-vig / fair odds", "State": "NEXT" if win_ready else "LOCKED"},
        {"Layer": "5M Monte Carlo", "State": "OFF"},
        {"Layer": "Final Moneyline grading", "State": "OFF"},
        {"Layer": "Daily Picks connector", "State": "OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)
    st.info(
        "V1.2 makes no Moneyline pick. Step 5 creates an independent win probability with sportsbook input = 0. "
        "No-vig market comparison and model fair odds are the next layer."
    )


__all__ = [
    "MODEL_VERSION",
    "render_wnba_moneyline_hub",
    "_independent_win_board",
    "_render_step5",
]
