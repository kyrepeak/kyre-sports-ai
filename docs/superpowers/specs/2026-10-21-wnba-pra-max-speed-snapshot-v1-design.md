# WNBA PRA Maximum-Speed Snapshot V1 — Design

Date: 2026-10-21
Workstream: `monster-wnba-pra-max-speed-snapshot-v1`
Base main: `b7a6641ef5b7fcd84fa9ceb191b8f4e92ef3ee43`
Status: design only; no production behavior changed by this document

## 1. Intent

Make the WNBA PRA page load at maximum practical speed without weakening data quality, sportsbook freshness, model correctness, provider provenance, or the existing GREEN + FROZEN control plane.

The user experience target is that opening or returning to WNBA PRA feels immediate. The page should no longer synchronously rebuild the full preserved PRA model graph in Streamlit before the initial board can render.

## 2. Non-negotiable constraints

1. Kyre Sports API remains the only application-facing WNBA data gateway.
2. No SGO, ESPN, ESPN BET, or Render is allowed in the active WNBA PRA speed path.
3. Vercel/Runless remains the authoritative production execution and verification path.
4. Exact sportsbook identity, line, side, American price, market identity, and capture timestamp must remain provider-specific. Conflicting sportsbook lines are never averaged.
5. FanDuel remains primary for PRA markets and DraftKings remains lazy fallback when the primary is unusable, exactly as certified by the currently frozen WNBA PRA market repair.
6. Existing projection math, matchup math, probability math, qualification rules, ranking rules, Monte Carlo semantics, final-card selection, and sportsbook influence rules must not change merely to improve speed.
7. Existing frozen market-routing artifacts are not silently modified. If implementation proves that a frozen mountpoint must change, it requires an explicit scoped thaw/finalization transaction before mutation.
8. Existing Speed V3 player-detail precompute remains compatible and continues to accelerate player opens.
9. Step 2A and anti-loop remain mandatory: one active speed problem, one branch, one PR, one proof path, one deployment path, one lease, and no duplicate async work.

## 3. Root cause

The current Streamlit PRA render path performs too much synchronous work before first paint.

`wnba_pra_hub_v3617.render_wnba_pra_hub()` resolves the slate, builds the full product snapshot, builds market consensus, builds player views, and only then renders the product. `wnba_pra_product_snapshot_v1.build_product_snapshot()` separately invokes base projection work, exact-market grading, matchup grading, stored Monte Carlo/final-card reads, schedule diagnostics, availability diagnostics, and role diagnostics.

Several of those layers repeat the same underlying work during one page load. In particular, market grading rebuilds the projection frame, while matchup grading separately rebuilds schedule/player/context work and re-reads paired PRA markets. Cold player variance/profile work can also require many player history reads. Streamlit route changes additionally purge WNBA module graphs for memory safety, making the first PRA entry behave like a cold load more often.

The Kyre Sports API market-board endpoint is not the main bottleneck. The bottleneck is the amount of synchronous orchestration and duplicate model/data work still executed in the Streamlit render path after the market data arrives.

## 4. Selected architecture

### 4.1 One finished PRA page snapshot

Introduce one Kyre Sports API read surface for the initial WNBA PRA page, conceptually:

`GET /api/v1/wnba/pra/page-snapshot?date=YYYY-MM-DD&season=2026`

The exact route name may be adjusted during planning only if an existing certified route namespace provides a safer mount point, but the contract stays the same: Streamlit receives one complete, render-ready PRA snapshot from Kyre Sports API.

The response contains enough information for the initial PRA board and final card to render without running the heavy preserved PRA assembly chain in Streamlit. It includes:

- verified slate/game context;
- exact current provider-specific PRA offers and provider health;
- player identity/team/opponent linkage;
- preserved projection outputs needed by the page;
- preserved matchup outputs needed by the page;
- history/variance summaries needed by the page;
- market probabilities, fair prices, edge/EV, freshness and quality fields already produced by the preserved model;
- final-card output already selected by the preserved model;
- diagnostics/provenance needed for the existing UI;
- snapshot generated time, source/capture timestamps, cache status, generation duration, and schema/version metadata.

The endpoint is an assembly/cache boundary, not a new prediction model.

### 4.2 Compute once, reuse everywhere

Within one backend generation, expensive common dependencies are loaded exactly once and passed forward rather than independently reconstructed by each layer.

The generation graph should be logically:

1. resolve verified slate once;
2. obtain exact PRA market board once;
3. build base player projection state once;
4. obtain reusable player-history/profile inputs with bounded concurrency and caching;
5. derive market grading from the shared projection/history/market inputs;
6. derive matchup grading from shared projection/history/market/context inputs;
7. read/reuse preserved stored Monte Carlo outputs where applicable;
8. select the preserved final card;
9. serialize one immutable render snapshot.

No duplicate projection run, duplicate market-board read, or per-layer duplicate player-history fetch is allowed inside one page-snapshot generation.

### 4.3 Two-tier freshness and cache policy

Fast-changing market fields and slow-changing basketball context must not be forced onto the same expiration clock.

Market quotes keep a short freshness window, initially 10–30 seconds, bounded by the existing market freshness rules. Schedule, identities, historical profiles, role context, and other slower data may use longer certified TTLs where their underlying semantics permit it.

The page-snapshot cache uses stale-while-revalidate behavior:

- if a fresh snapshot exists, return it immediately;
- if a still-safe stale snapshot exists, return it immediately with explicit stale/cache metadata while one bounded refresh is scheduled or performed by the authoritative backend path;
- never serve sportsbook prices beyond the existing model's stale safety threshold as if they were fresh;
- never start duplicate refreshes for the same date/season key;
- if no valid snapshot exists, build one through the single authoritative generation path.

Stale-while-revalidate is a latency mechanism only; it may not hide data degradation or fabricate freshness.

### 4.4 Streamlit becomes a thin renderer

The initial WNBA PRA page should perform one Kyre Sports API page-snapshot read and render the returned payload.

When the page-snapshot endpoint is healthy, Streamlit must not synchronously rebuild projections, histories, matchup grading, market grading, Monte Carlo selection, or final-card selection during initial page render.

A correctness-safe degraded path may retain the existing frozen V3.6.17 render chain only for explicit page-snapshot failure. Degraded fallback must be observable and must not silently become the normal path.

The existing player-detail Speed V3 Steps 7–9 remain intact for Game Center/player detail interactions after the initial board is visible.

### 4.5 Memory behavior

The current memory-safe router may continue releasing heavy stale WNBA route graphs when a route changes. The maximum-speed architecture should avoid making the initial PRA board dependent on re-importing the entire heavy legacy model graph.

A small snapshot client/renderer module may remain lightweight and cache-safe across WNBA route transitions if doing so does not violate the existing memory contract. Heavy model modules remain backend-only for snapshot generation or degraded fallback.

## 5. Alternatives considered

### A. Add more Streamlit `st.cache_data`

This is the smallest change but is not selected. It helps repeat visits while preserving duplicate cold-path work, module-purge sensitivity, and many Python-layer calls in the initial render.

### B. Parallelize the existing Streamlit model graph

This could shorten some cold loads, but it keeps the UI process responsible for model assembly, increases concurrency complexity, risks duplicate provider/history work, and makes deterministic anti-loop/failure ownership harder.

### C. Backend render-ready snapshot — selected

This moves heavy computation to the authoritative Kyre Sports API boundary, makes the Streamlit initial path one read plus rendering, gives one place to deduplicate/cache/prewarm work, and preserves the existing model as the source of truth.

## 6. Performance targets and proof gates

The targets are performance goals, not claims until measured on the exact candidate and merged production head:

- warm PRA initial board: under 0.50 seconds;
- normal fresh PRA initial board: under 1.00 second;
- true-cold PRA initial board: under 2.00 seconds when upstream providers are responsive;
- return/switch back to PRA: near-instant from valid cache;
- warm player detail open: preserve or beat existing Speed V3 target of 0.75 seconds;
- page-snapshot network reads from Streamlit initial board: 1;
- projection generations per page-snapshot generation: 1;
- market-board reads per page-snapshot generation: 1;
- duplicate refresh generations for the same snapshot key: 0.

Every performance measurement must report cold/warm classification, cache state, network read count, backend generation time, Streamlit read/render time where measurable, exact commit SHA, and endpoint schema version.

A target miss is not GREEN. It must be classified as provider latency, cold-start/runtime latency, duplicate computation, cache miss/design flaw, Streamlit render latency, or another evidenced class before any follow-up patch.

## 7. Correctness and equivalence gates

For the same deterministic fixture/input state, the new snapshot path must preserve the current certified WNBA PRA product outputs for all fields that are not presentation/cache metadata.

Tests must cover at minimum:

- exact sportsbook quote preservation and no averaging;
- FanDuel-primary/DraftKings-fallback behavior remains delegated to the already-certified Kyre Sports API market gateway;
- no SGO/ESPN/ESPN BET/Render in the active speed path;
- one snapshot request supplies the initial page;
- no duplicate base projection or market-board read during one generation;
- player-history/profile reuse rather than duplicate per-layer reads;
- fresh cache hit;
- safe stale-while-revalidate behavior with single-flight refresh;
- cold generation;
- provider degradation;
- exact output-equivalence fixtures against the preserved model;
- degraded Streamlit fallback is explicit, bounded, and not the default path;
- existing Speed V3 player-detail behavior remains intact.

## 8. Frozen-artifact and thaw rule

The prior live-props repair is already GREEN + FROZEN. This speed work must first identify the exact finalization records covering any file it proposes to mutate.

Preferred implementation is additive: new snapshot builder/cache/router/client/renderer modules plus the smallest possible integration seam. If a required integration seam is frozen, implementation must acquire one scoped thaw authorization for only those exact paths, prove the mutation, merge, re-freeze them in the same finalization transaction, and retire the thaw before lease release.

No frozen artifact may be edited merely because it is convenient.

## 9. Expected implementation surface

Planning should prefer new additive files and the smallest integration touch points. Likely surfaces include:

- one Vercel Kyre Sports API page-snapshot builder/cache module;
- one API route registration seam;
- one Streamlit page-snapshot client/adapter;
- one thin WNBA PRA snapshot renderer or compatibility bridge;
- targeted regression/performance tests;
- one immutable Runless proof plan;
- finalization metadata only after production proof.

Exact filenames and thaw scope are intentionally deferred to the implementation plan after current frozen-registry/finalization ownership is inspected.

## 10. Rollout and failure ownership

The rollout stays on one authoritative chain:

candidate tests and local/isolated benchmarks → exact-head Runless proof → one PR merge → merged-main verification → exact merged-SHA Vercel deployment verification → live Kyre Sports API snapshot verification → live Streamlit PRA verification → Finalization Ledger V2 transaction → GREEN + FROZEN → lease/thaw retirement.

If the exact candidate fails, classify and repair that same lane. Do not create another PR, deployment lane, proof request, or concurrent speed implementation.

If production page-snapshot fails after merge, the explicit degraded fallback may protect correctness while the speed lane remains non-green. A fallback-rendered page is not proof that maximum-speed V1 passed.

## 11. Definition of GREEN + FROZEN

This workstream reaches 100% only when all of the following are true:

1. exact candidate scope and frozen/thaw ownership are proven;
2. all correctness, routing, anti-source, single-flight, equivalence, regression, and performance tests pass;
3. exact-head Runless proof is terminal and authorized;
4. the exact proven candidate is merged;
5. merged main is verified and deployed on Vercel at the exact merged SHA;
6. production Kyre Sports API page-snapshot returns correct current WNBA PRA data;
7. production Streamlit initial PRA path demonstrably consumes the snapshot path and meets the accepted speed gates;
8. Finalization Ledger V2 records the exact merged artifacts, proof receipt, performance evidence, and freeze token;
9. any scoped thaw is retired and affected artifacts are re-frozen;
10. the scope lease is released only after canonical terminal read-back shows GREEN_FROZEN.

Until those gates are satisfied, status remains yellow and the workstream percentage must remain below 100%.
