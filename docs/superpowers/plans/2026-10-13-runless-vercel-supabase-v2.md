# Runless V2 — Vercel + Supabase Durable Proof Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task in this environment. Steps use checkbox syntax for tracking. If this work is moved to Codex with subagents available, `superpowers:subagent-driven-development` may be used instead.

**Goal:** Replace Render-hosted Runless V1 with a Vercel + Supabase proof authority that preserves Step 2A, exact-head proof, immutable receipts, anti-loop behavior, and GitHub finalization-ledger truth, then use that authority to finish Universal Sports Step 6.

**Architecture:** Vercel hosts a stateless FastAPI control API. Supabase Postgres owns durable proof/workstream state with atomic leases and fencing generations. Each static proof runs in one short-lived Vercel Sandbox that checks out the exact candidate SHA and executes only existing allowlisted Runless commands. GitHub App `5204253` remains the only publisher of `runless-final-gate`; GitHub immutable receipts and Finalization Ledger V2 remain terminal proof/freeze authority.

**Tech Stack:** Python 3.13, FastAPI, Pydantic 2, httpx, PyJWT/cryptography, Vercel Python SDK/Sandbox, Supabase Postgres/PostgREST RPC, pytest, GitHub App checks/contents APIs.

**Spec:** `docs/superpowers/specs/2026-10-13-runless-vercel-supabase-v2-design.md`

## Global Constraints

- Enforce Step 2A before every proof mutation.
- Exactly one authoritative Runless V2 proof chain per workstream.
- V2 must never create a second simultaneous authority beside V1; V2 mutation authority remains disabled until cutover certification passes.
- Render is not part of the V2 proof critical path and receives no new proof requests.
- `github_actions_fallback` remains `0`; GitHub Actions is not a proof substitute.
- Do not modify Universal Sports Step-6 PR #1531 while V2 is being built/certified.
- Do not mutate sports product/runtime/model behavior in this workstream.
- Secrets never enter repository files, logs, receipts, status strings, or chat.
- Supabase public/anon callers cannot mutate Runless V2 control state.
- No correctness-critical ownership/status may exist only in process RAM.
- No blind retry/poll loop. Inspect one authoritative terminal result before changing strategy.
- A successful GitHub check without the matching V2 receipt identity is insufficient for merge authorization.
- GREEN + FROZEN requires GitHub finalization-ledger persistence and independent readback.

## Review Focus

1. Two simultaneous claims for one workstream yield exactly one execution owner.
2. Expired ownership increments the fencing generation; stale generations cannot mutate state or publish a gate.
3. Cold starts/redeploys preserve proof status and cannot strand a ghost workstream owner.
4. Same-proof retries are idempotent, while a different candidate is blocked if an authorized proof is still outstanding.
5. Gate, immutable receipt, merged-main identity, freeze record, and manifest chain must all bind to the same candidate/proof before terminal closeout.

---

## Task 1 — Supabase Durable State Schema + Atomic RPCs

**Files:**
- Create: `supabase/migrations/20261013_runless_v2_durable_state.sql`
- Create: `tests/test_runless_v2_schema_contract.py`

**Schema contract:**
- Schema: `runless_v2`
- Tables: `proof_runs`, `workstream_leases`, `failed_fingerprints`, `receipt_mirrors`
- Database time, not client time, decides lease expiry.
- `workstream_leases.workstream` is the single active execution-owner key.
- `fencing_generation` is monotonically increasing per workstream.
- An outstanding `MERGE_AUTHORIZED` proof is program authority even after its execution lease is released.

**RPC interfaces:**

```text
runless_v2.claim_workstream(
  p_workstream text,
  p_proof_id text,
  p_task_id text,
  p_candidate_sha text,
  p_expected_main_sha text,
  p_scope_lease_id text,
  p_authorization_id text,
  p_request_fingerprint text,
  p_ttl_seconds integer
)

runless_v2.renew_workstream(
  p_workstream text,
  p_proof_id text,
  p_lease_token uuid,
  p_fencing_generation bigint,
  p_ttl_seconds integer
)

runless_v2.advance_proof_state(
  p_proof_id text,
  p_expected_state text,
  p_target_state text,
  p_lease_token uuid,
  p_fencing_generation bigint,
  p_detail text default ''
)

runless_v2.record_failure_and_release(...)
runless_v2.record_merge_authorized_and_release_execution(...)
runless_v2.closeout_green_frozen(...)
```

- `claim_workstream` must serialize by workstream using row locking or a transaction-scoped advisory lock.
- Same proof/request is idempotent and returns the existing generation.
- Different unexpired owner returns deterministic conflict.
- Expired owner can be replaced only by a new generation.
- An outstanding different `MERGE_AUTHORIZED` proof blocks a new candidate even when no execution lease remains.
- `record_failure_and_release` inserts deterministic failures into `failed_fingerprints` and releases only the matching token/generation.
- Infrastructure release before completed evidence must not create a deterministic failed fingerprint.
- `record_merge_authorized_and_release_execution` records receipt/gate evidence and atomically clears execution ownership.
- `closeout_green_frozen` is allowed only from the expected post-merge sequence and must not manufacture GitHub evidence; the application supplies already-read-back exact evidence.
- Revoke schema/table mutation from `anon` and `authenticated`; grant only the server-side role needed by V2.

- [ ] Write schema-contract tests first. Assert all four tables, all six RPCs, fencing checks, legal-state validation, DB-time expiry, outstanding-authority conflict, and privilege revocations exist.
- [ ] Run `python -m pytest -q tests/test_runless_v2_schema_contract.py` and observe RED because the migration does not exist.
- [ ] Implement the migration with transactional functions and explicit error codes such as `RUNLESS_V2_WORKSTREAM_BUSY`, `RUNLESS_V2_AUTHORITY_CONFLICT`, `RUNLESS_V2_STALE_FENCE`, and `RUNLESS_V2_ILLEGAL_TRANSITION`.
- [ ] Re-run the focused test to GREEN.
- [ ] Commit only migration + schema-contract test.

---

## Task 2 — Models, Config, and Durable Supabase State Adapter

**Files:**
- Create: `runless_v2/__init__.py`
- Create: `runless_v2/models.py`
- Create: `runless_v2/config.py`
- Create: `runless_v2/state_store.py`
- Create: `tests/test_runless_v2_state_store.py`

**Interfaces:**

```python
class ProofState(str, Enum): ...
class FailureClass(str, Enum): ...
class ProofRequest(BaseModel): ...
class ProofStatus(BaseModel): ...
class LeaseClaim(BaseModel): ...

class DurableStateStore:
    def claim(self, request, request_fingerprint, ttl_seconds) -> LeaseClaim: ...
    def renew(self, claim, ttl_seconds) -> LeaseClaim: ...
    def advance(self, proof_id, expected, target, claim, detail='') -> ProofStatus: ...
    def record_failure_and_release(self, ...) -> ProofStatus: ...
    def release_infra(self, ...) -> ProofStatus: ...
    def record_merge_authorized_and_release_execution(self, ...) -> ProofStatus: ...
    def status(self, proof_id) -> ProofStatus: ...
    def receipt_mirror(self, proof_id) -> dict: ...
    def closeout_green_frozen(self, ...) -> ProofStatus: ...
```

- Preserve the V1 state order: `IDENTIFY → 2A_LOCK → FINGERPRINT → REUSE_OR_PROVE → PUBLIC_CHECK_IF_REQUIRED → RECEIPT → RUNLESS_FINAL_GATE → MERGE_AUTHORIZED → MERGED → POST_MERGE_VERIFY → FREEZE → READ_BACK → GREEN_FROZEN`; `FAILED` is terminal.
- Use `httpx` against Supabase PostgREST RPC; do not implement client-side read/modify/write locking.
- Required environment values: `SUPABASE_URL`, privileged server credential, `GITHUB_APP_ID`, `GITHUB_APP_INSTALLATION_ID`, `GITHUB_APP_PRIVATE_KEY`, `RUNLESS_PROOF_AUTH_TOKEN`, repository identity, receipt ref/path, and `RUNLESS_AUTHORITY_ENABLED`.
- `RUNLESS_AUTHORITY_ENABLED` defaults to false.

- [ ] Write fake-transport tests first for RPC names/payloads, conflict mapping, idempotent claim reuse, stale-fence rejection, durable status reads, and fail-closed missing credentials.
- [ ] Run `python -m pytest -q tests/test_runless_v2_state_store.py` and observe RED.
- [ ] Implement models/config/store without storing authoritative state in module globals.
- [ ] Re-run focused tests to GREEN.
- [ ] Commit Task 2 files only.

---

## Task 3 — GitHub Authority, Immutable Receipts, Step 2A, and Finalization Readback

**Files:**
- Create: `runless_v2/github_authority.py`
- Create: `runless_v2/receipt_contract.py`
- Create: `runless_v2/finalization_readback.py`
- Create: `tests/test_runless_v2_github_authority.py`
- Create: `tests/test_runless_v2_finalization_readback.py`

**Required behavior:**
- Refactor the proven GitHub App authentication/check behavior from `vercel_finalizer/app.py`; remove its hard-coded old PR/branch assumptions.
- Preserve App ID `5204253`, repository `kyrepeak/kyre-sports-ai`, and gate name `runless-final-gate`.
- Preserve V1 Step 2A checks: exact candidate commit, requested `main`, workstream identity, live external scope lease, frozen-artifact protection, artifact/dependency maps, and authorization ID.
- Immutable proof receipts remain on branch `runless-proof-receipts` beneath `devsystem/runless_proof_receipts/`.
- Receipt digest semantics must remain compatible with `devsystem/runless_terminal_proof_receipt_v1.py`; add parity tests rather than silently inventing a second digest format.
- Gate publication is successful only if readback finds `name=runless-final-gate`, `conclusion=success`, `app.id=5204253`, exact candidate SHA, and output bound to the V2 receipt digest.
- Final closeout independently reads `monster-finalization-ledger-v2`, validates the freeze record with the same canonical semantics as `devsystem/universal_sports_finalization_bootstrap_v1.py`, validates manifest chaining, and binds `workstream`, freeze token, candidate SHA, proof digest, and merged-main SHA.

**Interfaces:**

```python
class GithubAuthority:
    def installation_token(self) -> str: ...
    def commit(self, sha: str) -> dict: ...
    def main_sha(self) -> str: ...
    def tree_blobs(self, sha: str) -> dict[str, str]: ...
    def read_live_scope_lease(self, lease_id: str) -> dict: ...
    def verify_step2a(self, request, plan, candidate_tree, main_tree) -> dict: ...
    def put_or_read_receipt(self, receipt: dict) -> dict: ...
    def publish_gate_and_readback(self, candidate_sha: str, receipt: dict) -> dict: ...

validate_finalization_closeout(...) -> dict
```

- [ ] Write tests first for wrong App ID, wrong candidate, main drift, dead scope lease, receipt collision, receipt tampering, wrong check app, wrong check SHA, wrong digest, wrong freeze token, stale manifest chain, and successful exact binding.
- [ ] Run `python -m pytest -q tests/test_runless_v2_github_authority.py tests/test_runless_v2_finalization_readback.py` and observe RED.
- [ ] Implement the smallest reusable authority/readback layer.
- [ ] Run focused tests plus `python -m pytest -q vercel_finalizer/test_app.py vercel_finalizer/test_publish_gate_build.py` to protect existing behavior.
- [ ] Commit Task 3 files only.

---

## Task 4 — Ephemeral Vercel Sandbox Exact-Candidate Executor

**Files:**
- Create: `runless_v2/sandbox_executor.py`
- Create: `runless_v2/public_probe.py`
- Create: `tests/test_runless_v2_sandbox_executor.py`

**Execution contract:**
- One non-persistent Sandbox per authoritative static-proof attempt.
- Python runtime `python3.13`.
- Sandbox timeout derived from the proof plan and capped by V2 policy.
- Checkout exact candidate SHA with a short-lived GitHub installation credential; verify `git rev-parse HEAD` equals the requested SHA before any proof command.
- Load the proof plan from the candidate checkout.
- Reuse the existing command allowlist semantics from `devsystem/runless_proof_plan_v1.py`: only approved `python -m pytest`, `python -m devsystem.*`, and `python -m py_compile` forms; reject shell metacharacters.
- Bootstrap only the dependencies necessary to execute the candidate proof plan. For the current Universal Sports Step 6, the worker must at minimum support pytest plus the FastAPI/httpx/PyJWT dependencies already required by the Vercel finalizer tests; do not install unrelated application packages unless a validated proof import requires them.
- Hash stdout/stderr and return deterministic evidence objects; never store raw secret-bearing output in receipts.
- Always stop/destroy the Sandbox in `finally`.
- No automatic second Sandbox on failure.
- Public probes remain separate and execute only when declared by the proof plan.

**Interface:**

```python
class SandboxExecutor:
    async def execute(self, *, candidate_sha: str, task_id: str,
                      github_token: str, timeout_seconds: int) -> SandboxProofResult: ...
```

- [ ] Write executor tests with an injected fake Sandbox backend: exact checkout, HEAD mismatch fail-close, allowlist rejection, timeout classification, stdout/stderr digesting, and cleanup after success/failure.
- [ ] Run `python -m pytest -q tests/test_runless_v2_sandbox_executor.py` and observe RED.
- [ ] Implement against the `vercel` Python package (`from vercel import sandbox`) behind a narrow adapter so tests do not require live Sandbox allocation.
- [ ] Re-run focused tests to GREEN.
- [ ] Commit Task 4 files only.

---

## Task 5 — Durable Pre-Merge Proof Orchestration

**Files:**
- Create: `runless_v2/proof_service.py`
- Create: `tests/test_runless_v2_proof_service.py`

**Flow:**

```text
request
→ exact candidate/main/registry/external-scope-lease verification
→ artifact + dependency + policy fingerprint
→ deterministic proof ID + request fingerprint
→ durable claim
→ idempotent reuse check
→ Sandbox static evidence
→ required public probes
→ immutable GitHub receipt
→ Supabase receipt mirror
→ exact-head GitHub gate publication + readback
→ atomic MERGE_AUTHORIZED + execution-lease release
```

**Rules:**
- Same proof ID + same request fingerprint reuses durable status and never creates a second Sandbox if immutable successful evidence is already valid.
- Same proof ID with conflicting identity is integrity failure.
- Different candidate with an outstanding authorized proof returns `RUNLESS_V2_AUTHORITY_CONFLICT`.
- Deterministic static/public failures record failed fingerprints and block unchanged retries.
- Infra failure before trustworthy evidence completion releases execution ownership but does not poison the fingerprint as a product failure.
- A stale fencing generation cannot write receipt/gate state.
- Before gate publication, revalidate fence ownership and exact candidate identity so a stale worker cannot certify after takeover.

**Interface:**

```python
async def execute_proof_request(
    request: ProofRequest,
    *, state_store: DurableStateStore,
    github: GithubAuthority,
    sandbox: SandboxExecutor,
) -> ProofResult: ...
```

- [ ] Write orchestration tests first for happy path, same-proof reuse, simultaneous authority conflict, deterministic failure anti-loop, infra release, stale fence before gate, candidate/main movement, receipt collision, and gate readback failure.
- [ ] Run `python -m pytest -q tests/test_runless_v2_proof_service.py` and observe RED.
- [ ] Implement proof service by composing Tasks 2–4; do not add hidden retries.
- [ ] Run Tasks 2–5 suites together and require GREEN.
- [ ] Commit Task 5 files only.

---

## Task 6 — Authenticated FastAPI Surface + Dedicated Vercel Package

**Files:**
- Create: `runless_v2/app.py`
- Create: `runless_v2/auth.py`
- Create: `runless_v2/requirements.txt`
- Create: `runless_v2/vercel.json`
- Create: `tests/test_runless_v2_api.py`

**Vercel packaging:**
- Dedicated project name: `kyre-runless-proof`.
- Vercel project root directory: `runless_v2` so it does not collide with the existing Streamlit root application.
- Keep `runless_v2` self-contained at runtime. Pure receipt/finalization parity is protected by repository tests rather than importing parent-directory modules from the deployed package.
- `requirements.txt` includes only the control-plane runtime: FastAPI, Pydantic, httpx, PyJWT/cryptography, `vercel`, and test-only pytest if needed for build verification.
- `vercel.json` binds the FastAPI entrypoint and an explicit bounded function duration; Sandbox command duration remains separately bounded.

**API:**
- `GET /health` — no secret; returns service/version, `render_dependency=false`, `github_actions_fallback=0`, Supabase connectivity status, GitHub App configured status, and whether proof authority is enabled.
- `POST /prove` — authenticated; refuses with `RUNLESS_V2_AUTHORITY_DISABLED` until cutover.
- `GET /status/{proof_id}` — authenticated operational read.
- `GET /receipts/{proof_id}` — authenticated operational mirror read; immutable GitHub receipt is still authoritative.
- `POST /closeout` — authenticated; independently validates GitHub finalization evidence before durable terminal transitions.

**Authentication:**
- `Authorization: Bearer <RUNLESS_PROOF_AUTH_TOKEN>` for mutation/operational endpoints.
- Constant-time token comparison.
- Missing/invalid token fails 401 before any proof-state mutation.
- No privileged Supabase or GitHub secret returned from health/errors.

- [ ] Write API tests first for authority-disabled prove, missing/invalid auth, healthy read, correct proof delegation, status persistence across app re-instantiation, closeout failure on mismatched ledger evidence, and successful closeout.
- [ ] Run `python -m pytest -q tests/test_runless_v2_api.py` and observe RED.
- [ ] Implement app/auth/package config.
- [ ] Run all local V2 tests: `python -m pytest -q tests/test_runless_v2_*.py`.
- [ ] Commit Task 6 files only.

---

## Task 7 — V2 Cutover Contract, Proof Plan, and Operations Runbook

**Files:**
- Create: `devsystem/contracts/runless-vercel-supabase-v2.json`
- Create: `devsystem/runless_proof_plans/runless-vercel-supabase-v2-cutover.json`
- Create: `tests/test_runless_v2_cutover_contract.py`
- Create: `docs/runless-proof-plane-v2-operations.md`

**Contract requirements:**
- Workstream: `runless-vercel-supabase-v2`.
- Freeze token: `RUNLESS_VERCEL_SUPABASE_V2_CUTOVER_FROZEN`.
- `render_dependency=false`.
- `github_actions_fallback=0`.
- V2 authority requires durable Supabase proof identity plus immutable GitHub receipt and App-5204253 gate.
- Render V1 becomes `LEGACY_NON_AUTHORITATIVE` after cutover activation; no new request is sent to it.
- V2 is initially deployed with `RUNLESS_AUTHORITY_ENABLED=0`.
- Activation is allowed only after the non-authoritative certification matrix is fully green.

**Certification matrix:**
- cold-start status recovery;
- simultaneous claim single winner;
- expired lease takeover increments generation;
- stale fence rejected;
- same-proof idempotency;
- different-candidate outstanding-authority rejection;
- deterministic failure anti-loop;
- exact candidate checkout;
- Sandbox cleanup;
- API auth failure before mutation;
- zero production gate publication while authority disabled.

- [ ] Write the cutover-contract test first and observe RED.
- [ ] Add contract, Runless proof plan, and operations runbook.
- [ ] Run `python -m pytest -q tests/test_runless_v2_cutover_contract.py tests/test_runless_v2_*.py` to GREEN.
- [ ] Confirm the proof plan itself has `github_actions_fallback: 0` and no Render dependency.
- [ ] Commit Task 7 files only.

---

## Task 8 — Live Supabase + Vercel Activation and V2 Self-Certification

**Infrastructure targets:**
- Supabase project: `jqajcdckalsfizbvngiu`
- Vercel team/account: `team_3woqbtJQBL6MIwjv58QP3NlE`
- New Vercel project: `kyre-runless-proof`
- GitHub repository: `kyrepeak/kyre-sports-ai`
- GitHub App: `5204253`

- [ ] Enforce Step 2A for the V2 infrastructure workstream: one branch, one candidate, one Vercel project, one Supabase migration path, one proof path.
- [ ] Apply `20261013_runless_v2_durable_state.sql` once through Supabase migration tooling.
- [ ] Read back table/function/privilege definitions and run Supabase security/performance advisors. Patch only actual findings that affect this workstream.
- [ ] Create/reuse exactly one `kyre-runless-proof` Vercel project with root directory `runless_v2`; do not alter `kyre-sports-finalizer`.
- [ ] Configure secrets in Vercel encrypted environment storage: GitHub App ID/installation/private key, Supabase URL + privileged server credential, `RUNLESS_PROOF_AUTH_TOKEN`, repository/receipt identity, and `RUNLESS_AUTHORITY_ENABLED=0`. Never print secret values.
- [ ] If the privileged Supabase credential or GitHub private key cannot be securely transferred by the connected tooling, stop for one explicit secure user handoff rather than substituting a publishable/anon key.
- [ ] Deploy one preview from the exact V2 candidate and verify `/health` reports authority disabled, Render false, Actions fallback 0.
- [ ] Execute the certification matrix once. Use durable DB readback after a fresh API instance/cold start; do not repeatedly poll unfinished work.
- [ ] Verify no `runless-final-gate` was published during authority-disabled certification.
- [ ] Only after all certification checks pass, set `RUNLESS_AUTHORITY_ENABLED=1` for the exact certified deployment/config.
- [ ] Submit exactly one V2 self-proof for `runless-vercel-supabase-v2-cutover`; require immutable receipt + exact-head `runless-final-gate` from App 5204253.
- [ ] Merge only the exact certified V2 candidate. Verify merged-main contains the candidate and the cutover contract.
- [ ] Deploy/promote the merged-main V2 build to production and read back health/deployment identity.
- [ ] Freeze the V2 infrastructure workstream using its canonical freeze token and independent GitHub readback before calling V2 itself GREEN + FROZEN.

**Do not proceed to Task 9 if V2 lacks exact terminal evidence.**

---

## Task 9 — First Production Use: Finish Universal Sports Step 6

**Existing authoritative product path:**
- Workstream: `universal-sports-source-finalization-v1`
- PR: `#1531`
- Candidate expected at handoff: `1f270dcd8a76c4ac6f1576ded02a1b4c048286a4`
- Expected pre-Step6 main at handoff: `246d7d92485fdc93b220f53b14df95402d9aadc6`
- Registry baseline: revision 301, state hash `4889c944c0d386d7275ba698d42e0f8ee53b2076a2f6c8b68488cd17ffcd68c2`
- Freeze token: `UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP6_SOURCE_RECEIPT_PROVENANCE_FROZEN`

- [ ] Fresh-read `main`, PR #1531 head/mergeability, registry revision/hash, and the external Step-6 scope lease exactly once before proof. If any identity moved, reconcile that actual drift before proof.
- [ ] If the Step-6 scope lease expired, renew/claim one authoritative lease before proof; do not create competing leases.
- [ ] Send exactly one Step-6 `/prove` request to Runless V2 using the canonical workstream and exact candidate.
- [ ] Require terminal premerge evidence: V2 state `MERGE_AUTHORIZED`, immutable receipt, receipt digest, exact candidate SHA, exact `runless-final-gate` success, App ID 5204253, and independent check readback.
- [ ] Fresh-read `main` and PR identity once more; merge #1531 only if the certified candidate and expected base remain valid.
- [ ] Read merged-main SHA and prove candidate-to-main ancestry/identity according to existing finalization rules.
- [ ] Create the Step-6 Finalization Ledger V2 record using canonical hashing from `devsystem/universal_sports_finalization_bootstrap_v1.py`; manifest must advance from revision 5 to revision 6 with previous state hash `152c5c638a0b56908d29c410a6efd4bddc824b4e497959e5dd6800e4b2abfb1d`.
- [ ] Preserve `render_dependency=false`, `github_actions_fallback=0`, and `legacy_registry_mutation=false`; do not use the legacy frozen registry as the Step-6 freeze plane.
- [ ] Independently read back the Step-6 record, record hash, manifest revision 6, previous-state link, state hash, freeze token, candidate, merged-main SHA, and proof digest.
- [ ] Call authenticated V2 `/closeout` with the exact proof/candidate/merged-main/freeze identity. V2 must independently re-read GitHub ledger evidence before advancing `MERGED → POST_MERGE_VERIFY → FREEZE → READ_BACK → GREEN_FROZEN`.
- [ ] Read V2 status once and require `GREEN_FROZEN` with no active execution lease.
- [ ] Report Universal Sports Step 6 **GREEN + FROZEN**, program progress **6/8 = 75%**, blocker **NONE**.
- [ ] Stop. Do not automatically start Step 7.

## Final Verification Commands

Before any completion claim on the V2 implementation branch:

```bash
python -m pytest -q tests/test_runless_v2_schema_contract.py
python -m pytest -q tests/test_runless_v2_state_store.py tests/test_runless_v2_github_authority.py tests/test_runless_v2_finalization_readback.py
python -m pytest -q tests/test_runless_v2_sandbox_executor.py tests/test_runless_v2_proof_service.py tests/test_runless_v2_api.py
python -m pytest -q tests/test_runless_v2_cutover_contract.py tests/test_runless_v2_*.py
python -m py_compile runless_v2/*.py
```

Live completion additionally requires:
- Supabase migration/readback + security advisor review;
- exact Vercel deployment identity;
- authority-disabled certification matrix;
- V2 self-proof and immutable GitHub receipt;
- exact-head App-5204253 gate readback;
- exact merge;
- immutable freeze/manifest readback;
- then, separately, the Step-6 proof/merge/ledger/closeout sequence.

No single green test, deployment, check run, or database write is sufficient by itself to claim GREEN + FROZEN.
