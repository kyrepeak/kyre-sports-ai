"""WNBA Step20B FanDuel full-game market scope compatibility.

FanDuel can expose quarter/half player markets on the same event pages used by
our full-game player-prop collector. The certified Step19F stat recognizer
already protects the P/R/A/PRA contract by excluding two-stat combos. A title
such as ``Napheesa Collier - 1st Qtr`` can still carry a generic ``Player
Points`` market type, however, and is therefore visible to that full-game stat
recognizer.

Such a market is outside the certified full-game model contract and must be
ignored, not reconciled by weakening player identity or by stripping the period
suffix.

This compatibility layer composes *outside* the certified Step19F market-stat
wrapper: explicit quarter/half markets return ``None`` (unsupported), while all
other markets delegate unchanged to Step19F. Identity, price, line, provider
transport, exact-line matching, projection math, and wagering behavior remain
untouched.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Mapping

from sports_api import wnba_step11_fanduel_provider as fanduel
from sports_api import wnba_step19f_draftkings_identity as step19f

SOURCE = "Kyre Sports API WNBA Step20B FanDuel full-game period filter"
MODEL_VERSION = "wnba_step20b_fanduel_full_game_period_filter_v2"

_CERTIFIED_UPSTREAM_MARKET_STAT = step19f.fanduel_market_stat_step19f
_FROZEN_BASE_MARKET_STAT = step19f._ORIGINAL_FD_MARKET_STAT
_INSTALLED = False

_PERIOD_RE = re.compile(
    r"(?:"
    r"\b(?:1st|first|2nd|second|3rd|third|4th|fourth)\s*(?:qtr|quarter)\b"
    r"|\b(?:qtr|quarter)\s*(?:1|2|3|4)\b"
    r"|\bq[1-4]\b"
    r"|\b(?:1st|first|2nd|second)\s*half\b"
    r"|\bhalf\s*(?:1|2)\b"
    r"|\bh[12]\b"
    r")",
    flags=re.I,
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def is_explicit_period_market(market: Mapping[str, Any]) -> bool:
    text = " ".join(
        _clean(market.get(key))
        for key in ("marketName", "marketType", "name", "type", "period", "periodName")
    )
    return bool(_PERIOD_RE.search(text))


def market_stat_full_game_only_step20b(market: Mapping[str, Any]) -> str | None:
    """Reject explicit period markets, otherwise preserve Step19F exactly."""
    if is_explicit_period_market(market):
        return None
    return _CERTIFIED_UPSTREAM_MARKET_STAT(market)


def install_step20b_fanduel_period_filter() -> dict[str, Any]:
    """Install only on top of the certified Step19F market-stat wrapper."""
    global _INSTALLED
    current = fanduel._market_stat
    if current is market_stat_full_game_only_step20b:
        _INSTALLED = True
        return installation_status()
    if current is not _CERTIFIED_UPSTREAM_MARKET_STAT:
        raise RuntimeError(
            "Step20B requires the certified Step19F FanDuel market-stat wrapper "
            "and refuses to replace an unknown override."
        )
    fanduel._market_stat = market_stat_full_game_only_step20b
    _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    return {
        "data_type": "wnba_step20b_fanduel_period_filter_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "installed": _INSTALLED,
        "market_stat_filter_active": fanduel._market_stat is market_stat_full_game_only_step20b,
        "certified_step19f_upstream_preserved": (
            _CERTIFIED_UPSTREAM_MARKET_STAT is step19f.fanduel_market_stat_step19f
        ),
        "guardrails": {
            "scope": "explicit_quarter_and_half_markets_only",
            "full_game_market_stat_delegated_to_step19f": True,
            "step19f_two_stat_combo_filter_preserved": True,
            "player_identity_modified": False,
            "roster_identity_relaxed": False,
            "sportsbook_transport_modified": False,
            "price_logic_modified": False,
            "exact_line_matching_modified": False,
            "different_lines_blended": False,
            "projection_math_modified": False,
            "monte_carlo_simulation_count_modified": False,
            "monte_carlo_batch_size_modified": False,
            "readiness_relaxed": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


__all__ = [
    "MODEL_VERSION",
    "SOURCE",
    "install_step20b_fanduel_period_filter",
    "installation_status",
    "is_explicit_period_market",
    "market_stat_full_game_only_step20b",
]
