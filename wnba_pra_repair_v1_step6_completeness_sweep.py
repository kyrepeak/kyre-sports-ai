"""WNBA PRA Repair V1 Step 6 — full game/player/final-card completeness sweep.

Verification-only. This module does not mutate runtime state, fetch data, or change
projection, market, probability, qualification, ranking, or sportsbook math.
It audits already-produced Step 1-5 records and fails closed on incomplete rows.
"""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import math
from pathlib import Path
from typing import Any, Mapping

MODEL_VERSION = "WNBA PRA REPAIR V1 • STEP 6 COMPLETENESS SWEEP"
ROOT = Path(__file__).resolve().parent

GAME_REQUIRED_FIELDS = (
    "game_id",
    "game_date",
    "away_team_id",
    "away_team",
    "home_team_id",
    "home_team",
)
PLAYER_REQUIRED_FIELDS = (
    "player_id",
    "player_name",
    "team_id",
    "projected_minutes",
    "projected_pts",
    "projected_reb",
    "projected_ast",
    "projected_pra",
)
TERMINAL_CARD_STATES = {
    "CERTIFIED MARKET",
    "MODEL FALLBACK",
    "HISTORY FALLBACK",
    "DATA LIMITED",
}


def _load_source_module(path: Path, name: str):
    spec = spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load verification dependency: {path.name}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _text(value: Any) -> str:
    return str(value or "").strip()


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result > 0 else None


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def canonical_team_ids() -> set[int]:
    step2 = _load_source_module(ROOT / "wnba_pra_repair_v1_step2_team_identity.py", "wnba_step6_step2_identity")
    step3 = _load_source_module(ROOT / "wnba_pra_repair_v1_step3_data.py", "wnba_step6_step3_data")
    ids2 = {int(value) for value in getattr(step2, "TEAM_BY_ID", {})}
    ids3 = {int(value) for value in getattr(step3, "TEAM_REGISTRY", {})}
    if not ids2 or ids2 != ids3:
        raise RuntimeError("WNBA canonical team registries are incomplete or disagree.")
    return ids2


def audit_game(game: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(game) if isinstance(game, Mapping) else {}
    missing: list[str] = []
    for field in GAME_REQUIRED_FIELDS:
        value = row.get(field)
        if field.endswith("_team_id"):
            if _positive_int(value) is None:
                missing.append(field)
        elif not _text(value):
            missing.append(field)

    away_id = _positive_int(row.get("away_team_id"))
    home_id = _positive_int(row.get("home_team_id"))
    canonical = canonical_team_ids()
    if away_id is not None and away_id not in canonical:
        missing.append("away_team_id:noncanonical")
    if home_id is not None and home_id not in canonical:
        missing.append("home_team_id:noncanonical")
    if away_id is not None and home_id is not None and away_id == home_id:
        missing.append("matchup:duplicate_team")

    return {
        "ready": not missing,
        "game_id": _text(row.get("game_id")),
        "game_date": _text(row.get("game_date")),
        "away_team_id": away_id,
        "home_team_id": home_id,
        "missing": tuple(missing),
    }


def audit_player(player: Mapping[str, Any] | None, game: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(player) if isinstance(player, Mapping) else {}
    game_row = dict(game) if isinstance(game, Mapping) else {}
    missing: list[str] = []

    player_id = _positive_int(row.get("player_id"))
    team_id = _positive_int(row.get("team_id"))
    if player_id is None:
        missing.append("player_id")
    if not _text(row.get("player_name")):
        missing.append("player_name")
    if team_id is None:
        missing.append("team_id")

    allowed_teams = {
        value for value in (
            _positive_int(game_row.get("away_team_id")),
            _positive_int(game_row.get("home_team_id")),
        ) if value is not None
    }
    if team_id is not None and team_id not in allowed_teams:
        missing.append("team_id:not_in_selected_game")

    for field in (
        "projected_minutes",
        "projected_pts",
        "projected_reb",
        "projected_ast",
        "projected_pra",
    ):
        if _finite_number(row.get(field)) is None:
            missing.append(field)

    return {
        "ready": not missing,
        "player_id": player_id,
        "player_name": _text(row.get("player_name")),
        "team_id": team_id,
        "missing": tuple(missing),
    }


def audit_card(card: Mapping[str, Any] | None) -> dict[str, Any]:
    row = dict(card) if isinstance(card, Mapping) else {}
    source = _text(row.get("decision_source")).upper()
    line_source = _text(row.get("line_source")).upper()
    expected = _finite_number(row.get("expected_pra"))
    line = _finite_number(row.get("line"))
    probability = _finite_number(row.get("probability"))
    direction = _text(row.get("direction")).upper() or "N/A"
    missing: list[str] = []

    if source not in TERMINAL_CARD_STATES:
        missing.append("decision_source")
    if expected is None:
        missing.append("expected_pra")

    truthful_data_limited = (
        source == "DATA LIMITED"
        and line is None
        and probability is None
        and direction == "N/A"
        and line_source in {"", "NONE"}
    )

    if source == "CERTIFIED MARKET":
        if line is None:
            missing.append("line")
        if direction not in {"OVER", "UNDER"}:
            missing.append("direction")
        if probability is None or not 0.0 <= probability <= 1.0:
            missing.append("probability")
        if line_source != "SPORTSBOOK":
            missing.append("line_source")
    elif source in {"MODEL FALLBACK", "HISTORY FALLBACK"}:
        if line is None:
            missing.append("line")
        if direction not in {"OVER", "UNDER"}:
            missing.append("direction")
        if probability is None or not 0.0 <= probability <= 1.0:
            missing.append("probability")
        if line_source != "REFERENCE":
            missing.append("line_source")
    elif source == "DATA LIMITED" and not truthful_data_limited:
        missing.append("data_limited_contract")

    return {
        "covered": not missing,
        "decision_source": source,
        "truthful_data_limited": truthful_data_limited,
        "missing": tuple(missing),
    }


def sweep_game(
    game: Mapping[str, Any] | None,
    players: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None,
    cards_by_player_id: Mapping[Any, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    game_audit = audit_game(game)
    player_rows = list(players or [])
    card_map = dict(cards_by_player_id) if isinstance(cards_by_player_id, Mapping) else {}

    player_audits = [audit_player(player, game or {}) for player in player_rows]
    valid_ids = [row["player_id"] for row in player_audits if row.get("player_id") is not None]
    duplicate_player_ids = tuple(sorted({pid for pid in valid_ids if valid_ids.count(pid) > 1}))

    card_audits: dict[int, dict[str, Any]] = {}
    missing_card_ids: list[int] = []
    for row in player_audits:
        pid = row.get("player_id")
        if pid is None:
            continue
        card = card_map.get(pid)
        if card is None:
            card = card_map.get(str(pid))
        if not isinstance(card, Mapping):
            missing_card_ids.append(pid)
            continue
        card_audits[pid] = audit_card(card)

    away_id = _positive_int((game or {}).get("away_team_id")) if isinstance(game, Mapping) else None
    home_id = _positive_int((game or {}).get("home_team_id")) if isinstance(game, Mapping) else None
    team_counts: dict[int, int] = {}
    for team_id in (away_id, home_id):
        if team_id is not None:
            team_counts[team_id] = sum(1 for row in player_audits if row.get("team_id") == team_id)

    players_ready = sum(1 for row in player_audits if row["ready"])
    cards_covered = sum(1 for row in card_audits.values() if row["covered"])
    both_teams_have_players = bool(team_counts) and all(count > 0 for count in team_counts.values())
    ready = (
        game_audit["ready"]
        and bool(player_audits)
        and players_ready == len(player_audits)
        and cards_covered == len(player_audits)
        and not missing_card_ids
        and not duplicate_player_ids
        and both_teams_have_players
    )

    return {
        "ready": bool(ready),
        "game": game_audit,
        "players_seen": len(player_audits),
        "players_ready": players_ready,
        "cards_covered": cards_covered,
        "team_player_counts": team_counts,
        "missing_card_player_ids": tuple(sorted(missing_card_ids)),
        "duplicate_player_ids": duplicate_player_ids,
        "incomplete_player_ids": tuple(sorted(row["player_id"] for row in player_audits if not row["ready"] and row.get("player_id") is not None)),
        "incomplete_card_player_ids": tuple(sorted(pid for pid, row in card_audits.items() if not row["covered"])),
    }


__all__ = [
    "MODEL_VERSION",
    "TERMINAL_CARD_STATES",
    "_load_source_module",
    "audit_card",
    "audit_game",
    "audit_player",
    "canonical_team_ids",
    "sweep_game",
]
