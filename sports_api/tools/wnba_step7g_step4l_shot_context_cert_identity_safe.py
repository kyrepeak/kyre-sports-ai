"""Run the Step-4L live cert against the box-verified identity-safe adapter."""
from __future__ import annotations

from sports_api.tools import wnba_step7g_step4l_shot_context_cert as cert
from sports_api.wnba_step7g_first_party_shot_context_identity_safe import (
    get_first_party_opponent_defense_by_shot_zone_dataset,
    get_first_party_player_shot_chart_dataset,
)

# Rebind only the cert's local direct-call handles. The real FastAPI path below
# is independently bound by the default-OFF Step-7G integration at app import.
cert.get_first_party_player_shot_chart_dataset = (
    get_first_party_player_shot_chart_dataset
)
cert.get_first_party_opponent_defense_by_shot_zone_dataset = (
    get_first_party_opponent_defense_by_shot_zone_dataset
)


if __name__ == "__main__":
    raise SystemExit(cert.main())
