"""API 2 Finalization Authority V1 Step 5 — Authority Garbage Collector.

TDD RED stub. The production implementation is intentionally absent here.
"""
from __future__ import annotations

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
GITHUB_ACTIONS_FALLBACK = 0


class AuthorityGarbageCollectorFailure(RuntimeError):
    pass


def collect_authority_garbage(**kwargs):
    raise NotImplementedError("STEP5_AUTHORITY_GC_NOT_IMPLEMENTED")
