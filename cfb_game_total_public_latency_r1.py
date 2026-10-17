"""CFB Game Total public cold-start latency hardening R1.

Additive transport-only adapter.  It preserves the existing Kyre/ESPN/Action
source set, model ownership, presentation, and selected-game runtime while
removing duplicate same-day Kyre transport work and running the independent
ESPN FBS/FCS Phoenix-day fallback requests concurrently.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, Mapping

MODEL_VERSION = "CFB GAME TOTAL PUBLIC LATENCY R1"
ACTIVE_MARKER = "CFB_GAME_TOTAL_PUBLIC_LATENCY_R1_ACTIVE"
MAX_SCOREBOARD_WORKERS = 4
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_SELECTED_GAME_RUNTIME = False
SOURCE_DIVERSITY_REDUCED = False


def install_shared_daily_slate_loaders(page_module: Any) -> dict[str, Any]:
    """Share one same-day Kyre transport outcome inside the current render.

    Successes and failures are both memoized.  That matters because the hosted
    Kyre endpoint can return/timeout on the first loader; without failure
    memoization the second TTL loader immediately repeats the same 20s call.
    """
    original_60 = page_module._load_slate_cached_60
    original_20 = page_module._load_slate_cached_20
    outcomes: dict[str, tuple[str, Any]] = {}

    def _load(day_iso: str, delegate):
        key = str(day_iso)
        cached = outcomes.get(key)
        if cached is not None:
            kind, value = cached
            if kind == "error":
                raise value
            return dict(value)
        try:
            payload = dict(delegate(day_iso))
        except Exception as exc:
            outcomes[key] = ("error", exc)
            raise
        outcomes[key] = ("ok", payload)
        return dict(payload)

    def load_60(day_iso: str):
        return _load(day_iso, original_60)

    def load_20(day_iso: str):
        return _load(day_iso, original_20)

    load_60._cfbgt_latency_shared = True  # type: ignore[attr-defined]
    load_20._cfbgt_latency_shared = True  # type: ignore[attr-defined]
    page_module._load_slate_cached_60 = load_60
    page_module._load_slate_cached_20 = load_20
    return {
        "module": page_module,
        "load_60": original_60,
        "load_20": original_20,
        "wrapped_60": load_60,
        "wrapped_20": load_20,
    }


def restore_shared_daily_slate_loaders(originals: Mapping[str, Any]) -> None:
    module = originals["module"]
    if getattr(module, "_load_slate_cached_60", None) is originals["wrapped_60"]:
        module._load_slate_cached_60 = originals["load_60"]
    if getattr(module, "_load_slate_cached_20", None) is originals["wrapped_20"]:
        module._load_slate_cached_20 = originals["load_20"]


def build_parallel_scoreboard_payload(fallback_module: Any, selected_phoenix_date, *, scoreboard_payloads=None):
    """Equivalent fallback payload with independent ESPN fetches overlapped."""
    attempts = [
        (day, group_id, subdivision)
        for day in fallback_module.upstream_scoreboard_dates_for_phoenix_day(selected_phoenix_date)
        for group_id, subdivision in ((80, "FBS"), (81, "FCS"))
    ]
    fetched: dict[tuple[str, int], Mapping[str, Any]] = {}
    errors: dict[tuple[str, int], Exception] = {}

    if scoreboard_payloads is None:
        with ThreadPoolExecutor(max_workers=min(MAX_SCOREBOARD_WORKERS, max(1, len(attempts)))) as pool:
            futures = {
                (day, group_id): pool.submit(fallback_module._fetch_scoreboard_payload, day, group_id)
                for day, group_id, _subdivision in attempts
            }
            for day, group_id, _subdivision in attempts:
                key = (day, group_id)
                try:
                    payload = futures[key].result()
                    fetched[key] = dict(payload) if isinstance(payload, Mapping) else {}
                except Exception as exc:
                    errors[key] = exc
    else:
        for day, group_id, _subdivision in attempts:
            key = (day, group_id)
            fetched[key] = dict(scoreboard_payloads.get(key) or {})

    normalized_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for day, group_id, subdivision in attempts:
        key = (day, group_id)
        exc = errors.get(key)
        if exc is not None:
            diagnostics.append({
                "date": day,
                "group_id": group_id,
                "subdivision": subdivision,
                "ok": False,
                "games": 0,
                "error": f"{type(exc).__name__}: {exc}"[:220],
            })
            continue
        try:
            payload = fetched.get(key, {})
            count = 0
            for event in payload.get("events") or []:
                game = fallback_module.normalize_scoreboard_event(event, subdivision=subdivision)
                if game is not None:
                    normalized_rows.append(game)
                    count += 1
            diagnostics.append({
                "date": day,
                "group_id": group_id,
                "subdivision": subdivision,
                "ok": True,
                "games": count,
            })
        except Exception as parse_exc:
            diagnostics.append({
                "date": day,
                "group_id": group_id,
                "subdivision": subdivision,
                "ok": False,
                "games": 0,
                "error": f"{type(parse_exc).__name__}: {parse_exc}"[:220],
            })

    games = fallback_module.merge_scoreboard_games(normalized_rows, selected_day=selected_phoenix_date)
    if not any(row.get("ok") for row in diagnostics):
        raise RuntimeError("all fallback scoreboard transports failed")
    return {
        "service": "Kyre Sports Streamlit Runtime Fallback",
        "sport": "college_football",
        "schema_version": "cfb_daily_slate_runtime_fallback_r1",
        "model_version": fallback_module.MODEL_VERSION,
        "requested_phoenix_date": selected_phoenix_date.isoformat(),
        "timezone": "America/Phoenix",
        "game_count": len(games),
        "games": games,
        "diagnostics": {"scoreboard_attempts": diagnostics},
        "sportsbook_projection_influence": fallback_module.SPORTSBOOK_PROJECTION_INFLUENCE,
        "page_wide_source_authority": fallback_module.PAGE_WIDE_SOURCE_AUTHORITY,
        "fabrication": fallback_module.FABRICATION,
    }


@contextmanager
def install_parallel_scoreboard_fallback(fallback_module: Any):
    original = fallback_module.build_requests_fallback_payload
    canonical = (
        getattr(original, "__module__", "") == getattr(fallback_module, "__name__", "")
        and getattr(original, "__name__", "") == "build_requests_fallback_payload"
    )
    if not canonical:
        # Preserve injected test/diagnostic delegates instead of shadowing them.
        yield
        return

    def build(selected_phoenix_date, *, scoreboard_payloads=None):
        return build_parallel_scoreboard_payload(
            fallback_module,
            selected_phoenix_date,
            scoreboard_payloads=scoreboard_payloads,
        )

    fallback_module.build_requests_fallback_payload = build
    try:
        yield
    finally:
        if fallback_module.build_requests_fallback_payload is build:
            fallback_module.build_requests_fallback_payload = original


__all__ = [
    "ACTIVE_MARKER",
    "MAX_SCOREBOARD_WORKERS",
    "MODEL_VERSION",
    "SOURCE_DIVERSITY_REDUCED",
    "build_parallel_scoreboard_payload",
    "install_parallel_scoreboard_fallback",
    "install_shared_daily_slate_loaders",
    "restore_shared_daily_slate_loaders",
]
