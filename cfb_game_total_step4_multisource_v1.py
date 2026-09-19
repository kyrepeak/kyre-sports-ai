"""CFB Game Total Step 4 multi-source display fallback V1.

Presentation-only data recovery for Step 4. NCAA remains the primary matchup
source. When a visible Step 4 dimension is missing, this adapter can read the
same current-season team facts from cfbstats.com.

Important boundaries:
- display evidence only; never mutates matchup-engine/model math,
- no sportsbook or market input,
- no projection/probability/distribution changes,
- missing/ambiguous teams fail closed,
- values are only used to fill a tile that the certified NCAA engine left blank.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from typing import Any, Mapping
from urllib.parse import urljoin
from urllib.request import Request, urlopen

import requests
import streamlit as st

MODEL_VERSION = "CFB GAME TOTAL STEP4 MULTISOURCE V1 • CFBSTATS DISPLAY FALLBACK"
SOURCE = "cfbstats.com"
ROOT = "https://cfbstats.com"
TIMEOUT_SECONDS = 7
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_DIMENSION_KEYS = {
    "passing": ("pass_yards_pg", "pass_yards_allowed_pg", "yds/g"),
    "rushing": ("rush_yards_pg", "rush_yards_allowed_pg", "yds/g"),
    "third_down": ("third_down_offense_pct", "third_down_defense_pct", "%"),
    "red_zone": ("red_zone_offense_pct", "red_zone_defense_pct", "%"),
    "sack_pressure": ("sacks_allowed_pg", "team_sacks_pg", "sacks/g"),
    "turnovers": ("turnovers_lost_pg", "turnovers_gained_pg", "turnovers/g"),
}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _float(value: Any) -> float | None:
    text = _clean(value).replace(",", "").replace("%", "")
    if not text or text in {"-", "—"}:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except Exception:
        return None


def _numbers(value: Any) -> list[float]:
    return [
        float(item)
        for item in re.findall(r"\d+(?:\.\d+)?", _clean(value).replace(",", ""))
    ]


def _key(value: Any) -> str:
    text = _clean(value).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"\buniversity\b", " ", text)
    text = re.sub(r"\bthe\b", " ", text)
    text = re.sub(r"\bst\.?\b", " state ", text)
    return re.sub(r"[^a-z0-9]+", "", text)


def _season(game: Mapping[str, Any] | None) -> int:
    game = game or {}
    for raw in (
        game.get("game_date"),
        game.get("kickoff_iso"),
        game.get("date"),
    ):
        text = _clean(raw)
        match = re.match(r"(20\d{2})", text)
        if match:
            return int(match.group(1))
    return datetime.now(timezone.utc).year


def _fetch_requests(url: str) -> str:
    response = requests.get(
        url,
        timeout=TIMEOUT_SECONDS,
        headers={
            "User-Agent": "KyreSportsAI-Step4-Multisource/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    response.raise_for_status()
    return response.text


def _fetch_urllib(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "KyreSportsAI-Step4-Multisource/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return response.read().decode("utf-8", errors="replace")


def _fetch_text(url: str) -> tuple[str, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    for name, fn in (("requests", _fetch_requests), ("urllib", _fetch_urllib)):
        try:
            text = fn(url)
            attempts.append(
                {
                    "source": SOURCE,
                    "transport": name,
                    "url": url,
                    "ok": bool(text),
                    "error": "",
                }
            )
            if text:
                return text, attempts
        except Exception as exc:
            attempts.append(
                {
                    "source": SOURCE,
                    "transport": name,
                    "url": url,
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}"[:260],
                }
            )
    return "", attempts


class _DirectoryParser(HTMLParser):
    def __init__(self, season: int) -> None:
        super().__init__()
        self.season = int(season)
        self.href = ""
        self.parts: list[str] = []
        self.in_link = False
        self.rows: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href") or ""
        if (
            re.search(rf"(?:/|^){self.season}/team/\d+/index\.html$", href)
            or re.search(r"(?:^|/)\d+/index\.html$", href)
        ):
            self.in_link = True
            self.href = href
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.in_link:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self.in_link:
            return
        name = _clean(" ".join(self.parts))
        match = (
            re.search(r"/team/(\d+)/index\.html$", self.href)
            or re.search(r"(?:^|/)(\d+)/index\.html$", self.href)
        )
        if name and match:
            self.rows.append((name, match.group(1)))
        self.in_link = False
        self.href = ""
        self.parts = []


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_row = False
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.current: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.in_row = True
            self.current = []
        elif self.in_row and tag in {"td", "th"}:
            self.in_cell = True
            self.cell_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.in_cell and tag in {"td", "th"}:
            self.current.append(_clean(" ".join(self.cell_parts)))
            self.in_cell = False
            self.cell_parts = []
        elif self.in_row and tag == "tr":
            if self.current:
                self.rows.append(list(self.current))
            self.in_row = False
            self.current = []
        elif tag == "table":
            self.in_table = False


def _parse_directory(html: str, season: int) -> dict[str, dict[str, str]]:
    parser = _DirectoryParser(season)
    parser.feed(html or "")
    out: dict[str, dict[str, str]] = {}
    for name, team_id in parser.rows:
        key = _key(name)
        if key and key not in out:
            out[key] = {"team": name, "team_id": team_id}
    return out


def _table_rows(html: str) -> list[list[str]]:
    parser = _TableParser()
    parser.feed(html or "")
    return parser.rows


def _team_stat_map(html: str) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for row in _table_rows(html):
        if len(row) < 3:
            continue
        label = _clean(row[0])
        if ":" not in label:
            continue
        out[label] = (_clean(row[1]), _clean(row[2]))
    return out


def _sack_rows(html: str) -> tuple[dict[str, float], dict[str, float]]:
    total: dict[str, float] = {}
    opponents: dict[str, float] = {}
    for row in _table_rows(html):
        lowered = [_clean(cell).lower() for cell in row]
        if "total" in lowered:
            idx = lowered.index("total")
            nums = []
            for cell in row[idx + 1 :]:
                nums.extend(_numbers(cell))
            if len(nums) >= 4:
                total = {
                    "games": nums[0],
                    "sacks": nums[1],
                    "sacks_pg": nums[-1],
                }
        elif "opponents" in lowered:
            idx = lowered.index("opponents")
            nums = []
            for cell in row[idx + 1 :]:
                nums.extend(_numbers(cell))
            if len(nums) >= 4:
                opponents = {
                    "games": nums[0],
                    "sacks": nums[1],
                    "sacks_pg": nums[-1],
                }
    return total, opponents


def _pick_pair(stats: Mapping[str, tuple[str, str]], label: str) -> tuple[str, str]:
    pair = stats.get(label) or ("", "")
    return _clean(pair[0]), _clean(pair[1])


def _parse_team_metrics(team_html: str, sack_html: str) -> dict[str, Any]:
    stats = _team_stat_map(team_html)
    games_team, games_opp = _pick_pair(stats, "Scoring: Games - Points")
    game_nums = _numbers(games_team)
    opp_game_nums = _numbers(games_opp)
    games = int(game_nums[0]) if game_nums else 0
    opp_games = int(opp_game_nums[0]) if opp_game_nums else games

    rush_team, rush_opp = _pick_pair(stats, "Rushing: Attempts - Yards - TD")
    pass_team, pass_opp = _pick_pair(stats, "Passing: Yards")
    pass_line_team, pass_line_opp = _pick_pair(
        stats,
        "Passing: Attempts - Completions - Interceptions - TD",
    )
    fumble_team, fumble_opp = _pick_pair(stats, "Fumbles: Number - Lost")
    third_team, third_opp = _pick_pair(stats, "3rd Down Conversions: Conversion %")
    red_team, red_opp = _pick_pair(stats, "Red Zone: Success %")

    rush_team_nums = _numbers(rush_team)
    rush_opp_nums = _numbers(rush_opp)
    pass_team_nums = _numbers(pass_team)
    pass_opp_nums = _numbers(pass_opp)
    pass_line_team_nums = _numbers(pass_line_team)
    pass_line_opp_nums = _numbers(pass_line_opp)
    fumble_team_nums = _numbers(fumble_team)
    fumble_opp_nums = _numbers(fumble_opp)

    team_interceptions_thrown = (
        pass_line_team_nums[2] if len(pass_line_team_nums) >= 3 else None
    )
    opp_interceptions_thrown = (
        pass_line_opp_nums[2] if len(pass_line_opp_nums) >= 3 else None
    )
    team_fumbles_lost = (
        fumble_team_nums[1] if len(fumble_team_nums) >= 2 else None
    )
    opp_fumbles_lost = (
        fumble_opp_nums[1] if len(fumble_opp_nums) >= 2 else None
    )

    sack_total, sack_opponents = _sack_rows(sack_html)

    def per_game(value: float | None, count: int) -> float | None:
        if value is None or count <= 0:
            return None
        return float(value) / float(count)

    rush_yards = rush_team_nums[1] if len(rush_team_nums) >= 2 else None
    rush_yards_allowed = rush_opp_nums[1] if len(rush_opp_nums) >= 2 else None
    pass_yards = pass_team_nums[0] if pass_team_nums else None
    pass_yards_allowed = pass_opp_nums[0] if pass_opp_nums else None

    turnovers_lost = None
    if team_interceptions_thrown is not None and team_fumbles_lost is not None:
        turnovers_lost = team_interceptions_thrown + team_fumbles_lost

    turnovers_gained = None
    if opp_interceptions_thrown is not None and opp_fumbles_lost is not None:
        turnovers_gained = opp_interceptions_thrown + opp_fumbles_lost

    return {
        "games": games,
        "pass_yards_pg": per_game(pass_yards, games),
        "pass_yards_allowed_pg": per_game(pass_yards_allowed, opp_games),
        "rush_yards_pg": per_game(rush_yards, games),
        "rush_yards_allowed_pg": per_game(rush_yards_allowed, opp_games),
        "third_down_offense_pct": _float(third_team),
        "third_down_defense_pct": _float(third_opp),
        "red_zone_offense_pct": _float(red_team),
        "red_zone_defense_pct": _float(red_opp),
        "team_sacks_pg": _float(sack_total.get("sacks_pg")),
        "sacks_allowed_pg": _float(sack_opponents.get("sacks_pg")),
        "turnovers_lost_pg": per_game(turnovers_lost, games),
        "turnovers_gained_pg": per_game(turnovers_gained, opp_games),
        "source": SOURCE,
    }


@st.cache_data(ttl=900, show_spinner=False)
def _load_directory(season: int) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    url = f"{ROOT}/{int(season)}/team/index.html"
    html, attempts = _fetch_text(url)
    return _parse_directory(html, season), {
        "url": url,
        "attempts": attempts,
        "rows": len(_parse_directory(html, season)),
    }


def _resolve_team(
    directory: Mapping[str, Mapping[str, str]],
    profile: Mapping[str, Any],
) -> dict[str, str]:
    candidates = []
    for raw in (
        profile.get("team"),
        profile.get("name"),
        profile.get("team_name"),
        profile.get("team_slug"),
    ):
        key = _key(raw)
        if key:
            candidates.append(key)

    for key in candidates:
        if key in directory:
            return dict(directory[key])

    matches: list[dict[str, str]] = []
    for directory_key, item in directory.items():
        for candidate in candidates:
            if (
                len(candidate) >= 6
                and len(directory_key) >= 6
                and (candidate in directory_key or directory_key in candidate)
            ):
                matches.append(dict(item))
                break

    unique = {
        str(item.get("team_id") or ""): item
        for item in matches
        if str(item.get("team_id") or "")
    }
    return dict(next(iter(unique.values()))) if len(unique) == 1 else {}


@st.cache_data(ttl=900, show_spinner=False)
def _load_team_metrics(
    season: int,
    team_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = f"{ROOT}/{int(season)}/team/{team_id}"
    team_url = f"{base}/index.html"
    sack_url = f"{base}/sack/index.html"
    with ThreadPoolExecutor(max_workers=2) as pool:
        team_future = pool.submit(_fetch_text, team_url)
        sack_future = pool.submit(_fetch_text, sack_url)
        team_html, team_attempts = team_future.result()
        sack_html, sack_attempts = sack_future.result()
    metrics = _parse_team_metrics(team_html, sack_html) if team_html else {}
    if metrics:
        metrics["team_id"] = str(team_id)
        metrics["source_url"] = team_url
    return metrics, {
        "team_url": team_url,
        "sack_url": sack_url,
        "attempts": [*team_attempts, *sack_attempts],
    }


def _fmt(value: Any, unit: str) -> str:
    number = _float(value)
    if number is None:
        return ""
    if unit == "%":
        return f"{number:.1f}%"
    if unit == "yds/g":
        return f"{number:.1f}"
    if unit == "sacks/g":
        return f"{number:.2f}/g"
    if unit == "turnovers/g":
        return f"{number:.2f}/g"
    return f"{number:.1f}"


def _fallback_dimensions(
    offense: Mapping[str, Any],
    defense: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key, (offense_key, defense_key, unit) in _DIMENSION_KEYS.items():
        off = _float(offense.get(offense_key))
        deff = _float(defense.get(defense_key))
        out[key] = {
            "ready": bool(off is not None and deff is not None),
            "edge": None,
            "offense_rank": None,
            "defense_rank": None,
            "offense_value": _fmt(off, unit),
            "defense_value": _fmt(deff, unit),
            "source": SOURCE,
            "display_fallback": True,
        }
    return out


def build_display_fallback(
    game: Mapping[str, Any] | None,
    away: Mapping[str, Any] | None,
    home: Mapping[str, Any] | None,
) -> dict[str, Any]:
    season = _season(game)
    away = away or {}
    home = home or {}

    directory, directory_diag = _load_directory(season)
    away_ref = _resolve_team(directory, away)
    home_ref = _resolve_team(directory, home)
    if not away_ref or not home_ref:
        return {
            "ready": False,
            "source": SOURCE,
            "season": season,
            "reason": "cfbstats team identity did not resolve uniquely",
            "away_offense": {},
            "home_offense": {},
            "diagnostics": {
                "directory": directory_diag,
                "away_ref": away_ref,
                "home_ref": home_ref,
            },
        }

    with ThreadPoolExecutor(max_workers=2) as pool:
        away_future = pool.submit(
            _load_team_metrics,
            season,
            str(away_ref["team_id"]),
        )
        home_future = pool.submit(
            _load_team_metrics,
            season,
            str(home_ref["team_id"]),
        )
        away_result = away_future.result()
        home_result = home_future.result()

    away_metrics, away_diag = away_result
    home_metrics, home_diag = home_result
    ready = bool(away_metrics and home_metrics)

    return {
        "ready": ready,
        "source": SOURCE,
        "season": season,
        "reason": "" if ready else "cfbstats team metrics incomplete",
        "away_team_id": str(away_ref.get("team_id") or ""),
        "home_team_id": str(home_ref.get("team_id") or ""),
        "away_metrics": away_metrics,
        "home_metrics": home_metrics,
        "away_offense": {
            "dimensions": _fallback_dimensions(away_metrics, home_metrics)
        } if ready else {},
        "home_offense": {
            "dimensions": _fallback_dimensions(home_metrics, away_metrics)
        } if ready else {},
        "diagnostics": {
            "directory": directory_diag,
            "away": away_diag,
            "home": home_diag,
        },
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
    }


def merge_missing_dimensions(
    engine: Mapping[str, Any] | None,
    fallback: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], int]:
    out = dict(engine or {})
    filled = 0
    fallback = fallback or {}

    for side in ("away_offense", "home_offense"):
        engine_side = dict(out.get(side) or {})
        engine_dims = dict(engine_side.get("dimensions") or {})
        fallback_side = fallback.get(side) or {}
        fallback_dims = dict(
            fallback_side.get("dimensions") or {}
            if isinstance(fallback_side, Mapping)
            else {}
        )

        for key, fallback_dim in fallback_dims.items():
            current = dict(engine_dims.get(key) or {})
            if bool(current.get("ready")):
                continue
            if not bool((fallback_dim or {}).get("ready")):
                continue
            engine_dims[key] = dict(fallback_dim)
            filled += 1

        engine_side["dimensions"] = engine_dims
        out[side] = engine_side

    out["display_fallback_source"] = _clean(fallback.get("source"))
    out["display_fallback_filled"] = filled
    out["display_fallback_ready"] = bool(fallback.get("ready"))
    return out, filled


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SOURCE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_fallback_dimensions",
    "_parse_directory",
    "_parse_team_metrics",
    "_resolve_team",
    "build_display_fallback",
    "merge_missing_dimensions",
]
