from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_step8_context_adjustment import (
    WNBAStep8ContextAdjustmentDisabledError,
    WNBAStep8ContextAdjustmentNotReadyError,
    WNBAStep8ContextAdjustmentUpstreamError,
)
from sports_api.wnba_step8_core_projection import (
    WNBAStep8CoreProjectionDisabledError,
    WNBAStep8CoreProjectionNotReadyError,
    WNBAStep8CoreProjectionUpstreamError,
)
from sports_api.wnba_step8_joint_monte_carlo import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_SIMULATIONS,
    MIN_SIMULATIONS,
    WNBAStep8MonteCarloDisabledError,
    WNBAStep8MonteCarloUpstreamError,
    get_player_game_step8_joint_probability_distribution,
    probability_for_line,
)
from sports_api.wnba_step8_official_box_baseline import (
    WNBAStep8OfficialBoxBaselineNotFoundError,
    WNBAStep8OfficialBoxBaselineUpstreamError,
)
from sports_api.wnba_step8_projection_handoff import (
    WNBAStep8ProjectionHandoffDisabledError,
    WNBAStep8ProjectionHandoffNotReadyError,
    WNBAStep8ProjectionHandoffUpstreamError,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])

MAX_API_SIMULATIONS = 10_000_000
MIN_API_BATCH_SIZE = 10_000
MAX_API_BATCH_SIZE = 500_000

_DISABLED_ERRORS = (
    WNBAStep8ProjectionHandoffDisabledError,
    WNBAStep8CoreProjectionDisabledError,
    WNBAStep8ContextAdjustmentDisabledError,
    WNBAStep8MonteCarloDisabledError,
)
_NOT_READY_ERRORS = (
    WNBAStep8ProjectionHandoffNotReadyError,
    WNBAStep8CoreProjectionNotReadyError,
    WNBAStep8ContextAdjustmentNotReadyError,
)
_UPSTREAM_ERRORS = (
    WNBAStep8ProjectionHandoffUpstreamError,
    WNBAStep8OfficialBoxBaselineUpstreamError,
    WNBAStep8CoreProjectionUpstreamError,
    WNBAStep8ContextAdjustmentUpstreamError,
    WNBAStep8MonteCarloUpstreamError,
)


def _validate_identity(game_id: str, player_id: int) -> None:
    if not isinstance(player_id, int) or isinstance(player_id, bool) or player_id <= 0:
        raise HTTPException(status_code=400, detail="player_id must be a positive integer")
    if len(game_id) != 10 or not game_id.isdigit():
        raise HTTPException(status_code=400, detail="game_id must be exactly 10 numeric digits")


def _attach_line_probabilities(
    result: dict,
    *,
    points_line: float | None,
    rebounds_line: float | None,
    assists_line: float | None,
    pra_line: float | None,
) -> dict:
    requested = {
        "points": points_line,
        "rebounds": rebounds_line,
        "assists": assists_line,
        "points_rebounds_assists": pra_line,
    }
    line_probabilities = {
        stat: probability_for_line(result, stat, float(line))
        for stat, line in requested.items()
        if line is not None
    }
    response = dict(result)
    response["requested_line_probabilities"] = line_probabilities
    response["requested_lines"] = {
        stat: float(line) for stat, line in requested.items() if line is not None
    }
    return response


@router.get("/games/{game_id}/players/{player_id}/projection-probabilities")
def player_game_step8_projection_probabilities(
    game_id: str,
    player_id: int,
    simulation_count: int = Query(
        default=DEFAULT_SIMULATIONS,
        ge=MIN_SIMULATIONS,
        le=MAX_API_SIMULATIONS,
        description="Joint P/R/A Monte Carlo trials. Certified default: 5,000,000.",
    ),
    batch_size: int = Query(
        default=DEFAULT_BATCH_SIZE,
        ge=MIN_API_BATCH_SIZE,
        le=MAX_API_BATCH_SIZE,
        description="Vectorized NumPy batch size used for convergence diagnostics.",
    ),
    points_line: float | None = Query(default=None),
    rebounds_line: float | None = Query(default=None),
    assists_line: float | None = Query(default=None),
    pra_line: float | None = Query(
        default=None,
        description="Points + rebounds + assists line.",
    ),
):
    """Return the frozen Step-8 projection distribution and optional line probabilities.

    This endpoint remains default-OFF. It does not call a sportsbook, write to
    Supabase/persistence, or start any scheduler/production runtime.
    """
    _validate_identity(game_id, player_id)
    if batch_size > simulation_count:
        raise HTTPException(
            status_code=422,
            detail="batch_size must be no larger than simulation_count",
        )
    try:
        result = get_player_game_step8_joint_probability_distribution(
            player_id,
            game_id,
            simulations=simulation_count,
            batch_size=batch_size,
        )
        return _attach_line_probabilities(
            result,
            points_line=points_line,
            rebounds_line=rebounds_line,
            assists_line=assists_line,
            pra_line=pra_line,
        )
    except _DISABLED_ERRORS as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except WNBAStep8OfficialBoxBaselineNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except _NOT_READY_ERRORS as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except _UPSTREAM_ERRORS as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
