# Guardian Shared Infrastructure Readiness Contract V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a permanent read-only Guardian shared-infrastructure baseline that API 2 and MONSTER can automatically discover without borrowing Guardian execution authority.

**Architecture:** Store shared facts in one Guardian-owned JSON file, validate and load them through one dependency-light Python reader, and expose the preflight requirement at repository entry through `AGENTS.md`. No network service and no sports-feature changes.

**Tech Stack:** Python 3, JSON, pytest, GitHub source control, existing Runless/Vercel/Supabase authority.

**Spec:** `docs/superpowers/specs/2026-10-27-guardian-shared-infrastructure-readiness-contract-v1-design.md`

## Global Constraints

- Guardian, API 2, and MONSTER remain independent systems.
- Readiness is context only, never branch/PR/proof/lease/freeze authority.
- No sports-feature runtime changes.
- No new network dependency.
- Baseline freshness is scoped to shared-infrastructure revision, not every page-only merge.
- One Guardian branch/PR/proof path only.

## Review Focus

- Cross-system state accidentally included in the baseline must fail validation.
- Unknown consumer names must fail closed.
- Baseline drift from the frozen Guardian source-parity manifest must be caught by tests.
- Missing `AGENTS.md` preflight language must fail tests.
- The reader must not perform network or mutation operations.

---

### Task 1: Contract reader and baseline

**Files:**
- Create: `tests/test_guardian_shared_infrastructure_readiness_v1.py`
- Create: `devsystem/guardian_shared_infrastructure_readiness_v1.py`
- Create: `devsystem/guardian_shared_infrastructure_readiness_v1.json`

**Interfaces:**
- Consumes: `devsystem/guardian_source_of_truth_configuration_parity_v1.json` as source-of-truth evidence for current shared facts.
- Produces: `validate_baseline(payload) -> dict` and `load_readiness(consumer_system, repo_root=None) -> dict`.

- [ ] **Step 1:** Write tests asserting API2/MONSTER loads, equivalent shared facts, canonical digest, unknown-consumer rejection, forbidden-authority-key rejection, source-parity values, and no network/mutation flags.
- [ ] **Step 2:** Run the focused test and verify RED because reader/baseline do not exist.
- [ ] **Step 3:** Implement the minimal JSON baseline and Python reader/validator.
- [ ] **Step 4:** Run focused tests and verify GREEN.
- [ ] **Step 5:** Commit Task 1.

### Task 2: Repository-level automatic discovery

**Files:**
- Create: `AGENTS.md`
- Modify: `tests/test_guardian_shared_infrastructure_readiness_v1.py`

**Interfaces:**
- Consumes: Task 1 reader path and contract token.
- Produces: repository entry instructions requiring API 2/MONSTER page agents to load the readiness contract while forbidding borrowed Guardian authority.

- [ ] **Step 1:** Add a failing test for required `AGENTS.md` preflight and isolation language.
- [ ] **Step 2:** Run focused test and verify RED because `AGENTS.md` is absent.
- [ ] **Step 3:** Create minimal `AGENTS.md` instructions.
- [ ] **Step 4:** Run focused tests and verify GREEN.
- [ ] **Step 5:** Commit Task 2.

### Task 3: Regression and freeze proof

**Files:**
- Create: `devsystem/guardian_shared_infrastructure_readiness_contract_v1.json`
- Create: `devsystem/runless_proof_plans/guardian-shared-infrastructure-readiness-contract-v1.json`

**Interfaces:**
- Consumes: Task 1/2 contract and existing Guardian parity/security tests.
- Produces: fail-closed freeze manifest and Runless exact-head proof plan.

- [ ] **Step 1:** Add final contract assertions requiring `state=FROZEN` only after protected merge and post-merge convergence.
- [ ] **Step 2:** Run focused + existing Guardian parity/security regression tests.
- [ ] **Step 3:** Create freeze manifest/proof-plan artifacts with state `OPEN` before merge.
- [ ] **Step 4:** Run exact-head suite, protected Runless gate, merge, and post-merge convergence.
- [ ] **Step 5:** Mark the contract `FROZEN` only after terminal post-merge evidence is green.
