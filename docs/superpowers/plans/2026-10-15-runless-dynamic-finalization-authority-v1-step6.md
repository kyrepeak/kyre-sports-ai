# Runless Dynamic Finalization Authority V1 — Step 6

## Regression + Existing NBA Candidate Recovery

Step 6 proves that the dynamic finalization authority can recover an already-terminal candidate without restarting it or relaxing the live mutation authority contract.

The read-only recovery seam must:

1. resolve exactly one durable proof row for the requested workstream/task/candidate/fencing generation;
2. allow only terminal `FAILED` or `GREEN_FROZEN` states;
3. require zero live Runless execution leases for the workstream;
4. preserve the original proof ID, candidate SHA, failure class/detail, and fencing generation;
5. return `restart_required = false`;
6. direct failed proofs to diagnosis of the existing terminal failure rather than a new proof;
7. keep the normal mutation resolver unchanged so active work still requires one live execution lease;
8. hardcode no NBA candidate, PR, historical PR #1526, or historical allowed branch in production authority code.

Recovery target for certification only: NBA PR #1541 / candidate `0caf4fd0728b5ff666653b385a63d1c8ced9f154`, treated as read-only corroborating evidence.

Freeze token: `RUNLESS_DYNAMIC_FINALIZATION_AUTHORITY_V1_STEP6_FROZEN`.
