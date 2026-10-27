# Guardian Source-of-Truth + Configuration Parity V1

## Mission
Make Guardian fail closed on Git/Supabase/Vercel drift and prevent a healthy production surface from being mistaken for a reproducible environment.

## Authoritative scope
- GitHub: `kyrepeak/kyre-sports-ai`
- Supabase: `jqajcdckalsfizbvngiu`
- Vercel production projects: `kyre-sports-api`, `kyre-runless-proof`, `kyre-sports-finalizer`

## Implemented
1. Source-index all 38 live Supabase migration records by version, name, and content MD5.
2. Source-control all nine live Edge Function entrypoints, including historical API2 tombstones.
3. Explicitly allowlist the eight intentional public RLS/no-policy deny-by-default tables.
4. Classify six `kyre_runtime` RLS-disabled tables as backend-only after direct proof of zero anon/authenticated table grants and zero anon/authenticated schema grants.
5. Add a deterministic post-merge convergence evaluator that requires all three production projects to be READY on the exact main SHA with zero runtime error/fatal counts and healthy Supabase security state.
6. Make freeze eligibility require zero stale preview env variables and a complete migration SQL payload archive.

## Fail-closed open items
- The exact SQL payloads for the 38 live migration ledger rows are not yet source-controlled. Hash inventory is complete, reconstruction archive is not.
- Nine preview-only Finalizer env records tied to merged PRs #1527, #1528, and #1529 remain. The connected Vercel interface exposes list/edit/create but no project-env delete action; Vercel rejects detaching an env from all targets.

## Freeze rule
`GUARDIAN_SOURCE_OF_TRUTH_CONFIGURATION_PARITY_V1_FROZEN` may be issued only when:
- migration payload archive = COMPLETE
- stale preview env count = 0
- post-merge convergence = GREEN
- targeted + previous Guardian security regression tests pass

Until then the mission remains OPEN by design.
