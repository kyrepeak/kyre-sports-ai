# Universal Sports Source Finalization V1 Step 8 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the eight-step program with a deterministic end-to-end integration certifier that proves provider registry → field routing → canonical identity/field health → minimum trustworthy quorum → source receipt → finalization can compose without page-wide provider authority, product/model mutation, Render dependency, or GitHub Actions fallback.

**Architecture:** Add one pure Step-8 orchestration/certification module that consumes the frozen Step-2 through Step-6 contracts and a deterministic scenario. It filters observations by Step-5 field-health eligibility before Step-4 quorum evaluation, emits a Step-6 receipt only for accepted decisions, binds prior Step-1 through Step-7 freeze tokens, and produces a tamper-evident certification summary. Step-7 finalization remains the only final freeze mutation owner.

**Tech Stack:** Python 3.13, pytest, existing Universal Sports V1 modules, Runless V2 exact-head proof, GitHub Finalization Ledger V2.

**Spec:** `docs/superpowers/specs/2026-10-12-universal-sports-source-finalization-v1-design.md`

## Global Constraints
- Step 2A single-authority execution remains mandatory.
- `DATA_FIELD` remains the routing unit.
- No page-wide provider authority.
- Active providers means actually consulted providers only.
- Same-semantic-metric fallbacks only.
- Canonical IDs remain KYRE/internal; provider IDs are aliases.
- Field-health inspection does not itself activate a provider.
- Minimum trustworthy quorum early-stop remains mandatory.
- No sports product/runtime/model/projection mutation.
- Render dependency is false.
- GitHub Actions fallback remains 0.
- Steps 1–7 remain frozen and are consumed, not modified.
- GREEN + FROZEN requires exact-head proof, merge identity, finalization ledger persistence, and independent readback.

## Review Focus
- An unhealthy primary provider must not become active merely because it is first in route order.
- A healthy fallback quorum must preserve route order and stop immediately when minimum quorum is satisfied.
- Ambiguous or unresolved canonical identity must fail closed before a receipt is emitted.
- Off-route or semantically incompatible observations must fail closed rather than be blended.
- Tampering with a prior freeze token, component contract, or final receipt must invalidate Step-8 certification.

---

### Task 1: Full Integration Certifier

**Files:**
- Create: `devsystem/universal_sports_full_integration_certifier_v1.py`
- Create: `tests/test_devsystem_universal_sports_full_integration_step8_v1.py`

**Interfaces:**
- Consumes: Step-1 architecture contract constants; Step-2 registry; Step-3 router policy; Step-4 trust policy; Step-5 identity/health contract + snapshot; Step-6 source receipt contract; Step-7 freeze token.
- Produces: `certify_full_integration(...) -> dict[str, Any]` and `validate_full_integration_contract(...) -> dict[str, Any]`.

- [ ] Write failing tests for the NBA-injuries fallback-quorum happy path and review-focus failures.
- [ ] Run focused Step-8 tests and confirm RED because `devsystem.universal_sports_full_integration_certifier_v1` does not exist.
- [ ] Implement the minimal certifier without modifying Steps 1–7.
- [ ] Run focused Step-8 tests and confirm GREEN.
- [ ] Run Step-2 through Step-7 regression suites plus Python compile.

### Task 2: Step-8 Certification Contract + Proof Plan

**Files:**
- Create: `devsystem/contracts/universal-sports-full-integration-v1.json`
- Create: `devsystem/runless_proof_plans/universal-sports-source-finalization-v1-step8.json`
- Create: `devsystem/execution_plans/universal-sports-source-finalization-v1-step8.json`
- Create: `devsystem/task_ledgers/universal-sports-source-finalization-v1-step8.json`

**Interfaces:**
- Consumes: Task-1 certifier and frozen Step-1 through Step-7 tokens.
- Produces: exact Step-8 proof identity and freeze token `UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP8_FULL_INTEGRATION_CERTIFICATION_FROZEN`.

- [ ] Lock prior-freeze lineage and Step-8 invariants in the contract.
- [ ] Bind focused integration + prior-step regression + compile commands in the Runless proof plan.
- [ ] Verify JSON contracts parse and exact artifacts are listed.
- [ ] Obtain one exact-head Runless V2 proof for the final candidate.
- [ ] Merge only that certified exact head.
- [ ] Persist the Step-8 freeze record through the existing finalization authority and independently read back the manifest/record chain.
- [ ] Confirm durable Runless state `GREEN_FROZEN`, release the Step-8 scope lease, and certify the eight-step program complete.
