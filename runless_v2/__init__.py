"""Runless V2 durable proof authority."""

VERSION = "RUNLESS_V2"
__version__ = "2.0.0"

# Apply bounded identity normalization before registering/finalizing the single
# NBA enrichment router. These modules perform no network I/O at import time.
from . import nba_pra_cbs_alias_patch_v1 as _nba_pra_cbs_alias_patch_v1  # noqa: E402,F401
from . import nba_pra_enrichment_v1 as _nba_pra_enrichment_v1  # noqa: E402,F401
from . import nba_pra_canonical_id_patch_v1 as _nba_pra_canonical_id_patch_v1  # noqa: E402,F401
