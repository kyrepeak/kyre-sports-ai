"""Kyre Sports API NBA schedule route backed by the official league feed."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Mapping
from zoneinfo import ZoneInfo
import re

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/nba/pra/schedule", tags=["nba-pra-schedule"])
PHOENIX_TZ = ZoneInfo("America/Phoenix")
EASTERN_TZ = ZoneInfo("America/New_York")
OFFICIAL_URLS = (
    "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json",
    "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
)
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

BACKUP_ROOT = "https://www.cbssports.com/nba/schedule"
CODE_ALIASES = {"NY":"NYK","PHO":"PHX","GS":"GSW","NO":"NOP","SA":"SAS"}
TEAM_NAMES = {
    "ATL":"Atlanta Hawks","BOS":"Boston Celtics","BKN":"Brooklyn Nets","CHA":"Charlotte Hornets",
    "CHI":"Chicago Bulls","CLE":"Cleveland Cavaliers","DAL":"Dallas Mavericks","DEN":"Denver Nuggets",
    "DET":"Detroit Pistons","GSW":"Golden State Warriors","HOU":"Houston Rockets","IND":"Indiana Pacers",
    "LAC":"LA Clippers","LAL":"Los Angeles Lakers","MEM":"Memphis Grizzlies","MIA":"Miami Heat",
    "MIL":"Milwaukee Bucks","MIN":"Minnesota Timberwolves","NOP":"New Orleans Pelicans","NYK":"New York Knicks",
    "OKC":"Oklahoma City Thunder","ORL":"Orlando Magic","PHI":"Philadelphia 76ers","PHX":"Phoenix Suns",
    "POR":"Portland Trail Blazers","SAC":"Sacramento Kings","SAS":"San Antonio Spurs","TOR":"Toronto Raptors",
    "UTA":"Utah Jazz","WAS":"Washington Wizards",
}


class NbaPraScheduleRequest(BaseModel):
    now_utc: datetime | None = None


def _text(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split())


def _parse_utc(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _team_name(team: Mapping[str, Any], code: str) -> str:
    city = _text(team.get("teamCity"))
    name = _text(team.get("teamName") or team.get("displayName"))
    if city and name and not name.casefold().startswith(city.casefold()):
        return f"{city} {name}"
    return name or code


def _status(value: Any) -> str:
    try:
        code = int(value)
    except (TypeError, ValueError):
        code = 1
    return "FINAL" if code == 3 else "LIVE" if code == 2 else "UPCOMING"


def _fetch_official() -> Mapping[str, Any]:
    last_error: Exception | None = None
    with httpx.Client(headers=HEADERS, timeout=httpx.Timeout(15.0, connect=3.0), follow_redirects=True) as client:
        for url in OFFICIAL_URLS:
            try:
                response = client.get(url)
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, Mapping):
                    return payload
            except Exception as exc:
                last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError("NBA_OFFICIAL_SCHEDULE_UNAVAILABLE")


def _backup_code(value: str) -> str:
    code = _text(value).upper()
    return CODE_ALIASES.get(code, code)


def _parse_backup_schedule_html(document: str, slate_date: date, now_utc: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", document or "", flags=re.I | re.S):
        raw_codes = re.findall(r"/nba/teams/([A-Z]+)/[^/]+/", row_html, flags=re.I)
        codes: list[str] = []
        for raw in raw_codes:
            code = _backup_code(raw)
            if code and code not in codes:
                codes.append(code)
        if len(codes) < 2:
            continue
        match = re.search(r"\b(\d{1,2}:\d{2})\s*(am|pm)\b", row_html, flags=re.I)
        if not match:
            continue
        clock = datetime.strptime(f"{match.group(1)} {match.group(2).upper()}", "%I:%M %p").time()
        local = datetime.combine(slate_date, clock, tzinfo=EASTERN_TZ)
        tip = local.astimezone(timezone.utc)
        if tip <= now_utc.astimezone(timezone.utc):
            continue
        away_code, home_code = codes[:2]
        phoenix = tip.astimezone(PHOENIX_TZ)
        rows.append({
            "source": "CBS Sports backup",
            "source_game_id": f"CBS-{slate_date.strftime('%Y%m%d')}-{away_code}@{home_code}",
            "game_key": f"{away_code}@{home_code}:{phoenix.date().isoformat()}",
            "away_tricode": away_code,
            "away_name": TEAM_NAMES.get(away_code, away_code),
            "home_tricode": home_code,
            "home_name": TEAM_NAMES.get(home_code, home_code),
            "tip_utc": tip.isoformat().replace("+00:00", "Z"),
            "tip_iso_phoenix": phoenix.isoformat(),
            "game_date_phoenix": phoenix.date().isoformat(),
            "gameStatus": 1,
            "status": "UPCOMING",
            "venue": "",
        })
    return sorted(rows, key=lambda row: row["tip_utc"])


def _fetch_backup(day: date) -> str:
    url = f"{BACKUP_ROOT}/{day.strftime('%Y%m%d')}/"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/html"}
    with httpx.Client(headers=headers, timeout=httpx.Timeout(15.0, connect=3.0), follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def collect_nba_pra_schedule(now_utc: datetime | None = None) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    today = now.astimezone(PHOENIX_TZ).date()
    last_day = today + timedelta(days=8)
    official_error = ""
    try:
        payload = _fetch_official()
        league = payload.get("leagueSchedule") if isinstance(payload, Mapping) else None
        blocks = league.get("gameDates") if isinstance(league, Mapping) else None
        games: list[dict[str, Any]] = []
        if isinstance(blocks, list):
            for block in blocks:
                if not isinstance(block, Mapping):
                    continue
                for raw in block.get("games") or []:
                    if not isinstance(raw, Mapping):
                        continue
                    away = raw.get("awayTeam") or {}; home = raw.get("homeTeam") or {}
                    if not isinstance(away, Mapping) or not isinstance(home, Mapping):
                        continue
                    away_code = _text(away.get("teamTricode")).upper(); home_code = _text(home.get("teamTricode")).upper()
                    tip = _parse_utc(raw.get("gameDateTimeUTC"))
                    if not away_code or not home_code or tip is None:
                        continue
                    local = tip.astimezone(PHOENIX_TZ)
                    if local.date() < today or local.date() > last_day or tip <= now:
                        continue
                    code = raw.get("gameStatus"); status = _status(code)
                    if status != "UPCOMING":
                        continue
                    games.append({
                        "source":"NBA Official","source_game_id":_text(raw.get("gameId")),
                        "game_key":f"{away_code}@{home_code}:{local.date().isoformat()}",
                        "away_tricode":away_code,"away_name":_team_name(away,away_code),
                        "home_tricode":home_code,"home_name":_team_name(home,home_code),
                        "tip_utc":tip.isoformat().replace("+00:00","Z"),"tip_iso_phoenix":local.isoformat(),
                        "game_date_phoenix":local.date().isoformat(),"gameStatus":1,"status":"UPCOMING",
                        "venue":_text(raw.get("arenaName") or raw.get("arena") or ""),
                    })
        if games:
            games.sort(key=lambda row:(row["tip_utc"],row["away_tricode"]))
            return {"source":"Kyre Sports API — NBA Official","verification":"VERIFIED","diagnostic_state":"OK","games":games,"provider_health":{"nba_official":{"status":"HEALTHY","attempted":True}},"fabrication":False}
        official_error = "NBA_OFFICIAL_NO_WINDOW_GAMES"
    except Exception as exc:
        official_error = f"NBA_OFFICIAL_ERROR:{type(exc).__name__}"

    backup_error = ""
    for offset in range(0, 9):
        day = today + timedelta(days=offset)
        try:
            rows = _parse_backup_schedule_html(_fetch_backup(day), day, now)
        except Exception as exc:
            backup_error = f"CBS_BACKUP_ERROR:{type(exc).__name__}"
            continue
        if rows:
            first_day = rows[0]["game_date_phoenix"]
            rows = [row for row in rows if row["game_date_phoenix"] == first_day]
            return {
                "source":"Kyre Sports API — CBS Sports backup",
                "verification":"VERIFIED",
                "diagnostic_state":"OFFICIAL_DEGRADED_BACKUP_VERIFIED",
                "games":rows,
                "provider_health":{"nba_official":{"status":"DEGRADED","detail":official_error,"attempted":True},"cbs_sports":{"status":"HEALTHY","attempted":True}},
                "fabrication":False,
            }
    return {
        "source":"Kyre Sports API — NBA schedule",
        "verification":"UNAVAILABLE",
        "diagnostic_state":backup_error or official_error or "NO_UPCOMING_GAMES",
        "games":[],
        "provider_health":{"nba_official":{"status":"DEGRADED","detail":official_error,"attempted":True},"cbs_sports":{"status":"DEGRADED","detail":backup_error,"attempted":True}},
        "fabrication":False,
    }


@router.post("")
def schedule(request: NbaPraScheduleRequest) -> dict[str, Any]:
    return collect_nba_pra_schedule(request.now_utc)
