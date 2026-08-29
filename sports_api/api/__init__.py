"""API package bootstrap.

Step 19D is installed when ``sports_api.main`` first imports the API package.
That occurs after the frozen runtime modules are imported but before the FastAPI
lifespan starts, so the already-bound Step-4V opportunity seam can be updated
without changing any frozen scheduler source.

Step 19E uses the same bootstrap point to interpose a read-only durable-cooldown
preflight before Step17B starts an expensive scheduler cycle. The frozen
controller and scheduler implementations remain unchanged.
"""

import sports_api.wnba_step19d_history_transport_resilience as _wnba_step19d_history_transport_resilience  # noqa: F401
import sports_api.wnba_step19e_cooldown_aware_cycle as _wnba_step19e_cooldown_aware_cycle

_wnba_step19e_cooldown_aware_cycle.install_step19e_cooldown_aware_cycle()
