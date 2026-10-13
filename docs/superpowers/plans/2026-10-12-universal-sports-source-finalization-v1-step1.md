# Universal Sports Source Intelligence + Finalization Worker V1 — Step 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lock the universal sports source architecture in machine-checkable form and bootstrap a Render-independent, append-oriented freeze ledger so Step 1 can reach exact GREEN + FROZEN without touching sports product code or the legacy monolithic frozen registry.

**Architecture:** Step 1 adds a pure structured contract certifier plus a pure finalization-bootstrap module. The bootstrap writes only small immutable freeze records and a compact manifest on a dedicated GitHub ledger branch; it never mutates the legacy monolithic registry. Exact artifact identity, proof digest, compare-and-swap preconditions, and independent GitHub readback are required before the Step-1 freeze token is accepted.

**Tech Stack:** Python 3, pytest, JSON, SHA-256 canonical hashing, GitHub contents/ref primitives, existing Runless proof-plan format.

**Spec:** `docs/superpowers/specs/2026-10-12-universal-sports-source-finalization-v1-design.md`

## Global Constraints

- Workstream: `universal-sports-source-finalization-v1`.
- Step: `1/8`.
- Freeze token: `UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP1_ARCHITECTURE_CONTRACT_FROZEN`.
- `DATA_FIELD` remains the routing unit.
- No provider may be the page-wide universal source of truth.
- Approved provider pool and active providers are distinct; active means actually consulted.
- Capability-incompatible metrics may never substitute for each other.
- Minimum trustworthy quorum expands only when required.
- Render dependency for Step-1 freeze is false.
- GitHub Actions fallback is `0`.
- Legacy monolithic frozen-registry mutation is forbidden in Step 1.
- Product/runtime and sports-model mutation are forbidden.
- Step 2A single-authority and workstream isolation remain mandatory.
- No GREEN + FROZEN claim before independent GitHub readback.

## Review Focus

- A contract that accidentally allows page-wide source loyalty must fail certification.
- A fallback rule that permits raw bet count to be replaced by percentage-only data must fail certification.
- A freeze record whose artifact blob map or proof digest changes after hashing must fail validation.
- A manifest update based on a stale revision/hash must fail closed instead of overwriting concurrent state.
- A manifest/readback that points to the wrong merged-main SHA or freeze token must not certify FROZEN.

---

### Task 1: Machine-checkable Step-1 architecture contract

**Files:**
- Create: `devsystem/contracts/universal-sports-source-finalization-v1-step1.json`
- Create: `devsystem/universal_sports_source_finalization_step1_contract_v1.py`
- Test: `tests/test_devsystem_universal_sports_source_finalization_step1_v1.py`

**Interfaces:**
- Consumes: the Step-1 design spec and structured contract JSON.
- Produces: `certify_contract(contract: Mapping[str, Any], spec_text: str) -> dict[str, Any]` and `load_contract(path: Path) -> dict[str, Any]`.

- [ ] **Step 1: Write failing contract-certification tests**

Add tests asserting the valid contract certifies the fixed eight-step program, `DATA_FIELD`, no page-wide source authority, active-provider semantics, capability-compatible fallbacks, minimum-quorum early stop, Render-independent bootstrap, GitHub Actions fallback `0`, legacy-registry isolation, and the exact freeze token. Add negative tests for page-wide source loyalty, incompatible raw-count/percentage substitution, Render-required finalization, and nonzero GitHub Actions fallback.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest -q tests/test_devsystem_universal_sports_source_finalization_step1_v1.py`

Expected: FAIL because the Step-1 contract module/contract file does not yet exist.

- [ ] **Step 3: Implement the structured contract and pure certifier**

Implement `load_contract(path: Path) -> dict[str, Any]` and `certify_contract(contract: Mapping[str, Any], spec_text: str) -> dict[str, Any]` in `devsystem/universal_sports_source_finalization_step1_contract_v1.py`. The certifier must be side-effect free and fail closed on any Global Constraint drift.

- [ ] **Step 4: Run focused tests and compile check**

Run: `python -m pytest -q tests/test_devsystem_universal_sports_source_finalization_step1_v1.py`

Run: `python -m py_compile devsystem/universal_sports_source_finalization_step1_contract_v1.py`

Expected: PASS.

- [ ] **Step 5: Commit Task 1 on the authoritative branch**

Commit message: `feat: lock universal sports source architecture contract`

### Task 2: Render-independent finalization bootstrap

**Files:**
- Create: `devsystem/universal_sports_finalization_bootstrap_v1.py`
- Modify: `tests/test_devsystem_universal_sports_source_finalization_step1_v1.py`

**Interfaces:**
- Consumes: exact merged-main SHA, exact candidate SHA, proof digest, artifact blob map, freeze token, and optional previous manifest.
- Produces:
  - `canonical_hash(value: Mapping[str, Any]) -> str`
  - `build_freeze_record(*, workstream: str, freeze_token: str, merged_main_sha: str, candidate_sha: str, proof_digest: str, artifacts: Mapping[str, str]) -> dict[str, Any]`
  - `validate_freeze_record(record: Mapping[str, Any]) -> dict[str, Any]`
  - `build_manifest(*, previous: Mapping[str, Any] | None, freeze_token: str, record_path: str, record_blob_sha: str, merged_main_sha: str) -> dict[str, Any]`
  - `validate_manifest_transition(previous: Mapping[str, Any] | None, target: Mapping[str, Any]) -> dict[str, Any]`

- [ ] **Step 1: Add failing bootstrap tests**

Add tests proving deterministic hashes, exact SHA validation, `render_dependency=false`, `github_actions_fallback=0`, `legacy_registry_mutation=false`, tamper rejection, genesis manifest creation, monotonic revision, previous-hash chaining, and stale-precondition rejection.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_devsystem_universal_sports_source_finalization_step1_v1.py`

Expected: FAIL because bootstrap functions do not yet exist.

- [ ] **Step 3: Implement the pure bootstrap module**

Implement the five interfaces above. Canonical hashing is lowercase SHA-256 of UTF-8 JSON with recursively sorted keys, `ensure_ascii=True`, separators `(',', ':')`, and the record/manifest hash field excluded from its own hash input.

- [ ] **Step 4: Run focused tests and compile check**

Run: `python -m pytest -q tests/test_devsystem_universal_sports_source_finalization_step1_v1.py`

Run: `python -m py_compile devsystem/universal_sports_finalization_bootstrap_v1.py`

Expected: PASS.

- [ ] **Step 5: Commit Task 2 on the authoritative branch**

Commit message: `feat: add provider-independent finalization bootstrap`

### Task 3: Runless proof metadata and execution ledger

**Files:**
- Create: `devsystem/execution_plans/universal-sports-source-finalization-v1-step1.json`
- Create: `devsystem/runless_proof_plans/universal-sports-source-finalization-v1-step1.json`
- Create: `devsystem/task_ledgers/universal-sports-source-finalization-v1-step1.json`
- Modify: `tests/test_devsystem_universal_sports_source_finalization_step1_v1.py`

**Interfaces:**
- Consumes: Task-1/Task-2 artifacts and existing `devsystem.runless_proof_plan_v1` schema.
- Produces: one valid static Runless proof plan with no public deployment probe and no GitHub Actions fallback.

- [ ] **Step 1: Add failing metadata tests**

Assert the proof plan task/workstream/freeze token are exact, commands are only focused pytest/py_compile/certification commands, artifacts include every Step-1 contract/bootstrap/spec/plan file, public probes are empty, product/runtime scope is false, legacy-registry mutation is false, and GitHub Actions fallback is `0`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `python -m pytest -q tests/test_devsystem_universal_sports_source_finalization_step1_v1.py`

Expected: FAIL because proof metadata does not yet exist.

- [ ] **Step 3: Create execution plan, Runless proof plan, and task ledger**

Use task ID `universal-sports-source-finalization-v1-step1`, workstream `universal-sports-source-finalization-v1`, and the fixed Step-1 freeze token. Public probes remain empty because Step 1 changes no production runtime.

- [ ] **Step 4: Validate proof plan through the existing loader and run all focused commands**

Run: `python -m pytest -q tests/test_devsystem_universal_sports_source_finalization_step1_v1.py`

Run: `python -m py_compile devsystem/universal_sports_source_finalization_step1_contract_v1.py devsystem/universal_sports_finalization_bootstrap_v1.py`

Expected: PASS.

- [ ] **Step 5: Commit Task 3 on the authoritative branch**

Commit message: `chore: compile step1 runless proof contract`

### Task 4: Exact-head proof, merge, and sidecar freeze

**Files:**
- Create after merge on dedicated ledger branch: `devsystem/finalization_ledger_v2/records/UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP1_ARCHITECTURE_CONTRACT_FROZEN.json`
- Create after merge on dedicated ledger branch: `devsystem/finalization_ledger_v2/manifest.json`
- No legacy registry files may be modified.

**Interfaces:**
- Consumes: exact candidate head, exact artifact blob map, focused test results, and the pure bootstrap module.
- Produces: exact proof digest, merged-main identity, immutable freeze record, manifest revision/hash, and independent GitHub readback.

- [ ] **Step 1: Verify exact candidate head and artifact blobs**

Read the authoritative branch head once. Fetch every proof-plan artifact at that exact SHA and record its Git blob SHA. Abort on branch movement or missing artifact.

- [ ] **Step 2: Run the minimum authoritative static proof on exact candidate content**

Execute the Runless proof-plan commands against content verified to match the candidate artifact blobs. Record command results and compute one deterministic proof digest bound to candidate SHA + artifact map + command evidence. Do not start a second proof path if this proof succeeds.

- [ ] **Step 3: Create one PR and merge only the exact proven head**

Open one PR from `api2-universal-sports-source-finalization-v1-step1` to `main`. Before merge, confirm PR head still equals the proven candidate SHA. Merge once; record merged-main SHA.

- [ ] **Step 4: Verify post-merge artifact identity instead of rerunning redundant proof**

Compare each Step-1 artifact blob on merged main with the exact proven candidate blob map. If identical, reuse static proof under Runless Final-Mile semantics. If any artifact differs, stop and classify exact-head drift.

- [ ] **Step 5: Create or reuse the dedicated finalization-ledger branch**

Use one branch named `monster-finalization-ledger-v2`. If absent, create it from the exact merged-main SHA. If present, read its manifest once and use its exact current revision/hash as compare-and-swap preconditions.

- [ ] **Step 6: Build and write the immutable freeze record**

Use `build_freeze_record(...)` with exact merged-main SHA, candidate SHA, proof digest, and merged-main artifact blob map. Write only the fixed freeze-record path. If the record already exists, require byte/hash identity; otherwise fail closed.

- [ ] **Step 7: Build and write the compact manifest**

Fetch the written record to obtain its Git blob SHA. Build the genesis or next manifest with `build_manifest(...)`. Write/update `devsystem/finalization_ledger_v2/manifest.json` only when the expected prior blob/revision/hash still matches.

- [ ] **Step 8: Independent readback proof**

Read both record and manifest from GitHub. Validate record hash, manifest state hash, exact freeze token, exact record blob SHA, exact merged-main SHA, monotonic revision, and `legacy_registry_mutation=false`.

Expected terminal state: `GREEN + FROZEN` for Step 1 only.

- [ ] **Step 9: Confirm legacy registry untouched and release Step-1 authority**

Verify `devsystem/frozen_artifact_registry_state_v1.json` was not changed by this workstream. Record Step-1 completion and set next legal action to `START_STEP2_CREDIBLE_PROVIDER_REGISTRY`.
