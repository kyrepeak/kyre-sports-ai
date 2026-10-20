"""Presentation-only professional intelligence for CFB Player Props Page 3.

Consumes the frozen Page-3 packet without mutating projection/model owners.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import cfb_player_props_page3_source_policy_v1 as source_policy

SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_OPTIONAL_QB_NUMERIC_FIELDS = (
    "pass_attempts", "completions", "passing_touchdowns", "interceptions",
)
_DIRECT_BOOK_TOKENS = (
    "fanduel", "draftkings", "betmgm", "caesars", "fanatics", "bet365",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _finite(value: Any) -> float | None:
    try:
        out = float(str(value).replace(",", "").strip())
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _unique(values: Sequence[Any]) -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values or ():
        value = _text(raw)
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return tuple(out)


def _value(raw: Any, key: str) -> Any:
    if isinstance(raw, Mapping):
        return raw.get(key)
    return getattr(raw, key, None)


def _provider_id(label: Any) -> str:
    text = _text(label)
    token = "".join(ch for ch in text.casefold() if ch.isalnum())
    if not token:
        return ""
    if any(book in token for book in _DIRECT_BOOK_TOKENS):
        return "direct_sportsbook_feed"
    if "oddsapi" in token:
        return "the_odds_api"
    if "sportsdataio" in token or token == "sportsdata":
        return "sportsdataio"
    if "sportsreference" in token:
        return "sports_reference"
    if "collegefootballdata" in token or token == "cfbd":
        return "collegefootballdata"
    if "ncaa" in token:
        return "ncaa_official"
    if "officialteam" in token or token in {"teamsite", "teamsites"}:
        return "official_team_sites"
    if "rotowire" in token:
        return "rotowire"
    if "actionnetwork" in token:
        return "action_network"
    if "vegasinsider" in token:
        return "vegasinsider"
    if token == "espn" or token.startswith("espn"):
        return "espn"
    if token == "cbs" or token.startswith("cbssports"):
        return "cbs_sports"
    return ""


def _newest_timestamp(rows: Sequence[Any]) -> str:
    normalized = []
    for raw in rows or ():
        stamp = _text(_value(raw, "observed_at_utc") or _value(raw, "updated_at_utc") or _value(raw, "updated_at"))
        label = _text(_value(raw, "provider") or _value(raw, "source") or _value(raw, "provider_id"))
        if stamp:
            normalized.append({"provider": label, "observed_at_utc": stamp})
    newest = source_policy.choose_newest_equivalent(normalized)
    return _text((newest or {}).get("observed_at_utc"))


def _source_block(field_family: str, labels: Sequence[Any], *, newest_timestamp: str = "") -> dict[str, Any]:
    actual = _unique(labels)
    available_ids = _unique([_provider_id(label) for label in actual if _provider_id(label)])
    active = source_policy.rank_sources(field_family, available_ids)
    block = source_policy.provenance(field_family, active, newest_timestamp=newest_timestamp)
    block["actual_provider_labels"] = actual
    return block


def _build_source_status(
    context: Mapping[str, Any], packet: Mapping[str, Any], history_rows: Sequence[Mapping[str, Any]], market: Mapping[str, Any]
) -> dict[str, Any]:
    observations = tuple(market.get("observations") or ())
    player_prop_labels = [
        _value(row, "provider") or _value(row, "source") or _value(row, "provider_id")
        for row in observations
    ]
    history_labels = [row.get("source") or row.get("provider") or row.get("provider_id") for row in history_rows]

    availability = packet.get("availability") or {}
    availability_labels = []
    if isinstance(availability, Mapping):
        availability_labels.append(availability.get("source") or availability.get("provider") or availability.get("provider_id"))

    movement = packet.get("movement") or market.get("movement") or {}
    movement_labels = []
    movement_stamp = ""
    if isinstance(movement, Mapping):
        movement_labels.extend((movement.get("sportsbook"), movement.get("source"), movement.get("provider")))
        movement_stamp = _text(movement.get("observed_at_utc") or movement.get("updated_at_utc"))

    game_state_labels = [
        context.get("game_state_source"), context.get("status_source"), context.get("schedule_source")
    ]
    game_state = packet.get("game_state") or {}
    if isinstance(game_state, Mapping):
        game_state_labels.extend((game_state.get("source"), game_state.get("provider")))

    history_stamp = _newest_timestamp(history_rows)
    return {
        "player_props": _source_block("player_props", player_prop_labels, newest_timestamp=_newest_timestamp(observations)),
        "game_lines": _source_block("game_lines", movement_labels, newest_timestamp=movement_stamp),
        "player_stats": _source_block("player_stats", history_labels, newest_timestamp=history_stamp),
        "game_state": _source_block("game_state", game_state_labels),
        "history": _source_block("history", history_labels, newest_timestamp=history_stamp),
        "availability": _source_block("availability", availability_labels),
    }


def _verified_row(raw: Mapping[str, Any]) -> dict[str, Any] | None:
    value = _finite(raw.get("value"))
    if value is None or value < 0:
        return None
    row = dict(raw)
    row["value"] = value
    for field in _OPTIONAL_QB_NUMERIC_FIELDS:
        if field in row:
            numeric = _finite(row.get(field))
            if numeric is None or numeric < 0:
                row.pop(field, None)
            else:
                row[field] = numeric
    attempts = _finite(row.get("pass_attempts"))
    completions = _finite(row.get("completions"))
    if attempts is not None and attempts > 0:
        row["yards_per_attempt"] = round(value / attempts, 2)
        if completions is not None and completions >= 0:
            row["completion_percentage"] = round(completions / attempts * 100.0, 1)
    return row


def _summary(rows: Sequence[Mapping[str, Any]], selected_line: float | None) -> dict[str, Any]:
    verified = [row for raw in rows if isinstance(raw, Mapping) and (row := _verified_row(raw)) is not None]
    values = [float(row["value"]) for row in verified]
    line = _finite(selected_line)
    hits = sum(1 for value in values if value > line) if line is not None else None
    sources = _unique([row.get("source") or row.get("provider_id") for row in verified])
    newest = source_policy.choose_newest_equivalent(verified)
    return {
        "sample_size": len(values),
        "average": (sum(values) / len(values)) if values else None,
        "hits": hits,
        "hit_rate": (hits / len(values)) if hits is not None and values else None,
        "rows": tuple(verified),
        "sources": sources,
        "newest_timestamp": _text((newest or {}).get("observed_at_utc")),
    }


def build_recent_window(
    rows: Sequence[Mapping[str, Any]], *, limit: int, selected_line: float | None
) -> dict[str, Any]:
    size = max(0, int(limit))
    out = _summary(list(rows or ())[:size], selected_line)
    out["label"] = f"Last {size}"
    return out


def build_direct_opponent(
    rows: Sequence[Mapping[str, Any]], *, opponent_team_id: str, selected_line: float | None
) -> dict[str, Any]:
    opponent = _text(opponent_team_id)
    matched = [
        raw for raw in rows or ()
        if isinstance(raw, Mapping) and opponent and _text(raw.get("opponent_team_id")) == opponent
    ]
    out = _summary(matched, selected_line)
    out["available"] = bool(out["sample_size"])
    out["label"] = "Direct Player vs Opponent"
    out["opponent_team_id"] = opponent
    return out


def build_team_matchup(
    rows: Sequence[Mapping[str, Any]], *, opponent_team_id: str, selected_player_id: str
) -> dict[str, Any]:
    opponent = _text(opponent_team_id)
    player = _text(selected_player_id)
    matched = []
    for raw in rows or ():
        if not isinstance(raw, Mapping) or not opponent or _text(raw.get("opponent_team_id")) != opponent:
            continue
        raw_player = _text(raw.get("official_player_id"))
        if raw_player and player and raw_player == player:
            continue
        matched.append(dict(raw))
    sources = _unique([row.get("source") or row.get("provider_id") for row in matched])
    newest = source_policy.choose_newest_equivalent(matched)
    return {
        "available": bool(matched),
        "label": "Team Matchup History",
        "sample_size": len(matched),
        "rows": tuple(matched),
        "sources": sources,
        "newest_timestamp": _text((newest or {}).get("observed_at_utc")),
        "opponent_team_id": opponent,
    }


def _player_id(context: Mapping[str, Any], packet: Mapping[str, Any]) -> str:
    direct = _text(context.get("official_player_id"))
    if direct:
        return direct
    player = context.get("player") or packet.get("player")
    return _text(getattr(player, "official_player_id", ""))


def _opponent_vs_role(context: Mapping[str, Any], packet: Mapping[str, Any]) -> dict[str, Any]:
    raw = packet.get("opponent_vs_role") or context.get("opponent_vs_role")
    if not isinstance(raw, Mapping) or raw.get("available") is not True or int(raw.get("sample_size") or 0) <= 0:
        return {"available": False, "sample_size": 0, "sources": (), "newest_timestamp": ""}
    out = dict(raw)
    out["available"] = True
    out["sample_size"] = int(raw.get("sample_size") or 0)
    out["sources"] = _unique(raw.get("sources") or ())
    return out


def _sportsbook_board(market: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for raw in market.get("observations") or ():
        if isinstance(raw, Mapping):
            get = raw.get
        else:
            get = lambda key, default=None, obj=raw: getattr(obj, key, default)
        sportsbook = _text(get("sportsbook"))
        side = _text(get("side")).lower()
        line = _finite(get("line"))
        if not sportsbook or side not in {"over", "under"} or line is None:
            continue
        rows.append({
            "sportsbook": sportsbook,
            "side": side,
            "line": line,
            "price": get("price"),
            "observed_at_utc": _text(get("observed_at_utc")),
        })
    return tuple(rows)


def build_professional_view(
    context: Mapping[str, Any], packet: Mapping[str, Any], *, selected_line: float | None
) -> dict[str, Any]:
    history_rows = tuple(dict(row) for row in (packet.get("history_rows") or ()) if isinstance(row, Mapping))
    line_result = dict(packet.get("line_lab") or {})
    projection = dict(packet.get("projection") or {})
    market = dict(packet.get("market") or {})
    quality = dict(packet.get("quality") or {})

    line = _finite(selected_line)
    if line is None:
        line = _finite(line_result.get("line"))
    projected = _finite(projection.get("projection"))
    margin = projected - line if projected is not None and line is not None else None
    model_ready = bool(line_result.get("model_ready") or projection.get("model_ready"))
    lean = None
    if model_ready and margin is not None:
        lean = "OVER" if margin > 0 else "UNDER" if margin < 0 else "EVEN"

    opponent = _text(packet.get("opponent_team_id") or context.get("opponent_team_id"))
    player_id = _player_id(context, packet)
    team_rows = context.get("team_matchup_rows") or context.get("team_matchup_history") or ()
    last3 = build_recent_window(history_rows, limit=3, selected_line=line)
    last5 = build_recent_window(history_rows, limit=5, selected_line=line)
    direct = build_direct_opponent(history_rows, opponent_team_id=opponent, selected_line=line)
    team = build_team_matchup(team_rows, opponent_team_id=opponent, selected_player_id=player_id)

    board = _sportsbook_board(market)
    source_status = _build_source_status(context, packet, history_rows, market)
    return {
        "decision": {
            "projection": projected,
            "selected_line": line,
            "market_consensus": _finite(market.get("consensus_line")),
            "margin": margin,
            "over_probability": _finite(line_result.get("over_probability")),
            "under_probability": _finite(line_result.get("under_probability")),
            "model_ready": model_ready,
            "lean": lean,
            "evidence_state": "MODEL READY" if model_ready else "LIMITED SAMPLE",
        },
        "last3": last3,
        "last5": last5,
        "direct_opponent": direct,
        "team_matchup": team,
        "opponent_vs_role": _opponent_vs_role(context, packet),
        "sportsbook_board": board,
        "market_movement": dict(packet.get("movement") or market.get("movement") or {"available": False}),
        "reasoning": dict(packet.get("reasoning") or {}),
        "source_status": source_status,
        "quality": {
            **quality,
            "history_sample_size": int(last5.get("sample_size") or 0),
            "history_sources": last5.get("sources") or (),
            "latest_history_timestamp": last5.get("newest_timestamp") or "",
            "sportsbook_row_count": len(board),
        },
        "sportsbook_projection_influence": SPORTSBOOK_PROJECTION_INFLUENCE,
    }


__all__ = [
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "build_recent_window",
    "build_direct_opponent",
    "build_team_matchup",
    "build_professional_view",
]
