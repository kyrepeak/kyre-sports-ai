"""WNBA Navigation V2 — Step 3 selected-game Game Center.

The frozen Step-2 Slate remains the Page-1 owner. Heavy WNBA role/projection
modules are imported lazily only after a matchup is selected. One cached batch
call produces the existing frozen minutes/role PTS/REB/AST/PRA values for the
selected game's two teams. When the direct player pool contains roster-only
zero-production fallbacks, this page hydrates only those rows from the hosted
Kyre Sports API official WNBA season/L10/L5 stats before the frozen role engine
runs. This layer does not change model math and does not load sportsbook
markets, H2H, ranking, qualification, Monte Carlo, or Page-3 intelligence.

Selecting a player writes only the frozen Step-1 player navigation state.
"""
from __future__ import annotations

from html import escape
import math
from time import perf_counter
from typing import Any, Mapping

import streamlit as st

import wnba_pra_navigation_v2_step1 as navigation
import wnba_pra_slate_v2_step2 as slate


MODEL_VERSION = "WNBA PRA NAVIGATION V2 • STEP 3 GAME CENTER"
CACHE_TTL_SECONDS = 180
HOSTED_STATS_CACHE_TTL_SECONDS = 90
PERF_KEY = "ks_wnba_pra_nav_v2_step3_perf"
SESSION_SELECTED_PLAYER = "ks_wnba_pra_nav_v2_selected_player"

GAME_CENTER_CONTRACT = {
    "project": "WNBA Navigation V2",
    "step": "3/7",
    "page": "game",
    "frozen_step1_navigation_reused": True,
    "frozen_step2_slate_reused": True,
    "selected_game_projection_batch_calls_per_uncached_render": 1,
    "cache_ttl_seconds": CACHE_TTL_SECONDS,
    "hosted_stats_fallback_reads_max": 3,
    "hosted_stats_fallback_only_for_zero_production": True,
    "fake_zero_production_allowed": False,
    "selected_game_output_only": True,
    "page3_prefetched": False,
    "sportsbook_markets_loaded": False,
    "h2h_loaded": False,
    "ranking_loaded": False,
    "qualification_loaded": False,
    "monte_carlo_loaded": False,
    "projection_math_changed": False,
    "market_math_changed": False,
    "sportsbook_projection_influence": 0.0,
}


class WNBAGameCenterLoadError(RuntimeError):
    pass


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _integer(value: Any) -> int | None:
    number = _float(value)
    if number is None:
        return None
    try:
        result = int(number)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result > 0 else None


def _fmt(value: Any, digits: int = 1) -> str:
    number = _float(value)
    return "—" if number is None else f"{number:.{digits}f}"


def _headshot_url(player_id: Any) -> str:
    pid = _integer(player_id)
    return "" if pid is None else f"https://cdn.wnba.com/headshots/wnba/latest/1040x760/{pid}.png"


def _team_logo_url(team_id: Any) -> str:
    tid = _integer(team_id)
    return "" if tid is None else f"https://cdn.nba.com/logos/wnba/{tid}/global/L/logo.svg"


def _game_snapshot() -> dict[str, Any]:
    raw = st.session_state.get(slate.SESSION_SELECTED_GAME)
    return dict(raw) if isinstance(raw, Mapping) else {}


def _game_key(game: Mapping[str, Any]) -> tuple[str, str, int, int, str, str]:
    game_id = _text(game.get("game_id"))
    game_date = _text(game.get("game_date"))
    away_id = _integer(game.get("away_team_id")) or 0
    home_id = _integer(game.get("home_team_id")) or 0
    away_team = _text(game.get("away_team"))
    home_team = _text(game.get("home_team"))
    if not game_id or not game_date or away_id <= 0 or home_id <= 0:
        raise WNBAGameCenterLoadError("Selected game identity is incomplete.")
    return game_id, game_date, away_id, home_id, away_team, home_team


def _record_from_role_row(row: Mapping[str, Any], team_id: int) -> dict[str, Any]:
    pid = _integer(row.get("PLAYER_ID"))
    designation = _text(row.get("DESIGNATION")) or "NO DESIGNATION"
    role_label = _text(row.get("ROLE_LABEL")) or (
        "CONFIRMED STARTER" if bool(row.get("STARTER_CONFIRMED")) else "ACTIVE"
    )
    return {
        "player_id": pid,
        "player_name": _text(row.get("PLAYER_NAME")) or "WNBA Player",
        "team_id": int(team_id),
        "team_abbreviation": _text(row.get("TEAM_ABBREVIATION")),
        "position": _text(row.get("POSITION")),
        "designation": designation,
        "detail": _text(row.get("DETAIL")),
        "starter_confirmed": bool(row.get("STARTER_CONFIRMED")),
        "role_label": role_label,
        "projected_minutes": _float(row.get("PROJ_MIN")),
        "projected_pts": _float(row.get("PROJ_PTS")),
        "projected_reb": _float(row.get("PROJ_REB")),
        "projected_ast": _float(row.get("PROJ_AST")),
        "projected_pra": _float(row.get("PROJ_PRA")),
        "headshot_url": _headshot_url(pid),
    }


@st.cache_data(ttl=HOSTED_STATS_CACHE_TTL_SECONDS, show_spinner=False)
def _hosted_stat_windows(season: int) -> dict[int, dict[str, Any]]:
    """Read official season/L10/L5 player stats from the hosted Kyre WNBA API."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from wnba_api_client_v1 import KyreWNBAAPIClient

    client = KyreWNBAAPIClient(timeout_seconds=6.0, attempts=1)

    def fetch(last_n: int) -> tuple[int, dict[str, Any]]:
        payload = client.get_json(
            "/api/v1/wnba/stats/players",
            params={
                "season": int(season),
                "season_type": "Regular Season",
                "last_n_games": int(last_n),
                "per_mode": "PerGame",
            },
        )
        return int(last_n), payload

    result: dict[int, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fetch, n): n for n in (0, 10, 5)}
        for future in as_completed(futures):
            try:
                n, payload = future.result()
            except Exception:
                continue
            if isinstance(payload, dict):
                result[int(n)] = payload
    return result


def _hydrate_stats_for_game(stats, *, game_date: str, away_id: int, home_id: int):
    """Hydrate only known zero-only fallback rows and drop unresolved fake-zero rows."""
    import pandas as pd
    from wnba_pra_game_center_stats_hydration_v1 import (
        count_zero_production_candidates,
        hydrate_zero_production_rows,
        is_zero_production_candidate,
    )

    allowed = {int(away_id), int(home_id)}
    records = stats.to_dict("records")
    candidates = count_zero_production_candidates(records, allowed)
    diag = {"candidates": candidates, "hydrated": 0, "unresolved": 0}
    if candidates:
        windows = _hosted_stat_windows(pd.to_datetime(game_date).year)
        records, diag = hydrate_zero_production_rows(
            records,
            season_payload=windows.get(0),
            l10_payload=windows.get(10),
            l5_payload=windows.get(5),
            allowed_team_ids=allowed,
        )

    usable = [
        row
        for row in records
        if not is_zero_production_candidate(row, allowed)
    ]
    out = pd.DataFrame(usable)
    if out.empty:
        raise WNBAGameCenterLoadError(
            "Observed WNBA player production is unavailable; fake zero production was blocked."
        )

    for team_id in allowed:
        if "TEAM_ID" not in out.columns:
            raise WNBAGameCenterLoadError("Hydrated WNBA player pool is missing TEAM_ID.")
        team = out[pd.to_numeric(out["TEAM_ID"], errors="coerce").eq(int(team_id))]
        if team.empty:
            raise WNBAGameCenterLoadError(
                f"Observed WNBA player production is unavailable for team {team_id}."
            )
        minutes = pd.to_numeric(team.get("MIN"), errors="coerce").fillna(0.0)
        if not bool(minutes.gt(0.0).any()):
            raise WNBAGameCenterLoadError(
                f"Observed WNBA player minutes are unavailable for team {team_id}."
            )

    return out.reset_index(drop=True), diag


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_game_center(
    game_id: str,
    game_date: str,
    away_id: int,
    home_id: int,
    away_team: str,
    home_team: str,
) -> dict[str, Any]:
    """Run one frozen selected-game role batch and return compact UI records.

    Heavy imports intentionally live inside this function so the frozen Slate
    route does not pay pandas/numpy/role-engine import cost.
    """
    import pandas as pd
    import wnba_availability_v27 as availability
    import wnba_role_v28 as role

    selected = pd.Series({
        "game_id": str(game_id),
        "game_date": str(game_date),
        "away_team_id": int(away_id),
        "home_team_id": int(home_id),
        "away_team": str(away_team),
        "home_team": str(home_team),
    })

    stats, pool_diag = availability._verified_pool_for_day(str(game_date))
    if stats is None or stats.empty:
        raise WNBAGameCenterLoadError("Date-correct WNBA player pool is unavailable.")

    stats, hydration_diag = _hydrate_stats_for_game(
        stats,
        game_date=str(game_date),
        away_id=int(away_id),
        home_id=int(home_id),
    )

    result = role.role_projection_for_game(selected, stats=stats)
    teams_obj = result.get("teams") if isinstance(result, Mapping) else None
    if not isinstance(teams_obj, Mapping):
        raise WNBAGameCenterLoadError("Frozen role engine returned no team projection map.")

    teams: dict[str, list[dict[str, Any]]] = {}
    for team_id in (int(away_id), int(home_id)):
        frame = teams_obj.get(team_id)
        if frame is None or not hasattr(frame, "iterrows"):
            teams[str(team_id)] = []
            continue
        rows = [
            _record_from_role_row(row, team_id)
            for _, row in frame.iterrows()
        ]
        teams[str(team_id)] = rows

    return {
        "game_id": str(game_id),
        "game_date": str(game_date),
        "away_team_id": int(away_id),
        "home_team_id": int(home_id),
        "away_team": str(away_team),
        "home_team": str(home_team),
        "teams": teams,
        "players": sum(len(rows) for rows in teams.values()),
        "pool_state": _text((pool_diag or {}).get("state")),
        "stat_hydration_candidates": int(hydration_diag.get("candidates") or 0),
        "stat_hydration_hydrated": int(hydration_diag.get("hydrated") or 0),
        "stat_hydration_unresolved": int(hydration_diag.get("unresolved") or 0),
        "usage_source": _text(result.get("usage_source")) if isinstance(result, Mapping) else "",
        "availability_source": _text(result.get("availability_source")) if isinstance(result, Mapping) else "",
        "model_version": _text(getattr(role, "MODEL_VERSION", "WNBA frozen role engine")),
    }


def _css() -> None:
    st.markdown(
        """
<style>
.wn3-hero{border:1px solid rgba(56,189,248,.25);border-radius:22px;padding:17px 19px;margin:.2rem 0 1rem;background:linear-gradient(135deg,rgba(14,116,144,.18),rgba(15,23,42,.96))}
.wn3-kicker{font-size:.7rem;font-weight:900;letter-spacing:.12em;text-transform:uppercase;color:#7dd3fc}
.wn3-title{font-size:clamp(1.45rem,4vw,2.15rem);font-weight:950;color:#f8fafc;letter-spacing:-.035em;margin:.2rem 0}
.wn3-sub{font-size:.8rem;color:#94a3b8}
.wn3-teamhead{display:flex;align-items:center;gap:.65rem;margin:1.2rem 0 .5rem;padding:.7rem .85rem;border-radius:16px;background:rgba(15,23,42,.72);border:1px solid rgba(148,163,184,.15)}
.wn3-teamlogo{width:42px;height:42px;object-fit:contain}.wn3-teamname{font-size:1.1rem;font-weight:950;color:#f8fafc}.wn3-teammeta{font-size:.68rem;color:#94a3b8}
.wn3-player{display:grid;grid-template-columns:64px minmax(0,1.15fr) minmax(260px,1fr);gap:.8rem;align-items:center;border:1px solid rgba(148,163,184,.17);border-radius:18px;padding:.75rem .85rem;margin:.52rem 0 .2rem;background:linear-gradient(145deg,rgba(15,23,42,.97),rgba(15,23,42,.84))}
.wn3-headshot{width:58px;height:58px;border-radius:14px;object-fit:cover;object-position:center top;background:rgba(30,41,59,.7)}
.wn3-name{font-weight:950;color:#f8fafc;line-height:1.05}.wn3-role{font-size:.66rem;font-weight:900;color:#7dd3fc;margin-top:.25rem;text-transform:uppercase}.wn3-detail{font-size:.64rem;color:#64748b;margin-top:.18rem}
.wn3-metrics{display:grid;grid-template-columns:repeat(5,minmax(44px,1fr));gap:.35rem}.wn3-metric{padding:.45rem .35rem;border-radius:11px;text-align:center;background:rgba(30,41,59,.56);border:1px solid rgba(148,163,184,.12)}
.wn3-metric b{display:block;color:#f8fafc;font-size:.82rem}.wn3-metric span{display:block;color:#64748b;font-size:.56rem;font-weight:900;letter-spacing:.06em;margin-top:.08rem}
.wn3-health{display:flex;gap:.45rem;flex-wrap:wrap;margin:.45rem 0 .75rem}.wn3-chip{font-size:.66rem;font-weight:850;color:#cbd5e1;border:1px solid rgba(148,163,184,.2);border-radius:999px;padding:.3rem .55rem;background:rgba(15,23,42,.72)}.wn3-chip.ok{color:#86efac;border-color:rgba(34,197,94,.3)}
@media(max-width:760px){.wn3-player{grid-template-columns:54px 1fr}.wn3-headshot{width:50px;height:50px}.wn3-metrics{grid-column:1/-1;grid-template-columns:repeat(5,1fr)}}
@media(max-width:430px){.wn3-metrics{grid-template-columns:repeat(3,1fr)}}
</style>
""",
        unsafe_allow_html=True,
    )


def _image(url: str, alt: str, cls: str) -> str:
    if not url:
        return ""
    return f'<img class="{cls}" src="{escape(url)}" alt="{escape(alt)}" loading="lazy">'


def _metric(label: str, value: Any) -> str:
    return (
        '<div class="wn3-metric">'
        f'<b>{escape(_fmt(value))}</b>'
        f'<span>{escape(label)}</span>'
        '</div>'
    )


def _render_player_card(player: Mapping[str, Any], game_id: str) -> None:
    pid = _integer(player.get("player_id"))
    name = _text(player.get("player_name")) or "WNBA Player"
    role_label = _text(player.get("role_label")) or "ACTIVE"
    designation = _text(player.get("designation"))
    detail = _text(player.get("detail"))
    position = _text(player.get("position"))
    small = " • ".join(part for part in (position, designation if designation != "NO DESIGNATION" else "") if part)

    st.markdown(
        '<div class="wn3-player">'
        f'{_image(_text(player.get("headshot_url")), name, "wn3-headshot")}'
        '<div>'
        f'<div class="wn3-name">{escape(name)}</div>'
        f'<div class="wn3-role">{escape(role_label)}</div>'
        f'<div class="wn3-detail">{escape(small or "Current roster")}</div>'
        + (f'<div class="wn3-detail">{escape(detail)}</div>' if detail else "")
        + '</div>'
        '<div class="wn3-metrics">'
        f'{_metric("MIN", player.get("projected_minutes"))}'
        f'{_metric("PTS", player.get("projected_pts"))}'
        f'{_metric("REB", player.get("projected_reb"))}'
        f'{_metric("AST", player.get("projected_ast"))}'
        f'{_metric("PRA", player.get("projected_pra"))}'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    if pid is not None:
        if st.button(
            f"Open {name} PRA →",
            key=f"wnba_nav_v2_step3_player_{game_id}_{pid}",
            use_container_width=True,
        ):
            st.session_state[SESSION_SELECTED_PLAYER] = dict(player)
            navigation.go_to_player(game_id, str(pid))
            st.rerun()
    else:
        st.caption("Player drill-down unavailable because official player ID is missing.")


def _render_team(
    *,
    team_id: int,
    team_name: str,
    label: str,
    players: list[dict[str, Any]],
    game_id: str,
) -> None:
    st.markdown(
        '<div class="wn3-teamhead">'
        f'{_image(_team_logo_url(team_id), team_name, "wn3-teamlogo")}'
        '<div>'
        f'<div class="wn3-teamname">{escape(team_name or "WNBA Team")}</div>'
        f'<div class="wn3-teammeta">{escape(label)} • {len(players)} players</div>'
        '</div></div>',
        unsafe_allow_html=True,
    )
    if not players:
        st.warning("No current-player projection rows were available for this team.")
        return
    for player in players:
        _render_player_card(player, game_id)


def render_game_center(state: navigation.NavigationState) -> dict[str, Any]:
    _css()
    game = _game_snapshot()
    try:
        game_id, game_date, away_id, home_id, away_team, home_team = _game_key(game)
    except WNBAGameCenterLoadError:
        st.error("Selected game context expired. Return to the Slate and choose the matchup again.")
        if st.button("← Back to WNBA Slate", key="wnba_nav_v2_step3_missing_game_back", use_container_width=True):
            navigation.go_to_slate()
            st.rerun()
        return {"state": "MISSING_GAME_CONTEXT"}

    if state.game_id != game_id:
        st.error("Selected game state does not match the cached matchup. Failing closed.")
        if st.button("← Reset to WNBA Slate", key="wnba_nav_v2_step3_mismatch_back", use_container_width=True):
            navigation.go_to_slate()
            st.rerun()
        return {"state": "GAME_STATE_MISMATCH"}

    if st.button("← Back to WNBA Slate", key="wnba_nav_v2_step3_back_slate", use_container_width=True):
        navigation.go_to_slate()
        st.rerun()

    st.markdown(
        '<div class="wn3-hero">'
        '<div class="wn3-kicker">Kyre Sports AI • WNBA Game Center</div>'
        f'<div class="wn3-title">{escape(away_team)} @ {escape(home_team)}</div>'
        '<div class="wn3-sub">Selected-game player projections only • tap a player for deeper PRA intelligence.</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    started = perf_counter()
    try:
        payload = load_game_center(game_id, game_date, away_id, home_id, away_team, home_team)
        error_type = ""
    except Exception as exc:
        payload = {
            "game_id": game_id,
            "game_date": game_date,
            "teams": {str(away_id): [], str(home_id): []},
            "players": 0,
            "pool_state": "LOAD_ERROR",
        }
        error_type = type(exc).__name__

    elapsed_ms = (perf_counter() - started) * 1000.0
    st.session_state[PERF_KEY] = {
        "page": navigation.PAGE_GAME,
        "game_id": game_id,
        "selected_game_projection_batch_calls_this_render": 1,
        "page3_prefetches": 0,
        "sportsbook_market_requests": 0,
        "h2h_requests": 0,
        "monte_carlo_requests": 0,
        "load_call_ms": elapsed_ms,
        "error_type": error_type,
    }

    if error_type:
        st.error("Game Center projections are temporarily unavailable. Fake zero-production cards were not rendered.")
        if st.button("Retry Game Center", key="wnba_nav_v2_step3_retry", use_container_width=True):
            try:
                load_game_center.clear()
                _hosted_stat_windows.clear()
            except Exception:
                pass
            st.rerun()
        return payload

    teams = payload.get("teams") if isinstance(payload.get("teams"), Mapping) else {}
    away_players = list(teams.get(str(away_id)) or [])
    home_players = list(teams.get(str(home_id)) or [])

    st.markdown(
        '<div class="wn3-health">'
        '<span class="wn3-chip ok">● GAME CENTER READY</span>'
        f'<span class="wn3-chip">{int(payload.get("players") or 0)} players</span>'
        '<span class="wn3-chip">1 cached selected-game batch</span>'
        '<span class="wn3-chip">Page 3 asleep</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    _render_team(
        team_id=away_id,
        team_name=away_team,
        label="AWAY",
        players=away_players,
        game_id=game_id,
    )
    _render_team(
        team_id=home_id,
        team_name=home_team,
        label="HOME",
        players=home_players,
        game_id=game_id,
    )
    st.caption("Projected values use the existing frozen WNBA minutes/role model with verified observed production hydration.")
    return payload


def render_player_placeholder(state: navigation.NavigationState) -> dict[str, Any]:
    _css()
    if st.button("← Back to Game Center", key="wnba_nav_v2_step3_back_game", use_container_width=True):
        navigation.go_to_game(state.game_id)
        st.rerun()

    raw = st.session_state.get(SESSION_SELECTED_PLAYER)
    player = dict(raw) if isinstance(raw, Mapping) else {}
    name = _text(player.get("player_name")) or f"Player {state.player_id}"
    st.markdown(
        '<div class="wn3-hero">'
        '<div class="wn3-kicker">WNBA Navigation V2 • Page 3</div>'
        f'<div class="wn3-title">🎯 {escape(name)} PRA Intelligence</div>'
        '<div class="wn3-sub">Detailed line, probability, edge, matchup and Monte Carlo intelligence is intentionally deferred to Step 4.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.info("Player identity is selected. No Page-3 analytics were prefetched by Game Center.")
    st.session_state[PERF_KEY] = {
        "page": navigation.PAGE_PLAYER,
        "game_id": state.game_id,
        "player_id": state.player_id,
        "selected_game_projection_batch_calls_this_render": 0,
        "page3_prefetches": 0,
        "sportsbook_market_requests": 0,
        "h2h_requests": 0,
        "monte_carlo_requests": 0,
    }
    return {"page": state.page, "game_id": state.game_id, "player_id": state.player_id}


def render_step3_route() -> dict[str, Any]:
    state = navigation.current_state()
    if state.page == navigation.PAGE_SLATE:
        return slate.render_slate_page()
    if state.page == navigation.PAGE_GAME:
        return render_game_center(state)
    return render_player_placeholder(state)


__all__ = [
    "CACHE_TTL_SECONDS",
    "GAME_CENTER_CONTRACT",
    "HOSTED_STATS_CACHE_TTL_SECONDS",
    "MODEL_VERSION",
    "PERF_KEY",
    "SESSION_SELECTED_PLAYER",
    "WNBAGameCenterLoadError",
    "load_game_center",
    "render_game_center",
    "render_player_placeholder",
    "render_step3_route",
]
