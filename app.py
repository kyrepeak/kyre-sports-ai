from html import escape

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


# ============================================================
# V14 UI — MODEL MATH REMAINS V13
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --ks-bg: #080d16;
        --ks-panel: #0f1726;
        --ks-panel-2: #131e31;
        --ks-border: rgba(148, 163, 184, .17);
        --ks-text: #f8fafc;
        --ks-muted: #94a3b8;
        --ks-blue: #38bdf8;
        --ks-blue-2: #2563eb;
        --ks-green: #22c55e;
        --ks-yellow: #f59e0b;
        --ks-red: #ef4444;
    }

    .stApp {
        background:
            radial-gradient(circle at 10% 0%, rgba(37, 99, 235, .13), transparent 32rem),
            var(--ks-bg);
    }

    .block-container {
        max-width: 1180px;
        padding-top: 1.3rem;
        padding-bottom: 4rem;
    }

    .ks-hero {
        background: linear-gradient(135deg, rgba(37,99,235,.22), rgba(15,23,38,.94) 55%, rgba(56,189,248,.08));
        border: 1px solid var(--ks-border);
        border-radius: 24px;
        padding: 24px 26px;
        margin-bottom: 20px;
        box-shadow: 0 22px 55px rgba(0,0,0,.22);
    }

    .ks-eyebrow {
        color: var(--ks-blue);
        font-size: .78rem;
        font-weight: 800;
        letter-spacing: .14em;
        text-transform: uppercase;
        margin-bottom: .45rem;
    }

    .ks-title {
        color: var(--ks-text);
        font-size: clamp(2rem, 5vw, 3.25rem);
        line-height: 1;
        font-weight: 900;
        letter-spacing: -.04em;
        margin: 0;
    }

    .ks-subtitle {
        color: var(--ks-muted);
        font-size: 1rem;
        margin-top: .7rem;
        margin-bottom: 0;
    }

    .ks-pills {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 16px;
    }

    .ks-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        border: 1px solid var(--ks-border);
        border-radius: 999px;
        background: rgba(15, 23, 42, .72);
        color: #cbd5e1;
        padding: 7px 10px;
        font-size: .78rem;
        font-weight: 700;
        white-space: nowrap;
    }

    .ks-dot {
        width: 7px;
        height: 7px;
        border-radius: 999px;
        background: var(--ks-green);
        box-shadow: 0 0 10px rgba(34,197,94,.7);
    }

    .ks-section-head {
        display: flex;
        justify-content: space-between;
        align-items: end;
        gap: 12px;
        margin: 22px 0 12px;
    }

    .ks-section-head h2,
    .ks-section-head h3 {
        margin: 0;
        color: var(--ks-text);
        letter-spacing: -.025em;
    }

    .ks-kicker {
        color: var(--ks-muted);
        font-size: .85rem;
        margin: 3px 0 0;
    }

    .ks-card-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 10px;
        margin: 10px 0 16px;
    }

    .ks-pick-card {
        position: relative;
        overflow: hidden;
        background: linear-gradient(180deg, rgba(19,30,49,.97), rgba(10,17,29,.97));
        border: 1px solid var(--ks-border);
        border-radius: 18px;
        padding: 16px;
        min-height: 190px;
    }

    .ks-pick-card:first-child {
        border-color: rgba(56,189,248,.55);
        box-shadow: 0 12px 34px rgba(37,99,235,.16);
    }

    .ks-rank {
        font-size: .75rem;
        color: var(--ks-blue);
        font-weight: 900;
        letter-spacing: .09em;
        text-transform: uppercase;
    }

    .ks-player {
        font-size: 1.06rem;
        color: var(--ks-text);
        font-weight: 850;
        line-height: 1.18;
        margin-top: 8px;
        min-height: 2.4em;
    }

    .ks-matchup {
        color: var(--ks-muted);
        font-size: .78rem;
        margin-top: 5px;
        line-height: 1.35;
    }

    .ks-prob {
        font-size: 2rem;
        color: white;
        font-weight: 900;
        letter-spacing: -.04em;
        margin-top: 13px;
    }

    .ks-prob-label {
        color: var(--ks-muted);
        font-size: .72rem;
        margin-top: -3px;
    }

    .ks-card-bottom {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 8px;
        margin-top: 13px;
    }

    .ks-badge {
        display: inline-block;
        border-radius: 999px;
        padding: 5px 8px;
        font-size: .68rem;
        font-weight: 900;
        letter-spacing: .04em;
        white-space: nowrap;
    }

    .ks-high { background: rgba(34,197,94,.14); color: #86efac; border: 1px solid rgba(34,197,94,.28); }
    .ks-medium { background: rgba(245,158,11,.14); color: #fde68a; border: 1px solid rgba(245,158,11,.28); }
    .ks-low { background: rgba(239,68,68,.14); color: #fca5a5; border: 1px solid rgba(239,68,68,.28); }

    .ks-mini {
        color: #cbd5e1;
        font-size: .72rem;
        white-space: nowrap;
    }

    .ks-feature {
        border: 1px solid var(--ks-border);
        border-radius: 20px;
        background: linear-gradient(135deg, rgba(37,99,235,.15), rgba(15,23,38,.95));
        padding: 20px;
        margin: 10px 0 16px;
    }

    .ks-feature-name {
        color: var(--ks-text);
        font-size: 1.45rem;
        font-weight: 900;
        letter-spacing: -.03em;
    }

    .ks-feature-meta {
        color: var(--ks-muted);
        margin-top: 5px;
        font-size: .88rem;
    }

    .ks-feature-prob {
        font-size: clamp(2.7rem, 8vw, 4.5rem);
        font-weight: 950;
        line-height: 1;
        letter-spacing: -.06em;
        color: #f8fafc;
        margin-top: 14px;
    }

    .ks-note {
        border-left: 3px solid var(--ks-blue);
        background: rgba(56,189,248,.06);
        padding: 10px 12px;
        color: #cbd5e1;
        border-radius: 0 10px 10px 0;
        font-size: .84rem;
        margin: 10px 0;
    }

    .ks-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        color: var(--ks-muted);
        font-size: .76rem;
        border-top: 1px solid var(--ks-border);
        margin-top: 34px;
        padding-top: 18px;
    }

    div[data-testid="stMetric"] {
        background: rgba(15,23,38,.78);
        border: 1px solid var(--ks-border);
        border-radius: 14px;
        padding: 10px 12px;
        min-height: 93px;
    }

    div[data-testid="stMetricLabel"] {
        color: var(--ks-muted);
    }

    div[data-testid="stMetricValue"] {
        color: var(--ks-text);
        font-size: clamp(1.15rem, 3vw, 1.8rem);
    }

    div[data-baseweb="tab-list"] {
        gap: 5px;
        overflow-x: auto;
        scrollbar-width: none;
    }

    button[data-baseweb="tab"] {
        border-radius: 12px 12px 0 0;
        white-space: nowrap;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--ks-border);
        border-radius: 14px;
        overflow: hidden;
    }

    .stButton > button,
    .stDownloadButton > button {
        border-radius: 12px;
        font-weight: 800;
        min-height: 44px;
    }

    div[data-testid="stExpander"] {
        border: 1px solid var(--ks-border);
        border-radius: 14px;
        background: rgba(15,23,38,.52);
    }

    @media (max-width: 900px) {
        .ks-card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        .ks-pick-card:first-child { grid-column: span 2; }
        .block-container { padding-left: .9rem; padding-right: .9rem; }
    }

    @media (max-width: 620px) {
        .ks-hero { border-radius: 18px; padding: 20px 17px; }
        .ks-card-grid { grid-template-columns: 1fr; }
        .ks-pick-card:first-child { grid-column: span 1; }
        .ks-pick-card { min-height: 0; }
        .ks-player { min-height: 0; }
        .ks-footer { align-items: flex-start; flex-direction: column; }
        div[data-testid="stMetric"] { min-height: 82px; padding: 9px; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def h(value):
    return escape(str(value if value is not None else ""))


def confidence_class(value):
    text = str(value or "").upper()
    if "HIGH" in text:
        return "ks-high"
    if "MEDIUM" in text:
        return "ks-medium"
    return "ks-low"


def render_hero(game_date):
    now = datetime.now(ET).strftime("%I:%M %p ET").lstrip("0")
    st.markdown(
        f"""
        <div class="ks-hero">
          <div class="ks-eyebrow">Sports projection intelligence</div>
          <div class="ks-title">🧠 KYRE SPORTS AI</div>
          <p class="ks-subtitle">MLB probability modeling, slate scanning and calibration — built for fast mobile use.</p>
          <div class="ks-pills">
            <span class="ks-pill"><span class="ks-dot"></span> Data engine online</span>
            <span class="ks-pill">⚾ MLB • {h(game_date)}</span>
            <span class="ks-pill">🧪 Model V13</span>
            <span class="ks-pill">✨ UI V14</span>
            <span class="ks-pill">🕒 {h(now)}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def section_header(title, subtitle=""):
    st.markdown(
        f"""
        <div class="ks-section-head">
          <div>
            <h2>{h(title)}</h2>
            <p class="ks-kicker">{h(subtitle)}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pick_cards(results):
    cards = []
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for rank, result in enumerate(results[:5], 1):
        sim = result["sim"]
        conf = result.get("confidence", "N/A")
        badge_class = confidence_class(conf)
        cards.append(
            f"""
            <div class="ks-pick-card">
              <div class="ks-rank">{medals.get(rank, '•')} Rank {rank}</div>
              <div class="ks-player">{h(result['player_name'])}</div>
              <div class="ks-matchup">{h(result['team'])} vs {h(result['opponent'])}<br>vs {h(result['starter_name'])} • Bat #{h(result['position'])}</div>
              <div class="ks-prob">{sim['p_one_plus'] * 100:.1f}%</div>
              <div class="ks-prob-label">Projected 1+ hit</div>
              <div class="ks-card-bottom">
                <span class="ks-badge {badge_class}">{h(conf)}</span>
                <span class="ks-mini">2+ {sim['p_two_plus'] * 100:.1f}%</span>
              </div>
            </div>
            """
        )
    st.markdown(
        '<div class="ks-card-grid">' + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )


def render_probability_feature(player_name, team, opponent, sim, grade, subtitle="1+ Hit Probability"):
    badge_class = confidence_class(grade)
    st.markdown(
        f"""
        <div class="ks-feature">
          <div class="ks-feature-name">{h(player_name)}</div>
          <div class="ks-feature-meta">{h(team)} vs {h(opponent)}</div>
          <div class="ks-feature-prob">{sim['p_one_plus'] * 100:.1f}%</div>
          <div class="ks-feature-meta">{h(subtitle)} &nbsp; • &nbsp; 2+ hits {sim['p_two_plus'] * 100:.1f}% &nbsp; • &nbsp; Expected hits {sim['expected_hits']:.2f}</div>
          <div style="margin-top:12px"><span class="ks-badge {badge_class}">{h(grade)} CONFIDENCE</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# DATA LOAD
# ============================================================

try:
    games_df, game_date = games_today()
except requests.RequestException:
    games_df, game_date = (
        pd.DataFrame(),
        datetime.now(ET).strftime("%Y-%m-%d"),
    )

render_hero(game_date)

nav1, nav2, nav3 = st.columns([1.15, 1.55, 1.0])
with nav1:
    sport = st.selectbox("Sport", ["MLB", "WNBA"], label_visibility="collapsed")
with nav2:
    if sport == "MLB":
        market = st.selectbox(
            "Market",
            ["1+ Hit", "2+ Hits", "Home Run", "Hits + Runs + RBIs", "Moneyline", "Run Line", "Game Total"],
            label_visibility="collapsed",
        )
    else:
        market = st.selectbox(
            "Market",
            ["Points", "Rebounds", "Assists", "PRA", "Spread", "Game Total"],
            label_visibility="collapsed",
        )
with nav3:
    st.markdown(
        '<div class="ks-pill" style="justify-content:center;margin-top:2px;min-height:42px">Model V13 • UI V14</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# MLB
# ============================================================

if sport == "MLB":
    with st.expander("⚾ Today’s MLB schedule", expanded=False):
        action_col, meta_col = st.columns([1, 2])
        with action_col:
            reload_schedule = st.button("🔄 Refresh schedule", use_container_width=True)
        with meta_col:
            st.caption(f"Schedule date: {game_date} • Probable pitchers and status from MLB data")

        if reload_schedule or not games_df.empty:
            if games_df.empty:
                st.warning("No MLB games found.")
            else:
                show = games_df[
                    ["away_team", "home_team", "first_pitch_et", "away_pitcher", "home_pitcher", "status"]
                ].rename(
                    columns={
                        "away_team": "Away",
                        "home_team": "Home",
                        "first_pitch_et": "ET",
                        "away_pitcher": "Away SP",
                        "home_pitcher": "Home SP",
                        "status": "Status",
                    }
                )
                st.dataframe(show, use_container_width=True, hide_index=True)

    if market == "1+ Hit":
        top_tab, single_tab, backtest_tab = st.tabs(
            ["🏆 Top Picks", "🔎 Analyzer", "📈 Backtest"]
        )

        # ----------------------------------------------------
        # TOP PICKS
        # ----------------------------------------------------
        with top_tab:
            section_header(
                "Daily 1+ Hit Scanner",
                "Confirmed lineups → full-slate screen → deep Monte Carlo finalists → ranked Top 5.",
            )

            ctrl1, ctrl2 = st.columns([1, 1.35])
            with ctrl1:
                include_live = st.checkbox("Include live games", value=False)
            with ctrl2:
                depth = st.selectbox(
                    "Simulation depth",
                    ["Fast — 100K/finalist", "Standard — 500K/finalist", "Deep — 1M/finalist"],
                    index=1,
                )

            sims = {
                "Fast — 100K/finalist": 100_000,
                "Standard — 500K/finalist": 500_000,
                "Deep — 1M/finalist": 1_000_000,
            }[depth]

            if st.button("🔥 SCAN TODAY’S CONFIRMED LINEUPS", use_container_width=True, type="primary"):
                if games_df.empty:
                    st.error("Today’s MLB schedule could not be loaded.")
                else:
                    with st.spinner("Reading confirmed lineups..."):
                        candidates, checked, with_lineups = slate_candidates(games_df, include_live)

                    if not candidates:
                        st.warning(
                            "No confirmed hitters were found in actionable games. Lineups may not be posted yet, or remaining games may already be underway/final."
                        )
                    else:
                        st.info(
                            f"{len(candidates)} confirmed hitters • {with_lineups}/{checked} actionable games with lineups"
                        )
                        screened = []
                        bar = st.progress(0, text="Screening hitters...")
                        for i, candidate in enumerate(candidates, 1):
                            try:
                                screened.append(prescreen(candidate))
                            except Exception:
                                pass
                            bar.progress(i / len(candidates), text=f"Screening {i}/{len(candidates)}")
                        bar.empty()

                        screened.sort(key=lambda x: x["screen_p1"], reverse=True)
                        finalists = screened[: min(8, len(screened))]
                        deep = []
                        bar = st.progress(0, text="Running deep finalist models...")
                        for i, candidate in enumerate(finalists, 1):
                            try:
                                deep.append(deep_scan(candidate, sims))
                            except Exception:
                                pass
                            bar.progress(i / max(len(finalists), 1), text=f"Modeling finalist {i}/{len(finalists)}")
                        bar.empty()

                        deep.sort(key=lambda x: x["sim"]["p_one_plus"], reverse=True)
                        st.session_state["v13_results"] = deep

                        if deep and not include_live:
                            added, total, _ = save_top5_snapshot(deep[:5], model_version="V13")
                            st.session_state["v13_save_note"] = (
                                f"Pregame calibration snapshot: {added} new prediction(s) • {total} total history rows."
                            )
                        elif include_live:
                            st.session_state["v13_save_note"] = (
                                "Live-game scan was not saved to calibration history to avoid look-ahead bias."
                            )

            results = st.session_state.get("v13_results")
            if results:
                section_header("Today’s Strongest Projections", "Probability ranking — not sportsbook value.")
                render_pick_cards(results)

                top = results[0]
                st.markdown(
                    f'<div class="ks-note"><b>Current #1:</b> {h(top["player_name"])} at <b>{top["sim"]["p_one_plus"] * 100:.1f}%</b> projected 1+ hit probability with {h(top["confidence"])} confidence.</div>',
                    unsafe_allow_html=True,
                )

                save_note = st.session_state.get("v13_save_note")
                if save_note:
                    if "not saved" in save_note.lower():
                        st.warning(save_note)
                    else:
                        st.info(save_note)

                with st.expander("📋 Open full Top 5 table"):
                    rows = []
                    for rank, result in enumerate(results[:5], 1):
                        sim = result["sim"]
                        rows.append(
                            {
                                "#": rank,
                                "Player": result["player_name"],
                                "Team": result["team"],
                                "Opp": result["opponent"],
                                "SP": result["starter_name"],
                                "Bat": f"#{result['position']}",
                                "1+": f"{sim['p_one_plus'] * 100:.1f}%",
                                "2+": f"{sim['p_two_plus'] * 100:.1f}%",
                                "xHits": f"{sim['expected_hits']:.2f}",
                                "Fair": odds(sim["p_one_plus"]),
                                "Conf": result["confidence"],
                                "Data": f"{result['data_score']}/8",
                            }
                        )
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                with st.expander("🧪 Finalist model details"):
                    detail = []
                    for result in results:
                        sim = result["sim"]
                        detail.append(
                            {
                                "Player": result["player_name"],
                                "Season AVG": f"{result['season_avg']:.3f}",
                                "Screen 1+": f"{result['screen_p1'] * 100:.1f}%",
                                "Final 1+": f"{sim['p_one_plus'] * 100:.1f}%",
                                "2+": f"{sim['p_two_plus'] * 100:.1f}%",
                                "3+": f"{sim['p_three_plus'] * 100:.1f}%",
                                "90% Range": f"{sim['scenario_low'] * 100:.1f}%–{sim['scenario_high'] * 100:.1f}%",
                                "MC SE": f"{sim['mc_se'] * 100:.3f} pts",
                                "Confidence": result["confidence"],
                            }
                        )
                    st.dataframe(pd.DataFrame(detail), use_container_width=True, hide_index=True)

                st.caption(
                    "Pregame Top 5 results are deduplicated by player + game + model version before entering V13 calibration history."
                )

        # ----------------------------------------------------
        # ANALYZER
        # ----------------------------------------------------
        with single_tab:
            section_header(
                "Single-Player Analyzer",
                "Search one hitter, inspect the matchup layers, then run the full Monte Carlo model.",
            )

            search_col, load_col = st.columns([2.2, 1])
            with search_col:
                name = st.text_input("Player", placeholder="Yordan Alvarez", label_visibility="collapsed")
            with load_col:
                load_clicked = st.button("📡 Load player", use_container_width=True)

            if load_clicked:
                st.session_state.pop("player_data", None)
                if not name.strip():
                    st.error("Enter a player name.")
                else:
                    try:
                        with st.spinner("Loading hitter, matchup, Statcast and bullpen data..."):
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
                    st.error("No current-season hitting stats were found.")
                else:
                    st.markdown(
                        f"""
                        <div class="ks-feature">
                          <div class="ks-eyebrow">Player loaded</div>
                          <div class="ks-feature-name">{h(player['name'])}</div>
                          <div class="ks-feature-meta">{h(player['team_name'])} • Bats {h(player['bat_side'])} • {h(stats['season'])}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    summary1, summary2, summary3, summary4 = st.columns(4)
                    with summary1:
                        st.metric("AVG", stats["avg"])
                    with summary2:
                        st.metric("OPS", stats["ops"])
                    with summary3:
                        st.metric("Hits", stats["hits"])
                    with summary4:
                        st.metric("HR", stats["home_runs"])

                    with st.expander("🔥 Recent form + Statcast", expanded=False):
                        if recent and recent.get("avg") is not None:
                            metric_grid(
                                [
                                    ("Last-10 AVG", f"{recent['avg']:.3f}"),
                                    ("Hits", recent["hits"]),
                                    ("AB", recent["at_bats"]),
                                    ("Hit Games", f"{recent['hit_games']}/{recent['games']}"),
                                ]
                            )
                        if statcast_data:
                            st.caption("Statcast contact quality")
                            metric_grid(
                                [
                                    ("xBA", f"{statcast_data['xba']:.3f}" if statcast_data.get("xba") is not None else "N/A"),
                                    ("Exit Velo", f"{statcast_data['avg_ev']:.1f}" if statcast_data.get("avg_ev") is not None else "N/A"),
                                    ("Hard-Hit", f"{statcast_data['hard_hit_rate'] * 100:.1f}%" if statcast_data.get("hard_hit_rate") is not None else "N/A"),
                                    ("Barrel", f"{statcast_data['barrel_rate'] * 100:.1f}%" if statcast_data.get("barrel_rate") is not None else "N/A"),
                                ]
                            )

                    with st.expander("⚔️ Matchup + starting pitcher", expanded=True):
                        if matchup_data:
                            metric_grid(
                                [
                                    ("Opponent", matchup_data["opponent"]),
                                    ("Venue", matchup_data.get("venue_name", "N/A")),
                                    ("First Pitch", matchup_data["first_pitch"]),
                                    ("Status", matchup_data["status"]),
                                ]
                            )
                            if pitcher:
                                st.caption("Opposing starter")
                                metric_grid(
                                    [
                                        ("Pitcher", pitcher["name"]),
                                        ("Throws", pitcher["hand"]),
                                        ("ERA", pitcher["era"]),
                                        ("WHIP", pitcher["whip"]),
                                        ("W-L", f"{pitcher['wins']}-{pitcher['losses']}"),
                                        ("Starts", pitcher["games_started"]),
                                        ("IP", pitcher["innings"]),
                                        ("K/9", f"{pitcher['k9']:.2f}" if pitcher.get("k9") is not None else "N/A"),
                                    ]
                                )

                            starter_split = (
                                split_r if pitcher and pitcher.get("hand") == "R"
                                else split_l if pitcher and pitcher.get("hand") == "L"
                                else None
                            )
                            if starter_split:
                                st.caption("Batter split vs starter hand")
                                metric_grid(
                                    [
                                        ("Split AVG", starter_split["avg"]),
                                        ("Split OPS", starter_split["ops"]),
                                        ("Split Hits", starter_split["hits"]),
                                        ("Split AB", starter_split["at_bats"]),
                                    ]
                                )
                        else:
                            st.warning("No game found today for this player’s team.")

                    with st.expander("🧯 Bullpen + park/weather", expanded=False):
                        if bullpen_data:
                            metric_grid(
                                [
                                    ("Bullpen ERA", f"{bullpen_data['era']:.2f}"),
                                    ("Bullpen WHIP", f"{bullpen_data['whip']:.2f}"),
                                    ("Bullpen K/9", f"{bullpen_data['k9']:.2f}"),
                                    ("RHP Mix", f"{bullpen_data['right_share'] * 100:.0f}%"),
                                ]
                            )
                        if matchup_data:
                            ev = env_adj(environment_data, matchup_data.get("venue_name", "Unknown"))
                            st.caption("Game environment")
                            metric_grid(
                                [
                                    ("Ballpark", ev["venue_name"]),
                                    ("Temp", f"{ev['temperature']:.0f}°F" if ev["temperature"] is not None else "N/A"),
                                    ("Condition", ev["condition"]),
                                    ("Environment", ev["grade"]),
                                ]
                            )

                    confirmed = data.get("confirmed_lineup")
                    estimated = data.get("recent_lineup")
                    projected = int(confirmed) if confirmed else int(estimated["position"]) if estimated else 4
                    source = (
                        "Confirmed today" if confirmed
                        else f"Recent estimate ({estimated['sample_games']} games)" if estimated
                        else "Manual fallback"
                    )

                    section_header("Projection Controls", f"Lineup source: {source}")
                    set1, set2, set3 = st.columns(3)
                    with set1:
                        spot = st.selectbox("Batting spot", list(range(1, 10)), index=projected - 1)
                    with set2:
                        expected_ab = st.number_input("Projected AB", 2.5, 6.0, float(ab_for_spot(spot)), 0.1)
                    with set3:
                        mode = st.selectbox(
                            "Simulation size",
                            ["Quick — 500K", "Standard — 5M", "Deep — 10M"],
                            index=1,
                        )

                    sim_n = {"Quick — 500K": 500_000, "Standard — 5M": 5_000_000, "Deep — 10M": 10_000_000}[mode]

                    if st.button("🔥 RUN DEEP PROJECTION", use_container_width=True, type="primary"):
                        base = sf(stats["avg"], 0) or 0
                        model = model_inputs(
                            base, spot, matchup_data, pitcher, split_r, split_l,
                            recent, environment_data, statcast_data, bullpen_data,
                        )
                        exposure = starter_exposure(pitcher, expected_ab)
                        deterministic = combined(
                            model["starter_rate"], model["bullpen_rate"],
                            exposure["starter_ab"], exposure["bullpen_ab"],
                        )
                        seed = sim_seed(player["id"], (matchup_data or {}).get("game_pk", 0))

                        with st.spinner(f"Running {sim_n:,} simulations..."):
                            sim = monte(
                                model["starter_rate"], model["bullpen_rate"], expected_ab,
                                exposure["starter_share"], model["split_weight"],
                                model["statcast_model"].get("reliability", 0),
                                model["pitcher_quality"].get("reliability", 0) if model["pitcher_quality"] else 0,
                                model["bullpen_quality"].get("reliability", 0) if model["bullpen_quality"] else 0,
                                sim_n, seed,
                            )

                        grade, score = confidence(
                            stats, pitcher, model["starter_split"], recent, confirmed,
                            environment_data, statcast_data, bullpen_data, sim,
                        )
                        season_base = p_from_avg(base, expected_ab)

                        render_probability_feature(
                            player["name"],
                            player["team_name"],
                            (matchup_data or {}).get("opponent", "No current opponent"),
                            sim,
                            grade,
                        )

                        metric_grid(
                            [
                                ("0 Hits", f"{sim['p_zero'] * 100:.1f}%"),
                                ("Exactly 1", f"{sim['p_exact_one'] * 100:.1f}%"),
                                ("3+ Hits", f"{sim['p_three_plus'] * 100:.1f}%"),
                                ("Fair 1+", odds(sim["p_one_plus"])),
                            ]
                        )

                        with st.expander("🧠 Model stack", expanded=False):
                            metric_grid(
                                [
                                    ("Season AVG", f"{base:.3f}"),
                                    ("Starter Rate", f"{model['starter_rate']:.3f}"),
                                    ("Bullpen Rate", f"{model['bullpen_rate']:.3f}"),
                                    ("Expected AB", f"{expected_ab:.1f}"),
                                    ("Starter Exposure", f"{exposure['starter_share'] * 100:.0f}%"),
                                    ("Deterministic 1+", f"{deterministic['p_one_plus'] * 100:.1f}%"),
                                    ("Environment", f"{model['env_model']['total_adjustment'] * 100:+.1f}%"),
                                    ("Contact", f"{model['statcast_model']['quality_adjustment'] * 100:+.1f}%"),
                                ]
                            )

                        with st.expander("🎲 Simulation diagnostics", expanded=False):
                            metric_grid(
                                [
                                    ("Simulations", f"{sim['simulations']:,}"),
                                    ("Batches", sim["batches"]),
                                    ("Convergence", "PASS" if sim["converged"] else "CHECK"),
                                    ("MC SE", f"{sim['mc_se'] * 100:.3f} pts"),
                                    ("Batch Spread", f"{sim['batch_range'] * 100:.2f} pts"),
                                    ("90% Range", f"{sim['scenario_low'] * 100:.1f}%–{sim['scenario_high'] * 100:.1f}%"),
                                    ("Median Hits", sim["median_hits"]),
                                    ("Mode Hits", sim["mode_hits"]),
                                ]
                            )

                        st.caption(
                            f"Season AVG + today’s {expected_ab:.1f} AB baseline: {season_base['p_one_plus'] * 100:.1f}% • Data layers: {score}/8 • Model V13"
                        )

                        if matchup_data and actionable(matchup_data.get("status"), include_live=False):
                            added, total = save_single_snapshot(
                                player, matchup_data, pitcher, spot, expected_ab,
                                sim, grade, score, model_version="V13",
                            )
                            if added:
                                st.info(f"Pregame projection saved to calibration history • {total} total row(s).")
                            else:
                                st.caption("This player/game already has a V13 pregame prediction in history.")
                        else:
                            st.warning("Live/final or no-current-game result was not saved to calibration history.")

        # ----------------------------------------------------
        # BACKTEST
        # ----------------------------------------------------
        with backtest_tab:
            section_header(
                "Prediction History & Calibration",
                "Record first-look pregame probabilities, grade official results, and measure whether the model is calibrated.",
            )

            history = load_history()
            if history.empty:
                st.markdown(
                    '<div class="ks-note"><b>No clean pregame history yet.</b> Run the Top Picks scanner or a single-player projection before a game starts. V13 will save the first clean prediction automatically.</div>',
                    unsafe_allow_html=True,
                )

            grade_col, backup_col = st.columns([1, 1])
            with grade_col:
                if st.button("🔄 GRADE FINISHED GAMES", use_container_width=True, type="primary"):
                    with st.spinner("Checking official MLB results..."):
                        summary = grade_finished_games()
                    st.success(
                        f"Graded {summary['graded']} • DNP {summary['dnp']} • Void {summary['void']} • Pending {summary['still_pending']}"
                    )
                    if summary["errors"]:
                        st.warning(f"{summary['errors']} result lookup(s) could not be completed right now.")
                    history = load_history()

            with backup_col:
                if not history.empty:
                    st.download_button(
                        "⬇️ DOWNLOAD HISTORY CSV",
                        data=history_download_bytes(history),
                        file_name="kyre_sports_ai_v13_history.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

            if not history.empty:
                metrics = calibration_metrics(history)
                top5 = top5_performance(history)
                stored = len(history)
                pending = int(history["grade_status"].fillna("PENDING").eq("PENDING").sum())

                section_header("Calibration Scoreboard", "Lower Brier score and log loss are better.")
                metric_grid(
                    [
                        ("Stored", stored),
                        ("Graded", metrics["graded"]),
                        ("Pending", pending),
                        ("Actual Hit Rate", f"{metrics['hit_rate'] * 100:.1f}%" if metrics["graded"] else "N/A"),
                        ("Avg Projected", f"{metrics['avg_prediction'] * 100:.1f}%" if metrics["graded"] else "N/A"),
                        ("Calibration Gap", f"{metrics['calibration_gap'] * 100:+.1f} pts" if metrics["graded"] else "N/A"),
                        ("Brier", f"{metrics['brier']:.3f}" if metrics["graded"] else "N/A"),
                        ("Log Loss", f"{metrics['log_loss']:.3f}" if metrics["graded"] else "N/A"),
                    ]
                )

                st.subheader("🏆 Ranked-pick performance")
                metric_grid(
                    [
                        ("Top-5 Graded", top5["predictions"]),
                        ("Top-5 Hit Rate", f"{top5['hit_rate'] * 100:.1f}%" if top5["predictions"] else "N/A"),
                        ("#1 Hit Rate", f"{top5['rank1_rate'] * 100:.1f}%" if top5["predictions"] and not pd.isna(top5["rank1_rate"]) else "N/A"),
                    ],
                    3,
                )

                with st.expander("🎯 Calibration by probability tier", expanded=False):
                    cal = calibration_table(history)
                    if cal.empty:
                        st.info("Probability tiers will appear after predictions are graded.")
                    else:
                        st.dataframe(cal, use_container_width=True, hide_index=True)

                with st.expander("🧪 Model-version performance", expanded=False):
                    versions = model_version_table(history)
                    if not versions.empty:
                        st.dataframe(versions, use_container_width=True, hide_index=True)

                with st.expander("🗂️ Prediction history", expanded=True):
                    display = history.copy()
                    for col_name in ("predicted_p1", "predicted_p2", "predicted_p3"):
                        display[col_name] = pd.to_numeric(display[col_name], errors="coerce").map(
                            lambda x: f"{x * 100:.1f}%" if pd.notna(x) else ""
                        )
                    columns = [
                        "created_at_et", "model_version", "source", "rank", "player_name",
                        "team", "opponent", "predicted_p1", "confidence", "grade_status",
                        "actual_hits", "actual_1plus",
                    ]
                    display = display[[c for c in columns if c in display.columns]].rename(
                        columns={
                            "created_at_et": "Saved ET",
                            "model_version": "Model",
                            "source": "Source",
                            "rank": "Rank",
                            "player_name": "Player",
                            "team": "Team",
                            "opponent": "Opp",
                            "predicted_p1": "Proj 1+",
                            "confidence": "Conf",
                            "grade_status": "Status",
                            "actual_hits": "Hits",
                            "actual_1plus": "1+?",
                        }
                    )
                    st.dataframe(display.iloc[::-1].head(100), use_container_width=True, hide_index=True)

            with st.expander("♻️ Restore a history backup", expanded=False):
                st.caption("Free Streamlit local storage can reset after redeploys/restarts. Keep a CSV backup periodically.")
                upload = st.file_uploader("Upload V13 history CSV", type=["csv"])
                if upload is not None and st.button("MERGE HISTORY BACKUP", use_container_width=True):
                    result = merge_uploaded_history(upload)
                    if result["ok"]:
                        st.success(result["message"])
                    else:
                        st.error(result["message"])

            st.caption(
                "Calibration Gap = actual hit rate minus average projected probability. The goal is a gap that trends toward 0 as the sample grows."
            )

    else:
        section_header(f"MLB {market}", "This market module is not built yet.")
        st.info("The current production model is MLB 1+ Hit. Other MLB markets can be added without changing the V13 1+ Hit engine.")


# ============================================================
# WNBA PLACEHOLDER
# ============================================================

else:
    section_header(f"WNBA {market}", "WNBA model workspace")
    st.info("The WNBA interface is ready for its own model modules. The MLB V13 engine remains untouched.")


st.markdown(
    """
    <div class="ks-footer">
      <span><b>KYRE SPORTS AI</b> • Model V13 • UI V14</span>
      <span>Probabilities are model estimates — not guarantees.</span>
    </div>
    """,
    unsafe_allow_html=True,
)
