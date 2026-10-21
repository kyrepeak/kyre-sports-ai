"""Canonical-ID finalizer for the single NBA enrichment router."""
from __future__ import annotations

from . import nba_pra_enrichment_core_v1 as _core
from . import nba_pra_enrichment_v1 as _router

_base_collect = _router.collect_nba_pra_enrichment


def collect_nba_pra_enrichment(*args, **kwargs):
    payload = _base_collect(*args, **kwargs)
    profiles = payload.get('profiles') or {}
    for row in profiles.values():
        if row.get('data_state') != 'VERIFIED':
            continue
        canonical_name = str(row.get('player_name') or '').strip()
        if canonical_name:
            row['kyre_player_id'] = _core.kyre_player_id(canonical_name)
    return payload


_router.collect_nba_pra_enrichment = collect_nba_pra_enrichment
_core.collect_nba_pra_enrichment = collect_nba_pra_enrichment
