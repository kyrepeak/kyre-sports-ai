# Guardian Shared Infrastructure Readiness Contract V1 — Design

## Intent

Publish one permanent, read-only Guardian-owned description of shared infrastructure so API 2 and MONSTER can discover the current infrastructure baseline from the repository without the user manually copying Guardian chat history into their page-work chats.

## Goals

- Give API 2 and MONSTER the same machine-readable shared-infrastructure facts.
- Make the baseline discoverable at repository entry through `AGENTS.md`.
- Validate the baseline with deterministic code before a consumer uses it.
- Preserve hard isolation: Guardian context is never API 2/MONSTER execution evidence or authority.
- Fail closed on malformed, missing, or cross-system contract data.
- Keep the contract dependency-light and network-free.

## Non-goals

- Do not share Guardian branches, PRs, leases, locks, checkpoints, execution state, failure state, recovery state, receipts, proof artifacts, percentages, or GREEN/FROZEN evidence with API 2/MONSTER.
- Do not authorize API 2 or MONSTER work.
- Do not replace Runless, Step 2A, Anti-Loop, Step 2B/2C/etc., or system-local frozen registries.
- Do not add a network service or runtime dependency.
- Do not modify sports-feature behavior.

## Constraints

- Guardian, API 2, and MONSTER remain independent systems.
- Kyre Sports production authority remains protected GitHub `main` plus existing Runless final-gate behavior.
- The readiness baseline is repository context only.
- Page-only merges do not make the infrastructure baseline stale; Guardian republishes it only when shared infrastructure changes.
- Consumers must resolve current Git `main` identity independently when exact-SHA authority is required.

## Approaches considered

### A. Repository baseline + strict reader + repository entry instructions — selected

Create a Guardian-owned JSON baseline, a deterministic Python reader/validator, and a root `AGENTS.md` instruction that tells API 2/MONSTER page work to load the reader before infrastructure-sensitive work. This is cheap, source-controlled, reviewable, works offline, and keeps authority separate.

### B. Documentation only — rejected

A Markdown handoff would be readable but not reliably machine-validatable and could silently drift.

### C. Live Guardian network service — rejected

A service would make API 2/MONSTER depend on Guardian availability and violate the desired hard isolation.

## Contract shape

`devsystem/guardian_shared_infrastructure_readiness_v1.json` owns only shared facts:

- contract/version/status/publisher;
- GitHub repository/protected-main/final-gate identity;
- Vercel production project names and stale-preview count;
- Supabase migration/security/isolation summary;
- source-of-truth manifest pointer;
- explicit allowed uses and forbidden uses;
- freshness semantics scoped to shared-infrastructure revision, not every product merge.

`devsystem/guardian_shared_infrastructure_readiness_v1.py` exposes:

- `load_readiness(consumer_system: str, repo_root: Path | None = None) -> dict`
- `validate_baseline(payload: Mapping[str, Any]) -> dict`

The returned packet stamps the consumer (`API2` or `MONSTER`), is immutable-by-convention/read-only context, and includes a canonical digest. The validator rejects unknown consumers, malformed required fields, non-GREEN published state, missing isolation policy, or any forbidden execution-authority field.

## Automatic discovery

A root `AGENTS.md` directs any API 2 or MONSTER page-work agent to load the readiness reader before shared-infrastructure decisions. This is the repository-level handoff: the user does not need to restate Guardian history in every chat.

The consumer is still responsible for its own Step 2A/Anti-Loop/proof/freeze path. Guardian readiness may explain infrastructure context but can never satisfy those gates.

## Acceptance criteria

1. API 2 and MONSTER receive equivalent shared facts but distinct consumer labels.
2. Unknown consumers fail closed.
3. A payload containing forbidden execution-state/authority keys fails validation.
4. The committed baseline matches the current frozen Guardian source-parity manifest for migration count, production projects, and stale-preview count.
5. `AGENTS.md` explicitly requires the readiness preflight and explicitly forbids borrowed Guardian evidence.
6. Existing Guardian source-parity/security tests remain green.
7. Protected merge and post-merge production convergence remain required before freeze.
