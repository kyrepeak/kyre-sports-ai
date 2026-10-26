"""Production Kyre Sports API NBA PRA player-context completeness V2.

Preserves verified opponent metadata already exposed by upstream history sources.
No provider ownership, projection math, sportsbook influence, or frontend routing
changes are made here. The frozen V1 collector is patched through ``install`` so
its public route remains stable.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any

VERSION = "KYRE_NBA_PRA_PLAYER_CONTEXT_COMPLETENESS_V2"


def _opponent_code(base: Any, value: Any) -> str:
    text = base._text(value).upper()
    if not text:
        return ""
    text = re.sub(r"^(?:@|VS\.?|V\.?)[\s:.-]*", "", text).strip()
    match = re.search(r"\b([A-Z]{2,3})\b$", text)
    return match.group(1) if match else ""


def _build_reference_game_log_parser(base: Any):
    def parse_game_log(document: str) -> list[dict[str, Any]]:
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
                base,
                cells.get("opp_id")
                or cells.get("opp_name_abbr")
                or cells.get("opponent")
                or cells.get("opp"),
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

    return parse_game_log


def _build_reference_daily_parser(base: Any):
    def parse_reference_daily_leaders(document: str, game_date: str) -> dict[str, dict[str, Any]]:
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
                base,
                cells.get("opp_id")
                or cells.get("opp_name_abbr")
                or cells.get("opponent")
                or cells.get("opp"),
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

    return parse_reference_daily_leaders


def _build_cbs_parser(base: Any):
    def parse_cbs_game_log_html(document: str) -> list[dict[str, Any]]:
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
                row = {
                    "game_date": game_day,
                    "minutes": minutes,
                    "points": pts,
                    "rebounds": reb,
                    "assists": ast,
                }
                if opponent_index is not None and opponent_index < len(cells):
                    opponent = _opponent_code(base, cells[opponent_index])
                    if opponent:
                        row["opponent"] = opponent
                games.append(row)
        games.sort(key=lambda row: str(row.get("game_date") or ""), reverse=True)
        return games

    return parse_cbs_game_log_html


def install(base: Any) -> Any:
    """Install verified-history normalization on the production V1 collector."""
    base._parse_game_log = _build_reference_game_log_parser(base)
    base._parse_reference_daily_leaders = _build_reference_daily_parser(base)
    base._parse_cbs_game_log_html = _build_cbs_parser(base)
    return base
