# API 2 Step 2B + Step 2C Permanent Execution Controls — Design

Date: 2026-10-24  
Status: Approved for immediate implementation  
Authoritative execution base: `refs/heads/api2-main`

## Intent
API 2 permanently owns its execution evidence and follows: Failure → Anti-Loop → Step 2C → Step 2B → Step 2A → Execute → Verify → GREEN → FROZEN.

## Hard isolation
API 2 authority accepts only API2-owned identities, paths, evidence, proof records, and freeze records. Shared repository/infrastructure may transport bytes, but another system's branch, PR, run, lease, checkpoint, ledger, state, proof, progress, recovery, or GREEN/FROZEN result is never API 2 evidence.

## Authority refs
- `refs/heads/api2-main`: API 2 execution base.
- `refs/heads/api2-proof-registry`: API 2 exact-candidate proof records.
- `refs/heads/api2-frozen-registry`: API 2 hash-chained freeze checkpoints.

## Components
- `api2_isolation_guard_v1.py`: fail-closed API2 identity boundary.
- `api2_anti_loop_v1.py`: failed-action/evidence/hypothesis fingerprints and blind-repeat block.
- `api2_step2c_root_cause_v1.py`: required-domain investigation, deepest supported root cause, narrow human-only blockers.
- `api2_step2b_reliability_gate_v1.py`: acceptance/path/root-cause/mapping/dependency/reachability/config/regression/verification/repair-delta gate.
- `api2_step2a_authority_v1.py`: one active problem/path and single-use repair authorization.
- `api2_execution_controller_v2.py`: permanent ordered state machine and truthful live status.
- `api2_execution_plan_compiler_cert_v1.py`: API2-native deterministic plan compiler rooted at `api2-main`.
- `api2_frozen_registry_v1.py`: API2-owned FROZEN registry; GREEN does not imply FROZEN.
- `api2_step2bc_cert_v1.py`: whole-stack adversarial certification.

## Human-only blockers
Only missing user-controlled credentials/access, external approval requiring the user, unresolved product/business choice with multiple valid answers, or irreversible/destructive action requiring explicit authorization may stop autonomous recovery. Normal technical failures remain autonomous.

## Proof contract
Exact candidate bytes must pass the focused control-plane suite, compiler compatibility suite, Python compilation, isolation import scan, and whole-stack certification. A proof record is then written/read back from the API2 proof registry before merge. After merge to `api2-main`, exact artifact blobs are reverified and the suite is rerun. FROZEN requires a hash-valid checkpoint written/read back from `api2-frozen-registry`.

## Non-goals
No sports page, provider routing, model, projection, probability, ranking, or selection changes.
