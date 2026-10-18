# WNBA PRA FanDuel + Multi-Source Product V2 Design

**Date:** 2026-10-18
**Workstream:** `monster-wnba-pra-fanduel-multisource-v2`
**Source main:** `6cd1e17c57eb39cbb35946242f0f3bc604ac09d3`
**Predecessor closeout:** WNBA PRA Playoff Product V1 / PR #1649 / `MONSTER_WNBA_PRA_PLAYOFF_PRODUCT_V1_FROZEN`

## 1. Goal

Make the WNBA PRA page show only players who are actually available on the current FanDuel PRA board for the verified active game, while keeping Kyre Sports API ownership, improving data freshness and source quality, and feeding the existing model with better verified inputs rather than silently replacing its frozen probability math.

The finished page should feel like a clean decision product, not a developer dashboard: exact FanDuel player eligibility, current line, model projection, over/under probability, edge, evidence confidence, and expandable supporting context.

## 2. Success Criteria

The step is complete only when all of the following are true:

1. The WNBA page still reads market truth through the Kyre Sports API boundary; Streamlit does not call FanDuel directly.
2. Player display eligibility is controlled by a current verified FanDuel PRA offer for the exact player/game identity.
3. The page never displays a player merely because the model has a projection if FanDuel does not currently list that player for PRA.
4. The Kyre Sports API has a fresh, persisted, auditable WNBA prop snapshot for the active slate.
5. One upstream WNBA roster/stat source timeout cannot collapse the entire player-prop ingestion path when corroborating verified identity data is available.
6. Multi-source evidence is used for schedule, player identity/roster, availability, recent form, matchup context, and market comparison where available.
7. FanDuel is authoritative for display eligibility and its displayed PRA line; other books are comparison/context only.
8. Existing projection, Monte Carlo, qualification, ranking, and final-card math are preserved unless a narrowly scoped bug is proven and separately approved.
9. Stale, conflicting, unmatched, or unresolved evidence fails closed or lowers confidence; it is never converted into fabricated certainty.
10. Exact-head proof, merged-main verification, registry freeze, read-back, and lease release complete before GREEN + FROZEN.

## 3. Current Verified State

### 3.1 Page/API ownership

The current customer page is `wnba_pra_hub_v3615.py`. It installs `wnba_pra_api_market_bridge_v1` before building the product snapshot. The bridge reads persisted WNBA player-prop snapshots through `KyreWNBAAPIClient`; Streamlit does not hold sportsbook credentials.

### 3.2 Persisted market data problem

The current Supabase WNBA prop store contains only one persisted snapshot, dated 2026-08-27. Its source is a historical DraftKings transport. The latest recorded scheduler attempt also dates to 2026-08-27 and ended in `provider_cycle_failed` because the official WNBA roster lookup timed out.

Therefore the existing page wiring is correct, but its live market-truth store is stale.

### 3.3 Provider gap

The WNBA failover layer currently supports the Kyre-owned provider, SportsGameOdds, and generic configured providers. There is no dedicated WNBA FanDuel collector in the WNBA collector path, even though other sports in the repository have FanDuel-specific collectors.

## 4. Scope

### In scope

- Add a WNBA FanDuel market adapter/collector behind the Kyre Sports API provider boundary.
- Persist current FanDuel WNBA PRA offers into the existing durable prop snapshot store.
- Keep FanDuel as the exact player/line eligibility source for the WNBA PRA customer page.
- Add resilient player identity/roster verification so a single official-source timeout does not invalidate otherwise corroborated exact identities.
- Add multi-source evidence assembly for availability, recent form, opponent context, and market comparison.
- Add a successor WNBA PRA product view that filters to FanDuel-eligible players and clearly labels evidence/freshness.
- Preserve current customer page routing and universal navigation behavior.
- Add focused tests, exact-head proof, merge, freeze, and read-back.

### Out of scope

- Rewriting Universal Runtime V5.
- Replacing the frozen WNBA projection engine.
- Changing sportsbook prices into projection inputs.
- Creating a second prediction engine.
- Adding wager execution or stake sizing.
- Reopening PR #1649 or stale historical WNBA PRs.
- Fixing unrelated Supabase RLS findings in this workstream.

## 5. Authority and Isolation

Exactly one mutation lane is allowed:

- Branch: `monster-wnba-pra-fanduel-multisource-v2`
- Base: current main at workstream creation
- One PR
- One Runless proof authority
- One scope lease
- No duplicate deployment/proof/run chain

API 2 remains a separate workstream. Shared architecture may be read, but live branches, runs, leases, proofs, blockers, and percentages are not imported from API 2.

## 6. Data Ownership Rules

### 6.1 FanDuel: display eligibility + displayed line

For the WNBA PRA page, a player is customer-visible only when a current FanDuel PRA offer matches all of:

- verified WNBA game identity,
- exact player identity,
- PRA market identity,
- current/future pregame state,
- allowed freshness window,
- valid line,
- valid side/price structure where required by the downstream decision layer.

FanDuel owns the displayed PRA threshold. If FanDuel removes the player/market, the player disappears from the FanDuel-qualified customer board even if other books still list the player.

### 6.2 Kyre Sports API: transport and storage owner

The Streamlit page must continue to read only through the hosted Kyre Sports API. FanDuel collection occurs server-side/provider-side and persists into the existing snapshot store. No FanDuel secret, cookie, or provider credential is exposed to Streamlit.

### 6.3 Official WNBA / Kyre identity: canonical identity owner

Official/Kyre schedule and canonical IDs remain the preferred identity source for games, teams, and players.

If the primary roster endpoint times out, the system may use corroborating exact identity data already available from other trusted WNBA/Kyre sources or persisted verified roster state. Fallback must be explicit and auditable; fuzzy guessing is not allowed.

### 6.4 Other books: comparison only

Other sportsbooks/providers may provide:

- corroborating line availability,
- min/max/median market context,
- source-count confidence,
- disagreement diagnostics.

They do not override FanDuel player visibility and do not move the model projection.

## 7. Source Strategy

Use the best available independent sources for each category instead of pretending one source is universal truth.

### Schedule / game identity

Primary: Kyre Sports API / official WNBA game identity.

Corroboration: existing WNBA schedule transport and other already integrated schedule sources.

### Player identity / roster

Primary: canonical Kyre/official WNBA player identity.

Fallback: persisted verified roster snapshots and independently corroborated exact player/team identity already available in the repository.

A fallback may confirm an identity; it may not manufacture a player ID.

### Availability / injury

Use multiple available sources when possible. Material disagreement becomes `CONFLICT` or `UNRESOLVED` and blocks final-card certification for the affected player.

### Recent form / historical stats

Use existing verified game-log/stat sources already integrated with the WNBA stack. Recent-form summaries are descriptive evidence; they are not silently converted into new model coefficients.

### Market truth

FanDuel: eligibility and displayed line.

Other books/providers: comparison and disagreement context.

## 8. Proposed Architecture

### Component A — WNBA FanDuel collector

Add a dedicated WNBA FanDuel collector under `sports_api/collectors/` following the repository's existing sportsbook collector patterns.

Responsibilities:

- obtain current WNBA event/market payload through the supported server-side transport,
- emit only supported pregame player-prop structures,
- preserve source event/market/offer IDs,
- preserve source timestamps,
- map PRA market aliases into the existing canonical feed format,
- never infer a line or player that FanDuel did not publish.

### Component B — resilient roster/identity resolver

Add a narrow resolver used by the WNBA prop adapter before a provider cycle is rejected.

Resolution order:

1. current canonical official/Kyre roster identity,
2. fresh persisted verified roster identity,
3. corroborated exact player/team identity from an already trusted integrated source,
4. fail closed.

The resolver must record which path confirmed the player and why a fallback was needed.

### Component C — provider failover integration

Extend the existing WNBA provider/failover layer to recognize the WNBA FanDuel collector as a first-class provider without deleting current providers.

Recommended order for this product lane:

1. FanDuel market truth for page eligibility,
2. existing provider(s) for market comparison/failover diagnostics,
3. generic configured providers where already supported.

A provider is not considered successful merely because HTTP returned 200; it must produce a fresh normalized board that passes exact identity and market-integrity checks.

### Component D — persisted snapshot freshness gate

The API market bridge must reject snapshots that are stale for the active slate.

Required metadata surfaced to the product layer:

- snapshot date,
- collected_at,
- provider/source,
- FanDuel availability flag,
- matched game count,
- matched FanDuel PRA player count,
- unresolved identity count,
- freshness state.

Historical snapshots may remain stored for audit, but they must not masquerade as today's market truth.

### Component E — FanDuel eligibility projection join

Add a read-only successor view-model step that joins:

- preserved model projections,
- preserved stored Monte Carlo probabilities,
- FanDuel current PRA offers,
- exact game/player identity,
- current availability evidence,
- optional multi-book comparison.

A player appears on the primary board only when `fanduel_eligible == true`.

### Component F — customer page cleanup

Create a WNBA PRA successor page over V3.6.15.

Primary card fields:

- player name + headshot + team logo,
- matchup,
- FanDuel PRA line,
- model PRA projection,
- over probability,
- under probability,
- edge,
- decision/confidence label,
- freshness/evidence badge.

Expandable detail may show:

- P/R/A projection components,
- projected minutes and role,
- recent form,
- opponent context,
- verified matchup history where available,
- FanDuel vs multi-book comparison,
- availability evidence,
- source/freshness diagnostics.

Internal engine/module terminology stays collapsed under Advanced Diagnostics.

## 9. Probability Integrity

This workstream improves the trustworthiness of the inputs feeding the existing decision product. It does not declare that more sources automatically mean a more accurate probability.

Rules:

- FanDuel line is the threshold being evaluated.
- Sportsbook prices and consensus are not projection inputs.
- Current role/minutes/availability and verified matchup inputs may flow only through already approved model interfaces.
- If a desired factor is not already modeled, show it as supporting context rather than silently inventing a weight.
- A probability cannot be customer-certified when required identity, freshness, or availability gates fail.
- Source disagreement must be visible in evidence state and may reduce confidence or block final selection.

## 10. Failure Behavior

### FanDuel unavailable

Show an honest empty/pending state for the FanDuel-qualified board. Do not substitute another book and call it FanDuel.

### FanDuel lists a player not resolvable to exact WNBA identity

Quarantine that offer in diagnostics; do not display it.

### Official roster lookup times out

Try the approved resilient identity resolver. If exact identity still cannot be established, fail the player closed rather than failing the entire slate when unrelated players are verifiable.

### Market snapshot stale

The page must label the market unavailable/pending and suppress final market decisions. Model research may remain visible only where the existing product contract permits it, but no stale FanDuel line is presented as current.

### Availability unresolved

Player research may remain visible, but final-card eligibility is blocked until availability is resolved under the existing integrity contract.

## 11. Testing Strategy

### Collector tests

- parses current FanDuel WNBA PRA payload shape,
- preserves source IDs/timestamps,
- ignores unsupported/non-PRA markets for eligibility,
- rejects malformed/stale/future-conflicting offers,
- never synthesizes missing lines.

### Identity tests

- official identity success,
- primary timeout + persisted verified fallback success,
- corroborated exact fallback success,
- ambiguous identity fails closed,
- one bad player does not collapse unrelated exact matches.

### API/store tests

- current FanDuel snapshot persists,
- stale Aug. 27 snapshot cannot satisfy an Oct. 19 active-slate read,
- snapshot metadata includes provider/freshness/player count,
- API bridge remains the only Streamlit market transport.

### View-model tests

- projection-only player absent when FanDuel PRA is absent,
- FanDuel-listed exact player present,
- FanDuel line shown even when other books disagree,
- other books affect comparison state only,
- unresolved availability blocks final-card certification.

### Page tests

- only FanDuel-eligible players render on primary board,
- mobile layout remains clean,
- source/freshness state is visible,
- advanced diagnostics remain collapsed,
- universal navigation regressions stay green.

### Regression tests

Preserve the predecessor WNBA PRA Playoff Product V1 suite, successor-compatible speed tests, universal navigation tests, and any existing WNBA API bridge tests.

## 12. Closeout / GREEN + FROZEN Contract

The workstream is not GREEN + FROZEN until:

1. one exact candidate SHA is selected,
2. focused + regression tests pass on that exact SHA,
3. authoritative Runless proof succeeds on that exact SHA,
4. proof-before-merge is satisfied,
5. the exact proven SHA is merged,
6. merged main is read back and verified,
7. frozen registry/manifest is forward-ported transactionally,
8. new freeze token is durably written,
9. canonical read-back confirms the token and merged main,
10. scope lease is released,
11. no duplicate proof/run/PR/deployment path exists.

Target freeze token:

`MONSTER_WNBA_PRA_FANDUEL_MULTISOURCE_V2_FROZEN`

## 13. Separate Security Finding

Supabase inspection exposed internal Runless/temp tables with RLS disabled. This is a real security concern but is intentionally excluded from this product workstream because enabling RLS without the matching policies could break the control plane.

Handle it later as a separate isolated security repair with its own scope, proof, and rollback plan.
