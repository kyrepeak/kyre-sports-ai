# Universal Sports Source + Finalization V1 — Step 5 Provider Health + Canonical Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Step 5/8, a deterministic provider-health and canonical-identity layer that keeps API 2 / MONSTER canonical team, player, and game IDs internal, resolves provider aliases fail-closed, and evaluates provider health per data field before Step-4 quorum evidence is accepted.

**Architecture:** Step 5 adds a pure read-only identity/health contract and adapter. It extends the existing `unified_data_identity_provider_health_graph_v1.py` architecture without creating a second mutation owner: canonical identities and provider aliases are immutable snapshot inputs, provider health is evaluated at `DATA_FIELD` scope, route order is preserved, unhealthy/unknown field states are rejected explicitly, and no provider is marked active merely because health metadata was inspected. The output is a deterministic Step-5 context for Step 6 provenance; Step 5 performs zero provider/network calls.

**Tech Stack:** Python 3, JSON contracts, pytest, Runless exact-head proof, provider-independent sidecar finalization ledger.

**Spec:** `docs/superpowers/specs/2026-10-12-universal-sports-source-finalization-v1-design.md`

## Global Constraints

- Workstream ID is `universal-sports-source-finalization-v1`.
- Program step is `5/8`; program total is 8.
- Routing unit remains exactly `DATA_FIELD`.
- Steps 1–4 are frozen inputs and may not be mutated.
- API 2 / MONSTER owns canonical team, player, and game IDs; provider IDs and names are aliases only.
- Ambiguous identity fails closed.
- Provider health is capability/field-specific, not a page-wide or provider-wide master boolean.
- Health inspection must not label an unused provider as active.
- Route order is preserved; Step 5 may block an unhealthy field/provider but may not invent a new route.
- Every field-health record carries freshness age, quality score, validation result, fallback rank, and rejection reason when unusable.
- No provider/network calls, product/runtime mutation, sports-model mutation, or provider fan-out are introduced.
- Existing unified identity/provider-health graph remains read-only compatibility architecture; no duplicate mutation ownership is introduced.
- Render dependency is false; GitHub Actions fallback is 0.
- Exact-head `runless-final-gate` from GitHub App `5204253` is required before merge.
- Final GREEN + FROZEN requires merged-main identity plus sidecar ledger append and independent GitHub readback.

## Review Focus

- Provider-specific aliases cannot override or create canonical IDs.
- A provider healthy for one field can be unhealthy/unknown for another without global source lock.
- Ambiguous global/provider-specific alias collisions fail closed before quorum.
- Route-health evaluation preserves Step-3 provider order and never activates providers by inspection alone.
- Snapshot/contract fingerprints are deterministic and tamper-evident.

---

### Task 1: Provider Health + Canonical Identity

**Files:**
- Create: `devsystem/contracts/universal-sports-identity-health-v1.json`
- Create: `devsystem/universal_sports_identity_health_v1.py`
- Test: `tests/test_devsystem_universal_sports_identity_health_step5_v1.py`
- Create: `devsystem/execution_plans/universal-sports-source-finalization-v1-step5.json`
- Create: `devsystem/runless_proof_plans/universal-sports-source-finalization-v1-step5.json`
- Create: `devsystem/task_ledgers/universal-sports-source-finalization-v1-step5.json`

**Interfaces:**
- Consumes: frozen Step-2 provider IDs/capabilities, frozen Step-3 route packets, canonical identity snapshots, and field-health observations.
- Produces: `load_identity_health_contract(path)`, `validate_identity_health_contract(contract)`, `seal_identity_health_snapshot(snapshot)`, `validate_identity_health_snapshot(snapshot)`, `resolve_canonical_identity(contract, snapshot, *, entity_type, value, provider_id=None)`, and `build_identity_health_context(contract, snapshot, route, *, entity_type, value, provider_id=None)`.
- Context exposes: canonical entity ID/key/name, aliases used, route provider order, field-aware provider health records, usable provider IDs, rejected providers with reason, deterministic context/identity IDs, zero active providers, and zero-network/fabrication invariants.

- [ ] **Step 1: Write failing Step-5 contract tests**

Pin contract certification, canonical team/player/game resolution, provider-specific aliases, unresolved/ambiguous fail-closed behavior, field-specific health divergence, unknown/unhealthy blocking, route-order preservation, no active-provider inflation, deterministic IDs, snapshot/contract tamper detection, and frozen Step-2/3/4 regression invariants.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_devsystem_universal_sports_identity_health_step5_v1.py`
Expected before implementation: collection/import failure because `devsystem.universal_sports_identity_health_v1` does not exist.

- [ ] **Step 3: Implement immutable identity + health adapter**

Validate contract/snapshot fingerprints, canonical IDs and alias scopes, field-health states/freshness/quality/validation fields, route identity and provider order, fail-closed ambiguity/unresolved identity, and deterministic health context without network calls or mutation.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest -q tests/test_devsystem_universal_sports_identity_health_step5_v1.py`
Expected: all Step-5 tests pass.

- [ ] **Step 5: Run syntax + frozen-regression verification**

Run: `python -m py_compile devsystem/universal_sports_identity_health_v1.py`
Expected: exit 0.

Run: `python -m pytest -q tests/test_devsystem_universal_sports_provider_registry_step2_v1.py tests/test_devsystem_universal_sports_field_router_step3_v1.py tests/test_devsystem_universal_sports_trust_quorum_step4_v1.py tests/test_devsystem_universal_sports_identity_health_step5_v1.py tests/test_devsystem_unified_data_identity_provider_health_graph_v1.py`
Expected: all frozen Step-2/3/4, Step-5, and compatibility-graph tests pass.

- [ ] **Step 6: Exact-head Runless proof and merge**

Bind one Step-5 Runless proof plan to the exact PR head. Require `runless-final-gate` success from App `5204253`; GitHub Actions fallback remains 0. Merge only the certified exact head.

- [ ] **Step 7: Immediate implementation/freeze**

Read back merged `main`, preserve Steps 1–4 frozen records, and finalize Step 5 under freeze token `UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP5_PROVIDER_HEALTH_CANONICAL_IDENTITY_FROZEN` using the existing provider-independent sidecar finalization contract. Certify GREEN + FROZEN only after authoritative record + manifest readback.
