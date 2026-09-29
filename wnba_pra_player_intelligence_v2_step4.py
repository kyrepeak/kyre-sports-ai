"""WNBA Navigation V2 — Step 4 Player PRA Intelligence.

This layer is presentation-only. It reuses the frozen Step-3 selected-player
snapshot, reads the already-computed Step-18 consumer board, and reads one
official player game log. The two hosted reads execute in parallel and are
cached. Streamlit does not run a projection, sportsbook fetch, qualification,
ranking, or Monte Carlo job.

Missing certified context is displayed as N/A rather than inferred.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from html import escape
import math
from time import perf_counter
from typing import Any, Mapping

import streamlit as st

import wnba_pra_navigation_v2_step1 as navigation
import wnba_pra_slate_v2_step2 as slate
import wnba_pra_game_center_v2_step3 as game_center


MODEL_VERSION = "WNBA PRA NAVIGATION V2 • STEP 4 PLAYER INTELLIGENCE"
CACHE_TTL_SECONDS = 60
API_TIMEOUT_SECONDS = 5.0
API_ATTEMPTS = 1
PERF_KEY = "ks_wnba_pra_nav_v2_step4_perf"

PLAYER_INTELLIGENCE_CONTRACT = {
    "project": "WNBA Navigation V2",
    "step": "4/7",
    "page": "player",
    "frozen_step1_navigation_reused": True,
    "frozen_step2_slate_reused": True,
    "frozen_step3_game_center_reused": True,
    "network_reads_per_uncached_render_max": 2,
    "network_reads_parallel": True,
    "api_timeout_seconds": API_TIMEOUT_SECONDS,
    "api_attempts": API_ATTEMPTS,
    "cache_ttl_seconds": CACHE_TTL_SECONDS,
    "consumer_board_read_only": True,
    "official_game_log_read_only": True,
    "streamlit_projection_runs": 0,
    "streamlit_sportsbook_calls": 0,
    "streamlit_qualification_runs": 0,
    "streamlit_ranking_runs": 0,
    "streamlit_monte_carlo_runs": 0,
    "projection_math_changed": False,
    "market_math_changed": False,
    "sportsbook_projection_influence": 0.0,
    "missing_context_fails_closed_to_na": True,
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _int(value: Any) -> int | None:
    number = _num(value)
    if number is None:
        return None
    try:
        result = int(number)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result > 0 else None


def _fmt(value: Any, digits: int = 1, suffix: str = "") -> str:
    number = _num(value)
    return "N/A" if number is None else f"{number:.{digits}f}{suffix}"


def _pct(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "N/A"
    if abs(number) <= 1.000001:
        number *= 100.0
    return f"{number:.1f}%"


def _american(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "N/A"
    integer = int(round(number))
    return f"+{integer}" if integer > 0 else str(integer)


def _selected_player() -> dict[str, Any]:
    value = st.session_state.get(game_center.SESSION_SELECTED_PLAYER)
    return dict(value) if isinstance(value, Mapping) else {}


def _selected_game() -> dict[str, Any]:
    value = st.session_state.get(slate.SESSION_SELECTED_GAME)
    return dict(value) if isinstance(value, Mapping) else {}


def _player_headshot(player_id: Any) -> str:
    pid = _int(player_id)
    return "" if pid is None else f"https://cdn.wnba.com/headshots/wnba/latest/1040x760/{pid}.png"


def _team_logo(team_id: Any) -> str:
    tid = _int(team_id)
    return "" if tid is None else f"https://cdn.nba.com/logos/wnba/{tid}/global/L/logo.svg"


def _read_consumer() -> dict[str, Any]:
    from wnba_api_client_v1 import KyreWNBAAPIClient
    from wnba_streamlit_consumer_v2 import normalize_consumer_payload

    client = KyreWNBAAPIClient(
        timeout_seconds=API_TIMEOUT_SECONDS,
        attempts=API_ATTEMPTS,
    )
    return normalize_consumer_payload(client.consumer_latest())


def _read_history(player_id: int) -> dict[str, Any]:
    from wnba_api_client_v1 import KyreWNBAAPIClient, SUPPORTED_SEASON

    client = KyreWNBAAPIClient(
        timeout_seconds=API_TIMEOUT_SECONDS,
        attempts=API_ATTEMPTS,
    )
    return client.player_game_log(player_id, SUPPORTED_SEASON)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_player_intelligence(game_id: str, player_id: int) -> dict[str, Any]:
    """Read consumer + history concurrently; never compute a fresh model."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        consumer_future = pool.submit(_read_consumer)
        history_future = pool.submit(_read_history, int(player_id))

        consumer: dict[str, Any] | None = None
        history: dict[str, Any] | None = None
        consumer_error = ""
        history_error = ""

        try:
            consumer = consumer_future.result()
        except Exception as exc:
            consumer_error = type(exc).__name__

        try:
            history = history_future.result()
        except Exception as exc:
            history_error = type(exc).__name__

    return {
        "game_id": str(game_id),
        "player_id": int(player_id),
        "consumer": consumer,
        "history": history,
        "consumer_error": consumer_error,
        "history_error": history_error,
        "network_reads": 2,
        "projection_runs": 0,
        "sportsbook_calls": 0,
        "qualification_runs": 0,
        "ranking_runs": 0,
        "monte_carlo_runs": 0,
    }


def _exact_pra_card(view: Mapping[str, Any] | None, game_id: str, player_id: int) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(view, Mapping) or _text(view.get("state")) != "ready":
        return None, "consumer_not_ready"
    cards = view.get("cards")
    if not isinstance(cards, list):
        return None, "consumer_cards_missing"

    matches: list[dict[str, Any]] = []
    for card in cards:
        if not isinstance(card, Mapping):
            continue
        player = card.get("player") if isinstance(card.get("player"), Mapping) else {}
        prop = card.get("prop") if isinstance(card.get("prop"), Mapping) else {}
        try:
            pid = int(player.get("player_id"))
        except (TypeError, ValueError):
            continue
        if (
            pid == int(player_id)
            and _text(player.get("game_id")) == str(game_id)
            and _text(prop.get("stat")).casefold() == "pra"
        ):
            matches.append(dict(card))

    if len(matches) == 1:
        return matches[0], "qualified_exact_pra_card"
    if len(matches) > 1:
        return None, "ambiguous_exact_pra_cards"
    return None, "no_qualified_exact_pra_card"


def _pra(game: Mapping[str, Any]) -> float | None:
    values = [_num(game.get("points")), _num(game.get("rebounds")), _num(game.get("assists"))]
    if any(value is None for value in values):
        return None
    return float(sum(value for value in values if value is not None))


def _avg(rows: list[Mapping[str, Any]], key: str) -> float | None:
    values: list[float] = []
    for row in rows:
        value = _pra(row) if key == "pra" else _num(row.get(key))
        if value is not None:
            values.append(value)
    return None if not values else sum(values) / len(values)


def _history_summary(history: Mapping[str, Any] | None, opponent_team_key: str | None) -> dict[str, Any]:
    games = history.get("games") if isinstance(history, Mapping) else None
    if not isinstance(games, list):
        return {
            "state": "UNAVAILABLE",
            "games": [],
            "recent5": [],
            "recent10": [],
            "h2h": [],
        }

    clean = [dict(row) for row in games if isinstance(row, Mapping)]
    clean.sort(key=lambda row: _text(row.get("game_date")), reverse=True)
    recent5 = clean[:5]
    recent10 = clean[:10]

    opponent = _text(opponent_team_key)
    h2h = []
    if opponent:
        for row in clean:
            matchup = row.get("matchup") if isinstance(row.get("matchup"), Mapping) else {}
            if _text(matchup.get("opponent_team_key")).casefold() == opponent.casefold():
                h2h.append(row)
        h2h = h2h[:5]

    return {
        "state": "READY",
        "games": clean,
        "recent5": recent5,
        "recent10": recent10,
        "h2h": h2h,
        "recent5_pra": _avg(recent5, "pra"),
        "recent10_pra": _avg(recent10, "pra"),
        "recent5_minutes": _avg(recent5, "minutes"),
        "recent5_points": _avg(recent5, "points"),
        "recent5_rebounds": _avg(recent5, "rebounds"),
        "recent5_assists": _avg(recent5, "assists"),
        "h2h_pra": _avg(h2h, "pra"),
        "h2h_minutes": _avg(h2h, "minutes"),
    }


def _css() -> None:
    st.markdown(
        """
<style>
.wn4-hero{display:grid;grid-template-columns:92px minmax(0,1fr);gap:1rem;align-items:center;border:1px solid rgba(56,189,248,.25);border-radius:22px;padding:18px 20px;margin:.2rem 0 1rem;background:linear-gradient(135deg,rgba(14,116,144,.18),rgba(15,23,42,.97))}
.wn4-headshot{width:86px;height:86px;border-radius:18px;object-fit:cover;object-position:center top;background:rgba(30,41,59,.65)}.wn4-kicker{font-size:.69rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:#7dd3fc}.wn4-title{font-size:clamp(1.45rem,4vw,2.2rem);font-weight:950;color:#f8fafc;letter-spacing:-.035em;line-height:1.02}.wn4-sub{font-size:.78rem;color:#94a3b8;margin-top:.35rem}
.wn4-chips{display:flex;gap:.4rem;flex-wrap:wrap;margin:.55rem 0}.wn4-chip{font-size:.64rem;font-weight:900;border:1px solid rgba(148,163,184,.2);border-radius:999px;padding:.28rem .52rem;color:#cbd5e1;background:rgba(15,23,42,.72)}.wn4-chip.ok{color:#86efac;border-color:rgba(34,197,94,.3)}
.wn4-strip{display:grid;grid-template-columns:repeat(5,minmax(80px,1fr));gap:.5rem;margin:.7rem 0 1rem}.wn4-metric{border:1px solid rgba(148,163,184,.16);border-radius:15px;padding:.65rem .5rem;text-align:center;background:rgba(15,23,42,.82)}.wn4-metric b{display:block;color:#f8fafc;font-size:1.05rem}.wn4-metric span{display:block;color:#64748b;font-size:.58rem;font-weight:900;letter-spacing:.08em;margin-top:.15rem}
.wn4-decision{border:1px solid rgba(34,197,94,.28);border-radius:20px;padding:1rem 1.05rem;background:linear-gradient(145deg,rgba(20,83,45,.2),rgba(15,23,42,.92));margin:.7rem 0 1rem}.wn4-decision.none{border-color:rgba(148,163,184,.18);background:rgba(15,23,42,.8)}.wn4-pick{font-size:1.35rem;font-weight:950;color:#f8fafc}.wn4-label{font-size:.62rem;color:#7dd3fc;font-weight:900;letter-spacing:.1em;text-transform:uppercase}.wn4-grid{display:grid;grid-template-columns:repeat(4,minmax(110px,1fr));gap:.45rem;margin-top:.7rem}
.wn4-panel{border:1px solid rgba(148,163,184,.16);border-radius:18px;padding:.85rem .9rem;background:rgba(15,23,42,.78);margin:.7rem 0}.wn4-panel h4{margin:0 0 .55rem;color:#f8fafc;font-size:.92rem}.wn4-row{display:flex;justify-content:space-between;gap:1rem;border-bottom:1px solid rgba(148,163,184,.09);padding:.34rem 0;font-size:.73rem}.wn4-row:last-child{border-bottom:0}.wn4-row span{color:#94a3b8}.wn4-row b{color:#f8fafc;text-align:right}
.wn4-games{display:grid;grid-template-columns:repeat(5,minmax(100px,1fr));gap:.45rem}.wn4-game{border:1px solid rgba(148,163,184,.13);border-radius:13px;padding:.55rem;background:rgba(30,41,59,.42);text-align:center}.wn4-game b{display:block;color:#f8fafc;font-size:.78rem}.wn4-game span{display:block;color:#64748b;font-size:.58rem;margin-top:.12rem}
@media(max-width:760px){.wn4-strip{grid-template-columns:repeat(3,1fr)}.wn4-grid{grid-template-columns:repeat(2,1fr)}.wn4-games{grid-template-columns:repeat(2,1fr)}}
@media(max-width:430px){.wn4-hero{grid-template-columns:64px 1fr;padding:14px}.wn4-headshot{width:60px;height:60px}.wn4-strip{grid-template-columns:repeat(2,1fr)}.wn4-grid{grid-template-columns:1fr}}
</style>
""",
        unsafe_allow_html=True,
    )


def _metric(label: str, value: str) -> str:
    return f'<div class="wn4-metric"><b>{escape(value)}</b><span>{escape(label)}</span></div>'


def _row(label: str, value: str) -> str:
    return f'<div class="wn4-row"><span>{escape(label)}</span><b>{escape(value)}</b></div>'


def _image(url: str, alt: str, cls: str) -> str:
    if not url:
        return ""
    return f'<img class="{cls}" src="{escape(url)}" alt="{escape(alt)}" loading="lazy">'


def _recent_games_markup(rows: list[Mapping[str, Any]]) -> str:
    cards = []
    for row in rows:
        matchup = row.get("matchup") if isinstance(row.get("matchup"), Mapping) else {}
        opponent = _text(matchup.get("opponent_team_key")) or "Opponent"
        date = _text(row.get("game_date")) or "Date N/A"
        cards.append(
            '<div class="wn4-game">'
            f'<b>{escape(_fmt(_pra(row)))} PRA</b>'
            f'<span>{escape(opponent)}</span>'
            f'<span>{escape(date)}</span>'
            '</div>'
        )
    return '<div class="wn4-games">' + "".join(cards) + "</div>" if cards else ""


def render_player_intelligence(state: navigation.NavigationState) -> dict[str, Any]:
    _css()
    player = _selected_player()
    game = _selected_game()

    player_id = _int(player.get("player_id"))
    game_id = _text(game.get("game_id"))
    if (
        player_id is None
        or not game_id
        or str(player_id) != _text(state.player_id)
        or game_id != _text(state.game_id)
    ):
        st.error("Selected player/game context expired or no longer matches navigation state.")
        if st.button("← Back to Game Center", key="wnba_nav_v2_step4_missing_back", use_container_width=True):
            navigation.go_to_game(state.game_id)
            st.rerun()
        return {"state": "PLAYER_CONTEXT_MISMATCH"}

    if st.button("← Back to Game Center", key="wnba_nav_v2_step4_back_game", use_container_width=True):
        navigation.go_to_game(game_id)
        st.rerun()

    name = _text(player.get("player_name")) or f"Player {player_id}"
    team_id = _int(player.get("team_id"))
    team_abbr = _text(player.get("team_abbreviation"))
    role = _text(player.get("role_label")) or "ACTIVE"
    designation = _text(player.get("designation")) or "NO DESIGNATION"
    starter = bool(player.get("starter_confirmed"))

    started = perf_counter()
    payload = load_player_intelligence(game_id, player_id)
    elapsed_ms = (perf_counter() - started) * 1000.0

    consumer = payload.get("consumer") if isinstance(payload.get("consumer"), Mapping) else None
    history = payload.get("history") if isinstance(payload.get("history"), Mapping) else None
    card, card_state = _exact_pra_card(consumer, game_id, player_id)

    card_player = card.get("player") if isinstance(card, Mapping) and isinstance(card.get("player"), Mapping) else {}
    opponent_key = _text(card_player.get("opponent_team_key")) or None
    history_view = _history_summary(history, opponent_key)

    st.session_state[PERF_KEY] = {
        "page": navigation.PAGE_PLAYER,
        "game_id": game_id,
        "player_id": player_id,
        "network_reads_this_uncached_render_max": 2,
        "network_reads_parallel": True,
        "projection_runs": 0,
        "sportsbook_calls": 0,
        "qualification_runs": 0,
        "ranking_runs": 0,
        "monte_carlo_runs": 0,
        "load_call_ms": elapsed_ms,
        "consumer_error": _text(payload.get("consumer_error")),
        "history_error": _text(payload.get("history_error")),
        "card_state": card_state,
    }

    away = _text(game.get("away_team"))
    home = _text(game.get("home_team"))
    matchup = f"{away} @ {home}".strip(" @")

    headshot = _text(player.get("headshot_url")) or _player_headshot(player_id)
    st.markdown(
        '<div class="wn4-hero">'
        f'{_image(headshot, name, "wn4-headshot")}'
        '<div>'
        '<div class="wn4-kicker">Kyre Sports AI • WNBA PRA Intelligence</div>'
        f'<div class="wn4-title">{escape(name)}</div>'
        f'<div class="wn4-sub">{escape(team_abbr or "WNBA")} • {escape(matchup)} • {escape(role)}</div>'
        '<div class="wn4-chips">'
        f'<span class="wn4-chip ok">● PLAYER SELECTED</span>'
        f'<span class="wn4-chip">{"STARTER" if starter else "STARTER NOT CONFIRMED"}</span>'
        f'<span class="wn4-chip">{escape(designation)}</span>'
        '<span class="wn4-chip">Read-only intelligence</span>'
        '</div></div></div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="wn4-strip">'
        + _metric("MIN", _fmt(player.get("projected_minutes")))
        + _metric("PTS", _fmt(player.get("projected_pts")))
        + _metric("REB", _fmt(player.get("projected_reb")))
        + _metric("AST", _fmt(player.get("projected_ast")))
        + _metric("PRA", _fmt(player.get("projected_pra")))
        + '</div>',
        unsafe_allow_html=True,
    )

    if isinstance(card, Mapping):
        prop = card.get("prop") if isinstance(card.get("prop"), Mapping) else {}
        market = card.get("market") if isinstance(card.get("market"), Mapping) else {}
        model = card.get("model") if isinstance(card.get("model"), Mapping) else {}
        consensus = card.get("consensus") if isinstance(card.get("consensus"), Mapping) else {}
        value = card.get("value") if isinstance(card.get("value"), Mapping) else {}
        fair = model.get("fair_price") if isinstance(model.get("fair_price"), Mapping) else {}

        decision = _text(prop.get("pick")) or "QUALIFIED PRA"
        confidence = _pct(model.get("resolved_fair_probability"))
        st.markdown(
            '<div class="wn4-decision">'
            '<div class="wn4-label">Final Qualified Decision</div>'
            f'<div class="wn4-pick">{escape(decision)}</div>'
            f'<div class="wn4-sub">Model confidence {escape(confidence)} • exact certified market snapshot</div>'
            '<div class="wn4-grid">'
            + _metric("LINE", _fmt(prop.get("line")))
            + _metric("BOOK ODDS", _american(market.get("american_odds")))
            + _metric("FAIR ODDS", _american(fair.get("american_odds")))
            + _metric("MODEL", confidence)
            + _metric("NO-VIG", _pct(consensus.get("no_vig_probability")))
            + _metric("EDGE", _fmt(consensus.get("edge_percentage_points"), 1, " pp"))
            + _metric("EV ROI", _fmt(value.get("ev_roi_percentage"), 1, "%"))
            + _metric("MC RUNS", f'{int(model.get("simulations") or 0):,}')
            + '</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="wn4-decision none">'
            '<div class="wn4-label">Final Decision</div>'
            '<div class="wn4-pick">NO QUALIFIED PRA CARD</div>'
            '<div class="wn4-sub">No exact qualified PRA market decision is currently published for this player/game. Odds, probability and edge are intentionally withheld.</div>'
            '</div>',
            unsafe_allow_html=True,
        )

    recent5 = history_view.get("recent5") or []
    recent10 = history_view.get("recent10") or []
    h2h = history_view.get("h2h") or []

    st.markdown(
        '<div class="wn4-panel"><h4>📈 Recent Form</h4>'
        + _row("Last 5 PRA avg", _fmt(history_view.get("recent5_pra")))
        + _row("Last 10 PRA avg", _fmt(history_view.get("recent10_pra")))
        + _row("Last 5 minutes avg", _fmt(history_view.get("recent5_minutes")))
        + _row("Last 5 P / R / A", f'{_fmt(history_view.get("recent5_points"))} / {_fmt(history_view.get("recent5_rebounds"))} / {_fmt(history_view.get("recent5_assists"))}')
        + _recent_games_markup(recent5)
        + '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="wn4-panel"><h4>🧭 Matchup + Pace</h4>'
        + _row("Matchup", matchup or "N/A")
        + _row("Game time", _text(game.get("time_label")) or "N/A")
        + _row("Game status", _text(game.get("status_text")) or "N/A")
        + _row("Opponent key", opponent_key or "N/A")
        + _row("Exact pace adjustment", "N/A — not exposed by read-only payload")
        + '</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="wn4-panel"><h4>🩺 Minutes, Role, Usage + Availability</h4>'
        + _row("Projected minutes", _fmt(player.get("projected_minutes")))
        + _row("Role", role)
        + _row("Starter", "Confirmed" if starter else "Not confirmed")
        + _row("Availability", designation)
        + _row("Injury detail", _text(player.get("detail")) or "None published")
        + _row("Exact usage projection", "N/A — not carried into frozen Step-3 snapshot")
        + '</div>',
        unsafe_allow_html=True,
    )

    h2h_label = opponent_key or "current opponent"
    st.markdown(
        '<div class="wn4-panel"><h4>🔁 Same-Opponent H2H Context</h4>'
        + _row("Opponent", h2h_label)
        + _row("Verified games found", str(len(h2h)))
        + _row("H2H PRA avg", _fmt(history_view.get("h2h_pra")))
        + _row("H2H minutes avg", _fmt(history_view.get("h2h_minutes")))
        + (_recent_games_markup(h2h) if h2h else '<div class="wn4-sub">No exact same-opponent history was available from the current read-only payload.</div>')
        + '</div>',
        unsafe_allow_html=True,
    )

    with st.expander("🔬 Advanced diagnostics", expanded=False):
        snapshot = consumer.get("snapshot") if isinstance(consumer, Mapping) and isinstance(consumer.get("snapshot"), Mapping) else {}
        st.write({
            "step": "4/7",
            "game_id": game_id,
            "player_id": player_id,
            "consumer_state": _text(consumer.get("state")) if isinstance(consumer, Mapping) else "unavailable",
            "consumer_error": _text(payload.get("consumer_error")),
            "consumer_snapshot_age_seconds": snapshot.get("age_seconds"),
            "consumer_effective_stale": snapshot.get("effective_stale"),
            "exact_pra_card_state": card_state,
            "history_state": history_view.get("state"),
            "history_error": _text(payload.get("history_error")),
            "history_game_count": len(history_view.get("games") or []),
            "network_reads_max": 2,
            "parallel_reads": True,
            "projection_runs": 0,
            "sportsbook_calls": 0,
            "qualification_runs": 0,
            "ranking_runs": 0,
            "monte_carlo_runs": 0,
            "missing_context_policy": "N/A, never invented",
        })

    return {
        "state": "READY",
        "game_id": game_id,
        "player_id": player_id,
        "card_state": card_state,
        "recent5_games": len(recent5),
        "recent10_games": len(recent10),
        "h2h_games": len(h2h),
    }


def render_step4_route() -> dict[str, Any]:
    state = navigation.current_state()
    if state.page == navigation.PAGE_SLATE:
        return slate.render_slate_page()
    if state.page == navigation.PAGE_GAME:
        return game_center.render_game_center(state)
    return render_player_intelligence(state)


__all__ = [
    "API_ATTEMPTS",
    "API_TIMEOUT_SECONDS",
    "CACHE_TTL_SECONDS",
    "MODEL_VERSION",
    "PERF_KEY",
    "PLAYER_INTELLIGENCE_CONTRACT",
    "_exact_pra_card",
    "_history_summary",
    "load_player_intelligence",
    "render_player_intelligence",
    "render_step4_route",
]
