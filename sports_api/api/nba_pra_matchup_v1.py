'''Kyre Sports API NBA PRA opponent-rank route using approved CBS backup tables.'''
from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Callable
import re

import httpx
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/nba/pra/matchup", tags=["nba-pra-matchup"])
CBS_ROOT = "https://www.cbssports.com/nba/stats/team/opponent"
HEADERS = {"User-Agent":"Mozilla/5.0", "Accept":"text/html,application/xhtml+xml"}

_TEAM_ALIASES = {
    "atlanta":"ATL","boston":"BOS","brooklyn":"BKN","charlotte":"CHA","chicago":"CHI","cleveland":"CLE",
    "dallas":"DAL","denver":"DEN","detroit":"DET","goldenst":"GSW","goldenstate":"GSW","houston":"HOU",
    "indiana":"IND","laclippers":"LAC","losangelesclippers":"LAC","lalakers":"LAL","losangeleslakers":"LAL",
    "memphis":"MEM","miami":"MIA","milwaukee":"MIL","minnesota":"MIN","neworleans":"NOP","newyork":"NYK",
    "oklahomacity":"OKC","orlando":"ORL","philadelphia":"PHI","phoenix":"PHX","portland":"POR",
    "sacramento":"SAC","sanantonio":"SAS","toronto":"TOR","utah":"UTA","washington":"WAS",
}

class NbaPraMatchupRequest(BaseModel):
    opponent: str = Field(min_length=2, max_length=20)
    now_utc: datetime | None = None

class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._in_table = False
    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "table" and not self._in_table:
            self._in_table = True
        elif self._in_table and tag == "tr":
            self._row = []
        elif self._in_table and tag in {"th","td"} and self._row is not None:
            self._cell = []
    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)
    def handle_endtag(self, tag: str) -> None:
        if self._in_table and tag in {"th","td"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif self._in_table and tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
        elif tag == "table" and self._in_table:
            self._in_table = False

def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").casefold() if ch.isalnum())

def _team_code(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    if re.fullmatch(r"[A-Z]{2,3}", text) and text in set(_TEAM_ALIASES.values()):
        return text
    return _TEAM_ALIASES.get(_norm(value))

def parse_cbs_opponent_table(html: str, *, metric: str) -> list[dict[str, Any]]:
    parser = _TableParser(); parser.feed(str(html or ""))
    if not parser.rows:
        return []
    header_index = next((
        i for i,row in enumerate(parser.rows)
        if row and row[0].strip().casefold()=="team" and any(cell.split()[0] == metric for cell in row if cell)
    ), None)
    if header_index is None:
        return []
    header = parser.rows[header_index]
    try:
        gp_idx = next(i for i,cell in enumerate(header) if cell.split()[0] == "GP")
        metric_idx = next(i for i,cell in enumerate(header) if cell.split()[0] == metric)
    except ValueError:
        return []
    out=[]
    for row in parser.rows[header_index+1:]:
        if len(row) <= max(gp_idx,metric_idx):
            continue
        team=_team_code(row[0])
        try:
            gp=int(float(row[gp_idx])); value=float(row[metric_idx])
        except (TypeError,ValueError):
            continue
        if team and gp > 0:
            out.append({"team":team,"games_played":gp,"value":value})
    return out

def rank_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    ordered=sorted((dict(r) for r in rows if r.get("team") and r.get("value") is not None), key=lambda r:(float(r["value"]),str(r["team"])))
    out={}
    prior=None; rank=0
    for idx,row in enumerate(ordered, start=1):
        value=float(row["value"])
        if prior is None or value != prior:
            rank=idx
        prior=value
        row["rank"]=rank
        out[str(row["team"]).upper()]=row
    return out

def _season_label(now: datetime, period: str) -> str:
    year = now.year if now.month >= 7 else now.year - 1
    return f"{year}-{str(year+1)[-2:]} {period}"

def _get_text(url: str, request_get: Callable[..., Any]) -> str:
    response=request_get(url,headers=HEADERS,timeout=15.0,follow_redirects=True)
    if hasattr(response,"raise_for_status"):
        response.raise_for_status()
    return str(getattr(response,"text","") or "")

def _category_rows(category: str, metric: str, period: str, request_get: Callable[..., Any]) -> list[dict[str,Any]]:
    url=f"{CBS_ROOT}/{category}/nba/{period.casefold()}/"
    return parse_cbs_opponent_table(_get_text(url,request_get), metric=metric)

def collect_nba_pra_matchup(opponent: str, now_utc: datetime | None = None, *, request_get: Callable[..., Any] | None = None) -> dict[str, Any]:
    team=_team_code(opponent)
    if not team:
        return {"source":"Kyre Sports API — CBS Sports","verification":"UNAVAILABLE","diagnostic_state":"INVALID_OPPONENT","fabrication":False}
    now=now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None: now=now.replace(tzinfo=timezone.utc)
    getter=request_get or httpx.get
    try:
        scoring_regular=_category_rows("scoring","PPG","regular",getter)
    except Exception:
        scoring_regular=[]
    period="REGULAR SEASON" if scoring_regular and team in rank_rows(scoring_regular) else "PRESEASON BASELINE"
    route_period="regular" if period=="REGULAR SEASON" else "preseason"
    try:
        scoring=scoring_regular if route_period=="regular" else _category_rows("scoring","PPG",route_period,getter)
        rebounds=_category_rows("rebounds","RPG",route_period,getter)
        assists=_category_rows("assists-turnovers","APG",route_period,getter)
    except Exception as exc:
        return {"source":"Kyre Sports API — CBS Sports","verification":"UNAVAILABLE","diagnostic_state":type(exc).__name__,"fabrication":False}
    ranked={"points":rank_rows(scoring),"rebounds":rank_rows(rebounds),"assists":rank_rows(assists)}
    result={name: rows.get(team) for name,rows in ranked.items()}
    verified=sum(1 for value in result.values() if value)
    return {
        "source":"Kyre Sports API — CBS Sports opponent team stats",
        "verification":"VERIFIED" if verified==3 else "PARTIAL" if verified else "UNAVAILABLE",
        "diagnostic_state":f"RESOLVED_{verified}_OF_3",
        "opponent":team,
        "evidence_period":_season_label(now,period),
        **result,
        "fabrication":False,
    }

@router.post("")
def matchup(request: NbaPraMatchupRequest) -> dict[str, Any]:
    return collect_nba_pra_matchup(request.opponent, request.now_utc)
