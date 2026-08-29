from fastapi import APIRouter

from sports_api.wnba_step17b_always_on_runtime import get_step17b_status
from sports_api import wnba_step19e_cooldown_aware_cycle as _step19e
from sports_api import wnba_step19g_hosted_provider_trace as _step19g

# Install only after the frozen scheduler/runtime dependency graph is fully
# imported. This avoids API-package bootstrap cycles while still interposing
# before the FastAPI lifespan starts Step17B.
_step19e.install_step19e_cooldown_aware_cycle()
_step19g.install_step19g_hosted_provider_trace()

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


@router.get("/step17b")
def step17b_runtime_status():
    return get_step17b_status()


@router.get("/step19g-provider-trace")
def step19g_provider_trace_status():
    """Return sanitized in-process provider discovery from the last Step12B call."""
    return _step19g.get_step19g_hosted_provider_trace()
