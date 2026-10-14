# Universal Sports Source + Finalization V1 — Step 4 Trust + Quorum Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Step 4/8, a deterministic field-level Trust + Quorum Engine that consumes frozen Step-3 route packets, accepts the minimum trustworthy evidence required by policy, stops immediately when satisfied, and fails closed on stale, ambiguous, incompatible, or exhausted evidence.

**Architecture:** Step 4 adds an immutable trust-policy contract for all 15 semantic data fields and a pure evaluator with zero provider/network calls. `evaluate_quorum()` processes only Step-3 eligible providers in route order, counts only actually consulted observations as active, enforces freshness/quality/quorum/tolerance policy, returns one of the architecture's locked quorum terminal states, and never blends values or substitutes incompatible metrics. Step 5 retains provider-health and canonical-identity resolution ownership; Step 4 only consumes the route and supplied normalized observations.

**Tech Stack:** Python 3, JSON contracts, pytest, Runless exact-head proof, provider-independent sidecar finalization ledger.

**Spec:** `docs/superpowers/specs/2026-10-12-universal-sports-source-finalization-v1-design.md`

## Global Constraints

- Workstream ID is `universal-sports-source-finalization-v1`.
- Program step is `4/8`; program total is 8.
- Routing unit remains exactly `DATA_FIELD`.
- No provider may become page-wide source authority.
- Step 3 routes remain frozen and are consumed without mutation.
- Active providers means actually consulted observations only.
- Minimum trustworthy quorum stops immediately when policy is satisfied.
- Expansion occurs only for stale data, low quality, disagreement, insufficient evidence, or missing evidence.
- Incompatible semantic metrics may never count toward quorum.
- Accepted values are selected from agreeing observations and are never averaged/blended merely to force agreement.
- Ambiguous identity fails closed; Step 5 will own identity resolution itself.
- Step 4 performs zero provider/network calls and no product/runtime or sports-model mutation.
- Steps 1–3 frozen artifacts remain unchanged.
- Render dependency is false; GitHub Actions fallback is 0.
- Exact-head `runless-final-gate` from GitHub App `5204253` is required before merge.
- Final GREEN + FROZEN requires merged-main identity plus immediate implementation/freeze under the existing sidecar finalization contract.

## Review Focus

- A provider outside the Step-3 eligible route can never be injected into quorum.
- Stale or low-quality evidence is rejected without being counted toward quorum.
- Disagreement expands only to remaining compatible route candidates and fails closed when exhausted.
- Single-authority fields stop after one valid primary observation; quorum fields stop at the minimum matching set.
- Numeric tolerance may establish agreement but must never alter or average the accepted source value.

---

### Task 1: Trust + Quorum Engine

**Files:**
- Create: `devsystem/contracts/universal-sports-trust-quorum-v1.json`
- Create: `devsystem/universal_sports_trust_quorum_v1.py`
- Test: `tests/test_devsystem_universal_sports_trust_quorum_step4_v1.py`
- Create: `devsystem/execution_plans/universal-sports-source-finalization-v1-step4.json`
- Create: `devsystem/runless_proof_plans/universal-sports-source-finalization-v1-step4.json`
- Create: `devsystem/task_ledgers/universal-sports-source-finalization-v1-step4.json`

**Interfaces:**
- Consumes: immutable Step-3 route packets from `route_field()` with `route_id`, field/semantic metric, ordered eligible providers, zero active providers, and fail-closed route status.
- Produces: `load_trust_policy(path) -> dict[str, Any]`, `validate_trust_policy(policy) -> dict[str, Any]`, and `evaluate_quorum(policy, route, observations, *, identity_ambiguous=False) -> dict[str, Any]`.
- Decisions expose: terminal `status`, deterministic `decision_id`, `active_provider_ids`, `selected_provider_ids`, rejected attempts, remaining expansion providers, accepted value + fingerprint when accepted, quorum/early-stop state, and zero-network/fabrication invariants.

- [ ] **Step 1: Write failing Step-4 contract tests**

Pin policy certification, single-authority early stop, two-source quorum, fallback quorum after stale primary, disagreement expansion, compatible-source exhaustion, stale fail-closed, ambiguous-identity fail-closed, off-route provider rejection, semantic mismatch rejection, low-quality expansion, numeric tolerance without blending, deterministic/value-sensitive decision IDs, and policy fingerprint tamper detection.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_devsystem_universal_sports_trust_quorum_step4_v1.py`
Expected before implementation: collection/import failure because `devsystem.universal_sports_trust_quorum_v1` does not exist.

- [ ] **Step 3: Implement immutable trust policy + minimal evaluator**

Validate all 15 semantic field policies, canonical policy fingerprint, Step-3 route invariants, exact semantic compatibility, observation quality/freshness, route-order processing, single-authority and quorum acceptance, deterministic tolerance comparison, minimum-evidence early stop, fallback-quorum classification, expansion reasons, fail-closed exhaustion, and deterministic decision/value fingerprints.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `python -m pytest -q tests/test_devsystem_universal_sports_trust_quorum_step4_v1.py`
Expected: all Step-4 tests pass.

- [ ] **Step 5: Run syntax + frozen-regression verification**

Run: `python -m py_compile devsystem/universal_sports_trust_quorum_v1.py`
Expected: exit 0.

Run: `python -m pytest -q tests/test_devsystem_universal_sports_provider_registry_step2_v1.py tests/test_devsystem_universal_sports_field_router_step3_v1.py tests/test_devsystem_universal_sports_trust_quorum_step4_v1.py`
Expected: all Step-2 + Step-3 + Step-4 tests pass.

- [ ] **Step 6: Exact-head Runless proof and merge**

Bind one Step-4 Runless proof plan to the exact PR head. Require `runless-final-gate` success from App `5204253`; GitHub Actions fallback remains 0. Merge only the certified exact head.

- [ ] **Step 7: Immediate implementation/freeze**

Read back merged `main`, preserve Steps 1–3 frozen artifacts, and finalize Step 4 under freeze token `UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP4_TRUST_QUORUM_ENGINE_FROZEN` using the existing provider-independent finalization contract. Certify GREEN + FROZEN only after authoritative merged-main/proof readback.
