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
# Step19N is the outermost Step12B wrapper. It classifies only the exact
# post-fetch FanDuel no-complete-two-way-records subtype as market availability.
# All transport, upstream, landing, and identity failures remain provider failures.
_step19n.install_step19n_fanduel_empty_market()
# Step20B is diagnostic-only and wraps component callables used inside the
# already-installed Step12B chain. It does not alter the Step12B wrapper order.
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


@router.get("/step17b")
def step17b_runtime_status():
    return get_step17b_status()


@router.get("/step19g-provider-trace")
def step19g_provider_trace_status():
    """Return sanitized in-process provider discovery from the last Step12B call."""
    return _step19g.get_step19g_hosted_provider_trace()


@router.get("/step19h-fanduel-transport")
def step19h_fanduel_transport_status():
    """Return metadata-only diagnostics for hosted FanDuel GET responses."""
    return _step19h.get_step19h_fanduel_transport_status()


@router.get("/step19i-official-slate-transport")
def step19i_official_slate_transport_status():
    """Return non-sensitive installation status for the Step19I slate repair."""
    return _step19i.installation_status()


@router.get("/step19j-runtime-acceleration")
def step19j_runtime_acceleration_status():
    """Return non-sensitive cycle-local runtime acceleration status."""
    return _step19j.installation_status()


@router.get("/step19k-market-not-ready")
def step19k_market_not_ready_status():
    """Return non-sensitive exact-line market readiness compatibility status."""
    return _step19k.installation_status()


@router.get("/step19l-fanduel-identity-trace")
def step19l_fanduel_identity_trace_status():
    """Return sanitized cumulative hosted FanDuel identity-error diagnostics."""
    return _step19l.get_step19l_fanduel_identity_trace()


@router.get("/step19m-fanduel-line-move")
def step19m_fanduel_line_move_status():
    """Return non-sensitive status for the strict same-market line-move repair."""
    return _step19m.installation_status()


@router.get("/step19n-fanduel-empty-market")
def step19n_fanduel_empty_market_status():
    """Return non-sensitive status for exact FanDuel empty-market classification."""
    return _step19n.installation_status()


@router.get("/step20b-rollover-stage-trace")
def step20b_rollover_stage_trace_status():
    """Return sanitized in-flight timing for the current projection assembly."""
    return _step20b.installation_status()


@router.post("/step20b-player-opportunity-probe")
def step20b_player_opportunity_probe(
    x_step20b_diagnostic_token: str | None = Header(
        default=None,
        alias="X-Step20B-Diagnostic-Token",
    ),
):
    """Run one fixed, token-gated Step4V opportunity probe on diagnostic deploys only."""
    _authorize_step20b_probe(x_step20b_diagnostic_token)
    started = time.perf_counter()
    try:
        result = _step4w.get_player_opportunity_context(
            _STEP20B_PROBE_PLAYER_ID,
            _STEP20B_PROBE_SEASON,
            season_type="Regular Season",
            last_n_games=5,
            include_current_availability=True,
        )
        return {
            "data_type": "wnba_step20b_player_opportunity_probe",
            "model_version": _step20b.MODEL_VERSION,
            "status": "returned",
            "player_id": _STEP20B_PROBE_PLAYER_ID,
            "season": _STEP20B_PROBE_SEASON,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "result_summary": {
                "data_type": result.get("data_type") if isinstance(result, dict) else None,
                "latest_observed_team_key": result.get("latest_observed_team_key") if isinstance(result, dict) else None,
                "requested_last_n_games": result.get("requested_last_n_games") if isinstance(result, dict) else None,
                "components": result.get("components") if isinstance(result, dict) else None,
            },
        }
    except Exception as exc:
        return {
            "data_type": "wnba_step20b_player_opportunity_probe",
            "model_version": _step20b.MODEL_VERSION,
            "status": "raised",
            "player_id": _STEP20B_PROBE_PLAYER_ID,
            "season": _STEP20B_PROBE_SEASON,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:1000],
        }


@router.get("/build")
def runtime_build_identity():
    """Return the running process's source-byte identity, not a provider SHA claim."""
    return get_runtime_build_identity()
