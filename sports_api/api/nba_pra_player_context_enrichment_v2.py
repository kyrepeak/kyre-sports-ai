"""Production Kyre Sports API NBA PRA player-context enrichment V2.

Composes the frozen V1 collector with verified NBA Stats usage metadata while
keeping the public player-context route unchanged.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Callable, Mapping, Sequence

from . import nba_pra_player_context_v1 as base
from .nba_pra_usage_v1 import load_nba_usage_context

_BASE_COLLECT = base.collect_nba_pra_player_context
_USAGE_FIELDS = (
    "usage_pct",
    "usage_rank",
    "usage_team_size",
    "usage_games",
    "usage_minutes",
    "usage_period",
    "usage_source",
    "usage_scope",
)


def _merge_usage(result: dict[str, Any], names: Sequence[str], payload: Mapping[str, Any]) -> None:
    raw_profiles = payload.get("profiles") or {}
    if not isinstance(raw_profiles, Mapping):
        return
    profiles = result.get("profiles") or {}
    if not isinstance(profiles, dict):
        return
    for name in names:
        key = base._norm(name)
        target = profiles.get(key)
        raw = raw_profiles.get(key)
        if not isinstance(target, dict) or not isinstance(raw, Mapping):
            continue
        for field in _USAGE_FIELDS:
            value = raw.get(field)
            if value is not None and value != "":
                target[field] = value


def collect_nba_pra_player_context(
    slate_date: date,
    player_names: Sequence[str],
    *,
    team_codes: Sequence[str] | None = None,
    official_loader: Callable[[date, Sequence[str]], Any] | None = None,
    licensed_loaders: Sequence[Any] | None = None,
    basketball_reference_index_loader: Callable[[date, Sequence[str]], Any] | None = None,
    basketball_reference_loader: Callable[[date, Sequence[str]], Any] | None = None,
    basketball_reference_bulk_history_loader: Callable[..., Any] | None = None,
    cbs_roster_loader: Callable[[str], Any] | None = None,
    cbs_history_loader: Callable[..., Any] | None = None,
    usage_loader: Callable[[date, Sequence[str]], Any] | None = None,
) -> dict[str, Any]:
    result = _BASE_COLLECT(
        slate_date,
        player_names,
        team_codes=team_codes,
        official_loader=official_loader,
        licensed_loaders=licensed_loaders,
        basketball_reference_index_loader=basketball_reference_index_loader,
        basketball_reference_loader=basketball_reference_loader,
        basketball_reference_bulk_history_loader=basketball_reference_bulk_history_loader,
        cbs_roster_loader=cbs_roster_loader,
        cbs_history_loader=cbs_history_loader,
    )
    names = [base._text(name) for name in player_names if base._text(name)]
    loader = usage_loader or load_nba_usage_context
    health = result.setdefault("provider_health", {})
    try:
        payload = loader(slate_date, names)
        if not isinstance(payload, Mapping) or (payload.get("fabrication") is not False and usage_loader is None):
            raise ValueError("NBA_USAGE_CONTRACT_INVALID")
        status, _rows, detail = base._coerce_provider_payload(payload)
        _merge_usage(result, names, payload)
        health["nba_usage"] = base._health(status, detail, True)
    except Exception as exc:
        health["nba_usage"] = base._health("DEGRADED", type(exc).__name__, True)
    result["schema_version"] = "KYRE_NBA_PLAYER_CONTEXT_V2"
    return result


base.collect_nba_pra_player_context = collect_nba_pra_player_context
