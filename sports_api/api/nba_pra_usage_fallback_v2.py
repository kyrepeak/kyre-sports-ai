"""Production Kyre Sports API NBA PRA usage fallback V2.

NBA Stats remains primary. When verified usage is still missing, this bounded
server-side successor checks Basketball-Reference Advanced and fills only the
missing usage fields. Application pages continue to use Kyre Sports API only.
"""
from __future__ import annotations

from datetime import date
import re
from typing import Any, Mapping, Sequence

from . import nba_pra_player_context_v1 as base

_BASE_COLLECT = base.collect_nba_pra_player_context
BREF_ADVANCED_TEMPLATE = "https://www.basketball-reference.com/leagues/NBA_{season}_advanced.html"
_USAGE_FIELDS = (
    "usage_pct",
    "usage_rank",
    "usage_team_size",
    "usage_games",
    "usage_minutes",
    "usage_period",
    "usage_source",
    "usage_scope",
)


def _season_end_year(day: date) -> int:
    return day.year + 1 if day.month >= 10 else day.year


def _season_label(end_year: int) -> str:
    return f"{end_year - 1}-{str(end_year)[-2:]}"


def _parse_advanced(document: str, *, season_label: str) -> dict[str, dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    for row_html in re.findall(r"<tr\b[^>]*>(.*?)</tr>", document or "", flags=re.I | re.S):
        cells: dict[str, str] = {}
        for stat, body in re.findall(
            r"<(?:td|th)\b[^>]*data-stat=[\"']([^\"']+)[\"'][^>]*>(.*?)</(?:td|th)>",
            row_html,
            flags=re.I | re.S,
        ):
            cells[stat] = base._strip_tags(body)
        name = base._text(cells.get("name_display") or cells.get("player"))
        team = base._text(cells.get("team_name_abbr") or cells.get("team_id") or cells.get("team")).upper()
        usage = base._num(cells.get("usg_pct") or cells.get("usg_percent"))
        games = base._num(cells.get("games") or cells.get("g"))
        minutes = base._num(cells.get("mp_per_g"))
        if minutes is None:
            total_minutes = base._num(cells.get("mp"))
            if total_minutes is not None and games is not None and games > 0:
                minutes = total_minutes / games
        if not name or not team or usage is None:
            continue
        usage_points = usage * 100.0 if 0.0 <= usage <= 1.5 else usage
        raw.append({
            "player_name": name,
            "team": team,
            "usage_pct": round(float(usage_points), 1),
            "usage_games": int(games) if games is not None and games >= 0 else None,
            "usage_minutes": round(float(minutes), 1) if minutes is not None else None,
        })

    out: dict[str, dict[str, Any]] = {}
    for row in raw:
        teammates = [candidate for candidate in raw if candidate["team"] == row["team"]]
        rank = 1 + sum(1 for candidate in teammates if float(candidate["usage_pct"]) > float(row["usage_pct"]))
        out[base._norm(row["player_name"])] = {
            **row,
            "usage_rank": rank,
            "usage_team_size": len(teammates),
            "usage_period": f"{season_label} REGULAR SEASON",
            "usage_source": "Basketball-Reference Advanced",
            "usage_scope": "TEAM PLAYERS WITH VERIFIED BASKETBALL-REFERENCE USG%",
        }
    return out


def _load_bref_usage(slate_date: date, names: Sequence[str]) -> dict[str, Any]:
    requested = [(base._norm(name), base._text(name)) for name in names if base._norm(name)]
    if not requested:
        return {"status": "DEGRADED", "diagnostic_state": "NO_PLAYERS", "profiles": {}}
    end_year = _season_end_year(slate_date)
    profiles: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for year in (end_year, end_year - 1):
        missing = [key for key, _name in requested if key not in profiles]
        if not missing:
            break
        try:
            document, _ = base._get_text(BREF_ADVANCED_TEMPLATE.format(season=year), timeout=10.0)
            rows = _parse_advanced(document, season_label=_season_label(year))
        except Exception as exc:
            errors.append(f"NBA_{year}_{type(exc).__name__}")
            continue
        for key in missing:
            if key in rows:
                profiles[key] = dict(rows[key])
    detail = f"RESOLVED_{len(profiles)}_OF_{len(requested)}"
    if errors:
        detail += ":" + ":".join(errors)
    return {
        "status": "HEALTHY" if len(profiles) == len(requested) else "DEGRADED",
        "diagnostic_state": detail,
        "profiles": profiles,
    }


def collect_nba_pra_player_context(slate_date: date, player_names: Sequence[str], **kwargs: Any) -> dict[str, Any]:
    result = _BASE_COLLECT(slate_date, player_names, **kwargs)
    profiles = result.get("profiles") if isinstance(result.get("profiles"), dict) else {}
    missing = [
        base._text(name)
        for name in player_names
        if base._text(name)
        and isinstance(profiles.get(base._norm(name)), Mapping)
        and profiles[base._norm(name)].get("usage_pct") is None
    ]
    health = result.setdefault("provider_health", {})
    if not missing:
        health["basketball_reference_usage"] = base._health("HEALTHY", "NOT_NEEDED", False)
        result["schema_version"] = "KYRE_NBA_PLAYER_CONTEXT_V3"
        return result
    try:
        fallback = _load_bref_usage(slate_date, missing)
        rows = fallback.get("profiles") if isinstance(fallback.get("profiles"), Mapping) else {}
        for name in missing:
            key = base._norm(name)
            target = profiles.get(key)
            row = rows.get(key)
            if not isinstance(target, dict) or not isinstance(row, Mapping):
                continue
            for field in _USAGE_FIELDS:
                value = row.get(field)
                if value is not None and value != "":
                    target[field] = value
        health["basketball_reference_usage"] = base._health(
            str(fallback.get("status") or "DEGRADED"),
            str(fallback.get("diagnostic_state") or "NO_DATA"),
            True,
        )
    except Exception as exc:
        health["basketball_reference_usage"] = base._health("DEGRADED", type(exc).__name__, True)
    result["schema_version"] = "KYRE_NBA_PLAYER_CONTEXT_V3"
    return result


base.collect_nba_pra_player_context = collect_nba_pra_player_context
