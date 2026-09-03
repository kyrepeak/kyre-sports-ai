"""MLB Matchup Explorer V6.1 — Cleanup Step 17 deep-research performance.

Performance-only wrapper over certified Cleanup Step 16. The V2 model is unchanged:
Steps 1-10 keep their certified builders, Step 11 keeps the same Monte Carlo engine and
simulation count, and Step 12 keeps the same calibration/final-intelligence math.

This layer removes avoidable work around those frozen engines:
- memoizes each Step 1-10 builder so the rendered Step card and Step 11 reuse the exact
  same profile instead of rebuilding it in the same Streamlit run;
- keeps short-lived per-session profile/result caches keyed by immutable game/player
  identity plus lineup/starter state, so revisiting the same unchanged matchup does not
  repeat expensive research or Monte Carlo work;
- defers Legacy V1 audit and Daily Top 5 calculations until the user explicitly loads
  those optional collapsed sections;
- records millisecond timings/cache hits in session state for diagnostics.
"""
from __future__ import annotations

import copy
import time
from typing import Any, Callable

import streamlit as st

import mlb_matchup_calibration_v1 as calibration
import mlb_matchup_hub_v14 as roster
import mlb_matchup_hub_v56 as current
import mlb_matchup_player_v20 as legacy_v1
import mlb_matchup_player_v24 as step1
import mlb_matchup_player_v25 as step2
import mlb_matchup_player_v26 as step3
import mlb_matchup_player_v27 as step4
import mlb_matchup_player_v28 as step5
import mlb_matchup_player_v29 as step6
import mlb_matchup_player_v30 as step7
import mlb_matchup_player_v31 as step8
import mlb_matchup_player_v32 as step9
import mlb_matchup_player_v33 as step10
import mlb_matchup_player_v35 as final_layer
import mlb_matchup_rankings_v21 as rankings

VERSION = "MLB Matchup Hub V6.1 • Cleanup Step 17 Deep Research Performance"
FROZEN_MATCHUP_CHAIN = current.FROZEN_MATCHUP_CHAIN
FROZEN_STEP16_PRESENTATION = "mlb_matchup_hub_v56"

PROFILE_CACHE_TTL_SECONDS = 300
RESULT_CACHE_TTL_SECONDS = 300
MAX_PROFILE_CACHE_ENTRIES = 80
MAX_RESULT_CACHE_ENTRIES = 16

_PROFILE_CACHE_KEY = "mx57_profile_cache"
_RESULT_CACHE_KEY = "mx57_result_cache"
_PERF_KEY = "mx57_perf_last"

_BUILDER_SPECS = (
    (step1, "_build_foundation", "step1"),
    (step2, "_build_profile", "step2"),
    (step3, "_build_step3", "step3"),
    (step4, "_build_step4", "step4"),
    (step5, "_build_step5", "step5"),
    (step6, "_build_step6", "step6"),
    (step7, "_build_step7", "step7"),
    (step8, "_build_step8", "step8"),
    (step9, "_build_step9", "step9"),
    (step10, "_build_step10", "step10"),
)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _session_dict(key: str) -> dict[Any, Any]:
    value = st.session_state.get(key)
    if not isinstance(value, dict):
        value = {}
        st.session_state[key] = value
    return value


def _trim(store: dict[Any, Any], limit: int) -> dict[Any, Any]:
    if len(store) <= int(limit):
        return store
    ordered = sorted(
        store.items(),
        key=lambda item: float((item[1] or {}).get("ts") or 0.0),
        reverse=True,
    )
    return dict(ordered[: int(limit)])


def _cache_get(store_key: str, key: Any, ttl_seconds: int) -> Any | None:
    store = _session_dict(store_key)
    entry = store.get(key)
    if not isinstance(entry, dict):
        return None
    age = time.time() - float(entry.get("ts") or 0.0)
    if age < 0 or age > int(ttl_seconds):
        store.pop(key, None)
        st.session_state[store_key] = store
        return None
    return copy.deepcopy(entry.get("value"))


def _cache_put(store_key: str, key: Any, value: Any, limit: int) -> None:
    store = _session_dict(store_key)
    store[key] = {"ts": time.time(), "value": copy.deepcopy(value)}
    st.session_state[store_key] = _trim(store, limit)


def _selection_context(games_df) -> dict[str, Any] | None:
    if games_df is None or games_df.empty:
        return None
    game_index = _safe_int(st.session_state.get("mh12_game", 0), 0)
    game_index = max(0, min(game_index, len(games_df) - 1))
    row = games_df.iloc[game_index]
    game_pk = _safe_int(row.get("game_pk"), game_index)

    player_id = _safe_int(st.session_state.get("mx56_active_player_id"), 0)
    players = list(roster._all_hitters_v14(row) or [])
    player = None
    if player_id > 0:
        player = next((p for p in players if _safe_int(p.get("id"), 0) == player_id), None)
    if player is None and players:
        player_index = _safe_int(st.session_state.get("mh12_player", 0), 0)
        player_index = max(0, min(player_index, len(players) - 1))
        player = players[player_index]
        player_id = _safe_int(player.get("id"), 0)
    if not player or player_id <= 0:
        return None

    fingerprint = (
        game_pk,
        player_id,
        str(row.get("game_date") or ""),
        str(row.get("status") or ""),
        str(row.get("first_pitch_et") or ""),
        _safe_int(row.get("away_pitcher_id"), 0),
        _safe_int(row.get("home_pitcher_id"), 0),
        str(row.get("away_pitcher") or ""),
        str(row.get("home_pitcher") or ""),
        str(player.get("source") or ""),
        _safe_int(player.get("slot"), 99),
        bool(player.get("lineup_role")),
        str(player.get("side") or ""),
        _safe_int(player.get("opponent_pitcher_id"), 0),
    )
    return {
        "fingerprint": fingerprint,
        "game_pk": game_pk,
        "player_id": player_id,
        "game_date": str(row.get("game_date") or ""),
    }


def _record(perf: dict[str, Any], name: str, source: str, elapsed_ms: float = 0.0) -> None:
    bucket = perf.setdefault(name, {"calls": 0, "compute_ms": 0.0, "render_hits": 0, "session_hits": 0})
    bucket["calls"] += 1
    if source == "compute":
        bucket["compute_ms"] += round(float(elapsed_ms), 3)
    elif source == "render":
        bucket["render_hits"] += 1
    elif source == "session":
        bucket["session_hits"] += 1


def _memoized_builder(
    name: str,
    original: Callable[..., Any],
    render_cache: dict[Any, Any],
    perf: dict[str, Any],
    identity_fn: Callable[[Any], dict[str, Any] | None],
):
    """Reuse one certified Step profile in-run and briefly across unchanged reruns."""
    def wrapped(games_df, *args: Any, **kwargs: Any):
        context = identity_fn(games_df)
        fingerprint = (context or {}).get("fingerprint")
        call_tag = (tuple(repr(x) for x in args), tuple(sorted((k, repr(v)) for k, v in kwargs.items())))
        key = (name, fingerprint, call_tag)

        if key in render_cache:
            _record(perf, name, "render")
            return copy.deepcopy(render_cache[key])

        if fingerprint is not None:
            cached = _cache_get(_PROFILE_CACHE_KEY, key, PROFILE_CACHE_TTL_SECONDS)
            if cached is not None:
                render_cache[key] = copy.deepcopy(cached)
                _record(perf, name, "session")
                return cached

        started = time.perf_counter()
        value = original(games_df, *args, **kwargs)
        elapsed = (time.perf_counter() - started) * 1000.0
        _record(perf, name, "compute", elapsed)
        render_cache[key] = copy.deepcopy(value)
        if fingerprint is not None and value is not None:
            _cache_put(_PROFILE_CACHE_KEY, key, value, MAX_PROFILE_CACHE_ENTRIES)
        return value
    return wrapped


def _result_entry_key(context: dict[str, Any] | None) -> Any | None:
    return (context or {}).get("fingerprint")


def _result_entry_get(key: Any) -> dict[str, Any] | None:
    if key is None:
        return None
    return _cache_get(_RESULT_CACHE_KEY, key, RESULT_CACHE_TTL_SECONDS)


def _result_entry_put(key: Any, value: dict[str, Any]) -> None:
    if key is not None:
        _cache_put(_RESULT_CACHE_KEY, key, value, MAX_RESULT_CACHE_ENTRIES)


def _raw_signature(raw: dict[str, Any] | None) -> tuple[Any, ...]:
    d = raw or {}
    return (
        _safe_int(d.get("game_pk"), 0),
        _safe_int(d.get("player_id"), 0),
        str(d.get("probability_status") or ""),
        d.get("p1_plus"),
        d.get("p0"),
        d.get("p2_plus"),
        d.get("expected_hits"),
    )


def _profile_matches(raw: dict[str, Any] | None, context: dict[str, Any] | None) -> bool:
    if not raw or not context:
        return False
    return (
        _safe_int(raw.get("game_pk"), -1) == _safe_int(context.get("game_pk"), -2)
        and _safe_int(raw.get("player_id"), -1) == _safe_int(context.get("player_id"), -2)
    )


def _cached_step11(
    original: Callable[..., Any],
    perf: dict[str, Any],
    identity_fn: Callable[[Any], dict[str, Any] | None],
):
    """Cache only the normal certified Step 11 run; explicit simulation overrides pass through."""
    def wrapped(games_df, simulations: int | None = None):
        if simulations is not None:
            started = time.perf_counter()
            value = original(games_df, simulations=simulations)
            _record(perf, "step11", "compute", (time.perf_counter() - started) * 1000.0)
            return value

        context = identity_fn(games_df)
        key = _result_entry_key(context)
        entry = _result_entry_get(key)
        if entry and entry.get("raw") is not None:
            _record(perf, "step11", "session")
            perf["step11_cache_hit"] = True
            return copy.deepcopy(entry["raw"])

        started = time.perf_counter()
        raw = original(games_df, simulations=None)
        elapsed = (time.perf_counter() - started) * 1000.0
        _record(perf, "step11", "compute", elapsed)
        perf["step11_cache_hit"] = False
        if key is not None and raw is not None and _profile_matches(raw, context):
            _result_entry_put(key, {"raw": raw, "final": None, "raw_signature": _raw_signature(raw)})
        return raw
    return wrapped


def _cached_final(
    original: Callable[..., Any],
    games_df,
    perf: dict[str, Any],
    identity_fn: Callable[[Any], dict[str, Any] | None],
):
    """Reuse Step 12 only when it belongs to the same cached Step 11 profile."""
    def wrapped(raw, *args: Any, **kwargs: Any):
        persist = kwargs.get("persist", True)
        if persist is False:
            started = time.perf_counter()
            value = original(raw, *args, **kwargs)
            _record(perf, "step12", "compute", (time.perf_counter() - started) * 1000.0)
            return value

        context = identity_fn(games_df)
        key = _result_entry_key(context)
        entry = _result_entry_get(key)
        signature = _raw_signature(raw)
        if (
            entry
            and entry.get("final") is not None
            and tuple(entry.get("raw_signature") or ()) == signature
            and _profile_matches(raw, context)
        ):
            _record(perf, "step12", "session")
            perf["step12_cache_hit"] = True
            return copy.deepcopy(entry["final"])

        started = time.perf_counter()
        final = original(raw, *args, **kwargs)
        elapsed = (time.perf_counter() - started) * 1000.0
        _record(perf, "step12", "compute", elapsed)
        perf["step12_cache_hit"] = False
        if key is not None and raw is not None and _profile_matches(raw, context):
            _result_entry_put(key, {"raw": raw, "final": final, "raw_signature": signature})
        return final
    return wrapped


def _lazy_legacy(original: Callable[..., Any], perf: dict[str, Any]):
    """Collapsed Legacy V1 becomes truly lazy instead of silently executing every rerun."""
    def wrapped(games_df, *args: Any, **kwargs: Any):
        context = _selection_context(games_df) or {}
        suffix = f"{context.get('game_pk', 0)}_{context.get('player_id', 0)}"
        state_key = f"mx57_legacy_loaded_{suffix}"
        if st.button("Load Legacy V1 audit", key=f"mx57_legacy_button_{suffix}"):
            st.session_state[state_key] = True
        if not bool(st.session_state.get(state_key, False)):
            perf["legacy_v1"] = "deferred"
            st.caption("⚡ Legacy V1 is asleep until you load it, so it no longer slows the normal Matchup Explorer run.")
            return None
        started = time.perf_counter()
        value = original(games_df, *args, **kwargs)
        perf["legacy_v1"] = {"loaded_ms": round((time.perf_counter() - started) * 1000.0, 3)}
        return value
    return wrapped


def _lazy_rankings(original: Callable[..., Any], perf: dict[str, Any]):
    """Collapsed Daily Top 5 becomes load-on-demand as well."""
    def wrapped(games_df, *args: Any, **kwargs: Any):
        game_date = "slate"
        try:
            if games_df is not None and not games_df.empty:
                game_date = str(games_df.iloc[0].get("game_date") or "slate")[:10]
        except Exception:
            pass
        state_key = f"mx57_rankings_loaded_{game_date}"
        if st.button("Load Daily Top 5 rankings", key=f"mx57_rankings_button_{game_date}"):
            st.session_state[state_key] = True
        if not bool(st.session_state.get(state_key, False)):
            perf["rankings"] = "deferred"
            st.caption("⚡ Daily Top 5 is load-on-demand and no longer computes while its section is collapsed.")
            return None
        started = time.perf_counter()
        value = original(games_df, *args, **kwargs)
        perf["rankings"] = {"loaded_ms": round((time.perf_counter() - started) * 1000.0, 3)}
        return value
    return wrapped


def render_matchup_hub(games_df, section_header=None, status_info=None, team_logo=None, h=None):
    if games_df is None or games_df.empty:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)

    render_cache: dict[Any, Any] = {}
    perf: dict[str, Any] = {"version": VERSION, "profile_ttl_s": PROFILE_CACHE_TTL_SECONDS, "result_ttl_s": RESULT_CACHE_TTL_SECONDS}
    identity_holder: dict[str, Any] = {}

    def identity_fn(gdf):
        if "context" not in identity_holder:
            identity_holder["context"] = _selection_context(gdf)
        return identity_holder.get("context")

    originals: list[tuple[Any, str, Callable[..., Any]]] = []
    for module, attr, name in _BUILDER_SPECS:
        original = getattr(module, attr)
        originals.append((module, attr, original))
        setattr(module, attr, _memoized_builder(name, original, render_cache, perf, identity_fn))

    original_step11 = final_layer._build_step11_fallback
    original_final = calibration.build_final_intelligence
    original_legacy = legacy_v1.render_player_layer
    original_rankings = rankings.render_daily_rankings

    final_layer._build_step11_fallback = _cached_step11(original_step11, perf, identity_fn)
    calibration.build_final_intelligence = _cached_final(original_final, games_df, perf, identity_fn)
    legacy_v1.render_player_layer = _lazy_legacy(original_legacy, perf)
    rankings.render_daily_rankings = _lazy_rankings(original_rankings, perf)

    total_started = time.perf_counter()
    try:
        return current.render_matchup_hub(games_df, section_header, status_info, team_logo, h)
    finally:
        perf["total_render_ms"] = round((time.perf_counter() - total_started) * 1000.0, 3)
        context = identity_holder.get("context") or _selection_context(games_df)
        perf["identity"] = {
            "game_pk": (context or {}).get("game_pk"),
            "player_id": (context or {}).get("player_id"),
        }
        st.session_state[_PERF_KEY] = perf

        rankings.render_daily_rankings = original_rankings
        legacy_v1.render_player_layer = original_legacy
        calibration.build_final_intelligence = original_final
        final_layer._build_step11_fallback = original_step11
        for module, attr, original in reversed(originals):
            setattr(module, attr, original)


__all__ = [
    "FROZEN_MATCHUP_CHAIN",
    "FROZEN_STEP16_PRESENTATION",
    "PROFILE_CACHE_TTL_SECONDS",
    "RESULT_CACHE_TTL_SECONDS",
    "VERSION",
    "_BUILDER_SPECS",
    "_memoized_builder",
    "_raw_signature",
    "_selection_context",
    "render_matchup_hub",
]
