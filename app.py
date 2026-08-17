from engine import *
from history import (
    calibration_metrics,
    calibration_table,
    grade_finished_games,
    history_download_bytes,
    load_history,
    merge_uploaded_history,
    model_version_table,
    save_single_snapshot,
    save_top5_snapshot,
    top5_performance,
)

st.title("🧠 KYRE SPORTS AI")
st.subheader("Sports Projection & Analytics Engine")
st.divider()

sport = st.selectbox("Choose Sport", ["MLB", "WNBA"])

if sport == "MLB":
    try:
        games_df, game_date = games_today()
    except requests.RequestException:
        games_df, game_date = (
            pd.DataFrame(),
            datetime.now(ET).strftime("%Y-%m-%d"),
        )

    st.header("📡 Live MLB Data")
    if st.button("🔄 LOAD TODAY'S MLB GAMES", use_container_width=True):
        if games_df.empty:
            st.warning("No MLB games found.")
        else:
            st.success(f"Schedule loaded for {game_date}")
            show = games_df[
                [
                    "away_team",
                    "home_team",
                    "first_pitch_et",
                    "away_pitcher",
                    "home_pitcher",
                    "status",
                ]
            ].rename(
                columns={
                    "away_team": "Away",
                    "home_team": "Home",
                    "first_pitch_et": "First Pitch (ET)",
                    "away_pitcher": "Away Pitcher",
                    "home_pitcher": "Home Pitcher",
                    "status": "Status",
                }
            )
            st.dataframe(
                show,
                use_container_width=True,
                hide_index=True,
            )

    st.divider()
    market = st.selectbox(
        "Choose Market",
        [
            "1+ Hit",
            "2+ Hits",
            "Home Run",
            "Hits + Runs + RBIs",
            "Moneyline",
            "Run Line",
            "Game Total",
        ],
    )

    if market == "1+ Hit":
        top_tab, single_tab, backtest_tab = st.tabs(
            [
                "🏆 Daily Top 5 Scanner",
                "🔎 Single Player",
                "📈 V13 Backtest",
            ]
        )

        with top_tab:
            st.header("🏆 V13 Daily Top 5 — MLB 1+ Hit")
            st.write(
                "Scans confirmed batting orders, screens the full actionable slate, "
                "deep-models the strongest finalists, and automatically records "
                "pregame Top 5 projections for calibration."
            )

            include_live = st.checkbox(
                "Include games already in progress",
                value=False,
            )
            depth = st.selectbox(
                "Slate Simulation Depth",
                [
                    "Fast — 100,000 per finalist",
                    "Standard — 500,000 per finalist",
                    "Deep — 1,000,000 per finalist",
                ],
                index=1,
            )
            sims = {
                "Fast — 100,000 per finalist": 100_000,
                "Standard — 500,000 per finalist": 500_000,
                "Deep — 1,000,000 per finalist": 1_000_000,
            }[depth]

            if st.button(
                "🔥 SCAN TODAY'S CONFIRMED LINEUPS",
                use_container_width=True,
            ):
                if games_df.empty:
                    st.error("Today's MLB schedule could not be loaded.")
                else:
                    with st.spinner(
                        "Reading today's confirmed lineups..."
                    ):
                        candidates, checked, with_lineups = slate_candidates(
                            games_df,
                            include_live,
                        )

                    if not candidates:
                        st.warning(
                            "No confirmed hitters were found in actionable games. "
                            "Lineups may not be posted yet, or today's remaining games "
                            "may already be underway/final."
                        )
                    else:
                        st.info(
                            f"Found {len(candidates)} confirmed hitters across "
                            f"{with_lineups}/{checked} actionable games."
                        )

                        screened = []
                        bar = st.progress(
                            0,
                            text="Screening confirmed hitters...",
                        )
                        for i, candidate in enumerate(candidates, 1):
                            try:
                                screened.append(prescreen(candidate))
                            except Exception:
                                pass
                            bar.progress(
                                i / len(candidates),
                                text=f"Screening hitters: {i}/{len(candidates)}",
                            )
                        bar.empty()

                        screened.sort(
                            key=lambda x: x["screen_p1"],
                            reverse=True,
                        )
                        finalists = screened[: min(8, len(screened))]
                        deep = []

                        bar = st.progress(
                            0,
                            text="Running deep V13 models...",
                        )
                        for i, candidate in enumerate(finalists, 1):
                            try:
                                deep.append(deep_scan(candidate, sims))
                            except Exception:
                                pass
                            bar.progress(
                                i / max(len(finalists), 1),
                                text=(
                                    f"Deep modeling finalists: "
                                    f"{i}/{len(finalists)}"
                                ),
                            )
                        bar.empty()

                        deep.sort(
                            key=lambda x: x["sim"]["p_one_plus"],
                            reverse=True,
                        )
                        st.session_state["v13_results"] = deep

                        if deep and not include_live:
                            added, total, scan_id = save_top5_snapshot(
                                deep[:5],
                                model_version="V13",
                            )
                            st.session_state["v13_save_note"] = (
                                f"Pregame snapshot saved: {added} new "
                                f"prediction(s). History now has {total} row(s)."
                            )
                        elif include_live:
                            st.session_state["v13_save_note"] = (
                                "Live-game scan was NOT added to calibration history. "
                                "V13 only auto-saves pregame scans to avoid look-ahead bias."
                            )

            results = st.session_state.get("v13_results")
            if results:
                st.subheader(
                    "🥇 Today's Strongest 1+ Hit Projections"
                )
                rows = []

                for rank, result in enumerate(results[:5], 1):
                    sim = result["sim"]
                    rows.append(
                        {
                            "Rank": rank,
                            "Player": result["player_name"],
                            "Team": result["team"],
                            "Opponent": result["opponent"],
                            "Starter": result["starter_name"],
                            "Lineup": f"#{result['position']}",
                            "1+ Hit": f"{sim['p_one_plus'] * 100:.1f}%",
                            "2+ Hits": f"{sim['p_two_plus'] * 100:.1f}%",
                            "Expected Hits": f"{sim['expected_hits']:.2f}",
                            "Fair 1+ Odds": odds(sim["p_one_plus"]),
                            "Confidence": result["confidence"],
                            "Data": f"{result['data_score']}/8",
                        }
                    )

                st.dataframe(
                    pd.DataFrame(rows),
                    use_container_width=True,
                    hide_index=True,
                )

                top = results[0]
                st.success(
                    f"#1 right now: {top['player_name']} — "
                    f"{top['sim']['p_one_plus'] * 100:.1f}% projected "
                    f"1+ hit probability, {top['confidence']} confidence."
                )

                save_note = st.session_state.get("v13_save_note")
                if save_note:
                    if "NOT" in save_note:
                        st.warning(save_note)
                    else:
                        st.info(save_note)

                st.caption(
                    "V13 ranks model probability, not sportsbook value. Pregame "
                    "Top 5 snapshots are deduplicated by player + game + model version "
                    "before entering the calibration history."
                )

                with st.expander("Show finalist details"):
                    detail = []
                    for result in results:
                        sim = result["sim"]
                        detail.append(
                            {
                                "Player": result["player_name"],
                                "Team": result["team"],
                                "Opponent": result["opponent"],
                                "Starter": result["starter_name"],
                                "Spot": result["position"],
                                "Season AVG": (
                                    f"{result['season_avg']:.3f}"
                                ),
                                "Screen 1+": (
                                    f"{result['screen_p1'] * 100:.1f}%"
                                ),
                                "Final 1+": (
                                    f"{sim['p_one_plus'] * 100:.1f}%"
                                ),
                                "2+": (
                                    f"{sim['p_two_plus'] * 100:.1f}%"
                                ),
                                "3+": (
                                    f"{sim['p_three_plus'] * 100:.1f}%"
                                ),
                                "90% Scenario Range": (
                                    f"{sim['scenario_low'] * 100:.1f}%–"
                                    f"{sim['scenario_high'] * 100:.1f}%"
                                ),
                                "MC SE": (
                                    f"{sim['mc_se'] * 100:.3f} pts"
                                ),
                                "Confidence": result["confidence"],
                            }
                        )
                    st.dataframe(
                        pd.DataFrame(detail),
                        use_container_width=True,
                        hide_index=True,
                    )

        with single_tab:
            st.header("⚾ Single-Player Deep Analysis")
            name = st.text_input(
                "Player Name",
                placeholder="Example: Yordan Alvarez",
            )

            if st.button(
                "📡 LOAD PLAYER + MATCHUP",
                use_container_width=True,
            ):
                st.session_state.pop("player_data", None)

                if not name.strip():
                    st.error("Enter a player name.")
                else:
                    try:
                        with st.spinner(
                            "Loading live hitter, matchup, Statcast and bullpen data..."
                        ):
                            data = load_player(name, games_df)

                        if data:
                            st.session_state["player_data"] = data
                        else:
                            st.error("Player not found.")
                    except requests.RequestException as exc:
                        st.error(f"Could not load MLB data: {exc}")

            if st.session_state.get("player_data"):
                data = st.session_state["player_data"]
                player = data["player"]
                stats = data["stats"]
                recent = data.get("recent")
                matchup_data = data.get("matchup")
                pitcher = data.get("pitcher")
                split_r = data.get("split_r")
                split_l = data.get("split_l")
                environment_data = data.get("environment")
                statcast_data = data.get("statcast")
                bullpen_data = data.get("bullpen")

                if not stats:
                    st.error(
                        "No current-season hitting stats were found."
                    )
                else:
                    st.success(
                        f"Live data loaded for {player['name']}"
                    )
                    st.subheader(
                        f"📊 {player['name']} — {stats['season']}"
                    )
                    st.caption(
                        f"Team: {player['team_name']} • "
                        f"Bats: {player['bat_side']}"
                    )
                    metric_grid(
                        [
                            ("AVG", stats["avg"]),
                            ("Hits", stats["hits"]),
                            ("At-Bats", stats["at_bats"]),
                            ("Games", stats["games"]),
                            ("HR", stats["home_runs"]),
                            ("OBP", stats["obp"]),
                            ("SLG", stats["slg"]),
                            ("OPS", stats["ops"]),
                        ]
                    )

                    st.subheader("🔥 Recent Form — Last 10 Games")
                    if recent and recent.get("avg") is not None:
                        metric_grid(
                            [
                                (
                                    "Recent AVG",
                                    f"{recent['avg']:.3f}",
                                ),
                                ("Hits", recent["hits"]),
                                ("Recent AB", recent["at_bats"]),
                                (
                                    "Hit Games",
                                    f"{recent['hit_games']}/"
                                    f"{recent['games']}",
                                ),
                            ]
                        )

                    st.subheader("📡 Statcast Contact Quality")
                    if statcast_data:
                        metric_grid(
                            [
                                (
                                    "xBA",
                                    f"{statcast_data['xba']:.3f}"
                                    if statcast_data.get("xba")
                                    is not None
                                    else "N/A",
                                ),
                                (
                                    "Avg Exit Velo",
                                    f"{statcast_data['avg_ev']:.1f} mph"
                                    if statcast_data.get("avg_ev")
                                    is not None
                                    else "N/A",
                                ),
                                (
                                    "Hard-Hit %",
                                    f"{statcast_data['hard_hit_rate'] * 100:.1f}%"
                                    if statcast_data.get(
                                        "hard_hit_rate"
                                    )
                                    is not None
                                    else "N/A",
                                ),
                                (
                                    "Barrel %",
                                    f"{statcast_data['barrel_rate'] * 100:.1f}%"
                                    if statcast_data.get("barrel_rate")
                                    is not None
                                    else "N/A",
                                ),
                            ]
                        )

                    st.subheader("⚔️ Today's Matchup")
                    if matchup_data:
                        metric_grid(
                            [
                                (
                                    "Opponent",
                                    matchup_data["opponent"],
                                ),
                                (
                                    "Home/Away",
                                    matchup_data["location"],
                                ),
                                (
                                    "First Pitch",
                                    matchup_data["first_pitch"],
                                ),
                                (
                                    "Status",
                                    matchup_data["status"],
                                ),
                            ]
                        )

                        if pitcher:
                            metric_grid(
                                [
                                    ("Pitcher", pitcher["name"]),
                                    ("Throws", pitcher["hand"]),
                                    ("ERA", pitcher["era"]),
                                    ("WHIP", pitcher["whip"]),
                                    (
                                        "W-L",
                                        f"{pitcher['wins']}-"
                                        f"{pitcher['losses']}",
                                    ),
                                    (
                                        "Starts",
                                        pitcher["games_started"],
                                    ),
                                    ("IP", pitcher["innings"]),
                                    (
                                        "K/9",
                                        f"{pitcher['k9']:.2f}"
                                        if pitcher.get("k9")
                                        is not None
                                        else "N/A",
                                    ),
                                ]
                            )

                        starter_split = (
                            split_r
                            if pitcher
                            and pitcher.get("hand") == "R"
                            else split_l
                            if pitcher
                            and pitcher.get("hand") == "L"
                            else None
                        )

                        if starter_split:
                            st.subheader(
                                "↔️ Batter vs Starter Hand"
                            )
                            metric_grid(
                                [
                                    (
                                        "Split AVG",
                                        starter_split["avg"],
                                    ),
                                    (
                                        "Split Hits",
                                        starter_split["hits"],
                                    ),
                                    (
                                        "Split AB",
                                        starter_split["at_bats"],
                                    ),
                                    (
                                        "Split OPS",
                                        starter_split["ops"],
                                    ),
                                ]
                            )

                        st.subheader("🧯 Opponent Bullpen")
                        if bullpen_data:
                            metric_grid(
                                [
                                    (
                                        "Bullpen ERA",
                                        f"{bullpen_data['era']:.2f}",
                                    ),
                                    (
                                        "Bullpen WHIP",
                                        f"{bullpen_data['whip']:.2f}",
                                    ),
                                    (
                                        "Bullpen K/9",
                                        f"{bullpen_data['k9']:.2f}",
                                    ),
                                    (
                                        "Relievers",
                                        bullpen_data[
                                            "reliever_count"
                                        ],
                                    ),
                                    (
                                        "RHP Exposure",
                                        f"{bullpen_data['right_share'] * 100:.0f}%",
                                    ),
                                    (
                                        "LHP Exposure",
                                        f"{bullpen_data['left_share'] * 100:.0f}%",
                                    ),
                                ]
                            )

                        st.subheader("🏟️ Park + Weather")
                        env_view = env_adj(
                            environment_data,
                            matchup_data.get(
                                "venue_name",
                                "Unknown",
                            ),
                        )
                        metric_grid(
                            [
                                (
                                    "Ballpark",
                                    env_view["venue_name"],
                                ),
                                (
                                    "Temperature",
                                    f"{env_view['temperature']:.0f}°F"
                                    if env_view["temperature"]
                                    is not None
                                    else "N/A",
                                ),
                                (
                                    "Condition",
                                    env_view["condition"],
                                ),
                                ("Wind", env_view["wind"]),
                                (
                                    "Roof Type",
                                    env_view["roof_type"],
                                ),
                                (
                                    "Environment Grade",
                                    env_view["grade"],
                                ),
                                (
                                    "Park Adj",
                                    f"{env_view['park_adjustment'] * 100:+.1f}%",
                                ),
                            ]
                        )
                    else:
                        st.warning(
                            "No game found today for this player's team."
                        )

                    confirmed = data.get("confirmed_lineup")
                    estimated = data.get("recent_lineup")
                    projected = (
                        int(confirmed)
                        if confirmed
                        else int(estimated["position"])
                        if estimated
                        else 4
                    )
                    source = (
                        "Confirmed today's lineup"
                        if confirmed
                        else (
                            f"Recent lineup estimate "
                            f"({estimated['sample_games']} games)"
                        )
                        if estimated
                        else "Manual fallback"
                    )

                    st.subheader("📋 Lineup Position")
                    metric_grid(
                        [
                            (
                                "Projected Batting Spot",
                                f"#{projected}",
                            ),
                            ("Lineup Source", source),
                            (
                                "Baseline Expected AB",
                                f"{ab_for_spot(projected):.1f}",
                            ),
                        ],
                        3,
                    )

                    spot = st.selectbox(
                        "Batting Order Used by Model",
                        list(range(1, 10)),
                        index=projected - 1,
                    )
                    expected_ab = st.number_input(
                        "Projected At-Bats Today",
                        2.5,
                        6.0,
                        float(ab_for_spot(spot)),
                        0.1,
                    )
                    st.number_input(
                        "Sportsbook Hit Line",
                        value=0.5,
                        step=0.5,
                    )

                    mode = st.selectbox(
                        "Monte Carlo Simulation Size",
                        [
                            "Quick — 500,000",
                            "Standard — 5,000,000",
                            "Deep — 10,000,000",
                        ],
                        index=1,
                    )
                    sim_n = {
                        "Quick — 500,000": 500_000,
                        "Standard — 5,000,000": 5_000_000,
                        "Deep — 10,000,000": 10_000_000,
                    }[mode]

                    if st.button(
                        "🔥 RUN V13 SINGLE-PLAYER MONTE CARLO",
                        use_container_width=True,
                    ):
                        base = sf(stats["avg"], 0) or 0
                        model = model_inputs(
                            base,
                            spot,
                            matchup_data,
                            pitcher,
                            split_r,
                            split_l,
                            recent,
                            environment_data,
                            statcast_data,
                            bullpen_data,
                        )
                        exposure = starter_exposure(
                            pitcher,
                            expected_ab,
                        )
                        deterministic = combined(
                            model["starter_rate"],
                            model["bullpen_rate"],
                            exposure["starter_ab"],
                            exposure["bullpen_ab"],
                        )
                        seed = sim_seed(
                            player["id"],
                            (matchup_data or {}).get(
                                "game_pk",
                                0,
                            ),
                        )

                        with st.spinner(
                            f"Running {sim_n:,} Monte Carlo simulations..."
                        ):
                            sim = monte(
                                model["starter_rate"],
                                model["bullpen_rate"],
                                expected_ab,
                                exposure["starter_share"],
                                model["split_weight"],
                                model["statcast_model"].get(
                                    "reliability",
                                    0,
                                ),
                                model["pitcher_quality"].get(
                                    "reliability",
                                    0,
                                )
                                if model["pitcher_quality"]
                                else 0,
                                model["bullpen_quality"].get(
                                    "reliability",
                                    0,
                                )
                                if model["bullpen_quality"]
                                else 0,
                                sim_n,
                                seed,
                            )

                        grade, score = confidence(
                            stats,
                            pitcher,
                            model["starter_split"],
                            recent,
                            confirmed,
                            environment_data,
                            statcast_data,
                            bullpen_data,
                            sim,
                        )
                        season_base = p_from_avg(
                            base,
                            expected_ab,
                        )

                        st.header("🧠 V13 Single-Player Model")
                        metric_grid(
                            [
                                ("Season AVG", f"{base:.3f}"),
                                (
                                    "Starter-Facing Rate",
                                    f"{model['starter_rate']:.3f}",
                                ),
                                (
                                    "Bullpen-Facing Rate",
                                    f"{model['bullpen_rate']:.3f}",
                                ),
                                (
                                    "Expected AB",
                                    f"{expected_ab:.1f}",
                                ),
                                (
                                    "Starter Exposure",
                                    f"{exposure['starter_share'] * 100:.0f}%",
                                ),
                                (
                                    "Deterministic 1+",
                                    f"{deterministic['p_one_plus'] * 100:.1f}%",
                                ),
                                (
                                    "Environment Adj",
                                    f"{model['env_model']['total_adjustment'] * 100:+.1f}%",
                                ),
                                (
                                    "Contact Adj",
                                    f"{model['statcast_model']['quality_adjustment'] * 100:+.1f}%",
                                ),
                            ]
                        )

                        st.subheader(
                            "🎲 Monte Carlo — Uncertainty Engine"
                        )
                        metric_grid(
                            [
                                (
                                    "Simulations",
                                    f"{sim['simulations']:,}",
                                ),
                                ("Batches", sim["batches"]),
                                ("Random Seed", sim["seed"]),
                                (
                                    "Convergence",
                                    "PASS"
                                    if sim["converged"]
                                    else "CHECK",
                                ),
                                (
                                    "MC Standard Error",
                                    f"{sim['mc_se'] * 100:.3f} pts",
                                ),
                                (
                                    "Max Batch Spread",
                                    f"{sim['batch_range'] * 100:.2f} pts",
                                ),
                                (
                                    "Scenario 90% Range",
                                    f"{sim['scenario_low'] * 100:.1f}%–"
                                    f"{sim['scenario_high'] * 100:.1f}%",
                                ),
                                ("Confidence Grade", grade),
                            ]
                        )

                        st.header("📊 V13 Simulation Results")
                        metric_grid(
                            [
                                (
                                    "Expected Hits",
                                    f"{sim['expected_hits']:.2f}",
                                ),
                                (
                                    "1+ Hit Probability",
                                    f"{sim['p_one_plus'] * 100:.1f}%",
                                ),
                                (
                                    "0 Hit Probability",
                                    f"{sim['p_zero'] * 100:.1f}%",
                                ),
                                (
                                    "Exactly 1 Hit",
                                    f"{sim['p_exact_one'] * 100:.1f}%",
                                ),
                                (
                                    "2+ Hit Probability",
                                    f"{sim['p_two_plus'] * 100:.1f}%",
                                ),
                                (
                                    "3+ Hit Probability",
                                    f"{sim['p_three_plus'] * 100:.1f}%",
                                ),
                                (
                                    "Median Hits",
                                    sim["median_hits"],
                                ),
                                (
                                    "Mode Hits",
                                    sim["mode_hits"],
                                ),
                                (
                                    "Fair Odds — 1+",
                                    odds(sim["p_one_plus"]),
                                ),
                                (
                                    "Season AVG + Current AB",
                                    f"{season_base['p_one_plus'] * 100:.1f}%",
                                ),
                                ("Data Layers", f"{score}/8"),
                                ("Model Version", "V13"),
                            ]
                        )

                        if (
                            matchup_data
                            and actionable(
                                matchup_data.get("status"),
                                include_live=False,
                            )
                        ):
                            added, total = save_single_snapshot(
                                player,
                                matchup_data,
                                pitcher,
                                spot,
                                expected_ab,
                                sim,
                                grade,
                                score,
                                model_version="V13",
                            )
                            if added:
                                st.info(
                                    "Pregame single-player projection "
                                    f"saved to V13 history. "
                                    f"History now has {total} row(s)."
                                )
                            else:
                                st.caption(
                                    "This player/game already has a V13 "
                                    "pregame prediction in history, so it "
                                    "was not duplicated."
                                )
                        else:
                            st.warning(
                                "This result was not saved to calibration "
                                "history because the game is already live/final "
                                "or no current game was found."
                            )

                        st.caption(
                            "Season AVG + Current AB is the season batting-average "
                            "baseline using today's projected at-bat count. "
                            "V13 history saves the first pregame prediction per "
                            "player/game/model so repeated scans do not inflate "
                            "the backtest sample."
                        )

        with backtest_tab:
            st.header("📈 V13 Prediction History & Calibration")
            st.write(
                "Pregame predictions are recorded before the result is known. "
                "After games finish, V13 can pull the official MLB box score, "
                "grade each prediction, and measure whether the probability "
                "model is actually calibrated."
            )

            st.warning(
                "Free Streamlit storage is local to the running app and can reset "
                "after a redeploy/restart. Download the history CSV periodically. "
                "You can upload that backup here later and V13 will merge it back."
            )

            if st.button(
                "🔄 GRADE FINISHED GAMES",
                use_container_width=True,
            ):
                with st.spinner(
                    "Checking MLB results and grading finished games..."
                ):
                    summary = grade_finished_games()

                st.success(
                    f"Graded {summary['graded']} prediction(s) • "
                    f"DNP {summary['dnp']} • "
                    f"Void {summary['void']} • "
                    f"Still pending {summary['still_pending']}."
                )
                if summary["errors"]:
                    st.warning(
                        f"{summary['errors']} game lookup(s) could not be "
                        "completed right now."
                    )

            history = load_history()

            if history.empty:
                st.info(
                    "No prediction history yet. Run a pregame Top 5 scan "
                    "or a pregame single-player projection first."
                )
            else:
                metrics = calibration_metrics(history)
                top5 = top5_performance(history)

                stored = len(history)
                pending = int(
                    history["grade_status"]
                    .fillna("PENDING")
                    .eq("PENDING")
                    .sum()
                )

                metric_grid(
                    [
                        ("Stored Predictions", stored),
                        ("Graded Predictions", metrics["graded"]),
                        ("Pending", pending),
                        (
                            "Actual 1+ Hit Rate",
                            f"{metrics['hit_rate'] * 100:.1f}%"
                            if metrics["graded"]
                            else "N/A",
                        ),
                        (
                            "Avg Projected 1+",
                            f"{metrics['avg_prediction'] * 100:.1f}%"
                            if metrics["graded"]
                            else "N/A",
                        ),
                        (
                            "Calibration Gap",
                            f"{metrics['calibration_gap'] * 100:+.1f} pts"
                            if metrics["graded"]
                            else "N/A",
                        ),
                        (
                            "Brier Score",
                            f"{metrics['brier']:.3f}"
                            if metrics["graded"]
                            else "N/A",
                        ),
                        (
                            "Log Loss",
                            f"{metrics['log_loss']:.3f}"
                            if metrics["graded"]
                            else "N/A",
                        ),
                    ]
                )

                st.subheader("🏆 Historical Top 5 Performance")
                metric_grid(
                    [
                        (
                            "Top 5 Graded Picks",
                            top5["predictions"],
                        ),
                        (
                            "Top 5 Hit Rate",
                            f"{top5['hit_rate'] * 100:.1f}%"
                            if top5["predictions"]
                            else "N/A",
                        ),
                        (
                            "#1 Pick Hit Rate",
                            f"{top5['rank1_rate'] * 100:.1f}%"
                            if top5["predictions"]
                            and not pd.isna(top5["rank1_rate"])
                            else "N/A",
                        ),
                    ],
                    3,
                )

                st.subheader("🎯 Calibration by Probability Tier")
                cal = calibration_table(history)
                if cal.empty:
                    st.info(
                        "Calibration tiers will appear after at least "
                        "one prediction has been graded."
                    )
                else:
                    st.dataframe(
                        cal,
                        use_container_width=True,
                        hide_index=True,
                    )

                st.subheader("🧪 Model-Version Performance")
                versions = model_version_table(history)
                if not versions.empty:
                    st.dataframe(
                        versions,
                        use_container_width=True,
                        hide_index=True,
                    )

                st.subheader("🗂️ Prediction History")
                display = history.copy()
                for col in (
                    "predicted_p1",
                    "predicted_p2",
                    "predicted_p3",
                ):
                    display[col] = pd.to_numeric(
                        display[col],
                        errors="coerce",
                    ).map(
                        lambda x: (
                            f"{x * 100:.1f}%"
                            if pd.notna(x)
                            else ""
                        )
                    )

                columns = [
                    "created_at_et",
                    "model_version",
                    "source",
                    "rank",
                    "player_name",
                    "team",
                    "opponent",
                    "predicted_p1",
                    "confidence",
                    "grade_status",
                    "actual_hits",
                    "actual_1plus",
                ]
                display = display[
                    [c for c in columns if c in display.columns]
                ].rename(
                    columns={
                        "created_at_et": "Saved At (ET)",
                        "model_version": "Model",
                        "source": "Source",
                        "rank": "Rank",
                        "player_name": "Player",
                        "team": "Team",
                        "opponent": "Opponent",
                        "predicted_p1": "Projected 1+",
                        "confidence": "Confidence",
                        "grade_status": "Grade Status",
                        "actual_hits": "Actual Hits",
                        "actual_1plus": "Hit 1+?",
                    }
                )
                st.dataframe(
                    display.iloc[::-1].head(100),
                    use_container_width=True,
                    hide_index=True,
                )

                st.download_button(
                    "⬇️ DOWNLOAD V13 HISTORY CSV",
                    data=history_download_bytes(history),
                    file_name="kyre_sports_ai_v13_history.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            st.divider()
            st.subheader("♻️ Restore a History Backup")
            upload = st.file_uploader(
                "Upload a previous V13 history CSV",
                type=["csv"],
            )
            if upload is not None and st.button(
                "MERGE HISTORY BACKUP",
                use_container_width=True,
            ):
                result = merge_uploaded_history(upload)
                if result["ok"]:
                    st.success(result["message"])
                else:
                    st.error(result["message"])

            st.caption(
                "Brier score and log loss are proper probability-scoring rules: "
                "lower is better. Calibration Gap = actual hit rate minus average "
                "projected probability. A well-calibrated model should move toward "
                "a gap near 0 as the sample grows."
            )

    else:
        st.info(f"The MLB {market} engine will be added later.")

else:
    market = st.selectbox(
        "Choose Market",
        [
            "Points",
            "Rebounds",
            "Assists",
            "PRA",
            "Spread",
            "Game Total",
        ],
    )
    st.info(f"The WNBA {market} model will be added later.")

st.divider()
st.caption("Kyre Sports AI • Projection Engine V13")
