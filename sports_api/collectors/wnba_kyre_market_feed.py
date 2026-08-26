"""Kyre-owned durable WNBA player-prop market feed.

Step 6C removes SportsGameOdds from the active production dependency graph.
The source of truth is a small JSON envelope on the service's persistent disk.
The collector is intentionally network-free and returns the same collection
shape consumed by the frozen Step 5O -> Step 5M market pipeline.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any

from sports_api.collectors.wnba_prop_feed_collector import (
    WNBAPropFeedCollectorModelInputError,
    WNBAPropFeedCollectorNotReadyError,
    WNBAPropFeedCollectorUpstreamError,
)
from sports_api.wnba_prop_line_feed_adapter import CANONICAL_FEED_FORMAT

MODEL_SOURCE = "Kyre Sports API WNBA Step 6C owned market feed"
MODEL_VERSION = "wnba_step_6c_owned_market_feed_v1"
SCHEMA_VERSION = "wnba_step_6c_owned_market_feed_v1"

KYRE_MARKET_PROVIDER_ID = "kyre"
MARKET_PROVIDER_MODE_ENV = "WNBA_MARKET_PROVIDER_MODE"
KYRE_MARKET_FEED_PATH_ENV = "WNBA_KYRE_MARKET_FEED_PATH"
DEFAULT_KYRE_MARKET_FEED_PATH = "/var/lib/kyre-sports-api/wnba_market_feed.json"
DEFAULT_ODDS_FORMAT = "american"
MAX_FEED_BYTES = 5_000_000
MAX_OFFERS = 10_000
_ALLOWED_MODES = {"kyre", "auto", "legacy_sportsgameodds"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class WNBAKyreMarketFeedModelInputError(WNBAPropFeedCollectorModelInputError):
    pass


class WNBAKyreMarketFeedNotReadyError(WNBAPropFeedCollectorNotReadyError):
    pass


class WNBAKyreMarketFeedUpstreamError(WNBAPropFeedCollectorUpstreamError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def market_provider_mode(env: Mapping[str, str] | None = None) -> str | None:
    """Return explicit Step 6C mode, or None for frozen legacy compatibility."""
    environment = _environment(env)
    raw = _clean(environment.get(MARKET_PROVIDER_MODE_ENV))
    if raw is None:
        return None
    mode = raw.casefold()
    if mode not in _ALLOWED_MODES:
        raise WNBAKyreMarketFeedModelInputError(
            f"{MARKET_PROVIDER_MODE_ENV} must be one of: {', '.join(sorted(_ALLOWED_MODES))}."
        )
    return mode


def resolve_kyre_market_feed_path(
    path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    environment = _environment(env)
    raw = path if path is not None else environment.get(KYRE_MARKET_FEED_PATH_ENV, DEFAULT_KYRE_MARKET_FEED_PATH)
    resolved = Path(str(raw)).expanduser()
    if not resolved.is_absolute():
        raise WNBAKyreMarketFeedModelInputError(
            f"{KYRE_MARKET_FEED_PATH_ENV} must be an absolute path."
        )
    return resolved


def _aware_iso(value: Any, field: str) -> str:
    text = _clean(value)
    if not text:
        raise WNBAKyreMarketFeedModelInputError(f"Kyre market feed {field} is required.")
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WNBAKyreMarketFeedModelInputError(f"Kyre market feed {field} must be ISO-8601.") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise WNBAKyreMarketFeedModelInputError(f"Kyre market feed {field} must include a timezone.")
    return _iso(dt)


def validate_kyre_market_feed(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise WNBAKyreMarketFeedModelInputError("Kyre market feed must be a JSON object.")
    schema = _clean(document.get("schema_version"))
    if schema not in {SCHEMA_VERSION, "wnba_kyre_market_feed_v1"}:
        raise WNBAKyreMarketFeedModelInputError(
            f"Kyre market feed schema_version must be {SCHEMA_VERSION!r}."
        )
    date = _clean(document.get("date"))
    if not date or not _DATE_RE.fullmatch(date):
        raise WNBAKyreMarketFeedModelInputError("Kyre market feed date must use YYYY-MM-DD.")
    try:
        season = int(document.get("season"))
    except (TypeError, ValueError) as exc:
        raise WNBAKyreMarketFeedModelInputError("Kyre market feed season must be an integer.") from exc
    if season < 1997 or season > 2200:
        raise WNBAKyreMarketFeedModelInputError("Kyre market feed season is outside the supported range.")
    captured = _aware_iso(document.get("captured_at_utc"), "captured_at_utc")
    feed_source = _clean(document.get("feed_source")) or "Kyre-owned market ingestion"
    if len(feed_source) > 160:
        raise WNBAKyreMarketFeedModelInputError("Kyre market feed feed_source is too long.")
    feed_format = (_clean(document.get("feed_format")) or CANONICAL_FEED_FORMAT).casefold()
    if feed_format != CANONICAL_FEED_FORMAT:
        raise WNBAKyreMarketFeedModelInputError(
            f"Kyre market feed currently requires {CANONICAL_FEED_FORMAT}."
        )
    odds_format = (_clean(document.get("odds_format")) or DEFAULT_ODDS_FORMAT).casefold()
    if odds_format not in {"american", "decimal"}:
        raise WNBAKyreMarketFeedModelInputError("Kyre market feed odds_format must be american or decimal.")
    offers = document.get("offers")
    if not isinstance(offers, list):
        raise WNBAKyreMarketFeedModelInputError("Kyre market feed offers must be a list.")
    if len(offers) > MAX_OFFERS:
        raise WNBAKyreMarketFeedModelInputError(f"Kyre market feed cannot exceed {MAX_OFFERS} offers.")
    if any(not isinstance(row, dict) for row in offers):
        raise WNBAKyreMarketFeedModelInputError("Every Kyre market offer must be a JSON object.")
    return {
        "schema_version": SCHEMA_VERSION,
        "date": date,
        "season": season,
        "captured_at_utc": captured,
        "feed_source": feed_source,
        "feed_format": feed_format,
        "odds_format": odds_format,
        "offers": [dict(row) for row in offers],
    }


def _load(path: Path) -> dict[str, Any]:
    try:
        stat = path.stat()
    except FileNotFoundError as exc:
        raise WNBAKyreMarketFeedNotReadyError(
            f"Kyre market feed is not present yet at {path}. Import the current board before activation."
        ) from exc
    except OSError as exc:
        raise WNBAKyreMarketFeedUpstreamError(f"Kyre market feed cannot be inspected: {exc}") from exc
    if stat.st_size <= 0:
        raise WNBAKyreMarketFeedNotReadyError("Kyre market feed file is empty.")
    if stat.st_size > MAX_FEED_BYTES:
        raise WNBAKyreMarketFeedModelInputError(f"Kyre market feed exceeds {MAX_FEED_BYTES} bytes.")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WNBAKyreMarketFeedModelInputError("Kyre market feed contains invalid JSON.") from exc
    except OSError as exc:
        raise WNBAKyreMarketFeedUpstreamError(f"Kyre market feed cannot be read: {exc}") from exc
    return validate_kyre_market_feed(document)


def describe_kyre_market_onboarding(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = _environment(env)
    try:
        mode = market_provider_mode(environment)
        path = resolve_kyre_market_feed_path(env=environment)
        absolute = True
        mode_error = None
    except WNBAKyreMarketFeedModelInputError as exc:
        return {
            "provider_id": KYRE_MARKET_PROVIDER_ID,
            "ready": False,
            "mode": _clean(environment.get(MARKET_PROVIDER_MODE_ENV)),
            "feed_path": _clean(environment.get(KYRE_MARKET_FEED_PATH_ENV)),
            "feed_exists": False,
            "feed_valid": False,
            "offer_count": 0,
            "configuration_error": str(exc),
            "secret_required": False,
            "network_required": False,
        }
    exists = path.is_file()
    valid = False
    error = None
    offer_count = 0
    date = None
    season = None
    captured_at_utc = None
    if exists:
        try:
            feed = _load(path)
            valid = True
            offer_count = len(feed["offers"])
            date = feed["date"]
            season = feed["season"]
            captured_at_utc = feed["captured_at_utc"]
        except (WNBAKyreMarketFeedModelInputError, WNBAKyreMarketFeedNotReadyError, WNBAKyreMarketFeedUpstreamError) as exc:
            error = str(exc)
    return {
        "provider_id": KYRE_MARKET_PROVIDER_ID,
        "ready": bool(valid),
        "mode": mode,
        "feed_path": str(path),
        "feed_path_absolute": absolute,
        "feed_exists": exists,
        "feed_valid": valid,
        "offer_count": offer_count,
        "date": date,
        "season": season,
        "captured_at_utc": captured_at_utc,
        "configuration_error": mode_error or error,
        "secret_required": False,
        "network_required": False,
        "semantics": {
            "kyre_owned": True,
            "persistent_disk_source_of_truth": True,
            "sportsbook_network_collection": False,
            "frozen_step_5m_remains_market_integrity_authority": True,
        },
    }


def kyre_market_ready(env: Mapping[str, str] | None = None) -> bool:
    return bool(describe_kyre_market_onboarding(env).get("ready"))


def collect_kyre_market_feed(
    *,
    date: str | None = None,
    season: int,
    env: Mapping[str, str] | None = None,
    requester: Any = None,
    path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    del requester  # network-free by design; accepted for Step 5O collector compatibility.
    resolved = resolve_kyre_market_feed_path(path, env)
    feed = _load(resolved)
    if date is not None and feed["date"] != str(date):
        raise WNBAKyreMarketFeedNotReadyError(
            f"Kyre market feed date {feed['date']} does not match requested date {date}."
        )
    if int(feed["season"]) != int(season):
        raise WNBAKyreMarketFeedNotReadyError(
            f"Kyre market feed season {feed['season']} does not match requested season {season}."
        )
    raw_feed = {"offers": feed["offers"]}
    raw_sha = _hash(raw_feed)
    collected_at = _iso(_now())
    identity = {
        "provider_id": KYRE_MARKET_PROVIDER_ID,
        "date": feed["date"],
        "season": feed["season"],
        "captured_at_utc": feed["captured_at_utc"],
        "raw_feed_sha256": raw_sha,
        "path": str(resolved),
    }
    fingerprint = _hash(identity)
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_prop_feed_provider_collection",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "model_family": "kyre_owned_durable_market_collection",
        "generated_at_utc": collected_at,
        "collection_id": f"wnba-6c-kyre-{fingerprint[:20]}",
        "collection_fingerprint_sha256": fingerprint,
        "provider_id": KYRE_MARKET_PROVIDER_ID,
        "feed_source": feed["feed_source"],
        "feed_format": feed["feed_format"],
        "odds_format": feed["odds_format"],
        "date": feed["date"],
        "season": feed["season"],
        "collected_at_utc": feed["captured_at_utc"],
        "transport": {
            "method": "LOCAL_FILE",
            "path": str(resolved),
            "network_used": False,
            "status_code": None,
        },
        "provider_configuration": {
            "provider_id": KYRE_MARKET_PROVIDER_ID,
            "kyre_owned": True,
            "secret_required": False,
            "feed_path": str(resolved),
        },
        "raw_feed_sha256": raw_sha,
        "raw_feed": raw_feed,
        "collector_semantics": {
            "network_free": True,
            "sportsbook_vendor_key_required": False,
            "persistent_disk_source_of_truth": True,
            "market_data_cannot_modify_model_probability": True,
        },
    }


def write_kyre_market_feed(
    document: Any,
    *,
    path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    validated = validate_kyre_market_feed(document)
    target = resolve_kyre_market_feed_path(path, env)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(validated, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if len(payload.encode("utf-8")) > MAX_FEED_BYTES:
        raise WNBAKyreMarketFeedModelInputError(f"Kyre market feed exceeds {MAX_FEED_BYTES} bytes.")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temporary_name, 0o600)
        except OSError:
            pass
        os.replace(temporary_name, target)
    finally:
        try:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        except OSError:
            pass
    return {
        "provider_id": KYRE_MARKET_PROVIDER_ID,
        "stored": True,
        "path": str(target),
        "date": validated["date"],
        "season": validated["season"],
        "captured_at_utc": validated["captured_at_utc"],
        "offer_count": len(validated["offers"]),
        "content_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        "secret_values_returned": False,
        "network_used": False,
    }
