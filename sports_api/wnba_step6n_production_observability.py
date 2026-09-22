"""WNBA Step 6N read-only production observability.

Step 6N observes the frozen/verified Step 6M owned-feed scheduler without
creating a second scheduler, refresh path, storage initializer, or network
client.  It intentionally distinguishes an approved *deferred* pre-hosting
state from a true production incident.

All durable scheduler reads use SQLite ``mode=ro``.  The Kyre market feed is
inspected through the existing network-free Step 6C file validator.  No status
path initializes a database, creates a directory, contacts DraftKings, runs a
model, or performs a wager action.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any
from urllib.parse import quote

from sports_api.collectors.wnba_kyre_market_feed import describe_kyre_market_onboarding
from sports_api.database.wnba_current_board_store import DEFAULT_STORE_PATH, STORE_PATH_ENV
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_schedule import ARIZONA_TZ
from sports_api.wnba_step6m_scheduler_orchestration import get_step6m_scheduler_orchestration_status

MODEL_SOURCE = "Kyre Sports API WNBA Step 6N production observability"
MODEL_VERSION = "wnba_step_6n_production_observability_v1"
SCHEMA_VERSION = MODEL_VERSION
DEFAULT_OVERDUE_GRACE_SECONDS = 120
CRITICAL_OVERDUE_SECONDS = 600
CONSECUTIVE_FAILURE_CRITICAL_COUNT = 3
_TERMINAL_NO_PROVIDER_OUTCOMES = {"empty_official_slate", "pregame_closed"}
_FAILURE_OUTCOMES = {"provider_cycle_failed", "board_rebuild_failed"}


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _target_date(value: str | None, now_utc: datetime) -> str:
    if value is None:
        return now_utc.astimezone(ARIZONA_TZ).date().isoformat()
    text = str(value).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("WNBA Step 6N date must use YYYY-MM-DD format.") from exc
    return text


def _positive_season(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError("WNBA Step 6N season must be a positive integer.")
    return value


def _store_path(environment: Mapping[str, str], explicit: str | os.PathLike[str] | None = None) -> Path:
    raw = explicit if explicit is not None else environment.get(STORE_PATH_ENV)
    return Path(raw).expanduser() if raw else DEFAULT_STORE_PATH


def _readonly_connect(path: Path) -> sqlite3.Connection:
    # URI mode=ro is the hard guarantee that observability cannot create or
    # mutate the scheduler store, even if a caller accidentally points at a
    # missing path.
    uri = f"file:{quote(str(path.resolve()))}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=1.0)
    conn.row_factory = sqlite3.Row
    return conn


def read_scheduler_store_snapshot(
    *,
    date: str,
    season: int,
    env: Mapping[str, str] | None = None,
    board_store_path: str | os.PathLike[str] | None = None,
    run_limit: int = 5,
) -> dict[str, Any]:
    """Read Step 5P scheduler evidence without initializing or mutating SQLite."""
    environment = _environment(env)
    path = _store_path(environment, board_store_path)
    if not path.is_file():
        return {
            "ready": False,
            "store_exists": False,
            "store_path": str(path),
            "latest_scheduler_run": None,
            "recent_scheduler_runs": [],
            "latest_publication": None,
            "error": "scheduler store is not present yet",
            "read_only": True,
        }
    try:
        conn = _readonly_connect(path)
        try:
            run_rows = conn.execute(
                "SELECT run_json FROM wnba_board_scheduler_runs WHERE date=? AND season=? "
                "ORDER BY completed_at_utc DESC,run_id DESC LIMIT ?",
                (date, season, int(run_limit)),
            ).fetchall()
            pub_row = conn.execute(
                "SELECT publication_json FROM wnba_board_publications WHERE date=? AND season=? "
                "ORDER BY published_at_utc DESC,publication_id DESC LIMIT 1",
                (date, season),
            ).fetchone()
        finally:
            conn.close()
        runs = [json.loads(row["run_json"]) for row in run_rows]
        publication = json.loads(pub_row["publication_json"]) if pub_row is not None else None
        return {
            "ready": True,
            "store_exists": True,
            "store_path": str(path),
            "latest_scheduler_run": runs[0] if runs else None,
            "recent_scheduler_runs": runs,
            "latest_publication": publication,
            "error": None,
            "read_only": True,
        }
    except (sqlite3.Error, json.JSONDecodeError, OSError) as exc:
        return {
            "ready": False,
            "store_exists": True,
            "store_path": str(path),
            "latest_scheduler_run": None,
            "recent_scheduler_runs": [],
            "latest_publication": None,
            "error": f"{type(exc).__name__}: {exc}",
            "read_only": True,
        }


def _consecutive_failures(runs: list[dict[str, Any]]) -> int:
    count = 0
    for run in runs:
        if str(run.get("outcome") or "") not in _FAILURE_OUTCOMES:
            break
        count += 1
    return count


def _selected_publication_provider(publication: dict[str, Any] | None) -> str | None:
    if not isinstance(publication, dict):
        return None
    content = publication.get("content") or {}
    source = content.get("source_reference") or {}
    value = source.get("selected_provider_id")
    return str(value).strip().casefold() if value is not None and str(value).strip() else None


def build_step6n_production_observability(
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    now_utc: datetime | None = None,
    env: Mapping[str, str] | None = None,
    overdue_grace_seconds: int = DEFAULT_OVERDUE_GRACE_SECONDS,
    step6m_getter: Callable[..., dict[str, Any]] = get_step6m_scheduler_orchestration_status,
    feed_getter: Callable[..., dict[str, Any]] = describe_kyre_market_onboarding,
    store_reader: Callable[..., dict[str, Any]] = read_scheduler_store_snapshot,
) -> dict[str, Any]:
    """Build a network-free, mutation-free production health report."""
    environment = _environment(env)
    now = _now(now_utc)
    target_date = _target_date(date, now)
    target_season = _positive_season(season)
    if not isinstance(overdue_grace_seconds, int) or isinstance(overdue_grace_seconds, bool) or overdue_grace_seconds < 0:
        raise ValueError("WNBA Step 6N overdue_grace_seconds must be a non-negative integer.")

    step6m = step6m_getter(env=environment)
    step6l = step6m.get("step_6l") or {}
    step6k = step6l.get("step_6k") or {}
    scheduler_authorized = step6k.get("scheduler_authorized") is True
    scheduler_cycle_ready = step6m.get("scheduler_cycle_ready") is True

    feed = feed_getter(env=environment)
    store = store_reader(date=target_date, season=target_season, env=environment)
    latest_run = store.get("latest_scheduler_run") if isinstance(store, dict) else None
    recent_runs = list((store or {}).get("recent_scheduler_runs") or [])
    latest_publication = (store or {}).get("latest_publication")

    incidents: list[dict[str, Any]] = []

    def incident(code: str, severity: str, detail: str) -> None:
        incidents.append({"code": code, "severity": severity, "detail": detail})

    if not scheduler_authorized:
        # This is our current intentional state: Step 6J durable hosting/canary
        # is deferred. Missing production stores/feed are therefore not outages.
        state = "safe_deferred"
        healthy = True
        incident_active = False
        deferred_reason = (
            "Production scheduler authorization is intentionally absent; Step 6J durable hosting/canary remains a prerequisite."
        )
    else:
        deferred_reason = None
        if not scheduler_cycle_ready:
            incident(
                "scheduler_cycle_not_ready",
                "critical",
                "Step 6K authorizes scheduler work but the Step 6M/6L owned-feed cycle is not ready.",
            )
        if not (store or {}).get("ready"):
            incident("scheduler_store_unavailable", "critical", str((store or {}).get("error") or "scheduler store unavailable"))

        latest_outcome = str((latest_run or {}).get("outcome") or "")
        provider_required = latest_outcome not in _TERMINAL_NO_PROVIDER_OUTCOMES
        if provider_required and feed.get("ready") is not True:
            incident("kyre_feed_unavailable", "critical", str(feed.get("configuration_error") or "Kyre feed is missing or invalid."))

        if latest_run is None and (store or {}).get("ready"):
            incident("scheduler_has_no_run_yet", "warning", "Authorized scheduler has no persisted cycle for this slate yet.")
        elif isinstance(latest_run, dict):
            selected = latest_run.get("selected_provider_id")
            if latest_run.get("provider_collection_attempted") is True and selected not in {None, "kyre"}:
                incident("non_kyre_provider_observed", "critical", f"Persisted scheduler run selected unexpected provider {selected!r}.")

            failures = _consecutive_failures(recent_runs)
            if failures >= CONSECUTIVE_FAILURE_CRITICAL_COUNT:
                incident("repeated_scheduler_failures", "critical", f"{failures} consecutive provider/model scheduler failures are persisted.")
            elif failures > 0:
                incident("scheduler_failure_observed", "warning", f"Latest persisted scheduler history contains {failures} consecutive failure(s).")

            due = _dt(latest_run.get("next_due_at_utc"))
            if due is not None:
                overdue_seconds = (now - due).total_seconds()
                if overdue_seconds > overdue_grace_seconds:
                    severity = "critical" if overdue_seconds >= CRITICAL_OVERDUE_SECONDS else "warning"
                    incident(
                        "scheduler_overdue",
                        severity,
                        f"Scheduler is {round(overdue_seconds, 3)} seconds past persisted next_due_at_utc.",
                    )

        publication_provider = _selected_publication_provider(latest_publication)
        if publication_provider not in {None, "kyre"}:
            incident(
                "non_kyre_publication_provider",
                "critical",
                f"Latest persisted publication references unexpected provider {publication_provider!r}.",
            )

        has_critical = any(item["severity"] == "critical" for item in incidents)
        has_warning = any(item["severity"] == "warning" for item in incidents)
        state = "critical" if has_critical else "degraded" if has_warning else "healthy"
        healthy = not has_critical
        incident_active = bool(incidents)

    latest_run_summary = None
    if isinstance(latest_run, dict):
        latest_run_summary = {
            "run_id": latest_run.get("run_id"),
            "outcome": latest_run.get("outcome"),
            "completed_at_utc": latest_run.get("completed_at_utc"),
            "next_due_at_utc": latest_run.get("next_due_at_utc"),
            "provider_collection_attempted": latest_run.get("provider_collection_attempted"),
            "board_rebuild_attempted": latest_run.get("board_rebuild_attempted"),
            "selected_provider_id": latest_run.get("selected_provider_id"),
            "publication_id": latest_run.get("publication_id"),
        }

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6n_production_observability",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso(now),
        "date": target_date,
        "season": target_season,
        "state": state,
        "healthy": healthy,
        "incident_active": incident_active,
        "deferred_reason": deferred_reason,
        "scheduler_authorized": scheduler_authorized,
        "scheduler_cycle_ready": scheduler_cycle_ready,
        "incidents": incidents,
        "step_6m": step6m,
        "kyre_feed": {
            "ready": feed.get("ready"),
            "mode": feed.get("mode"),
            "feed_exists": feed.get("feed_exists"),
            "feed_valid": feed.get("feed_valid"),
            "offer_count": feed.get("offer_count"),
            "date": feed.get("date"),
            "season": feed.get("season"),
            "captured_at_utc": feed.get("captured_at_utc"),
            "configuration_error": feed.get("configuration_error"),
        },
        "scheduler_store": {
            "ready": (store or {}).get("ready"),
            "store_exists": (store or {}).get("store_exists"),
            "read_only": (store or {}).get("read_only"),
            "error": (store or {}).get("error"),
            "latest_scheduler_run": latest_run_summary,
            "recent_run_count": len(recent_runs),
            "consecutive_failure_count": _consecutive_failures(recent_runs),
        },
        "semantics": {
            "safe_deferred_is_not_an_outage": True,
            "scheduler_due_time_comes_from_persisted_step_5p_next_due_at_utc": True,
            "sqlite_opened_mode_ro": True,
            "scheduler_store_not_initialized_by_observability": True,
            "step_5q_lock_not_probed_by_observability": True,
            "network_used": False,
            "draftkings_called": False,
            "feed_write_performed": False,
            "scheduler_cycle_triggered": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "paid_provider_used": False,
        },
    }


def build_step6n_health(
    **kwargs: Any,
) -> dict[str, Any]:
    report = build_step6n_production_observability(**kwargs)
    return {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "status": report["state"],
        "healthy": report["healthy"],
        "incident_active": report["incident_active"],
        "scheduler_authorized": report["scheduler_authorized"],
        "scheduler_cycle_ready": report["scheduler_cycle_ready"],
        "date": report["date"],
        "season": report["season"],
        "deferred_reason": report["deferred_reason"],
        "incidents": report["incidents"],
    }
