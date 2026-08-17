import pandas as pd
import streamlit as st

import moneyline_hub_v16 as base
from spread_engine import recent_team_form

MODEL_VERSION = "V16.1"


def _record(form):
    if not form or not form.get("games"):
        return "N/A"
    games = int(form.get("games") or 0)
    wins = int(round(float(form.get("win_pct", 0) or 0) * games))
    wins = max(0, min(wins, games))
    return f"{wins}-{games - wins}"


def _h2h_record(games):
    if not games:
        return "N/A"
    wins = sum(1 for g in games if float(g.get("margin", 0) or 0) > 0)
    return f"{wins}-{len(games) - wins}"


def _recent5(team_id):
    try:
        return recent_team_form(int(team_id), 5)
    except Exception:
        return None


def _selected_forms(result):
    model = result.get("model") or {}
    if result.get("selected_side") == "home":
        team10 = model.get("home_recent")
        opp10 = model.get("away_recent")
        opp_id = result.get("away_team_id")
    else:
        team10 = model.get("away_recent")
        opp10 = model.get("home_recent")
        opp_id = result.get("home_team_id")
    return team10, _recent5(result.get("team_id")), opp10, _recent5(opp_id)


def _fmt_form(form):
    if not form:
        return "N/A"
    return (
        f'{_record(form)} • R/G {float(form.get("runs_per_game", 0) or 0):.2f} • '
        f'RA/G {float(form.get("runs_allowed_per_game", 0) or 0):.2f} • '
        f'Diff {float(form.get("run_diff_per_game", 0) or 0):+.2f}'
    )


def _render_cards_v161(results, status_info, team_logo, h):
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for rank, result in enumerate(results[:5], 1):
        status_label, status_css = status_info(result.get("status"))
        badge = base._badge_class(result.get("confidence"))
        first = " ks-first" if rank == 1 else ""
        logo = team_logo(result.get("team_id"))
        history = result.get("history") or {}
        summary = history.get("summary") or {}
        h2h_games = history.get("games") or []
        h2h10 = _h2h_record(h2h_games[:10])
        h2h5 = _h2h_record(h2h_games[:5])
        team10, team5, opp10, opp5 = _selected_forms(result)
        score = (
            f'{result["away_name"]} {result["away_score"]:.1f} — '
            f'{result["home_name"]} {result["home_score"]:.1f}'
        )
        avg_margin = summary.get("avg_margin")
        avg_margin_text = f"{float(avg_margin):+.1f}" if avg_margin is not None else "N/A"

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
            f'<span class="ks-mini">H2H L10 {h(h2h10)}</span>'
            f'<span class="ks-mini">L10 {_record(team10)}</span>'
            f'<span class="ks-mini">L5 {_record(team5)}</span>'
            '</div><details class="ks-card-details"><summary>＋ H2H + recent form</summary>'
            '<div class="ks-detail-body">'
            f'<b>H2H:</b> Last 10 {h(h2h10)} • Last 5 {h(h2h5)} • Avg margin {h(avg_margin_text)} • Current season {h(summary.get("current_season_record", "0-0"))}<br>'
            f'<b>{h(result["team"])}:</b> L10 {h(_fmt_form(team10))}<br>'
            f'<b>{h(result["team"])}:</b> L5 {h(_fmt_form(team5))}<br>'
            f'<b>{h(result["opponent"])}:</b> L10 {h(_fmt_form(opp10))}<br>'
            f'<b>{h(result["opponent"])}:</b> L5 {h(_fmt_form(opp5))}<br>'
            f'<b>Model:</b> Core win {result["core_prob"] * 100:.1f}% • History adj {result["history_effect"] * 100:+.1f} pts • One-run {result["one_run"] * 100:.1f}%'
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


def _history_rows(history, team_name, opponent_name):
    rows = []
    for game in (history or {}).get("games", [])[:10]:
        team_runs = float(game.get("team_runs", 0) or 0)
        opp_runs = float(game.get("opponent_runs", 0) or 0)
        margin = team_runs - opp_runs
        rows.append({
            "Date": game.get("date", ""),
            "Result": "W" if margin > 0 else "L",
            "Score": f"{team_name} {team_runs:.0f} - {opponent_name} {opp_runs:.0f}",
            "Margin": f"{margin:+.0f}",
            "Location": str(game.get("location", "")).title(),
        })
    return rows


def _team_form_row(name, form10, form5, h2h):
    summary = (h2h or {}).get("summary") or {}
    games = (h2h or {}).get("games") or []
    return {
        "Team": name,
        "Last 10": _record(form10),
        "L10 R/G": f'{float((form10 or {}).get("runs_per_game", 0) or 0):.2f}' if form10 else "N/A",
        "L10 Diff": f'{float((form10 or {}).get("run_diff_per_game", 0) or 0):+.2f}' if form10 else "N/A",
        "Last 5": _record(form5),
        "L5 R/G": f'{float((form5 or {}).get("runs_per_game", 0) or 0):.2f}' if form5 else "N/A",
        "L5 Diff": f'{float((form5 or {}).get("run_diff_per_game", 0) or 0):+.2f}' if form5 else "N/A",
        "H2H L10": _h2h_record(games[:10]),
        "H2H L5": _h2h_record(games[:5]),
        "H2H Avg Margin": f'{float(summary.get("avg_margin", 0) or 0):+.1f}' if summary.get("games") else "N/A",
    }


def _render_analyzer_history_panel(section_header):
    result = st.session_state.get("v16_moneyline_game_result")
    if not result:
        return
    model = result.get("model") or {}
    away10 = model.get("away_recent")
    home10 = model.get("home_recent")
    away5 = _recent5(result.get("away_team_id"))
    home5 = _recent5(result.get("home_team_id"))
    away_history = result.get("away_history") or {}
    home_history = result.get("home_history") or {}

    section_header(
        "H2H History + Recent Form — V16.1",
        "Last 10 and last 5 overall games are shown separately from head-to-head history.",
    )
    st.dataframe(
        pd.DataFrame([
            _team_form_row(result["away_name"], away10, away5, away_history),
            _team_form_row(result["home_name"], home10, home5, home_history),
        ]),
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("📚 Last 10 head-to-head meetings"):
        rows = _history_rows(away_history, result["away_name"], result["home_name"])
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("No recent head-to-head games were found in the history window.")

    st.caption(
        "Last 10 / Last 5 = each team's most recent completed games overall. H2H L10 / L5 = only meetings between these two teams. V16.1 is a display upgrade; the V16 moneyline probability math is unchanged."
    )


def _section_header_v161(section_header):
    def wrapped(title, subtitle=""):
        title = title.replace("V16", "V16.1")
        title = title.replace("Today's Strongest Moneyline Projections", "Selected Slate's Strongest Moneyline Projections")
        subtitle = subtitle.replace("V16", "V16.1")
        return section_header(title, subtitle)
    return wrapped


def render_moneyline_hub(games_df, section_header, status_info, team_logo, h):
    section = _section_header_v161(section_header)
    scanner_tab, analyzer_tab = st.tabs([
        "🏆 Moneyline Scanner",
        "🔎 Game Analyzer",
    ])

    with scanner_tab:
        old_renderer = base._render_cards
        try:
            base._render_cards = _render_cards_v161
            base._render_scanner(games_df, section, status_info, team_logo, h)
        finally:
            base._render_cards = old_renderer

    with analyzer_tab:
        base._render_analyzer(games_df, section, status_info, team_logo, h)
        _render_analyzer_history_panel(section)
