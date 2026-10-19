"""NBA Spread live-data repair V2 — additive verified market transport bridge."""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import os

import nba_spread_live_data_repair_v1 as frozen_v1
from nba_spread_espn_market_fallback_v1 import load_verified_espn_spread_observations_v1
from nba_spread_sportsbook_observations_v2 import load_verified_sportsbook_observations_v2

MODEL_VERSION = "NBA_SPREAD_LIVE_DATA_REPAIR_V2"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_FROZEN_STEPS = False
METRIC_SUBSTITUTION = False

load_public_betting_payload = frozen_v1.load_public_betting_payload
build_public_betting_features = frozen_v1.build_public_betting_features


def resolve_sgo_api_key() -> str | None:
    """Resolve the existing SportsGameOdds credential without bare-mode crashes."""
    env_key = str(os.getenv("SPORTSGAMEODDS_API_KEY") or "").strip()
    if env_key:
        return env_key
    try:
        value = frozen_v1.resolve_sgo_api_key()
    except Exception:
        return None
    text = str(value or "").strip()
    return text or None


def _unavailable(diagnostic: str, *, source: str = "SportsGameOdds+ESPN Public Scoreboard") -> dict[str, object]:
    return {
        "verification": "UNAVAILABLE",
        "diagnostic_state": diagnostic,
        "source": source,
        "observations": [],
        "fabrication": False,
        "page_wide_source_authority": False,
        "sportsbook_projection_influence": 0.0,
    }


def load_market_payload_v2(
    schedule_games: Sequence[Mapping[str, object]],
    *,
    credential_resolver: Callable[[], object] | None = None,
    sgo_loader: Callable[..., Mapping[str, object]] | None = None,
    espn_loader: Callable[[Sequence[Mapping[str, object]]], Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Prefer SportsGameOdds; fail over to verified ESPN-carried sportsbook rows."""
    credential_resolver = credential_resolver or resolve_sgo_api_key
    sgo_loader = sgo_loader or load_verified_sportsbook_observations_v2
    espn_loader = espn_loader or load_verified_espn_spread_observations_v1

    key = str(credential_resolver() or "").strip()
    primary_state = "SPORTSGAMEODDS_CREDENTIAL_UNAVAILABLE"
    if key:
        def _secret_getter(name: str) -> str | None:
            return key if name == "SPORTSGAMEODDS_API_KEY" else None

        try:
            sgo_payload = sgo_loader(
                schedule_games,
                secret_getter=_secret_getter,
            )
        except Exception as exc:
            sgo_payload = _unavailable(f"SPORTSGAMEODDS_TRANSPORT_ERROR:{type(exc).__name__}", source="SportsGameOdds")
        if isinstance(sgo_payload, Mapping):
            sgo_result = dict(sgo_payload)
            primary_state = str(sgo_result.get("diagnostic_state") or "SPORTSGAMEODDS_UNAVAILABLE")
            if str(sgo_result.get("verification") or "").upper() == "VERIFIED":
                sgo_result["source_chain"] = ["SportsGameOdds"]
                sgo_result["sportsbook_projection_influence"] = 0.0
                return sgo_result
        else:
            primary_state = "SPORTSGAMEODDS_INVALID_PAYLOAD"

    try:
        fallback_payload = espn_loader(schedule_games)
    except Exception as exc:
        fallback_payload = _unavailable(f"ESPN_MARKET_TRANSPORT_ERROR:{type(exc).__name__}", source="ESPN Public Scoreboard")

    if isinstance(fallback_payload, Mapping):
        fallback = dict(fallback_payload)
        fallback["primary_source_state"] = primary_state
        fallback["source_chain"] = ["SportsGameOdds", "ESPN Public Scoreboard"]
        fallback["sportsbook_projection_influence"] = 0.0
        if str(fallback.get("verification") or "").upper() == "VERIFIED":
            return fallback
        fallback_state = str(fallback.get("diagnostic_state") or "ESPN_MARKET_UNAVAILABLE")
    else:
        fallback_state = "ESPN_MARKET_INVALID_PAYLOAD"

    result = _unavailable(f"MARKET_SOURCES_UNAVAILABLE:{primary_state}|{fallback_state}")
    result["primary_source_state"] = primary_state
    result["fallback_source_state"] = fallback_state
    result["source_chain"] = ["SportsGameOdds", "ESPN Public Scoreboard"]
    return result


load_market_payload = load_market_payload_v2

__all__ = [
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_FROZEN_STEPS",
    "METRIC_SUBSTITUTION",
    "resolve_sgo_api_key",
    "load_public_betting_payload",
    "build_public_betting_features",
    "load_market_payload_v2",
    "load_market_payload",
]
