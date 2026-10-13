# Universal Sports Source Intelligence + Finalization Worker V1 — Design Spec

## Purpose

Create one provider-independent sports data and finalization architecture for API 2 / MONSTER that routes every sports field through credible capability-specific sources, preserves canonical identity and provenance, uses minimum trustworthy quorum, and removes Render from the critical path for final frozen-registry persistence.

## Scope

Eight serial steps:

1. Architecture + Contract Lock
2. Credible Provider Registry
3. Field-Level Source Router
4. Trust + Quorum Engine
5. Provider Health + Canonical Identity
6. Source Receipt + Provenance
7. MONSTER Finalization Worker
8. Full Integration + Certification

Step 1 locks architecture only. It does not mutate sports product code or reopen NBA Spread Step 4.

## Existing Systems Reused

This architecture extends rather than replaces:

- `devsystem/unified_data_identity_provider_health_graph_v1.py`
- `devsystem/unified_data_identity_provider_health_cases_v1.json`
- `sports_api/nfl_data_router_v1.py`
- `devsystem/finalization_100_percent_finalizer_v1.py`
- Step 2A
- scope-aware leases
- parallel workstream isolation
- Runless exact-head proof
- terminal receipts
- frozen registry
- anti-loop protection
- Finalization Authority

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

- Approved Provider Pool: sources permitted for one or more capabilities.
- Active Providers: sources actually consulted for the current field/request.
- Category Owners: provider(s) selected for a specific field.

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

It may not blend incompatible metrics just to force agreement.

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
- fabrication=false
- receipt digest

## Finalization Worker Contract

Step 7 introduces a narrow provider-independent mutation worker. It acts only after product/proof gates are already satisfied.

The worker must:

1. consume an already-certified finalization packet,
2. verify repository/workstream identity,
3. verify expected registry ref/head/blob/revision/state hash,
4. verify certified candidate/merged-main identity,
5. verify authorized freeze/thaw scope,
6. construct the deterministic target registry,
7. recompute canonical state hash,
8. verify target before write,
9. perform one atomic GitHub compare-and-swap / force-with-lease write,
10. independently read back the registry,
11. verify exact revision/hash/token/thaw retirement and unrelated-state preservation,
12. emit GREEN + FROZEN only after successful readback.

Hard protections:

- Render is not required for registry persistence.
- GitHub Actions fallback remains disabled unless explicitly authorized.
- No product/runtime mutation.
- No model/projection mutation.
- No blind whole-registry overwrite without exact preconditions.
- No retry loop on deterministic failure.
- No success claim before exact readback.
- No billing-dependent platform may be the sole finalization authority.
- Worker remains portable across execution environments.

## Step 2A / Parallel Isolation

Finalization remains one authoritative workstream with one active problem, one target registry mutation, one expected registry head, one write attempt per unchanged evidence state, and one readback proof. Cross-workstream freeze/thaw mutation is forbidden.

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

## Step 1 Acceptance Criteria

Step 1 is design-complete only when these are locked:

1. no page-wide universal source authority,
2. `DATA_FIELD` remains the routing unit,
3. active providers means actually consulted providers only,
4. provider pool is capability-scoped,
5. incompatible metrics cannot substitute,
6. quorum expands only when required,
7. source receipts are deterministic and provenance-complete,
8. canonical identity remains internal,
9. provider health is field-aware,
10. finalization is independent of Render,
11. GitHub registry writes require exact preconditions and readback,
12. Step 2A and workstream isolation remain mandatory,
13. GitHub Actions fallback is not introduced,
14. frozen sports product code is not reopened by Step 1,
15. implementation remains blocked until written-spec review and implementation-plan approval.

## Proposed Step 1 Freeze Token

`UNIVERSAL_SPORTS_SOURCE_FINALIZATION_V1_STEP1_ARCHITECTURE_CONTRACT_FROZEN`

The token becomes authoritative only after the written spec is reviewed, the implementation plan is approved, and Step 1 receives its required exact-head/frozen-registry closeout.

## Non-Goals

Step 1 does not reopen NBA Spread Step 4, mutate existing NBA Spread frozen artifacts, change projection math/probabilities, claim paid-provider access not actually configured, fabricate data to satisfy quorum, create duplicate canonical IDs, replace existing control-plane systems, create a paid Render workaround, or label every approved provider as active.

## Program Success Criteria

The eight-step program is complete only when API 2 / MONSTER can choose credible providers per field, resolve canonical identities, stop after minimum trustworthy evidence, expand fallbacks only when needed, explain accepted values through source receipts, fail closed on exhaustion/mismatch, finalize without Render build capacity, and verify frozen-registry state by independent readback before claiming GREEN + FROZEN.