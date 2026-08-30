from fastapi import APIRouter

from sports_api.wnba_step17b_always_on_runtime import get_step17b_status
from sports_api import wnba_step19e_cooldown_aware_cycle as _step19e
from sports_api import wnba_step19g_hosted_provider_trace as _step19g
from sports_api import wnba_step19h_fanduel_hosted_transport as _step19h
from sports_api import wnba_step19i_official_slate_transport as _step19i
from sports_api import wnba_step19j_runtime_acceleration as _step19j

# Install only after the frozen scheduler/runtime dependency graph is fully
# imported. This avoids API-package bootstrap cycles while still interposing
# before the FastAPI lifespan starts Step17B.
_step19e.install_step19e_cooldown_aware_cycle()
_step19g.install_step19g_hosted_provider_trace()
_step19h.install_step19h_fanduel_hosted_transport()
_step19i.install_step19i_official_slate_transport()
# Step19J must be last: it wraps the already-installed Step19G trace chain so
# provider diagnostics remain active while a private per-cycle context memo is
# in scope.
_step19j.install_step19j_runtime_acceleration()

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
