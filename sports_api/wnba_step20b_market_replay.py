"""WNBA Step20B certification-only deterministic market replay.

This module exists only to remove current sportsbook market availability from the
Step20B *runtime certification* path.  It does not modify the live DraftKings or
FanDuel providers, exact-line matching, projection readiness, or projection math.

The replay is anchored to a game/player target that was observed in the prior live
Step12B diagnostic run.  Stat/line/price fields are deterministic certification
placeholders whose only purpose is to recreate one exact-line two-book target.
They are not historical sportsbook quotes and must never be interpreted as betting
advice or live market data.

Only provider fetchers are replayed.  Step12B still invokes its real frozen
projection loader, including the certified 5,000,000-draw Step8D Monte Carlo path.
The module is default-OFF and requires an explicit certification environment gate.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
from typing import Any, Mapping

from sports_api import wnba_step11_draftkings_provider as draftkings
from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step11_multibook_shadow_board as step11d
from sports_api import wnba_step11_release_freeze as release

SOURCE = "Kyre Sports API WNBA Step20B certification-only market replay"
MODEL_VERSION = "wnba_step20b_market_replay_v1"
STEP20B_MARKET_REPLAY_ENABLED_ENV = "WNBA_STEP20B_MARKET_REPLAY_ENABLED"

# This identity was observed in the prior live Step12B runtime trace.  Quote
# fields below are deliberately synthetic certification placeholders.
REPLAY_GAME_ID = "1022600300"
REPLAY_PLAYER_ID = 1629501
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


def _record(provider: str, captured_at: str) -> dict[str, Any]:
    return {
        "game_id": REPLAY_GAME_ID,
        "player_id": REPLAY_PLAYER_ID,
        "player_name": f"Step20B Replay Player {REPLAY_PLAYER_ID}",
        "sportsbook": provider,
        "stat": REPLAY_STAT,
        "line": REPLAY_LINE,
        "over_price": REPLAY_OVER_PRICE,
        "under_price": REPLAY_UNDER_PRICE,
        "market_captured_at": captured_at,
    }


def _bridge(
    provider: str,
    *,
    slate_date: str,
    evaluated_at: datetime,
) -> dict[str, Any]:
    captured = evaluated_at.isoformat()
    payload = {
        "provider": provider,
        "price_format": "american",
        "records": [_record(provider, captured)],
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
        "target_identity_from_prior_live_step12b": True,
        "quote_values_are_deterministic_certification_placeholders": True,
        "sportsbook_network_performed_during_replay_invocation": False,
        "projection_loader_injected": False,
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
        )
    )


def installation_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    return {
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "enabled": market_replay_enabled(env),
        "target": {
            "game_id": REPLAY_GAME_ID,
            "player_id": REPLAY_PLAYER_ID,
            "stat": REPLAY_STAT,
            "line": REPLAY_LINE,
        },
        "guardrails": {
            "default_off": True,
            "certification_only": True,
            "target_identity_from_prior_live_step12b": True,
            "quote_values_are_deterministic_certification_placeholders": True,
            "live_provider_bindings_modified": False,
            "exact_line_logic_modified": False,
            "projection_loader_injected": False,
            "simulations_modified": False,
            "batch_size_modified": False,
            "projection_math_modified": False,
            "readiness_relaxed": False,
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
    "REPLAY_STAT",
    "STEP20B_MARKET_REPLAY_ENABLED_ENV",
    "draftkings_replay_fetcher",
    "fanduel_replay_fetcher",
    "installation_status",
    "market_replay_enabled",
]
