"""NBA PRA live-acceptance server-side repairs.

This module patches only Kyre Sports API provider normalization. Application
pages still consume the stable Kyre Sports API route and never call providers.
Verified opponent metadata is preserved when the upstream history document
contains it; nothing is inferred when the source does not expose an opponent.
"""
from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any, Mapping

from . import nba_pra_player_context_v1 as base


def _opponent_code(value: Any) -> str:
    text = base._text(value).upper()
    if not text:
        return ""
    text = re.sub(r"^(?:@|VS\.?|V\.?)[\s:.-]*", "", text).strip()
    match = re.search(r"\b([A-Z]{2,3})\b$", text)
    return match.group(1) if match else ""


def _parse_game_log(document: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", document or "", flags=re.I | re.S):
        cells: dict[str, str] = {}
        for stat, body in re.findall(
            r"<(?:td|th)\b[^>]*data-stat=[\"']([^\"']+)[\"'][^>]*>(.*?)</(?:td|th)>",
            row_html,
            flags=re.I | re.S,
        ):
            cells[stat] = base._strip_tags(body)
        game_date = base._text(cells.get("date_game") or cells.get("date"))
        pts, reb, ast = base._num(cells.get("pts")), base._num(cells.get("trb")), base._num(cells.get("ast"))
        if not game_date or pts is None or reb is None or ast is None:
            continue
        opponent = _opponent_code(
            cells.get("opp_id")
            or cells.get("opp_name_abbr")
            or cells.get("opponent")
            or cells.get("opp")
        )
        row = {
            "game_date": game_date,
            "minutes": base._minutes(cells.get("mp")),
            "points": pts,
            "rebounds": reb,
            "assists": ast,
        }
        if opponent:
            row["opponent"] = opponent
        rows.append(row)
    rows.sort(key=lambda row: str(row.get("game_date") or ""), reverse=True)
    return rows[:40]


def _parse_reference_daily_leaders(document: str, game_date: str) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", document or "", flags=re.I | re.S):
        cells: dict[str, str] = {}
        raw_cells: dict[str, str] = {}
        for stat, body in re.findall(
            r"<(?:td|th)\b[^>]*data-stat=[\"']([^\"']+)[\"'][^>]*>(.*?)</(?:td|th)>",
            row_html,
            flags=re.I | re.S,
        ):
            raw_cells[stat] = body
            cells[stat] = base._strip_tags(body)
        name = base._text(cells.get("player"))
        pts, reb, ast = base._num(cells.get("pts")), base._num(cells.get("trb")), base._num(cells.get("ast"))
        minutes = base._minutes(cells.get("mp"))
        if not name or pts is None or reb is None or ast is None:
            continue
        slug_match = re.search(r"/players/[a-z]/([a-z0-9]+)\.html", raw_cells.get("player") or "", flags=re.I)
        slug = slug_match.group(1).casefold() if slug_match else ""
        opponent = _opponent_code(
            cells.get("opp_id")
            or cells.get("opp_name_abbr")
            or cells.get("opponent")
            or cells.get("opp")
        )
        game = {
            "game_date": base._text(game_date),
            "minutes": minutes,
            "points": pts,
            "rebounds": reb,
            "assists": ast,
        }
        if opponent:
            game["opponent"] = opponent
        rows[base._norm(name)] = {
            "player_name": name,
            "team": base._text(cells.get("team_id")).upper(),
            "provider_ids": {"basketball_reference": slug} if slug else {},
            "game": game,
        }
    return rows


def _parse_cbs_game_log_html(document: str) -> list[dict[str, Any]]:
    games: list[dict[str, Any]] = []
    for match in re.finditer(r"<h4\b[^>]*>(.*?)</h4>(.*?<table\b[^>]*>.*?</table>)", document or "", flags=re.I | re.S):
        title = base._strip_tags(match.group(1))
        if "regular season game log" not in title.casefold():
            continue
        table = match.group(2)
        header_match = re.search(r"<thead>(.*?)</thead>", table, flags=re.I | re.S)
        header_html = header_match.group(1) if header_match else ""
        headers: list[str] = []
        for raw in re.findall(r"<th\b[^>]*>(.*?)</th>", header_html, flags=re.I | re.S):
            text = base._strip_tags(raw).casefold().split()
            headers.append(text[0] if text else "")
        index = {name: i for i, name in enumerate(headers) if name}
        if not all(name in index for name in ("date", "min", "pts", "reb", "ast")):
            continue
        opponent_index = index.get("opponent")
        if opponent_index is None:
            opponent_index = index.get("opp")
        body_match = re.search(r"<tbody>(.*?)</tbody>", table, flags=re.I | re.S)
        body = body_match.group(1) if body_match else table
        for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", body, flags=re.I | re.S):
            cells = [base._strip_tags(value) for value in re.findall(r"<td\b[^>]*>(.*?)</td>", row_html, flags=re.I | re.S)]
            if not cells or max(index.values()) >= len(cells):
                continue
            try:
                game_day = datetime.strptime(cells[index["date"]], "%b %d, %Y").date().isoformat()
            except ValueError:
                continue
            minutes = base._minutes(cells[index["min"]])
            pts, reb, ast = base._num(cells[index["pts"]]), base._num(cells[index["reb"]]), base._num(cells[index["ast"]])
            if pts is None or reb is None or ast is None:
                continue
            row = {"game_date": game_day, "minutes": minutes, "points": pts, "rebounds": reb, "assists": ast}
            if opponent_index is not None and opponent_index < len(cells):
                opponent = _opponent_code(cells[opponent_index])
                if opponent:
                    row["opponent"] = opponent
            games.append(row)
    games.sort(key=lambda row: str(row.get("game_date") or ""), reverse=True)
    return games


def _cbs_player_history(player_name: str, slate_date: date, seed: Mapping[str, Any] | None) -> dict[str, Any] | None:
    profile = dict(seed or {})
    provider_ids = dict(profile.get("provider_ids") or {})
    provider_id = base._text(provider_ids.get("cbs_sports"))
    if not provider_id:
        return None
    canonical_name = base._text(profile.get("player_name") or player_name)
    current_start = slate_date.year if slate_date.month >= 10 else slate_date.year - 1
    current_games: list[dict[str, Any]] = []
    prior_games: list[dict[str, Any]] = []
    for season_start, target in ((current_start, current_games), (current_start - 1, prior_games)):
        try:
            document = base._cbs_game_log_document(provider_id, canonical_name, season_start)
            target.extend(_parse_cbs_game_log_html(document))
        except Exception:
            continue
        if len(current_games) >= 10:
            break
    if not current_games and not prior_games:
        return None
    out = dict(profile)
    out.update(
        {
            "player_name": canonical_name,
            "provider_ids": provider_ids,
            "current_games": current_games[:40],
            "prior_games": prior_games[:40],
            "stats_source": "CBS Sports game log",
        }
    )
    return out


base._parse_game_log = _parse_game_log
base._parse_reference_daily_leaders = _parse_reference_daily_leaders
base._cbs_player_history = _cbs_player_history
