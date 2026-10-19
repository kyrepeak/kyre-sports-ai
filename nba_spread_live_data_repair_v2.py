"""NBA Spread live-data repair V2 — additive verified market transport bridge."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import nba_spread_live_data_repair_v1 as frozen_v1
from nba_spread_sportsbook_observations_v2 import load_verified_sportsbook_observations_v2

MODEL_VERSION = "NBA_SPREAD_LIVE_DATA_REPAIR_V2"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_FROZEN_STEPS = False
METRIC_SUBSTITUTION = False

resolve_sgo_api_key = frozen_v1.resolve_sgo_api_key
load_public_betting_payload = frozen_v1.load_public_betting_payload
build_public_betting_features = frozen_v1.build_public_betting_features


def load_market_payload_v2(schedule_games: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Load V2 sportsbook observations through the frozen credential contract."""
    key = resolve_sgo_api_key()
    if not key:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SPORTSGAMEODDS_CREDENTIAL_UNAVAILABLE",
            "source": "SportsGameOdds",
            "observations": [],
            "fabrication": False,
            "page_wide_source_authority": False,
            "sportsbook_projection_influence": 0.0,
        }

    def _secret_getter(name: str) -> str | None:
        return key if name == "SPORTSGAMEODDS_API_KEY" else None

    try:
        payload = load_verified_sportsbook_observations_v2(
            schedule_games,
            secret_getter=_secret_getter,
        )
    except Exception as exc:
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": f"SPORTSGAMEODDS_TRANSPORT_ERROR:{type(exc).__name__}",
            "source": "SportsGameOdds",
            "observations": [],
            "fabrication": False,
            "page_wide_source_authority": False,
            "sportsbook_projection_influence": 0.0,
        }
    if not isinstance(payload, Mapping):
        return {
            "verification": "UNAVAILABLE",
            "diagnostic_state": "SPORTSGAMEODDS_INVALID_PAYLOAD",
            "source": "SportsGameOdds",
            "observations": [],
            "fabrication": False,
            "page_wide_source_authority": False,
            "sportsbook_projection_influence": 0.0,
        }
    return dict(payload)


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
