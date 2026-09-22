"""FastAPI transport for WNBA Step 5K Top-5 player-prop ranking."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sports_api.database.wnba_pregame_prediction_store import (
    WNBAPregameStoreError,
    WNBAPregameStoreNotReadyError,
    evaluate_stored_calibration,
)
from sports_api.wnba_player_prop_top_five_board import (
    DEFAULT_MAXIMUM_SCENARIO_SPAN_PERCENTAGE_POINTS,
    DEFAULT_MINIMUM_BASE_PROBABILITY,
    DEFAULT_MINIMUM_WORST_SCENARIO_PROBABILITY,
    DEFAULT_TOP_N,
    MAX_TOP_N,
    MIN_TOP_N,
    WNBAPlayerPropBoardModelInputError,
    WNBAPlayerPropBoardNotReadyError,
    WNBAPlayerPropBoardUpstreamError,
    build_player_prop_top_five_board,
)
from sports_api.wnba_prop_threshold_probability import (
    MODEL_VERSION as THRESHOLD_MODEL_VERSION,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


class PlayerPropBoardCandidateInput(BaseModel):
    threshold: dict[str, Any]
    market_consensus: dict[str, Any] | None = None
    player_name: str | None = None


class PlayerPropTopFiveBoardInput(BaseModel):
    candidates: list[PlayerPropBoardCandidateInput]
    calibration_report: dict[str, Any] | None = None


def _raise_api_error(exc: Exception) -> None:
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, WNBAPlayerPropBoardModelInputError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, (WNBAPlayerPropBoardNotReadyError, WNBAPregameStoreNotReadyError)):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, WNBAPlayerPropBoardUpstreamError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if isinstance(exc, WNBAPregameStoreError):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    raise exc


@router.post("/rankings/player-props/top-five")
def create_player_prop_top_five_board(
    payload: PlayerPropTopFiveBoardInput,
    top_n: int = Query(default=DEFAULT_TOP_N, ge=MIN_TOP_N, le=MAX_TOP_N),
    minimum_base_probability: float = Query(
        default=DEFAULT_MINIMUM_BASE_PROBABILITY, ge=0.0, le=1.0
    ),
    minimum_worst_scenario_probability: float = Query(
        default=DEFAULT_MINIMUM_WORST_SCENARIO_PROBABILITY, ge=0.0, le=1.0
    ),
    maximum_scenario_span_percentage_points: float = Query(
        default=DEFAULT_MAXIMUM_SCENARIO_SPAN_PERCENTAGE_POINTS,
        ge=0.0,
        le=100.0,
    ),
    require_same_favored_side_all_scenarios: bool = Query(default=True),
    require_strict_numerical_readiness: bool = Query(default=True),
    require_mature_calibration: bool = Query(default=False),
    one_line_per_player_stat: bool = Query(default=True),
    include_stored_calibration_when_available: bool = Query(
        default=True,
        description=(
            "When the request does not include a Step-5I calibration report, attach the "
            "current model version's audit-grade Step-5J stored calibration if one exists. "
            "Calibration remains evidence metadata and does not rescale Step-5F probabilities."
        ),
    ),
):
    calibration_report = payload.calibration_report
    calibration_source = "request" if calibration_report is not None else "unavailable"
    if calibration_report is None and include_stored_calibration_when_available:
        try:
            calibration_report = evaluate_stored_calibration(
                probability_model_version=THRESHOLD_MODEL_VERSION,
                require_single_probability_model_version=True,
            )
            calibration_source = "step_5j_durable_store"
        except WNBAPregameStoreNotReadyError:
            calibration_report = None
            calibration_source = "unavailable_no_graded_audit_history_yet"
        except Exception as exc:
            _raise_api_error(exc)

    try:
        result = build_player_prop_top_five_board(
            [candidate.model_dump() for candidate in payload.candidates],
            calibration_report=calibration_report,
            top_n=top_n,
            minimum_base_probability=minimum_base_probability,
            minimum_worst_scenario_probability=minimum_worst_scenario_probability,
            maximum_scenario_span_percentage_points=maximum_scenario_span_percentage_points,
            require_same_favored_side_all_scenarios=require_same_favored_side_all_scenarios,
            require_strict_numerical_readiness=require_strict_numerical_readiness,
            require_mature_calibration=require_mature_calibration,
            one_line_per_player_stat=one_line_per_player_stat,
        )
        result["transport_context"] = {
            "calibration_input_source": calibration_source,
            "stored_calibration_lookup_requested": include_stored_calibration_when_available,
            "transport_context_not_part_of_board_fingerprint": True,
        }
        return result
    except Exception as exc:
        _raise_api_error(exc)
