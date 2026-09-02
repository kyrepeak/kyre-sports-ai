"""WNBA Step19M: strict FanDuel same-market line-move compatibility.

A hosted Step19L trace proved the intermittent Step11C identity failure was a
normal FanDuel line move between sequential event-page GETs: the market id,
runner count and runner selection ids stayed identical while only the runner
line shape changed. Frozen Step11C already documents that the same market may
legitimately reprice between those GETs and keeps the newest copy, but its
``_market_identity_surface`` accidentally includes runner line/handicap and
line-bearing runner text, causing that legitimate update to be rejected as an
identity mutation.

This compatibility layer narrows the immutable duplicate-market fingerprint to
actual identity: market id/name/type/player fields plus each runner's selection
id, player fields and Over/Under side. The threshold line remains mutable quote
state and is read only from the newest complete market copy selected by frozen
Step11C. Any change to selection ids, side identity, market/player identity, or
other official reconciliation still fails closed exactly as before.

No line blending, fake identity, projection change, readiness relaxation,
controller change, persistence change, or wagering capability is introduced.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import json
import threading
from typing import Any

from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step19l_fanduel_identity_trace as step19l

SOURCE = "Kyre Sports API WNBA Step19M FanDuel immutable-market identity repair"
MODEL_VERSION = "wnba_step19m_fanduel_line_move_identity_v1"

_UPSTREAM_IDENTITY_SURFACE = step19l.market_identity_surface_step19l
_INSTALLED = False
_LOCK = threading.RLock()
_CALL_COUNT = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    return fanduel._clean(value)


def _runner_side(runner: Mapping[str, Any]) -> str:
    """Resolve only the stable side label; never retain the mutable threshold."""
    parsed = fanduel._runner_side_line(runner)
    if parsed is not None:
        return str(parsed[0]).casefold()
    direct = _clean(runner.get("side") or runner.get("resultType")).casefold()
    if direct in {"over", "under"}:
        return direct
    nested = runner.get("result")
    if isinstance(nested, Mapping):
        side = _clean(nested.get("type")).casefold()
        if side in {"over", "under"}:
            return side
    return direct


def _stable_runner_identity(runner: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "selection_id": _clean(
            runner.get("selectionId")
            or runner.get("runnerId")
            or runner.get("id")
            or runner.get("_attachment_key")
        ),
        "side": _runner_side(runner),
        "player_name": _clean(runner.get("playerName")),
        "participant_name": _clean(runner.get("participantName")),
        "player": _clean(runner.get("player")),
    }


def market_identity_surface_step19m(market: Mapping[str, Any]) -> dict[str, Any]:
    """Return immutable identity while leaving line/price/status to the newest snapshot."""
    # Preserve Step19L's field-level flight recorder. It returns the original
    # frozen surface unchanged; we intentionally do not consume its volatile
    # runner line fields in the immutable fingerprint below.
    _UPSTREAM_IDENTITY_SURFACE(market)

    runners = [
        _stable_runner_identity(runner)
        for runner in fanduel._iter_mapping_or_list(market.get("runners"))
    ]
    runners.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":"), default=str))
    surface = {
        "market_id": _clean(market.get("marketId") or market.get("id") or market.get("_attachment_key")),
        "market_name": _clean(market.get("marketName") or market.get("name")),
        "market_type": _clean(market.get("marketType") or market.get("type")),
        "player_name": _clean(market.get("playerName")),
        "participant_name": _clean(market.get("participantName")),
        "player": _clean(market.get("player")),
        "runners": runners,
    }
    with _LOCK:
        global _CALL_COUNT
        _CALL_COUNT += 1
    return surface


def install_step19m_fanduel_line_move() -> dict[str, Any]:
    """Install only over the certified Step19L trace surface."""
    global _INSTALLED
    current = fanduel._market_identity_surface
    if current is market_identity_surface_step19m:
        _INSTALLED = True
        return installation_status()
    if current is not _UPSTREAM_IDENTITY_SURFACE:
        raise RuntimeError("Step19M refuses to replace an unknown FanDuel market identity override.")
    fanduel._market_identity_surface = market_identity_surface_step19m
    _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    with _LOCK:
        calls = int(_CALL_COUNT)
    return {
        "data_type": "wnba_step19m_fanduel_line_move_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now(),
        "installed": _INSTALLED,
        "market_identity_repair_active": (
            fanduel._market_identity_surface is market_identity_surface_step19m
        ),
        "identity_surface_call_count": calls,
        "guardrails": {
            "same_market_line_move_allowed": True,
            "newest_complete_market_copy_selected_by_frozen_step11c": True,
            "same_selection_ids_required": True,
            "same_runner_side_identity_required": True,
            "same_market_name_and_type_required": True,
            "same_player_identity_required": True,
            "selection_id_change_allowed": False,
            "runner_side_change_allowed": False,
            "market_type_change_allowed": False,
            "player_identity_change_allowed": False,
            "different_lines_blended": False,
            "exact_line_matching_modified": False,
            "official_game_reconciliation_modified": False,
            "official_roster_reconciliation_modified": False,
            "projection_logic_modified": False,
            "monte_carlo_simulation_count_modified": False,
            "readiness_relaxed": False,
            "provider_retry_policy_modified": False,
            "controller_state_modified": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


def _reset_for_test() -> None:
    global _CALL_COUNT
    with _LOCK:
        _CALL_COUNT = 0


__all__ = [
    "MODEL_VERSION",
    "SOURCE",
    "install_step19m_fanduel_line_move",
    "installation_status",
    "market_identity_surface_step19m",
]
