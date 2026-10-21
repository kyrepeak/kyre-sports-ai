"""Lightweight render-ready WNBA PRA page snapshot API."""
from __future__ import annotations

from datetime import datetime, timezone
import asyncio
import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any, Callable, Mapping

from fastapi import APIRouter, Body, Header, HTTPException, Query

from .wnba_pra_market_v1 import build_pra_market_board
from .wnba_pra_page_snapshot_store_v1 import WNBAPRASnapshotStore

router = APIRouter(prefix="/api/v1/wnba/pra", tags=["wnba-pra-page-snapshot"])
MODEL_SCHEMA_VERSION = "wnba_pra_page_model_artifact_v1"
PAGE_SCHEMA_VERSION = "wnba_pra_page_snapshot_v1"
FRESH_MODEL_SECONDS = 300.0
STALE_SAFE_MODEL_SECONDS = 900.0


def _utc(value: Any) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _name(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def _row_key(row: Mapping[str, Any]) -> tuple[str, float]:
    return _name(row.get("player_name") or row.get("player")), float(row.get("line"))


def _safe_model_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "p_over", "p_under", "no_vig_over", "fair_over", "fair_under", "edge", "ev100",
        "final_ready", "model_qualified", "converged", "data_quality", "context_quality",
        "variance_source", "model_pass", "projection_pra", "projection_minutes", "team", "opponent",
    )
    return {field: row[field] for field in allowed if field in row}


def _market_capture(board: Mapping[str, Any]) -> str | None:
    captures = [str(x.get("market_captured_at_utc") or "") for x in (board.get("offers") or []) if isinstance(x, Mapping)]
    captures = [x for x in captures if x]
    return max(captures) if captures else None



def _artifact_hash(payload: Mapping[str, Any]) -> str:
    raw = dict(payload)
    raw.pop("content_hash", None)
    text = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def validate_artifact_light(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("model artifact must be an object")
    out = dict(payload)
    if out.get("schema_version") != MODEL_SCHEMA_VERSION:
        raise ValueError("model artifact schema mismatch")
    datetime.strptime(str(out.get("date") or ""), "%Y-%m-%d")
    if int(out.get("season") or 0) != 2026:
        raise ValueError("model artifact season mismatch")
    _utc(out.get("generated_at"))
    if not str(out.get("model_version") or "").strip():
        raise ValueError("model artifact model version required")
    if not isinstance(out.get("rows"), list) or not isinstance(out.get("line_bindings"), Mapping) or not isinstance(out.get("final_card"), list):
        raise ValueError("model artifact shape invalid")
    if out.get("content_hash") != _artifact_hash(out):
        raise ValueError("model artifact content hash mismatch")
    return out


async def _artifact_from_exact_sha_sandbox(date: str, season: int) -> dict[str, Any]:
    from .config import Settings
    from .github_authority import GithubAuthority
    from .sandbox_executor import VercelSandboxBackend

    settings = Settings.from_env()
    github = GithubAuthority(settings)
    candidate_sha = str(os.environ.get("VERCEL_GIT_COMMIT_SHA") or github.main_sha()).strip().lower()
    if len(candidate_sha) != 40 or any(ch not in "0123456789abcdef" for ch in candidate_sha):
        raise RuntimeError("WNBA_PRA_REFRESH_SHA_INVALID")
    backend = VercelSandboxBackend()
    session_id = await backend.create(
        candidate_sha=candidate_sha, github_token=github.installation_token(), runtime="python3.13",
        persistent=False, timeout_ms=240000,
    )
    code = (
        "import json,sys;"
        "from wnba_pra_page_model_artifact_v1 import build_model_artifact,_hash_payload,validate_model_artifact;"
        "a=build_model_artifact(sys.argv[1],int(sys.argv[2]));"
        "s={k:a[k] for k in ('schema_version','date','season','generated_at','model_version','source_status','blocked_fallback_calls','rows','line_bindings','final_card')};"
        "s['content_hash']=_hash_payload(s);validate_model_artifact(s);"
        "print(json.dumps(s,sort_keys=True,separators=(',',':')))"
    )
    try:
        result = await backend.run(session_id, "python", ["-c", code, str(date), str(int(season))], timeout_ms=210000)
        if int(result.get("exit_code", 1)) != 0:
            raise RuntimeError("WNBA_PRA_REFRESH_SANDBOX_FAILED")
        lines = [line for line in str(result.get("stdout") or "").splitlines() if line.strip()]
        if not lines:
            raise RuntimeError("WNBA_PRA_REFRESH_SANDBOX_EMPTY")
        return validate_artifact_light(json.loads(lines[-1]))
    finally:
        await backend.stop(session_id)


def _build_artifact_server_owned(date: str, season: int) -> dict[str, Any]:
    return asyncio.run(_artifact_from_exact_sha_sandbox(date, season))


def refresh_snapshot_server_owned(
    *, date: str, season: int = 2026, store: Any | None = None,
    page_state_builder: Callable[..., dict[str, Any]] | None = None,
    artifact_builder: Callable[[str, int], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    datetime.strptime(str(date), "%Y-%m-%d")
    if int(season) != 2026:
        raise ValueError("WNBA PRA refresh supports season 2026 only.")
    repo = store or WNBAPRASnapshotStore.from_env()
    state_builder = page_state_builder or build_page_snapshot
    state = state_builder(date=str(date), season=int(season), store=repo)
    if state.get("refresh_required") is not True and state.get("cache_state") == "FRESH" and state.get("snapshot_state") == "READY":
        return {"state":"NOT_NEEDED", "snapshot_state":"READY", "cache_state":"FRESH"}
    owner_id = "vercel-refresh-" + uuid.uuid4().hex[:16]
    claim = repo.claim_refresh(date=str(date), season=int(season), owner_id=owner_id, ttl_seconds=300)
    if claim.get("acquired") is not True or not claim.get("lease_token"):
        return {"state":"ALREADY_RUNNING", "snapshot_state":state.get("snapshot_state"), "cache_state":state.get("cache_state")}
    lease_token = str(claim["lease_token"])
    build = artifact_builder or _build_artifact_server_owned
    try:
        artifact = validate_artifact_light(build(str(date), int(season)))
        stored = repo.publish_with_lease(artifact, owner_id=owner_id, lease_token=lease_token)
        return {"state":"REFRESHED", "content_hash":stored.get("content_hash") or artifact["content_hash"], "snapshot_state":state.get("snapshot_state")}
    except Exception:
        try:
            repo.release_refresh(date=str(date), season=int(season), owner_id=owner_id, lease_token=lease_token)
        except Exception:
            pass
        raise

def require_publish_token(authorization: str | None) -> None:
    expected = str(os.environ.get("WNBA_PRA_SNAPSHOT_PUBLISH_TOKEN") or "").strip()
    supplied = str(authorization or "")
    prefix = "Bearer "
    if not expected or not supplied.startswith(prefix):
        raise HTTPException(status_code=401, detail="WNBA_PRA_SNAPSHOT_AUTH_REQUIRED")
    if not hmac.compare_digest(supplied[len(prefix):], expected):
        raise HTTPException(status_code=401, detail="WNBA_PRA_SNAPSHOT_AUTH_INVALID")


def build_page_snapshot(
    *,
    date: str,
    season: int = 2026,
    store: Any | None = None,
    market_board_builder: Callable[..., dict[str, Any]] = build_pra_market_board,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    datetime.strptime(str(date), "%Y-%m-%d")
    if int(season) != 2026:
        raise ValueError("WNBA PRA page snapshot currently supports season 2026.")
    started = time.perf_counter()
    repo = store or WNBAPRASnapshotStore.from_env()
    artifact = repo.read(date=str(date), season=int(season), schema_version=MODEL_SCHEMA_VERSION)
    board = market_board_builder(date=str(date), season=int(season))
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age: float | None = None
    cache_state = "MODEL_UNAVAILABLE"
    model_rows: dict[tuple[str, float], dict[str, Any]] = {}
    final_card: list[dict[str, Any]] = []
    model_generated_at: str | None = None
    if isinstance(artifact, Mapping):
        model_generated_at = str(artifact.get("generated_at") or "") or None
        if model_generated_at:
            age = max(0.0, (now.astimezone(timezone.utc) - _utc(model_generated_at)).total_seconds())
        if age is not None and age <= FRESH_MODEL_SECONDS:
            cache_state = "FRESH"
        elif age is not None and age <= STALE_SAFE_MODEL_SECONDS:
            cache_state = "STALE_SAFE"
        else:
            cache_state = "MODEL_UNAVAILABLE"
        if cache_state != "MODEL_UNAVAILABLE":
            for raw in artifact.get("rows") or []:
                if isinstance(raw, Mapping) and raw.get("line") is not None:
                    model_rows[_row_key(raw)] = dict(raw)
            final_card = [dict(x) for x in (artifact.get("final_card") or []) if isinstance(x, Mapping)]

    offers: list[dict[str, Any]] = []
    mismatch = False
    live_keys: set[tuple[str, float]] = set()
    for raw in board.get("offers") or []:
        if not isinstance(raw, Mapping):
            continue
        offer = dict(raw)
        try:
            key = _row_key(offer)
        except (TypeError, ValueError):
            offer["model_state"] = "MODEL_UNAVAILABLE"
            offers.append(offer)
            continue
        live_keys.add(key)
        matched = model_rows.get(key)
        if matched is not None:
            offer.update(_safe_model_fields(matched))
            offer["model_state"] = "LINE_BOUND_READY"
        elif cache_state != "MODEL_UNAVAILABLE":
            same_player = any(k[0] == key[0] for k in model_rows)
            if same_player:
                mismatch = True
                offer["model_state"] = "MODEL_REFRESH_REQUIRED"
            else:
                offer["model_state"] = "MODEL_UNAVAILABLE"
        else:
            offer["model_state"] = "MODEL_UNAVAILABLE"
        offers.append(offer)

    if mismatch:
        snapshot_state = "MODEL_REFRESH_REQUIRED"
        refresh_required = True
        final_card = []
    elif cache_state == "MODEL_UNAVAILABLE":
        snapshot_state = "MODEL_UNAVAILABLE"
        refresh_required = True
        final_card = []
    else:
        snapshot_state = "READY"
        refresh_required = cache_state == "STALE_SAFE"
        final_card = [
            card for card in final_card
            if isinstance(card, Mapping)
            and card.get("line") is not None
            and (_name(card.get("player_name") or card.get("player")), float(card.get("line"))) in live_keys
        ]

    return {
        "service": "Kyre Sports API — Vercel",
        "schema_version": PAGE_SCHEMA_VERSION,
        "date": str(date),
        "season": int(season),
        "snapshot_state": snapshot_state,
        "cache_state": cache_state,
        "model_age_seconds": age,
        "model_generated_at": model_generated_at,
        "market_capture_at": _market_capture(board),
        "selected_provider": board.get("selected_provider"),
        "sportsbooks": list(board.get("sportsbooks") or []),
        "provider_health": list(board.get("provider_health") or []),
        "schedule": list((artifact or {}).get("schedule") or []) if isinstance(artifact, Mapping) else [],
        "diagnostics": dict((artifact or {}).get("diagnostics") or {}) if isinstance(artifact, Mapping) else {},
        "offers": offers,
        "final_card": final_card,
        "refresh_required": bool(refresh_required),
        "market_board_reads": 1,
        "consensus_averaging": False,
        "projection_weight": 0.0,
        "assembly_ms": round((time.perf_counter() - started) * 1000.0, 3),
    }


@router.get("/page-snapshot")
def page_snapshot(date: str = Query(...), season: int = Query(2026)) -> dict[str, Any]:
    try:
        return build_page_snapshot(date=date, season=season)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"WNBA PRA page snapshot unavailable: {type(exc).__name__}") from exc


@router.post("/page-snapshot/refresh-claim")
def refresh_claim(
    payload: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    require_publish_token(authorization)
    date = str(payload.get("date") or "")
    season = int(payload.get("season") or 2026)
    owner_id = str(payload.get("owner_id") or "").strip()
    if not date or not owner_id:
        raise HTTPException(status_code=422, detail="date and owner_id are required")
    return WNBAPRASnapshotStore.from_env().claim_refresh(date=date, season=season, owner_id=owner_id, ttl_seconds=300)


@router.post("/page-snapshot/refresh-release")
def refresh_release(
    payload: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    require_publish_token(authorization)
    date = str(payload.get("date") or "")
    season = int(payload.get("season") or 2026)
    owner_id = str(payload.get("owner_id") or "").strip()
    lease_token = str(payload.get("lease_token") or "").strip()
    if not date or not owner_id or not lease_token:
        raise HTTPException(status_code=422, detail="date, owner_id and lease_token are required")
    return WNBAPRASnapshotStore.from_env().release_refresh(
        date=date, season=season, owner_id=owner_id, lease_token=lease_token
    )


@router.post("/page-snapshot/refresh-request")
def refresh_request(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        return refresh_snapshot_server_owned(
            date=str(payload.get("date") or ""), season=int(payload.get("season") or 2026)
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"WNBA PRA refresh unavailable: {type(exc).__name__}") from exc


@router.post("/page-snapshot/publish")
def publish_snapshot(
    payload: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    require_publish_token(authorization)
    artifact = validate_artifact_light(payload.get("artifact") or {})
    owner_id = str(payload.get("owner_id") or "").strip()
    lease_token = str(payload.get("lease_token") or "").strip()
    if not owner_id or not lease_token:
        raise HTTPException(status_code=422, detail="owner_id and lease_token are required")
    store = WNBAPRASnapshotStore.from_env()
    stored = store.publish_with_lease(artifact, owner_id=owner_id, lease_token=lease_token)
    return {"stored": bool(stored.get("stored")), "content_hash": stored.get("content_hash")}


__all__ = [
    "MODEL_SCHEMA_VERSION", "PAGE_SCHEMA_VERSION", "build_page_snapshot", "page_snapshot",
    "publish_snapshot", "refresh_claim", "refresh_release", "refresh_request", "refresh_snapshot_server_owned",
    "validate_artifact_light", "require_publish_token", "router",
]
