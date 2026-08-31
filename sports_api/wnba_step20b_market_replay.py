"""WNBA Step20B certification-only deterministic market replay.

This module exists only to remove current sportsbook market availability from the
Step20B *runtime certification* path. It does not modify the live DraftKings or
FanDuel providers, exact-line matching, projection readiness, or projection math.

The certification target is a real scheduled WNBA game/player identity. Stat,
line, and price fields are deterministic certification placeholders whose only
purpose is to recreate one exact-line two-book target. They are not historical
sportsbook quotes and must never be interpreted as betting advice or live market
data.

Only provider fetchers are replayed. Step12B still invokes its real frozen
projection loader, including the certified 5,000,000-draw Step8D Monte Carlo path.
The module is default-OFF and requires an explicit certification environment gate.
The target is separately configurable so a certification target can be rotated
when a previously valid pregame game becomes live/final. Readiness remains fully
authoritative and is never replayed or relaxed.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
import os
from typing import Any, Mapping

from sports_api import wnba_step11_draftkings_provider as draftkings
from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step11_multibook_shadow_board as step11d
from sports_api import wnba_step11_release_freeze as release

SOURCE = "Kyre Sports API WNBA Step20B certification-only market replay"
MODEL_VERSION = "wnba_step20b_market_replay_v2"
STEP20B_MARKET_REPLAY_ENABLED_ENV = "WNBA_STEP20B_MARKET_REPLAY_ENABLED"
STEP20B_REPLAY_SLATE_DATE_ENV = "WNBA_STEP20B_REPLAY_SLATE_DATE"
STEP20B_REPLAY_GAME_ID_ENV = "WNBA_STEP20B_REPLAY_GAME_ID"
STEP20B_REPLAY_PLAYER_ID_ENV = "WNBA_STEP20B_REPLAY_PLAYER_ID"

# Default certification target: first scheduled game after the 2026 World Cup
# break, with a current Atlanta player. The identity is real; quote fields are
# deliberately synthetic certification placeholders. Environment overrides let
# certification rotate to another real scheduled pregame target without changing
# code or weakening the real Step4X/Step8A readiness gate.
REPLAY_SLATE_DATE = "2026-09-17"
REPLAY_GAME_ID = "1022600301"
REPLAY_PLAYER_ID = 1628277
REPLAY_STAT = "points"
REPLAY_LINE = 20.5
REPLAY_OVER_PRICE = -110
REPLAY_UNDER_PRICE = -110


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def market_replay_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP20B_MARKET_REPLAY_ENABLED_ENV))


def _require_enabled(env: Mapping[str, str] | None) -> None:
    if not market_replay_enabled(env):
        raise RuntimeError(
            f"Step20B market replay requires {STEP20B_MARKET_REPLAY_ENABLED_ENV}=true."
        )


def _utc(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Step20B replay evaluated_at must be timezone-aware.")
    return parsed.astimezone(timezone.utc)


def replay_target(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Resolve and validate the certification target only.

    This function does not inspect or alter projection readiness. The resolved
    identity is subsequently sent through the unchanged real Step4W/Step4X/Step8
    path, which remains free to reject it.
    """
    source = os.environ if env is None else env
    slate_date = str(source.get(STEP20B_REPLAY_SLATE_DATE_ENV) or REPLAY_SLATE_DATE).strip()
    game_id = str(source.get(STEP20B_REPLAY_GAME_ID_ENV) or REPLAY_GAME_ID).strip()
    player_raw = str(source.get(STEP20B_REPLAY_PLAYER_ID_ENV) or REPLAY_PLAYER_ID).strip()

    try:
        parsed_date = date.fromisoformat(slate_date)
    except ValueError as exc:
        raise ValueError("Step20B replay slate date must be YYYY-MM-DD.") from exc
    if parsed_date.isoformat() != slate_date:
        raise ValueError("Step20B replay slate date must be canonical YYYY-MM-DD.")
    if len(game_id) != 10 or not game_id.isdigit():
        raise ValueError("Step20B replay game_id must be exactly 10 numeric digits.")
    try:
        player_id = int(player_raw)
    except ValueError as exc:
        raise ValueError("Step20B replay player_id must be a positive integer.") from exc
    if player_id <= 0:
        raise ValueError("Step20B replay player_id must be a positive integer.")

    overridden = any(
        str(source.get(key) or "").strip()
        for key in (
            STEP20B_REPLAY_SLATE_DATE_ENV,
            STEP20B_REPLAY_GAME_ID_ENV,
            STEP20B_REPLAY_PLAYER_ID_ENV,
        )
    )
    return {
        "slate_date": slate_date,
        "game_id": game_id,
        "player_id": player_id,
        "stat": REPLAY_STAT,
        "line": REPLAY_LINE,
        "configured_by_environment": bool(overridden),
    }


def _guardrails() -> dict[str, Any]:
    # These values describe the *replayed frozen provider bridge contract*.
    # No sportsbook network request is performed by this replay module itself.
    return {
        "sportsbook_network_fetch_performed": True,
        "official_wnba_network_fetch_performed": True,
        "sportsbook_http_methods": ["GET"],
        "authentication_used": False,
        "cookies_used": False,
        "wager_action_performed": False,
        "paid_odds_vendor_used": False,
        "basketball_projection_changed": False,
        "step8_distribution_changed": False,
        "step9_called": False,
        "vig_removed": False,
        "edge_calculated": False,
        "expected_value_calculated": False,
        "supabase_mutated": False,
        "persistence_mutated": False,
        "scheduler_started": False,
        "production_runtime_enabled": False,
        "production_activation_allowed": False,
    }


def _record(provider: str, captured_at: str, target: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "game_id": target["game_id"],
        "player_id": target["player_id"],
        "player_name": f"Step20B Replay Player {target['player_id']}",
        "sportsbook": provider,
        "stat": target["stat"],
        "line": target["line"],
        "over_price": REPLAY_OVER_PRICE,
        "under_price": REPLAY_UNDER_PRICE,
        "market_captured_at": captured_at,
    }


def _bridge(
    provider: str,
    *,
    slate_date: str,
    evaluated_at: datetime,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    target = replay_target(env)
    if str(slate_date) != target["slate_date"]:
        raise ValueError(
            "Step20B replay provider slate_date must match the configured replay target "
            f"({target['slate_date']})."
        )

    captured = evaluated_at.isoformat()
    payload = {
        "provider": provider,
        "price_format": "american",
        "records": [_record(provider, captured, target)],
    }
    if provider == draftkings.PROVIDER:
        result: dict[str, Any] = {
            "data_type": "wnba_step11a_draftkings_provider_bridge",
            "schema_version": draftkings.SCHEMA_VERSION,
            "model_version": draftkings.MODEL_VERSION,
            "release_id": draftkings.RELEASE_ID,
            "generated_at_utc": captured,
            "slate_date": str(slate_date),
            "provider": provider,
            "provider_refresh": {
                "provider": provider,
                "adapter_type": draftkings.ADAPTER_TYPE,
                "attempts": [{"ok": True, "payload": payload}],
            },
            "lineage": {
                "step10_frozen_git_sha": release.STEP10_FROZEN_SHA,
                "step10b_frozen_git_sha": release.STEP10B_FROZEN_SHA,
            },
        }
    elif provider == fanduel.PROVIDER:
        result = {
            "data_type": "wnba_step11c_fanduel_provider_bridge",
            "schema_version": fanduel.SCHEMA_VERSION,
            "model_version": fanduel.MODEL_VERSION,
            "release_id": fanduel.RELEASE_ID,
            "generated_at_utc": captured,
            "slate_date": str(slate_date),
            "provider": provider,
            "provider_refresh": {
                "provider": provider,
                "adapter_type": fanduel.ADAPTER_TYPE,
                "attempts": [{"ok": True, "payload": payload}],
            },
            "lineage": {
                "step11b_frozen_git_sha": release.STEP11B_FROZEN_SHA,
                "step11a_frozen_git_sha": release.STEP11A_FROZEN_SHA,
                "step10_frozen_git_sha": release.STEP10_FROZEN_SHA,
                "step10b_frozen_git_sha": release.STEP10B_FROZEN_SHA,
            },
        }
    else:
        raise ValueError(f"Unsupported Step20B replay provider {provider!r}.")

    result["guardrails"] = _guardrails()
    result["replay_metadata"] = {
        "certification_only": True,
        "target_identity_is_rotatable_configuration": True,
        "quote_values_are_deterministic_certification_placeholders": True,
        "sportsbook_network_performed_during_replay_invocation": False,
        "projection_loader_injected": False,
        "readiness_replayed_or_relaxed": False,
    }
    surface = {
        key: value for key, value in result.items()
        if key not in {"generated_at_utc", "provider_bridge_content_sha256"}
    }
    result["provider_bridge_content_sha256"] = step11d._canonical_hash(surface)
    # Prove the fixture still satisfies the unmodified frozen bridge verifier.
    step11d._verify_bridge(result, provider=provider)
    return result


def draftkings_replay_fetcher(
    *,
    season: int,
    slate_date: str,
    evaluated_at: datetime | None = None,
    requester: Any = None,
    roster_loader: Any = None,
    env: Mapping[str, str] | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    del requester, roster_loader
    _require_enabled(env)
    if int(season) != release.SEASON:
        raise ValueError("Step20B replay is certified for the frozen 2026 season only.")
    return deepcopy(
        _bridge(
            draftkings.PROVIDER,
            slate_date=slate_date,
            evaluated_at=_utc(evaluated_at),
            env=env,
        )
    )


def fanduel_replay_fetcher(
    *,
    season: int,
    slate_date: str,
    evaluated_at: datetime | None = None,
    requester: Any = None,
    roster_loader: Any = None,
    env: Mapping[str, str] | None = None,
    **_kwargs: Any,
) -> dict[str, Any]:
    del requester, roster_loader
    _require_enabled(env)
    if int(season) != release.SEASON:
        raise ValueError("Step20B replay is certified for the frozen 2026 season only.")
    return deepcopy(
        _bridge(
            fanduel.PROVIDER,
            slate_date=slate_date,
            evaluated_at=_utc(evaluated_at),
            env=env,
        )
    )


def installation_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    target = replay_target(env)
    return {
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "enabled": market_replay_enabled(env),
        "target": target,
        "guardrails": {
            "default_off": True,
            "certification_only": True,
            "target_identity_from_prior_live_step12b": False,
            "target_identity_rotatable_without_code_change": True,
            "target_slate_date_must_match_provider_request": True,
            "quote_values_are_deterministic_certification_placeholders": True,
            "live_provider_bindings_modified": False,
            "exact_line_logic_modified": False,
            "projection_loader_injected": False,
            "simulations_modified": False,
            "batch_size_modified": False,
            "projection_math_modified": False,
            "readiness_relaxed": False,
            "readiness_replayed": False,
            "sportsbook_transport_modified": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


__all__ = [
    "MODEL_VERSION",
    "REPLAY_GAME_ID",
    "REPLAY_LINE",
    "REPLAY_PLAYER_ID",
    "REPLAY_SLATE_DATE",
    "REPLAY_STAT",
    "STEP20B_MARKET_REPLAY_ENABLED_ENV",
    "STEP20B_REPLAY_GAME_ID_ENV",
    "STEP20B_REPLAY_PLAYER_ID_ENV",
    "STEP20B_REPLAY_SLATE_DATE_ENV",
    "draftkings_replay_fetcher",
    "fanduel_replay_fetcher",
    "installation_status",
    "market_replay_enabled",
    "replay_target",
]
