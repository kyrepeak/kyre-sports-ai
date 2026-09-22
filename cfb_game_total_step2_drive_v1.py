"""Step 2 points-per-drive enrichment.

Upstream truth comes from Punt & Rally's current-season offense/defense Points
Per Drive tables. Production delivery prefers a verified GitHub snapshot,
falls back to the checked-in snapshot, then tries the direct public table only
as a final recovery path. This module is display/evidence-only and never
changes model/projection inputs outside Step 2 evidence.
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import unicodedata
from typing import Any, Mapping

import requests

PUNT_RALLY_URL = "https://www.puntandrally.com/viewteameff.php"
PUNT_RALLY_TIMEOUT_SECONDS = 4.0
SNAPSHOT_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    "cfb-step2-drive-snapshot-auto-refresh-v1/"
    "data/cfb_step2_drive_snapshot_v1.json"
)
SNAPSHOT_TIMEOUT_SECONDS = 3.0
LOCAL_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent / "data" / "cfb_step2_drive_snapshot_v1.json"
)
_CACHE_TTL_SECONDS = 300.0

_CACHE: dict[tuple[int, str], tuple[float, dict[str, float]]] = {}
_SNAPSHOT_CACHE: dict[
    int,
    tuple[float, dict[str, float], dict[str, float], dict[str, Any]],
] = {}

_COMMON_ALIASES = {
    "appalachianstate": "appstate",
    "louisianamonroe": "ulmonroe",
    "miamifl": "miami",
    "miamiflorida": "miami",
    "southernmississippi": "southernmiss",
    "texassanantonio": "utsa",
    "texaselpaso": "utep",
    "connecticut": "uconn",
}


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = str(data or "").strip()
        if text:
            self.parts.append(text)


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _team_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _clean(value)).encode("ascii", "ignore").decode("ascii")
    key = "".join(ch for ch in text.casefold() if ch.isalnum())
    return _COMMON_ALIASES.get(key, key)


def _candidate_keys(value: Any) -> list[str]:
    raw = _clean(value)
    candidates = [_team_key(raw)]
    without_parenthetical = re.sub(r"\s*\([^)]*\)\s*$", "", raw).strip()
    if without_parenthetical and without_parenthetical != raw:
        candidates.append(_team_key(without_parenthetical))
    out: list[str] = []
    for key in candidates:
        if key and key not in out:
            out.append(key)
    return out


def _text_content(html: str) -> str:
    parser = _TextCollector()
    parser.feed(str(html or ""))
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def _parse_ppd_table(html: str, stat: str) -> dict[str, float]:
    stat = _clean(stat).casefold()
    if stat not in {"offense", "defense"}:
        raise ValueError(f"unsupported PPD stat: {stat!r}")
    text = _text_content(html)
    pattern = re.compile(
        rf"\b\d+\.\s+(.+?)\s*:\s*(-?\d+(?:\.\d+)?)\s+pts/drive\s*\({stat}\)",
        re.IGNORECASE,
    )
    rows: dict[str, float] = {}
    for match in pattern.finditer(text):
        name = _clean(match.group(1))
        key = _team_key(name)
        if not key:
            continue
        try:
            value = float(match.group(2))
        except (TypeError, ValueError):
            continue
        rows[key] = value
    return rows


def _fetch_ppd_table(season: int, stat: str) -> dict[str, float]:
    key = (int(season), _clean(stat).casefold())
    now = time.monotonic()
    cached = _CACHE.get(key)
    if cached and now - cached[0] <= _CACHE_TTL_SECONDS:
        return dict(cached[1])

    response = requests.get(
        PUNT_RALLY_URL,
        params={"metric": "ppd", "stat": key[1], "year": int(season)},
        headers={"User-Agent": "KyreSportsAI-Step2/1.0"},
        timeout=PUNT_RALLY_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = _parse_ppd_table(response.text, key[1])
    if len(rows) < 100:
        raise RuntimeError(
            f"Punt & Rally {key[1]} PPD table parsed only {len(rows)} teams"
        )
    _CACHE[key] = (now, dict(rows))
    return rows


def _snapshot_tables_from_payload(
    payload: Mapping[str, Any],
    season: int,
) -> tuple[dict[str, float], dict[str, float], dict[str, Any]]:
    if int(payload.get("season") or 0) != int(season):
        raise RuntimeError(
            f"drive snapshot season mismatch: expected {int(season)} "
            f"got {payload.get('season')!r}"
        )
    teams = payload.get("teams") or {}
    if not isinstance(teams, Mapping) or len(teams) < 100:
        raise RuntimeError(
            f"drive snapshot coverage too small: {len(teams) if isinstance(teams, Mapping) else 0}"
        )

    offense: dict[str, float] = {}
    defense: dict[str, float] = {}
    for raw_key, raw_row in teams.items():
        if not isinstance(raw_row, Mapping):
            continue
        key = _team_key(raw_key) or _team_key(raw_row.get("team"))
        if not key:
            continue
        try:
            ppd = float(raw_row.get("points_per_drive"))
            ppda = float(raw_row.get("points_per_drive_allowed"))
        except (TypeError, ValueError):
            continue
        offense[key] = ppd
        defense[key] = ppda

    if len(offense) < 100 or len(defense) < 100:
        raise RuntimeError(
            f"drive snapshot parsed offense={len(offense)} defense={len(defense)}"
        )
    diag = {
        "generated_at": payload.get("generated_at"),
        "snapshot_team_count": len(teams),
        "upstream_source": payload.get("source") or "Punt & Rally",
    }
    return offense, defense, diag


def _fetch_snapshot_tables(
    season: int,
) -> tuple[dict[str, float], dict[str, float], dict[str, Any]]:
    season = int(season)
    now = time.monotonic()
    cached = _SNAPSHOT_CACHE.get(season)
    if cached and now - cached[0] <= _CACHE_TTL_SECONDS:
        return dict(cached[1]), dict(cached[2]), dict(cached[3])

    errors: list[str] = []
    payload: dict[str, Any] = {}
    delivery = ""

    try:
        response = requests.get(
            SNAPSHOT_URL,
            headers={"User-Agent": "KyreSportsAI-Step2-Snapshot/1.0"},
            timeout=SNAPSHOT_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        candidate = response.json()
        if isinstance(candidate, Mapping):
            payload = dict(candidate)
            delivery = "github_raw_snapshot"
    except Exception as exc:
        errors.append(f"remote {type(exc).__name__}: {exc}"[:220])

    if not payload:
        try:
            candidate = json.loads(LOCAL_SNAPSHOT_PATH.read_text(encoding="utf-8"))
            if isinstance(candidate, Mapping):
                payload = dict(candidate)
                delivery = "checked_in_snapshot"
        except Exception as exc:
            errors.append(f"local {type(exc).__name__}: {exc}"[:220])

    if not payload:
        raise RuntimeError("drive snapshot unavailable: " + " | ".join(errors))

    offense, defense, diag = _snapshot_tables_from_payload(payload, season)
    diag["delivery"] = delivery
    diag["delivery_errors"] = errors
    _SNAPSHOT_CACHE[season] = (
        now,
        dict(offense),
        dict(defense),
        dict(diag),
    )
    return offense, defense, diag


def _lookup(rows: Mapping[str, float], team: Any) -> float | None:
    for key in _candidate_keys(team):
        if key in rows:
            return float(rows[key])
    return None


def _numeric_missing(value: Any) -> bool:
    if value is None:
        return True
    text = _clean(value)
    if not text or text in {"—", "-"}:
        return True
    try:
        float(text)
        return False
    except ValueError:
        return True


def enrich_step2_drive_metrics(
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
    season: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    away_out = dict(away or {})
    home_out = dict(home or {})
    diag: dict[str, Any] = {
        "source": "Punt & Rally",
        "season": int(season),
        "snapshot_url": SNAPSHOT_URL,
        "offense_url": f"{PUNT_RALLY_URL}?metric=ppd&stat=offense&year={int(season)}",
        "defense_url": f"{PUNT_RALLY_URL}?metric=ppd&stat=defense&year={int(season)}",
        "status": "CHECK",
    }

    try:
        offense, defense, snapshot_diag = _fetch_snapshot_tables(int(season))
        diag.update(snapshot_diag)
    except Exception as snapshot_exc:
        diag["snapshot_error"] = f"{type(snapshot_exc).__name__}: {snapshot_exc}"[:300]
        try:
            offense = _fetch_ppd_table(int(season), "offense")
            defense = _fetch_ppd_table(int(season), "defense")
            diag["delivery"] = "direct_upstream_fallback"
        except Exception as direct_exc:
            diag["error"] = (
                f"snapshot={type(snapshot_exc).__name__}: {snapshot_exc}; "
                f"direct={type(direct_exc).__name__}: {direct_exc}"
            )[:500]
            return away_out, home_out, diag

    sides = (("away", away_out), ("home", home_out))
    matches: dict[str, Any] = {}
    for side, row in sides:
        team = _clean(row.get("team") or row.get("team_name"))
        ppd = _lookup(offense, team)
        ppda = _lookup(defense, team)
        if _numeric_missing(row.get("points_per_drive")) and ppd is not None:
            row["points_per_drive"] = ppd
        if _numeric_missing(row.get("points_per_drive_allowed")) and ppda is not None:
            row["points_per_drive_allowed"] = ppda
        if ppd is not None or ppda is not None:
            row["step2_drive_source"] = (
                "Punt & Rally via verified snapshot"
                if "snapshot" in _clean(diag.get("delivery"))
                else "Punt & Rally"
            )
        matches[side] = {
            "team": team,
            "points_per_drive": ppd,
            "points_per_drive_allowed": ppda,
            "matched": ppd is not None and ppda is not None,
        }

    diag["matches"] = matches
    diag["status"] = (
        "READY"
        if all(bool(item.get("matched")) for item in matches.values())
        else "CHECK"
    )
    return away_out, home_out, diag
