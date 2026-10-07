# API 2 Finalization Authority Step 2 — Ledger Auto-Heal Implementation Plan

**Goal:** Eliminate split-brain completion by making stale task-ledger terminal metadata repairable only from Step 1 canonical frozen-registry + Runless truth.

**Architecture:** Add one pure auto-heal planner above `canonical_completion_resolver_v1.resolve_completion`. The planner never writes files or grants mutation authority. It fails closed on task/freeze identity mismatch or invalid canonical evidence; when canonical completion is valid, it returns either one idempotent healed ledger payload or a no-op for an already aligned ledger.

**Constraints:**
- Step 2A before every mutation.
- One active branch/PR/proof chain.
- Runless proof only; GitHub Actions fallback = 0.
- No product/runtime/sports-model changes.
- Step 1 remains frozen and authoritative.
- Unrelated active thaws remain untouched.
- No ledger may manufacture completion.

## Acceptance

- RED is observed while the auto-heal module is absent.
- Valid canonical GREEN_FROZEN evidence can plan a stale-ledger repair.
- Failed/mismatched canonical evidence never plans a write.
- Task/freeze identity mismatch fails closed.
- Already aligned ledger is a no-op.
- Planner never mutates its input.
- A second pass over the healed payload is a no-op.
- Exact candidate is Runless-certified before merge.
- Exact certified head only is merged.
- Post-merge proof is reused without static reexecution.
- `API2_FINALIZATION_AUTHORITY_V1_STEP2_FROZEN` is present in authoritative registry read-back.
