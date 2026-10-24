"""Kyre Sports API NBA injury route using the official league report only."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/nba/pra/injuries", tags=["nba-pra-injuries"])


class NbaPraInjuryRequest(BaseModel):
    games: list[dict[str, Any]] = Field(default_factory=list, max_length=30)
    now_utc: datetime | None = None


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())


def collect_nba_pra_injuries(games: list[dict[str, Any]], now_utc: datetime | None = None) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    try:
        from nba_spread_injury_availability_v1 import _fetch_official_rows
        rows, meta = _fetch_official_rows(games, now.astimezone(timezone.utc))
    except Exception as exc:
        rows, meta = [], {"available": False, "error": type(exc).__name__}
    available = bool(meta.get("available"))
    players: dict[str, dict[str, Any]] = {}
    if available:
        for row in rows:
            if not isinstance(row, dict) or not row.get("player_name"):
                continue
            item = dict(row)
            item["verification"] = "VERIFIED"
            item["providers_consulted"] = ["NBA Official Injury Report"]
            players[_norm(row["player_name"])] = item
    return {
        "source": "Kyre Sports API — NBA Official Injury Report",
        "verification": "VERIFIED" if available else "UNAVAILABLE",
        "diagnostic_state": "OK" if available else str(meta.get("error") or "OFFICIAL_REPORT_UNAVAILABLE"),
        "players": players,
        "reported_at_utc": meta.get("reported_at_utc"),
        "fabrication": False,
    }


@router.post("")
def injuries(request: NbaPraInjuryRequest) -> dict[str, Any]:
    return collect_nba_pra_injuries(request.games, request.now_utc)
