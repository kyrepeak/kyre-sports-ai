"""NBA PRA official injury report parser V2.

The NBA injury report is league-wide. Page 2 usually asks for one selected game,
so segmenting the PDF only on those two teams can accidentally attribute every
intervening league row to the first selected team. V2 segments on all NBA team
headers first, then filters to the requested game teams.

Official NBA report only. No ESPN/SGO dependency and no model/projection impact.
"""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
import re
from typing import Any, Iterable


OFFICIAL_PROVIDER = "nba_official"
_STATUS_PATTERN = r"Available|Probable|Questionable|Doubtful|Out"

# Official report display-name aliases. The first value is the canonical label
# used for output matching; alternates cover league naming variants.
NBA_TEAM_HEADERS: dict[str, tuple[str, ...]] = {
    "ATL": ("Atlanta Hawks",),
    "BOS": ("Boston Celtics",),
    "BKN": ("Brooklyn Nets",),
    "CHA": ("Charlotte Hornets",),
    "CHI": ("Chicago Bulls",),
    "CLE": ("Cleveland Cavaliers",),
    "DAL": ("Dallas Mavericks",),
    "DEN": ("Denver Nuggets",),
    "DET": ("Detroit Pistons",),
    "GSW": ("Golden State Warriors",),
    "HOU": ("Houston Rockets",),
    "IND": ("Indiana Pacers",),
    "LAC": ("LA Clippers", "Los Angeles Clippers"),
    "LAL": ("Los Angeles Lakers",),
    "MEM": ("Memphis Grizzlies",),
    "MIA": ("Miami Heat",),
    "MIL": ("Milwaukee Bucks",),
    "MIN": ("Minnesota Timberwolves",),
    "NOP": ("New Orleans Pelicans",),
    "NYK": ("New York Knicks",),
    "OKC": ("Oklahoma City Thunder",),
    "ORL": ("Orlando Magic",),
    "PHI": ("Philadelphia 76ers",),
    "PHX": ("Phoenix Suns",),
    "POR": ("Portland Trail Blazers",),
    "SAC": ("Sacramento Kings",),
    "SAS": ("San Antonio Spurs",),
    "TOR": ("Toronto Raptors",),
    "UTA": ("Utah Jazz",),
    "WAS": ("Washington Wizards",),
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _player_name(value: Any) -> str:
    text = _clean(value)
    if "," in text:
        last, first = [part.strip() for part in text.split(",", 1)]
        text = f"{first} {last}".strip()
    return text


def _normalize_status(value: Any) -> str:
    text = _clean(value).upper()
    if "OUT" in text:
        return "OUT"
    if "DOUBT" in text:
        return "DOUBTFUL"
    if "QUESTION" in text:
        return "QUESTIONABLE"
    if "PROBABLE" in text:
        return "PROBABLE"
    if "AVAILABLE" in text:
        return "AVAILABLE"
    return text or "UNKNOWN"


def _reason(value: str) -> str:
    text = _clean(value)
    for marker in (" Injury Report:", " Page "):
        if marker in text:
            text = text.split(marker, 1)[0].strip()
    return text


def _target_teams(games: Iterable[dict[str, Any]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for game in games:
        game_key = _clean(game.get("game_key"))
        for side in ("away", "home"):
            code = _clean(game.get(f"{side}_tricode")).upper()
            name = _clean(game.get(f"{side}_name"))
            if code and game_key:
                out[code] = {
                    "game_key": game_key,
                    "team_tricode": code,
                    "team_name": name or (NBA_TEAM_HEADERS.get(code) or (code,))[0],
                }
    return out


def _all_team_anchors(flat: str) -> list[tuple[int, int, str]]:
    candidates: list[tuple[int, int, str]] = []
    for code, aliases in NBA_TEAM_HEADERS.items():
        for alias in aliases:
            for match in re.finditer(re.escape(alias), flat, flags=re.I):
                candidates.append((match.start(), match.end(), code))
    # Prefer the longest alias when aliases overlap at the same position.
    by_start: dict[int, tuple[int, int, str]] = {}
    for item in candidates:
        prior = by_start.get(item[0])
        if prior is None or (item[1] - item[0]) > (prior[1] - prior[0]):
            by_start[item[0]] = item
    return sorted(by_start.values(), key=lambda item: item[0])


def parse_official_injury_report_text_v2(
    text: str,
    *,
    games: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw = "\n".join(line.strip() for line in str(text or "").splitlines() if line.strip())
    targets = _target_teams(games)
    if not raw or not targets:
        return []

    flat = re.sub(r"\s+", " ", raw)
    anchors = _all_team_anchors(flat)
    if not anchors:
        return []

    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for index, (_start, end_of_header, code) in enumerate(anchors):
        segment_end = anchors[index + 1][0] if index + 1 < len(anchors) else len(flat)
        info = targets.get(code)
        if info is None:
            continue
        segment = flat[end_of_header:segment_end].strip()
        player_matches = list(
            re.finditer(
                rf"([A-Za-z .'-]+,\s*[A-Za-z .'-]+)\s+({_STATUS_PATTERN})\b",
                segment,
                flags=re.I,
            )
        )
        for player_index, match in enumerate(player_matches):
            reason_start = match.end()
            reason_end = (
                player_matches[player_index + 1].start()
                if player_index + 1 < len(player_matches)
                else len(segment)
            )
            player = _player_name(match.group(1))
            status = _normalize_status(match.group(2))
            identity = (info["game_key"], code, player.casefold())
            if not player or identity in seen:
                continue
            seen.add(identity)
            rows.append(
                {
                    "game_key": info["game_key"],
                    "team_tricode": code,
                    "team_name": info["team_name"],
                    "player_name": player,
                    "status": status,
                    "reason": _reason(segment[reason_start:reason_end]),
                    "provider": OFFICIAL_PROVIDER,
                }
            )
    return sorted(rows, key=lambda row: (row["game_key"], row["team_tricode"], row["player_name"]))


def fetch_official_rows_v2(
    games: list[dict[str, Any]],
    now_utc: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fetch the official league PDF and parse only requested game teams."""
    try:
        import requests
        from pypdf import PdfReader
        from nba_spread_injury_availability_v1 import (
            DEFAULT_HEADERS,
            _discover_official_report,
        )

        url, report_time = _discover_official_report(now_utc)
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=15, allow_redirects=True)
        response.raise_for_status()
        if not response.content.startswith(b"%PDF"):
            raise RuntimeError("NBA_OFFICIAL_INJURY_REPORT_NOT_PDF")
        reader = PdfReader(BytesIO(response.content))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        rows = parse_official_injury_report_text_v2(text, games=games)
        return rows, {
            "available": True,
            "provider": OFFICIAL_PROVIDER,
            "url": url,
            "reported_at_utc": report_time,
        }
    except Exception as exc:
        return [], {
            "available": False,
            "provider": OFFICIAL_PROVIDER,
            "error": str(exc)[:180],
        }
