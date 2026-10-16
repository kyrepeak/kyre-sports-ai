"""NBA Spread Step 7 — current injury + availability context.

Read-only descriptive layer for the frozen Step-3 matchup identity. Injury data
is routed at the INJURIES field level: NBA Official injury reports are primary
and ESPN NBA injuries are an independent same-semantic fallback/corroborator.
The layer never changes sportsbook lines, projections, probabilities, edges,
rankings, or model inputs.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
import re
from typing import Any, Iterable
import unicodedata
from zoneinfo import ZoneInfo

import requests
from pypdf import PdfReader

MODEL_VERSION = "NBA_SPREAD_STEP7_INJURY_AVAILABILITY_V1"
INJURY_SECTION_LABEL = "Injury + Availability"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False

UTC = timezone.utc
EASTERN_TZ = ZoneInfo("America/New_York")
OFFICIAL_PROVIDER = "nba_official"
ESPN_PROVIDER = "espn"
OFFICIAL_REPORT_BASE_URL = "https://ak-static.cms.nba.com/referee/injury"
ESPN_INJURIES_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
DEFAULT_MAX_AGE_SECONDS = 6 * 60 * 60
OFFICIAL_STATUSES = ("AVAILABLE", "PROBABLE", "QUESTIONABLE", "DOUBTFUL", "OUT")
_STATUS_PATTERN = r"Available|Probable|Questionable|Doubtful|Out"
STATUS_RE = re.compile(rf"\b({_STATUS_PATTERN})\b", re.I)
REPORT_HEADER_RE = re.compile(r"Injury\s+Report:\s*(\d{2}/\d{2}/\d{2})\s+(\d{2}:\d{2})\s+(AM|PM)", re.I)
MATCHUP_RE = re.compile(r"\b([A-Z]{2,4}@[A-Z]{2,4})\b")
DEFAULT_HEADERS = {
    "Accept": "application/json,application/pdf,*/*;q=0.8",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI/1.0; +injury-context)",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", _clean(value)).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def _player_name(value: Any) -> str:
    text = _clean(value)
    if "," in text:
        last, first = [part.strip() for part in text.split(",", 1)]
        text = f"{first} {last}".strip()
    return text


def normalize_status(value: Any) -> str:
    text = _clean(value).upper().replace("_", " ")
    if "OUT" in text or "INACTIVE" in text or "SUSPENDED" in text:
        return "OUT"
    if "DOUBT" in text:
        return "DOUBTFUL"
    if "QUESTION" in text or "GAME TIME" in text or "GAME-TIME" in text:
        return "QUESTIONABLE"
    if "PROBABLE" in text:
        return "PROBABLE"
    if "AVAILABLE" in text or "ACTIVE" in text or "CLEARED" in text:
        return "AVAILABLE"
    return text or "UNKNOWN"


def _game_team_index(games: Iterable[dict[str, Any]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for game in games:
        key = _clean(game.get("game_key"))
        if not key:
            continue
        for side in ("away", "home"):
            code = _clean(game.get(f"{side}_tricode")).upper()
            name = _clean(game.get(f"{side}_name"))
            if code:
                out[code] = {"game_key": key, "team_tricode": code, "team_name": name or code}
                out[_norm(name)] = out[code]
    return out


def _game_by_matchup(games: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for game in games:
        matchup = f"{_clean(game.get('away_tricode')).upper()}@{_clean(game.get('home_tricode')).upper()}"
        if "@" in matchup:
            out[matchup] = game
    return out


def _reason_until_next_row(text: str) -> str:
    value = _clean(text)
    for marker in (" Injury Report:", " Page "):
        if marker in value:
            value = value.split(marker, 1)[0].strip()
    return value


def parse_official_injury_report_text(text: str, *, games: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Parse player rows from NBA Official injury-report PDF text.

    The parser is deliberately bound to the frozen Step-3 matchup/team names so
    an unknown team or matchup is never guessed into the page.
    """
    raw = "\n".join(line.strip() for line in str(text or "").splitlines() if line.strip())
    if not raw:
        return []
    matchups = _game_by_matchup(games)
    team_index = _game_team_index(games)
    if not matchups:
        return []

    flat = re.sub(r"\s+", " ", raw)
    anchors: list[tuple[int, str, dict[str, str]]] = []
    for token, info in team_index.items():
        if not token or token.isupper():
            continue
        name = info["team_name"]
        for m in re.finditer(re.escape(name), flat, re.I):
            anchors.append((m.start(), name, info))
    anchors.sort(key=lambda item: item[0])

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for idx, (start, name, info) in enumerate(anchors):
        end = anchors[idx + 1][0] if idx + 1 < len(anchors) else len(flat)
        segment = flat[start + len(name):end].strip()
        player_matches = list(re.finditer(rf"([A-Za-z .'-]+,\s*[A-Za-z .'-]+)\s+({_STATUS_PATTERN})\b", segment, re.I))
        for pidx, pm in enumerate(player_matches):
            reason_start = pm.end()
            reason_end = player_matches[pidx + 1].start() if pidx + 1 < len(player_matches) else len(segment)
            reason = _reason_until_next_row(segment[reason_start:reason_end])
            player = _player_name(pm.group(1))
            status = normalize_status(pm.group(2))
            identity = (_clean(info["game_key"]), info["team_tricode"], _norm(player))
            if not player or identity in seen:
                continue
            seen.add(identity)
            rows.append({
                "game_key": info["game_key"],
                "team_tricode": info["team_tricode"],
                "team_name": info["team_name"],
                "player_name": player,
                "status": status,
                "reason": reason,
                "provider": OFFICIAL_PROVIDER,
            })
    return sorted(rows, key=lambda row: (row["game_key"], row["team_tricode"], row["player_name"]))


def _flatten_espn(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in (payload or {}).get("injuries", []) or []:
        if not isinstance(item, dict):
            continue
        nested = item.get("injuries")
        if isinstance(nested, list):
            team = item.get("team") or {}
            for child in nested:
                if not isinstance(child, dict):
                    continue
                merged = dict(child)
                merged.setdefault("team", team)
                out.append(merged)
        else:
            out.append(item)
    return out


def parse_espn_injury_payload(payload: dict[str, Any], *, games: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    team_index = _game_team_index(games)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in _flatten_espn(payload if isinstance(payload, dict) else {}):
        team = item.get("team") or {}
        athlete = item.get("athlete") or {}
        code = _clean(team.get("abbreviation")).upper()
        info = team_index.get(code) or team_index.get(_norm(team.get("displayName") or team.get("name")))
        if not info:
            continue
        player = _player_name(athlete.get("displayName") or athlete.get("fullName") or item.get("playerName"))
        status = normalize_status(item.get("status"))
        if not player or status == "UNKNOWN":
            continue
        reason = _clean(item.get("shortComment") or item.get("longComment") or (item.get("injury") or {}).get("type"))
        identity = (info["game_key"], info["team_tricode"], _norm(player))
        if identity in seen:
            continue
        seen.add(identity)
        rows.append({
            "game_key": info["game_key"],
            "team_tricode": info["team_tricode"],
            "team_name": info["team_name"],
            "player_name": player,
            "status": status,
            "reason": reason,
            "provider": ESPN_PROVIDER,
        })
    return sorted(rows, key=lambda row: (row["game_key"], row["team_tricode"], row["player_name"]))


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (_clean(row.get("game_key")), _clean(row.get("team_tricode")).upper(), _norm(row.get("player_name")))


def reconcile_injury_sources(
    official_rows: list[dict[str, Any]],
    espn_rows: list[dict[str, Any]],
    *,
    official_available: bool = True,
    espn_available: bool = True,
) -> dict[str, Any]:
    official = {_row_key(row): dict(row) for row in official_rows}
    espn = {_row_key(row): dict(row) for row in espn_rows}
    providers = []
    if official_available:
        providers.append(OFFICIAL_PROVIDER)
    if espn_available:
        providers.append(ESPN_PROVIDER)

    for key in sorted(set(official) & set(espn)):
        if normalize_status(official[key].get("status")) != normalize_status(espn[key].get("status")):
            return {
                "verification": "UNAVAILABLE",
                "diagnostic_state": "PROVIDER_CONFLICT",
                "providers_consulted": providers,
                "players": [],
            }

    merged: list[dict[str, Any]] = []
    all_keys = sorted(set(official) | set(espn))
    for key in all_keys:
        primary = official.get(key) or espn.get(key)
        if primary is None:
            continue
        item = {
            "game_key": primary["game_key"],
            "team_tricode": primary["team_tricode"],
            "team_name": primary["team_name"],
            "player_name": primary["player_name"],
            "status": normalize_status(primary.get("status")),
            "reason": _clean((official.get(key) or primary).get("reason") or primary.get("reason")),
            "provider": OFFICIAL_PROVIDER if key in official else ESPN_PROVIDER,
            "source_count": int(key in official) + int(key in espn),
            "source_receipts": [provider for provider, table in ((OFFICIAL_PROVIDER, official), (ESPN_PROVIDER, espn)) if key in table],
            "canonical_player_key": _norm(primary.get("player_name")),
        }
        merged.append(item)

    if official_available:
        verification = "VERIFIED"
        diagnostic = "OK"
    elif espn_available:
        verification = "VERIFIED_FALLBACK"
        diagnostic = "PRIMARY_UNAVAILABLE"
    else:
        verification = "UNAVAILABLE"
        diagnostic = "SOURCE_UNAVAILABLE"
    return {
        "verification": verification,
        "diagnostic_state": diagnostic,
        "providers_consulted": providers,
        "players": merged,
    }


def _status_counts(players: list[dict[str, Any]]) -> dict[str, int]:
    return {status: sum(1 for row in players if normalize_status(row.get("status")) == status) for status in OFFICIAL_STATUSES}


def _side_payload(code: str, players: list[dict[str, Any]]) -> dict[str, Any]:
    part = [dict(row) for row in players if _clean(row.get("team_tricode")).upper() == code]
    return {"team_tricode": code, "players": part, "counts": _status_counts(part)}


def _as_utc(value: datetime | str | None) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _clean(value)
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def build_game_injury_features(
    games: list[dict[str, Any]],
    *,
    official_rows: list[dict[str, Any]],
    espn_rows: list[dict[str, Any]],
    official_available: bool,
    espn_available: bool,
    fetched_at_utc: datetime | str | None,
    now_utc: datetime | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    now = _as_utc(now_utc or datetime.now(UTC)) or datetime.now(UTC)
    fetched = _as_utc(fetched_at_utc)
    stale = fetched is None or (now - fetched).total_seconds() > max_age_seconds
    reconciliation = reconcile_injury_sources(
        official_rows,
        espn_rows,
        official_available=official_available,
        espn_available=espn_available,
    )
    features: list[dict[str, Any]] = []
    for game in games:
        key = _clean(game.get("game_key"))
        away = _clean(game.get("away_tricode")).upper()
        home = _clean(game.get("home_tricode")).upper()
        players = [row for row in reconciliation["players"] if _clean(row.get("game_key")) == key]
        if stale:
            verification, diagnostic, players = "UNAVAILABLE", "STALE_SNAPSHOT", []
        else:
            verification = reconciliation["verification"]
            diagnostic = reconciliation["diagnostic_state"]
        features.append({
            "game_key": key,
            "away_tricode": away,
            "home_tricode": home,
            "verification": verification,
            "diagnostic_state": diagnostic,
            "providers_consulted": list(reconciliation["providers_consulted"]),
            "away": _side_payload(away, players),
            "home": _side_payload(home, players),
        })
    return {
        "verification": "VERIFIED" if features and all(f["verification"].startswith("VERIFIED") for f in features) else "UNAVAILABLE",
        "features": features,
        "fetched_at_utc": fetched.isoformat().replace("+00:00", "Z") if fetched else None,
        "max_age_seconds": int(max_age_seconds),
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "model_mutation": False,
        "probability_mutation": False,
    }


def _report_url_for_datetime(value: datetime) -> str:
    local = value.astimezone(EASTERN_TZ)
    return f"{OFFICIAL_REPORT_BASE_URL}/Injury-Report_{local.strftime('%Y-%m-%d_%I_%M%p')}.pdf"


def _candidate_report_datetimes(now_eastern: datetime, lookback_hours: int = 30) -> list[datetime]:
    floored = now_eastern.replace(minute=(now_eastern.minute // 15) * 15, second=0, microsecond=0)
    return [floored - timedelta(minutes=15 * i) for i in range(lookback_hours * 4 + 1)]


def _discover_official_report(now_utc: datetime) -> tuple[str, datetime]:
    now_eastern = now_utc.astimezone(EASTERN_TZ)
    for candidate in _candidate_report_datetimes(now_eastern):
        url = _report_url_for_datetime(candidate)
        try:
            response = requests.head(url, headers=DEFAULT_HEADERS, timeout=4, allow_redirects=True)
            if response.status_code == 200:
                return url, candidate.astimezone(UTC)
            if response.status_code in (405, 501):
                probe = requests.get(url, headers={**DEFAULT_HEADERS, "Range": "bytes=0-7"}, timeout=5, allow_redirects=True)
                if probe.status_code in (200, 206) and probe.content.startswith(b"%PDF"):
                    return url, candidate.astimezone(UTC)
        except requests.RequestException:
            continue
    raise RuntimeError("NBA_OFFICIAL_INJURY_REPORT_UNAVAILABLE")


def _fetch_official_rows(games: list[dict[str, Any]], now_utc: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        url, report_time = _discover_official_report(now_utc)
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15, allow_redirects=True)
        response.raise_for_status()
        if not response.content.startswith(b"%PDF"):
            raise RuntimeError("NBA_OFFICIAL_INJURY_REPORT_NOT_PDF")
        reader = PdfReader(BytesIO(response.content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        rows = parse_official_injury_report_text(text, games=games)
        return rows, {"available": True, "provider": OFFICIAL_PROVIDER, "url": url, "reported_at_utc": report_time}
    except Exception as exc:
        return [], {"available": False, "provider": OFFICIAL_PROVIDER, "error": str(exc)[:180]}


def _fetch_espn_rows(games: list[dict[str, Any]], now_utc: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        response = requests.get(ESPN_INJURIES_URL, headers=DEFAULT_HEADERS, timeout=8)
        response.raise_for_status()
        payload = response.json()
        rows = parse_espn_injury_payload(payload, games=games)
        return rows, {"available": True, "provider": ESPN_PROVIDER, "reported_at_utc": now_utc}
    except Exception as exc:
        return [], {"available": False, "provider": ESPN_PROVIDER, "error": str(exc)[:180]}


def load_injury_availability_features(
    games: list[dict[str, Any]],
    *,
    now_utc: datetime | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> dict[str, Any]:
    """Load current Step-7 injury context for frozen Step-3 games."""
    current = _as_utc(now_utc or datetime.now(UTC)) or datetime.now(UTC)
    eligible = [dict(game) for game in games if _clean(game.get("status")).upper() in {"UPCOMING", "DELAYED"}]
    official_rows, official_meta = _fetch_official_rows(eligible, current)
    espn_rows, espn_meta = _fetch_espn_rows(eligible, current)
    result = build_game_injury_features(
        eligible,
        official_rows=official_rows,
        espn_rows=espn_rows,
        official_available=bool(official_meta.get("available")),
        espn_available=bool(espn_meta.get("available")),
        fetched_at_utc=current,
        now_utc=current,
        max_age_seconds=max_age_seconds,
    )
    result["source_receipts"] = [official_meta, espn_meta]
    result["active_providers"] = [m["provider"] for m in (official_meta, espn_meta) if m.get("available")]
    result["semantic_metric_id"] = "INJURIES"
    result["routing_unit"] = "DATA_FIELD"
    result["page_wide_source_authority"] = False
    return result
