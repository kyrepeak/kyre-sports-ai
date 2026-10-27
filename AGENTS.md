# KYRE SPORTS Repository Agent Contract

## Guardian shared-infrastructure preflight

For any **API 2** or **MONSTER** page-work mission, read the repository's Guardian shared-infrastructure readiness contract before making decisions about shared infrastructure, provider/runtime dependencies, deployment surfaces, Supabase, Runless, Finalizer, or Vercel.

The authoritative contract is `GUARDIAN_SHARED_INFRASTRUCTURE_READINESS_CONTRACT_V1` in:

- `devsystem/guardian_shared_infrastructure_readiness_v1.json`
- `devsystem/guardian_shared_infrastructure_readiness_v1.py`

Load it through the validated reader:

- API 2: `load_readiness("API2")`
- MONSTER: `load_readiness("MONSTER")`

The returned policy is `CONTEXT_ONLY_NOT_EXECUTION_EVIDENCE`.

Guardian readiness **must not** be used as API 2 or MONSTER branch authority, PR authority, lease/lock/checkpoint authority, proof authority, failure/recovery state, execution authorization, percentage/progress evidence, frozen-registry evidence, or **GREEN/FROZEN** authority. Each system must independently run its own Step 2A, Anti-Loop, reliability/root-cause gates, proof path, merge path, deployment convergence, and freeze certification.

If the Guardian readiness contract is missing, malformed, or fails validation, fail closed for shared-infrastructure assumptions. Do not invent or borrow infrastructure facts from another system's state.

Page-only merges do not invalidate the shared readiness baseline. Guardian owns refresh of the baseline when shared infrastructure changes.
