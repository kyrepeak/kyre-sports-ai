"""NFL Moneyline V12 — performance-only fast execution over frozen V11.

V12 preserves the exact certified V11 -> V10 -> V9 -> V8 analytical/runtime
chain. The first render (or any stale/mismatched render) still executes the full
frozen engine. A short request-session hot path may reuse exact model-side state
for the same date/game identity while refreshing the sportsbook market on every
visit through the certified Kyre API adapter and rebuilding frozen V7 edge/EV.

The hot window is deliberately shorter than the existing upstream schedule,
injury, roster, and Monte Carlo cache windows. Current pregame eligibility is
rechecked before hot reuse. Any date, game-identity, model-fingerprint, readiness,
or age mismatch falls back to the complete frozen V11 chain.

No model formula, 5M Monte Carlo count, market freshness rule, identity rule,
edge/EV formula, grade, stake behavior, or visible V9 card output is changed.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import json
import time
from time import perf_counter
from typing import Any, Callable, Iterator

import pandas as pd
import streamlit as st

import nfl_hub_v1 as foundation
import nfl_moneyline_hub_v1 as step1
import nfl_moneyline_hub_v43 as calibration_page
import nfl_moneyline_hub_v7 as frozen_v7
import nfl_moneyline_hub_v11 as v11
import nfl_moneyline_market_api_v1 as kyre_market

MODEL_VERSION = "NFL MONEYLINE V12.1 • FRESH-MARKET HOT REFRESH • V11 FROZEN"
FROZEN_PRIOR = "nfl_moneyline_hub_v11"
FROZEN_ENGINE = "nfl_moneyline_hub_v8"
PERFORMANCE_ONLY = True
SPORTSBOOK_MODEL_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MONTE_CARLO_SIMULATIONS = 5_000_000
HOT_MODEL_TTL_SECONDS = 30.0
HOT_STATE_KEY = "nfl_moneyline_v12_model_hot_state"


class _Sink:
    """Minimal DeltaGenerator-like sink for output that is already invisible."""

    def __init__(self, stats: dict[str, Any], name: str = "sink") -> None:
        self._stats = stats
        self._name = name

    def _hit(self, name: str | None = None) -> None:
        key = name or self._name
        suppressed = self._stats.setdefault("suppressed", {})
        suppressed[key] = int(suppressed.get(key) or 0) + 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def __getattr__(self, name: str):
        def _method(*args: Any, **kwargs: Any):
            self._hit(name)
            if name in {"container", "empty", "expander", "status"}:
                return self
            if name == "progress":
                return self
            return None
        return _method

    def container(self, *args: Any, **kwargs: Any):
        self._hit("container")
        return self

    def empty(self, *args: Any, **kwargs: Any):
        self._hit("empty")
        return self

    def update(self, *args: Any, **kwargs: Any):
        self._hit("update")
        return None


_SIMPLE_OUTPUTS = (
    "markdown",
    "caption",
    "dataframe",
    "table",
    "write",
    "text",
    "code",
    "json",
    "image",
    "metric",
    "info",
    "warning",
    "success",
    "error",
    "header",
    "subheader",
    "divider",
    "toast",
)
_CONTEXT_OUTPUTS = ("spinner", "expander", "container", "empty", "status", "progress")


def _simple_sink(stats: dict[str, Any], name: str) -> Callable[..., None]:
    def _wrapped(*args: Any, **kwargs: Any) -> None:
        suppressed = stats.setdefault("suppressed", {})
        suppressed[name] = int(suppressed.get(name) or 0) + 1
        return None
    return _wrapped


def _context_sink(stats: dict[str, Any], name: str) -> Callable[..., _Sink]:
    def _wrapped(*args: Any, **kwargs: Any) -> _Sink:
        suppressed = stats.setdefault("suppressed", {})
        suppressed[name] = int(suppressed.get(name) or 0) + 1
        return _Sink(stats, name)
    return _wrapped


def _columns_sink(stats: dict[str, Any], spec: Any = 1, *args: Any, **kwargs: Any):
    suppressed = stats.setdefault("suppressed", {})
    suppressed["columns"] = int(suppressed.get("columns") or 0) + 1
    if isinstance(spec, int):
        count = max(0, spec)
    else:
        try:
            count = len(spec)
        except Exception:
            count = 1
    return tuple(_Sink(stats, "column") for _ in range(count))


@contextmanager
def _sink_hidden_presentation(stats: dict[str, Any]) -> Iterator[None]:
    """Keep hidden legacy rendering session-safe.

    V11 already places the frozen legacy engine inside a CSS-hidden keyed
    container before any legacy child is created. Do not mutate top-level
    Streamlit methods here: multiple reruns/sessions share one process, so
    global method replacement can suppress presentation in another Moneyline
    render. The hidden V11 container remains the presentation-hiding layer.
    """
    stats["presentation_suppression_mode"] = "v11-css-hidden-container"
    yield

def _timed_request_memo(
    original: Callable[..., Any],
    key_fn: Callable[..., Any],
    stats: dict[str, Any],
    name: str,
) -> Callable[..., Any]:
    cache: dict[Any, Any] = {}

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        bucket = stats.setdefault(name, {"calls": 0, "misses": 0, "hits": 0, "work_ms": 0.0})
        bucket["calls"] += 1
        key = key_fn(*args, **kwargs)
        if key in cache:
            bucket["hits"] += 1
            return cache[key]
        bucket["misses"] += 1
        started = perf_counter()
        value = original(*args, **kwargs)
        bucket["work_ms"] += (perf_counter() - started) * 1000.0
        cache[key] = value
        return value

    return wrapped


def _schedule_key(day_str: Any, *args: Any, **kwargs: Any) -> tuple[str]:
    return (str(day_str or "").strip(),)


def _calibration_key(*args: Any, **kwargs: Any) -> tuple[str]:
    return ("frozen-calibration",)


def _gid(game: dict[str, Any]) -> str:
    value = str(game.get("game_id") or "").strip()
    if value:
        return value
    return f"{str(game.get('away_abbr') or '').strip().upper()}@{str(game.get('home_abbr') or '').strip().upper()}"


def _selected_day() -> str:
    selected = st.session_state.get("nfl_v1_date")
    try:
        return pd.to_datetime(selected).strftime("%Y-%m-%d")
    except Exception:
        return ""


def _pregame_ids(rows: Any) -> tuple[str, ...]:
    if isinstance(rows, pd.DataFrame):
        games = [src.to_dict() for _, src in rows.iterrows()]
    else:
        games = list(rows or [])
    return tuple(sorted(_gid(dict(game or {})) for game in games if _gid(dict(game or {}))))


def _model_fingerprint(game_ids: tuple[str, ...]) -> str:
    payload = {
        "game_ids": game_ids,
        "probability_ready": bool(st.session_state.get("nfl_moneyline_v43_probability_ready")),
        "mc_ready": bool(st.session_state.get("nfl_moneyline_v6_mc_ready")),
        "gameplan_ready": bool(st.session_state.get("nfl_moneyline_v3_gameplan_ready")),
        "probabilities": st.session_state.get("nfl_moneyline_v43_probability_outputs") or {},
        "mc": st.session_state.get("nfl_moneyline_v6_mc_outputs") or {},
        "profiles": st.session_state.get("nfl_moneyline_v4_strength_profiles") or {},
        "contexts": st.session_state.get("nfl_moneyline_v3_team_context") or st.session_state.get("nfl_moneyline_v2_team_context") or {},
        "gameplans": st.session_state.get("nfl_moneyline_v3_gameplan_context") or {},
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return sha256(raw).hexdigest()


def _record_hot_state(stats: dict[str, Any]) -> None:
    pregame = list(st.session_state.get("nfl_moneyline_v3_pregame") or st.session_state.get("nfl_moneyline_v1_pregame") or [])
    game_ids = _pregame_ids(pregame)
    day_str = _selected_day()
    if not day_str or not game_ids:
        st.session_state.pop(HOT_STATE_KEY, None)
        return
    st.session_state[HOT_STATE_KEY] = {
        "day": day_str,
        "game_ids": game_ids,
        "fingerprint": _model_fingerprint(game_ids),
        "built_at": time.time(),
        "ttl_seconds": HOT_MODEL_TTL_SECONDS,
        "simulations": MONTE_CARLO_SIMULATIONS,
        "sportsbook_model_influence": 0.0,
    }
    stats.setdefault("hot_path", {})["primed"] = True


def _fresh_pregame_for_hot_state(stats: dict[str, Any]) -> tuple[pd.DataFrame | None, str]:
    state = st.session_state.get(HOT_STATE_KEY) or {}
    day_str = _selected_day()
    if not state or not day_str or state.get("day") != day_str:
        return None, "missing-or-date-mismatch"
    age = max(0.0, time.time() - float(state.get("built_at") or 0.0))
    if age > HOT_MODEL_TTL_SECONDS:
        return None, "expired"
    if int(state.get("simulations") or 0) != MONTE_CARLO_SIMULATIONS:
        return None, "simulation-mismatch"
    if state.get("sportsbook_model_influence") != 0.0:
        return None, "market-firewall-mismatch"
    if not st.session_state.get("nfl_moneyline_v43_probability_ready") or not st.session_state.get("nfl_moneyline_v6_mc_ready"):
        return None, "model-not-ready"

    game_ids = tuple(state.get("game_ids") or ())
    if not game_ids or state.get("fingerprint") != _model_fingerprint(game_ids):
        return None, "fingerprint-mismatch"

    started = perf_counter()
    schedule, diag = foundation.load_nfl_slate(day_str)
    bucket = stats.setdefault("hot_eligibility", {"calls": 0, "work_ms": 0.0})
    bucket["calls"] += 1
    bucket["work_ms"] += (perf_counter() - started) * 1000.0
    if not (diag or {}).get("request_ok"):
        return None, "schedule-not-ready"
    pregame, _ = step1._pregame_partition(schedule, day_str, now_et=pd.Timestamp.now(tz=foundation.ET))
    if pregame is None or pregame.empty:
        return None, "no-current-pregame"
    if _pregame_ids(pregame) != game_ids:
        return None, "game-identity-mismatch"
    return pregame, "ready"


def _refresh_market_and_edge(pregame: pd.DataFrame, day_str: str, stats: dict[str, Any]) -> bool:
    market_started = perf_counter()
    snapshots, mdiag = kyre_market.fetch_nfl_moneyline_markets(pregame, day_str)
    stats["hot_market"] = {
        "calls": 1,
        "work_ms": (perf_counter() - market_started) * 1000.0,
        "games_requested": int(len(pregame)),
    }

    ready_games = int((mdiag or {}).get("games_with_market") or 0)
    market_ready = bool(len(pregame) and ready_games == len(pregame))
    st.session_state["nfl_moneyline_v5_market_snapshots"] = snapshots
    st.session_state["nfl_moneyline_v5_market_diag"] = mdiag
    st.session_state["nfl_moneyline_v5_market_ready"] = market_ready

    mc_outputs = st.session_state.get("nfl_moneyline_v6_mc_outputs") or {}
    edge_started = perf_counter()
    outputs: dict[str, Any] = {}
    ready_edges = 0
    for _, src in pregame.iterrows():
        game = src.to_dict()
        gid = _gid(game)
        out = frozen_v7._build_game_output(game, snapshots.get(gid, {}), mc_outputs.get(gid, {}))
        outputs[gid] = out
        if out.get("ready"):
            ready_edges += 1
    edge_ready = bool(market_ready and st.session_state.get("nfl_moneyline_v6_mc_ready") and ready_edges == len(pregame))
    st.session_state["nfl_moneyline_v7_edge_outputs"] = outputs
    st.session_state["nfl_moneyline_v7_edge_ready"] = edge_ready
    stats["hot_edge"] = {
        "calls": 1,
        "work_ms": (perf_counter() - edge_started) * 1000.0,
        "games_ready": ready_edges,
    }
    return True


def _store_speed_stats(stats: dict[str, Any], total_ms: float) -> None:
    try:
        st.session_state["nfl_moneyline_speed_v12_last"] = {
            "version": MODEL_VERSION,
            "total_wrapper_ms": max(0.0, float(total_ms)),
            "schedule": dict(stats.get("schedule") or {}),
            "calibration": dict(stats.get("calibration") or {}),
            "hot_path": dict(stats.get("hot_path") or {}),
            "hot_eligibility": dict(stats.get("hot_eligibility") or {}),
            "hot_market": dict(stats.get("hot_market") or {}),
            "hot_edge": dict(stats.get("hot_edge") or {}),
            "suppressed": dict(stats.get("suppressed") or {}),
            "suppressed_total": sum(int(v or 0) for v in (stats.get("suppressed") or {}).values()),
            "performance_only": True,
            "sportsbook_model_influence": 0.0,
            "stake_sizing_enabled": False,
            "monte_carlo_simulations": MONTE_CARLO_SIMULATIONS,
            "hot_model_ttl_seconds": HOT_MODEL_TTL_SECONDS,
            "model_math_changed": False,
            "market_semantics_changed": False,
            "freshness_rules_changed": False,
            "identity_rules_changed": False,
        }
    except Exception:
        pass


def _fast_hidden_run_frozen_engine(stats: dict[str, Any]) -> None:
    """Use fresh-market hot refresh when safe; otherwise execute exact frozen V8."""
    st.markdown(v11._HIDDEN_LEGACY_CSS, unsafe_allow_html=True)
    hidden = st.container(key=v11.LEGACY_CONTAINER_KEY)
    with hidden:
        legacy = st.empty()
        with legacy.container():
            with _sink_hidden_presentation(stats):
                pregame, reason = _fresh_pregame_for_hot_state(stats)
                hot = stats.setdefault("hot_path", {})
                hot["used"] = False
                hot["eligibility"] = reason
                if pregame is not None:
                    try:
                        if _refresh_market_and_edge(pregame, _selected_day(), stats):
                            hot["used"] = True
                            hot["market_refreshed"] = True
                    except Exception as exc:
                        hot["refresh_error"] = type(exc).__name__
                if not hot["used"]:
                    full_started = perf_counter()
                    v11.frozen_v9.frozen.render_nfl_moneyline_hub()
                    hot["full_engine_ms"] = (perf_counter() - full_started) * 1000.0
                    _record_hot_state(stats)
        legacy.empty()


def render_nfl_hub(market: str = "Moneyline"):
    if str(market or "Moneyline") != "Moneyline":
        raise RuntimeError("Moneyline V12 direct handler is Moneyline only.")

    stats: dict[str, Any] = {}
    started = perf_counter()

    original_schedule = foundation.load_nfl_slate
    original_calibration = calibration_page._fit_calibration_model
    original_hidden_runner = v11._hidden_run_frozen_engine

    foundation.load_nfl_slate = _timed_request_memo(
        original_schedule, _schedule_key, stats, "schedule"
    )
    calibration_page._fit_calibration_model = _timed_request_memo(
        original_calibration, _calibration_key, stats, "calibration"
    )
    v11._hidden_run_frozen_engine = lambda: _fast_hidden_run_frozen_engine(stats)

    try:
        return v11.render_nfl_hub(market)
    finally:
        v11._hidden_run_frozen_engine = original_hidden_runner
        calibration_page._fit_calibration_model = original_calibration
        foundation.load_nfl_slate = original_schedule
        _store_speed_stats(stats, (perf_counter() - started) * 1000.0)


__all__ = [
    "FROZEN_ENGINE",
    "FROZEN_PRIOR",
    "HOT_MODEL_TTL_SECONDS",
    "HOT_STATE_KEY",
    "MODEL_VERSION",
    "MONTE_CARLO_SIMULATIONS",
    "PERFORMANCE_ONLY",
    "SPORTSBOOK_MODEL_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_Sink",
    "_calibration_key",
    "_fast_hidden_run_frozen_engine",
    "_fresh_pregame_for_hot_state",
    "_model_fingerprint",
    "_pregame_ids",
    "_record_hot_state",
    "_refresh_market_and_edge",
    "_schedule_key",
    "_sink_hidden_presentation",
    "_timed_request_memo",
    "render_nfl_hub",
]