"""WNBA Rebounds V2.2.2 — cold-start team-environment resilience.

Preserves V2.2.1 SportsGameOdds subscription-safe Step 13 and all Step 1-12
model logic. This patch fixes a reboot-only failure mode in Steps 7/8/9/10:
transient ESPN team-stat request failures were cached for six hours by the
shared Streamlit cache, so one bad cold-start request could leave an entire
matchup stuck in CHECK even though the same teams had verified minutes earlier.

Reliability rules:
- Use the same ESPN WNBA team-stat endpoint and same parsing/math as V1.9.
- Retry each cold team-stat request up to 3 times with a slightly longer timeout.
- Cache successful payloads for six hours, but do NOT cache transport failures.
- Persist only verified provider payload results to a small <=6h disk fallback,
  equivalent to the existing six-hour cache TTL, so a reboot during a brief ESPN
  outage can reuse a recent verified same-season team environment.
- If a Step-7, Step-8 or Step-10 aggregate frame is incomplete, clear only that
  failed aggregate cache and retry once. If still incomplete, leave the cache
  cleared so the next rerun can try again instead of freezing the failure for 6h.
- No sportsbook line, rebound projection, no-vig, EV or Monte Carlo math changes.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd
import streamlit as st

import wnba_players_v25 as players
import wnba_schedule_v24 as schedule_v24
import wnba_rebounds_hub_v16 as step7mod
import wnba_rebounds_hub_v17 as step8mod
import wnba_rebounds_hub_v19 as step10mod
import wnba_rebounds_hub_v221 as base

MODEL_VERSION = "WNBA REBOUNDS V2.2.2 • RESILIENT COLD-START TEAM ENVIRONMENT"
CACHE_TTL_SECONDS = 6 * 60 * 60
CACHE_DIR = Path(os.path.expanduser("~/.cache/kyre_sports_ai/wnba_team_env_v222"))

# Capture originals once so temporary monkey-patches can never recurse.
_ORIGINAL_BUILD7 = step7mod._build_step7_cached
_ORIGINAL_BUILD8 = step8mod._build_step8_cached
_ORIGINAL_BUILD10 = step10mod._build_step10_cached


def _json_safe(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    try:
        return float(value)
    except Exception:
        return str(value)


def _disk_path(team_id: int, season: int) -> Path:
    return CACHE_DIR / f"{int(season)}_{int(team_id)}.json"


def _write_verified_disk(team_id: int, season: int, env: dict) -> None:
    # A provider payload is worth persisting when at least one parser path is
    # usable. The individual Step 7/8/10 gates still decide whether their fields
    # are sufficient; this never promotes CHECK data to VERIFIED on its own.
    if not isinstance(env, dict) or not env.get("provider_payload_received"):
        return
    payload = {
        "saved_at": time.time(),
        "season": int(season),
        "team_id": int(team_id),
        "env": _json_safe(env),
    }
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _disk_path(team_id, season)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        pass


def _read_recent_disk(team_id: int, season: int):
    path = _disk_path(team_id, season)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        age = max(0.0, time.time() - float(payload.get("saved_at") or 0.0))
        if age > CACHE_TTL_SECONDS:
            return None
        if int(payload.get("season") or 0) != int(season):
            return None
        if int(payload.get("team_id") or 0) != int(team_id):
            return None
        env = payload.get("env")
        if not isinstance(env, dict):
            return None
        env = dict(env)
        env["source"] = "ESPN WNBA team statistics • verified persistent <=6h fallback"
        env["persistent_fallback"] = True
        env["persistent_age_seconds"] = int(age)
        return env
    except Exception:
        return None


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False, max_entries=64)
def _team_environment_resilient_cached(team_id: int, day: str) -> dict:
    """Shared team environment where transport failures are never sticky."""
    team_id = int(team_id)
    day = str(day)
    season = int(pd.to_datetime(day).year)
    slug = players.TEAM_SLUGS.get(team_id)
    if not slug:
        raise RuntimeError(f"no ESPN team slug for team_id={team_id}")

    payload = None
    meta = {}
    try:
        payload, meta = schedule_v24._request_json(
            "ESPN WNBA resilient team shooting/rebounding/pace stats",
            step10mod.ESPN_TEAM_STATS.format(team=slug),
            params={"season": season},
            timeout=7,
            attempts=3,
        )
    except Exception as exc:
        meta = {"error": str(exc)}
        payload = None

    if payload is None:
        fallback = _read_recent_disk(team_id, season)
        if fallback is not None:
            return fallback
        # Raising is deliberate: Streamlit does not cache exceptions, so this
        # transient failure can be retried on the next aggregate attempt/rerun.
        raise RuntimeError(str((meta or {}).get("error") or "empty ESPN team-stat response"))

    shooting = step7mod._parse_team_shooting(payload)
    rebounding = step8mod._parse_team_rebounding(payload)
    pace = step10mod._parse_pace_inputs(payload, shooting, rebounding)
    env = {
        "ok": bool(shooting.get("ok") or rebounding.get("ok") or pace.get("ok")),
        "shooting": shooting,
        "rebounding": rebounding,
        "pace": pace,
        "source": "ESPN WNBA team statistics • resilient 3-attempt fetch",
        "team_id": team_id,
        "provider_payload_received": True,
        "persistent_fallback": False,
    }
    _write_verified_disk(team_id, season, env)
    return env


def _shooting_from_resilient_environment(team_id: int, day: str) -> dict:
    env = _team_environment_resilient_cached(int(team_id), str(day))
    out = dict(env.get("shooting") or {})
    out["source"] = env.get("source") or "ESPN WNBA team statistics"
    out["team_id"] = int(team_id)
    if not out.get("ok") and not out.get("error"):
        out["error"] = env.get("error") or "shooting fields unavailable"
    return out


def _clear_cached_function(func) -> None:
    try:
        func.clear()
    except Exception:
        pass


def _retry_aggregate(original, day, slate):
    """Retry an incomplete aggregate once and never leave a failed frame sticky."""
    frame, info = original(day, slate)
    if bool((info or {}).get("ready")):
        return frame, info

    _clear_cached_function(original)
    frame2, info2 = original(day, slate)
    if bool((info2 or {}).get("ready")):
        return frame2, info2

    # Important: do not preserve a failed aggregate for six hours. Successful
    # team environments remain cached independently, while failed teams can retry.
    _clear_cached_function(original)
    return frame2, info2


def _build_step7_resilient(day: str, slate: pd.DataFrame):
    return _retry_aggregate(_ORIGINAL_BUILD7, day, slate)


def _build_step8_resilient(day: str, slate: pd.DataFrame):
    return _retry_aggregate(_ORIGINAL_BUILD8, day, slate)


def _build_step10_resilient(day: str, slate: pd.DataFrame):
    return _retry_aggregate(_ORIGINAL_BUILD10, day, slate)


def render_wnba_rebounds_hub(*args, **kwargs):
    # Patch the exact functions used throughout the V1.9 chain. V1.9 itself
    # temporarily maps Step 7/8 to its shared environment; by replacing the V1.9
    # environment symbol first, its normal patch automatically points to this
    # resilient implementation.
    old_env10 = step10mod._team_environment_pace_cached
    old_build7 = step7mod._build_step7_cached
    old_build8 = step8mod._build_step8_cached
    old_build10 = step10mod._build_step10_cached

    step10mod._team_environment_pace_cached = _team_environment_resilient_cached
    step7mod._build_step7_cached = _build_step7_resilient
    step8mod._build_step8_cached = _build_step8_resilient
    step10mod._build_step10_cached = _build_step10_resilient

    try:
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
        st.caption(
            "⚡ V2.2.2 cold-start reliability • ESPN team environment uses 3 attempts • "
            "transport failures are not six-hour cached • incomplete Step-7/8/10 frames auto-retry once • "
            "verified <=6h persistent team-stat fallback across reboot • Steps 1-13 math unchanged."
        )
        return out
    finally:
        step10mod._team_environment_pace_cached = old_env10
        step7mod._build_step7_cached = old_build7
        step8mod._build_step8_cached = old_build8
        step10mod._build_step10_cached = old_build10


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
