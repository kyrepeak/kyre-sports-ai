# Runless Base-Drift Authority Supersession V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one audited, fail-closed Runless V2 recovery path that retires a stale `MERGE_AUTHORIZED` candidate only when verified upstream base drift forces a new exact PR head, then allows exactly one fresh successor proof.

**Architecture:** Preserve immutable proof/check evidence on the old candidate, add a terminal historical `SUPERSEDED_BASE_DRIFT` state plus an immutable `authority_supersessions` record, and require GitHub PR/head/main/ancestry corroboration before the transactional state change. The connected caller uses a secret-safe Supabase transport RPC to the existing Runless V2 service; the successor then re-enters the unchanged normal proof/finalization path.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, httpx/PyJWT, PostgreSQL/Supabase PL/pgSQL + pg_net/http extension pattern, GitHub App `5204253`, pytest, Vercel `kyre-runless-proof`.

**Spec:** `docs/superpowers/specs/2026-10-17-runless-base-drift-authority-supersession-v1-design.md`

## Global Constraints

- Never create parallel merge/finalization authority for one workstream.
- Existing receipt mirrors, proof fingerprints, receipt digests, and gate check IDs on the old proof remain immutable.
- Only `MERGE_AUTHORIZED -> SUPERSEDED_BASE_DRIFT` is added; `SUPERSEDED_BASE_DRIFT` is terminal.
- Supersession is valid only for verified base drift, never for ordinary product edits or proof repair.
- No live Runless execution lease may exist for the workstream during supersession.
- The successor SHA must differ from the old SHA and be a Git descendant of both the old candidate and current `main`.
- The PR must still be open, on the same authoritative branch, and its current head must equal the successor SHA.
- The successor must run a fresh exact-head Runless proof and publish a new App-`5204253` `runless-final-gate`.
- GitHub branch protection is never bypassed; GitHub Actions fallback remains `0`.
- Do not mix sports-page product code into the repair PR.
- Do not expose `RUNLESS_PROOF_AUTH_TOKEN` or Vercel protection credentials to the connected chat/client.

## Review Focus

- **Repeated request:** same old proof + same successor must return the same immutable supersession record without a second mutation. Covered in Task 1 schema/RPC tests and Task 3 service tests.
- **Competing successor:** same old proof + a different successor must fail closed with a typed collision. Covered in Task 1 and Task 3.
- **Ancestry ambiguity/unavailability:** if GitHub cannot prove descendant-of-old and descendant-of-current-main, no durable mutation may occur. Covered in Task 2.
- **Historical authority leakage:** `SUPERSEDED_BASE_DRIFT` must never resolve as active finalizer authority or block the one valid successor claim. Covered in Tasks 1 and 5.
- **Old proof evidence drift:** receipt digest and gate check ID must be identical before/after supersession. Covered in Tasks 1, 3, and 6.

---

### Task 1: Durable supersession state + atomic RPC

**Files:**
- Create: `supabase/migrations/20261017_runless_base_drift_authority_supersession_v1.sql`
- Create: `tests/test_runless_base_drift_authority_supersession_schema_v1.py`
- Modify: `runless_v2/models.py`
- Modify: `tests/test_runless_v2_schema_contract.py`

**Interfaces:**
- Consumes: existing `runless_v2.proof_runs`, `workstream_leases`, `receipt_mirrors`, and `claim_workstream` authority semantics.
- Produces: `ProofState.SUPERSEDED_BASE_DRIFT`, typed `AuthoritySupersession`, table `runless_v2.authority_supersessions`, and RPC `runless_v2.supersede_base_drift_authority(...)`.

- [ ] **Step 1: Write failing schema/model tests**

Add tests asserting:

```python
def test_superseded_base_drift_is_terminal_historical_state(): ...
def test_authority_supersessions_table_has_required_identity_and_uniqueness(): ...
def test_supersession_rpc_requires_merge_authorized_no_live_lease_and_old_evidence(): ...
def test_same_supersession_is_idempotent_but_different_successor_collides(): ...
def test_claim_workstream_ignores_superseded_historical_authority(): ...
```

Assert the migration contains `SUPERSEDED_BASE_DRIFT`, one unique supersession per `old_proof_id`, uniqueness for `(workstream, successor_candidate_sha)`, the workstream advisory lock, no-live-lease check, outstanding-authority exclusion, and preservation of `receipt_digest` / `gate_check_run_id`.

- [ ] **Step 2: Run schema/model tests to RED**

Run:
`python -m pytest -q tests/test_runless_base_drift_authority_supersession_schema_v1.py tests/test_runless_v2_schema_contract.py`

Expected: FAIL because the migration/state/model do not yet exist.

- [ ] **Step 3: Implement the migration and model**

In `runless_v2/models.py` add:

```python
ProofState.SUPERSEDED_BASE_DRIFT = "SUPERSEDED_BASE_DRIFT"

class AuthoritySupersession(BaseModel):
    supersession_id: str
    workstream: str
    old_proof_id: str
    old_candidate_sha: str
    old_expected_main_sha: str | None
    successor_candidate_sha: str
    successor_expected_main_sha: str
    reason: str
    github_pr_number: int | None
    github_branch: str
    old_gate_check_run_id: int
    old_receipt_digest: str
    created_at: str
```

The SQL RPC signature is:

```text
runless_v2.supersede_base_drift_authority(
  p_workstream text,
  p_task_id text,
  p_old_proof_id text,
  p_old_candidate_sha text,
  p_successor_candidate_sha text,
  p_successor_expected_main_sha text,
  p_github_pr_number bigint,
  p_github_branch text
) -> authority_supersessions
```

The RPC must be idempotent only for the exact same identity, reject a different successor, insert the audit row and transition the old proof in one transaction, and never modify the old receipt/gate fields.

- [ ] **Step 4: Run schema/model tests to GREEN**

Run the Step 2 command again. Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Commit: `feat: add durable base-drift authority supersession`

---

### Task 2: GitHub base-drift corroboration

**Files:**
- Modify: `runless_v2/github_authority.py`
- Modify: `tests/test_runless_v2_github_authority.py`

**Interfaces:**
- Consumes: repository identity, old proof identity, PR number/branch, old candidate SHA, successor candidate SHA, successor expected-main SHA.
- Produces: `GithubAuthority.verify_base_drift_successor(...) -> dict[str, Any]` containing canonical PR/head/main/ancestry evidence or a typed `GithubAuthorityError`.

- [ ] **Step 1: Write failing GitHub authority tests**

Add tests:

```python
def test_base_drift_accepts_open_same_branch_head_descendant_of_old_and_main(): ...
def test_base_drift_rejects_closed_pr_or_branch_mismatch(): ...
def test_base_drift_rejects_successor_not_current_pr_head(): ...
def test_base_drift_rejects_unchanged_main(): ...
def test_base_drift_rejects_non_descendant_of_old_candidate(): ...
def test_base_drift_rejects_successor_not_containing_current_main(): ...
def test_base_drift_fails_closed_when_compare_api_is_unavailable(): ...
```

- [ ] **Step 2: Run focused GitHub tests to RED**

Run: `python -m pytest -q tests/test_runless_v2_github_authority.py`
Expected: FAIL because the verifier does not exist.

- [ ] **Step 3: Implement exact verifier**

Add:

```python
def verify_base_drift_successor(
    self,
    *,
    old_candidate_sha: str,
    old_expected_main_sha: str | None,
    successor_candidate_sha: str,
    successor_expected_main_sha: str,
    pr_number: int,
    branch: str,
) -> dict[str, Any]: ...
```

Use GitHub PR readback plus compare/commit ancestry. Require current `main == successor_expected_main_sha`, current main differs from old expected main, PR is open, PR branch/head match exactly, and both ancestry checks succeed. Return only corroborating metadata; do not mutate GitHub.

- [ ] **Step 4: Run focused GitHub tests to GREEN**

Run Step 2 command again. Expected: PASS.

- [ ] **Step 5: Commit Task 2**

Commit: `feat: verify base-drift successor ancestry`

---

### Task 3: State-store boundary + authenticated Runless endpoint

**Files:**
- Modify: `runless_v2/state_store.py`
- Modify: `runless_v2/app.py`
- Create: `tests/test_runless_v2_base_drift_supersession_v1.py`
- Modify: `tests/test_runless_v2_state_store.py`

**Interfaces:**
- Consumes: `GithubAuthority.verify_base_drift_successor(...)` and the Task-1 Supabase RPC.
- Produces: `DurableStateStore.supersede_base_drift_authority(...) -> AuthoritySupersession`, `DurableStateStore.authority_supersession(old_proof_id) -> AuthoritySupersession`, and authenticated `POST /supersede-base-drift`.

- [ ] **Step 1: Write failing service/state-store tests**

Cover happy path, idempotent same request, different-successor collision, wrong old state, live execution lease, missing receipt/gate, alternate outstanding authority, repository/workstream/task mismatch, GitHub corroboration failure, and evidence immutability.

The endpoint request model is:

```python
class BaseDriftSupersessionRequest(BaseModel):
    repository: str
    workstream: str
    task_id: str
    old_proof_id: str
    old_candidate_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    successor_candidate_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    successor_expected_main_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    pr_number: int = Field(gt=0)
    branch: str = Field(min_length=1)
```

- [ ] **Step 2: Run focused tests to RED**

Run:
`python -m pytest -q tests/test_runless_v2_base_drift_supersession_v1.py tests/test_runless_v2_state_store.py`

Expected: FAIL on missing methods/route.

- [ ] **Step 3: Implement state-store methods**

Add typed RPC mapping for base-drift errors and the two methods above. Preserve the existing `_rpc()` / `_single()` pattern; do not add client-side read-modify-write authority logic.

- [ ] **Step 4: Implement authenticated endpoint**

`POST /supersede-base-drift` must:
1. require existing bearer auth and `authority_enabled`;
2. require repository equality with settings;
3. read the old proof exactly and verify workstream/task/candidate/state/evidence;
4. require zero live workstream execution leases;
5. call the GitHub base-drift verifier;
6. call the one atomic Supabase supersession RPC;
7. read the supersession record back and require exact identity/evidence;
8. return the immutable record.

Do not create a successor proof in this endpoint.

- [ ] **Step 5: Run focused tests to GREEN**

Run Step 2 command again. Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Commit: `feat: expose audited base-drift supersession`

---

### Task 4: Secret-safe connected Supabase transport

**Files:**
- Create: `supabase/migrations/20261017_runless_base_drift_supersession_transport_v1.sql`
- Create: `tests/test_runless_base_drift_supersession_transport_v1.py`
- Create: `docs/runless-base-drift-authority-supersession-v1-operations.md`

**Interfaces:**
- Consumes: authenticated Runless `POST /supersede-base-drift` from Task 3 and Vault secrets already used by `request_proof_transport`.
- Produces: `runless_v2.request_base_drift_supersession_transport(...) -> jsonb` for the connected Supabase service-role path.

- [ ] **Step 1: Write failing transport contract tests**

Assert the migration uses `SECURITY DEFINER`, Supabase Vault, the existing Runless bearer + Vercel protection bypass, advisory serialization, a `kyre-runless-proof*.vercel.app` allowlist, service-role-only execute permissions, and no bearer literal committed in source.

- [ ] **Step 2: Run transport tests to RED**

Run: `python -m pytest -q tests/test_runless_base_drift_supersession_transport_v1.py tests/test_runless_execution_transport_v1_contract.py`
Expected: new transport test FAIL; existing transport contract stays PASS.

- [ ] **Step 3: Implement transport RPC**

Signature:

```text
runless_v2.request_base_drift_supersession_transport(
  p_repository text,
  p_workstream text,
  p_task_id text,
  p_old_proof_id text,
  p_old_candidate_sha text,
  p_successor_candidate_sha text,
  p_successor_expected_main_sha text,
  p_pr_number bigint,
  p_branch text,
  p_base_url text
) -> jsonb
```

It must return an existing exact supersession read-back before network mutation, otherwise call `/supersede-base-drift`, sanitize remote error details to typed Runless markers, then independently read the durable supersession row and return that durable identity.

- [ ] **Step 4: Write operations doc**

Document the supported connected flow: durable preflight -> one transport invocation -> durable read-back -> normal successor `request_proof_transport`. Explicitly forbid credential export, direct proof-row edits, stale-gate reuse, alternate workstream creation, and blind retries.

- [ ] **Step 5: Run transport/regression tests to GREEN**

Run Step 2 command again. Expected: PASS.

- [ ] **Step 6: Commit Task 4**

Commit: `feat: add secret-safe base-drift supersession transport`

---

### Task 5: Dynamic finalizer authority filtering

**Files:**
- Modify: `vercel_finalizer/authority.py`
- Modify: `vercel_finalizer/test_authority.py`
- Modify: `vercel_finalizer/test_dynamic_authority.py`

**Interfaces:**
- Consumes: proof rows containing the new historical state.
- Produces: active authority resolution that never treats `SUPERSEDED_BASE_DRIFT` as current mutation/finalization authority, while preserving explicit historical recovery/read paths.

- [ ] **Step 1: Write failing finalizer tests**

Add tests asserting an exact `SUPERSEDED_BASE_DRIFT` row cannot resolve through `resolve_authority`, cannot satisfy merge/finalization authority, and does not make one valid non-superseded successor ambiguous.

- [ ] **Step 2: Run finalizer tests to RED**

Run: `python -m pytest -q vercel_finalizer/test_authority.py vercel_finalizer/test_dynamic_authority.py`
Expected: FAIL until historical-state filtering is explicit.

- [ ] **Step 3: Implement filtering**

Keep terminal historical rows queryable only by explicit recovery/history code. `resolve_authority()` must reject/ignore `SUPERSEDED_BASE_DRIFT` as active authority without choosing “newest” by time.

- [ ] **Step 4: Run finalizer tests to GREEN**

Run Step 2 command again. Expected: PASS.

- [ ] **Step 5: Commit Task 5**

Commit: `fix: exclude superseded proofs from active finalizer authority`

---

### Task 6: Full regression lock + Runless proof plan

**Files:**
- Create: `devsystem/runless_proof_plans/runless-base-drift-authority-supersession-v1.json`
- Create: `tests/test_runless_base_drift_authority_supersession_contract_v1.py`

**Interfaces:**
- Consumes: Tasks 1–5 complete branch head.
- Produces: one exact-head proof plan with `freeze_token = RUNLESS_BASE_DRIFT_AUTHORITY_SUPERSESSION_V1_FROZEN`, `required_check = runless-final-gate`, `required_check_app_id = 5204253`, and `github_actions_fallback = 0`.

- [ ] **Step 1: Write contract/proof-plan test**

Assert no sports runtime/model/page files are artifacts, the new migrations/modules/tests are declared, probes are empty unless a public Runless API probe is explicitly required, App ID is `5204253`, and GitHub Actions fallback is `0`.

- [ ] **Step 2: Run complete focused suite once**

Run:
`python -m pytest -q tests/test_runless_base_drift_authority_supersession_schema_v1.py tests/test_runless_v2_base_drift_supersession_v1.py tests/test_runless_base_drift_supersession_transport_v1.py tests/test_runless_base_drift_authority_supersession_contract_v1.py tests/test_runless_v2_state_store.py tests/test_runless_v2_github_authority.py tests/test_runless_v2_schema_contract.py tests/test_runless_v2_proof_service.py tests/test_runless_v2_finalization_readback.py vercel_finalizer/test_authority.py vercel_finalizer/test_dynamic_authority.py vercel_finalizer/test_app.py`

Expected: PASS.

- [ ] **Step 3: Run py_compile gate**

Run:
`python -m py_compile runless_v2/models.py runless_v2/state_store.py runless_v2/github_authority.py runless_v2/app.py vercel_finalizer/authority.py`

Expected: PASS.

- [ ] **Step 4: Create the exact Runless proof plan**

Bind `source_main_sha` to the main SHA used to start the final repair candidate and include the exact commands from Steps 2–3. Do not create a second proof plan for the same candidate.

- [ ] **Step 5: Commit Task 6**

Commit: `test: certify base-drift authority supersession`

---

### Task 7: Repair PR exact-head proof, merge, migration rollout, and freeze

**Files:**
- No new product files unless proof/freeze governance requires a task ledger/contract already used by the repository.

**Interfaces:**
- Consumes: exact Task-6 candidate and proof plan.
- Produces: repair PR merged to `main`, both migrations applied once to Supabase, deployed Runless V2 service exposing `/supersede-base-drift`, and durable repair `GREEN_FROZEN` read-back.

- [ ] **Step 1: Reconcile repair branch to then-current main before proof**

Do this once immediately before the authoritative proof. If main changes after `MERGE_AUTHORIZED`, use this repair's own mechanism only after it has been deployed; do not invent a second workstream.

- [ ] **Step 2: Open/reuse one repair PR**

Head: `runless-base-drift-authority-supersession-v1`. Base: `main`. No sports files allowed.

- [ ] **Step 3: Execute one exact-head Runless proof**

Use the existing privileged `request_proof_transport` path. Required result: exact candidate -> `MERGE_AUTHORIZED`, fresh receipt digest, App-`5204253` `runless-final-gate` success.

- [ ] **Step 4: Merge exact authorized repair candidate and verify main**

Merge only with expected head SHA. Read `main` back and require it contains the repair candidate.

- [ ] **Step 5: Apply the two Supabase migrations exactly once**

Apply `20261017_runless_base_drift_authority_supersession_v1.sql` then `20261017_runless_base_drift_supersession_transport_v1.sql`. Verify the new table/RPCs via read-only catalog queries.

- [ ] **Step 6: Verify production Runless endpoint/deployment**

Require the deployed `kyre-runless-proof` service to expose the authenticated supersession endpoint and preserve `/prove` regression behavior.

- [ ] **Step 7: Complete normal merged-main freeze/read-back**

Use existing Runless finalization convergence. Required durable state: `GREEN_FROZEN` with freeze token `RUNLESS_BASE_DRIFT_AUTHORITY_SUPERSESSION_V1_FROZEN`.

---

### Task 8: Recover and finish API 2 PR #1600

**Files:**
- Reuse PR #1600 and its existing branch/workstream. No new sports PR and no new workstream.

**Interfaces:**
- Consumes: production supersession path from Task 7 and old proof `api2-universal-nav-single-owner-speed-v1-d5fc3affb6b80b6f-c7392888590faff7`.
- Produces: PR #1600 current exact head with a fresh Runless proof, exact-head merge, merged-main verification, freeze, and durable `GREEN_FROZEN`.

- [ ] **Step 1: Read back current PR #1600 head and current main once**

If the PR head does not contain current main, merge current main into the same PR branch exactly once. Record that resulting exact successor SHA.

- [ ] **Step 2: Preflight old authority and supersession absence**

Require old proof state `MERGE_AUTHORIZED`, old receipt/gate unchanged, zero live Runless workstream execution leases, and no existing supersession for that old proof.

- [ ] **Step 3: Invoke one privileged base-drift supersession transport request**

Use the same workstream/task, old proof/candidate, current PR head, current main, PR `1600`, and branch `api2-universal-nav-single-owner-speed-v1`.

- [ ] **Step 4: Read back supersession record**

Require reason `BASE_DRIFT`, exact old/new SHAs, PR/branch identity, and old receipt/gate identity. Require old proof state `SUPERSEDED_BASE_DRIFT`.

- [ ] **Step 5: Submit one fresh successor proof**

Use the normal `request_proof_transport` path with current main as `expected_main_sha`. Required result: a new proof ID, new receipt digest, and new successful App-`5204253` `runless-final-gate` on the exact current PR head.

- [ ] **Step 6: Merge exact successor head**

Use expected-head SHA; never reuse the old `d5fc...` gate. If main drifts again before merge, repeat the audited supersession chain for the newly authorized proof only.

- [ ] **Step 7: Complete merged-main verification + freeze + canonical read-back**

Require the successor proof to reach durable `GREEN_FROZEN` and the existing PR #1600 freeze token `API2_UNIVERSAL_NAV_SINGLE_OWNER_SPEED_V1_FROZEN`.

- [ ] **Step 8: Final evidence report**

Record: supersession ID, old proof/gate/receipt, successor exact SHA, successor proof ID/gate/receipt, PR #1600 merge commit, merged-main SHA, freeze token, and canonical `GREEN_FROZEN` read-back. Only then report `🟢 100% GREEN + ❄️ FROZEN`.
