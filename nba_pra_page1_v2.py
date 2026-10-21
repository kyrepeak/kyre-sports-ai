"""NBA PRA Page 1/3 — Command Center V2."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Mapping

from nba_pra_page1_api_only_v1 import load_page1_snapshot_v2
from nba_pra_page1_model_v1 import grade_market, project_pra
from nba_pra_page1_ui_v2 import FILTER_OPTIONS, SESSION_PLAYER, build_game_card_html, build_player_card_html, css, dashboard_kpis

MODEL_VERSION = "NBA PRA PAGE 1/3 • COMMAND CENTER V2"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
SOURCE_DIAGNOSTICS_MARKER = "NBA_PRA_SOURCE_DIAGNOSTICS_V1"


def source_diagnostic_summary(snapshot: Mapping[str, Any]) -> dict[str, str]:
    sources = dict(snapshot.get("sources") or {})
    payload = dict(sources.get("kyre_sports_api") or {})
    verification = str(payload.get("verification") or "UNAVAILABLE").strip().upper()
    diagnostic = str(payload.get("diagnostic_state") or "NO_DIAGNOSTIC").strip()
    return {
        "runtime_marker": SOURCE_DIAGNOSTICS_MARKER,
        "kyre_sports_api": f"{verification} • {diagnostic}",
    }


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def build_items(snapshot: Mapping[str, Any], *, now_utc: datetime | None = None) -> list[dict[str, Any]]:
    profiles, injuries = snapshot.get("profiles") or {}, snapshot.get("injury_players") or {}
    items: list[dict[str, Any]] = []
    for key, market in (snapshot.get("market") or {}).items():
        featured = dict(market.get("featured_quote") or {})
        if featured.get("line") is None:
            continue
        profile = dict(profiles.get(key) or {"player_name": market.get("player_name")})
        model = project_pra(profile.get("current_games") or [], profile.get("prior_games") or [])
        grade = grade_market(model.get("projection"), featured.get("line"), model.get("sigma"))
        injury = injuries.get(key) or injuries.get(_norm(profile.get("player_name"))) or {}
        items.append({
            "key": key,
            "player_name": profile.get("player_name") or market.get("player_name") or "Player",
            "team": profile.get("team") or featured.get("team") or "",
            "position": profile.get("position") or "",
            "headshot": profile.get("headshot") or "",
            "stats_source": profile.get("stats_source") or "History unavailable",
            "availability": injury.get("status") or "No verified injury flag",
            "quotes": list(market.get("quotes") or []),
            "featured_quote": featured,
            "model": model,
            "grade": grade,
        })

    def rank(item):
        grade = item["grade"]
        p = grade.get("over_probability")
        certainty = max(float(p), 1.0 - float(p)) if p is not None else 0.0
        edge = abs(float(grade.get("edge"))) if grade.get("edge") is not None else 0.0
        return certainty, edge

    return sorted(items, key=rank, reverse=True)


def _filter_items(items: list[dict[str, Any]], selected: str) -> list[dict[str, Any]]:
    if selected == "BEST EDGES":
        return [x for x in items if x["grade"].get("lean") in {"OVER", "UNDER"}][:10]
    if selected == "OVER":
        return [x for x in items if x["grade"].get("lean") == "OVER"]
    if selected == "UNDER":
        return [x for x in items if x["grade"].get("lean") == "UNDER"]
    if selected == "HIGH CONFIDENCE":
        return [x for x in items if x["grade"].get("confidence") == "HIGH"]
    return items


def render_nba_pra_page1_v2() -> None:
    import streamlit as st

    now = datetime.now(timezone.utc)
    st.markdown(css(), unsafe_allow_html=True)
    st.markdown(
        '<div class="np2-hero"><div class="np2-kicker">KYRE SPORTS AI • NBA PRA COMMAND CENTER</div>'
        '<div class="np2-title">NBA PRA Intelligence</div>'
        '<div class="np2-sub">Find the strongest Points + Rebounds + Assists opportunities fast — live sportsbook-specific lines, player analytics, model projections, and upcoming games in one decision surface.</div>'
        '<div class="np2-status"><span>KYRE SPORTS API PRIMARY</span><span>SMART SOURCE ROUTING</span><span>LIVE MULTI-BOOK</span><span>NO LINE AVERAGING</span><span>SPORTSBOOK INFLUENCE 0.0%</span></div></div>',
        unsafe_allow_html=True,
    )
    with st.spinner("Loading verified NBA PRA intelligence…"):
        snapshot = load_page1_snapshot_v2(now=now)

    games = list(snapshot.get("games") or [])
    if not games:
        st.info("No upcoming NBA games are currently eligible. Live, completed, canceled, postponed, and ambiguous games are intentionally hidden.")
        return

    items = build_items(snapshot, now_utc=now)
    slate = escape(str(snapshot.get("slate_date") or "—"))
    st.markdown(
        f'<div class="np2-sec"><b>UPCOMING NBA SLATE • {slate}</b><span>{len(games)} games • Phoenix time</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="np2-games">' + "".join(build_game_card_html(g) for g in games) + "</div>", unsafe_allow_html=True)

    kpis = dashboard_kpis(items, now_utc=now)
    over = f"+{kpis['best_over_edge']:.1f}" if kpis["best_over_edge"] is not None else "—"
    under = f"{kpis['best_under_edge']:.1f}" if kpis["best_under_edge"] is not None else "—"
    freshness = f"{kpis['fresh_quotes']}/{kpis['players_tracked']}" if kpis["players_tracked"] else "0/0"
    st.markdown(
        '<div class="np2-kpis">'
        f'<div class="np2-kpi"><small>PLAYERS TRACKED</small><b>{kpis["players_tracked"]}</b><em>verified PRA markets</em></div>'
        f'<div class="np2-kpi"><small>BEST OVER EDGE</small><b>{over}</b><em>PRA vs featured line</em></div>'
        f'<div class="np2-kpi"><small>BEST UNDER EDGE</small><b>{under}</b><em>PRA vs featured line</em></div>'
        f'<div class="np2-kpi"><small>FRESH MARKET</small><b>{freshness}</b><em>≤ 120 sec</em></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    diagnostics = source_diagnostic_summary(snapshot)
    with st.expander("Kyre Sports API • Sources & Diagnostics", expanded=False):
        st.caption(diagnostics["runtime_marker"])
        st.write({"Kyre Sports API": diagnostics["kyre_sports_api"]})

    if not items:
        st.warning("PRA market or model history is unavailable for the upcoming slate. No line, price, or probability was fabricated.")
        return

    selected = st.radio("PRA filters", FILTER_OPTIONS, horizontal=True, label_visibility="collapsed", key="np2-filter")
    ranked = _filter_items(items, selected)
    st.markdown(
        '<div class="np2-sec"><b>KYRE AI • TOP PRA EDGES</b><span>ranked by model certainty, then edge</span></div>',
        unsafe_allow_html=True,
    )
    featured = ranked[:3]
    if featured:
        columns = st.columns(len(featured))
        for index, item in enumerate(featured, start=1):
            with columns[index - 1]:
                st.markdown(build_player_card_html(item, rank=index, now_utc=now), unsafe_allow_html=True)
                if st.button(f"Analyze {item['player_name']}", key=f"np2-featured-{item['key']}", use_container_width=True):
                    st.session_state[SESSION_PLAYER] = item["key"]

    st.markdown(
        '<div class="np2-sec"><b>ALL UPCOMING PRA MARKETS</b><span>sportsbook quotes remain separate</span></div>',
        unsafe_allow_html=True,
    )
    market_rows = items if selected == "BEST EDGES" else ranked
    for start in range(0, len(market_rows), 2):
        columns = st.columns(2)
        for offset, item in enumerate(market_rows[start:start + 2]):
            with columns[offset]:
                st.markdown(build_player_card_html(item, now_utc=now), unsafe_allow_html=True)
                if st.button(f"View {item['player_name']} on Page 2", key=f"np2-all-{item['key']}", use_container_width=True):
                    st.session_state[SESSION_PLAYER] = item["key"]
