'''NBA PRA Page 2 verified data-completeness helpers.

Pure normalization only. No provider I/O, no sportsbook influence, and no
projection/model mutation. The application continues to consume Kyre Sports API
payloads and this layer only preserves verified evidence already returned by the
gateway.
'''
from __future__ import annotations

from typing import Any, Mapping


VERSION = "API2_NBA_PRA_PAGE2_DATA_COMPLETENESS_V1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _text(value: Any) -> str:
    return " ".join(str(value if value is not None else "").split()).strip()


def _norm(value: Any) -> str:
    return "".join(ch for ch in _text(value).casefold() if ch.isalnum())


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None


def combined_verified_games(profile: Mapping[str, Any]) -> list[dict[str, Any]]:
    '''Return verified current + prior games, newest first, without duplicates.'''
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    raw_games = list(profile.get("current_games") or []) + list(profile.get("prior_games") or [])
    for raw in raw_games:
        if not isinstance(raw, Mapping):
            continue
        points = _num(raw.get("points"))
        rebounds = _num(raw.get("rebounds"))
        assists = _num(raw.get("assists"))
        if points is None or rebounds is None or assists is None:
            continue
        game_date = _text(raw.get("game_date") or raw.get("date"))
        opponent = _text(raw.get("opponent")).upper()
        minutes = _num(raw.get("minutes"))
        dedupe_key = (game_date, opponent, points, rebounds, assists, minutes)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        row = dict(raw)
        row["game_date"] = game_date
        if opponent:
            row["opponent"] = opponent
        row["points"] = points
        row["rebounds"] = rebounds
        row["assists"] = assists
        row["minutes"] = minutes
        row["pra"] = points + rebounds + assists
        rows.append(row)
    rows.sort(key=lambda row: _text(row.get("game_date")), reverse=True)
    return rows


def enrich_role_availability_context(
    context: Mapping[str, Any],
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    '''Preserve official availability and teammate injury evidence for Page 2.'''
    out = dict(context or {})
    sources = snapshot.get("sources") if isinstance(snapshot.get("sources"), Mapping) else {}
    injuries = sources.get("injuries") if isinstance(sources.get("injuries"), Mapping) else {}
    verification = _text(injuries.get("verification")).upper()
    players = injuries.get("players") if isinstance(injuries.get("players"), Mapping) else {}

    profile = out.get("player") if isinstance(out.get("player"), Mapping) else {}
    player_name = _text(out.get("player_name") or profile.get("player_name"))
    player_key = _norm(player_name)
    team = _text(out.get("team") or profile.get("team")).upper()

    selected: dict[str, Any] | None = None
    teammates: list[dict[str, str]] = []
    for raw_key, raw in players.items():
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        name = _text(row.get("player_name"))
        key = _norm(name or raw_key)
        row_team = _text(row.get("team_tricode") or row.get("team")).upper()
        status = _text(row.get("status")).upper()
        reason = _text(row.get("reason"))
        if key == player_key and player_key:
            selected = row
            continue
        if team and row_team == team and status not in {"", "AVAILABLE", "UNKNOWN", "UNVERIFIED"}:
            teammates.append({"player_name": name or _text(raw_key), "status": status, "reason": reason})

    if verification == "VERIFIED":
        out["availability_verification"] = "VERIFIED"
        out["availability_source"] = "NBA Official Injury Report"
        out["availability_reported_at_utc"] = injuries.get("reported_at_utc")
        if selected is not None:
            out["availability"] = _text(selected.get("status")).upper() or "UNVERIFIED"
            out["availability_reason"] = _text(selected.get("reason"))
        else:
            out["availability"] = "NO OFFICIAL INJURY DESIGNATION"
            out["availability_reason"] = ""
        teammates.sort(key=lambda row: (row["status"], row["player_name"]))
        out["teammate_injuries"] = teammates
    return out
