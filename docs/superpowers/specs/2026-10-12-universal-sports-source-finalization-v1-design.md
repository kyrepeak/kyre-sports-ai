# Universal Sports Source Intelligence + Finalization Worker V1 — Design Spec

## Purpose

**Workstream ID:** `universal-sports-source-finalization-v1`

Create one provider-independent sports data and finalization architecture for API 2 / MONSTER that routes every sports field through credible capability-specific sources, preserves canonical identity and provenance, uses minimum trustworthy quorum, and removes Render from the critical path for final frozen-state persistence.

The architecture must make future sports-page work faster by reducing provider hunting, preventing page-wide source loyalty, expanding source checks only when needed, and giving every step a deterministic path to GREEN + FROZEN.

## Scope

Eight serial steps:

1. Architecture + Contract Lock + Finalization Bootstrap
2. Credible Provider Registry
3. Field-Level Source Router
4. Trust + Quorum Engine
5. Provider Health + Canonical Identity
6. Source Receipt + Provenance
7. Finalization Worker Hardening + Legacy Bridge
8. Full Integration + Certification

Step 1 locks the architecture and introduces only the minimum finalization foundation required for this new workstream to reach an independently verifiable FROZEN state without Render. It does not reopen or mutate NBA Spread Step 4 product code.

## Existing Systems Reused

This architecture extends rather than replaces:

- `devsystem/unified_data_identity_provider_health_graph_v1.py`
- `devsystem/unified_data_identity_provider_health_cases_v1.json`
- `sports_api/nfl_data_router_v1.py`
- `devsystem/finalization_100_percent_finalizer_v1.py`
- Step 2A
- scope-aware leases
- parallel workstream isolation
- Runless exact-head proof semantics
- terminal receipts
- frozen-registry protection
- anti-loop protection
- Finalization Authority / 100% Convergence V1

No duplicate mutation-ownership system may be introduced.

## Governing Rules

### Field-level ownership

No provider may become the page-wide master source. The unit of work remains `DATA_FIELD`.

Every required field/category receives an explicit route, including schedule, game identity, team/player identity, rosters, injuries, official stats, advanced stats, history, sportsbook lines, line movement, public bet count, public bet percentage, money percentage, and news/context.

### Capability-compatible fallbacks

Fallbacks may substitute only for the same semantic metric. Raw bet count cannot be replaced by bet percentage. Bet percentage cannot be replaced by money percentage. Incompatible metrics fail closed instead of being silently substituted.

### Minimum trustworthy quorum

The router must not hit every approved provider on every request. It resolves canonical identity, selects the strongest eligible source route, obtains the minimum evidence required by policy, stops as soon as the policy is satisfied, and expands only for provider failure, stale data, ambiguity, low confidence, or disagreement.

This is the primary speed mechanism.

### Provider pool versus active providers

The architecture distinguishes:

- **Approved Provider Pool** — sources permitted for one or more capabilities.
- **Active Providers** — sources actually consulted for the current field/request.
- **Category Owners** — provider(s) selected for a specific field.

The live board may never label an unused source as active.

### Canonical internal identity

API 2 / MONSTER owns canonical team, player, and game IDs. External provider IDs and names are aliases. Ambiguous identity fails closed.

### Field-aware health

Provider health is capability-specific, not a single global boolean. A provider may be healthy for schedules but degraded for injuries. Every accepted field result carries provider ID, field, freshness, quality, validation result, fallback rank, and rejected-attempt reasons.

## Approved Provider Registry Contract

Step 2 will implement a capability registry. The approved pool may include, where access/licensing permit:

- official league sources such as NBA.com / NBA Stats
- official team sources
- Sportradar
- SportsDataIO
- Basketball-Reference / Stathead
- ESPN
- CBS Sports
- AP / Reuters for news/context
- RotoWire
- Action Network
- Covers
- VSiN
- direct sportsbook / structured odds feeds
- additional sport-specific authoritative sources later

Being in the approved pool does not imply the provider is active, universally authoritative, credentialed, or currently reachable.

## Trust Policy Contract

Every field route declares:

- semantic metric ID
- eligible providers
- preferred order
- minimum freshness
- minimum accepted quality
- whether one-source authority is allowed
- whether independent verification is required
- minimum quorum size
- disagreement rule/tolerance
- escalation order
- fail-closed terminal state

## Quorum Decisions

The quorum engine may terminate with:

- `ACCEPTED_SINGLE_AUTHORITY`
- `ACCEPTED_QUORUM`
- `ACCEPTED_FALLBACK_QUORUM`
- `DISAGREEMENT_REQUIRES_EXPANSION`
- `UNAVAILABLE_AFTER_COMPATIBLE_SOURCE_EXHAUSTION`
- `AMBIGUOUS_IDENTITY_FAIL_CLOSED`
- `STALE_DATA_FAIL_CLOSED`

It may not blend incompatible metrics merely to force agreement.

## Source Receipt Contract

Every accepted field decision must eventually emit a deterministic source receipt containing at minimum:

- workstream ID
- sport/page/step
- canonical entity/game ID
- field / semantic metric ID
- providers actually attempted
- selected provider(s)
- fallback rank
- normalized value fingerprint
- freshness observation
- provider health at decision time
- agreement/disagreement result
- quorum policy ID
- rejected attempts with reason
- aliases used
- `fabrication=false`
- receipt digest

## Step 1 Finalization Bootstrap Contract

The existing monolithic frozen-registry file has become a transport bottleneck because each finalization rewrites a large shared document. Step 1 therefore introduces a small, append-oriented finalization ledger for this new architecture workstream. It is not allowed to rewrite or reinterpret legacy frozen entries.

The bootstrap consists of:

1. a deterministic contract certifier for this Step-1 architecture,
2. a small immutable freeze record for the Step-1 exact merged SHA and proof digest,
3. a compact manifest that points to the latest valid freeze record and carries its own canonical hash,
4. exact compare-and-swap preconditions for manifest updates,
5. independent GitHub readback before any GREEN + FROZEN claim.

### Bootstrap authority boundary

The bootstrap is authoritative only for checkpoints created by `UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1` until Step 7 completes the explicit legacy bridge. It must not mutate, supersede, or claim ownership of the legacy monolithic registry.

That means:

- legacy frozen state remains frozen and untouched,
- current NBA Spread Step 4 legacy closeout remains a separate workstream,
- this new program can freeze its own checkpoints without Render,
- Step 7 must either bridge the new ledger into the global finalization model or prove a safe migration path before wider adoption.

### Freeze record requirements

Every Step-1 freeze record must contain:

- version
- workstream ID
- checkpoint/freeze token
- exact merged-main SHA
- exact certified candidate SHA when different
- proof kind
- proof digest
- artifact path → blob SHA map
- Step 2A single-authority assertion
- GitHub Actions fallback = 0
- Render dependency = false
- unrelated legacy-registry mutation = false
- canonical record hash

### Manifest requirements

The manifest must contain:

- version
- repository
- workstream
- revision
- current freeze token
- freeze-record path
- freeze-record blob SHA
- merged-main SHA
- previous manifest hash or `GENESIS`
- canonical state hash

The manifest update must fail closed if the expected prior blob/revision/hash has changed.

## Finalization Worker Contract

Step 7 hardens and generalizes the bootstrap into the reusable MONSTER Finalization Worker. It acts only after product/proof gates are already satisfied.

The hardened worker must:

1. consume an already-certified finalization packet,
2. verify repository/workstream identity,
3. verify the relevant registry/ledger expected ref/head/blob/revision/state hash,
4. verify certified candidate/merged-main identity,
5. verify authorized freeze/thaw scope,
6. construct the deterministic target state,
7. recompute canonical hashes,
8. verify target before write,
9. perform one atomic GitHub compare-and-swap / force-with-lease write path,
10. independently read back final state,
11. verify exact revision/hash/token/thaw retirement and unrelated-state preservation,
12. emit GREEN + FROZEN only after successful readback.

Hard protections:

- Render is not required for final-state persistence.
- GitHub Actions fallback remains disabled unless explicitly authorized.
- No product/runtime mutation.
- No model/projection mutation.
- No blind whole-registry overwrite without exact preconditions.
- No retry loop on deterministic failure.
- No success claim before exact readback.
- No billing-dependent platform may be the sole finalization authority.
- Worker remains portable across execution environments.

## Step 2A / Parallel Isolation

Finalization remains one authoritative workstream with one active problem, one target finalization mutation, one expected state head, one write attempt per unchanged evidence state, and one readback proof. Cross-workstream freeze/thaw mutation is forbidden.

## Performance Contract

Adding providers must not create linear fan-out. The system must support:

- early stop after minimum trustworthy evidence
- capability filtering before network calls
- cached provider-health/capability metadata with explicit freshness
- parallel probes only when quorum requires more than one source
- no blind polling
- no revalidation of identical immutable evidence
- reusable source receipts while freshness policy permits
- immediate fail-closed classification for semantic incompatibility

Finalization must also avoid rewriting unrelated frozen state merely to add one checkpoint.

## Step 1 Acceptance Criteria

Step 1 is complete only when these are locked and proven:

1. no page-wide universal source authority,
2. `DATA_FIELD` remains the routing unit,
3. active providers means actually consulted providers only,
4. provider pool is capability-scoped,
5. incompatible metrics cannot substitute,
6. quorum expands only when required,
7. source receipts are deterministic and provenance-complete,
8. canonical identity remains internal,
9. provider health is field-aware,
10. Render is not required for this workstream's Step-1 freeze,
11. the bootstrap ledger is isolated from the legacy monolithic registry,
12. exact preconditions and independent readback are mandatory,
13. Step 2A and workstream isolation remain mandatory,
14. GitHub Actions fallback is not introduced,
15. frozen sports product code is not reopened by Step 1,
16. exact-head proof binds the architecture spec and bootstrap artifacts,
17. the Step-1 freeze record and manifest read back exactly from GitHub.

## Step 1 Freeze Token

`UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP1_ARCHITECTURE_CONTRACT_FROZEN`

## Non-Goals

Step 1 does not reopen NBA Spread Step 4, mutate legacy frozen-registry entries, change projection math/probabilities, claim paid-provider access not actually configured, fabricate data to satisfy quorum, create duplicate canonical team/player/game identities, create a paid Render workaround, or label every approved provider as active.

## Program Success Criteria

The eight-step program is complete only when API 2 / MONSTER can choose credible providers per field, resolve canonical identities, stop after minimum trustworthy evidence, expand fallbacks only when needed, explain accepted values through source receipts, fail closed on exhaustion/mismatch, finalize without Render build capacity, and verify final frozen state by independent readback before claiming GREEN + FROZEN.
