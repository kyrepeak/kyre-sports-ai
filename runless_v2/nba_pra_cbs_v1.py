"""Approved CBS Sports fallback for NBA identity/roster/history.

This module is server-side only behind Kyre Sports API. It does not provide
sportsbook lines and never influences provider routing outside NBA enrichment.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from html.parser import HTMLParser
import re
from typing import Any, Callable, Mapping, Sequence

import httpx

CBS_BASE = "https://www.cbssports.com"
CBS_HEADSHOT = "https://sportshub.cbsistatic.com/i/sports/player/headshot/{player_id}.png?width=160"
CBS_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAI/1.0)",
}

# Canonical NBA tricode -> CBS route code / slug.
TEAM_ROUTES: dict[str, tuple[str, str]] = {
    "ATL": ("ATL", "atlanta-hawks"),
    "BOS": ("BOS", "boston-celtics"),
    "BKN": ("BKN", "brooklyn-nets"),
    "CHA": ("CHA", "charlotte-hornets"),
    "CHI": ("CHI", "chicago-bulls"),
    "CLE": ("CLE", "cleveland-cavaliers"),
    "DAL": ("DAL", "dallas-mavericks"),
    "DEN": ("DEN", "denver-nuggets"),
    "DET": ("DET", "detroit-pistons"),
    "GSW": ("GS", "golden-state-warriors"),
    "HOU": ("HOU", "houston-rockets"),
    "IND": ("IND", "indiana-pacers"),
    "LAC": ("LAC", "los-angeles-clippers"),
    "LAL": ("LAL", "los-angeles-lakers"),
    "MEM": ("MEM", "memphis-grizzlies"),
    "MIA": ("MIA", "miami-heat"),
    "MIL": ("MIL", "milwaukee-bucks"),
    "MIN": ("MIN", "minnesota-timberwolves"),
    "NOP": ("NO", "new-orleans-pelicans"),
    "NYK": ("NY", "new-york-knicks"),
    "OKC": ("OKC", "oklahoma-city-thunder"),
    "ORL": ("ORL", "orlando-magic"),
    "PHI": ("PHI", "philadelphia-76ers"),
    "PHX": ("PHO", "phoenix-suns"),
    "POR": ("POR", "portland-trail-blazers"),
    "SAC": ("SAC", "sacramento-kings"),
    "SAS": ("SA", "san-antonio-spurs"),
    "TOR": ("TOR", "toronto-raptors"),
    "UTA": ("UTA", "utah-jazz"),
    "WAS": ("WAS", "washington-wizards"),
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _norm(value: Any) -> str:
    return "".join(ch for ch in _clean(value).casefold() if ch.isalnum())


def _number(value: Any) -> float | None:
    text = _clean(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _date(value: Any) -> str | None:
    text = _clean(value)
    for fmt in ("%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y", "%m.%d.%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _strip_tags(value: str) -> str:
    return _clean(re.sub(r"<[^>]+>", " ", str(value or "")))


class _HTMLTables(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._depth = 0
        self._rows: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:
        name = tag.casefold()
        if name == "table":
            self._depth += 1
            if self._depth == 1:
                self._rows = []
        elif self._depth == 1 and name == "tr":
            self._row = []
        elif self._depth == 1 and name in {"th", "td"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            text = _clean(data)
            if text:
                self._cell.append(text)

    def handle_endtag(self, tag: str) -> None:
        name = tag.casefold()
        if self._depth == 1 and name in {"th", "td"} and self._cell is not None:
            if self._row is not None:
                self._row.append(_clean(" ".join(self._cell)))
            self._cell = None
        elif self._depth == 1 and name == "tr" and self._row is not None:
            if any(_clean(cell) for cell in self._row):
                assert self._rows is not None
                self._rows.append(self._row)
            self._row = None
            self._cell = None
        elif name == "table" and self._depth > 0:
            if self._depth == 1 and self._rows is not None:
                self.tables.append(self._rows)
                self._rows = None
            self._depth -= 1


def parse_cbs_roster(document: str, *, team: str) -> dict[str, dict[str, Any]]:
    canonical_team = _clean(team).upper()
    out: dict[str, dict[str, Any]] = {}
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", str(document or ""), flags=re.I | re.S):
        links = re.findall(
            r"<a[^>]+href=[\"']/nba/players/(\d+)/([^/]+)/[\"'][^>]*>(.*?)</a>",
            row_html,
            flags=re.I | re.S,
        )
        if not links:
            continue
        candidates: list[tuple[str, str, str]] = []
        for player_id, slug, label_html in links:
            label = _strip_tags(label_html)
            if label:
                candidates.append((player_id, slug, label))
        if not candidates:
            continue
        # CBS renders short and long labels for responsive layouts. Longest label
        # is the canonical visible name, not a guessed provider alias.
        player_id, slug, player_name = max(candidates, key=lambda row: len(row[2]))
        cells = [
            _strip_tags(body)
            for body in re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.I | re.S)
        ]
        position = cells[2] if len(cells) >= 3 else ""
        key = _norm(player_name)
        if not key:
            continue
        out[key] = {
            "player_name": player_name,
            "team": canonical_team,
            "position": position,
            "provider_ids": {"cbs_sports": player_id},
            "provider_slug": slug,
            "headshot": CBS_HEADSHOT.format(player_id=player_id),
        }
    return out


def parse_cbs_gamelog(document: str) -> list[dict[str, Any]]:
    parser = _HTMLTables()
    parser.feed(str(document or ""))
    games: list[dict[str, Any]] = []
    seen: set[str] = set()
    for table in parser.tables:
        if not table:
            continue
        header_index = None
        index: dict[str, int] = {}
        for i, row in enumerate(table[:3]):
            normalized = [_norm(cell) for cell in row]
            local = {name: pos for pos, name in enumerate(normalized)}
            required = {"date", "minminutes", "ptspoints", "rebtotalrebounds", "asttotalassists"}
            if required.issubset(local):
                header_index = i
                index = local
                break
        if header_index is None:
            continue
        for raw in table[header_index + 1 :]:
            if len(raw) <= max(index.values()):
                continue
            game_date = _date(raw[index["date"]])
            if game_date is None or game_date in seen:
                continue
            minutes = _number(raw[index["minminutes"]])
            points = _number(raw[index["ptspoints"]])
            rebounds = _number(raw[index["rebtotalrebounds"]])
            assists = _number(raw[index["asttotalassists"]])
            if points is None or rebounds is None or assists is None:
                continue
            seen.add(game_date)
            games.append({
                "game_date": game_date,
                "minutes": minutes,
                "points": points,
                "rebounds": rebounds,
                "assists": assists,
            })
    games.sort(key=lambda row: row["game_date"], reverse=True)
    return games


def _default_fetch_text(kind: str, value: str, season: int | None = None) -> str:
    timeout = httpx.Timeout(12.0, connect=3.0)
    with httpx.Client(headers=CBS_HEADERS, timeout=timeout, follow_redirects=True) as client:
        if kind == "roster":
            code = _clean(value).upper()
            route = TEAM_ROUTES.get(code)
            if route is None:
                raise ValueError("CBS_TEAM_ROUTE_UNAVAILABLE")
            cbs_code, slug = route
            url = f"{CBS_BASE}/nba/teams/{cbs_code}/{slug}/roster/"
        elif kind == "gamelog" and season is not None:
            player_id = _clean(value)
            url = f"{CBS_BASE}/nba/players/{player_id}/player/game-log/{int(season)}/"
            # Current CBS route canonicalizes without the placeholder slug.
            url = f"{CBS_BASE}/nba/players/{player_id}/x/game-log/{int(season)}/"
        else:
            raise ValueError("CBS_FETCH_KIND_UNSUPPORTED")
        response = client.get(url)
        if kind == "gamelog" and response.status_code == 404:
            # CBS requires a slug in the path. Resolve by stable player-id route.
            response = client.get(f"{CBS_BASE}/nba/players/{player_id}/x/game-log/{int(season)}/")
        response.raise_for_status()
        return response.text


def _fetch_gamelog(player_id: str, slug: str, season: int) -> str:
    timeout = httpx.Timeout(12.0, connect=3.0)
    url = f"{CBS_BASE}/nba/players/{player_id}/{slug}/game-log/{int(season)}/"
    with httpx.Client(headers=CBS_HEADERS, timeout=timeout, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        return response.text


def load_cbs_profiles(
    slate_date: date,
    player_names: Sequence[str],
    *,
    team_codes: Sequence[str] | None = None,
    fetch_text: Callable[[str, str, int | None], str] | None = None,
    max_workers: int = 8,
) -> dict[str, dict[str, Any]]:
    wanted = {_norm(name): _clean(name) for name in player_names if _clean(name)}
    if not wanted:
        return {}
    codes = list(dict.fromkeys(_clean(code).upper() for code in (team_codes or TEAM_ROUTES) if _clean(code).upper() in TEAM_ROUTES))
    if not codes:
        return {}
    fetch_text = fetch_text or _default_fetch_text

    roster_rows: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(codes)))) as pool:
        jobs = {pool.submit(fetch_text, "roster", code, None): code for code in codes}
        for future in as_completed(jobs):
            code = jobs[future]
            try:
                parsed = parse_cbs_roster(future.result(), team=code)
            except Exception:
                continue
            for key, row in parsed.items():
                if key in wanted and key not in roster_rows:
                    roster_rows[key] = row
    if not roster_rows:
        return {}

    current_start_year = slate_date.year if slate_date.month >= 7 else slate_date.year - 1

    def history_job(key: str, row: Mapping[str, Any]) -> tuple[str, dict[str, Any] | None]:
        player_id = _clean((row.get("provider_ids") or {}).get("cbs_sports"))
        slug = _clean(row.get("provider_slug"))
        if not player_id or not slug:
            return key, None
        try:
            if fetch_text is _default_fetch_text:
                current_doc = _fetch_gamelog(player_id, slug, current_start_year)
            else:
                current_doc = fetch_text("gamelog", player_id, current_start_year)
            current = parse_cbs_gamelog(current_doc)
        except Exception:
            current = []
        prior: list[dict[str, Any]] = []
        # Stop once current-season history is sufficient; otherwise add one prior
        # season baseline. This controls latency and source usage.
        if len(current) < 8:
            try:
                if fetch_text is _default_fetch_text:
                    prior_doc = _fetch_gamelog(player_id, slug, current_start_year - 1)
                else:
                    prior_doc = fetch_text("gamelog", player_id, current_start_year - 1)
                prior = parse_cbs_gamelog(prior_doc)
            except Exception:
                prior = []
        if not current and not prior:
            return key, None
        profile = dict(row)
        profile.pop("provider_slug", None)
        profile["current_games"] = current
        profile["prior_games"] = prior
        profile["stats_source"] = "CBS Sports"
        profile["data_state"] = "VERIFIED"
        return key, profile

    out: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, len(roster_rows)))) as pool:
        jobs = {pool.submit(history_job, key, row): key for key, row in roster_rows.items()}
        for future in as_completed(jobs):
            try:
                key, profile = future.result()
            except Exception:
                continue
            if profile:
                out[key] = profile
    return out
