# KYRE GUARDIAN Security + Configuration Hardening V1

## Intent
Raise shared-infrastructure security and configuration cleanliness to a trustworthy terminal state without modifying API 2 or MONSTER private state, sports product logic, frozen model behavior, or the previously frozen Guardian cleanup lane.

## Scope
- Harden the live Supabase project against exposed temporary API2 artifacts and unsafe public execution surfaces.
- Remove orphaned temporary database artifacts only after proving they have no repository references or database dependents.
- Harden remaining mutable function search paths where behavior is unchanged.
- Preserve all current runtime schemas, frozen registries, leases, checkpoints, and production data.
- Clean stale Finalizer configuration only when it is provably obsolete and not required by an active branch/workstream.
- Verify Vercel production remains READY on the authoritative main SHA and runtime errors remain absent.
- Produce repeatable proof and an immutable freeze receipt for this Guardian-only lane.

## Hard Isolation
- Do not import, mutate, infer, synchronize, or reuse API 2 or MONSTER branches, commits, PRs, runs, leases, locks, checkpoints, ledgers, proof artifacts, frozen state, or execution state.
- Do not alter sports models, sports page presentation, provider routing, sportsbook logic, or frozen feature artifacts.
- The existing Guardian Infrastructure + Automation Cleanup V1 freeze remains untouched.

## Step 2A
One authoritative branch: `guardian-security-configuration-hardening-v1`.
One authoritative PR and one terminal proof path.
No duplicate runs or blind retries.

## Anti-Loop
Every failed signal must be classified before repair. Reuse authoritative evidence; do not rerun unchanged work.

## Acceptance Criteria
1. Supabase project reports ACTIVE_HEALTHY.
2. Supabase Security Advisor has zero ERROR findings.
3. No anonymous or authenticated execution remains on orphaned temporary SECURITY DEFINER functions.
4. Orphaned `_api2_temp_*` tables and temporary helper functions identified by this lane are removed only after zero dependency/reference proof.
5. `runless_v2.is_legal_transition` and retained helper functions have explicit safe search paths where required, with semantics unchanged.
6. No destructive change touches live Runless, API2, MONSTER, or sports-product state.
7. Finalizer configuration contains no provably stale production task/workstream/fencing values from completed API2 work; required secrets are not exposed or invented.
8. All three Vercel production projects remain READY on the authoritative merged SHA and show no new runtime error clusters.
9. Main protection remains active with `runless-final-gate` required.
10. Final proof is merged to main and recorded as `GUARDIAN_SECURITY_CONFIGURATION_HARDENING_V1_FROZEN`.
