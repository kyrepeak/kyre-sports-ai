"""WNBA Step 5N: automatic, security-hardened provider collection for real prop feeds.

Step 5N owns transport/configuration only. It never invents sportsbook lines,
never changes Step 5F probabilities, and never changes Step 5K ranking. A
provider must be configured by the API operator through environment variables;
API callers select only a configured provider id and can never supply an
arbitrary URL.

Provider registry environment variable
--------------------------------------
WNBA_PROP_FEED_PROVIDERS_JSON accepts either a JSON list of provider objects or
an object with ``providers`` plus optional ``default_provider_id``.

A provider may define:
- provider_id: stable lowercase id
- enabled: boolean (default true)
- url: HTTPS endpoint; supports {date} and {season} templates outside hostname
- feed_source: human-readable source label passed to Step 5M
- feed_format: canonical_offers_v1 or bookmaker_event_markets_v1
- odds_format: american or decimal
- timeout_seconds: 1..30
- max_response_bytes: 1..10,000,000
- headers: non-secret static headers
- query_params: non-secret static query values
- secret_header_env: {header_name: ENV_VAR_NAME}
- secret_query_env: {query_name: ENV_VAR_NAME}
- response_json_path: list of object keys used to select nested JSON
- list_wrapper_key: optional wrapper for a selected JSON list

Literal authentication material is rejected from URLs/static headers/static
query parameters. Secret values are read only at request time from referenced
environment variables and are never returned in collector output.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
import re
from time import monotonic
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import httpx

from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_prop_line_feed_adapter import (
    BOOKMAKER_EVENT_FEED_FORMAT,
    CANONICAL_FEED_FORMAT,
    SUPPORTED_FEED_FORMATS,
    SUPPORTED_ODDS_FORMATS,
    build_feed_daily_top_five,
    build_prop_line_feed_board,
)
from sports_api.wnba_schedule import ARIZONA_TZ

MODEL_SOURCE = "Kyre Sports API WNBA Step 5N automatic prop-feed collector"
MODEL_VERSION = "wnba_step_5n_automatic_prop_feed_collector_v1"
SCHEMA_VERSION = "wnba_step_5n_automatic_prop_feed_collector_v1"
MODEL_FAMILY = "configured_https_provider_collection_and_step_5m_handoff"

PROVIDERS_ENV = "WNBA_PROP_FEED_PROVIDERS_JSON"
DEFAULT_PROVIDER_ENV = "WNBA_PROP_FEED_DEFAULT_PROVIDER"

DEFAULT_TIMEOUT_SECONDS = 12.0
MIN_TIMEOUT_SECONDS = 1.0
MAX_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RESPONSE_BYTES = 5_000_000
MAX_RESPONSE_BYTES = 10_000_000
MAX_PROVIDER_COUNT = 25
MAX_PROVIDER_ID_LENGTH = 64
MAX_FEED_SOURCE_LENGTH = 160
MAX_STATIC_HEADERS = 32
MAX_STATIC_QUERY_PARAMS = 64
MAX_SECRET_BINDINGS = 32
MAX_RESPONSE_JSON_PATH_DEPTH = 12
USER_AGENT = "KyreSportsAPI-WNBA-Step5N/1.0"

_PROVIDER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_ENV_NAME_RE = re.compile(r"^[A-Z_][A-Z0-9_]{0,127}$")
_HEADER_NAME_RE = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_TEMPLATE_RE = re.compile(r"\{([a-zA-Z0-9_]+)\}")
_ALLOWED_TEMPLATE_FIELDS = frozenset({"date", "season"})

_SENSITIVE_HEADER_NAMES = frozenset(
    {
        "authorization",
        "proxy-authorization",
        "x-api-key",
        "api-key",
        "apikey",
        "x-auth-token",
        "cookie",
        "set-cookie",
    }
)
_SENSITIVE_QUERY_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "api-key",
        "access_token",
        "token",
        "auth",
        "authorization",
        "key",
    }
)
_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
    }
)


class WNBAPropFeedCollectorConfigError(ValueError):
    pass


class WNBAPropFeedCollectorNotReadyError(RuntimeError):
    pass


class WNBAPropFeedCollectorUpstreamError(RuntimeError):
    pass


class WNBAPropFeedCollectorModelInputError(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _target_date(value: str | None) -> str:
    if value is None:
        return datetime.now(ARIZONA_TZ).date().isoformat()
    text = str(value).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("WNBA Step 5N date must use YYYY-MM-DD format.") from exc
    return text


def _positive_season(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA Step 5N season must be a positive integer.")
    return value


def _provider_id(value: Any) -> str:
    text = (_clean(value) or "").casefold()
    if not _PROVIDER_ID_RE.fullmatch(text):
        raise WNBAPropFeedCollectorConfigError(
            "WNBA Step 5N provider_id must match [a-z0-9][a-z0-9_-]{0,63}."
        )
    return text


def _feed_source(value: Any, provider_id: str) -> str:
    text = _clean(value) or provider_id
    if len(text) > MAX_FEED_SOURCE_LENGTH:
        raise WNBAPropFeedCollectorConfigError(
            f"WNBA Step 5N feed_source cannot exceed {MAX_FEED_SOURCE_LENGTH} characters."
        )
    return " ".join(text.split())


def _choice(value: Any, allowed: tuple[str, ...], label: str) -> str:
    text = (_clean(value) or "").casefold()
    lookup = {item.casefold(): item for item in allowed}
    result = lookup.get(text)
    if result is None:
        raise WNBAPropFeedCollectorConfigError(
            f"WNBA Step 5N unsupported {label} {value!r}. Allowed values: "
            + ", ".join(allowed)
            + "."
        )
    return result


def _float_range(value: Any, *, default: float, minimum: float, maximum: float, label: str) -> float:
    if value is None:
        return default
    if isinstance(value, bool):
        raise WNBAPropFeedCollectorConfigError(f"WNBA Step 5N {label} must be numeric.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBAPropFeedCollectorConfigError(f"WNBA Step 5N {label} must be numeric.") from exc
    if not minimum <= number <= maximum:
        raise WNBAPropFeedCollectorConfigError(
            f"WNBA Step 5N {label} must be from {minimum:g} through {maximum:g}."
        )
    return number


def _int_range(value: Any, *, default: int, minimum: int, maximum: int, label: str) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise WNBAPropFeedCollectorConfigError(f"WNBA Step 5N {label} must be an integer.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise WNBAPropFeedCollectorConfigError(f"WNBA Step 5N {label} must be an integer.") from exc
    if number != value and not isinstance(value, str):
        raise WNBAPropFeedCollectorConfigError(f"WNBA Step 5N {label} must be an integer.")
    if not minimum <= number <= maximum:
        raise WNBAPropFeedCollectorConfigError(
            f"WNBA Step 5N {label} must be from {minimum} through {maximum}."
        )
    return number


def _env_name(value: Any) -> str:
    text = _clean(value) or ""
    if not _ENV_NAME_RE.fullmatch(text):
        raise WNBAPropFeedCollectorConfigError(
            "WNBA Step 5N secret environment names must match [A-Z_][A-Z0-9_]{0,127}."
        )
    return text


def _header_name(value: Any) -> str:
    text = _clean(value) or ""
    if not _HEADER_NAME_RE.fullmatch(text):
        raise WNBAPropFeedCollectorConfigError("WNBA Step 5N invalid HTTP header name.")
    return text


def _query_name(value: Any) -> str:
    text = _clean(value) or ""
    if not text or len(text) > 128 or any(ord(ch) < 32 for ch in text):
        raise WNBAPropFeedCollectorConfigError("WNBA Step 5N invalid query parameter name.")
    return text


def _validate_templates(value: str, *, label: str) -> str:
    fields = set(_TEMPLATE_RE.findall(value))
    unsupported = fields - _ALLOWED_TEMPLATE_FIELDS
    if unsupported:
        raise WNBAPropFeedCollectorConfigError(
            f"WNBA Step 5N {label} contains unsupported templates: {', '.join(sorted(unsupported))}."
        )
    return value


def _render(value: str, *, date: str, season: int) -> str:
    _validate_templates(value, label="configured value")
    return value.replace("{date}", date).replace("{season}", str(season))


def _validate_host(hostname: str) -> None:
    host = hostname.casefold().rstrip(".")
    if host in _BLOCKED_HOSTNAMES or host.endswith((".localhost", ".local", ".internal")):
        raise WNBAPropFeedCollectorConfigError("WNBA Step 5N provider host is not allowed.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise WNBAPropFeedCollectorConfigError("WNBA Step 5N private/local provider IPs are not allowed.")


def _validate_url(value: Any) -> str:
    text = _clean(value) or ""
    if len(text) > 2048:
        raise WNBAPropFeedCollectorConfigError("WNBA Step 5N provider URL is too long.")
    parsed = urlsplit(text)
    if parsed.scheme.casefold() != "https":
        raise WNBAPropFeedCollectorConfigError("WNBA Step 5N provider URL must use HTTPS.")
    if not parsed.hostname:
        raise WNBAPropFeedCollectorConfigError("WNBA Step 5N provider URL must include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise WNBAPropFeedCollectorConfigError(
            "WNBA Step 5N provider URL cannot contain embedded credentials."
        )
    if parsed.fragment:
        raise WNBAPropFeedCollectorConfigError("WNBA Step 5N provider URL cannot contain a fragment.")
    if "{" in parsed.hostname or "}" in parsed.hostname:
        raise WNBAPropFeedCollectorConfigError(
            "WNBA Step 5N provider URL templates are not allowed in the hostname."
        )
    _validate_host(parsed.hostname)
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        if key.casefold() in _SENSITIVE_QUERY_NAMES:
            raise WNBAPropFeedCollectorConfigError(
                "WNBA Step 5N authentication values cannot be embedded in the provider URL query."
            )
    _validate_templates(text, label="provider URL")
    return text


def _static_headers(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > MAX_STATIC_HEADERS:
        raise WNBAPropFeedCollectorConfigError(
            f"WNBA Step 5N headers must be an object with at most {MAX_STATIC_HEADERS} entries."
        )
    result: dict[str, str] = {}
    for raw_name, raw_value in value.items():
        name = _header_name(raw_name)
        if name.casefold() in _SENSITIVE_HEADER_NAMES:
            raise WNBAPropFeedCollectorConfigError(
                f"WNBA Step 5N sensitive header {name!r} must use secret_header_env."
            )
        text = _clean(raw_value)
        if text is None or any(ch in text for ch in ("\r", "\n")):
            raise WNBAPropFeedCollectorConfigError("WNBA Step 5N static header values must be non-empty single-line strings.")
        result[name] = _validate_templates(text, label=f"header {name}")
    return result


def _static_query(value: Any) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > MAX_STATIC_QUERY_PARAMS:
        raise WNBAPropFeedCollectorConfigError(
            f"WNBA Step 5N query_params must be an object with at most {MAX_STATIC_QUERY_PARAMS} entries."
        )
    result: dict[str, str] = {}
    for raw_name, raw_value in value.items():
        name = _query_name(raw_name)
        if name.casefold() in _SENSITIVE_QUERY_NAMES:
            raise WNBAPropFeedCollectorConfigError(
                f"WNBA Step 5N sensitive query parameter {name!r} must use secret_query_env."
            )
        text = _clean(raw_value)
        if text is None:
            raise WNBAPropFeedCollectorConfigError("WNBA Step 5N static query values must be non-empty strings.")
        result[name] = _validate_templates(text, label=f"query parameter {name}")
    return result


def _secret_bindings(value: Any, *, binding_label: str, key_parser: Callable[[Any], str]) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > MAX_SECRET_BINDINGS:
        raise WNBAPropFeedCollectorConfigError(
            f"WNBA Step 5N {binding_label} must be an object with at most {MAX_SECRET_BINDINGS} entries."
        )
    result: dict[str, str] = {}
    for raw_key, raw_env_name in value.items():
        key = key_parser(raw_key)
        result[key] = _env_name(raw_env_name)
    return result


def _response_path(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > MAX_RESPONSE_JSON_PATH_DEPTH:
        raise WNBAPropFeedCollectorConfigError(
            f"WNBA Step 5N response_json_path must be a list with at most {MAX_RESPONSE_JSON_PATH_DEPTH} keys."
        )
    result: list[str] = []
    for item in value:
        text = _clean(item)
        if not text or len(text) > 128:
            raise WNBAPropFeedCollectorConfigError(
                "WNBA Step 5N response_json_path keys must be non-empty strings of at most 128 characters."
            )
        result.append(text)
    return result


def _list_wrapper(value: Any, feed_format: str) -> str | None:
    if value is None:
        return None
    text = _clean(value)
    if not text or len(text) > 128:
        raise WNBAPropFeedCollectorConfigError("WNBA Step 5N list_wrapper_key is invalid.")
    expected = "offers" if feed_format == CANONICAL_FEED_FORMAT else "events"
    if text != expected:
        raise WNBAPropFeedCollectorConfigError(
            f"WNBA Step 5N list_wrapper_key must be {expected!r} for feed_format {feed_format!r}."
        )
    return text


def _normalize_provider(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise WNBAPropFeedCollectorConfigError("WNBA Step 5N each provider must be a JSON object.")
    provider_id = _provider_id(row.get("provider_id") or row.get("id"))
    enabled = row.get("enabled", True)
    if not isinstance(enabled, bool):
        raise WNBAPropFeedCollectorConfigError("WNBA Step 5N provider enabled must be boolean.")
    feed_format = _choice(row.get("feed_format", CANONICAL_FEED_FORMAT), SUPPORTED_FEED_FORMATS, "feed_format")
    odds_format = _choice(row.get("odds_format", "american"), SUPPORTED_ODDS_FORMATS, "odds_format")
    secret_header_env = _secret_bindings(
        row.get("secret_header_env"),
        binding_label="secret_header_env",
        key_parser=_header_name,
    )
    secret_query_env = _secret_bindings(
        row.get("secret_query_env"),
        binding_label="secret_query_env",
        key_parser=_query_name,
    )
    static_headers = _static_headers(row.get("headers"))
    static_query = _static_query(row.get("query_params"))
    if set(name.casefold() for name in static_headers) & set(name.casefold() for name in secret_header_env):
        raise WNBAPropFeedCollectorConfigError(
            "WNBA Step 5N static and secret headers cannot define the same header."
        )
    if set(static_query) & set(secret_query_env):
        raise WNBAPropFeedCollectorConfigError(
            "WNBA Step 5N static and secret query parameters cannot define the same key."
        )
    return {
        "provider_id": provider_id,
        "enabled": enabled,
        "url": _validate_url(row.get("url")),
        "feed_source": _feed_source(row.get("feed_source"), provider_id),
        "feed_format": feed_format,
        "odds_format": odds_format,
        "timeout_seconds": _float_range(
            row.get("timeout_seconds"),
            default=DEFAULT_TIMEOUT_SECONDS,
            minimum=MIN_TIMEOUT_SECONDS,
            maximum=MAX_TIMEOUT_SECONDS,
            label="timeout_seconds",
        ),
        "max_response_bytes": _int_range(
            row.get("max_response_bytes"),
            default=DEFAULT_MAX_RESPONSE_BYTES,
            minimum=1,
            maximum=MAX_RESPONSE_BYTES,
            label="max_response_bytes",
        ),
        "headers": static_headers,
        "query_params": static_query,
        "secret_header_env": secret_header_env,
        "secret_query_env": secret_query_env,
        "response_json_path": _response_path(row.get("response_json_path")),
        "list_wrapper_key": _list_wrapper(row.get("list_wrapper_key"), feed_format),
    }


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def load_provider_registry(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = _environment(env)
    raw = _clean(environment.get(PROVIDERS_ENV))
    if not raw:
        providers_raw: list[Any] = []
        document_default = None
    else:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WNBAPropFeedCollectorConfigError(
                f"WNBA Step 5N {PROVIDERS_ENV} must contain valid JSON."
            ) from exc
        if isinstance(parsed, list):
            providers_raw = parsed
            document_default = None
        elif isinstance(parsed, dict):
            providers_raw = parsed.get("providers")
            document_default = parsed.get("default_provider_id")
            if not isinstance(providers_raw, list):
                raise WNBAPropFeedCollectorConfigError(
                    f"WNBA Step 5N {PROVIDERS_ENV}.providers must be a list."
                )
        else:
            raise WNBAPropFeedCollectorConfigError(
                f"WNBA Step 5N {PROVIDERS_ENV} must be a JSON list or object."
            )
    if len(providers_raw) > MAX_PROVIDER_COUNT:
        raise WNBAPropFeedCollectorConfigError(
            f"WNBA Step 5N cannot configure more than {MAX_PROVIDER_COUNT} providers."
        )
    providers = [_normalize_provider(row) for row in providers_raw]
    ids = [row["provider_id"] for row in providers]
    if len(ids) != len(set(ids)):
        raise WNBAPropFeedCollectorConfigError("WNBA Step 5N provider_id values must be unique.")

    raw_default = _clean(environment.get(DEFAULT_PROVIDER_ENV)) or _clean(document_default)
    default_provider_id = _provider_id(raw_default) if raw_default else None
    by_id = {row["provider_id"]: row for row in providers}
    if default_provider_id and default_provider_id not in by_id:
        raise WNBAPropFeedCollectorConfigError(
            "WNBA Step 5N default provider must identify a configured provider."
        )
    if default_provider_id and not by_id[default_provider_id]["enabled"]:
        raise WNBAPropFeedCollectorConfigError(
            "WNBA Step 5N default provider cannot reference a disabled provider."
        )
    return {
        "default_provider_id": default_provider_id,
        "providers": providers,
        "providers_by_id": by_id,
    }


def _missing_secret_env(provider: dict[str, Any], environment: Mapping[str, str]) -> list[str]:
    names = set(provider["secret_header_env"].values()) | set(provider["secret_query_env"].values())
    return sorted(name for name in names if not _clean(environment.get(name)))


def _endpoint_public(url: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _public_provider(provider: dict[str, Any], environment: Mapping[str, str]) -> dict[str, Any]:
    missing = _missing_secret_env(provider, environment)
    return {
        "provider_id": provider["provider_id"],
        "enabled": provider["enabled"],
        "ready": provider["enabled"] and not missing,
        "feed_source": provider["feed_source"],
        "feed_format": provider["feed_format"],
        "odds_format": provider["odds_format"],
        "endpoint": _endpoint_public(provider["url"]),
        "timeout_seconds": provider["timeout_seconds"],
        "max_response_bytes": provider["max_response_bytes"],
        "static_header_names": sorted(provider["headers"]),
        "static_query_names": sorted(provider["query_params"]),
        "secret_header_names": sorted(provider["secret_header_env"]),
        "secret_query_names": sorted(provider["secret_query_env"]),
        "missing_secret_env_names": missing,
        "response_json_path": list(provider["response_json_path"]),
        "list_wrapper_key": provider["list_wrapper_key"],
    }


def describe_provider_registry(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    environment = _environment(env)
    registry = load_provider_registry(environment)
    public = [_public_provider(provider, environment) for provider in registry["providers"]]
    enabled = [provider for provider in public if provider["enabled"]]
    ready = [provider for provider in enabled if provider["ready"]]
    fingerprint = _hash(
        {
            "default_provider_id": registry["default_provider_id"],
            "providers": public,
        }
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_prop_feed_provider_registry",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "provider_registry_fingerprint_sha256": fingerprint,
        "configuration_env": PROVIDERS_ENV,
        "default_provider_env": DEFAULT_PROVIDER_ENV,
        "configured_provider_count": len(public),
        "enabled_provider_count": len(enabled),
        "ready_provider_count": len(ready),
        "default_provider_id": registry["default_provider_id"],
        "providers": public,
        "security_semantics": {
            "api_callers_cannot_supply_arbitrary_provider_urls": True,
            "https_required": True,
            "private_local_ip_literals_rejected": True,
            "literal_sensitive_headers_rejected": True,
            "literal_sensitive_query_values_rejected": True,
            "secret_values_loaded_from_environment_only": True,
            "secret_values_never_returned": True,
            "redirects_disabled": True,
        },
    }


def _resolve_provider(
    provider_id: str | None,
    *,
    registry: dict[str, Any],
    environment: Mapping[str, str],
) -> dict[str, Any]:
    requested = _provider_id(provider_id) if provider_id else None
    if requested is None:
        requested = registry["default_provider_id"]
    if requested is None:
        enabled = [provider for provider in registry["providers"] if provider["enabled"]]
        if len(enabled) == 1:
            requested = enabled[0]["provider_id"]
        elif not enabled:
            raise WNBAPropFeedCollectorNotReadyError(
                f"WNBA Step 5N has no enabled providers. Configure {PROVIDERS_ENV}."
            )
        else:
            raise WNBAPropFeedCollectorNotReadyError(
                f"WNBA Step 5N has multiple enabled providers; configure {DEFAULT_PROVIDER_ENV} or select provider_id."
            )
    provider = registry["providers_by_id"].get(requested)
    if provider is None:
        raise WNBAPropFeedCollectorModelInputError(
            f"WNBA Step 5N provider_id {requested!r} is not configured."
        )
    if not provider["enabled"]:
        raise WNBAPropFeedCollectorNotReadyError(
            f"WNBA Step 5N provider {requested!r} is disabled."
        )
    missing = _missing_secret_env(provider, environment)
    if missing:
        raise WNBAPropFeedCollectorNotReadyError(
            "WNBA Step 5N provider is missing required secret environment variables: "
            + ", ".join(missing)
            + "."
        )
    return provider


def _request_parts(
    provider: dict[str, Any],
    *,
    environment: Mapping[str, str],
    date: str,
    season: int,
) -> tuple[str, dict[str, str], dict[str, str]]:
    url = _render(provider["url"], date=date, season=season)
    headers = {
        name: _render(value, date=date, season=season)
        for name, value in provider["headers"].items()
    }
    query = {
        name: _render(value, date=date, season=season)
        for name, value in provider["query_params"].items()
    }
    for name, env_name in provider["secret_header_env"].items():
        headers[name] = str(environment[env_name])
    for name, env_name in provider["secret_query_env"].items():
        query[name] = str(environment[env_name])
    headers.setdefault("Accept", "application/json")
    headers.setdefault("User-Agent", USER_AGENT)
    return url, headers, query


def _response_size(response: Any) -> int:
    content = getattr(response, "content", b"")
    if isinstance(content, bytes):
        return len(content)
    if isinstance(content, str):
        return len(content.encode("utf-8"))
    text = getattr(response, "text", "")
    return len(str(text).encode("utf-8"))


def _extract_raw_feed(payload: Any, provider: dict[str, Any]) -> dict[str, Any]:
    selected = payload
    for key in provider["response_json_path"]:
        if not isinstance(selected, dict) or key not in selected:
            raise WNBAPropFeedCollectorUpstreamError(
                f"WNBA Step 5N provider {provider['provider_id']!r} response is missing configured JSON path key {key!r}."
            )
        selected = selected[key]
    if isinstance(selected, list):
        wrapper = provider["list_wrapper_key"]
        if wrapper is None:
            wrapper = "offers" if provider["feed_format"] == CANONICAL_FEED_FORMAT else "events"
        return {wrapper: selected}
    if not isinstance(selected, dict):
        raise WNBAPropFeedCollectorUpstreamError(
            f"WNBA Step 5N provider {provider['provider_id']!r} selected JSON payload must be an object or list."
        )
    return selected


def collect_provider_feed(
    provider_id: str | None = None,
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    env: Mapping[str, str] | None = None,
    requester: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    target_date = _target_date(date)
    season = _positive_season(season)
    environment = _environment(env)
    registry = load_provider_registry(environment)
    provider = _resolve_provider(provider_id, registry=registry, environment=environment)
    url, headers, params = _request_parts(
        provider,
        environment=environment,
        date=target_date,
        season=season,
    )
    request_fn = requester or httpx.get
    started = monotonic()
    try:
        response = request_fn(
            url,
            params=params,
            headers=headers,
            timeout=provider["timeout_seconds"],
            follow_redirects=False,
        )
    except (httpx.TimeoutException, TimeoutError) as exc:
        raise WNBAPropFeedCollectorUpstreamError(
            f"WNBA Step 5N provider {provider['provider_id']!r} timed out."
        ) from exc
    except httpx.HTTPError as exc:
        raise WNBAPropFeedCollectorUpstreamError(
            f"WNBA Step 5N provider {provider['provider_id']!r} request failed."
        ) from exc
    except Exception as exc:
        raise WNBAPropFeedCollectorUpstreamError(
            f"WNBA Step 5N provider {provider['provider_id']!r} request failed."
        ) from exc
    latency_ms = round((monotonic() - started) * 1000.0, 3)
    status_code = int(getattr(response, "status_code", 0) or 0)
    if status_code in (301, 302, 303, 307, 308):
        raise WNBAPropFeedCollectorUpstreamError(
            f"WNBA Step 5N provider {provider['provider_id']!r} returned a redirect; configure the final HTTPS endpoint."
        )
    if status_code in (401, 403):
        raise WNBAPropFeedCollectorNotReadyError(
            f"WNBA Step 5N provider {provider['provider_id']!r} rejected authentication/authorization (HTTP {status_code})."
        )
    if status_code == 429:
        raise WNBAPropFeedCollectorNotReadyError(
            f"WNBA Step 5N provider {provider['provider_id']!r} is rate limited (HTTP 429)."
        )
    if status_code < 200 or status_code >= 300:
        raise WNBAPropFeedCollectorUpstreamError(
            f"WNBA Step 5N provider {provider['provider_id']!r} returned HTTP {status_code}."
        )
    response_bytes = _response_size(response)
    if response_bytes > provider["max_response_bytes"]:
        raise WNBAPropFeedCollectorUpstreamError(
            f"WNBA Step 5N provider {provider['provider_id']!r} response exceeded configured size limit."
        )
    try:
        payload = response.json()
    except Exception as exc:
        raise WNBAPropFeedCollectorUpstreamError(
            f"WNBA Step 5N provider {provider['provider_id']!r} did not return valid JSON."
        ) from exc
    raw_feed = _extract_raw_feed(payload, provider)
    collected_at_utc = _utc_now_iso()
    public_provider = _public_provider(provider, environment)
    fingerprint = _hash(
        {
            "provider": public_provider,
            "date": target_date,
            "season": season,
            "status_code": status_code,
            "response_bytes": response_bytes,
            "raw_feed_sha256": _hash(raw_feed),
            "collected_at_utc": collected_at_utc,
        }
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_prop_feed_provider_collection",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "model_family": MODEL_FAMILY,
        "generated_at_utc": collected_at_utc,
        "collection_id": f"wnba-5n-collection-{fingerprint[:20]}",
        "collection_fingerprint_sha256": fingerprint,
        "provider_id": provider["provider_id"],
        "feed_source": provider["feed_source"],
        "feed_format": provider["feed_format"],
        "odds_format": provider["odds_format"],
        "date": target_date,
        "season": season,
        "collected_at_utc": collected_at_utc,
        "transport": {
            "method": "GET",
            "endpoint": _endpoint_public(url),
            "status_code": status_code,
            "latency_ms": latency_ms,
            "response_bytes": response_bytes,
            "redirects_followed": False,
            "timeout_seconds": provider["timeout_seconds"],
        },
        "provider_configuration": public_provider,
        "raw_feed_sha256": _hash(raw_feed),
        "raw_feed": raw_feed,
        "collector_semantics": {
            "configured_provider_only": True,
            "arbitrary_url_input_disabled": True,
            "secret_values_not_returned": True,
            "collection_timestamp_is_step_5m_feed_capture_fallback": True,
            "step_5m_remains_authoritative_for_market_integrity": True,
        },
    }


def build_collected_prop_line_board(
    provider_id: str | None = None,
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    env: Mapping[str, str] | None = None,
    requester: Callable[..., Any] | None = None,
    collector: Callable[..., dict[str, Any]] = collect_provider_feed,
    line_board_builder: Callable[..., dict[str, Any]] = build_prop_line_feed_board,
    **line_board_kwargs: Any,
) -> dict[str, Any]:
    collection = collector(
        provider_id,
        date=date,
        season=season,
        env=env,
        requester=requester,
    )
    line_board = line_board_builder(
        collection["raw_feed"],
        feed_source=collection["feed_source"],
        feed_format=collection["feed_format"],
        odds_format=collection["odds_format"],
        feed_captured_at_utc=collection["collected_at_utc"],
        date=collection["date"],
        season=collection["season"],
        **line_board_kwargs,
    )
    fingerprint = _hash(
        {
            "collection_fingerprint_sha256": collection["collection_fingerprint_sha256"],
            "line_board_fingerprint_sha256": line_board.get("line_board_fingerprint_sha256"),
        }
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_collected_feed_to_step_5m_line_board_pipeline",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "collector_pipeline_id": f"wnba-5n-lines-{fingerprint[:20]}",
        "collector_pipeline_fingerprint_sha256": fingerprint,
        "collection_reference": {
            "collection_id": collection["collection_id"],
            "collection_fingerprint_sha256": collection["collection_fingerprint_sha256"],
            "provider_id": collection["provider_id"],
            "feed_source": collection["feed_source"],
            "feed_format": collection["feed_format"],
            "odds_format": collection["odds_format"],
            "collected_at_utc": collection["collected_at_utc"],
            "transport": collection["transport"],
            "raw_feed_sha256": collection["raw_feed_sha256"],
        },
        "line_board": line_board,
        "pipeline_semantics": {
            "network_collection_precedes_step_5m": True,
            "step_5m_market_integrity_rules_unchanged": True,
            "step_5m_receives_real_collected_json": True,
        },
    }


def build_collected_daily_top_five(
    provider_id: str | None = None,
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    env: Mapping[str, str] | None = None,
    requester: Callable[..., Any] | None = None,
    collector: Callable[..., dict[str, Any]] = collect_provider_feed,
    daily_builder: Callable[..., dict[str, Any]] = build_feed_daily_top_five,
    **daily_kwargs: Any,
) -> dict[str, Any]:
    collection = collector(
        provider_id,
        date=date,
        season=season,
        env=env,
        requester=requester,
    )
    daily = daily_builder(
        collection["raw_feed"],
        feed_source=collection["feed_source"],
        feed_format=collection["feed_format"],
        odds_format=collection["odds_format"],
        feed_captured_at_utc=collection["collected_at_utc"],
        date=collection["date"],
        season=collection["season"],
        **daily_kwargs,
    )
    fingerprint = _hash(
        {
            "collection_fingerprint_sha256": collection["collection_fingerprint_sha256"],
            "feed_pipeline_fingerprint_sha256": daily.get("feed_pipeline_fingerprint_sha256"),
        }
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_collected_feed_to_daily_top_five_pipeline",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "collector_pipeline_id": f"wnba-5n-top5-{fingerprint[:20]}",
        "collector_pipeline_fingerprint_sha256": fingerprint,
        "collection_reference": {
            "collection_id": collection["collection_id"],
            "collection_fingerprint_sha256": collection["collection_fingerprint_sha256"],
            "provider_id": collection["provider_id"],
            "feed_source": collection["feed_source"],
            "feed_format": collection["feed_format"],
            "odds_format": collection["odds_format"],
            "collected_at_utc": collection["collected_at_utc"],
            "transport": collection["transport"],
            "raw_feed_sha256": collection["raw_feed_sha256"],
        },
        "feed_daily_top_five": daily,
        "probability_board_count": daily.get("probability_board_count", 0),
        "value_board_count": daily.get("value_board_count", 0),
        "probability_board": daily.get("probability_board", []),
        "value_board": daily.get("value_board", []),
        "pipeline_semantics": {
            "network_collection_precedes_step_5m": True,
            "step_5m_precedes_step_5l": True,
            "step_5k_primary_probability_rank_unchanged": True,
            "market_data_cannot_move_primary_probability_rank": True,
        },
    }
