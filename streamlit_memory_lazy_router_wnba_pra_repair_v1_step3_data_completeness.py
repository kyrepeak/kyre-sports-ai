"""WNBA PRA Repair V1 Step 3 — Page-3 data completeness overlay.

This wrapper sits above the merged Step-2 team-identity runtime, which itself preserves the frozen WNBA PRA Speed V3 Step-9 runtime.  It does
not change projection, probability, qualification, market, Monte Carlo, ranking,
or sportsbook math.

Repairs presentation/data handoff only:
- retain L5/L10 form + usage fields already present on the frozen role row;
- derive opponent identity from selected-game truth instead of consumer Top-5;
- use verified L5/L10 aggregates if the per-game history transport is missing;
- expose the existing PRA V3.6 team-relative pace context;
- expose existing role-engine usage when present, with the repository-established
  production-role proxy as an explicitly labeled display-only last resort.
"""
from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Mapping

import streamlit as st

import streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity as frozen_parent
import wnba_pra_game_center_v2_step3 as game_center
import wnba_pra_navigation_v2_step1 as navigation
import wnba_pra_player_intelligence_v2_step4 as player_intelligence
import wnba_pra_performance_v2_step5 as performance
import wnba_pra_repair_v1_step3_data as data
import wnba_pra_slate_v2_step2 as slate

MODEL_VERSION = "WNBA PRA REPAIR V1 • STEP 3 DATA COMPLETENESS"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_PROJECTION_MATH = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_QUALIFICATION = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
SESSION_CONTEXT = "ks_wnba_pra_repair_v1_step3_context"
PROOF_MARKER = "data-completeness"
SHELL_SPORT_QUERY_KEY = "ks_jump_sport"
SHELL_MARKET_QUERY_KEY = "ks_jump_market"
SHELL_SPORT_SESSION_KEY = "ks_sport_touch"
SHELL_MARKET_SESSION_KEY = "ks_wnba_market_touch"
SHELL_SPORT_VALUE = "WNBA"
SHELL_MARKET_VALUE = "PRA"
CFB_ROUTE_QUERY_SPORT = "ks_sport"
CFB_ROUTE_QUERY_MARKET = "ks_cfb_market"
CFB_SPORT_SESSION_KEY = "ks_sport_touch"
CFB_MARKET_SESSION_KEY = "ks_cfb_market_touch"
CFB_SPORT_VALUE = "College Football"
CFB_TOP_PICKS_VALUE = "Top Picks"


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def _num(value: Any) -> float | None:
    return data.number(value)


def _current_context() -> dict[str, Any]:
    value = st.session_state.get(SESSION_CONTEXT)
    return dict(value) if isinstance(value, Mapping) else {}


def _save_context(**updates: Any) -> dict[str, Any]:
    current = _current_context()
    current.update(updates)
    st.session_state[SESSION_CONTEXT] = current
    return current


def _enrich_role_record(original, row: Any, team_id: int) -> dict[str, Any]:
    result = dict(original(row, team_id))
    getter = getattr(row, "get", lambda _k, _d=None: _d)
    additions = {
        "season_minutes": getter("MIN"),
        "season_points": getter("PTS"),
        "season_rebounds": getter("REB"),
        "season_assists": getter("AST"),
        "season_pra": getter("PRA"),
        "l10_minutes": getter("L10_MIN"),
        "l10_points": getter("L10_PTS"),
        "l10_rebounds": getter("L10_REB"),
        "l10_assists": getter("L10_AST"),
        "l10_pra": getter("L10_PRA"),
        "l5_minutes": getter("L5_MIN"),
        "l5_points": getter("L5_PTS"),
        "l5_rebounds": getter("L5_REB"),
        "l5_assists": getter("L5_AST"),
        "l5_pra": getter("L5_PRA"),
        "base_usage": getter("BASE_USG"),
        "projected_usage": getter("PROJ_USG"),
        "season_usage": getter("USG_PCT"),
        "l10_usage": getter("L10_USG_PCT"),
        "l5_usage": getter("L5_USG_PCT"),
        "role_delta_pct": getter("ROLE_DELTA_PCT"),
        "usage_ratio": getter("USG_RATIO"),
        "player_id_source": getter("PLAYER_ID_SOURCE"),
        "data_source": getter("DATA_SOURCE"),
    }
    for key, value in additions.items():
        result[key] = value
    return result


def _all_game_rows() -> list[dict[str, Any]]:
    payload = st.session_state.get(performance.SESSION_GAME_PAYLOAD)
    teams = payload.get("teams") if isinstance(payload, Mapping) else None
    if not isinstance(teams, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for values in teams.values():
        if isinstance(values, list):
            rows.extend(dict(row) for row in values if isinstance(row, Mapping))
    return rows


def _selected_player_enriched() -> dict[str, Any]:
    raw = st.session_state.get(game_center.SESSION_SELECTED_PLAYER)
    player = dict(raw) if isinstance(raw, Mapping) else {}
    if _num(player.get("projected_usage")) is not None or _num(player.get("l5_pra")) is not None:
        return player

    try:
        pid = int(player.get("player_id") or 0)
    except (TypeError, ValueError):
        pid = 0
    if pid <= 0:
        return player

    for row in _all_game_rows():
        try:
            row_pid = int(row.get("player_id") or 0)
        except (TypeError, ValueError):
            continue
        if row_pid == pid:
            player.update(row)
            st.session_state[game_center.SESSION_SELECTED_PLAYER] = dict(player)
            break
    return player


def _usage_proxy_from_game(player: Mapping[str, Any]) -> tuple[float | None, str]:
    direct = _num(player.get("projected_usage"))
    if direct is not None:
        return direct, "role engine projected USG"

    weighted = data.weighted_usage(
        player.get("season_usage"),
        player.get("l10_usage"),
        player.get("l5_usage"),
    )
    if weighted is not None:
        return weighted, "verified usage blend"

    try:
        team_id = int(player.get("team_id") or 0)
        player_id = int(player.get("player_id") or 0)
    except (TypeError, ValueError):
        return None, ""

    team_rows = []
    for row in _all_game_rows():
        try:
            if int(row.get("team_id") or 0) != team_id:
                continue
        except (TypeError, ValueError):
            continue
        minutes = _num(row.get("season_minutes"))
        points = _num(row.get("season_points"))
        assists = _num(row.get("season_assists"))
        if minutes is None or minutes <= 0 or points is None or assists is None:
            continue
        load = (points + 1.35 * assists) / minutes
        if math.isfinite(load) and load > 0:
            team_rows.append((int(row.get("player_id") or 0), load))

    if not team_rows:
        return None, ""

    loads = [value for _, value in team_rows]
    avg = mean(loads)
    sigma = pstdev(loads) if len(loads) > 1 else 0.0
    denom = max(float(sigma), 0.08)
    for pid, load in team_rows:
        if pid != player_id:
            continue
        proxy = max(8.0, min(35.0, 20.0 + 4.5 * ((load - avg) / denom)))
        return proxy, "production-role proxy (display only)"
    return None, ""


@st.cache_data(ttl=900, show_spinner=False)
def _pace_context(
    game_id: str,
    game_date: str,
    away_id: int,
    home_id: int,
    player_team_id: int,
) -> dict[str, Any]:
    try:
        import wnba_context_v26 as team_context
        import wnba_pra_matchup_v36 as matchup

        game = {
            "game_id": str(game_id),
            "game_date": str(game_date),
            "away_team_id": int(away_id),
            "home_team_id": int(home_id),
        }
        context = team_context.game_context(game, str(game_date))
        if not isinstance(context, Mapping):
            return {"ready": False, "reason": "context_missing"}

        if int(player_team_id) == int(away_id):
            team_side, opponent_side = "away", "home"
        elif int(player_team_id) == int(home_id):
            team_side, opponent_side = "home", "away"
        else:
            return {"ready": False, "reason": "player_team_mismatch"}

        team_ctx = context.get(team_side) if isinstance(context.get(team_side), Mapping) else {}
        opp_ctx = context.get(opponent_side) if isinstance(context.get(opponent_side), Mapping) else {}
        factors = matchup.matchup_factors_v36(team_ctx, opp_ctx)
        factor = _num(factors.get("pace_factor"))
        expected = _num(factors.get("expected_pace"))
        source = str(factors.get("pace_source") or "")
        if factor is None:
            return {"ready": False, "reason": "pace_factor_missing"}
        return {
            "ready": True,
            "pace_factor": factor,
            "expected_pace": expected,
            "pace_source": source,
            "context_quality": _num(factors.get("context_quality")),
            "defense_factor": _num(factors.get("defense_factor")),
        }
    except Exception as exc:
        return {"ready": False, "reason": type(exc).__name__}


def _build_context() -> dict[str, Any]:
    player = _selected_player_enriched()
    game_raw = st.session_state.get(slate.SESSION_SELECTED_GAME)
    game = dict(game_raw) if isinstance(game_raw, Mapping) else {}

    try:
        player_team_id = int(player.get("team_id") or 0)
        player_id = int(player.get("player_id") or 0)
        away_id = int(game.get("away_team_id") or 0)
        home_id = int(game.get("home_team_id") or 0)
    except (TypeError, ValueError):
        player_team_id = player_id = away_id = home_id = 0

    opponent = data.opponent_identity(game, player_team_id)
    usage, usage_source = _usage_proxy_from_game(player)

    pace = {"ready": False, "reason": "identity_incomplete"}
    game_id = str(game.get("game_id") or "")
    game_date = str(game.get("game_date") or "")
    if game_id and game_date and away_id and home_id and player_team_id:
        pace = _pace_context(game_id, game_date, away_id, home_id, player_team_id)

    fallback = data.form_fallback(player)
    context = {
        "player_id": player_id,
        "opponent_ready": bool(opponent.get("ready")),
        "opponent_key": str(opponent.get("opponent_team_key") or ""),
        "opponent_name": str(opponent.get("opponent_name") or ""),
        "usage": usage,
        "usage_source": usage_source,
        "usage_ready": usage is not None,
        "pace_ready": bool(pace.get("ready")),
        "pace_factor": pace.get("pace_factor"),
        "expected_pace": pace.get("expected_pace"),
        "pace_source": str(pace.get("pace_source") or ""),
        "context_quality": pace.get("context_quality"),
        "recent5_fallback": fallback.get("recent5_pra"),
        "recent10_fallback": fallback.get("recent10_pra"),
        "recent5_ready": fallback.get("recent5_pra") is not None,
        "recent10_ready": fallback.get("recent10_pra") is not None,
        "recent_fallback_used": False,
        "history_game_count": 0,
        "h2h_count": 0,
        "history_opponent_linked": False,
    }
    st.session_state[SESSION_CONTEXT] = context
    return context


def _repair_history_summary(original, history: Mapping[str, Any] | None, opponent_team_key: str | None):
    ctx = _current_context()
    opponent = str(opponent_team_key or ctx.get("opponent_key") or "").strip() or None
    out = dict(original(history, opponent))
    player = _selected_player_enriched()
    fallback = data.form_fallback(player)
    used = False
    for key, value in fallback.items():
        if out.get(key) is None and value is not None:
            out[key] = value
            used = True

    recent5_ready = _num(out.get("recent5_pra")) is not None
    recent10_ready = _num(out.get("recent10_pra")) is not None
    history_games = len(out.get("games") or [])
    h2h_count = len(out.get("h2h") or [])
    _save_context(
        recent5_ready=recent5_ready,
        recent10_ready=recent10_ready,
        recent_fallback_used=used,
        history_game_count=history_games,
        h2h_count=h2h_count,
        history_opponent_linked=bool(opponent),
        history_source=str((history or {}).get("source") or "role-row aggregate fallback"),
    )
    return out


def _repair_row(original, label: str, value: str) -> str:
    ctx = _current_context()
    new_label = label
    new_value = value

    if label == "Opponent key" and ctx.get("opponent_key"):
        new_value = str(ctx["opponent_key"])
    elif label == "Opponent" and value == "current opponent" and ctx.get("opponent_key"):
        new_value = str(ctx["opponent_key"])
    elif label == "Exact pace adjustment":
        new_label = "Pace adjustment (PRA V3.6)"
        new_value = data.format_pace(
            ctx.get("pace_factor"),
            ctx.get("expected_pace"),
            str(ctx.get("pace_source") or ""),
        )
    elif label == "Exact usage projection":
        new_label = "Usage projection"
        new_value = data.format_usage(ctx.get("usage"), str(ctx.get("usage_source") or ""))

    return original(new_label, new_value)


def _render_marker() -> None:
    ctx = _current_context()
    status = (
        bool(ctx.get("opponent_ready"))
        and bool(ctx.get("recent5_ready"))
        and bool(ctx.get("recent10_ready"))
        and bool(ctx.get("usage_ready"))
        and bool(ctx.get("pace_ready"))
        and bool(ctx.get("history_opponent_linked"))
    )
    st.markdown(
        '<span data-wnba-pra-repair-v1-step3="data-completeness" '
        f'data-status="{"green" if status else "blocked"}" '
        f'data-opponent-ready="{str(bool(ctx.get("opponent_ready"))).lower()}" '
        f'data-recent5-ready="{str(bool(ctx.get("recent5_ready"))).lower()}" '
        f'data-recent10-ready="{str(bool(ctx.get("recent10_ready"))).lower()}" '
        f'data-usage-ready="{str(bool(ctx.get("usage_ready"))).lower()}" '
        f'data-pace-ready="{str(bool(ctx.get("pace_ready"))).lower()}" '
        f'data-history-opponent-linked="{str(bool(ctx.get("history_opponent_linked"))).lower()}" '
        f'data-recent-fallback-used="{str(bool(ctx.get("recent_fallback_used"))).lower()}" '
        f'data-history-games="{int(ctx.get("history_game_count") or 0)}" '
        f'data-h2h-games="{int(ctx.get("h2h_count") or 0)}" '
        'data-consumer-independent-context="true" '
        'data-projection-math-changed="false" '
        'data-market-math-changed="false" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def _query_value(key: str) -> str:
    try:
        raw = st.query_params.get(key)
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _protect_explicit_cfb_top_picks_route() -> bool:
    """Yield universal shell ownership to an explicit College Football / Top Picks route."""
    if (
        _query_value(CFB_ROUTE_QUERY_SPORT) != CFB_SPORT_VALUE
        or _query_value(CFB_ROUTE_QUERY_MARKET) != CFB_TOP_PICKS_VALUE
    ):
        return False

    try:
        st.query_params.pop(SHELL_SPORT_QUERY_KEY, None)
        st.query_params.pop(SHELL_MARKET_QUERY_KEY, None)
    except Exception:
        pass

    st.session_state[CFB_SPORT_SESSION_KEY] = CFB_SPORT_VALUE
    st.session_state[CFB_MARKET_SESSION_KEY] = CFB_TOP_PICKS_VALUE
    return True


def _pin_deep_wnba_shell_route(state: navigation.NavigationState | None = None) -> navigation.NavigationState:
    """Keep the universal shell on WNBA/PRA across Game/Player reruns.

    The frozen navigation layer owns only wnba_pra_* route state. Streamlit can
    re-enter the universal shell after its query update; without an explicit
    shell handoff that shell may fall back to its default MLB route. This Step-3
    overlay owns the repair without changing frozen navigation or model math.
    """
    resolved = state or navigation.current_state()
    if _protect_explicit_cfb_top_picks_route():
        return resolved
    if resolved.page not in {navigation.PAGE_GAME, navigation.PAGE_PLAYER}:
        return resolved

    st.session_state[SHELL_SPORT_SESSION_KEY] = SHELL_SPORT_VALUE
    st.session_state[SHELL_MARKET_SESSION_KEY] = SHELL_MARKET_VALUE
    try:
        st.query_params[SHELL_SPORT_QUERY_KEY] = SHELL_SPORT_VALUE
        st.query_params[SHELL_MARKET_QUERY_KEY] = SHELL_MARKET_VALUE
    except Exception:
        pass
    return resolved


def render_app() -> Any:
    original_record = game_center._record_from_role_row
    original_history = player_intelligence._history_summary
    original_row = player_intelligence._row
    original_player_renderer = player_intelligence.render_player_intelligence
    original_nav_query_writer = navigation._write_query

    def enriched_record(row: Any, team_id: int):
        return _enrich_role_record(original_record, row, team_id)

    def repaired_history(history, opponent_team_key):
        return _repair_history_summary(original_history, history, opponent_team_key)

    def repaired_row(label: str, value: str):
        return _repair_row(original_row, label, value)

    def repaired_player_renderer(state):
        _build_context()
        result = original_player_renderer(state)
        _render_marker()
        return result

    def stable_nav_query_writer(state):
        result = original_nav_query_writer(state)
        _pin_deep_wnba_shell_route(state)
        return result

    _pin_deep_wnba_shell_route()
    navigation._write_query = stable_nav_query_writer
    game_center._record_from_role_row = enriched_record
    player_intelligence._history_summary = repaired_history
    player_intelligence._row = repaired_row
    player_intelligence.render_player_intelligence = repaired_player_renderer
    try:
        return frozen_parent.render_app()
    finally:
        navigation._write_query = original_nav_query_writer
        game_center._record_from_role_row = original_record
        player_intelligence._history_summary = original_history
        player_intelligence._row = original_row
        player_intelligence.render_player_intelligence = original_player_renderer


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION_MATH",
    "MAY_MODIFY_QUALIFICATION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "PROOF_MARKER",
    "SESSION_CONTEXT",
    "SHELL_SPORT_QUERY_KEY",
    "SHELL_MARKET_QUERY_KEY",
    "SHELL_SPORT_SESSION_KEY",
    "SHELL_MARKET_SESSION_KEY",
    "SHELL_SPORT_VALUE",
    "SHELL_MARKET_VALUE",
    "CFB_ROUTE_QUERY_SPORT",
    "CFB_ROUTE_QUERY_MARKET",
    "CFB_SPORT_SESSION_KEY",
    "CFB_MARKET_SESSION_KEY",
    "CFB_SPORT_VALUE",
    "CFB_TOP_PICKS_VALUE",
    "_protect_explicit_cfb_top_picks_route",
    "_pin_deep_wnba_shell_route",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
