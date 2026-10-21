"""Display-identity successor over frozen WNBA PRA model artifact V1.

Adds official WNBA/NBA CDN presentation URLs only from verified numeric IDs
already present in the preserved projection frame. No projection, probability,
qualification, Monte Carlo, market, or selection math changes.
"""
from __future__ import annotations

from typing import Any, Mapping

import wnba_pra_page_model_artifact_v1 as prior

SCHEMA_VERSION = prior.SCHEMA_VERSION
_BASE_MODEL_ROW = prior._model_row
_hash_payload = prior._hash_payload
validate_model_artifact = prior.validate_model_artifact


def _positive_int(value: Any) -> int | None:
    try:
        result = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result > 0 else None


def _model_row(row: Mapping[str, Any], projection_map: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    out = _BASE_MODEL_ROW(row, projection_map)
    if out is None:
        return None
    pkey = str(row.get("player_key") or "")
    projection = projection_map.get(pkey, {})
    player_id = _positive_int(projection.get("PLAYER_ID"))
    team_id = _positive_int(projection.get("TEAM_ID"))
    out["player_id"] = player_id
    out["team_id"] = team_id
    out["headshot_url"] = (
        f"https://cdn.wnba.com/headshots/wnba/latest/1040x760/{player_id}.png" if player_id else ""
    )
    out["team_logo_url"] = (
        f"https://cdn.nba.com/logos/wnba/{team_id}/global/L/logo.svg" if team_id else ""
    )
    return out


def build_model_artifact(*args: Any, **kwargs: Any) -> dict[str, Any]:
    original = prior._model_row
    prior._model_row = _model_row
    try:
        return prior.build_model_artifact(*args, **kwargs)
    finally:
        prior._model_row = original


__all__ = ["SCHEMA_VERSION", "build_model_artifact", "validate_model_artifact", "_hash_payload", "_model_row"]
