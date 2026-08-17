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
# V14.2 UI — V13 MODEL MATH IS UNCHANGED
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --ks-bg:#080d16;
        --ks-panel:#0f1726;
        --ks-panel2:#131e31;
        --ks-border:rgba(148,163,184,.18);
        --ks-text:#f8fafc;
        --ks-muted:#94a3b8;
        --ks-blue:#38bdf8;
        --ks-blue2:#2563eb;
        --ks-green:#22c55e;
        --ks-yellow:#facc15;
        --ks-silver:#cbd5e1;
        --ks-bronze:#fb923c;
        --ks-red:#ef4444;
    }

    .stApp {
        background:
            radial-gradient(circle at 12% 0%,rgba(37,99,235,.14),transparent 32rem),
            var(--ks-bg);
    }

    .block-container {
        max-width:1180px;
        padding-top:1.1rem;
        padding-bottom:4rem;
    }

    .ks-hero {
        background:linear-gradient(135deg,rgba(37,99,235,.22),rgba(15,23,38,.96) 58%,rgba(56,189,248,.08));
        border:1px solid var(--ks-border);
        border-radius:22px;
        padding:22px 24px;
        margin-bottom:18px;
        box-shadow:0 20px 50px rgba(0,0,0,.22);
    }

    .ks-eyebrow {
        color:var(--ks-blue);
        font-size:.75rem;
        font-weight:900;
        letter-spacing:.13em;
        text-transform:uppercase;
    }

    .ks-title {
        color:var(--ks-text);
        font-size:clamp(2rem,5vw,3.1rem);
        line-height:1;
        font-weight:950;
        letter-spacing:-.045em;
        margin-top:5px;
    }

    .ks-subtitle {
        color:var(--ks-muted);
        font-size:.95rem;
        margin:.65rem 0 0;
    }

    .ks-pills {
        display:flex;
        flex-wrap:wrap;
        gap:7px;
        margin-top:14px;
    }

    .ks-pill {
        display:inline-flex;
        align-items:center;
        gap:6px;
        border:1px solid var(--ks-border);
        border-radius:999px;
        background:rgba(15,23,42,.72);
        color:#cbd5e1;
        padding:6px 9px;
        font-size:.74rem;
        font-weight:800;
        white-space:nowrap;
    }

    .ks-dot {
        width:7px;
        height:7px;
        border-radius:50%;
        background:var(--ks-green);
        box-shadow:0 0 10px rgba(34,197,94,.7);
    }

    .ks-section {
        margin:22px 0 10px;
    }

    .ks-section h2 {
        margin:0;
        color:var(--ks-text);
        font-size:1.45rem;
        letter-spacing:-.025em;
    }

    .ks-kicker {
        color:var(--ks-muted);
        font-size:.82rem;
        margin-top:3px;
    }

    .ks-updated {
        display:inline-flex;
        align-items:center;
        gap:6px;
        color:#cbd5e1;
        background:rgba(56,189,248,.07);
        border:1px solid rgba(56,189,248,.16);
        border-radius:999px;
        padding:5px 9px;
        font-size:.72rem;
        font-weight:750;
        margin:0 0 8px;
    }

    /* V14.2 horizontal ranking cards */
    .ks-pick-card {
        display:grid;
        grid-template-columns:70px minmax(0,1fr) 155px;
        gap:14px;
        align-items:center;
        background:linear-gradient(180deg,rgba(19,30,49,.97),rgba(10,17,29,.97));
        border:1px solid var(--ks-border);
        border-radius:17px;
        padding:14px 16px;
        margin:9px 0;
        box-shadow:0 8px 24px rgba(0,0,0,.12);
    }

    .ks-pick-card.ks-first {
        border-color:rgba(250,204,21,.55);
        box-shadow:0 12px 34px rgba(37,99,235,.15), inset 3px 0 0 rgba(250,204,21,.7);
    }

    .ks-rank {
        font-size:.73rem;
        font-weight:950;
        letter-spacing:.07em;
        text-transform:uppercase;
        white-space:nowrap;
    }

    .ks-rank-1 { color:var(--ks-yellow); }
    .ks-rank-2 { color:var(--ks-silver); }
    .ks-rank-3 { color:var(--ks-bronze); }
    .ks-rank-other { color:var(--ks-blue); }

    .ks-player-row {
        display:flex;
        align-items:center;
        gap:10px;
        min-width:0;
    }

    .ks-team-logo {
        width:34px;
        height:34px;
        object-fit:contain;
        flex:0 0 auto;
        filter:drop-shadow(0 4px 8px rgba(0,0,0,.2));
    }

    .ks-player-copy { min-width:0; }

    .ks-player {
        color:var(--ks-text);
        font-size:1.05rem;
        font-weight:900;
        line-height:1.15;
    }

    .ks-matchup {
        color:var(--ks-muted);
        font-size:.75rem;
        line-height:1.45;
        margin-top:5px;
        overflow-wrap:anywhere;
    }

    .ks-meta-line {
        display:flex;
        flex-wrap:wrap;
        align-items:center;
        gap:6px;
        margin-top:7px;
    }

    .ks-status {
        display:inline-block;
        border-radius:999px;
        padding:3px 7px;
        font-size:.61rem;
        font-weight:950;
        letter-spacing:.05em;
        white-space:nowrap;
    }

    .ks-pregame {
        color:#bae6fd;
        background:rgba(56,189,248,.10);
        border:1px solid rgba(56,189,248,.22);
    }

    .ks-live {
        color:#fecaca;
        background:rgba(239,68,68,.12);
        border:1px solid rgba(239,68,68,.28);
        animation:ksPulse 1.6s ease-in-out infinite;
    }

    .ks-final {
        color:#cbd5e1;
        background:rgba(148,163,184,.10);
        border:1px solid rgba(148,163,184,.20);
    }

    @keyframes ksPulse {
        0%,100% { opacity:1; }
        50% { opacity:.66; }
    }

    .ks-right { text-align:right; }

    .ks-prob {
        color:white;
        font-size:1.9rem;
        font-weight:950;
        line-height:1;
        letter-spacing:-.04em;
        white-space:nowrap;
    }

    .ks-prob-label {
        color:var(--ks-muted);
        font-size:.67rem;
        margin-top:4px;
    }

    .ks-card-meta {
        display:flex;
        justify-content:flex-end;
        align-items:center;
        gap:7px;
        margin-top:8px;
        flex-wrap:wrap;
    }

    .ks-badge {
        display:inline-block;
        border-radius:999px;
        padding:4px 7px;
        font-size:.64rem;
        font-weight:950;
        letter-spacing:.04em;
        white-space:nowrap;
    }

    .ks-high {
        background:rgba(34,197,94,.14);
        color:#86efac;
        border:1px solid rgba(34,197,94,.28);
    }

    .ks-medium {
        background:rgba(245,158,11,.14);
        color:#fde68a;
        border:1px solid rgba(245,158,11,.28);
    }

    .ks-low {
        background:rgba(239,68,68,.14);
        color:#fca5a5;
        border:1px solid rgba(239,68,68,.28);
    }

    .ks-mini {
        color:#cbd5e1;
        font-size:.68rem;
        white-space:nowrap;
    }

    details.ks-card-details {
        margin-top:7px;
        color:#cbd5e1;
        font-size:.68rem;
    }

    details.ks-card-details summary {
        cursor:pointer;
        color:var(--ks-blue);
        font-weight:850;
        user-select:none;
        list-style:none;
    }

    details.ks-card-details summary::-webkit-details-marker { display:none; }

    .ks-detail-body {
        margin-top:6px;
        padding:7px 8px;
        border:1px solid var(--ks-border);
        background:rgba(2,6,23,.35);
        border-radius:9px;
        line-height:1.5;
    }

    .ks-feature {
        border:1px solid var(--ks-border);
        border-radius:19px;
        background:linear-gradient(135deg,rgba(37,99,235,.16),rgba(15,23,38,.96));
        padding:18px;
        margin:10px 0 14px;
    }

    .ks-feature-name {
        color:var(--ks-text);
        font-size:1.35rem;
        font-weight:950;
        letter-spacing:-.03em;
    }

    .ks-feature-meta {
        color:var(--ks-muted);
        margin-top:5px;
        font-size:.82rem;
        overflow-wrap:anywhere;
    }

    .ks-feature-prob {
        font-size:clamp(2.7rem,8vw,4.3rem);
        font-weight:950;
        line-height:1;
        letter-spacing:-.06em;
        color:#f8fafc;
        margin-top:13px;
    }

    .ks-note {
        border-left:3px solid var(--ks-blue);
        background:rgba(56,189,248,.06);
        padding:10px 12px;
        color:#cbd5e1;
        border-radius:0 10px 10px 0;
        font-size:.82rem;
        margin:10px 0;
    }

    .ks-live-note {
        border-left:3px solid var(--ks-red);
        background:rgba(239,68,68,.07);
        padding:10px 12px;
        color:#fecaca;
        border-radius:0 10px 10px 0;
        font-size:.8rem;
        margin:8px 0 12px;
    }

    .ks-footer {
        display:flex;
        justify-content:space-between;
        gap:12px;
        color:var(--ks-muted);
        font-size:.74rem;
        border-top:1px solid var(--ks-border);
        margin-top:34px;
        padding-top:18px;
    }

    div[data-testid="stMetric"] {
        background:rgba(15,23,38,.78);
        border:1px solid var(--ks-border);
        border-radius:13px;
        padding:9px 11px;
        min-height:88px;
    }

    div[data-testid="stMetricLabel"] { color:var(--ks-muted); }
    div[data-testid="stMetricValue"] {
        color:var(--ks-text);
        font-size:clamp(1.12rem,3vw,1.75rem);
    }

    div[data-baseweb="tab-list"] {
        gap:4px;
        overflow-x:auto;
        scrollbar-width:none;
    }

    button[data-baseweb="tab"] {
        border-radius:11px 11px 0 0;
        white-space:nowrap;
    }

    div[data-testid="stDataFrame"] {
        border:1px solid var(--ks-border);
        border-radius:13px;
        overflow:hidden;
    }

    .stButton>button,
    .stDownloadButton>button {
        border-radius:11px;
        font-weight:850;
        min-height:44px;
    }

    .stButton>button[kind="primary"] {
        background:linear-gradient(135deg,var(--ks-blue2),#0284c7) !important;
        border:1px solid rgba(125,211,252,.55) !important;
        color:white !important;
        box-shadow:0 8px 24px rgba(37,99,235,.20);
    }

    .stButton>button[kind="primary"]:hover {
        border-color:#7dd3fc !important;
        box-shadow:0 10px 28px rgba(37,99,235,.30);
    }

    div[data-testid="stExpander"] {
        border:1px solid var(--ks-border);
        border-radius:13px;
        background:rgba(15,23,38,.5);
    }

    @media(max-width:700px) {
        .block-container { padding-left:.8rem; padding-right:.8rem; }
        .ks-hero { padding:18px 16px; border-radius:17px; }
        .ks-pick-card {
            grid-template-columns:54px minmax(0,1fr) 118px;
            gap:9px;
            padding:12px;
        }
        .ks-team-logo { width:29px; height:29px; }
        .ks-prob { font-size:1.55rem; }
        .ks-player { font-size:.98rem; }
        .ks-matchup { font-size:.70rem; }
        .ks-rank { font-size:.64rem; }
        .ks-card-meta { gap:4px; }
    }

    @media(max-width:470px) {
        .ks-pick-card { grid-template-columns:1fr 96px; }
        .ks-rank { grid-column:1/-1; }
        .ks-right { grid-column:2; grid-row:2; text-align:right; }
        .ks-card-main { grid-column:1; grid-row:2; }
        .ks-footer { flex-direction:column; }
        .ks-team-logo { display:none; }
        div[data-testid="stMetric"] { min-height:80px; padding:8px; }
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


def status_info(status):
    text = str(status or "Unknown")
    low = text.lower()
    if any(x in low for x in ["final", "game over", "completed"]):
        return "FINAL", "ks-final"
    if any(x in low for x in ["in progress", "live", "delayed"]):
        return "LIVE", "ks-live"
    return "PREGAME", "ks-pregame"


def rank_class(rank):
    return {
        1: "ks-rank-1",
        2: "ks-rank-2",
        3: "ks-rank-3",
    }.get(rank, "ks-rank-other")


def team_logo(team_id):
    if team_id is None or (isinstance(team_id, float) and pd.isna(team_id)):
        return ""
    try:
        tid = int(team_id)
    except (TypeError, ValueError):
        return ""
    return (
        f'<img class="ks-team-logo" '
        f'src="https://www.mlbstatic.com/team-logos/{tid}.svg" '
        f'alt="team logo" loading="lazy">'
    )


def render_hero(game_date):
    now = datetime.now(ET).strftime("%I:%M %p ET").lstrip("0")
    html = (
        '<div class="ks-hero">'
        '<div class="ks-eyebrow">Sports projection intelligence</div>'
        '<div class="ks-title">🧠 KYRE SPORTS AI</div>'
        '<p class="ks-subtitle">MLB probability modeling, slate scanning and calibration — built for fast mobile use.</p>'
        '<div class="ks-pills">'
        '<span class="ks-pill"><span class="ks-dot"></span>Data engine online</span>'
        f'<span class="ks-pill">⚾ MLB • {h(game_date)}</span>'
        '<span class="ks-pill">🧪 Model V13</span>'
        '<span class="ks-pill">✨ UI V14.2</span>'
        f'<span class="ks-pill">🕒 {h(now)}</span>'
        '</div></div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def section_header(title, subtitle=""):
    html = (
        '<div class="ks-section">'
        f'<h2>{h(title)}</h2>'
        f'<div class="ks-kicker">{h(subtitle)}</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_pick_cards(results):
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for rank, result in enumerate(results[:5], 1):
        sim = result["sim"]
        conf = result.get("confidence", "N/A")
        badge = confidence_class(conf)
        first = " ks-first" if rank == 1 else ""
        rank_css = rank_class(rank)
        status_label, status_css = status_info(result.get("status"))
        logo = team_logo(result.get("team_id"))
        first_pitch = result.get("first_pitch") or "TBD"
        data_score = result.get("data_score", "?")
        scenario = (
            f'{sim.get("scenario_low", 0) * 100:.1f}%–'
            f'{sim.get("scenario_high", 0) * 100:.1f}%'
        )

        card = (
            f'<div class="ks-pick-card{first}">'
            f'<div class="ks-rank {rank_css}">{medals.get(rank, "•")} #{rank}</div>'
            '<div class="ks-card-main">'
            '<div class="ks-player-row">'
            f'{logo}'
            '<div class="ks-player-copy">'
            f'<div class="ks-player">{h(result["player_name"])}</div>'
            f'<div class="ks-matchup">{h(result["team"])} vs {h(result["opponent"])} • vs {h(result["starter_name"])} • Bat #{h(result["position"])}</div>'
            '</div></div>'
            '<div class="ks-meta-line">'
            f'<span class="ks-status {status_css}">{status_label}</span>'
            f'<span class="ks-mini">🕒 {h(first_pitch)} ET</span>'
            '</div>'
            '<details class="ks-card-details">'
            '<summary>＋ Matchup details</summary>'
            '<div class="ks-detail-body">'
            f'Expected hits <b>{sim["expected_hits"]:.2f}</b> • '
            f'3+ <b>{sim["p_three_plus"] * 100:.1f}%</b><br>'
            f'90% scenario range <b>{scenario}</b> • Data <b>{h(data_score)}/8</b>'
            '</div></details>'
            '</div>'
            '<div class="ks-right">'
            f'<div class="ks-prob">{sim["p_one_plus"] * 100:.1f}%</div>'
            '<div class="ks-prob-label">Projected 1+ hit</div>'
            '<div class="ks-card-meta">'
            f'<span class="ks-badge {badge}">{h(conf)}</span>'
            f'<span class="ks-mini">2+ {sim["p_two_plus"] * 100:.1f}%</span>'
            f'<span class="ks-mini">xH {sim["expected_hits"]:.2f}</span>'
            '</div></div></div>'
        )
        st.markdown(card, unsafe_allow_html=True)


def render_probability_feature(player_name, team, opponent, sim, grade):
    badge = confidence_class(grade)
    html = (
        '<div class="ks-feature">'
        f'<div class="ks-feature-name">{h(player_name)}</div>'
        f'<div class="ks-feature-meta">{h(team)} vs {h(opponent)}</div>'
        f'<div class="ks-feature-prob">{sim["p_one_plus"] * 100:.1f}%</div>'
        f'<div class="ks-feature-meta">1+ Hit Probability • 2+ {sim["p_two_plus"] * 100:.1f}% • Expected hits {sim["expected_hits"]:.2f}</div>'
        f'<div style="margin-top:11px"><span class="ks-badge {badge}">{h(grade)} CONFIDENCE</span></div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


# ============================================================
# DATA / NAV
# ============================================================

try:
    games_df, game_date = games_today()
except requests.RequestException:
    games_df = pd.DataFrame()
    game_date = datetime.now(ET).strftime("%Y-%m-%d")

render_hero(game_date)

nav1, nav2, nav3 = st.columns([1.05, 1.55, 1.0])
with nav1:
    sport = st.selectbox(
        "Sport",
        ["MLB", "WNBA"],
        label_visibility="collapsed",
    )
with nav2:
    if sport == "MLB":
        market = st.selectbox(
            "Market",
            [
                "1+ Hit",
                "2+ Hits",
                "Home Run",
                "Hits + Runs + RBIs",
                "Moneyline",
                "Run Line",
                "Game Total",
            ],
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
        '<div class="ks-pill" style="justify-content:center;min-height:42px">V13 • UI 14.2</div>',
        unsafe_allow_html=True,
    )


# ============================================================
# MLB
# ============================================================

if sport == "MLB":
    with st.expander("⚾ Today’s MLB schedule", expanded=False):
        if games_df.empty:
            st.warning("No MLB games found.")
        else:
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
                    "first_pitch_et": "ET",
                    "away_pitcher": "Away SP",
                    "home_pitcher": "Home SP",
                    "status": "Status",
                }
            )
            st.caption(f"{game_date} • MLB probable pitchers and game status")
            st.dataframe(show, use_container_width=True, hide_index=True)

    if market == "1+ Hit":
        top_tab, single_tab, backtest_tab = st.tabs(
            ["🏆 Top Picks", "🔎 Analyzer", "📈 Backtest"]
        )

        # ---------------- TOP PICKS ----------------
        with top_tab:
            section_header(
                "Daily 1+ Hit Scanner",
                "Confirmed lineups → full-slate screen → deep Monte Carlo finalists → ranked Top 5.",
            )

            c1, c2 = st.columns([1, 1.35])
            with c1:
                include_live = st.checkbox(
                    "⚠️ Include live games",
                    value=False,
                )
            with c2:
                depth = st.selectbox(
                    "Simulation depth",
                    [
                        "Fast — 100K/finalist",
                        "Standard — 500K/finalist",
                        "Deep — 1M/finalist",
                    ],
                    index=1,
                )

            if include_live:
                st.markdown(
                    '<div class="ks-live-note"><b>Live mode is ON.</b> Live-game results can be viewed, but they will not be saved to calibration history.</div>',
                    unsafe_allow_html=True,
                )

            sims = {
                "Fast — 100K/finalist": 100_000,
                "Standard — 500K/finalist": 500_000,
                "Deep — 1M/finalist": 1_000_000,
            }[depth]

            if st.button(
                "🔥 SCAN TODAY’S CONFIRMED LINEUPS",
                use_container_width=True,
                type="primary",
            ):
                if games_df.empty:
                    st.error("Today’s MLB schedule could not be loaded.")
                else:
                    with st.spinner("Reading confirmed lineups..."):
                        candidates, checked, with_lineups = slate_candidates(
                            games_df,
                            include_live,
                        )

                    if not candidates:
                        st.warning("No confirmed hitters found in actionable games.")
                    else:
                        st.info(
                            f"{len(candidates)} confirmed hitters • "
                            f"{with_lineups}/{checked} actionable games with lineups"
                        )
                        screened = []
                        bar = st.progress(0, text="Screening hitters...")
                        for i, candidate in enumerate(candidates, 1):
                            try:
                                screened.append(prescreen(candidate))
                            except Exception:
                                pass
                            bar.progress(
                                i / len(candidates),
                                text=f"Screening {i}/{len(candidates)}",
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
                            text="Running deep finalist models...",
                        )
                        for i, candidate in enumerate(finalists, 1):
                            try:
                                deep.append(deep_scan(candidate, sims))
                            except Exception:
                                pass
                            bar.progress(
                                i / max(len(finalists), 1),
                                text=f"Modeling finalist {i}/{len(finalists)}",
                            )
                        bar.empty()

                        deep.sort(
                            key=lambda x: x["sim"]["p_one_plus"],
                            reverse=True,
                        )
                        st.session_state["v13_results"] = deep
                        st.session_state["v14_scan_time"] = datetime.now(ET).strftime(
                            "%I:%M:%S %p ET"
                        ).lstrip("0")

                        if deep and not include_live:
                            added, total, _ = save_top5_snapshot(
                                deep[:5],
                                model_version="V13",
                            )
                            st.session_state["v13_save_note"] = (
                                f"Pregame calibration snapshot: {added} new • "
                                f"{total} total history rows."
                            )
                        elif include_live:
                            st.session_state["v13_save_note"] = (
                                "Live-game scan was not saved to calibration history."
                            )

            results = st.session_state.get("v13_results")
            if results:
                section_header(
                    "Today’s Strongest Projections",
                    "Probability ranking — not sportsbook value.",
                )
                scan_time = st.session_state.get("v14_scan_time")
                if scan_time:
                    st.markdown(
                        f'<div class="ks-updated">↻ Last scan {h(scan_time)}</div>',
                        unsafe_allow_html=True,
                    )

                render_pick_cards(results)

                top = results[0]
                st.markdown(
                    f'<div class="ks-note"><b>Current #1:</b> {h(top["player_name"])} • '
                    f'<b>{top["sim"]["p_one_plus"] * 100:.1f}%</b> projected 1+ • '
                    f'{h(top["confidence"])} confidence.</div>',
                    unsafe_allow_html=True,
                )

                note = st.session_state.get("v13_save_note")
                if note:
                    st.caption(note)

                with st.expander("📋 Full Top 5 table"):
                    rows = []
                    for rank, result in enumerate(results[:5], 1):
                        sim = result["sim"]
                        status_label, _ = status_info(result.get("status"))
                        rows.append(
                            {
                                "#": rank,
                                "Player": result["player_name"],
                                "Team": result["team"],
                                "Opp": result["opponent"],
                                "SP": result["starter_name"],
                                "Time": result.get("first_pitch", "TBD"),
                                "Status": status_label,
                                "Bat": f"#{result['position']}",
                                "1+": f"{sim['p_one_plus'] * 100:.1f}%",
                                "2+": f"{sim['p_two_plus'] * 100:.1f}%",
                                "xHits": f"{sim['expected_hits']:.2f}",
                                "Fair": odds(sim["p_one_plus"]),
                                "Conf": result["confidence"],
                                "Data": f"{result['data_score']}/8",
                            }
                        )
                    st.dataframe(
                        pd.DataFrame(rows),
                        use_container_width=True,
                        hide_index=True,
                    )

                with st.expander("🧪 Finalist details"):
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
                                "90% Range": (
                                    f"{sim['scenario_low'] * 100:.1f}%–"
                                    f"{sim['scenario_high'] * 100:.1f}%"
                                ),
                                "MC SE": f"{sim['mc_se'] * 100:.3f} pts",
                                "Confidence": result["confidence"],
                            }
                        )
                    st.dataframe(
                        pd.DataFrame(detail),
                        use_container_width=True,
                        hide_index=True,
                    )

        # ---------------- ANALYZER ----------------
        with single_tab:
            section_header(
                "Single-Player Analyzer",
                "Search one hitter, inspect matchup layers, then run the full V13 Monte Carlo model.",
            )

            search_col, load_col = st.columns([2.2, 1])
            with search_col:
                name = st.text_input(
                    "Player",
                    placeholder="Yordan Alvarez",
                    label_visibility="collapsed",
                )
            with load_col:
                load_clicked = st.button(
                    "📡 Load player",
                    use_container_width=True,
                )

            if load_clicked:
                st.session_state.pop("player_data", None)
                if not name.strip():
                    st.error("Enter a player name.")
                else:
                    try:
                        with st.spinner(
                            "Loading hitter, matchup, Statcast and bullpen data..."
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
                    st.error("No current-season hitting stats were found.")
                else:
                    player_logo = team_logo(player.get("team_id"))
                    st.markdown(
                        '<div class="ks-feature">'
                        '<div class="ks-eyebrow">Player loaded</div>'
                        '<div class="ks-player-row" style="margin-top:7px">'
                        f'{player_logo}'
                        '<div class="ks-player-copy">'
                        f'<div class="ks-feature-name">{h(player["name"])}</div>'
                        f'<div class="ks-feature-meta">{h(player["team_name"])} • '
                        f'Bats {h(player["bat_side"])} • {h(stats["season"])}</div>'
                        '</div></div></div>',
                        unsafe_allow_html=True,
                    )
                    metric_grid(
                        [
                            ("AVG", stats["avg"]),
                            ("OPS", stats["ops"]),
                            ("Hits", stats["hits"]),
                            ("HR", stats["home_runs"]),
                        ]
                    )

                    with st.expander("🔥 Recent form + Statcast", expanded=False):
                        if recent and recent.get("avg") is not None:
                            metric_grid(
                                [
                                    ("Last-10 AVG", f"{recent['avg']:.3f}"),
                                    ("Hits", recent["hits"]),
                                    ("AB", recent["at_bats"]),
                                    (
                                        "Hit Games",
                                        f"{recent['hit_games']}/{recent['games']}",
                                    ),
                                ]
                            )
                        if statcast_data:
                            metric_grid(
                                [
                                    (
                                        "xBA",
                                        f"{statcast_data['xba']:.3f}"
                                        if statcast_data.get("xba") is not None
                                        else "N/A",
                                    ),
                                    (
                                        "Exit Velo",
                                        f"{statcast_data['avg_ev']:.1f}"
                                        if statcast_data.get("avg_ev") is not None
                                        else "N/A",
                                    ),
                                    (
                                        "Hard-Hit",
                                        f"{statcast_data['hard_hit_rate'] * 100:.1f}%"
                                        if statcast_data.get("hard_hit_rate") is not None
                                        else "N/A",
                                    ),
                                    (
                                        "Barrel",
                                        f"{statcast_data['barrel_rate'] * 100:.1f}%"
                                        if statcast_data.get("barrel_rate") is not None
                                        else "N/A",
                                    ),
                                ]
                            )

                    with st.expander("⚔️ Matchup + starter", expanded=True):
                        if matchup_data:
                            status_label, _ = status_info(matchup_data.get("status"))
                            metric_grid(
                                [
                                    ("Opponent", matchup_data["opponent"]),
                                    ("Venue", matchup_data.get("venue_name", "N/A")),
                                    ("First Pitch", matchup_data["first_pitch"]),
                                    ("Status", status_label),
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
                                            f"{pitcher['wins']}-{pitcher['losses']}",
                                        ),
                                        ("Starts", pitcher["games_started"]),
                                        ("IP", pitcher["innings"]),
                                        (
                                            "K/9",
                                            f"{pitcher['k9']:.2f}"
                                            if pitcher.get("k9") is not None
                                            else "N/A",
                                        ),
                                    ]
                                )
                            starter_split = (
                                split_r
                                if pitcher and pitcher.get("hand") == "R"
                                else split_l
                                if pitcher and pitcher.get("hand") == "L"
                                else None
                            )
                            if starter_split:
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
                                    (
                                        "RHP Mix",
                                        f"{bullpen_data['right_share'] * 100:.0f}%",
                                    ),
                                ]
                            )
                        if matchup_data:
                            ev = env_adj(
                                environment_data,
                                matchup_data.get("venue_name", "Unknown"),
                            )
                            metric_grid(
                                [
                                    ("Ballpark", ev["venue_name"]),
                                    (
                                        "Temp",
                                        f"{ev['temperature']:.0f}°F"
                                        if ev["temperature"] is not None
                                        else "N/A",
                                    ),
                                    ("Condition", ev["condition"]),
                                    ("Environment", ev["grade"]),
                                ]
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
                        "Confirmed today"
                        if confirmed
                        else f"Recent estimate ({estimated['sample_games']} games)"
                        if estimated
                        else "Manual fallback"
                    )

                    section_header(
                        "Projection Controls",
                        f"Lineup source: {source}",
                    )
                    s1, s2, s3 = st.columns(3)
                    with s1:
                        spot = st.selectbox(
                            "Batting spot",
                            list(range(1, 10)),
                            index=projected - 1,
                        )
                    with s2:
                        expected_ab = st.number_input(
                            "Projected AB",
                            2.5,
                            6.0,
                            float(ab_for_spot(spot)),
                            0.1,
                        )
                    with s3:
                        mode = st.selectbox(
                            "Simulation size",
                            ["Quick — 500K", "Standard — 5M", "Deep — 10M"],
                            index=1,
                        )
                    sim_n = {
                        "Quick — 500K": 500_000,
                        "Standard — 5M": 5_000_000,
                        "Deep — 10M": 10_000_000,
                    }[mode]

                    if st.button(
                        "🔥 RUN DEEP PROJECTION",
                        use_container_width=True,
                        type="primary",
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
                        exposure = starter_exposure(pitcher, expected_ab)
                        deterministic = combined(
                            model["starter_rate"],
                            model["bullpen_rate"],
                            exposure["starter_ab"],
                            exposure["bullpen_ab"],
                        )
                        seed = sim_seed(
                            player["id"],
                            (matchup_data or {}).get("game_pk", 0),
                        )

                        with st.spinner(f"Running {sim_n:,} simulations..."):
                            sim = monte(
                                model["starter_rate"],
                                model["bullpen_rate"],
                                expected_ab,
                                exposure["starter_share"],
                                model["split_weight"],
                                model["statcast_model"].get("reliability", 0),
                                model["pitcher_quality"].get("reliability", 0)
                                if model["pitcher_quality"]
                                else 0,
                                model["bullpen_quality"].get("reliability", 0)
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
                        season_base = p_from_avg(base, expected_ab)
                        render_probability_feature(
                            player["name"],
                            player["team_name"],
                            (matchup_data or {}).get(
                                "opponent",
                                "No current opponent",
                            ),
                            sim,
                            grade,
                        )
                        metric_grid(
                            [
                                ("0 Hits", f"{sim['p_zero'] * 100:.1f}%"),
                                (
                                    "Exactly 1",
                                    f"{sim['p_exact_one'] * 100:.1f}%",
                                ),
                                (
                                    "3+ Hits",
                                    f"{sim['p_three_plus'] * 100:.1f}%",
                                ),
                                ("Fair 1+", odds(sim["p_one_plus"])),
                            ]
                        )

                        with st.expander("🧠 Model stack"):
                            metric_grid(
                                [
                                    ("Season AVG", f"{base:.3f}"),
                                    (
                                        "Starter Rate",
                                        f"{model['starter_rate']:.3f}",
                                    ),
                                    (
                                        "Bullpen Rate",
                                        f"{model['bullpen_rate']:.3f}",
                                    ),
                                    ("Expected AB", f"{expected_ab:.1f}"),
                                    (
                                        "Starter Exposure",
                                        f"{exposure['starter_share'] * 100:.0f}%",
                                    ),
                                    (
                                        "Deterministic 1+",
                                        f"{deterministic['p_one_plus'] * 100:.1f}%",
                                    ),
                                    (
                                        "Environment",
                                        f"{model['env_model']['total_adjustment'] * 100:+.1f}%",
                                    ),
                                    (
                                        "Contact",
                                        f"{model['statcast_model']['quality_adjustment'] * 100:+.1f}%",
                                    ),
                                ]
                            )
                        with st.expander("🎲 Simulation diagnostics"):
                            metric_grid(
                                [
                                    ("Simulations", f"{sim['simulations']:,}"),
                                    ("Batches", sim["batches"]),
                                    (
                                        "Convergence",
                                        "PASS" if sim["converged"] else "CHECK",
                                    ),
                                    (
                                        "MC SE",
                                        f"{sim['mc_se'] * 100:.3f} pts",
                                    ),
                                    (
                                        "Batch Spread",
                                        f"{sim['batch_range'] * 100:.2f} pts",
                                    ),
                                    (
                                        "90% Range",
                                        f"{sim['scenario_low'] * 100:.1f}%–"
                                        f"{sim['scenario_high'] * 100:.1f}%",
                                    ),
                                    ("Median Hits", sim["median_hits"]),
                                    ("Mode Hits", sim["mode_hits"]),
                                ]
                            )

                        st.caption(
                            f"Season AVG + today’s {expected_ab:.1f} AB baseline: "
                            f"{season_base['p_one_plus'] * 100:.1f}% • "
                            f"Data layers: {score}/8 • Model V13"
                        )

                        if matchup_data and actionable(
                            matchup_data.get("status"),
                            include_live=False,
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
                                    f"Pregame projection saved • {total} history row(s)."
                                )
                            else:
                                st.caption(
                                    "This player/game already has a V13 pregame prediction in history."
                                )
                        else:
                            st.warning(
                                "Live/final or no-current-game result was not saved to calibration history."
                            )

        # ---------------- BACKTEST ----------------
        with backtest_tab:
            section_header(
                "Prediction History & Calibration",
                "Grade clean pregame predictions against official MLB results.",
            )
            history = load_history()
            if history.empty:
                st.markdown(
                    '<div class="ks-note"><b>No clean pregame history yet.</b> Run a Top Picks scan or single-player projection before a game starts.</div>',
                    unsafe_allow_html=True,
                )

            grade_col, backup_col = st.columns(2)
            with grade_col:
                if st.button(
                    "🔄 GRADE FINISHED GAMES",
                    use_container_width=True,
                    type="primary",
                ):
                    with st.spinner("Checking official MLB results..."):
                        summary = grade_finished_games()
                    st.success(
                        f"Graded {summary['graded']} • DNP {summary['dnp']} • "
                        f"Void {summary['void']} • Pending {summary['still_pending']}"
                    )
                    if summary["errors"]:
                        st.warning(
                            f"{summary['errors']} result lookup(s) could not be completed."
                        )
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
                pending = int(
                    history["grade_status"]
                    .fillna("PENDING")
                    .eq("PENDING")
                    .sum()
                )
                section_header(
                    "Calibration Scoreboard",
                    "Lower Brier score and log loss are better.",
                )
                metric_grid(
                    [
                        ("Stored", len(history)),
                        ("Graded", metrics["graded"]),
                        ("Pending", pending),
                        (
                            "Actual Hit Rate",
                            f"{metrics['hit_rate'] * 100:.1f}%"
                            if metrics["graded"]
                            else "N/A",
                        ),
                        (
                            "Avg Projected",
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
                            "Brier",
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
                metric_grid(
                    [
                        ("Top-5 Graded", top5["predictions"]),
                        (
                            "Top-5 Hit Rate",
                            f"{top5['hit_rate'] * 100:.1f}%"
                            if top5["predictions"]
                            else "N/A",
                        ),
                        (
                            "#1 Hit Rate",
                            f"{top5['rank1_rate'] * 100:.1f}%"
                            if top5["predictions"]
                            and not pd.isna(top5["rank1_rate"])
                            else "N/A",
                        ),
                    ],
                    3,
                )

                with st.expander("🎯 Calibration by probability tier"):
                    cal = calibration_table(history)
                    if cal.empty:
                        st.info(
                            "Probability tiers appear after predictions are graded."
                        )
                    else:
                        st.dataframe(
                            cal,
                            use_container_width=True,
                            hide_index=True,
                        )
                with st.expander("🧪 Model-version performance"):
                    versions = model_version_table(history)
                    if not versions.empty:
                        st.dataframe(
                            versions,
                            use_container_width=True,
                            hide_index=True,
                        )
                with st.expander("🗂️ Prediction history", expanded=True):
                    display = history.copy()
                    for c in (
                        "predicted_p1",
                        "predicted_p2",
                        "predicted_p3",
                    ):
                        display[c] = pd.to_numeric(
                            display[c],
                            errors="coerce",
                        ).map(
                            lambda x: f"{x * 100:.1f}%"
                            if pd.notna(x)
                            else ""
                        )
                    cols = [
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
                        [c for c in cols if c in display.columns]
                    ].rename(
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
                    st.dataframe(
                        display.iloc[::-1].head(100),
                        use_container_width=True,
                        hide_index=True,
                    )

            with st.expander("♻️ Restore history backup"):
                upload = st.file_uploader(
                    "Upload V13 history CSV",
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

    else:
        section_header(
            f"MLB {market}",
            "This market module is not built yet.",
        )
        st.info("The production model currently covers MLB 1+ Hit.")

else:
    section_header(f"WNBA {market}", "WNBA model workspace")
    st.info(
        "The WNBA interface is ready for its own model modules. MLB V13 remains unchanged."
    )

st.markdown(
    '<div class="ks-footer"><span><b>KYRE SPORTS AI</b> • Model V13 • UI V14.2</span><span>Model probabilities are estimates — not guarantees.</span></div>',
    unsafe_allow_html=True,
)
