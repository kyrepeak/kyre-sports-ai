# WNBA PRA Playoff Product V1 — Design Specification

Date: 2026-10-18
Status: Design approved in chat; written spec awaiting user review
Authoritative design lane: `monster-wnba-pra-playoff-product-v1`
Base main at design start: `3ccae958a953d47284c3ff2a41e573232917af3a`

## 1. Purpose

Rebuild the visible WNBA PRA experience into a professional playoff-first product without rewriting or weakening the already-validated PRA projection, qualification, Monte Carlo, ranking, or selection stack.

The current page exposes too much internal machinery (Step 6/7/8/9 labels, raw hold messages, Monte Carlo controls, zero-count diagnostics, provider health blocks) and treats an off-day as if nothing relevant is happening. During the playoffs, the product should instead understand the active series, automatically surface the next verified game when today is an off day, show a clean PRA decision board, and keep all developer/control-plane detail under Advanced Diagnostics.

Primary user outcome:

> Open WNBA PRA, immediately understand the next relevant playoff matchup, see the strongest player PRA decisions, and drill into evidence without seeing internal pipeline mechanics.

## 2. Non-Negotiable Constraints

1. Preserve the existing validated PRA model stack. No projection, qualification, no-vig, Monte Carlo, ranking, or selection math changes are permitted unless a later explicitly approved model task says otherwise.
2. Sportsbook prices remain read-only grading/context. Market prices never move the model projection.
3. Multi-source is mandatory. No critical slate, availability, statistical, or market conclusion may silently rely on one sportsbook or one sports page when additional sources are available.
4. Never fabricate a line, starter, injury status, player identity, schedule event, statistic, or market quote.
5. Source conflicts must be surfaced internally and must lower confidence or block finalization where appropriate.
6. The user-facing page must be PRA-first. Points, Rebounds, and Assists become components of each player's PRA analysis rather than equal top-level products on this page.
7. Internal Step 6/7/8/9 implementation language must not dominate the production UI.
8. Advanced technical detail remains available under a collapsed Advanced Diagnostics surface.
9. The page must work cleanly on mobile first and remain usable on desktop.
10. Existing universal navigation behavior, frozen model protections, proof-before-merge rules, and one-authoritative-lane execution controls remain in force.

## 3. Existing Architecture to Preserve

The repository already uses layered WNBA PRA wrappers that add presentation/context while preserving the validated production model beneath them. The redesign should continue that pattern instead of replacing the engine.

The production app enters through Universal Runtime V5. The WNBA PRA redesign therefore integrates as a successor presentation/orchestration layer behind the existing PRA route, not as a parallel app and not as a new model engine.

Current preserved model responsibilities include:

- player projection logic
- minutes/role logic
- availability gating
- sportsbook grading
- no-vig probability calculations
- qualification rules
- correlated PRA Monte Carlo
- final-ready gating
- ranking and final selection
- existing performance/cache behavior

The redesign owns presentation, playoff slate resolution, source fusion metadata, market consensus presentation, player-detail composition, and clean final-decision UX.

## 4. Recommended Product Structure

### 4.1 Playoff Header

The top of the page becomes series-aware.

Display:

- competition state: Regular Season / Playoffs / Semifinals / Finals as verified
- active series teams
- series score if verified
- selected game number when applicable
- next verified tip time in the user's local timezone
- current selected slate date
- compact freshness indicator

Behavior:

- If games exist on the selected date, load that verified slate.
- If today is an off day during an active playoff series, automatically resolve the next verified WNBA game and make that the primary slate while clearly saying there is no game today.
- Keep a manual date control so the user can inspect another date.
- Never advance to a fabricated matchup when schedule verification is unavailable.

Example production copy:

`WNBA FINALS • GSV leads 1-0`
`Next: ATL @ GSV • Tomorrow • 5:00 PM PT`

The exact teams/score/time are data-driven; the example is not hard-coded.

### 4.2 PRA Player Board

The main product is a ranked PRA board.

Each player card should contain, when verified/available:

- player headshot
- player name
- team logo
- opponent
- expected role / projected minutes summary
- sportsbook PRA line
- model projected PRA
- model-vs-line edge
- Over probability
- Under probability
- preferred side if qualified
- confidence / evidence quality indicator
- availability state
- compact market-source count

Card hierarchy should emphasize the decision, not the pipeline.

Primary card language:

- `MODEL PRA`
- `MARKET LINE`
- `OVER / UNDER`
- `EDGE`
- `CONFIDENCE`
- `AVAILABILITY`

Do not show `Step 6`, `Step 7`, `Step 8`, or `Step 9` on the normal card surface.

### 4.3 Player Detail

Tapping a player expands a focused analysis panel.

Sections:

1. Decision Snapshot
   - projected PRA
   - market PRA line
   - model edge
   - Over/Under probability
   - confidence
   - availability

2. P / R / A Breakdown
   - points projection
   - rebounds projection
   - assists projection
   - optional uncertainty bands if already available from the preserved engine

3. Minutes + Role
   - projected minutes
   - starter/bench expectation
   - usage/role context
   - relevant rotation notes

4. Recent Form
   - recent completed-game PRA and P/R/A trends
   - minutes context
   - avoid overweighting tiny samples

5. Opponent Context
   - pace
   - defensive profile
   - relevant positional/role context when verified
   - team environment

6. Matchup History
   - only verified, identity-safe history
   - labeled descriptive when sample is weak
   - never treated as an automatic model adjustment unless the preserved model already does so

7. Market Comparison
   - sportsbook lines and prices by source
   - consensus/median line when enough independent books are present
   - disagreement range
   - stale quote labels

8. Why This Side
   - concise model-driven reasons
   - one clear risk/counterargument

9. Sources + Freshness
   - compact summary by default
   - expandable provenance when requested

### 4.4 Final PRA Card

The final card is the clean decision layer.

Rules:

- maximum five qualified PRA picks
- never force five
- one clearly defined final PRA decision per player/market
- no duplicated identical market presented from multiple sportsbooks as separate picks
- if the same player/line exists across books, reuse one simulation result and present the market comparison separately
- final card remains locked when required availability integrity has not passed
- no raw `RUN 5,000,000 SIMS` control on the customer-facing surface

User-facing blocked state should be plain-language, for example:

`Final PRA decisions are waiting for verified availability.`

Do not show internal phrases like `PRA production HOLD`, `Monte Carlo restore disabled`, or raw Step-state messaging outside diagnostics.

## 5. Multi-Source Data Architecture

### 5.1 Source Classes

The system should select the best available sources by data type rather than using one provider for everything.

Schedule / postseason context:

- official WNBA schedule/competition data as primary authority
- at least one independent schedule cross-check when available

Rosters / starters / injuries / availability:

- official WNBA/team information
- independent injury/lineup reporting source(s)
- existing roster/availability integrations already in the repo

Player statistics / recent form / pace / defense / role context:

- official WNBA statistics where appropriate
- independent statistical providers for cross-checking and richer context
- existing ESPN-derived/cached context may remain one contributor, but must not be presented as the universal single source

Markets:

- multiple sportsbook/odds providers whenever available
- existing SportsGameOdds transport may remain an aggregation source
- direct/other supported book feeds may contribute when available
- one sportsbook must not silently define market consensus

### 5.2 Source Quality Labels

Every material internal fact should carry:

- provider/source name
- observation timestamp
- entity identity used for matching
- freshness classification
- verification state
- whether it is primary, corroborating, fallback, or single-source

Suggested evidence states:

- `VERIFIED_MULTI_SOURCE`
- `VERIFIED_PRIMARY`
- `SINGLE_SOURCE`
- `CONFLICT`
- `STALE`
- `UNAVAILABLE`

The production UI may simplify these to user-friendly badges while diagnostics retain exact detail.

### 5.3 Conflict Policy

If two sources disagree:

- schedule conflict: official WNBA authority wins, but log conflict
- player identity conflict: do not merge until identity is resolved
- injury/starter conflict: mark availability unresolved and block Final Card if material
- stat conflict: prefer official/statistically authoritative source for the field, retain alternate observation in diagnostics
- sportsbook conflict: do not choose a winner; preserve all valid quotes and summarize the market distribution

No conflict resolution may invent a missing value.

## 6. Market Consensus Rules

The page should distinguish model truth from market truth.

Model truth:

- preserved projection
- preserved simulation distribution
- preserved qualification/ranking math

Market truth:

- individual sportsbook lines/prices
- consensus line when enough independent quotes exist
- range and disagreement
- freshness

Recommended consensus behavior:

- 2+ independent current books: show consensus/median and source count
- 1 current book: show the quote but label it `single-source`; do not call it consensus
- 0 books: show model projection/research, but no market-based final decision
- stale books: exclude from current consensus and leave visible only in diagnostics/history

The market can grade the model; it cannot move the model projection.

## 7. Availability Integrity

Availability becomes a compact but strict gate.

User-facing states:

- `VERIFIED`
- `LIKELY / MONITOR`
- `UNRESOLVED`
- `OUT / INACTIVE`

Internal logic can remain richer.

Final-card behavior:

- verified enough for model's existing production rules -> eligible
- unresolved material injury/starter/minutes status -> preliminary analysis allowed, final selection blocked
- confirmed out/inactive -> remove from eligible player board/final card, retain diagnostics trail

The redesign must not weaken the existing availability checks.

## 8. Advanced Diagnostics

Collapsed by default.

Move the following out of the normal reading flow:

- Step 6/7/8/9 labels
- raw projection-match counts
- `0/0` context counters
- exact Monte Carlo execution state
- simulation restoration state
- provider health cards
- raw source stack
- covariance fallback notices
- internal hold/check language
- unsupported-layer detail
- retry/recheck controls that are only meaningful operationally

Diagnostics should still expose enough information for maintainers to understand why a pick is blocked or why a source is degraded.

## 9. Empty / Off-Day States

Off-day behavior is a first-class product state, not an error.

When the selected date has no WNBA games:

1. Verify that the date is truly empty.
2. If a next playoff game exists, show the next verified game/series prominently.
3. Allow preparation/research state for the next game where data is valid.
4. Do not fabricate player-market rows before actual valid inputs exist.
5. Keep manual date selection available.

The current `No WNBA games on this date` concept may remain, but it becomes secondary to playoff continuation context.

## 10. Error Handling

Customer-facing errors must answer three questions:

- what is unavailable?
- is the underlying model still safe?
- what happens next?

Examples:

- schedule unavailable -> `Schedule verification is temporarily unavailable. No slate has been fabricated.`
- market unavailable -> `PRA market lines are not available yet. Model projections remain visible; final market decisions are paused.`
- availability conflict -> `Player availability is unresolved. Preliminary analysis is visible; Final PRA decisions are paused.`

Raw tracebacks, provider exceptions, and internal step names belong only in diagnostics/logs.

## 11. Performance

The redesign must preserve the existing speed/cache improvements.

Requirements:

- first meaningful paint should not wait for deep diagnostics
- playoff header and player-board shell render before expensive secondary research where possible
- reuse same-render cached projection/context results
- identical player/line markets across books reuse one simulation
- source refreshes should be scoped by source class and freshness window rather than globally refetching everything
- opening one player should not recompute unrelated players unless required by preserved engine behavior

## 12. Proposed Component Boundaries

Implementation planning should prefer small successor modules with narrow ownership.

Suggested responsibilities:

- `playoff_context`: resolve selected date, active postseason series, next verified game, series metadata
- `source_fusion`: normalize provider observations, evidence states, timestamps, conflicts
- `market_consensus`: sportsbook quote normalization, consensus/range/freshness presentation only
- `pra_product_view`: playoff header, player board, player details, final card, empty states
- `advanced_diagnostics`: existing internal Step/provider/Monte Carlo diagnostics, collapsed by default
- existing preserved PRA engine: unchanged source of projection, simulation, qualification, ranking, selection

Exact filenames are an implementation-plan decision; the ownership boundaries are mandatory.

## 13. Routing and Navigation

The WNBA PRA route remains inside Universal Runtime V5.

Requirements:

- entering WNBA PRA loads the new product surface directly
- date/game/player interactions stay inside the WNBA PRA route
- no fallback to home or another sport on interaction
- query/session state must preserve selected WNBA slate/game/player when appropriate
- universal header/navigation remains visible and consistent with the rest of Kyre Sports AI

## 14. Testing Strategy

Implementation must be test-first for each behavior change.

Required coverage:

1. Playoff off-day resolution
   - today empty, next verified playoff game exists -> next game shown
   - today has game -> today remains selected
   - no verified future game -> honest empty state

2. Multi-source schedule verification
   - official + corroborating agree
   - corroborating missing
   - conflict path

3. Availability integrity
   - verified player
   - unresolved injury/starter state
   - confirmed out
   - conflicting sources

4. Market consensus
   - 3 books agreeing
   - line disagreement
   - only 1 book
   - stale quote exclusion
   - no market available

5. PRA-first UI
   - no normal-page Step 6/7/8/9 headings
   - no raw 5M simulation button in customer surface
   - P/R/A available inside player details
   - Final Card maximum five, never forced

6. Mobile rendering
   - card hierarchy fits narrow viewport
   - tap targets usable
   - no horizontal overflow

7. Regression
   - existing projection outputs unchanged for fixed fixtures
   - qualification outputs unchanged
   - Monte Carlo behavior unchanged
   - ranking/selection unchanged
   - universal navigation unchanged

8. End-to-end route
   - WNBA -> PRA -> next playoff slate -> player -> detail -> back/close retains PRA route

## 15. Migration Strategy

Use a successor presentation/orchestration layer over the current preserved PRA engine.

Do not delete old diagnostic/model modules during this redesign.

Migration sequence:

1. Add new playoff/source-fusion/product-view successor modules.
2. Point WNBA PRA presentation to the successor while keeping existing engine calls intact.
3. Verify fixed-fixture model outputs are byte/value-equivalent where expected.
4. Move legacy Step/provider UI under Advanced Diagnostics.
5. Verify production route behavior on mobile.
6. Only after proof and merged-main verification, certify the successor as frozen.

Rollback is simple: route presentation back to the prior frozen WNBA PRA view without altering the underlying model stack.

## 16. Explicit Non-Goals

This project does not:

- retrain or redesign the PRA model
- change sportsbook weight in projections
- change qualification thresholds
- change 5M/10M Monte Carlo mathematical rules
- create a new points/rebounds/assists prediction product
- rewrite Universal Runtime V5
- alter unrelated NFL/CFB/NBA/MLB/WNBA pages
- invent lineup or market data when coverage is absent

## 17. Acceptance Criteria

The redesign is complete only when all of the following are true:

- WNBA PRA opens as a clean playoff-aware product rather than a Step 6-9 diagnostic page.
- On an off day, the next verified playoff game is surfaced automatically when one exists.
- PRA is the main decision product; P/R/A are integrated into player detail.
- The player board provides model PRA, market line, edge, Over/Under probability, confidence/evidence, and availability when data exists.
- Multiple sources are used by category wherever available; single-source conditions are labeled rather than hidden.
- Multiple sportsbook quotes are preserved and summarized; no single book is silently treated as the market.
- Sportsbook information never changes the model projection.
- Availability uncertainty can block the Final Card without hiding preliminary research.
- Internal Step labels, raw Monte Carlo controls, and provider-health clutter are moved under Advanced Diagnostics.
- No data is fabricated.
- Existing model, Monte Carlo, ranking, qualification, and final-selection regression tests remain green.
- Universal navigation and mobile route behavior remain green.
- Exact-head authoritative proof succeeds.
- Merged-main verification succeeds.
- Finalization ledger records the frozen successor.
- Scope lease is released after canonical read-back.

## 18. Product Principle

The customer should see a sports decision product.

The maintainer should still be able to inspect the machinery.

Those are different interfaces, and this redesign deliberately separates them.
