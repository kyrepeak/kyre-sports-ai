import hmac
import os
import time

from fastapi import APIRouter, Header, HTTPException

from sports_api.wnba_step17b_always_on_runtime import get_step17b_status
from sports_api import wnba_projection_input_snapshot as _step4w
from sports_api import wnba_step19e_cooldown_aware_cycle as _step19e
from sports_api import wnba_step19g_hosted_provider_trace as _step19g
from sports_api import wnba_step19h_fanduel_hosted_transport as _step19h
from sports_api import wnba_step19i_official_slate_transport as _step19i
from sports_api import wnba_step19j_runtime_acceleration as _step19j
from sports_api import wnba_step19k_market_not_ready as _step19k
from sports_api import wnba_step19l_fanduel_identity_trace as _step19l
from sports_api import wnba_step19m_fanduel_line_move as _step19m
from sports_api import wnba_step19n_fanduel_empty_market as _step19n
from sports_api import wnba_step20b_runtime_acceleration as _step20b_accel
from sports_api import wnba_step20b_rollover_stage_trace as _step20b
from sports_api.runtime_fingerprint import get_runtime_build_identity

# Install only after the frozen scheduler/runtime dependency graph is fully
# imported. This avoids API-package bootstrap cycles while still interposing
# before the FastAPI lifespan starts Step17B.
_step19e.install_step19e_cooldown_aware_cycle()
_step19g.install_step19g_hosted_provider_trace()
_step19h.install_step19h_fanduel_hosted_transport()
_step19i.install_step19i_official_slate_transport()
# Step19J wraps the already-installed Step19G trace chain so provider diagnostics
# remain active while a private per-cycle context memo is in scope.
_step19j.install_step19j_runtime_acceleration()
# Step19K transforms only the proven no-exact-same-line Step12B condition into
# the existing closed-circuit market_not_ready controller semantics.
_step19k.install_step19k_market_not_ready()
# Step19L observes the complete already-installed FanDuel fetch chain only. It
# keeps a cumulative sanitized history of identity errors and re-raises them.
_step19l.install_step19l_fanduel_identity_trace()
# Step19M fixes the precise hosted line-move bug captured by Step19L: threshold
# changes are quote state, while market/player/selection/side identity stays
# immutable and fail-closed. Step19L remains inside this surface for diagnostics.
_step19m.install_step19m_fanduel_line_move()
# Step19N is the outermost pre-Step20B Step12B wrapper. It classifies only the
# exact post-fetch FanDuel no-complete-two-way-records subtype as availability.
_step19n.install_step19n_fanduel_empty_market()
# Step20B acceleration adds one-call-only memoization for exact observed game
# context. It installs before the trace so diagnostics can time cache misses/hits.
_step20b_accel.install_step20b_runtime_acceleration()
# Step20B trace is diagnostic-only and does not alter return values or math.
_step20b.install_step20b_rollover_stage_trace()

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])

_STEP20B_PROBE_ENABLED_ENV = "WNBA_STEP20B_PROBE_ENABLED"
_STEP20B_PROBE_TOKEN_ENV = "WNBA_STEP20B_PROBE_TOKEN"
_STEP20B_PROBE_PLAYER_ID = 203825
_STEP20B_PROBE_SEASON = 2026


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _authorize_step20b_probe(token: str | None) -> None:
    if not _truthy(os.environ.get(_STEP20B_PROBE_ENABLED_ENV)):
        raise HTTPException(status_code=404, detail="Not found")
    expected = str(os.environ.get(_STEP20B_PROBE_TOKEN_ENV) or "")
    supplied = str(token or "")
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="Diagnostic probe is not configured")
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="Forbidden")


def _run_fixed_opportunity_probe() -> dict:
    return _step4w.get_player_opportunity_context(
        _STEP20B_PROBE_PLAYER_ID,
        _STEP20B_PROBE_SEASON,
        season_type="Regular Season",
        last_n_games=5,
        include_current_availability=True,
    )


@router.get("/step17b")
def step17b_runtime_status():
    return get_step17b_status()


@router.get("/step19g-provider-trace")
def step19g_provider_trace_status():
    return _step19g.get_step19g_hosted_provider_trace()


@router.get("/step19h-fanduel-transport")
def step19h_fanduel_transport_status():
    return _step19h.get_step19h_fanduel_transport_status()


@router.get("/step19i-official-slate-transport")
def step19i_official_slate_transport_status():
    return _step19i.installation_status()


@router.get("/step19j-runtime-acceleration")
def step19j_runtime_acceleration_status():
    return _step19j.installation_status()


@router.get("/step19k-market-not-ready")
def step19k_market_not_ready_status():
    return _step19k.installation_status()


@router.get("/step19l-fanduel-identity-trace")
def step19l_fanduel_identity_trace_status():
    return _step19l.get_step19l_fanduel_identity_trace()


@router.get("/step19m-fanduel-line-move")
def step19m_fanduel_line_move_status():
    return _step19m.installation_status()


@router.get("/step19n-fanduel-empty-market")
def step19n_fanduel_empty_market_status():
    return _step19n.installation_status()


@router.get("/step20b-runtime-acceleration")
def step20b_runtime_acceleration_status():
    """Return non-sensitive cycle-local cache status for the Step20B candidate."""
    return _step20b_accel.installation_status()


@router.get("/step20b-rollover-stage-trace")
def step20b_rollover_stage_trace_status():
    return _step20b.installation_status()


@router.post("/step20b-player-opportunity-probe")
def step20b_player_opportunity_probe(
    x_step20b_diagnostic_token: str | None = Header(
        default=None,
        alias="X-Step20B-Diagnostic-Token",
    ),
):
    """Compare cold/warm fixed Step4V calls inside one private cache scope."""
    _authorize_step20b_probe(x_step20b_diagnostic_token)
    try:
        with _step20b_accel.cycle_local_cache_scope() as cache:
            cold_started = time.perf_counter()
            cold = _run_fixed_opportunity_probe()
            cold_elapsed = round(time.perf_counter() - cold_started, 3)

            warm_started = time.perf_counter()
            warm = _run_fixed_opportunity_probe()
            warm_elapsed = round(time.perf_counter() - warm_started, 3)
            stats = _step20b_accel.cache_stats(cache)

        comparable = (
            isinstance(cold, dict)
            and isinstance(warm, dict)
            and cold.get("data_type") == warm.get("data_type")
            and cold.get("player_id") == warm.get("player_id")
            and cold.get("latest_observed_team_key") == warm.get("latest_observed_team_key")
            and cold.get("requested_last_n_games") == warm.get("requested_last_n_games")
            and cold.get("components") == warm.get("components")
        )
        return {
            "data_type": "wnba_step20b_player_opportunity_probe",
            "trace_model_version": _step20b.MODEL_VERSION,
            "acceleration_model_version": _step20b_accel.MODEL_VERSION,
            "status": "returned",
            "player_id": _STEP20B_PROBE_PLAYER_ID,
            "season": _STEP20B_PROBE_SEASON,
            "cold_elapsed_seconds": cold_elapsed,
            "warm_elapsed_seconds": warm_elapsed,
            "elapsed_reduction_seconds": round(cold_elapsed - warm_elapsed, 3),
            "speedup_ratio": round(cold_elapsed / warm_elapsed, 3) if warm_elapsed > 0 else None,
            "comparison_surface_equal": comparable,
            "cache": stats,
            "result_summary": {
                "data_type": cold.get("data_type"),
                "latest_observed_team_key": cold.get("latest_observed_team_key"),
                "requested_last_n_games": cold.get("requested_last_n_games"),
                "components": cold.get("components"),
            },
        }
    except Exception as exc:
        return {
            "data_type": "wnba_step20b_player_opportunity_probe",
            "trace_model_version": _step20b.MODEL_VERSION,
            "acceleration_model_version": _step20b_accel.MODEL_VERSION,
            "status": "raised",
            "player_id": _STEP20B_PROBE_PLAYER_ID,
            "season": _STEP20B_PROBE_SEASON,
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:1000],
        }


@router.get("/build")
def runtime_build_identity():
    return get_runtime_build_identity()
