"""Runless V2 durable proof authority."""

VERSION = "RUNLESS_V2"
__version__ = "2.0.0"

# Register the Kyre NBA enrichment route onto the existing NBA PRA API router.
# The module performs no network I/O at import time.
from . import nba_pra_enrichment_v1 as _nba_pra_enrichment_v1  # noqa: E402,F401
