# Runless Base-Drift Authority Supersession V1 — Operations

This recovery exists only for an exact Runless proof that already reached `MERGE_AUTHORIZED` and then became unmergeable because upstream `main` advanced. It retires that exact merge authority as historical `SUPERSEDED_BASE_DRIFT`; it does not transfer proof to another SHA.

## Connected execution path

Connected ChatGPT execution calls the privileged Supabase RPC `runless_v2.request_base_drift_supersession_transport(...)`. The connected client never receives `RUNLESS_PROOF_AUTH_TOKEN`, the Runless bearer, or the Vercel protection bypass. Supabase Vault owns `runless_v2_transport_bearer` and `runless_v2_vercel_protection_bypass`, and the security-definer transport sends them server-side only to the allowlisted `kyre-runless-proof*.vercel.app` service.

The transport first checks `runless_v2.authority_supersessions` under an advisory transaction lock. An exact prior result is idempotently reused; a competing successor is rejected. Only when no durable result exists does it POST to `/supersede-base-drift`, then independently reads the durable supersession row and verifies its identity. HTTP response fields alone never become authority.

## Recovery sequence

The Runless service verifies the old proof is exactly `MERGE_AUTHORIZED`, carries its immutable receipt digest and App-5204253 gate check ID, and has no live Runless execution lease. GitHub must corroborate that the same PR is open on the same branch, its head is the requested successor, current `main` differs from the old expected main, and the successor descends from both the old candidate and current main.

The atomic Supabase mutation inserts one immutable audit record and marks only the old proof `SUPERSEDED_BASE_DRIFT`. It never creates a successor proof. After durable read-back, the successor must enter normal Step 2A and earn a **fresh exact-head proof**, receipt, and App-5204253 `runless-final-gate` before merge.

There is never a parallel merge/finalization authority lane. Repeated upstream movement produces an explicit historical supersession chain, never hidden row edits or a newest-proof heuristic.

GitHub branch protection remains unchanged. **GitHub Actions fallback: 0.**
