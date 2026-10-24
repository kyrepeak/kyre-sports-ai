'''NBA PRA Page 1 provider-independence command center.'''
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any, Mapping

from nba_pra_page1_api_only_provider_independence_v1 import load_page1_snapshot_v2
from nba_pra_page1_model_v1 import grade_market, project_pra
from nba_pra_runtime_v2 import select_player_for_analysis
from nba_pra_page1_ui_provider_independence_v1 import (
    FILTER_OPTIONS,
    build_game_card_html,
    build_kpi_strip_html,
    build_leaderboard_row_html,
    build_market_row_html,
    css,
    dashboard_kpis,
)

MODEL_VERSION = "NBA PRA PAGE 1/3 • PROVIDER INDEPENDENCE V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
SOURCE_DIAGNOSTICS_MARKER = "NBA_PRA_SOURCE_DIAGNOSTICS_V2_PROVIDER_LOCAL"


def source_diagnostic_summary(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    sources = dict(snapshot.get("sources") or {})
    payload = dict(sources.get("kyre_sports_api") or {})
    verification = str(payload.get("verification") or "UNAVAILABLE").strip().upper()
    diagnostic = str(payload.get("diagnostic_state") or "NO_DIAGNOSTIC").strip()
    return {
        "runtime_marker": SOURCE_DIAGNOSTICS_MARKER,
        "kyre_sports_api": f"{verification} • {diagnostic}",
        "provider_health": list(payload.get("provider_health") or []),
        "recent_participant_state": str(payload.get("recent_participant_state") or ""),
    }


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def build_items(snapshot: Mapping[str, Any], *, now_utc: datetime | None = None) -> list[dict[str, Any]]:
    del now_utc
    profiles = snapshot.get("profiles") or {}
    injuries = snapshot.get("injury_players") or {}
    market_board = snapshot.get("market") or {}
    source_payload = dict((snapshot.get("sources") or {}).get("kyre_sports_api") or {})
    global_market_state = str(source_payload.get("diagnostic_state") or "NO_APPROVED_PROVIDER_CURRENTLY_OFFERS_PRA")
    keys = sorted(set(str(key) for key in profiles) | set(str(key) for key in market_board))
    items: list[dict[str, Any]] = []

    for key in keys:
        market = dict(market_board.get(key) or {})
        profile = dict(profiles.get(key) or {"player_name": market.get("player_name")})
        if not profile.get("player_name") and not market.get("player_name"):
            continue
        featured = dict(market.get("featured_quote") or {})
        if "line" not in featured:
            featured["line"] = None
        model = project_pra(profile.get("current_games") or [], profile.get("prior_games") or [])
        baseline = profile.get("season_baseline") if isinstance(profile.get("season_baseline"), Mapping) else {}
        if model.get("projection") is None and baseline.get("pra") is not None:
            try:
                baseline_pra = round(float(baseline.get("pra")), 1)
            except (TypeError, ValueError):
                baseline_pra = None
            if baseline_pra is not None:
                model = {**model, "projection": baseline_pra, "sigma": None, "basis": "VERIFIED SEASON BASELINE"}
        grade = grade_market(model.get("projection"), featured.get("line"), model.get("sigma"))
        injury = injuries.get(key) or injuries.get(_norm(profile.get("player_name"))) or {}
        has_market = featured.get("line") is not None
        items.append(
            {
                "key": key,
                "player_name": profile.get("player_name") or market.get("player_name") or "Player",
                "team": profile.get("team") or featured.get("team") or "",
                "position": profile.get("position") or "",
                "headshot": profile.get("headshot") or "",
                "stats_source": profile.get("stats_source") or "History unavailable",
                "availability": injury.get("status") or "No verified injury flag",
                "quotes": list(market.get("quotes") or []),
                "featured_quote": featured,
                "snapshot_at_utc": str(featured.get("observed_at_utc") or ""),
                "market_state": "MARKET_AVAILABLE" if has_market else global_market_state,
                "model": model,
                "grade": grade,
            }
        )

    def rank(item):
        grade = item["grade"]
        probability = grade.get("over_probability")
        certainty = max(float(probability), 1.0 - float(probability)) if probability is not None else 0.0
        edge = abs(float(grade.get("edge"))) if grade.get("edge") is not None else 0.0
        projection = float((item.get("model") or {}).get("projection") or 0.0)
        return certainty, edge, projection

    return sorted(items, key=rank, reverse=True)


def _filter_items(items: list[dict[str, Any]], selected: str) -> list[dict[str, Any]]:
    if selected == "BEST EDGES":
        return [item for item in items if item["grade"].get("lean") in {"OVER", "UNDER"}][:10]
    if selected == "OVER":
        return [item for item in items if item["grade"].get("lean") == "OVER"]
    if selected == "UNDER":
        return [item for item in items if item["grade"].get("lean") == "UNDER"]
    if selected == "HIGH CONFIDENCE":
        return [item for item in items if item["grade"].get("confidence") == "HIGH"]
    return items


def _open_player(st, item: Mapping[str, Any]) -> None:
    select_player_for_analysis(st.session_state, item)
    st.rerun()


def render_market_player_cards(st, items: list[Mapping[str, Any]], *, now_utc: datetime | None = None) -> None:
    for item in items:
        st.markdown(build_market_row_html(item, now_utc=now_utc), unsafe_allow_html=True)
        player_name = str(item.get("player_name") or "Player").upper()
        if st.button(f"ANALYZE {player_name} →", key=f"np3-all-{item['key']}", use_container_width=False):
            _open_player(st, item)


def render_nba_pra_page1_v2() -> None:
    import streamlit as st

    now = datetime.now(timezone.utc)
    st.markdown(css(), unsafe_allow_html=True)
    st.markdown(
        '<section class="np3-command"><div><div class="np3-kicker">KYRE SPORTS AI • NBA PRA</div>'
        '<h1>NBA PRA Intelligence</h1>'
        '<p>Live player-prop decision board • sportsbook lines stay separate • model-driven analytics</p></div>'
        '<div class="np3-command-meta"><span>KYRE SPORTS API</span><span>SMART SOURCE ROUTING</span>'
        '<span>NO LINE AVERAGING</span><span>0.0% BOOK INFLUENCE</span></div></section>',
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
        f'<div class="np3-section"><b>UPCOMING NBA SLATE • {slate}</b><span>{len(games)} games • Phoenix time</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="np3-games">' + "".join(build_game_card_html(game) for game in games) + "</div>", unsafe_allow_html=True)

    kpis = dashboard_kpis(items, now_utc=now)
    st.markdown(build_kpi_strip_html(kpis), unsafe_allow_html=True)

    diagnostics = source_diagnostic_summary(snapshot)
    with st.expander("Kyre Sports API • Sources & Diagnostics", expanded=False):
        st.caption(diagnostics["runtime_marker"])
        st.write({"Kyre Sports API": diagnostics["kyre_sports_api"]})
        if diagnostics["provider_health"]:
            st.write({"Provider-local states": diagnostics["provider_health"]})
        if diagnostics["recent_participant_state"]:
            st.write({"Player pool": diagnostics["recent_participant_state"]})

    if not items:
        st.warning("No verified player history is available for the upcoming slate. No player, line, price, or probability was fabricated.")
        return

    selected = st.radio("PRA filters", FILTER_OPTIONS, horizontal=True, label_visibility="collapsed", key="np2-filter")
    ranked = _filter_items(items, selected)

    st.markdown('<div class="np3-section"><b>KYRE AI • TOP PRA EDGES</b><span>ranked by certainty, then edge</span></div>', unsafe_allow_html=True)
    featured = ranked[:3]
    if featured:
        st.markdown(
            '<div class="np3-leaderboard">'
            + "".join(build_leaderboard_row_html(item, rank=index, now_utc=now) for index, item in enumerate(featured, start=1))
            + "</div>",
            unsafe_allow_html=True,
        )
        for item in featured:
            if st.button(f"Analyze {item['player_name']} →", key=f"np3-featured-{item['key']}", use_container_width=False):
                _open_player(st, item)

    st.markdown(
        '<div class="np3-section"><b>ALL UPCOMING PRA PLAYERS</b><span>verified history remains visible even while a sportsbook market is not posted</span></div>',
        unsafe_allow_html=True,
    )
    market_rows = items if selected == "BEST EDGES" else ranked
    render_market_player_cards(st, market_rows, now_utc=now)


__all__ = ["build_items", "render_nba_pra_page1_v2", "source_diagnostic_summary"]
