"""Compose WNBA PRA customer view-models from preserved engine outputs only."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math
import pandas as pd

from wnba_pra_product_snapshot_v1 import PRAProductSnapshot
from wnba_pra_playoff_context_v1 import PlayoffContext

OUT = {"OUT", "INACTIVE", "DOUBTFUL"}
UNRESOLVED = {"QUESTIONABLE", "DAY-TO-DAY", "DAY TO DAY", "GTD", "GAME TIME DECISION", "PROBABLE"}


@dataclass(frozen=True)
class PlayerDecisionView:
    player_key: str
    player: str
    team: str
    opponent: str
    game_id: str
    headshot_url: str
    team_logo_url: str
    projected_minutes: float | None
    role_label: str
    availability_label: str
    proj_pts: float | None
    proj_reb: float | None
    proj_ast: float | None
    proj_pra: float | None
    market_line: float | None
    book_count: int
    over_probability: float | None
    under_probability: float | None
    edge: float | None
    decision_label: str
    decision_strength: float | None
    final_card_selected: bool
    evidence_state: str


def _value(row: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row and row.get(name) is not None and not (isinstance(row.get(name), float) and math.isnan(row.get(name))):
            return row.get(name)
    return default


def _flt(value: Any) -> float | None:
    try:
        number = float(value)
        return None if math.isnan(number) else number
    except (TypeError, ValueError):
        return None


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("game_id") or ""), str(row.get("player_key") or "")


def _map(frame: pd.DataFrame) -> dict[tuple[str, str], dict[str, Any]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return {}
    return {_key(r): r for r in frame.to_dict("records") if any(_key(r))}


def _consensus_map(frame: pd.DataFrame) -> dict[str, dict[str, Any]]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return {}
    return {str(r.get("player_key") or ""): r for r in frame.to_dict("records") if str(r.get("player_key") or "")}


def _availability(row: dict[str, Any]) -> tuple[str, str]:
    status = str(_value(row, "DESIGNATION", "designation", "availability", "role_label", default="") or "").upper().strip()
    if status in OUT:
        return "OUT / INACTIVE", "OUT / INACTIVE"
    if status in UNRESOLVED:
        return "UNRESOLVED", "UNRESOLVED"
    if status:
        return "VERIFIED", "VERIFIED"
    return "UNRESOLVED", "UNRESOLVED"


def build_player_views(
    snapshot: PRAProductSnapshot,
    context: PlayoffContext,
    consensus: pd.DataFrame,
) -> tuple[PlayerDecisionView, ...]:
    raw_rows = snapshot.projections.to_dict("records") if isinstance(snapshot.projections, pd.DataFrame) and not snapshot.projections.empty else []
    matchup = _map(snapshot.matchup_rows)
    stored = _map(snapshot.stored_mc_rows)
    final_rows = _map(snapshot.final_card)
    final_keys = set(final_rows)
    markets = _consensus_map(consensus)

    views: list[PlayerDecisionView] = []
    for raw in raw_rows:
        key = _key(raw)
        adjusted = matchup.get(key, {})
        source = dict(raw)
        source.update(adjusted)  # preserved matchup-adjusted output wins when present
        mc = stored.get(key, {})
        market = markets.get(str(key[1]), {})
        availability, availability_evidence = _availability(source)

        over = _flt(_value(mc, "model_over", "over_probability"))
        under = _flt(_value(mc, "model_under", "under_probability"))
        if under is None and over is not None:
            push = _flt(_value(mc, "push", default=0.0)) or 0.0
            under = max(0.0, min(1.0, 1.0 - over - push))
        selected = key in final_keys and availability != "OUT / INACTIVE"
        final_row = final_rows.get(key, {}) if selected else {}
        evidence = availability_evidence if availability_evidence != "VERIFIED" else str(market.get("evidence_state") or context.evidence_state or "UNAVAILABLE")

        views.append(PlayerDecisionView(
            player_key=str(key[1]),
            player=str(_value(source, "PLAYER_NAME", "player", "player_name", default=key[1]) or key[1]),
            team=str(_value(source, "TEAM_NAME", "team", default="") or ""),
            opponent=str(_value(source, "OPPONENT", "opponent", default="") or ""),
            game_id=str(key[0]),
            headshot_url=str(_value(source, "HEADSHOT_URL", "headshot_url", "player_headshot", default="") or ""),
            team_logo_url=str(_value(source, "TEAM_LOGO_URL", "team_logo_url", default="") or ""),
            projected_minutes=_flt(_value(source, "PROJ_MIN", "projected_minutes")),
            role_label=str(_value(source, "ROLE_LABEL", "role_label", default="") or ""),
            availability_label=availability,
            proj_pts=_flt(_value(source, "PROJ_PTS", "proj_pts", "projection_pts")),
            proj_reb=_flt(_value(source, "PROJ_REB", "proj_reb", "projection_reb")),
            proj_ast=_flt(_value(source, "PROJ_AST", "proj_ast", "projection_ast")),
            proj_pra=_flt(_value(source, "PROJ_PRA", "projection", "proj_pra")),
            market_line=_flt(market.get("consensus_line")),
            book_count=int(market.get("book_count") or 0),
            over_probability=over,
            under_probability=under,
            edge=_flt(_value(mc, "edge")),
            decision_label=str(_value(final_row, "decision_label", default=_value(mc, "decision_label", default="")) or ""),
            decision_strength=_flt(_value(final_row, "decision_strength", default=_value(mc, "decision_strength"))),
            final_card_selected=selected,
            evidence_state=evidence,
        ))
    return tuple(views)


__all__ = ["PlayerDecisionView", "build_player_views"]
