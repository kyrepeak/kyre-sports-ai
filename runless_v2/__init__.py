"""Runless V2 durable proof authority."""

VERSION = "RUNLESS_V2"
__version__ = "2.0.0"

# Server-side compatibility composition: keep the existing Kyre Sports API
# player-context route stable while enriching its response with verified NBA
# Stats usage metadata. Application clients still have one Kyre gateway.
from . import nba_pra_player_context_enrichment_v2 as _nba_pra_player_context_enrichment_v2  # noqa: E402,F401

# Live-acceptance normalization repair: preserve verified opponent metadata in
# history rows without changing the public Kyre Sports API route or fabricating
# missing source fields.
from . import nba_pra_live_acceptance_repair_v1 as _nba_pra_live_acceptance_repair_v1  # noqa: E402,F401

# Page-2 role completeness successor: NBA Stats stays primary; only players still
# missing verified usage are enriched from Basketball-Reference Advanced through
# the same Kyre Sports API player-context route.
from . import nba_pra_usage_fallback_v2 as _nba_pra_usage_fallback_v2  # noqa: E402,F401

# WNBA PRA Page 1 final-polish successor: preserve the frozen one-read route
# while enriching display identity only from already-verified WNBA projection IDs.
from . import wnba_pra_page1_final_polish_runtime_v1 as _wnba_pra_page1_final_polish_runtime_v1  # noqa: E402,F401

# API2 hard-isolation repair: api2-* proof workstreams must resolve Step 2A
# lease/registry authority only from API2-owned control-state branches. Legacy
# and non-API2 Runless proof behavior is preserved by the additive adapter.
from . import api2_authority_isolation_v1 as _api2_authority_isolation_v1  # noqa: E402,F401
