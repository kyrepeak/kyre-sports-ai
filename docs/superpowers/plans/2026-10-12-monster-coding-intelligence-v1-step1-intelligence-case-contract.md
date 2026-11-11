# MONSTER Coding Intelligence V1 Step 1 — Intelligence Case Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and freeze a pure, deterministic Intelligence Case Contract that converts an engineering problem into a machine-checkable normalized case without diagnosing root cause or granting mutation authority.

**Architecture:** Add one dependency-light DevSystem module that validates and normalizes a case packet, generates a deterministic case ID, serializes it canonically, and renders it in fixed order. Keep evidence classification, hypotheses, root-cause reasoning, strategy selection, and execution authority out of Step 1. Close the step with focused TDD, existing Runless proof, exact-head verification, and the existing frozen registry.

**Tech Stack:** Python 3 standard library, pytest, DevSystem JSON execution/runless/task-ledger conventions, existing Step 2A/scope lease, existing Runless proof plane, existing frozen-artifact registry.

**Spec:** `docs/superpowers/specs/2026-10-12-monster-coding-intelligence-v1-design.md`

## Global Constraints

- Step 1 implements only `INTELLIGENCE CASE CONTRACT V1`.
- Intelligence remains separate from the production control plane until Step 10 certification.
- No network calls, provider calls, deployments, product/runtime/model mutations, or GitHub mutation authority may exist inside the case-contract module.
- Do not implement evidence ranking, failure classification, hypothesis generation, root-cause inference, blast-radius reasoning, contradiction resolution, lessons, or outcome learning in Step 1.
- Reuse existing Step 2A, Runless, Finalization Authority, scope lease, anti-loop, and frozen-registry systems; do not create parallel authority systems.
- Unknown information must remain explicit rather than guessed.
- Visible symptom must remain separate from causal diagnosis.
- GitHub Actions fallback remains `0`.
- Freeze token: `MONSTER_CODING_INTELLIGENCE_V1_STEP1_INTELLIGENCE_CASE_CONTRACT_FROZEN`.

## Canonical Case Schema

Normalized output fields are exactly:

- `schema_version`: integer `1`
- `version`: `MONSTER_CODING_INTELLIGENCE_V1_STEP1_CASE_CONTRACT_V1`
- `case_id`: deterministic `CASE-<24 uppercase hex>` generated from normalized semantic fields
- `workstream_id`: required stable workstream identifier
- `goal`: required normalized text
- `visible_symptom`: required normalized text
- `success_condition`: required normalized text describing observable outcome
- `solved_when`: required normalized text describing terminal observable success
- `constraints`: normalized sorted unique list or `null` when unknown
- `do_not_change`: normalized sorted unique list or `null` when unknown
- `required_changes`: normalized sorted unique list or `null` when unknown
- `affected_systems`: normalized sorted unique list or `null` when unknown
- `environment`: normalized text or `null` when unknown
- `current_known_state`: normalized sorted unique list or `null` when unknown
- `suspected_subsystems`: normalized sorted unique list or `null` when unknown
- `network_calls`: `false`
- `auto_mutate`: `false`
- `may_modify_product_runtime`: `false`
- `mutation_authority_granted`: `false`
- `github_actions_fallback`: `0`

Accepted raw-input fields are only the semantic fields above excluding generated/control fields. Unknown extra fields fail closed. Step-2-and-later causal fields such as `root_cause`, `diagnosis`, `hypotheses`, `evidence`, or `confidence` are therefore rejected in Step 1.

### Normalization rules

- Human text: Unicode NFKC normalization, trim, collapse internal whitespace, strip terminal period-only punctuation, and casefold for deterministic machine identity.
- Workstream ID: trim + casefold; must match `[a-z0-9][a-z0-9._/-]*`.
- Collection fields: `null` stays unknown; an explicitly empty collection stays `[]`; non-empty values normalize item-by-item, deduplicate, and sort.
- Caller input is never mutated.
- `case_id` is SHA-256 over canonical JSON of normalized semantic fields, truncated to 24 hex characters and uppercased.
- Canonical serialization uses sorted keys and deterministic separators.

### Structural contradiction rule

If any normalized item appears in both `required_changes` and `do_not_change`, validation fails closed with `IntelligenceCaseValidationFailure`.

### Observable-success rule

`success_condition` and `solved_when` reject implementation-only terminal statements such as exactly `merge pr`, `deploy`, `commit`, `push`, `patch`, or `edit file`. They may mention implementation actions only when the normalized statement also contains an observable outcome beyond the action.

## Review Focus

- Missing optional context must serialize as `null`, while an explicit empty collection must remain `[]`.
- Collection order, duplicate entries, casing, whitespace, Unicode compatibility forms, and terminal periods must not change normalized output or `case_id`.
- A caller must not be able to smuggle `root_cause`, `diagnosis`, or another later-step reasoning field into Step 1.
- Exact overlap between `required_changes` and `do_not_change` must fail closed.
- Rendering and canonical JSON must remain deterministic regardless of input dictionary insertion order.

---

### Task 1: Pure Intelligence Case Contract + Deterministic Rendering

**Files:**
- Create: `devsystem/monster_coding_intelligence_case_contract_v1.py`
- Create: `tests/test_devsystem_monster_coding_intelligence_case_contract_v1.py`

**Interfaces:**
- Consumes: `Mapping[str, Any]` raw case packet.
- Produces: `normalize_intelligence_case(packet: Mapping[str, Any]) -> dict[str, Any]`.
- Produces: `serialize_intelligence_case(packet: Mapping[str, Any]) -> str`.
- Produces: `render_intelligence_case(packet: Mapping[str, Any]) -> str`.
- Produces: `IntelligenceCaseValidationFailure(RuntimeError)`.
- Produces constants `VERSION`, `NETWORK_CALLS=False`, `AUTO_MUTATE=False`, `MAY_MODIFY_PRODUCT_RUNTIME=False`, `MUTATION_AUTHORITY_GRANTED=False`, `GITHUB_ACTIONS_FALLBACK=0`.

- [ ] **Step 1: Write failing normalization tests**

Create focused tests that prove:

```python
BASE_CASE = {
    "workstream_id": "CFB-CARDS-DEBUG",
    "goal": "CFB cards appear normally.",
    "visible_symptom": "Expected games / cards are absent.",
    "success_condition": "Expected slate appears with verified underlying data.",
    "solved_when": "Expected cards are visibly present with verified data.",
    "constraints": ["Use existing multi-source architecture"],
    "do_not_change": ["Visual design", "Navigation"],
    "required_changes": None,
    "affected_systems": ["Schedule", "Rendering"],
    "environment": None,
    "current_known_state": None,
    "suspected_subsystems": ["rendering", "schedule"],
}
```

Assertions must cover:
- required fields normalize and generated control fields are present;
- input mapping remains unchanged;
- missing optional fields become `None`;
- explicit empty lists remain `[]`;
- list values deduplicate and sort;
- equivalent casing/whitespace/order/terminal periods produce identical normalized semantic fields and identical `case_id`;
- `case_id` matches `^CASE-[0-9A-F]{24}$`;
- `visible_symptom` exists and no `root_cause` field is generated;
- invalid workstream ID fails;
- missing required core fields fail;
- non-string collection entries fail;
- unknown extra field fails;
- explicit `root_cause`, `diagnosis`, or `hypotheses` input fails;
- required/do-not-change overlap fails;
- implementation-only `success_condition` or `solved_when` fails.

- [ ] **Step 2: Run tests and confirm RED**

Run:

```bash
python -m pytest -q tests/test_devsystem_monster_coding_intelligence_case_contract_v1.py
```

Expected: import/collection failure because `devsystem.monster_coding_intelligence_case_contract_v1` does not yet exist.

- [ ] **Step 3: Implement minimal normalizer and validator**

Create `devsystem/monster_coding_intelligence_case_contract_v1.py` with exact public signatures:

```python
class IntelligenceCaseValidationFailure(RuntimeError): ...

def normalize_intelligence_case(packet: Mapping[str, Any]) -> dict[str, Any]: ...
```

Implementation requirements:
- standard library only (`hashlib`, `json`, `re`, `unicodedata`, collections/typing helpers);
- copy caller input before normalization;
- enforce exact allowed input keys and required core keys;
- normalize according to Global Constraints;
- preserve unknown versus known-empty collection state;
- reject structural contradiction and implementation-only terminal success;
- generate deterministic case ID from semantic fields only;
- append fixed no-authority control fields.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run the focused test file. Expected: normalization/validation tests PASS.

- [ ] **Step 5: Write failing serialization and renderer tests**

Add tests proving:
- `serialize_intelligence_case` emits identical JSON for equivalent packets and for reversed input-key order;
- serialized JSON has lexicographically sorted keys and round-trips to the normalized dict;
- `render_intelligence_case` uses fixed field order and explicitly prints `unknown` for `None` and `none` for explicit empty collections;
- renderer never prints a root-cause/diagnosis/hypothesis section;
- control footer shows mutation authority false and GitHub Actions fallback 0.

- [ ] **Step 6: Run renderer tests and confirm RED**

Expected: FAIL because serialization/rendering is not yet implemented.

- [ ] **Step 7: Implement deterministic serialization and renderer**

Add exact signatures:

```python
def serialize_intelligence_case(packet: Mapping[str, Any]) -> str: ...

def render_intelligence_case(packet: Mapping[str, Any]) -> str: ...
```

Both must call `normalize_intelligence_case` first. Renderer line order is fixed to: title, Case ID, Workstream, Goal, Visible Symptom, Success Condition, Solved When, Constraints, Do Not Change, Required Changes, Affected Systems, Environment, Current Known State, Suspected Subsystems, Mutation Authority, GitHub Actions Fallback.

- [ ] **Step 8: Run final Task-1 verification**

Run:

```bash
python -m pytest -q tests/test_devsystem_monster_coding_intelligence_case_contract_v1.py
python -m py_compile devsystem/monster_coding_intelligence_case_contract_v1.py
```

Expected: all focused tests PASS and compile exits 0.

- [ ] **Step 9: Run the repository test command before calling implementation complete**

Run bare `python -m pytest -q`. Record any unrelated failures by exact test name; do not mutate unrelated code to chase them.

- [ ] **Step 10: Commit Task 1**

Commit module + focused tests with message:

```text
feat: add Monster intelligence case contract
```

---

### Task 2: Existing Control-Plane Proof, Merge, and Freeze

**Files:**
- Create: `devsystem/execution_plans/monster-coding-intelligence-v1-step1-case-contract.json`
- Create: `devsystem/runless_proof_plans/monster-coding-intelligence-v1-step1-case-contract.json`
- Create: `devsystem/task_ledgers/monster-coding-intelligence-v1-step1-case-contract.json`
- Read-only: approved spec and this plan.

**Interfaces:**
- Consumes Task-1 module/tests and current Step 2A/lease/registry truth.
- Produces one exact Runless proof plan.
- Produces freeze token `MONSTER_CODING_INTELLIGENCE_V1_STEP1_INTELLIGENCE_CASE_CONTRACT_FROZEN`.
- Produces one Step-1 ledger; it must not become a second intelligence or execution authority.

- [ ] **Step 1: Reconcile Step 2A immediately before proof metadata**

Verify current `main`, authoritative work branch/head, current scope lease, frozen-registry revision/hash, and any existing matching PR/proof. Reuse matching authoritative state; never create duplicates.

- [ ] **Step 2: Create execution-plan JSON**

Record project `MONSTER_CODING_INTELLIGENCE_V1`, step `1/10`, mission `Intelligence Case Contract V1`, exact current base main SHA, exact branch/head, product/runtime/model mutation false, one-PR max, duplicate async forbidden, GitHub Actions fallback 0, and fixed freeze token.

- [ ] **Step 3: Create Runless proof-plan JSON**

Commands are exactly:

```json
[
  ["python", "-m", "pytest", "-q", "tests/test_devsystem_monster_coding_intelligence_case_contract_v1.py"],
  ["python", "-m", "py_compile", "devsystem/monster_coding_intelligence_case_contract_v1.py"]
]
```

Artifacts: module, focused tests, execution plan, Runless plan, task ledger, approved spec, implementation plan. Dependencies: existing Runless plan validator, terminal receipt validator, scope-aware lease, frozen registry, and no sports product files.

- [ ] **Step 4: Create task-ledger JSON**

Record active problem, root cause, patch, TDD RED/GREEN evidence, exact authoritative branch/head, scope lease, zero mutation authority inside Intelligence Layer, and `green_plus_frozen_claimed=false` until independent readback.

- [ ] **Step 5: Verify focused proof commands locally/authoritatively once**

Focused pytest + py_compile must PASS. Do not rerun unchanged proof after a valid terminal receipt exists.

- [ ] **Step 6: Lock exact candidate and obtain one Runless terminal proof**

Required: exact candidate SHA, immutable receipt, `failure_class=NONE`, `runless-final-gate` SUCCESS, fallback 0.

- [ ] **Step 7: Open at most one PR and merge exact certified head**

Before merge, reconcile base-main drift and frozen registry. If candidate is already merged, consume that truth instead of creating another PR.

- [ ] **Step 8: Reuse content-addressed proof after merge when artifact/dependency blobs match**

Do not run unchanged proof merely because the merge commit SHA differs.

- [ ] **Step 9: Transactionally freeze Step 1 in the existing frozen registry**

Freeze only declared Step-1 artifacts under token:

```text
MONSTER_CODING_INTELLIGENCE_V1_STEP1_INTELLIGENCE_CASE_CONTRACT_FROZEN
```

Preserve all unrelated entries and active thaws.

- [ ] **Step 10: Independently read back terminal state**

Verify exact freeze token, FROZEN status, source main SHA, exact artifact blobs, valid registry hash, one revision advance, preserved unrelated thaws, exact Runless proof, and fallback 0.

Only then claim:

```text
MONSTER CODING INTELLIGENCE V1 — STEP 1/10 — 100% GREEN + FROZEN
```

- [ ] **Step 11: Release Step-1 scope authority and stop**

Do not start Step 2 automatically.

## Self-Review Result

- Spec coverage: complete for Step 1; Steps 2–10 remain explicitly excluded.
- Step scan: each step has one checkable result; implementation bodies are not transcribed.
- Type consistency: one normalized `dict[str, Any]` packet feeds both serializer and renderer.
- Review Focus coverage: unknown-vs-empty, normalization equivalence, later-step-field rejection, structural contradiction, and deterministic output all have explicit tests.
- Proportion: one focused module + one focused test file, matching the repository's existing pure DevSystem contract style.
