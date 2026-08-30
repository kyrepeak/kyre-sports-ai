from fastapi import APIRouter

from sports_api.wnba_step17b_always_on_runtime import get_step17b_status
from sports_api import wnba_step19e_cooldown_aware_cycle as _step19e
from sports_api import wnba_step19g_hosted_provider_trace as _step19g
from sports_api import wnba_step19h_fanduel_hosted_transport as _step19h
from sports_api import wnba_step19i_official_slate_transport as _step19i
from sports_api import wnba_step19j_runtime_acceleration as _step19j
from sports_api import wnba_step19k_market_not_ready as _step19k
from sports_api import wnba_step19l_fanduel_identity_trace as _step19l
from sports_api import wnba_step19m_fanduel_line_move as _step19m
from sports_api import wnba_step19n_fanduel_empty_market as _step19n
from sports_api import wnba_step20b_fanduel_period_filter as _step20b_period
from sports_api import wnba_step20b_shared_input_cache as _step20b
from sports_api import wnba_step20b_render_inflight_trace as _step20b_trace

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
# Step20B keeps the FanDuel collector on its certified full-game scope. Explicit
# quarter/half player markets are unsupported rather than having their period
# suffix stripped or their player identity relaxed.
_step20b_period.install_step20b_fanduel_period_filter()
# Step19N classifies only the exact post-fetch FanDuel
# no-complete-two-way-records subtype as market availability. All transport,
# upstream, landing, and identity failures remain provider failures.
_step19n.install_step19n_fanduel_empty_market()
# Step20B is outermost and changes no frozen provider/model contract. It gives
# one Step12B call private deep-copy memos for shared Step8A helper inputs, then
# discards every memo in finally before the next scheduler cycle.
_step20b.install_step20b_shared_input_cache()
# Diagnostic-only private Step12B orchestration timing. This leaves the Step20B
# Step12B wrapper itself outermost and does not touch official-data/provider seams.
_step20b_trace.install_step20b_render_inflight_trace()

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


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


@router.get("/step20b-fanduel-period-filter")
def step20b_fanduel_period_filter_status():
    """Return non-sensitive full-game FanDuel market-scope filter status."""
    return _step20b_period.installation_status()


@router.get("/step20b-shared-input-cache")
def step20b_shared_input_cache_status():
    """Return non-sensitive cycle-local Step8A shared-input cache diagnostics."""
    return _step20b.installation_status()


@router.get("/step20b-render-inflight-trace")
def step20b_render_inflight_trace_status():
    """Return semantics-neutral in-flight Step12B/Step8 timing diagnostics."""
    return _step20b_trace.installation_status()
