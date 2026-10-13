# Universal Sports Source + Finalization V1 — Step 3 Field-Level Source Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Step 3/8, a deterministic field-level source router that converts the Step-2 approved provider registry into one capability-compatible ordered route per sport/data field without consulting providers or creating page-wide source authority.

**Architecture:** Step 3 consumes `devsystem/contracts/universal-sports-provider-registry-v1.json` through the validated Step-2 registry API. A small immutable router-policy contract defines source-type preference per semantic field; `route_field()` filters by exact capability + sport, blocks credentialed-but-unconfigured providers, orders remaining candidates deterministically, and emits a route packet with zero active providers and zero network calls. Step 4 will consume these route packets to apply trust/quorum policy; Step 3 does not accept data values or fabricate quorum.

**Tech Stack:** Python 3, JSON contracts, pytest, Runless exact-head proof, provider-independent sidecar finalization ledger.

**Spec:** `docs/superpowers/specs/2026-10-12-universal-sports-source-finalization-v1-design.md`

## Global Constraints

- Workstream ID is `universal-sports-source-finalization-v1`.
- Program step is `3/8`; program total is 8.
- Routing unit remains exactly `DATA_FIELD`.
- No provider may become page-wide source authority.
- Fallback substitution is allowed only within the same semantic metric/capability.
- Approved providers are not active providers; active means actually consulted only.
- Step 3 performs zero provider/network calls.
- Credential-required providers with configuration state `NOT_CLAIMED` are not eligible route candidates and must be surfaced as blocked.
- Step 4 owns trust/quorum acceptance; Step 3 only constructs the candidate route.
- Step 1 and Step 2 frozen artifacts remain unchanged.
- No product/runtime or projection/model mutation.
- Render dependency is false; GitHub Actions fallback is 0.
- Exact-head `runless-final-gate` from GitHub App `5204253` is required before merge.
- Final GREEN + FROZEN requires merged-main identity plus independent sidecar freeze-record/manifest readback.

## Review Focus

- Unknown sport or field fails closed with no candidates and no network calls.
- Public bet count can never silently route to bet-percentage or money-percentage providers.
- Credentialed-but-unconfigured sources are blocked rather than treated as reachable candidates.
- Two identical requests against identical registry/policy inputs produce the same route ID and candidate order.
- A provider approved for another sport/capability never leaks into the current field route.

---

### Task 1: Field-Level Source Router

**Files:**
- Create: `devsystem/contracts/universal-sports-field-router-v1.json`
- Create: `devsystem/universal_sports_field_router_v1.py`
- Test: `tests/test_devsystem_universal_sports_field_router_step3_v1.py`
- Create: `devsystem/execution_plans/universal-sports-source-finalization-v1-step3.json`
- Create: `devsystem/runless_proof_plans/universal-sports-source-finalization-v1-step3.json`
- Create: `devsystem/task_ledgers/universal-sports-source-finalization-v1-step3.json`

**Interfaces:**
- Consumes: `load_registry(path)`, `validate_registry(registry)`, and `providers_for_capability(registry, *, capability, sport)` from `devsystem.universal_sports_provider_registry_v1`.
- Produces: `load_router_policy(path) -> dict[str, Any]`, `validate_router_policy(policy, registry) -> dict[str, Any]`, and `route_field(registry, policy, *, sport: str, field: str) -> dict[str, Any]` from `devsystem.universal_sports_field_router_v1`.
- Route packets expose: `status`, `route_id`, `sport`, `field`, `semantic_metric_id`, `primary_provider_id`, `fallback_provider_ids`, `eligible_provider_ids`, `blocked_providers`, `active_provider_ids`, `routing_unit`, `page_wide_source_authority`, `network_calls`, and `fabrication`.

- [ ] **Step 1: Write the failing Step-3 contract tests**

Tests assert the module is initially absent, then pin certification, exact capability filtering, deterministic ordering, credential blocking, semantic incompatibility fail-closed behavior, unknown sport/field fail-closed behavior, and fingerprint tamper detection.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_devsystem_universal_sports_field_router_step3_v1.py`
Expected before implementation: collection/import failure because `devsystem.universal_sports_field_router_v1` does not exist.

- [ ] **Step 3: Implement router policy + minimal router**

`validate_router_policy()` must verify the Step-2 registry first, require one policy entry for every registry capability with matching semantic metric ID, prohibit page-wide authority/network/product/model mutation, reject duplicate/unknown source types, and verify a canonical `router_id` fingerprint.

`route_field()` must validate both inputs; filter with `providers_for_capability()`; partition statically blocked credential-required/`NOT_CLAIMED` providers; order usable providers by the field policy's source-type rank then stable provider ID; set the first usable provider as `primary_provider_id`; put the rest in `fallback_provider_ids`; leave `active_provider_ids=[]`; return `UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION` when no usable compatible source remains; and compute `route_id` deterministically from immutable route inputs/output.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest -q tests/test_devsystem_universal_sports_field_router_step3_v1.py`
Expected: all Step-3 tests pass.

- [ ] **Step 5: Run syntax + regression verification**

Run: `python -m py_compile devsystem/universal_sports_field_router_v1.py`
Expected: exit 0.

Run: `python -m pytest -q tests/test_devsystem_universal_sports_provider_registry_step2_v1.py tests/test_devsystem_universal_sports_field_router_step3_v1.py`
Expected: all Step-2 + Step-3 tests pass.

- [ ] **Step 6: Exact-head Runless proof and merge**

Bind one Step-3 Runless proof plan to the exact PR head. Require `runless-final-gate` success from App `5204253`; GitHub Actions fallback remains 0. Merge only the certified exact head.

- [ ] **Step 7: Immediate implementation/freeze**

Read back merged `main`, collect exact artifact blob SHAs, append freeze token `UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP3_FIELD_LEVEL_SOURCE_ROUTER_FROZEN` to the sidecar ledger using exact manifest CAS, and independently read back the record + manifest before certifying GREEN + FROZEN.
