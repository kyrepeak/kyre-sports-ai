from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from sports_api import wnba_step9_release_freeze as release
from sports_api.wnba_step9_multisportsbook_consensus import (
    DEFAULT_MAX_SNAPSHOT_SPREAD_SECONDS,
    WNBAStep9MultiBookConsensusDisabledError,
    WNBAStep9MultiBookConsensusNotReadyError,
    WNBAStep9MultiBookConsensusUpstreamError,
    build_step9c_multibook_consensus,
)
from sports_api.wnba_step9_qualification_ranking import (
    DEFAULT_MAX_BOARD_SNAPSHOT_SPREAD_SECONDS,
    DEFAULT_MAXIMUM_CONSENSUS_RANGE_PERCENTAGE_POINTS,
    DEFAULT_MINIMUM_BOOKS_AT_LINE,
    DEFAULT_MINIMUM_CONSENSUS_EDGE,
    DEFAULT_MINIMUM_EV,
    DEFAULT_MINIMUM_MODEL_PROBABILITY,
    DEFAULT_TOP_N,
    WNBAStep9QualificationRankingDisabledError,
    WNBAStep9QualificationRankingNotReadyError,
    WNBAStep9QualificationRankingUpstreamError,
    build_step9d_qualification_ranking,
)
from sports_api.wnba_step9_sportsbook_market_comparison import (
    DEFAULT_MAX_MARKET_AGE_MINUTES,
    WNBAStep9MarketComparisonDisabledError,
    WNBAStep9MarketComparisonNotReadyError,
    WNBAStep9MarketComparisonUpstreamError,
    build_step9b_market_comparison,
)
from sports_api.wnba_step9_threshold_pricing import (
    WNBAStep9ThresholdPricingDisabledError,
    WNBAStep9ThresholdPricingNotReadyError,
    WNBAStep9ThresholdPricingUpstreamError,
    build_step9_threshold_pricing,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


class Step9SportsbookOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sportsbook: str = Field(min_length=1, max_length=80)
    line: float = Field(ge=0.0, le=250.0)
    over_odds: int
    under_odds: int
    market_captured_at_utc: str = Field(min_length=1)


class Step9PropInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step8_distribution: dict[str, Any]
    stat: str = Field(min_length=1, max_length=64)
    offers: list[Step9SportsbookOffer] = Field(min_length=2, max_length=50)


class Step9QualificationPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    top_n: int = Field(default=DEFAULT_TOP_N, ge=1, le=20)
    minimum_model_probability: float = Field(
        default=DEFAULT_MINIMUM_MODEL_PROBABILITY, ge=0.0, le=1.0
    )
    minimum_ev: float = Field(default=DEFAULT_MINIMUM_EV, ge=0.0, le=1.0)
    minimum_consensus_edge: float = Field(
        default=DEFAULT_MINIMUM_CONSENSUS_EDGE, ge=0.0, le=1.0
    )
    minimum_books_at_line: int = Field(
        default=DEFAULT_MINIMUM_BOOKS_AT_LINE, ge=1, le=25
    )
    maximum_consensus_range_percentage_points: float = Field(
        default=DEFAULT_MAXIMUM_CONSENSUS_RANGE_PERCENTAGE_POINTS,
        ge=0.0,
        le=100.0,
    )
    max_board_snapshot_spread_seconds: int = Field(
        default=DEFAULT_MAX_BOARD_SNAPSHOT_SPREAD_SECONDS,
        ge=0,
        le=3600,
    )
    max_prop_snapshot_spread_seconds: int = Field(
        default=DEFAULT_MAX_SNAPSHOT_SPREAD_SECONDS,
        ge=0,
        le=3600,
    )
    max_market_age_minutes: int = Field(
        default=DEFAULT_MAX_MARKET_AGE_MINUTES,
        ge=1,
        le=1440,
    )
    minimum_required_price_ev: float = Field(default=0.0, ge=0.0, le=1.0)
    require_fresh_market: bool = True
    require_synchronized_snapshots: bool = True
    one_selection_per_player: bool = True


class Step9MarketBoardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    props: list[Step9PropInput] = Field(min_length=1, max_length=250)
    policy: Step9QualificationPolicy = Field(default_factory=Step9QualificationPolicy)


_DISABLED_ERRORS = (
    WNBAStep9ThresholdPricingDisabledError,
    WNBAStep9MarketComparisonDisabledError,
    WNBAStep9MultiBookConsensusDisabledError,
    WNBAStep9QualificationRankingDisabledError,
)
_NOT_READY_ERRORS = (
    WNBAStep9ThresholdPricingNotReadyError,
    WNBAStep9MarketComparisonNotReadyError,
    WNBAStep9MultiBookConsensusNotReadyError,
    WNBAStep9QualificationRankingNotReadyError,
)
_UPSTREAM_ERRORS = (
    WNBAStep9ThresholdPricingUpstreamError,
    WNBAStep9MarketComparisonUpstreamError,
    WNBAStep9MultiBookConsensusUpstreamError,
    WNBAStep9QualificationRankingUpstreamError,
)


def _assert_step9_api_enabled() -> None:
    if not release.step9_fastapi_enabled():
        raise WNBAStep9QualificationRankingDisabledError(
            f"Step 9 FastAPI requires {release.STEP9_FASTAPI_ENABLED_ENV}=true."
        )


def _build_prop_consensus(
    prop_input: Step9PropInput,
    *,
    policy: Step9QualificationPolicy,
    evaluated_at: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    pricing_by_line: dict[float, dict[str, Any]] = {}
    bundles: list[dict[str, Any]] = []

    for offer in prop_input.offers:
        line_key = round(float(offer.line), 6)
        pricing = pricing_by_line.get(line_key)
        if pricing is None:
            pricing = build_step9_threshold_pricing(
                prop_input.step8_distribution,
                stat=prop_input.stat,
                line=line_key,
            )
            pricing_by_line[line_key] = pricing

        comparison = build_step9b_market_comparison(
            pricing,
            sportsbook=offer.sportsbook,
            over_odds=offer.over_odds,
            under_odds=offer.under_odds,
            market_captured_at_utc=offer.market_captured_at_utc,
            minimum_required_ev=policy.minimum_required_price_ev,
            max_market_age_minutes=policy.max_market_age_minutes,
            require_fresh_market=policy.require_fresh_market,
            evaluated_at=evaluated_at,
        )
        bundles.append({"comparison": comparison, "pricing": pricing})

    consensus = build_step9c_multibook_consensus(
        bundles,
        max_snapshot_spread_seconds=policy.max_prop_snapshot_spread_seconds,
        require_fresh_quotes=policy.require_fresh_market,
        require_synchronized_snapshot=policy.require_synchronized_snapshots,
    )
    summary = {
        "game_id": consensus["game_id"],
        "player_id": consensus["player_id"],
        "stat": consensus["prop"]["stat"],
        "offer_count": consensus["snapshot"]["offer_count"],
        "unique_sportsbook_count": consensus["snapshot"]["unique_sportsbook_count"],
        "unique_lines": consensus["prop"]["unique_lines"],
        "reference_line": consensus["prop"]["reference_line"],
        "consensus_content_sha256": consensus["consensus_content_sha256"],
        "step8_result_content_sha256": consensus["lineage"]["step8_result_content_sha256"],
    }
    return consensus, summary


@router.post("/props/market-board")
def wnba_step9_market_board(request: Step9MarketBoardRequest):
    """Build the frozen Step-9 A→B→C→D market board from caller-supplied quotes.

    The endpoint does not fetch sportsbook data. Each prop must include a certified
    Step-8 distribution and exact caller-supplied sportsbook quotes. The market
    enters only after the Step-8 basketball distribution is frozen.
    """
    try:
        _assert_step9_api_enabled()
        evaluated_at = datetime.now(timezone.utc)
        consensuses: list[dict[str, Any]] = []
        summaries: list[dict[str, Any]] = []
        for prop_input in request.props:
            consensus, summary = _build_prop_consensus(
                prop_input,
                policy=request.policy,
                evaluated_at=evaluated_at,
            )
            consensuses.append(consensus)
            summaries.append(summary)

        board = build_step9d_qualification_ranking(
            consensuses,
            top_n=request.policy.top_n,
            minimum_model_probability=request.policy.minimum_model_probability,
            minimum_ev=request.policy.minimum_ev,
            minimum_consensus_edge=request.policy.minimum_consensus_edge,
            minimum_books_at_line=request.policy.minimum_books_at_line,
            maximum_consensus_range_percentage_points=(
                request.policy.maximum_consensus_range_percentage_points
            ),
            max_board_snapshot_spread_seconds=(
                request.policy.max_board_snapshot_spread_seconds
            ),
            require_fresh_snapshots=request.policy.require_fresh_market,
            require_synchronized_snapshots=(
                request.policy.require_synchronized_snapshots
            ),
            one_selection_per_player=request.policy.one_selection_per_player,
        )
        return {
            "data_type": "wnba_step9_market_board_api_response_v1",
            "release": {
                "release_id": release.RELEASE_ID,
                "integration_version": release.INTEGRATION_VERSION,
                "season": release.SEASON,
                "season_type": release.SEASON_TYPE,
                "production_activation_allowed": release.PRODUCTION_ACTIVATION_ALLOWED,
            },
            "evaluated_at_utc": evaluated_at.isoformat(),
            "pipeline": {
                "order": ["step9a", "step9b", "step9c", "step9d"],
                "prop_count": len(consensuses),
                "props": summaries,
            },
            "board": board,
            "guardrails": {
                "sportsbook_network_fetch_performed": False,
                "basketball_projection_changed": False,
                "step8_distribution_changed": False,
                "supabase_mutated": False,
                "persistence_mutated": False,
                "scheduler_started": False,
                "production_runtime_enabled": False,
                "production_activation_allowed": False,
            },
        }
    except _DISABLED_ERRORS as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except _NOT_READY_ERRORS as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except _UPSTREAM_ERRORS as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
