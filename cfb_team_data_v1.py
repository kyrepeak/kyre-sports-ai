"""College Football Team Data V1 — Step 3 team data foundation.

Official/free-source foundation built on top of frozen CFB Step 2 identity.

Primary season context
----------------------
- NCAA official FBS schedule GraphQL already certified in Step 2.
- Completed-game scores are used to derive:
  * W-L-T record
  * scoring offense/defense baseline (PPG / points allowed per game)
  * point differential
  * home/away/neutral splits
  * recent five-game form
  * opponent-win-percentage strength-of-schedule context

Official stat enrichment
------------------------
- NCAA.com FBS team-stat pages are discovered dynamically from the official
  stats selector, then matched to the selected teams.
- Current AP ranking is read from NCAA.com's Associated Press ranking table.
- If either HTML source is unavailable or changes shape, the module fails
  closed to schedule-derived evidence and marks the missing fields LIMITED.

This module intentionally contains no win probability, projected score,
sportsbook line, fair odds, pick ranking, Monte Carlo, or calibration math.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
import re
from typing import Any, Iterable, Mapping
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import requests
import streamlit as st

import cfb_schedule_v1 as schedule

MODEL_VERSION = "CFB TEAM DATA V1 • STEP 3 TEAM DATA FOUNDATION"

NCAA_STATS_INDEX = "https://www.ncaa.com/stats/football/fbs"
NCAA_AP_RANKINGS = "https://www.ncaa.com/rankings/football/fbs/associated-press"
NCAA_ROOT = "https://www.ncaa.com"

_TIMEOUT = 18
_USER_AGENT = "KyreSportsAI/CFB-Step3"

_CORE_STAT_PATTERNS = {
    "scoring_offense": ("scoring offense",),
    "total_offense": ("total offense",),
    "scoring_defense": ("scoring defense",),
    "total_defense": ("total defense",),
    "turnover_margin": ("turnover margin",),
}

_CORE_STAT_LABELS = {
    "scoring_offense": "NCAA Scoring Offense",
    "total_offense": "NCAA Total Offense",
    "scoring_defense": "NCAA Scoring Defense",
    "total_defense": "NCAA Total Defense",
    "turnover_margin": "NCAA Turnover Margin",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _float(value: Any) -> float | None:
    text = _clean(value).replace(",", "").replace("%", "")
    if not text or text.upper() in {"N/A", "NA", "-", "—", "TBD"}:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _int(value: Any) -> int | None:
    number = _float(value)
    if number is None:
        return None
    try:
        return int(number)
    except Exception:
        return None


def _canonical_name(value: Any) -> str:
    text = _clean(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"\buniversity\b", "", text)
    text = re.sub(r"\bthe\b", "", text)
    text = re.sub(r"\bst\.?\b", "state", text)
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def _team_keys(name: Any, slug: Any = "") -> set[str]:
    raw_name = _clean(name)
    raw_slug = _clean(slug).replace("-", " ")
    keys = {_canonical_name(raw_name), _canonical_name(raw_slug)}

    # NCAA tables occasionally abbreviate "State" as "St." while schedule
    # identity uses the expanded form. Keep both deterministic variants.
    for raw in (raw_name, raw_slug):
        lower = raw.lower()
        if " state" in lower:
            keys.add(_canonical_name(re.sub(r"\bstate\b", "st", lower)))
        if re.search(r"\bst\.?\b", lower):
            keys.add(_canonical_name(re.sub(r"\bst\.?\b", "state", lower)))
    return {key for key in keys if key}


def _fetch_text_requests(url: str) -> tuple[str, dict[str, Any]]:
    r = requests.get(
        url,
        timeout=_TIMEOUT,
        headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )
    meta = {
        "transport": "requests",
        "http": int(r.status_code),
        "bytes": len(r.content or b""),
    }
    r.raise_for_status()
    return r.text, meta


def _fetch_text_urllib(url: str) -> tuple[str, dict[str, Any]]:
    req = Request(
        url,
        headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Cache-Control": "no-cache",
        },
    )
    with urlopen(req, timeout=_TIMEOUT) as response:
        raw = response.read()
        return raw.decode("utf-8", errors="replace"), {
            "transport": "urllib",
            "http": int(getattr(response, "status", 200)),
            "bytes": len(raw),
        }


def _fetch_text_with_fallback(url: str, provider: str) -> tuple[str, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    for transport, fn in (("requests", _fetch_text_requests), ("urllib", _fetch_text_urllib)):
        try:
            text, meta = fn(url)
            attempts.append(
                {
                    "provider": provider,
                    "transport": transport,
                    "http": meta.get("http"),
                    "bytes": meta.get("bytes"),
                    "error": "",
                }
            )
            return text, attempts
        except Exception as exc:
            attempts.append(
                {
                    "provider": provider,
                    "transport": transport,
                    "http": None,
                    "bytes": 0,
                    "error": f"{type(exc).__name__}: {exc}"[:260],
                }
            )
    return "", attempts


class _OptionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._value = ""
        self._parts: list[str] = []
        self._in_option = False
        self.options: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "option":
            return
        self._in_option = True
        self._parts = []
        self._value = dict(attrs).get("value") or ""

    def handle_data(self, data: str) -> None:
        if self._in_option:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "option" or not self._in_option:
            return
        label = _clean(" ".join(self._parts))
        value = _clean(self._value)
        if "/stats/football/fbs/" in value and "/team/" in value and label:
            self.options.append((label, value))
        self._in_option = False
        self._parts = []
        self._value = ""


class _TableParser(HTMLParser):
    """Small dependency-free HTML table parser for NCAA stat/ranking tables."""

    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.cell_tag = ""
        self.cell_parts: list[str] = []
        self.current: list[tuple[str, str]] = []
        self.rows: list[list[tuple[str, str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.in_row = True
            self.current = []
        elif self.in_row and tag in {"th", "td"}:
            self.in_cell = True
            self.cell_tag = tag
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.in_cell and tag == self.cell_tag:
            self.current.append((self.cell_tag, _clean(" ".join(self.cell_parts))))
            self.in_cell = False
            self.cell_tag = ""
            self.cell_parts = []
        elif self.in_row and tag == "tr":
            if self.current:
                self.rows.append(self.current)
            self.in_row = False
            self.current = []
        elif tag == "table":
            self.in_table = False


@dataclass(frozen=True)
class TeamGame:
    date: str
    opponent: str
    opponent_slug: str
    location: str
    points_for: int
    points_against: int
    result: str
    margin: int


def _completed(contest: Mapping[str, Any]) -> bool:
    state = _clean(contest.get("gameState")).upper()
    message = _clean(contest.get("finalMessage")).lower()
    return state == "F" or message.startswith("final")


def _team_score(team: Mapping[str, Any]) -> int | None:
    for key in ("score", "points", "teamScore"):
        score = _int(team.get(key))
        if score is not None:
            return score
    return None


def _team_meta(team: Mapping[str, Any]) -> dict[str, Any]:
    name = _clean(
        team.get("nameShort")
        or team.get("name6Char")
        or team.get("displayName")
        or team.get("name")
    )
    slug = _clean(team.get("seoname") or team.get("seoName") or "").strip()
    if not slug:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return {
        "name": name,
        "slug": slug,
        "conference": _clean(
            team.get("conferenceSeo")
            or team.get("conference")
            or team.get("conferenceName")
        )
        or "Conference unavailable",
        "rank": _int(team.get("teamRank")),
        "score": _team_score(team),
        "winner": bool(team.get("isWinner")),
    }


def _contest_teams(contest: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]] | None:
    home = None
    away = None
    for team in contest.get("teams") or []:
        if not isinstance(team, dict):
            continue
        if bool(team.get("isHome")):
            home = _team_meta(team)
        else:
            away = _team_meta(team)
    if not home or not away:
        return None
    return away, home


def _season_games_from_payload(
    payload: Mapping[str, Any],
    as_of_day: str,
) -> tuple[dict[str, list[TeamGame]], dict[str, dict[str, Any]], dict[str, Any]]:
    """Build completed-game ledgers for every team in the NCAA FBS schedule payload."""
    day = schedule._day(as_of_day)
    ledgers: dict[str, list[TeamGame]] = {}
    meta: dict[str, dict[str, Any]] = {}
    raw = 0
    completed = 0
    ignored_future = 0
    ignored_unscored = 0

    for contest in schedule._walk_contests(payload):
        raw += 1
        dt = schedule._contest_datetime(contest)
        if dt is None:
            continue
        contest_day = dt.astimezone(schedule._ET).date().isoformat()
        if contest_day > day:
            ignored_future += 1
            continue
        if not _completed(contest):
            continue

        pair = _contest_teams(contest)
        if pair is None:
            continue
        away, home = pair
        if away["score"] is None or home["score"] is None:
            ignored_unscored += 1
            continue

        completed += 1
        neutral = bool(contest.get("neutralSite") or contest.get("isNeutralSite"))
        for side, team, opp in (("away", away, home), ("home", home, away)):
            if team["score"] > opp["score"]:
                result = "W"
            elif team["score"] < opp["score"]:
                result = "L"
            else:
                result = "T"
            location = "neutral" if neutral else side
            key = _canonical_name(team["slug"] or team["name"])
            if not key:
                continue
            ledgers.setdefault(key, []).append(
                TeamGame(
                    date=contest_day,
                    opponent=opp["name"],
                    opponent_slug=opp["slug"],
                    location=location,
                    points_for=int(team["score"]),
                    points_against=int(opp["score"]),
                    result=result,
                    margin=int(team["score"]) - int(opp["score"]),
                )
            )
            current = meta.setdefault(
                key,
                {
                    "team": team["name"],
                    "team_slug": team["slug"],
                    "conference": team["conference"],
                    "schedule_rank": team["rank"],
                },
            )
            if team.get("conference") and team["conference"] != "Conference unavailable":
                current["conference"] = team["conference"]
            if team.get("rank") is not None:
                current["schedule_rank"] = team["rank"]

    for games in ledgers.values():
        games.sort(key=lambda g: g.date)

    return ledgers, meta, {
        "raw_contests": raw,
        "completed_contests": completed,
        "future_contests_ignored": ignored_future,
        "unscored_finals_ignored": ignored_unscored,
    }


def _record(games: Iterable[TeamGame]) -> dict[str, int]:
    rows = list(games)
    return {
        "wins": sum(g.result == "W" for g in rows),
        "losses": sum(g.result == "L" for g in rows),
        "ties": sum(g.result == "T" for g in rows),
        "games": len(rows),
    }


def _record_text(record: Mapping[str, Any]) -> str:
    wins = int(record.get("wins") or 0)
    losses = int(record.get("losses") or 0)
    ties = int(record.get("ties") or 0)
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def _win_pct(record: Mapping[str, Any]) -> float | None:
    games = int(record.get("games") or 0)
    if games <= 0:
        return None
    return (float(record.get("wins") or 0) + 0.5 * float(record.get("ties") or 0)) / games


def _split_record(games: Iterable[TeamGame], location: str) -> dict[str, int]:
    return _record(g for g in games if g.location == location)


def _mean(values: Iterable[float | int]) -> float | None:
    rows = [float(v) for v in values]
    if not rows:
        return None
    return sum(rows) / len(rows)


def _schedule_foundation(
    key: str,
    ledgers: Mapping[str, list[TeamGame]],
) -> dict[str, Any]:
    games = list(ledgers.get(key) or [])
    record = _record(games)
    recent = games[-5:]
    points_for = sum(g.points_for for g in games)
    points_against = sum(g.points_against for g in games)
    n = len(games)

    opponent_pcts: list[float] = []
    opponent_games_known = 0
    for game in games:
        opp_key = _canonical_name(game.opponent_slug or game.opponent)
        opp_record = _record(ledgers.get(opp_key) or [])
        pct = _win_pct(opp_record)
        if pct is not None:
            opponent_pcts.append(pct)
            opponent_games_known += 1

    return {
        "record": record,
        "record_text": _record_text(record),
        "ppg": (points_for / n) if n else None,
        "points_allowed_pg": (points_against / n) if n else None,
        "point_diff_pg": ((points_for - points_against) / n) if n else None,
        "home_record": _split_record(games, "home"),
        "away_record": _split_record(games, "away"),
        "neutral_record": _split_record(games, "neutral"),
        "recent_form": "".join(g.result for g in recent) or "—",
        "recent_record": _record(recent),
        "recent_ppg": _mean(g.points_for for g in recent),
        "recent_points_allowed_pg": _mean(g.points_against for g in recent),
        "recent_point_diff_pg": _mean(g.margin for g in recent),
        "sos_opponent_win_pct": _mean(opponent_pcts),
        "sos_coverage": (opponent_games_known / n) if n else 0.0,
        "completed_games": [
            {
                "date": g.date,
                "opponent": g.opponent,
                "location": g.location,
                "result": g.result,
                "score": f"{g.points_for}-{g.points_against}",
                "margin": g.margin,
            }
            for g in games
        ],
    }


def _discover_stat_categories(html: str) -> dict[str, dict[str, str]]:
    parser = _OptionParser()
    parser.feed(html or "")
    discovered = parser.options
    out: dict[str, dict[str, str]] = {}
    for metric, patterns in _CORE_STAT_PATTERNS.items():
        for label, path in discovered:
            lower = label.lower()
            if all(part in lower for part in patterns[0].split()):
                out[metric] = {
                    "label": label,
                    "url": urljoin(NCAA_ROOT, path),
                }
                break
    return out


def _table_rows(html: str) -> tuple[list[str], list[list[str]]]:
    parser = _TableParser()
    parser.feed(html or "")
    headers: list[str] = []
    data: list[list[str]] = []
    for row in parser.rows:
        kinds = [kind for kind, _ in row]
        cells = [text for _, text in row]
        if "th" in kinds and not headers:
            headers = cells
        elif "td" in kinds:
            data.append(cells)
    return headers, data


def _team_cell_index(headers: list[str], rows: list[list[str]]) -> int:
    for i, header in enumerate(headers):
        h = header.lower()
        if "team" in h or "school" in h:
            return i
    # NCAA team-stat tables are normally Rank | Team | ...
    if rows and len(rows[0]) >= 2:
        return 1
    return 0


def _stat_page_values(
    html: str,
    targets: Mapping[str, set[str]],
) -> dict[str, dict[str, Any]]:
    headers, rows = _table_rows(html)
    if not rows:
        return {}
    team_idx = _team_cell_index(headers, rows)
    out: dict[str, dict[str, Any]] = {}
    for cells in rows:
        if team_idx >= len(cells):
            continue
        team_text = cells[team_idx]
        key = _canonical_name(team_text)
        if not key:
            continue
        matched_target = None
        for target, keys in targets.items():
            if key in keys or any(
                len(key) >= 5 and len(candidate) >= 5 and (key in candidate or candidate in key)
                for candidate in keys
            ):
                matched_target = target
                break
        if matched_target is None:
            continue
        value = cells[-1] if cells else ""
        out[matched_target] = {
            "team_text": team_text,
            "value": _clean(value),
            "value_numeric": _float(value),
            "headers": list(headers),
            "row": list(cells),
        }
    return out


def _max_stat_pages(html: str) -> int:
    pages = [1]
    for match in re.finditer(r"/p(\d+)(?:[\"'/?#]|$)", html or ""):
        try:
            pages.append(int(match.group(1)))
        except Exception:
            pass
    return max(1, min(max(pages), 12))


def _fetch_stat_metric(
    metric: str,
    cfg: Mapping[str, str],
    targets: Mapping[str, set[str]],
) -> tuple[str, dict[str, dict[str, Any]], list[dict[str, Any]]]:
    url = str(cfg.get("url") or "")
    attempts: list[dict[str, Any]] = []
    if not url:
        return metric, {}, attempts

    first, first_attempts = _fetch_text_with_fallback(url, f"NCAA {cfg.get('label') or metric}")
    attempts.extend(first_attempts)
    if not first:
        return metric, {}, attempts

    found = _stat_page_values(first, targets)
    max_pages = _max_stat_pages(first)

    # Fetch only until both selected teams are found.
    for page in range(2, max_pages + 1):
        if len(found) >= len(targets):
            break
        page_url = url.rstrip("/") + f"/p{page}"
        html, page_attempts = _fetch_text_with_fallback(
            page_url, f"NCAA {cfg.get('label') or metric} p{page}"
        )
        attempts.extend(page_attempts)
        if not html:
            continue
        found.update(_stat_page_values(html, targets))

    return metric, found, attempts


@st.cache_data(ttl=300, show_spinner=False)
def _load_official_stats(
    away_name: str,
    away_slug: str,
    home_name: str,
    home_slug: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    targets = {
        "away": _team_keys(away_name, away_slug),
        "home": _team_keys(home_name, home_slug),
    }
    attempts: list[dict[str, Any]] = []

    index_html, index_attempts = _fetch_text_with_fallback(
        NCAA_STATS_INDEX, "NCAA FBS stats category index"
    )
    attempts.extend(index_attempts)
    categories = _discover_stat_categories(index_html) if index_html else {}

    values = {
        "away": {},
        "home": {},
    }
    if categories:
        max_workers = min(5, len(categories))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(_fetch_stat_metric, metric, cfg, targets)
                for metric, cfg in categories.items()
            ]
            for future in as_completed(futures):
                metric, found, metric_attempts = future.result()
                attempts.extend(metric_attempts)
                label = _CORE_STAT_LABELS.get(metric, metric)
                for side, item in found.items():
                    values[side][metric] = {
                        "label": label,
                        **item,
                    }

    return values, {
        "categories_discovered": sorted(categories),
        "metrics_requested": sorted(_CORE_STAT_PATTERNS),
        "away_metrics_found": len(values["away"]),
        "home_metrics_found": len(values["home"]),
        "attempts": attempts,
    }


@st.cache_data(ttl=300, show_spinner=False)
def _load_ap_rankings() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    html, attempts = _fetch_text_with_fallback(NCAA_AP_RANKINGS, "NCAA AP rankings")
    headers, rows = _table_rows(html) if html else ([], [])
    rankings: dict[str, dict[str, Any]] = {}
    if rows:
        team_idx = _team_cell_index(headers, rows)
        rank_idx = 0
        for i, header in enumerate(headers):
            if "rank" in header.lower():
                rank_idx = i
                break
        for cells in rows:
            if team_idx >= len(cells):
                continue
            team = _clean(cells[team_idx])
            rank = _int(cells[rank_idx]) if rank_idx < len(cells) else None
            if not team or rank is None:
                continue
            rankings[_canonical_name(team)] = {
                "rank": rank,
                "team_text": team,
                "row": cells,
                "headers": headers,
            }
    return rankings, {
        "rows": len(rankings),
        "attempts": attempts,
    }


def _ranking_for_team(
    rankings: Mapping[str, Mapping[str, Any]],
    name: str,
    slug: str,
) -> dict[str, Any] | None:
    keys = _team_keys(name, slug)
    for key, value in rankings.items():
        if key in keys:
            return dict(value)
    for key, value in rankings.items():
        if any(
            len(key) >= 5 and len(candidate) >= 5 and (key in candidate or candidate in key)
            for candidate in keys
        ):
            return dict(value)
    return None


def _quality(profile: Mapping[str, Any]) -> dict[str, Any]:
    games = int((profile.get("record") or {}).get("games") or 0)
    stat_count = len(profile.get("official_stats") or {})
    sos_coverage = float(profile.get("sos_coverage") or 0.0)
    ranking_known = profile.get("ap_rank") is not None

    components = {
        "record": games > 0,
        "scoring_baseline": profile.get("ppg") is not None
        and profile.get("points_allowed_pg") is not None,
        "recent_form": games > 0 and profile.get("recent_form") not in {None, "", "—"},
        "home_away_splits": games > 0,
        "sos": games > 0 and sos_coverage >= 0.5,
        "official_stats": stat_count >= 2,
        "ranking": ranking_known,
    }
    passed = sum(bool(v) for v in components.values())
    score = passed / len(components)

    if games <= 0:
        grade = "CHECK"
    elif score >= 0.72:
        grade = "READY"
    else:
        grade = "LIMITED"

    return {
        "grade": grade,
        "score": score,
        "components": components,
        "sample_games": games,
        "official_stat_count": stat_count,
        "sos_coverage": sos_coverage,
    }


def _resolve_key(
    ledgers: Mapping[str, list[TeamGame]],
    meta: Mapping[str, Mapping[str, Any]],
    name: str,
    slug: str,
) -> str:
    candidates = _team_keys(name, slug)
    for key in ledgers:
        if key in candidates:
            return key
    for key, info in meta.items():
        info_keys = _team_keys(info.get("team"), info.get("team_slug"))
        if info_keys & candidates:
            return key
    # Do not invent a fake profile; return deterministic canonical identity.
    return _canonical_name(slug or name)


def _build_profile(
    side: str,
    game: Mapping[str, Any],
    ledgers: Mapping[str, list[TeamGame]],
    meta: Mapping[str, Mapping[str, Any]],
    official_stats: Mapping[str, Mapping[str, Any]],
    rankings: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    name = _clean(game.get(f"{side}_team"))
    slug = _clean(game.get(f"{side}_team_slug"))
    key = _resolve_key(ledgers, meta, name, slug)
    foundation = _schedule_foundation(key, ledgers)
    info = dict(meta.get(key) or {})

    ranking = _ranking_for_team(rankings, name, slug)
    schedule_rank = _int(game.get(f"{side}_rank"))
    ap_rank = _int((ranking or {}).get("rank"))
    if ap_rank is None:
        ap_rank = schedule_rank

    profile = {
        "side": side,
        "team": name,
        "team_slug": slug,
        "conference": _clean(
            game.get(f"{side}_conference")
            or info.get("conference")
        )
        or "Conference unavailable",
        "schedule_rank": schedule_rank,
        "ap_rank": ap_rank,
        "rank_source": "NCAA AP rankings" if ranking else (
            "NCAA schedule rank snapshot" if schedule_rank is not None else "unranked / unavailable"
        ),
        "official_stats": dict(official_stats.get(side) or {}),
        "data_source": "NCAA official FBS schedule + NCAA.com team stats/AP rankings",
        **foundation,
    }
    profile["data_quality"] = _quality(profile)
    return profile


@st.cache_data(ttl=300, show_spinner=False)
def load_matchup_team_data(
    game: Mapping[str, Any],
    as_of_day: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return Step 3 team foundations for the two Step 2 verified teams."""
    day = schedule._day(as_of_day)
    season_year = schedule._season_year(day)
    attempts: list[dict[str, Any]] = []

    raw_payload, schedule_attempts = schedule._fetch_json_with_fallback(
        schedule.NCAA_SCHEDULE_URL,
        schedule._ncaa_params(season_year),
        "NCAA official season schedule for Step 3",
    )
    attempts.extend(schedule_attempts)

    if raw_payload:
        ledgers, meta, ledger_diag = _season_games_from_payload(raw_payload, day)
    else:
        ledgers, meta, ledger_diag = {}, {}, {
            "raw_contests": 0,
            "completed_contests": 0,
            "future_contests_ignored": 0,
            "unscored_finals_ignored": 0,
        }

    stats, stats_diag = _load_official_stats(
        _clean(game.get("away_team")),
        _clean(game.get("away_team_slug")),
        _clean(game.get("home_team")),
        _clean(game.get("home_team_slug")),
    )
    attempts.extend(stats_diag.get("attempts") or [])

    rankings, rank_diag = _load_ap_rankings()
    attempts.extend(rank_diag.get("attempts") or [])

    away = _build_profile("away", game, ledgers, meta, stats, rankings)
    home = _build_profile("home", game, ledgers, meta, stats, rankings)

    ready_sides = sum(
        (away.get("data_quality") or {}).get("grade") == "READY",
    ) + sum(
        [(home.get("data_quality") or {}).get("grade") == "READY"]
    )

    diag = {
        "version": MODEL_VERSION,
        "date": day,
        "season_year": season_year,
        "team_profiles": 2,
        "ready_profiles": ready_sides,
        "schedule_source": "NCAA official FBS schedule GraphQL" if raw_payload else "unavailable",
        "stats_source": "NCAA.com FBS team stats" if (
            stats_diag.get("away_metrics_found") or stats_diag.get("home_metrics_found")
        ) else "unavailable",
        "ranking_source": "NCAA.com AP rankings" if rank_diag.get("rows") else "unavailable",
        "stats_categories_discovered": stats_diag.get("categories_discovered") or [],
        "away_metrics_found": stats_diag.get("away_metrics_found") or 0,
        "home_metrics_found": stats_diag.get("home_metrics_found") or 0,
        "ranking_rows": rank_diag.get("rows") or 0,
        "attempts": attempts,
        **ledger_diag,
    }
    return {"away": away, "home": home}, diag


def clear_team_data_cache() -> None:
    for fn in (_load_official_stats, _load_ap_rankings, load_matchup_team_data):
        try:
            fn.clear()
        except Exception:
            pass


__all__ = [
    "MODEL_VERSION",
    "NCAA_AP_RANKINGS",
    "NCAA_STATS_INDEX",
    "_canonical_name",
    "_discover_stat_categories",
    "_quality",
    "_record_text",
    "_season_games_from_payload",
    "_stat_page_values",
    "_table_rows",
    "clear_team_data_cache",
    "load_matchup_team_data",
]
