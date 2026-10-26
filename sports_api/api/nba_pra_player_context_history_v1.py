"""Kyre Sports API NBA PRA history-only player-context route.

Page 1 needs verified identity + game history to compute PRA projections, but it
never renders usage. This route captures the verified history collector before
usage enrichment is installed, so Page 1 does not pay for unrelated usage
providers. Page 2 continues using the full player-context route.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, Field

from . import nba_pra_player_context_v1 as base

router = APIRouter(prefix="/pra/player-context/history", tags=["nba-pra-player-context"])
_HISTORY_COLLECT = base.collect_nba_pra_player_context


class NbaPraPlayerContextHistoryRequest(BaseModel):
    date: date
    player_names: list[str] = Field(min_length=1, max_length=200)
    team_codes: list[str] = Field(default_factory=list, max_length=30)


@router.post("")
def player_context_history(request: NbaPraPlayerContextHistoryRequest):
    return _HISTORY_COLLECT(request.date, request.player_names, team_codes=request.team_codes)
