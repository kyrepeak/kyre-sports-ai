from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sports_api.wnba_historical_backtest_calibration import (
    WNBAHistoricalBacktestModelInputError,
    WNBAHistoricalBacktestNotFoundError,
    WNBAHistoricalBacktestNotReadyError,
    WNBAHistoricalBacktestUpstreamError,
    build_pregame_archive_envelope,
    evaluate_backtest_observations,
    get_graded_archived_prediction,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


class PregameArchiveInput(BaseModel):
    threshold: dict[str, Any]
    snapshot: dict[str, Any]


class ArchivedPredictionGradeInput(BaseModel):
    archive: dict[str, Any]


class BacktestCalibrationInput(BaseModel):
    observations: list[dict[str, Any]]


def _value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


@router.post("/backtests/player-props/archive")
def create_player_prop_backtest_archive(
    payload: PregameArchiveInput,
    require_signature: bool = Query(
        default=True,
        description=(
            "Require the archive to be HMAC-SHA256 signed with the server-side "
            "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET. Disable only for explicit "
            "diagnostic/non-audit-grade use."
        ),
    ),
):
    try:
        result = build_pregame_archive_envelope(
            payload.threshold,
            payload.snapshot,
        )
        if require_signature and result["signature"]["signed"] is not True:
            raise WNBAHistoricalBacktestNotReadyError(
                "Audit-grade archive creation requires the server environment variable "
                "WNBA_BACKTEST_ARCHIVE_HMAC_SECRET to be configured with at least 32 bytes."
            )
        return result
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAHistoricalBacktestNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except WNBAHistoricalBacktestModelInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except WNBAHistoricalBacktestUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/backtests/player-props/grade")
def grade_player_prop_backtest_archive(
    payload: ArchivedPredictionGradeInput,
    require_audit_grade: bool = Query(
        default=True,
        description=(
            "Require a verifiable HMAC-signed pregame archive before grading. "
            "Disable only to evaluate explicitly diagnostic legacy/unsigned records."
        ),
    ),
):
    try:
        return get_graded_archived_prediction(
            payload.archive,
            require_audit_grade=require_audit_grade,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAHistoricalBacktestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WNBAHistoricalBacktestNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except WNBAHistoricalBacktestModelInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except WNBAHistoricalBacktestUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/backtests/player-props/calibration")
def evaluate_player_prop_backtest_calibration(
    payload: BacktestCalibrationInput,
    require_audit_grade: bool = Query(
        default=True,
        description=(
            "Require every observation to originate from a verified HMAC-signed "
            "pregame archive. Disable only for diagnostic legacy analysis."
        ),
    ),
    require_single_probability_model_version: bool = Query(
        default=True,
        description=(
            "Reject mixed Step-5F probability model versions instead of pooling "
            "them. When disabled, versions are still reported separately and no "
            "cross-version pooled report is created."
        ),
    ),
):
    try:
        return evaluate_backtest_observations(
            payload.observations,
            require_audit_grade=require_audit_grade,
            require_single_probability_model_version=require_single_probability_model_version,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAHistoricalBacktestNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except WNBAHistoricalBacktestModelInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except WNBAHistoricalBacktestUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
