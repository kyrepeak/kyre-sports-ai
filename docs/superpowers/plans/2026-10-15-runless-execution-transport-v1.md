# Runless Execution Transport V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the connected API 2 / MONSTER execution environment a safe, reusable way to invoke the existing Runless V2 proof authority exactly once, recover from transport interruption without duplicate authority, and then use that transport to unblock Runless Dynamic Finalization Authority V1 Step 1.

**Architecture:** Keep `runless_v2/app.py` and `execute_proof_request(...)` as the only proof executor. Add a small authenticated HTTP transport client that can be run from one reusable Vercel named sandbox, harden the existing proof lease with a heartbeat during long sandbox execution, and rely on existing Supabase uniqueness/fencing plus GitHub App 5204253 for all proof/gate authority. The bridge is stateless and owns no proof truth.

**Tech Stack:** Python 3.13, FastAPI/Pydantic 2, `httpx`, asyncio, existing Runless V2 Supabase/PostgREST state store, Vercel Sandbox, pytest, GitHub App 5204253.

**Spec:** `docs/superpowers/specs/2026-10-15-runless-execution-transport-v1-design.md`

## Global Constraints

- Reuse the existing Runless V2 `POST /prove`; do not build another proof executor.
- One authoritative repair branch only: `api2-runless-execution-transport-v1`.
- Do not mutate NBA PR `#1541` or Runless Dynamic Finalization Authority PR `#1544` during repair implementation.
- No duplicate proof request, lease, Vercel proof sandbox, deployment, or PR.
- Supabase `runless_v2` remains durable proof/workstream authority.
- GitHub App `5204253` remains the only publisher of `runless-final-gate`.
- GitHub Actions fallback remains `0`.
- Bearer credentials must never be committed, logged, persisted in sandbox snapshots, emitted in JSON, or shown in chat.
- The transport sandbox is diagnostic/transport-only; it never executes proof commands itself.
- Existing Step 2A, expected-head, scope-lease, fencing, frozen-registry, receipt, and finalization rules remain mandatory.
- The original live certification candidate is `e8f833d761b809206c6ac67a245e388f6a225098`, but that value must not be hard-coded into reusable transport code.

## Review Focus

1. **HTTP success with malformed/non-JSON body:** client must fail closed with a transport error and never reinterpret it as proof success; pin in Task 1 tests.
2. **Token or URL accidentally appearing in exception text/output:** redact credentials and return bounded machine-readable errors; pin in Task 1 tests.
3. **Heartbeat renewal racing terminal proof completion:** stop heartbeat before receipt/gate transitions and carry the latest valid claim; pin in Task 2 tests.
4. **Transport interruption after the server already created durable proof state:** recovery must read durable state first and reuse the proof rather than blindly resubmit; pin in Task 3 tests.
5. **A live certification request whose candidate moved after preflight:** exact-head Step 2A validation must reject it and leave #1541 untouched; pin in Task 4 live checks.

---

## File Structure

- Create `runless_v2/transport_client.py` — stateless HTTP client + CLI for `prove`, `status`, and `receipt`; machine-readable JSON output and state projection.
- Create `tests/test_runless_v2_transport_client.py` — transport contract, authentication/redaction, recovery/idempotency projection tests.
- Modify `runless_v2/proof_service.py` — add fenced lease heartbeat around existing long-running proof sandbox execution only; do not duplicate proof logic.
- Modify `tests/test_runless_v2_proof_service.py` — heartbeat, stale-fence, and no-duplicate execution tests.
- Create `docs/runless-execution-transport-v1-operations.md` — exact Vercel named-sandbox invocation/recovery procedure without embedding secrets.
- Create `devsystem/contracts/runless-execution-transport-v1.json` — machine-readable certification contract and immutable scope exclusions.
- Create `devsystem/runless_proof_plans/runless-execution-transport-v1.json` — exact static proof plan for the repair candidate.
- Create `tests/test_runless_execution_transport_v1_contract.py` — static contract guards, including untouched #1541/#1544 scope exclusions and App 5204253 gate requirement.

### Task 1: Stateless Runless HTTP transport client

**Files:**
- Create: `runless_v2/transport_client.py`
- Create: `tests/test_runless_v2_transport_client.py`

**Interfaces:**
- Consumes: existing Runless V2 API endpoints `POST /prove`, `GET /status/{proof_id}`, `GET /receipts/{proof_id}` and existing `ProofRequest` fields.
- Produces: `TransportClient`, `TransportError`, `project_transport_state(native_state: str) -> str`, `request_proof(...) -> dict[str, Any]`, `get_status(...) -> dict[str, Any]`, `get_receipt(...) -> dict[str, Any]`, plus `python -m runless_v2.transport_client` CLI JSON output.

- [ ] **Step 1: Write failing client contract tests**

Add tests asserting:
- `project_transport_state("IDENTIFY") == "REQUESTED"`.
- `2A_LOCK`/`FINGERPRINT` map to `QUEUED`.
- `REUSE_OR_PROVE` through `RUNLESS_FINAL_GATE` map to `RUNNING`.
- `MERGE_AUTHORIZED` through `GREEN_FROZEN` map to `SUCCEEDED`.
- `FAILED` maps to `FAILED`.
- unknown native state raises `TransportError`.

- [ ] **Step 2: Run mapping tests and verify RED**

Run: `python -m pytest -q tests/test_runless_v2_transport_client.py -k transport_state`

Expected: FAIL because `runless_v2.transport_client` does not exist.

- [ ] **Step 3: Implement the minimal client interfaces**

In `runless_v2/transport_client.py`, define:

```python
class TransportError(RuntimeError): ...

def project_transport_state(native_state: str) -> str: ...

class TransportClient:
    def __init__(self, *, base_url: str, bearer_token: str, timeout_seconds: float = 30.0) -> None: ...
    def request_proof(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def get_status(self, proof_id: str) -> dict[str, Any]: ...
    def get_receipt(self, proof_id: str) -> dict[str, Any]: ...
```

Use `httpx.Client`; send bearer auth only in the `Authorization` header; strip trailing `/` from base URL.

- [ ] **Step 4: Add failing request/response tests**

Use `httpx.MockTransport` or injected client transport. Assert:
- `POST /prove` receives the exact generic request payload once.
- HTTP 409/503 returns `TransportError` carrying only status + safe Runless detail.
- HTTP 200 malformed/non-JSON response fails closed.
- bearer token never appears in `str(exc)`, returned JSON, or captured stdout/stderr.
- response includes native `state`/`status`, projected `transport_state`, `proof_id`, `candidate_sha`, `receipt_digest`, `gate_check_run_id` when present, and `execution_identity` equal to durable `proof_id` when no separate execution identity is returned.

- [ ] **Step 5: Run request/response tests and verify RED**

Run: `python -m pytest -q tests/test_runless_v2_transport_client.py`

Expected: FAIL on unimplemented HTTP/normalization behavior.

- [ ] **Step 6: Implement safe response normalization and CLI**

Add:

```python
def normalize_transport_response(payload: dict[str, Any]) -> dict[str, Any]: ...

def main(argv: list[str] | None = None) -> int: ...
```

CLI commands:
- `prove --base-url ... --task-id ... --workstream ... --candidate-sha ... --lease-id ... --authorization-id ... [--expected-main-sha ...]`
- `status --base-url ... --proof-id ...`
- `receipt --base-url ... --proof-id ...`

Read bearer token only from `RUNLESS_PROOF_AUTH_TOKEN`; emit one JSON object to stdout; emit safe JSON error to stderr and nonzero exit on failure.

- [ ] **Step 7: Run Task 1 tests**

Run: `python -m pytest -q tests/test_runless_v2_transport_client.py`

Expected: PASS.

- [ ] **Step 8: Commit Task 1**

Commit: `feat: add Runless V2 transport client`

### Task 2: Fenced execution heartbeat for long proof runs

**Files:**
- Modify: `runless_v2/proof_service.py`
- Modify: `tests/test_runless_v2_proof_service.py`

**Interfaces:**
- Consumes: existing `state_store.renew(claim, ttl_seconds)`, `LeaseClaim`, and existing `sandbox.execute(...)`.
- Produces: internal async heartbeat helper that preserves one lease/fencing generation and returns the latest valid claim; no new external authority.

- [ ] **Step 1: Write failing heartbeat tests**

Add tests for:
- a sandbox execution lasting beyond one heartbeat interval causes at least one `state_store.renew(...)` call before completion;
- renewal always uses the same lease token and fencing generation;
- successful proof continues with the latest renewed claim;
- heartbeat task is cancelled/stopped before receipt/gate terminal transitions;
- stale-fence renewal raises/fails closed and the stale execution cannot call `put_or_read_receipt` or `publish_gate_and_readback`;
- heartbeat failure does not start a second sandbox execution.

- [ ] **Step 2: Run heartbeat tests and verify RED**

Run: `python -m pytest -q tests/test_runless_v2_proof_service.py -k heartbeat`

Expected: FAIL because no heartbeat exists.

- [ ] **Step 3: Implement heartbeat helper**

Add an internal helper with explicit signature similar to:

```python
async def _execute_with_lease_heartbeat(
    *,
    sandbox: Any,
    state_store: Any,
    claim: Any,
    request: ProofRequest,
    github: Any,
    ttl_seconds: int,
    timeout_seconds: int,
) -> tuple[Any, Any]: ...
```

Rules:
- heartbeat interval is safely below TTL (for example `max(1, min(ttl_seconds // 3, 60))`);
- renew only the existing claim;
- never acquire a second lease in the heartbeat;
- if renewal fails, cancel/stop accepting the sandbox result and fail closed before receipt/gate mutation;
- return `(sandbox_result, latest_claim)`.

- [ ] **Step 4: Wire the helper into `execute_proof_request(...)`**

Replace only the direct long `await sandbox.execute(...)` section. Preserve existing failure classification and all downstream receipt/gate/finalization logic.

- [ ] **Step 5: Run focused proof-service tests**

Run: `python -m pytest -q tests/test_runless_v2_proof_service.py`

Expected: PASS.

- [ ] **Step 6: Run Runless V2 regression suite**

Run: `python -m pytest -q tests/test_runless_v2_state_store.py tests/test_runless_v2_proof_service.py tests/test_runless_v2_api.py`

Expected: PASS with no changed existing semantics except lease renewal during active execution.

- [ ] **Step 7: Commit Task 2**

Commit: `fix: renew Runless lease during active proof execution`

### Task 3: Reusable connected-execution operating contract

**Files:**
- Create: `docs/runless-execution-transport-v1-operations.md`
- Create: `devsystem/contracts/runless-execution-transport-v1.json`
- Create: `devsystem/runless_proof_plans/runless-execution-transport-v1.json`
- Create: `tests/test_runless_execution_transport_v1_contract.py`

**Interfaces:**
- Consumes: Task 1 CLI, existing Vercel `kyre-runless-proof` project, Vercel named sandbox capability, existing Vercel secret `RUNLESS_PROOF_AUTH_TOKEN`, existing Runless V2 `/prove` API.
- Produces: one deterministic operational lane and a Runless proof plan capable of certifying the repair branch itself.

- [ ] **Step 1: Write failing static contract tests**

Assert the contract fixes these values:
- version: `RUNLESS_EXECUTION_TRANSPORT_V1`;
- authority: `RUNLESS_V2_EXISTING_POST_PROVE`;
- gate name: `runless-final-gate`;
- GitHub App ID: `5204253`;
- GitHub Actions fallback: `0`;
- transport project: `kyre-runless-proof`;
- repair branch: `api2-runless-execution-transport-v1`;
- forbidden mutation scopes include NBA PR `1541`, Runless Step-1 PR `1544`, sports runtime/model/page files, and frozen registry state unless explicitly required by later finalization;
- no bearer/token literal exists in committed files.

- [ ] **Step 2: Run static contract test and verify RED**

Run: `python -m pytest -q tests/test_runless_execution_transport_v1_contract.py`

Expected: FAIL because contract/plan/docs do not exist.

- [ ] **Step 3: Add operations document**

Document exactly one reusable named transport sandbox lane:
- resolve current `kyre-runless-proof` production URL from Vercel rather than hard-coding a deployment URL;
- create/resume one named sandbox with repository source and no persistent bearer secret;
- inject `RUNLESS_PROOF_AUTH_TOKEN` only in the command environment for `python -m runless_v2.transport_client ...`;
- after transport interruption, inspect Supabase/Runless status first; never blindly issue a third call;
- stop or leave the transport sandbox without treating it as proof authority.

- [ ] **Step 4: Add machine-readable contract and proof plan**

The proof plan must run only focused transport/heartbeat/contract tests plus Python compile checks for changed Runless modules. No product/public sports probe is required for the generic repair itself.

- [ ] **Step 5: Run Task 3 tests**

Run: `python -m pytest -q tests/test_runless_execution_transport_v1_contract.py tests/test_runless_v2_transport_client.py tests/test_runless_v2_proof_service.py`

Expected: PASS.

- [ ] **Step 6: Compile changed Python**

Run: `python -m py_compile runless_v2/transport_client.py runless_v2/proof_service.py`

Expected: exit 0.

- [ ] **Step 7: Commit Task 3**

Commit: `docs: lock Runless execution transport operating contract`

### Task 4: Repair-branch proof and duplicate-safety certification

**Files:**
- No new product files unless a failing test identifies a root cause.
- Evidence is durable Runless V2 state + immutable receipt + exact-head GitHub check.

**Interfaces:**
- Consumes: Tasks 1–3 and existing `POST /prove` authority.
- Produces: exact-head repair candidate with one Runless proof, one immutable receipt, one App-5204253 `runless-final-gate`, and merge authorization.

- [ ] **Step 1: Freeze exact repair candidate identity**

Read repair branch head once and record it as the only candidate for this certification attempt. Confirm branch diff contains only approved repair files and the design/plan.

- [ ] **Step 2: Capture isolation baselines**

Record:
- NBA PR #1541 head SHA;
- Runless Step-1 PR #1544 head SHA (`e8f833...` unless it legitimately moved);
- current `main` SHA;
- no active proof/lease for the repair workstream.

- [ ] **Step 3: Execute exactly one repair proof through the new transport**

Use one named transport sandbox and Task 1 CLI. Resolve the repair workstream scope lease/authorization from repository authority. Submit exactly one request. If transport returns ambiguous failure, read durable state before any replacement attempt.

- [ ] **Step 4: Verify duplicate-safety matrix against durable state**

Prove:
- repeated identical request returns the same durable proof identity;
- active proof does not create a second proof/lease;
- terminal success returns same receipt;
- concurrent identical calls converge on one `(workstream, request_fingerprint)` row;
- wrong task/workstream and stale candidate fail closed;
- stale fence cannot publish receipt/gate.

Use test doubles for destructive concurrency cases where live duplication would violate Step 2A; use live durable readback only for the one authoritative proof identity.

- [ ] **Step 5: Require exact-head gate evidence**

Require:
- check name `runless-final-gate`;
- conclusion `SUCCESS`;
- check SHA equals exact repair candidate;
- GitHub App ID `5204253`;
- matching immutable receipt digest and durable `MERGE_AUTHORIZED` state.

- [ ] **Step 6: Verify isolation baselines unchanged**

NBA PR #1541 head SHA and Runless Step-1 PR #1544 head SHA must match Step 2 baselines. If either changed, classify before proceeding; do not overwrite.

- [ ] **Step 7: Open the single repair PR if none exists**

Open exactly one PR from `api2-runless-execution-transport-v1` to `main`. Do not create a replacement PR on ordinary proof failure.

- [ ] **Step 8: Merge repair PR with expected-head protection**

Merge only if exact candidate proof is valid and GitHub accepts `expected_head_sha=<certified repair candidate>`.

- [ ] **Step 9: Verify merged-main provenance and repair availability**

Read merged `main`, verify the merge contains the certified candidate, and verify the existing `kyre-runless-proof` production service remains healthy. Do not create a gratuitous deployment if Git integration already produced the authoritative merged deployment.

### Task 5: Live unblock of original Runless Dynamic Finalization Step 1

**Files:**
- Do not modify PR #1544 unless its proof returns a terminal code/root-cause failure requiring a candidate patch.

**Interfaces:**
- Consumes: merged transport repair, original workstream `runless-dynamic-finalization-authority-v1`, exact current PR #1544 head, existing Runless proof plan/scope authority, and existing Finalization Authority.
- Produces: original Step 1 genuinely `GREEN_FROZEN` or one explicit external blocker.

- [ ] **Step 1: Re-anchor Step 2A to live #1544**

Read PR #1544 again. Require one exact current candidate. Read Supabase durable state before mutation. If a proof now exists, reuse/classify it; do not create another.

- [ ] **Step 2: Reconfirm `PROOF_NOT_CREATED` before creation**

Only if there is still no proof, no receipt, and no active lease for the exact current candidate may the transport create one proof.

- [ ] **Step 3: Submit exactly one original Step-1 proof**

Invoke the merged transport client against existing Runless V2 `/prove` using repository-derived task/workstream/lease/authorization/expected-main fields. Persist proof identity immediately via existing Runless V2 claim path.

- [ ] **Step 4: Follow the authoritative durable state to terminal proof**

Do not poll blindly. Read the known proof identity at meaningful transitions. On terminal failure, classify the exact failure before any patch/replacement proof. On success, require immutable receipt + exact-head App-5204253 `runless-final-gate`.

- [ ] **Step 5: Continue existing Finalization Authority without user pause**

From valid `MERGE_AUTHORIZED`:
- exact-head gate readback;
- merge PR #1544 with `expected_head_sha` protection;
- obtain merged-main SHA;
- verify merge provenance;
- perform existing frozen-registry/finalization transaction;
- canonical readback;
- close Runless durable state to `GREEN_FROZEN`;
- verify execution lease released.

- [ ] **Step 6: Final regression/isolation readback**

Require:
- Step 1 durable state `GREEN_FROZEN`;
- freeze token/manifest state hash present;
- final gate bound to the exact certified candidate;
- NBA PR #1541 remains untouched;
- no duplicate proof rows/leases for the original workstream;
- GitHub Actions fallback remains `0`.

- [ ] **Step 7: Report GREEN + FROZEN only from authoritative evidence**

The final status board must cite the exact candidate SHA, proof ID, receipt digest, gate check run ID/App 5204253, merged-main SHA, freeze token/manifest hash, canonical readback, and released lease.

## Plan Self-Review

- **Spec coverage:** transport invocation, idempotency, durable recovery, heartbeat/fencing, exact-candidate rejection, receipt/gate handoff, finalization, isolation, and the 12 requested proof cases are all assigned to Tasks 1–5.
- **Step scan:** each implementation step is bounded to one code/test/verification action; live operations are separated from reusable code.
- **Type consistency:** Task 1 produces the only transport client interface; Task 2 consumes existing `LeaseClaim`/`state_store.renew`; later tasks invoke the CLI rather than defining another transport API.
- **Review Focus:** all five listed failure modes have explicit tests/checks in Tasks 1–4.
- **Proportion:** implementation remains deliberately small: one new client module, one heartbeat modification, tests/contracts/docs, and no rewrite of Runless V2.
