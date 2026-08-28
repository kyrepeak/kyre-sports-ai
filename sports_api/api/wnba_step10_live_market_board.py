from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from sports_api import wnba_step10_release_freeze as release
from sports_api import wnba_step10_refresh_controller as step10d
from sports_api.api import wnba_step9_market_board as step9api
from sports_api.wnba_step10_live_pipeline import (
    WNBAStep10LivePipelineDisabledError,
    WNBAStep10LivePipelineInputError,
    WNBAStep10LivePipelineNotReadyError,
    build_step10e_live_market_board,
)
from sports_api.wnba_step9_qualification_ranking import (
    DEFAULT_MAX_BOARD_SNAPSHOT_SPREAD_SECONDS,
    DEFAULT_MAXIMUM_CONSENSUS_RANGE_PERCENTAGE_POINTS,
    DEFAULT_MINIMUM_BOOKS_AT_LINE,
    DEFAULT_MINIMUM_CONSENSUS_EDGE,
    DEFAULT_MINIMUM_EV,
    DEFAULT_MINIMUM_MODEL_PROBABILITY,
    DEFAULT_TOP_N,
)
from sports_api.wnba_step9_multisportsbook_consensus import DEFAULT_MAX_SNAPSHOT_SPREAD_SECONDS
from sports_api.wnba_step9_sportsbook_market_comparison import DEFAULT_MAX_MARKET_AGE_MINUTES

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


class Step10ProviderAttempt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    payload: dict[str, Any] | None = None
    error_code: str | None = Field(default=None, max_length=80)


class Step10ProviderRefresh(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = Field(min_length=1, max_length=100)
    adapter_type: str = Field(min_length=1, max_length=80)
    attempts: list[Step10ProviderAttempt] = Field(min_length=1, max_length=5)


class Step10RefreshPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_interval_seconds: int = Field(
        default=step10d.DEFAULT_REFRESH_INTERVAL_SECONDS, ge=1, le=step10d.MAX_REFRESH_INTERVAL_SECONDS
    )
    max_attempts_per_provider: int = Field(
        default=step10d.DEFAULT_MAX_ATTEMPTS_PER_PROVIDER, ge=1, le=step10d.MAX_ATTEMPTS_PER_PROVIDER
    )
    retry_base_seconds: float = Field(default=step10d.DEFAULT_RETRY_BASE_SECONDS, ge=0.1, le=300.0)
    retry_multiplier: float = Field(default=step10d.DEFAULT_RETRY_MULTIPLIER, ge=1.0, le=10.0)
    retry_max_seconds: float = Field(default=step10d.DEFAULT_RETRY_MAX_SECONDS, ge=0.1, le=900.0)
    allow_last_good_fallback: bool = True
    max_last_good_age_seconds: float = Field(
        default=step10d.DEFAULT_MAX_LAST_GOOD_AGE_SECONDS, ge=1.0, le=86_400.0
    )
    max_quote_age_seconds: float = Field(default=600.0, gt=0.0, le=86_400.0)
    max_market_sync_seconds: float = Field(default=120.0, gt=0.0, le=86_400.0)
    max_board_sync_seconds: float = Field(default=300.0, gt=0.0, le=86_400.0)
    require_board_synchronized: bool = True


class Step10QualificationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_n: int = Field(default=DEFAULT_TOP_N, ge=1, le=20)
    minimum_model_probability: float = Field(default=DEFAULT_MINIMUM_MODEL_PROBABILITY, ge=0.0, le=1.0)
    minimum_ev: float = Field(default=DEFAULT_MINIMUM_EV, ge=0.0, le=1.0)
    minimum_consensus_edge: float = Field(default=DEFAULT_MINIMUM_CONSENSUS_EDGE, ge=0.0, le=1.0)
    minimum_books_at_line: int = Field(default=DEFAULT_MINIMUM_BOOKS_AT_LINE, ge=1, le=25)
    maximum_consensus_range_percentage_points: float = Field(
        default=DEFAULT_MAXIMUM_CONSENSUS_RANGE_PERCENTAGE_POINTS, ge=0.0, le=100.0
    )
    max_board_snapshot_spread_seconds: int = Field(
        default=DEFAULT_MAX_BOARD_SNAPSHOT_SPREAD_SECONDS, ge=0, le=3600
    )
    max_prop_snapshot_spread_seconds: int = Field(
        default=DEFAULT_MAX_SNAPSHOT_SPREAD_SECONDS, ge=0, le=3600
    )
    max_market_age_minutes: int = Field(default=DEFAULT_MAX_MARKET_AGE_MINUTES, ge=1, le=1440)
    minimum_required_price_ev: float = Field(default=0.0, ge=0.0, le=1.0)
    require_fresh_market: bool = True
    require_synchronized_snapshots: bool = True
    one_selection_per_player: bool = True


class Step10LiveMarketBoardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_refreshes: list[Step10ProviderRefresh] = Field(min_length=1, max_length=50)
    step8_distributions: list[dict[str, Any]] = Field(min_length=1, max_length=250)
    last_good_snapshot: dict[str, Any] | None = None
    expected_sportsbooks: list[str] | None = Field(default=None, max_length=100)
    cycle_started_at: datetime | None = None
    refresh_policy: Step10RefreshPolicy = Field(default_factory=Step10RefreshPolicy)
    qualification_policy: Step10QualificationPolicy = Field(default_factory=Step10QualificationPolicy)


@router.post("/props/live-market-board")
def wnba_step10_live_market_board(request: Step10LiveMarketBoardRequest):
    """Run the frozen Step-10 refresh/reconciliation stack into the frozen Step-9 board.

    Provider attempt payloads are caller-supplied. This endpoint does not open a
    sportsbook connection or start a scheduler; those remain explicitly disabled.
    """
    try:
        evaluated_at = datetime.now(timezone.utc)
        pipeline = build_step10e_live_market_board(
            provider_refreshes=[row.model_dump() for row in request.provider_refreshes],
            step8_distributions=request.step8_distributions,
            last_good_snapshot=request.last_good_snapshot,
            expected_sportsbooks=request.expected_sportsbooks,
            refresh_policy=request.refresh_policy.model_dump(),
            qualification_policy=request.qualification_policy.model_dump(),
            evaluated_at=evaluated_at,
            cycle_started_at=request.cycle_started_at,
        )
        return {
            "data_type": "wnba_step10_live_market_board_api_response_v1",
            "release": {
                "release_id": release.RELEASE_ID,
                "integration_version": release.INTEGRATION_VERSION,
                "season": release.SEASON,
                "season_type": release.SEASON_TYPE,
                "production_activation_allowed": release.PRODUCTION_ACTIVATION_ALLOWED,
                "endpoint_path": release.ENDPOINT_PATH,
            },
            "pipeline_result": pipeline,
        }
    except (WNBAStep10LivePipelineDisabledError, step10d.WNBAStep10RefreshControllerDisabledError, *step9api._DISABLED_ERRORS) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (WNBAStep10LivePipelineNotReadyError, *step9api._NOT_READY_ERRORS) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (step10d.WNBAStep10RefreshControllerIntegrityError, *step9api._UPSTREAM_ERRORS) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (WNBAStep10LivePipelineInputError, step10d.WNBAStep10RefreshControllerInputError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
