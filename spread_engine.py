from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import requests
import streamlit as st

from engine import (
    ET,
    MLB_API,
    actionable,
    bullpen,
    clamp,
    env_adj,
    environment,
    lineup_snapshot,
    odds,
    pitcher_stats,
    season,
    sf,
)


LEAGUE_RUNS_PER_TEAM = 4.40


def _stat_block(payload):
    groups = payload.get("stats", []) if isinstance(payload, dict) else []
    if not groups:
        return {}
    splits = groups[0].get("splits", [])
    if not splits:
        return {}
    return splits[0].get("stat", {}) or {}


@st.cache_data(ttl=900, show_spinner=False)
def team_season_profile(team_id):
    """Current-season team offense + pitching profile from MLB Stats API."""
    team_id = int(team_id)
    year = season()

    hitting = requests.get(
        f"{MLB_API}/teams/{team_id}/stats",
        params={"stats": "season", "group": "hitting", "season": year},
        timeout=18,
    )
    hitting.raise_for_status()

    pitching = requests.get(
        f"{MLB_API}/teams/{team_id}/stats",
        params={"stats": "season", "group": "pitching", "season": year},
        timeout=18,
    )
    pitching.raise_for_status()

    h = _stat_block(hitting.json())
    p = _stat_block(pitching.json())

    games = max(int(sf(h.get("gamesPlayed"), 0) or 0), 1)
    runs = sf(h.get("runs"), 0) or 0
    runs_allowed = sf(p.get("runs"))
    if runs_allowed is None:
        # Earned runs are not identical to runs allowed. This fallback is clearly
        # treated as an approximation and is only used when MLB omits total runs.
        er = sf(p.get("earnedRuns"), 0) or 0
        runs_allowed = er * 1.08

    p_games = max(int(sf(p.get("gamesPlayed"), games) or games), 1)

    return {
        "team_id": team_id,
        "season": year,
        "games": games,
        "runs": runs,
        "runs_per_game": runs / games,
        "avg": sf(h.get("avg")),
        "obp": sf(h.get("obp")),
        "slg": sf(h.get("slg")),
        "ops": sf(h.get("ops")),
        "home_runs": sf(h.get("homeRuns"), 0) or 0,
        "walks": sf(h.get("baseOnBalls"), 0) or 0,
        "strikeouts": sf(h.get("strikeOuts"), 0) or 0,
        "runs_allowed": runs_allowed,
        "runs_allowed_per_game": runs_allowed / p_games,
        "era": sf(p.get("era")),
        "whip": sf(p.get("whip")),
        "pitching_games": p_games,
    }


@st.cache_data(ttl=900, show_spinner=False)
def recent_team_form(team_id, n=10):
    """Last completed games, using official schedule scores."""
    team_id = int(team_id)
    today = datetime.now(ET).date()
    start = today - timedelta(days=32)

    r = requests.get(
        f"{MLB_API}/schedule",
        params={
            "sportId": 1,
            "teamId": team_id,
            "startDate": start.isoformat(),
            "endDate": today.isoformat(),
        },
        timeout=18,
    )
    r.raise_for_status()

    rows = []
    for block in r.json().get("dates", []):
        for game in block.get("games", []):
            status = str(game.get("status", {}).get("detailedState", ""))
            if "final" not in status.lower() and "game over" not in status.lower():
                continue

            away = game.get("teams", {}).get("away", {})
            home = game.get("teams", {}).get("home", {})
            away_id = (away.get("team") or {}).get("id")
            home_id = (home.get("team") or {}).get("id")
            away_score = sf(away.get("score"))
            home_score = sf(home.get("score"))
            if away_score is None or home_score is None:
                continue

            if int(away_id or 0) == team_id:
                rf, ra = away_score, home_score
            elif int(home_id or 0) == team_id:
                rf, ra = home_score, away_score
            else:
                continue

            rows.append(
                {
                    "game_pk": game.get("gamePk"),
                    "date": game.get("gameDate"),
                    "runs_for": float(rf),
                    "runs_against": float(ra),
                }
            )

    rows = rows[-int(n):]
    if not rows:
        return None

    rf = np.array([x["runs_for"] for x in rows], dtype=float)
    ra = np.array([x["runs_against"] for x in rows], dtype=float)
    return {
        "games": len(rows),
        "runs_per_game": float(rf.mean()),
        "runs_allowed_per_game": float(ra.mean()),
        "run_diff_per_game": float((rf - ra).mean()),
        "win_pct": float(np.mean(rf > ra)),
    }


def _lineup_profile(game_pk, side, team_ops):
    try:
        snap = lineup_snapshot(int(game_pk)).get(side, [])
    except Exception:
        return None
    if not snap:
        return None

    ops_values = [sf(x.get("ops")) for x in snap]
    ops_values = [x for x in ops_values if x is not None and x > 0]
    if not ops_values:
        return {"confirmed": True, "hitters": len(snap), "avg_ops": None, "multiplier": 1.0}

    avg_ops = float(np.mean(ops_values))
    if team_ops and team_ops > 0:
        raw = avg_ops / team_ops - 1
        multiplier = 1 + clamp(raw * 0.45, -0.045, 0.045)
    else:
        multiplier = 1.0

    return {
        "confirmed": True,
        "hitters": len(snap),
        "avg_ops": avg_ops,
        "multiplier": multiplier,
    }


def _pitcher_run_multiplier(p):
    if not p:
        return 1.0, 0.0, "Unknown"

    era = sf(p.get("era"))
    whip = sf(p.get("whip"))
    k9 = sf(p.get("k9"))
    innings = sf(p.get("true_innings"), 0) or 0

    comps = []
    if era is not None:
        comps.append(0.48 * ((4.20 - era) / 4.20))
    if whip is not None:
        comps.append(0.34 * ((1.30 - whip) / 1.30))
    if k9 is not None:
        comps.append(0.18 * ((k9 - 8.5) / 8.5))

    if not comps:
        return 1.0, 0.0, "Unknown"

    reliability = innings / (innings + 55) if innings > 0 else 0.0
    quality = sum(comps) * reliability
    # Positive quality means a tougher pitcher, therefore fewer expected runs.
    adjustment = clamp(-0.22 * quality, -0.105, 0.105)
    mult = 1 + adjustment

    grade = (
        "Very Tough" if adjustment <= -0.065
        else "Tough" if adjustment <= -0.025
        else "Very Favorable" if adjustment >= 0.065
        else "Favorable" if adjustment >= 0.025
        else "Near Neutral"
    )
    return mult, reliability, grade


def _bullpen_run_multiplier(bp):
    if not bp:
        return 1.0, 0.0, "Unknown"

    era = sf(bp.get("era"))
    whip = sf(bp.get("whip"))
    k9 = sf(bp.get("k9"))
    innings = sf(bp.get("innings"), 0) or 0

    comps = []
    if era is not None:
        comps.append(0.45 * ((4.20 - era) / 4.20))
    if whip is not None:
        comps.append(0.37 * ((1.30 - whip) / 1.30))
    if k9 is not None:
        comps.append(0.18 * ((k9 - 8.5) / 8.5))

    if not comps:
        return 1.0, 0.0, "Unknown"

    reliability = innings / (innings + 120) if innings > 0 else 0.0
    quality = sum(comps) * reliability
    adjustment = clamp(-0.16 * quality, -0.075, 0.075)
    mult = 1 + adjustment

    grade = (
        "Very Tough" if adjustment <= -0.045
        else "Tough" if adjustment <= -0.018
        else "Very Favorable" if adjustment >= 0.045
        else "Favorable" if adjustment >= 0.018
        else "Near Neutral"
    )
    return mult, reliability, grade


def _starter_share(p):
    if not p or not p.get("games_started"):
        return 0.58, 5.2
    ip_per_start = (sf(p.get("true_innings"), 0) or 0) / max(int(p.get("games_started") or 1), 1)
    ip_per_start = clamp(ip_per_start, 4.2, 6.5)
    return clamp(ip_per_start / 9.0, 0.47, 0.72), ip_per_start


def _base_offense(profile, recent):
    games = max(profile.get("games", 0), 0)
    season_rpg = profile.get("runs_per_game", LEAGUE_RUNS_PER_TEAM)
    rel = games / (games + 28) if games else 0
    base = LEAGUE_RUNS_PER_TEAM * (1 - rel) + season_rpg * rel

    recent_weight = 0.0
    if recent and recent.get("games"):
        recent_weight = clamp(0.18 * recent["games"] / (recent["games"] + 12), 0, 0.10)
        base = base * (1 - recent_weight) + recent["runs_per_game"] * recent_weight

    return base, rel, recent_weight


def _team_expected_runs(
    offense,
    recent,
    opponent_pitching,
    starter,
    opponent_bullpen,
    lineup,
    env_model,
    is_home,
):
    base, season_rel, recent_weight = _base_offense(offense, recent)

    # Opponent season run prevention adds a modest context layer. It is kept
    # small because starter and bullpen quality are modeled separately below.
    opp_ra = opponent_pitching.get("runs_allowed_per_game") if opponent_pitching else None
    defense_mult = 1.0
    if opp_ra is not None and opp_ra > 0:
        defense_mult = clamp((opp_ra / LEAGUE_RUNS_PER_TEAM) ** 0.22, 0.92, 1.08)

    starter_mult, starter_rel, starter_grade = _pitcher_run_multiplier(starter)
    bullpen_mult, bullpen_rel, bullpen_grade = _bullpen_run_multiplier(opponent_bullpen)
    starter_share, starter_ip = _starter_share(starter)
    pitching_mult = starter_mult * starter_share + bullpen_mult * (1 - starter_share)

    lineup_mult = lineup.get("multiplier", 1.0) if lineup else 1.0
    environment_mult = 1 + clamp(env_model.get("total_adjustment", 0) * 0.85, -0.04, 0.04)
    venue_mult = 1.020 if is_home else 0.985

    expected = base * defense_mult * pitching_mult * lineup_mult * environment_mult * venue_mult
    expected = clamp(expected, 1.75, 7.75)

    return {
        "expected_runs": expected,
        "base_runs": base,
        "season_reliability": season_rel,
        "recent_weight": recent_weight,
        "defense_multiplier": defense_mult,
        "starter_multiplier": starter_mult,
        "starter_reliability": starter_rel,
        "starter_grade": starter_grade,
        "starter_share": starter_share,
        "starter_ip": starter_ip,
        "bullpen_multiplier": bullpen_mult,
        "bullpen_reliability": bullpen_rel,
        "bullpen_grade": bullpen_grade,
        "lineup_multiplier": lineup_mult,
        "environment_multiplier": environment_mult,
        "venue_multiplier": venue_mult,
    }


@st.cache_data(ttl=300, show_spinner=False)
def build_game_model(game_pk, away_team_id, home_team_id, away_pitcher_id, home_pitcher_id, venue_name):
    away = team_season_profile(int(away_team_id))
    home = team_season_profile(int(home_team_id))

    try:
        away_recent = recent_team_form(int(away_team_id), 10)
    except Exception:
        away_recent = None
    try:
        home_recent = recent_team_form(int(home_team_id), 10)
    except Exception:
        home_recent = None

    away_sp = None
    home_sp = None
    if away_pitcher_id is not None and not pd.isna(away_pitcher_id):
        try:
            away_sp = pitcher_stats(int(away_pitcher_id))
        except Exception:
            pass
    if home_pitcher_id is not None and not pd.isna(home_pitcher_id):
        try:
            home_sp = pitcher_stats(int(home_pitcher_id))
        except Exception:
            pass

    try:
        away_bp = bullpen(int(away_team_id), int(away_pitcher_id) if away_pitcher_id is not None and not pd.isna(away_pitcher_id) else None)
    except Exception:
        away_bp = None
    try:
        home_bp = bullpen(int(home_team_id), int(home_pitcher_id) if home_pitcher_id is not None and not pd.isna(home_pitcher_id) else None)
    except Exception:
        home_bp = None

    try:
        env = environment(int(game_pk))
    except Exception:
        env = None
    env_model = env_adj(env, venue_name)

    away_lineup = _lineup_profile(int(game_pk), "away", away.get("ops"))
    home_lineup = _lineup_profile(int(game_pk), "home", home.get("ops"))

    away_model = _team_expected_runs(
        away,
        away_recent,
        home,
        home_sp,
        home_bp,
        away_lineup,
        env_model,
        False,
    )
    home_model = _team_expected_runs(
        home,
        home_recent,
        away,
        away_sp,
        away_bp,
        home_lineup,
        env_model,
        True,
    )

    data_layers = {
        "away_season": bool(away),
        "home_season": bool(home),
        "away_recent": bool(away_recent),
        "home_recent": bool(home_recent),
        "away_starter": bool(away_sp),
        "home_starter": bool(home_sp),
        "bullpens": bool(away_bp and home_bp),
        "environment": bool(env),
        "lineups": bool(away_lineup and home_lineup),
    }
    data_score = sum(data_layers.values())

    return {
        "away": away,
        "home": home,
        "away_recent": away_recent,
        "home_recent": home_recent,
        "away_starter": away_sp,
        "home_starter": home_sp,
        "away_bullpen": away_bp,
        "home_bullpen": home_bp,
        "environment": env_model,
        "away_lineup": away_lineup,
        "home_lineup": home_lineup,
        "away_model": away_model,
        "home_model": home_model,
        "data_score": data_score,
        "data_layers": data_layers,
    }


def _stable_seed(game_pk, salt=1500):
    day = int(datetime.now(ET).strftime("%Y%m%d"))
    return int((int(game_pk) * 1009 + day + int(salt)) % (2**32 - 1))


@st.cache_data(ttl=600, show_spinner=False)
def simulate_run_line(away_mean, home_mean, n, seed, selected_side, line):
    """Gamma-Poisson game simulation with a small shared run-environment shock."""
    n = int(n)
    rng = np.random.default_rng(int(seed))
    batch_size = 250_000
    done = 0

    cover_count = push_count = win_count = 0
    one_run_count = blowout_count = 0
    away_sum = home_sum = 0.0
    margin_counts = {}
    batch_cover = []

    while done < n:
        k = min(batch_size, n - done)

        # Shared factor gives both offenses a little same-game correlation.
        shared = rng.lognormal(mean=-0.5 * 0.10**2, sigma=0.10, size=k)

        # Gamma-Poisson mixture adds realistic over-dispersion compared with a
        # pure Poisson model, which is usually too narrow for baseball scoring.
        dispersion = 6.5
        away_lambda = rng.gamma(dispersion, away_mean / dispersion, size=k) * shared
        home_lambda = rng.gamma(dispersion, home_mean / dispersion, size=k) * shared

        away_runs = rng.poisson(away_lambda).astype(np.int16)
        home_runs = rng.poisson(home_lambda).astype(np.int16)

        # MLB games do not normally finish tied. Resolve simulated regulation
        # ties as a one-run extra-inning result, weighted by the two offenses.
        tied = away_runs == home_runs
        if np.any(tied):
            home_extra_p = home_mean / max(home_mean + away_mean, 1e-6)
            home_wins_tie = rng.random(int(tied.sum())) < home_extra_p
            idx = np.flatnonzero(tied)
            home_runs[idx[home_wins_tie]] += 1
            away_runs[idx[~home_wins_tie]] += 1

        away_sum += float(away_runs.sum())
        home_sum += float(home_runs.sum())

        raw_margin = home_runs - away_runs
        selected_margin = raw_margin if selected_side == "home" else -raw_margin
        settle = selected_margin + float(line)

        covers = settle > 1e-9
        pushes = np.abs(settle) <= 1e-9
        wins = selected_margin > 0

        cover_count += int(covers.sum())
        push_count += int(pushes.sum())
        win_count += int(wins.sum())
        one_run_count += int((np.abs(raw_margin) == 1).sum())
        blowout_count += int((np.abs(raw_margin) >= 4).sum())
        batch_cover.append(float(covers.mean()))

        vals, counts = np.unique(selected_margin, return_counts=True)
        for v, c in zip(vals.tolist(), counts.tolist()):
            margin_counts[int(v)] = margin_counts.get(int(v), 0) + int(c)

        done += k

    p_cover = cover_count / done
    p_push = push_count / done
    p_win = win_count / done
    p_opp_cover = max(0.0, 1 - p_cover - p_push)
    conditional_cover = p_cover / max(1 - p_push, 1e-9)

    ordered = sorted(margin_counts.items())
    cumulative = 0
    median_margin = 0
    for margin, count in ordered:
        cumulative += count
        if cumulative >= done / 2:
            median_margin = margin
            break
    mode_margin = max(margin_counts.items(), key=lambda x: x[1])[0] if margin_counts else 0

    se = float(np.sqrt(max(p_cover * (1 - p_cover), 0) / done))
    batch_spread = max(batch_cover) - min(batch_cover) if batch_cover else 0.0

    return {
        "simulations": done,
        "seed": int(seed),
        "away_score": away_sum / done,
        "home_score": home_sum / done,
        "p_cover": p_cover,
        "p_push": p_push,
        "p_opponent_cover": p_opp_cover,
        "p_win": p_win,
        "p_one_run": one_run_count / done,
        "p_blowout": blowout_count / done,
        "median_margin": int(median_margin),
        "mode_margin": int(mode_margin),
        "fair_cover_odds": odds(conditional_cover),
        "mc_se": se,
        "batch_spread": float(batch_spread),
        "converged": bool(batch_spread <= 0.006),
    }


def _game_label(row):
    return f"{row['away_team']} @ {row['home_team']} • {row['first_pitch_et']} • {row['status']}"


def _selected_game(games_df, include_live):
    rows = []
    for idx, row in games_df.iterrows():
        if actionable(row.get("status"), include_live=include_live):
            rows.append((idx, row))
    return rows


def render_spread_module(games_df, section_header, status_info, team_logo, h):
    section_header(
        "MLB Run Line — V15",
        "Team offense + starters + bullpens + recent form + confirmed lineups + park/weather + Monte Carlo.",
    )

    st.markdown(
        '<div class="ks-note"><b>V15 foundation:</b> this is an independent team run-line model. The sportsbook spread is used only to test cover probability; it does not influence the projected score.</div>',
        unsafe_allow_html=True,
    )

    include_live = st.checkbox("⚠️ Include live games", value=False, key="spread_include_live")
    if include_live:
        st.warning("Live games can be inspected, but V15 is designed as a pregame projection model. Live score/state is not included in the simulation yet.")

    available = _selected_game(games_df, include_live)
    if not available:
        st.info("No actionable MLB games are available right now. Turn on live games if today's remaining games have already started.")
        return

    labels = [_game_label(row) for _, row in available]
    choice = st.selectbox("Game", labels, key="spread_game")
    pos = labels.index(choice)
    _, game = available[pos]

    away_name = game["away_team"]
    home_name = game["home_team"]
    status_label, status_css = status_info(game.get("status"))

    logos = f"{team_logo(game.get('away_team_id'))}{team_logo(game.get('home_team_id'))}"
    st.markdown(
        '<div class="ks-feature">'
        f'<div class="ks-eyebrow">{h(status_label)} • {h(game["first_pitch_et"])} ET</div>'
        f'<div class="ks-player-row" style="margin-top:8px">{logos}<div class="ks-player-copy">'
        f'<div class="ks-feature-name">{h(away_name)} @ {h(home_name)}</div>'
        f'<div class="ks-feature-meta">{h(game.get("venue_name", "Unknown"))} • '
        f'{h(game.get("away_pitcher", "TBD"))} vs {h(game.get("home_pitcher", "TBD"))}</div>'
        '</div></div></div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    with c1:
        selected_team = st.selectbox("Team to grade", [home_name, away_name], key="spread_team")
    with c2:
        default_line = -1.5 if selected_team == home_name else 1.5
        line = st.selectbox(
            "Run line",
            [-3.5, -2.5, -1.5, -1.0, 1.0, 1.5, 2.5, 3.5],
            index=[-3.5, -2.5, -1.5, -1.0, 1.0, 1.5, 2.5, 3.5].index(default_line),
            key=f"spread_line_{selected_team}",
        )
    with c3:
        depth = st.selectbox(
            "Simulation size",
            ["Quick — 250K", "Standard — 1M", "Deep — 3M"],
            index=1,
            key="spread_depth",
        )

    sim_n = {"Quick — 250K": 250_000, "Standard — 1M": 1_000_000, "Deep — 3M": 3_000_000}[depth]

    if st.button("🔥 RUN V15 SPREAD PROJECTION", use_container_width=True, type="primary"):
        with st.spinner("Building team profiles, pitcher/bullpen layers and run simulation..."):
            try:
                model = build_game_model(
                    int(game["game_pk"]),
                    int(game["away_team_id"]),
                    int(game["home_team_id"]),
                    game.get("away_pitcher_id"),
                    game.get("home_pitcher_id"),
                    game.get("venue_name", "Unknown"),
                )

                selected_side = "home" if selected_team == home_name else "away"
                seed = _stable_seed(int(game["game_pk"]), 1500 + int(abs(float(line)) * 10))
                sim = simulate_run_line(
                    model["away_model"]["expected_runs"],
                    model["home_model"]["expected_runs"],
                    sim_n,
                    seed,
                    selected_side,
                    float(line),
                )
            except Exception as exc:
                st.error(f"V15 could not complete this game right now: {exc}")
                return

        st.session_state["v15_spread_result"] = {
            "game_pk": int(game["game_pk"]),
            "selected_team": selected_team,
            "line": float(line),
            "model": model,
            "sim": sim,
            "away_name": away_name,
            "home_name": home_name,
            "status": game.get("status"),
        }

    result = st.session_state.get("v15_spread_result")
    if not result or result.get("game_pk") != int(game["game_pk"]):
        return

    model = result["model"]
    sim = result["sim"]
    selected_team = result["selected_team"]
    line = result["line"]
    selected_side = "home" if selected_team == home_name else "away"

    projected_margin = (
        sim["home_score"] - sim["away_score"]
        if selected_side == "home"
        else sim["away_score"] - sim["home_score"]
    )

    data_score = model["data_score"]
    confidence = (
        "HIGH" if data_score >= 8 and sim["converged"]
        else "MEDIUM-HIGH" if data_score >= 6 and sim["converged"]
        else "MEDIUM" if data_score >= 5
        else "LOW"
    )

    section_header("V15 Projection", "Independent score projection + run-line settlement simulation.")

    st.markdown(
        '<div class="ks-feature">'
        f'<div class="ks-eyebrow">{h(selected_team)} {line:+.1f}</div>'
        f'<div class="ks-feature-name">Projected score: {h(away_name)} {sim["away_score"]:.1f} — {h(home_name)} {sim["home_score"]:.1f}</div>'
        f'<div class="ks-feature-prob">{sim["p_cover"] * 100:.1f}%</div>'
        f'<div class="ks-feature-meta">Projected cover probability • Expected margin {projected_margin:+.1f} • Fair cover odds {sim["fair_cover_odds"]}</div>'
        f'<div style="margin-top:11px"><span class="ks-badge {"ks-high" if confidence == "HIGH" else "ks-medium" if "MEDIUM" in confidence else "ks-low"}">{h(confidence)} CONFIDENCE</span></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    from engine import metric_grid
    metric_grid(
        [
            ("Cover", f"{sim['p_cover'] * 100:.1f}%"),
            ("Win", f"{sim['p_win'] * 100:.1f}%"),
            ("Opponent Covers", f"{sim['p_opponent_cover'] * 100:.1f}%"),
            ("Push", f"{sim['p_push'] * 100:.1f}%"),
            ("Expected Margin", f"{projected_margin:+.1f}"),
            ("Median Margin", f"{sim['median_margin']:+d}"),
            ("One-Run Game", f"{sim['p_one_run'] * 100:.1f}%"),
            ("4+ Run Margin", f"{sim['p_blowout'] * 100:.1f}%"),
        ]
    )

    with st.expander("🧠 Team offense + recent form", expanded=True):
        metric_grid(
            [
                (f"{away_name} R/G", f"{model['away']['runs_per_game']:.2f}"),
                (f"{home_name} R/G", f"{model['home']['runs_per_game']:.2f}"),
                (f"{away_name} OPS", f"{model['away']['ops']:.3f}" if model['away'].get('ops') is not None else "N/A"),
                (f"{home_name} OPS", f"{model['home']['ops']:.3f}" if model['home'].get('ops') is not None else "N/A"),
                (f"{away_name} L10 R/G", f"{model['away_recent']['runs_per_game']:.2f}" if model.get('away_recent') else "N/A"),
                (f"{home_name} L10 R/G", f"{model['home_recent']['runs_per_game']:.2f}" if model.get('home_recent') else "N/A"),
                (f"{away_name} Base xR", f"{model['away_model']['base_runs']:.2f}"),
                (f"{home_name} Base xR", f"{model['home_model']['base_runs']:.2f}"),
            ]
        )

    with st.expander("🎯 Starting pitchers + bullpens", expanded=False):
        away_sp = model.get("away_starter") or {}
        home_sp = model.get("home_starter") or {}
        away_bp = model.get("away_bullpen") or {}
        home_bp = model.get("home_bullpen") or {}
        metric_grid(
            [
                ("Away SP", away_sp.get("name", "TBD")),
                ("Away SP ERA", away_sp.get("era", "N/A")),
                ("Home SP", home_sp.get("name", "TBD")),
                ("Home SP ERA", home_sp.get("era", "N/A")),
                ("Away BP ERA", f"{away_bp.get('era'):.2f}" if away_bp.get('era') is not None else "N/A"),
                ("Away BP WHIP", f"{away_bp.get('whip'):.2f}" if away_bp.get('whip') is not None else "N/A"),
                ("Home BP ERA", f"{home_bp.get('era'):.2f}" if home_bp.get('era') is not None else "N/A"),
                ("Home BP WHIP", f"{home_bp.get('whip'):.2f}" if home_bp.get('whip') is not None else "N/A"),
            ]
        )

    with st.expander("🏟️ Lineups + environment", expanded=False):
        env = model["environment"]
        metric_grid(
            [
                ("Ballpark", env.get("venue_name", "Unknown")),
                ("Condition", env.get("condition", "Unknown")),
                ("Temperature", f"{env['temperature']:.0f}°F" if env.get("temperature") is not None else "N/A"),
                ("Environment", env.get("grade", "Unknown")),
                ("Away Lineup", "Confirmed" if model.get("away_lineup") else "Unavailable"),
                ("Home Lineup", "Confirmed" if model.get("home_lineup") else "Unavailable"),
                ("Away Lineup OPS", f"{model['away_lineup']['avg_ops']:.3f}" if model.get('away_lineup') and model['away_lineup'].get('avg_ops') is not None else "N/A"),
                ("Home Lineup OPS", f"{model['home_lineup']['avg_ops']:.3f}" if model.get('home_lineup') and model['home_lineup'].get('avg_ops') is not None else "N/A"),
            ]
        )

    with st.expander("🎲 Simulation diagnostics", expanded=False):
        metric_grid(
            [
                ("Simulations", f"{sim['simulations']:,}"),
                ("Random Seed", sim["seed"]),
                ("Convergence", "PASS" if sim["converged"] else "CHECK"),
                ("MC SE", f"{sim['mc_se'] * 100:.3f} pts"),
                ("Max Batch Spread", f"{sim['batch_spread'] * 100:.2f} pts"),
                ("Data Layers", f"{data_score}/9"),
                ("Model", "V15 Spread Foundation"),
                ("Market Input", f"{selected_team} {line:+.1f}"),
            ]
        )

    st.caption(
        "V15 is a prototype run-distribution model, not yet a calibrated betting model. It projects team scoring independently of the sportsbook line, then applies the selected run line only for cover/push settlement."
    )
