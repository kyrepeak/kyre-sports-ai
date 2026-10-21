"""Runless V2 durable proof authority."""

VERSION = "RUNLESS_V2"
__version__ = "2.0.0"

# Server-side compatibility composition: keep the existing Kyre Sports API
# player-context route stable while enriching its response with verified NBA
# Stats usage metadata. Application clients still have one Kyre gateway.
from . import nba_pra_player_context_enrichment_v2 as _nba_pra_player_context_enrichment_v2  # noqa: E402,F401
