"""Step 2 public points-per-drive enrichment.

Punt & Rally publishes current-season offense and defense Points Per Drive
tables without authentication. This adapter is display/evidence-only: it fills
missing Step 2 drive metrics and fails closed when the source cannot be reached
or matched. It never changes model/projection inputs outside Step 2 evidence.
"""
from __future__ import annotations

from html.parser import HTMLParser
import re
import time
import unicodedata
from typing import Any, Mapping

import requests

PUNT_RALLY_URL = "https://www.puntandrally.com/viewteameff.php"
PUNT_RALLY_TIMEOUT_SECONDS = 4.0
_CACHE_TTL_SECONDS = 300.0

_CACHE: dict[tuple[int, str], tuple[float, dict[str, float]]] = {}

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
    if len(rows) < 20:
        raise RuntimeError(
            f"Punt & Rally {key[1]} PPD table parsed only {len(rows)} teams"
        )
    _CACHE[key] = (now, dict(rows))
    return rows


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
        "offense_url": f"{PUNT_RALLY_URL}?metric=ppd&stat=offense&year={int(season)}",
        "defense_url": f"{PUNT_RALLY_URL}?metric=ppd&stat=defense&year={int(season)}",
        "status": "CHECK",
    }

    try:
        offense = _fetch_ppd_table(int(season), "offense")
        defense = _fetch_ppd_table(int(season), "defense")
    except Exception as exc:
        diag["error"] = f"{type(exc).__name__}: {exc}"[:300]
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
            row["step2_drive_source"] = "Punt & Rally"
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
