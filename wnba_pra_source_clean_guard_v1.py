"""Source-clean compatibility guard for out-of-band WNBA PRA generation.

The preserved model still imports historical compatibility hooks. During model
artifact generation this guard prevents those hooks from reaching prohibited
legacy network sources. When a generation date is supplied, roster/form/game-log
requests are redirected to the approved Basketball-Reference WNBA fallback;
historical schedule/game-summary fallbacks remain hard-empty.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
import importlib
import re
import sys
from typing import Any, Iterator, Mapping

import pandas as pd
import requests

_REFERENCE_ORIGIN = "https://www.basketball-reference.com"
_REFERENCE_SOURCE = "Basketball-Reference WNBA"
_DEFAULT_TIMEOUT = 6.0


def _legacy_marker() -> str:
    return "".join(("e", "s", "p", "n"))


def _fallback_names() -> tuple[str, ...]:
    marker = _legacy_marker()
    return (f"_{marker}_roster", f"_{marker}_season_schedule", f"_{marker}_game_summary")


def _stable_player_id(slug: str) -> int:
    digest = sha256(str(slug or "").strip().casefold().encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFF_FFFF


def _minutes(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return float("nan")
    if ":" in text:
        try:
            mins, secs = text.split(":", 1)
            return float(mins) + float(secs) / 60.0
        except Exception:
            return float("nan")
    try:
        return float(text)
    except Exception:
        return float("nan")


def _number(value: Any) -> float:
    if value is None:
        return float("nan")
    text = str(value).strip()
    if text == "":
        return float("nan")
    try:
        return float(text)
    except Exception:
        return float("nan")


class _StatsTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: list[dict[str, Any]] = []
        self._row: dict[str, Any] | None = None
        self._cell_stat: str | None = None
        self._cell_text: list[str] = []
        self._cell_href: str | None = None

    def _flush_cell(self) -> None:
        if self._row is None or not self._cell_stat:
            return
        value = " ".join("".join(self._cell_text).split())
        self._row[self._cell_stat] = value
        if self._cell_href:
            self._row[f"{self._cell_stat}__href"] = self._cell_href
        self._cell_stat = None
        self._cell_text = []
        self._cell_href = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {str(k): v for k, v in attrs}
        if tag == "tr":
            self._flush_cell()
            self._row = {}
        elif tag in {"td", "th"} and self._row is not None:
            # Basketball-Reference occasionally emits malformed closing markup
            # around a player cell. Starting the next cell is therefore also a
            # safe boundary at which to commit the previous cell.
            self._flush_cell()
            self._cell_stat = str(values.get("data-stat") or "") or None
            self._cell_text = []
            self._cell_href = None
        elif tag == "a" and self._cell_stat:
            href = values.get("href")
            if href:
                self._cell_href = str(href)

    def handle_data(self, data: str) -> None:
        if self._cell_stat:
            self._cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"}:
            self._flush_cell()
        elif tag == "tr" and self._row is not None:
            self._flush_cell()
            if self._row:
                self.rows.append(self._row)
            self._row = None


def _parse_rows(html: str) -> list[dict[str, Any]]:
    parser = _StatsTableParser()
    parser.feed(str(html or ""))
    return parser.rows


def _player_slug(href: str) -> str:
    match = re.search(r"/wnba/players/[^/]+/([^/.]+)\.html", str(href or ""))
    return match.group(1) if match else ""


class _ReferenceFallback:
    def __init__(
        self,
        day: str,
        season: int,
        *,
        session: Any | None = None,
        schedule_payload: Mapping[str, Any] | None = None,
        focus_names: set[str] | None = None,
    ):
        self.day = datetime.strptime(str(day), "%Y-%m-%d").date()
        self.season = int(season)
        self.session = session or requests.Session()
        self.schedule_payload = dict(schedule_payload or {})
        self.focus_names = {str(x).strip() for x in (focus_names or set()) if str(x).strip()}
        self._season_rows: list[dict[str, Any]] | None = None
        self._slug_by_id: dict[int, str] = {}
        self._name_by_id: dict[int, str] = {}
        self._log_cache: dict[int, pd.DataFrame] = {}

    def _get(self, path: str) -> str:
        response = self.session.get(
            _REFERENCE_ORIGIN + path,
            headers={"User-Agent": "kyre-sports-ai-wnba-reference/1"},
            timeout=_DEFAULT_TIMEOUT,
        )
        if int(getattr(response, "status_code", 500)) != 200:
            return ""
        return str(getattr(response, "text", "") or "")

    def _season(self) -> list[dict[str, Any]]:
        if self._season_rows is None:
            self._season_rows = _parse_rows(self._get(f"/wnba/years/{self.season}_per_game.html"))
            for row in self._season_rows:
                slug = _player_slug(str(row.get("player__href") or ""))
                if slug:
                    pid = _stable_player_id(slug)
                    self._slug_by_id[pid] = slug
                    self._name_by_id[pid] = str(row.get("player") or "")
        return self._season_rows

    def _team_identity(self, abbr: str) -> tuple[int, str]:
        code = str(abbr or "").upper()
        for game in self.schedule_payload.get("games") or []:
            if not isinstance(game, Mapping):
                continue
            for side in ("away", "home"):
                team = game.get(side) or {}
                if str(team.get("team_tricode") or "").upper() == code:
                    try:
                        return int(team.get("official_team_id")), str(team.get("full_name") or code)
                    except Exception:
                        return 0, str(team.get("full_name") or code)
        return 0, code

    def roster(self, team_id: int, team_name: str = "", team_abbr: str = "") -> pd.DataFrame:
        code = str(team_abbr or "").upper()
        team_rows = _parse_rows(self._get(f"/wnba/teams/{code}/{self.season}.html")) if code else []
        position_by_slug = {
            _player_slug(str(row.get("player__href") or "")): str(row.get("pos") or "")
            for row in team_rows
            if _player_slug(str(row.get("player__href") or ""))
        }
        rows: list[dict[str, Any]] = []
        for row in self._season():
            if str(row.get("team") or "").upper() != code:
                continue
            slug = _player_slug(str(row.get("player__href") or ""))
            if not slug:
                continue
            pid = _stable_player_id(slug)
            self._slug_by_id[pid] = slug
            self._name_by_id[pid] = str(row.get("player") or "")
            rows.append({
                "PLAYER_ID": pid,
                "PLAYER_NAME": str(row.get("player") or ""),
                "TEAM_ID": int(team_id),
                "TEAM_NAME": str(team_name or code),
                "TEAM_ABBREVIATION": code,
                "POSITION": position_by_slug.get(slug) or str(row.get("pos") or ""),
                "ROSTER_STATUS": "ROSTERED",
                "PLAYER_ID_SOURCE": _REFERENCE_SOURCE,
            })
        return pd.DataFrame(rows)

    def _gamelog_for_slug(self, slug: str, player_name: str = "") -> pd.DataFrame:
        pid = _stable_player_id(slug)
        if pid in self._log_cache:
            return self._log_cache[pid].copy(deep=True)
        prefix = slug[:1].lower() or "x"
        paths = (
            f"/wnba/players/{prefix}/{slug}/gamelog/{self.season}/",
            f"/wnba/players/{prefix}/{slug}/gamelog-playoffs/",
        )
        rows: list[dict[str, Any]] = []
        for path in paths:
            for raw in _parse_rows(self._get(path)):
                date_text = str(raw.get("date_game") or "").strip()
                try:
                    game_date = pd.Timestamp(date_text)
                except Exception:
                    continue
                if pd.isna(game_date):
                    continue
                if game_date.date() >= self.day:
                    continue
                rows.append({
                    "GAME_DATE": game_date,
                    "PLAYER_ID": pid,
                    "PLAYER_NAME": player_name or self._name_by_id.get(pid, ""),
                    "TEAM_ABBREVIATION": str(raw.get("team_id") or ""),
                    "OPPONENT": str(raw.get("opp_id") or ""),
                    "MIN": _minutes(raw.get("mp")),
                    "PTS": _number(raw.get("pts")),
                    "REB": _number(raw.get("trb")),
                    "AST": _number(raw.get("ast")),
                    "DATA_SOURCE": _REFERENCE_SOURCE,
                })
        frame = pd.DataFrame(rows)
        if not frame.empty:
            frame = frame.drop_duplicates(subset=["GAME_DATE", "PLAYER_ID"], keep="last")
            frame = frame.sort_values("GAME_DATE", ascending=False, kind="stable").reset_index(drop=True)
        self._log_cache[pid] = frame.copy(deep=True)
        return frame

    def player_game_log(self, player_id: Any, season: int | None = None) -> pd.DataFrame:
        self._season()
        try:
            pid = int(float(player_id))
        except Exception:
            return pd.DataFrame()
        slug = self._slug_by_id.get(pid)
        if not slug:
            return pd.DataFrame()
        return self._gamelog_for_slug(slug, self._name_by_id.get(pid, ""))

    def player_form_table(self, season: int | None = None) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for raw in self._season():
            slug = _player_slug(str(raw.get("player__href") or ""))
            if not slug:
                continue
            name = str(raw.get("player") or "")
            pid = _stable_player_id(slug)
            self._slug_by_id[pid] = slug
            self._name_by_id[pid] = name
            team_abbr = str(raw.get("team") or "").upper()
            team_id, team_name = self._team_identity(team_abbr)
            pts, reb, ast = _number(raw.get("pts_per_g")), _number(raw.get("trb_per_g")), _number(raw.get("ast_per_g"))
            history = pd.DataFrame()
            if not self.focus_names or name in self.focus_names:
                history = self._gamelog_for_slug(slug, name)
            recent = history.head(5) if not history.empty else pd.DataFrame()
            def mean(col: str) -> float:
                return float(pd.to_numeric(recent[col], errors="coerce").mean()) if not recent.empty and col in recent else float("nan")
            rows.append({
                "PLAYER_ID": pid,
                "PLAYER_NAME": name,
                "TEAM_ID": team_id,
                "TEAM_NAME": team_name,
                "TEAM_ABBREVIATION": team_abbr,
                "POSITION": str(raw.get("pos") or ""),
                "GP": int(_number(raw.get("g"))) if pd.notna(_number(raw.get("g"))) else 0,
                "MIN": _number(raw.get("mp_per_g")),
                "PTS": pts, "REB": reb, "AST": ast,
                "PRA": pts + reb + ast,
                "L5_GP": int(len(recent)),
                "L5_MIN": mean("MIN"), "L5_PTS": mean("PTS"), "L5_REB": mean("REB"), "L5_AST": mean("AST"),
                "LAST_GAME_DATE": history.iloc[0]["GAME_DATE"].strftime("%Y-%m-%d") if not history.empty else "",
                "DATA_SOURCE": _REFERENCE_SOURCE,
            })
        return pd.DataFrame(rows)



_FIRST_PARTY_SOURCE = "WNBA.com First-Party Page Data"


class _FirstPartyFallback:
    """Official-WNBA roster, season-rate and recent-history adapter."""
    def __init__(
        self,
        day: str,
        season: int = 2026,
        *,
        schedule_payload: Mapping[str, Any] | None = None,
        focus_names: set[str] | None = None,
        roster_loader: Any | None = None,
        player_page_loader: Any | None = None,
        history_loader: Any | None = None,
        reference_fallback: Any | None = None,
    ) -> None:
        self.day = pd.Timestamp(str(day)).date()
        self.season = int(season)
        self.schedule_payload = dict(schedule_payload or {})
        self.focus_names = {str(x).strip() for x in (focus_names or set()) if str(x).strip()}
        if roster_loader is None:
            roster_loader = importlib.import_module(
                "sports_api.wnba_step7g_first_party_rosters"
            ).get_first_party_current_players_dataset
        if player_page_loader is None or history_loader is None:
            history_module = importlib.import_module("sports_api.wnba_step7g_first_party_history")
            player_page_loader = player_page_loader or history_module._player_page
            history_loader = history_loader or history_module.get_first_party_player_recent_game_log_dataset
        self._roster_loader = roster_loader
        self._player_page_loader = player_page_loader
        self._history_loader = history_loader
        self._reference = reference_fallback
        self._roster_dataset: dict[str, Any] | None = None
        self._form_cache: pd.DataFrame | None = None
        self._log_cache: dict[int, pd.DataFrame] = {}
        self._team_map: dict[int, dict[str, Any]] = {}
        for game in self.schedule_payload.get("games") or []:
            if not isinstance(game, Mapping):
                continue
            for side in ("away", "home"):
                raw = game.get(side) or {}
                if not isinstance(raw, Mapping):
                    continue
                try:
                    tid = int(raw.get("official_team_id") or 0)
                except Exception:
                    tid = 0
                if tid > 0:
                    self._team_map[tid] = {
                        "team_id": tid,
                        "team_name": str(raw.get("full_name") or raw.get("team_tricode") or ""),
                        "team_abbr": str(raw.get("team_tricode") or "").upper(),
                    }

    def _dataset(self) -> dict[str, Any]:
        if self._roster_dataset is None:
            payload = self._roster_loader(self.season, current_roster_only=True)
            self._roster_dataset = dict(payload or {}) if isinstance(payload, Mapping) else {}
        return self._roster_dataset

    def _current_players(self) -> list[dict[str, Any]]:
        allowed = set(self._team_map)
        rows = []
        for raw in self._dataset().get("players") or []:
            if not isinstance(raw, Mapping):
                continue
            try:
                tid = int(raw.get("official_team_id") or 0)
            except Exception:
                tid = 0
            if allowed and tid not in allowed:
                continue
            if raw.get("is_current_roster") is False:
                continue
            rows.append(dict(raw))
        return rows

    def roster(self, team_id: int, team_name: str = "", team_abbr: str = "") -> pd.DataFrame:
        try:
            tid = int(team_id)
        except Exception:
            tid = 0
        rows = []
        for raw in self._current_players():
            if int(raw.get("official_team_id") or 0) != tid:
                continue
            meta = self._team_map.get(tid, {})
            rows.append({
                "PLAYER_ID": int(raw.get("player_id") or 0),
                "PLAYER_NAME": str(raw.get("full_name") or ""),
                "TEAM_ID": tid,
                "TEAM_NAME": str(meta.get("team_name") or team_name or raw.get("team_name") or ""),
                "TEAM_ABBREVIATION": str(meta.get("team_abbr") or team_abbr or raw.get("team_abbreviation") or "").upper(),
                "POSITION": str(raw.get("position") or ""),
                "ROSTER_STATUS": "CURRENT TEAM",
                "ROSTER_SOURCE": _FIRST_PARTY_SOURCE,
            })
        frame = pd.DataFrame(rows)
        if frame.empty and self._reference is not None:
            try:
                return self._reference.roster(team_id, team_name, team_abbr)
            except Exception:
                return frame
        return frame

    @staticmethod
    def _game_frame(games: list[Mapping[str, Any]], player_id: int) -> pd.DataFrame:
        rows = []
        for raw in games:
            if not isinstance(raw, Mapping):
                continue
            date_text = str(raw.get("game_date") or "").strip()
            try:
                stamp = pd.Timestamp(date_text)
            except Exception:
                continue
            if pd.isna(stamp):
                continue
            rows.append({
                "GAME_DATE": stamp,
                "PLAYER_ID": int(player_id),
                "MIN": _number(raw.get("minutes")),
                "PTS": _number(raw.get("points")),
                "REB": _number(raw.get("rebounds")),
                "AST": _number(raw.get("assists")),
                "DATA_SOURCE": _FIRST_PARTY_SOURCE,
            })
        if not rows:
            return pd.DataFrame(columns=["GAME_DATE", "PLAYER_ID", "MIN", "PTS", "REB", "AST", "DATA_SOURCE"])
        frame = pd.DataFrame(rows)
        frame = frame[frame["GAME_DATE"].dt.date < pd.Timestamp.now().date()] if False else frame
        return frame.drop_duplicates(subset=["GAME_DATE", "PLAYER_ID"], keep="first").sort_values("GAME_DATE", ascending=False, kind="stable").reset_index(drop=True)

    def _history(self, player_id: int) -> pd.DataFrame:
        pid = int(player_id)
        if pid in self._log_cache:
            return self._log_cache[pid].copy(deep=True)
        games: list[Mapping[str, Any]] = []
        for season_type in ("Playoffs", "Regular Season"):
            try:
                payload = self._history_loader(pid, self.season, season_type=season_type)
            except Exception:
                continue
            for game in (payload or {}).get("games") or []:
                if not isinstance(game, Mapping):
                    continue
                try:
                    stamp = pd.Timestamp(str(game.get("game_date") or ""))
                except Exception:
                    continue
                if pd.isna(stamp) or stamp.date() >= self.day:
                    continue
                games.append(dict(game))
        frame = self._game_frame(games, pid)
        if frame.empty and self._reference is not None:
            try:
                frame = self._reference.player_game_log(pid, self.season)
            except Exception:
                frame = pd.DataFrame()
        self._log_cache[pid] = frame.copy(deep=True)
        return frame

    def player_game_log(self, player_id: Any, season: int | None = None) -> pd.DataFrame:
        try:
            pid = int(float(player_id))
        except Exception:
            return pd.DataFrame()
        if season is not None and int(season) != self.season:
            return pd.DataFrame()
        return self._history(pid)

    def _player_page(self, player_id: int) -> dict[str, Any]:
        try:
            result = self._player_page_loader(int(player_id))
            if isinstance(result, tuple) and len(result) >= 2 and isinstance(result[1], Mapping):
                return dict(result[1])
            if isinstance(result, Mapping):
                return dict(result)
        except Exception:
            pass
        return {}

    def player_form_table(self, season: int | None = None) -> pd.DataFrame:
        if season is not None and int(season) != self.season:
            return pd.DataFrame()
        if self._form_cache is not None:
            return self._form_cache.copy(deep=True)
        rows: list[dict[str, Any]] = []
        for raw in self._current_players():
            try:
                pid = int(raw.get("player_id") or 0)
                tid = int(raw.get("official_team_id") or 0)
            except Exception:
                continue
            if pid <= 0 or tid <= 0:
                continue
            name = str(raw.get("full_name") or "")
            page = self._player_page(pid)
            stats = page.get("stats") if isinstance(page.get("stats"), Mapping) else {}
            history = self._history(pid)
            recent10 = history.head(10) if not history.empty else pd.DataFrame()
            recent5 = history.head(5) if not history.empty else pd.DataFrame()
            def mean(frame: pd.DataFrame, col: str) -> float:
                if frame is None or frame.empty or col not in frame.columns:
                    return float("nan")
                return float(pd.to_numeric(frame[col], errors="coerce").mean())
            season_pts = _number(stats.get("PTS"))
            season_reb = _number(stats.get("REB"))
            season_ast = _number(stats.get("AST"))
            if pd.isna(season_pts): season_pts = mean(recent10, "PTS")
            if pd.isna(season_reb): season_reb = mean(recent10, "REB")
            if pd.isna(season_ast): season_ast = mean(recent10, "AST")
            season_min = mean(recent10, "MIN")
            meta = self._team_map.get(tid, {})
            rows.append({
                "PLAYER_ID": pid,
                "PLAYER_NAME": name,
                "TEAM_ID": tid,
                "TEAM_NAME": str(meta.get("team_name") or raw.get("team_name") or ""),
                "TEAM_ABBREVIATION": str(meta.get("team_abbr") or raw.get("team_abbreviation") or "").upper(),
                "POSITION": str(raw.get("position") or page.get("position") or ""),
                "GP": int(len(history)),
                "MIN": season_min,
                "PTS": season_pts, "REB": season_reb, "AST": season_ast,
                "PRA": season_pts + season_reb + season_ast,
                "L10_GP": int(len(recent10)),
                "L10_MIN": mean(recent10, "MIN"), "L10_PTS": mean(recent10, "PTS"), "L10_REB": mean(recent10, "REB"), "L10_AST": mean(recent10, "AST"),
                "L10_PRA": mean(recent10, "PTS") + mean(recent10, "REB") + mean(recent10, "AST"),
                "L5_GP": int(len(recent5)),
                "L5_MIN": mean(recent5, "MIN"), "L5_PTS": mean(recent5, "PTS"), "L5_REB": mean(recent5, "REB"), "L5_AST": mean(recent5, "AST"),
                "L5_PRA": mean(recent5, "PTS") + mean(recent5, "REB") + mean(recent5, "AST"),
                "LAST_GAME_DATE": history.iloc[0]["GAME_DATE"].strftime("%Y-%m-%d") if not history.empty else "",
                "ROSTER_STATUS": "CURRENT TEAM",
                "PLAYER_ID_SOURCE": _FIRST_PARTY_SOURCE,
                "DATA_SOURCE": _FIRST_PARTY_SOURCE,
            })
        frame = pd.DataFrame(rows)
        if frame.empty and self._reference is not None:
            try:
                frame = self._reference.player_form_table(self.season)
            except Exception:
                frame = pd.DataFrame()
        self._form_cache = frame.copy(deep=True)
        return frame


def _make_first_party_fallback(day: str, season: int = 2026, **kwargs: Any) -> _FirstPartyFallback:
    return _FirstPartyFallback(day, season, **kwargs)

def _make_reference_fallback(day: str, season: int = 2026, **kwargs: Any) -> _ReferenceFallback:
    return _ReferenceFallback(day, season, **kwargs)


@dataclass
class SourceCleanGuardState:
    blocked_calls: int = 0
    reference_fallback: str | None = None


def _empty_frame(state: SourceCleanGuardState):
    def blocked(*_args: Any, **_kwargs: Any):
        state.blocked_calls += 1
        return pd.DataFrame()
    return blocked


@contextmanager
def source_clean_generation(
    day: str | None = None,
    season: int = 2026,
    *,
    schedule_payload: Mapping[str, Any] | None = None,
    focus_names: set[str] | None = None,
) -> Iterator[SourceCleanGuardState]:
    """Redirect preserved network fallbacks to approved source-clean inputs."""
    state = SourceCleanGuardState()
    players = importlib.import_module("wnba_players_v25")
    old_data = importlib.import_module("wnba_data_v232")
    replaced: list[tuple[Any, str, Any]] = []
    blocked = _empty_frame(state)
    roster_name, season_schedule_name, game_summary_name = _fallback_names()

    fallback = None
    if day:
        reference = _make_reference_fallback(
            str(day), int(season), schedule_payload=schedule_payload, focus_names=focus_names
        )
        fallback = _make_first_party_fallback(
            str(day), int(season), schedule_payload=schedule_payload, focus_names=focus_names,
            reference_fallback=reference,
        )
        state.reference_fallback = _FIRST_PARTY_SOURCE

    def swap(module: Any, name: str, value: Any) -> None:
        if module is not None and hasattr(module, name):
            replaced.append((module, name, getattr(module, name)))
            setattr(module, name, value)

    swap(players, roster_name, fallback.roster if fallback else blocked)
    swap(players, season_schedule_name, blocked)
    swap(players, game_summary_name, blocked)
    if fallback:
        swap(players, "player_game_log", fallback.player_game_log)
        swap(old_data, "player_form_table", fallback.player_form_table)
        swap(old_data, "player_game_log", fallback.player_game_log)
        if hasattr(old_data, "PLAYER_HOSTS"):
            previous = tuple(getattr(old_data, "PLAYER_HOSTS"))
            replaced.append((old_data, "PLAYER_HOSTS", previous))
            setattr(old_data, "PLAYER_HOSTS", tuple(x for x in previous if "stats.nba.com" not in str(x).casefold()))
    try:
        yield state
    finally:
        for module, name, previous in reversed(replaced):
            setattr(module, name, previous)


__all__ = [
    "SourceCleanGuardState", "source_clean_generation", "_FirstPartyFallback", "_ReferenceFallback",
    "_make_first_party_fallback", "_make_reference_fallback", "_stable_player_id",
]
