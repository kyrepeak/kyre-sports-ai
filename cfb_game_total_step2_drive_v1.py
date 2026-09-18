"""Step 2 public points-per-drive enrichment.

Punt & Rally publishes current-season offense and defense Points Per Drive
tables without authentication. GitHub Actions snapshots those tables onto the
same certified runtime-data branch already used by the CFB schedule/runtime
layer. Deployed Streamlit prefers that stable snapshot, then fails closed to a
checked-in snapshot or a direct upstream fallback.

This module is display/evidence-only. It never changes projection,
distribution, qualification, ranking, odds, or model behavior.
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
REMOTE_SNAPSHOT_TIMEOUT_SECONDS = 5.0
_CACHE_TTL_SECONDS = 300.0
LOCAL_SNAPSHOT_PATH = (
    Path(__file__).resolve().parent / "data" / "cfb_step2_drive_snapshot_v1.json"
)
REMOTE_SNAPSHOT_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    "cfb-runtime-snapshot-auto-refresh-v2/data/cfb_step2_drive_snapshot_v1.json"
)

_LIVE_CACHE: dict[tuple[int, str], tuple[float, dict[str, float]]] = {}
_SNAPSHOT_CACHE: dict[int, tuple[float, dict[str, Any]]] = {}

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
    text = (
        unicodedata.normalize("NFKD", _clean(value))
        .encode("ascii", "ignore")
        .decode("ascii")
    )
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
            rows[key] = float(match.group(2))
        except (TypeError, ValueError):
            continue
    return rows


def _fetch_ppd_table(season: int, stat: str) -> dict[str, float]:
    """Live upstream fetch used by the snapshot builder and final fallback."""
    key = (int(season), _clean(stat).casefold())
    now = time.monotonic()
    cached = _LIVE_CACHE.get(key)
    if cached and now - cached[0] <= _CACHE_TTL_SECONDS:
        return dict(cached[1])

    response = requests.get(
        PUNT_RALLY_URL,
        params={"metric": "ppd", "stat": key[1], "year": int(season)},
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/140 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout=PUNT_RALLY_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    rows = _parse_ppd_table(response.text, key[1])
    if len(rows) < 20:
        raise RuntimeError(
            f"Punt & Rally {key[1]} PPD table parsed only {len(rows)} teams"
        )
    _LIVE_CACHE[key] = (now, dict(rows))
    return rows


def _validated_snapshot(
    payload: Any,
    season: int,
    *,
    source: str,
) -> dict[str, Any] | None:
    if not isinstance(payload, Mapping):
        return None
    if int(payload.get("version") or 0) != 1:
        return None
    if int(payload.get("season") or 0) != int(season):
        return None

    out_tables: dict[str, dict[str, float]] = {}
    for stat in ("offense", "defense"):
        raw = payload.get(stat)
        if not isinstance(raw, Mapping) or len(raw) < 20:
            return None
        parsed: dict[str, float] = {}
        for team, value in raw.items():
            key = _team_key(team)
            if not key:
                continue
            try:
                parsed[key] = float(value)
            except (TypeError, ValueError):
                return None
        if len(parsed) < 20:
            return None
        out_tables[stat] = parsed

    out = dict(payload)
    out["offense"] = out_tables["offense"]
    out["defense"] = out_tables["defense"]
    out["_snapshot_source"] = source
    return out


def _load_drive_snapshot(season: int) -> dict[str, Any]:
    """Prefer the certified runtime-data branch before any direct upstream call."""
    season = int(season)
    now = time.monotonic()
    cached = _SNAPSHOT_CACHE.get(season)
    if cached and now - cached[0] <= _CACHE_TTL_SECONDS:
        return dict(cached[1])

    try:
        response = requests.get(
            REMOTE_SNAPSHOT_URL,
            timeout=REMOTE_SNAPSHOT_TIMEOUT_SECONDS,
            headers={
                "Accept": "application/json",
                "Cache-Control": "no-cache",
                "User-Agent": "KyreSportsAI-Step2-Snapshot/1.0",
            },
        )
        response.raise_for_status()
        remote = _validated_snapshot(
            response.json(),
            season,
            source="certified-runtime-branch",
        )
        if remote is not None:
            _SNAPSHOT_CACHE[season] = (now, dict(remote))
            return remote
    except Exception:
        pass

    try:
        local_payload = json.loads(LOCAL_SNAPSHOT_PATH.read_text(encoding="utf-8"))
        local = _validated_snapshot(
            local_payload,
            season,
            source="checked-in-main-fallback",
        )
        if local is not None:
            _SNAPSHOT_CACHE[season] = (now, dict(local))
            return local
    except Exception:
        pass

    # Final fail-closed transport fallback. GitHub Actions can reach the source
    # even when the deployed Streamlit runtime cannot. No value is fabricated.
    try:
        offense = _fetch_ppd_table(season, "offense")
        defense = _fetch_ppd_table(season, "defense")
        live = _validated_snapshot(
            {
                "version": 1,
                "season": season,
                "generated_at": "",
                "upstream": "Punt & Rally",
                "offense": offense,
                "defense": defense,
            },
            season,
            source="live-upstream-fallback",
        )
        if live is not None:
            _SNAPSHOT_CACHE[season] = (now, dict(live))
            return live
    except Exception:
        pass

    return {
        "version": 1,
        "season": season,
        "offense": {},
        "defense": {},
        "_snapshot_source": "unavailable",
    }


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
    snapshot = _load_drive_snapshot(int(season))
    offense = snapshot.get("offense") if isinstance(snapshot.get("offense"), Mapping) else {}
    defense = snapshot.get("defense") if isinstance(snapshot.get("defense"), Mapping) else {}

    diag: dict[str, Any] = {
        "source": "Punt & Rally via certified runtime snapshot",
        "snapshot_source": _clean(snapshot.get("_snapshot_source")),
        "generated_at": _clean(snapshot.get("generated_at")),
        "season": int(season),
        "snapshot_url": REMOTE_SNAPSHOT_URL,
        "status": "CHECK",
    }

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
                "Punt & Rally • certified runtime snapshot"
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
        if matches and all(bool(item.get("matched")) for item in matches.values())
        else "CHECK"
    )
    return away_out, home_out, diag
