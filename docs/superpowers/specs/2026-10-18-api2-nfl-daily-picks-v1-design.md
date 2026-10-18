# API 2 — NFL Daily Picks V1 Design

Date: 2026-10-18
Status: DESIGN — awaiting written-spec approval
Workstream: `api2-nfl-daily-picks-v1`
Repository: `kyrepeak/kyre-sports-ai`

## 1. Purpose

Build a production NFL Daily Picks page that replaces the current generic NFL foundation fallback with a real Top-10 board.

The page must aggregate the already-completed NFL market outputs instead of creating a second prediction engine. It must rank the strongest eligible pregame opportunities across:

- Moneyline
- Spread
- Game Total
- Passing Yards
- Rushing Yards
- Receiving Yards

The result is one clean, professional Daily Picks command board that remains consistent with the underlying NFL market pages.

## 2. Current Problem

Runtime V5 does not currently assign `NFL / Daily Picks` to a dedicated destination. Unmapped NFL routes fall through to the generic `nfl_hub_v18` owner, which in turn falls back to the older NFL V1 foundation page for markets it does not explicitly own.

That fallback is why the live Daily Picks route displays the old “reserved / betting model intentionally OFF” experience instead of a real Daily Picks page.

The current fallback surface can also expose raw matchup-card HTML as visible text. Daily Picks must not inherit or reproduce that behavior.

## 3. Design Principles

1. **Read-only aggregation.** Daily Picks reads certified source-market outputs; it does not rewrite their projections or probabilities.
2. **Pure Best 10.** The strongest eligible candidates win, with no artificial quota by market.
3. **Pregame only.** A game is ineligible once kickoff occurs.
4. **Correlation safety.** Near-duplicate and directly conflicting picks must not pad the Top 10.
5. **Fail soft by market.** One unhealthy market cannot take down the other five.
6. **Exact identity.** Game and player identity must be exact and current; no loose fallback matching.
7. **Freshness required.** Stale or unverifiable market output fails closed.
8. **Route ownership is explicit.** `NFL / Daily Picks` must never fall through to the generic NFL V1 foundation page again.
9. **Runtime V5 generation safety remains authoritative.** Late work from an abandoned Daily Picks route may warm cache, but may not repaint a different page.
10. **One execution lane.** Step 2A and anti-loop remain mandatory during implementation and finalization.

## 4. Source-Market Ownership

Each source market remains authoritative for its own model and eligibility logic.

Daily Picks may consume only already-produced market facts such as:

- current game/player identity
- current market line and side
- model projection
- model/hit probability
- edge or market delta
- source-market eligibility / readiness
- source timestamp / freshness
- kickoff time
- existing uncertainty / risk signals

Daily Picks must not alter the underlying source-market projection, probability, line, or recommendation state.

If an existing market does not expose a safe read-only output contract, implementation must treat that as an adapter compatibility problem. It must not screen-scrape a rendered page or reproduce the source model inside Daily Picks.

## 5. Common Candidate Contract

Each source-market adapter maps its eligible output into a common candidate structure. The exact implementation type may be a dataclass, TypedDict, or validated mapping, but the semantic contract is:

- `market_id`
- `market_label`
- `game_id`
- `game_date`
- `kickoff_at`
- `team_id`
- `opponent_team_id`
- `athlete_id` when player-specific
- `subject_label` (team or player)
- `matchup_label`
- `side` (for example Over, Under, Moneyline side, spread side)
- `market_line`
- `model_projection` when applicable
- `model_probability`
- `edge_value`
- `source_ready`
- `source_fresh_at`
- `source_age_seconds`
- `data_quality`
- `uncertainty`
- `source_version`
- `reason_components` for user-facing “Why this pick” text

Fields that are not meaningful for a specific market may be null, but identity, eligibility, probability/strength information, source readiness, kickoff, and freshness must be sufficient for ranking.

## 6. Eligibility Gate

A candidate may enter the shared pool only when all applicable rules pass:

1. belongs to the current active NFL slate;
2. game identity matches the selected/current authoritative schedule;
3. player identity is exact for player props;
4. source market marks the row ready/eligible;
5. current market line is usable when the market requires one;
6. source output is within its approved freshness window;
7. kickoff has not occurred;
8. game is not in-progress or final;
9. required ranking inputs are finite and valid;
10. no explicit source-level safety gate blocks the pick.

There is no fallback roster filler and no fabricated candidate when a market has no qualifying output.

## 7. Ranking Engine

Daily Picks ranks only eligible candidates.

The ranking score is a Daily-Picks-only comparison layer. It may normalize the existing source-market outputs so structurally different markets can be compared fairly, but it may not modify the source model itself.

The score should primarily reflect:

- model probability / hit probability;
- model edge relative to the current line or market;
- data completeness / confidence;
- source freshness;
- existing source-market eligibility strength;
- uncertainty / risk penalties.

Normalization should be market-aware so a moneyline probability and a player-prop edge can compete on a comparable scale without pretending they use identical raw units.

### Tie-break order

When overall scores are effectively tied, prefer:

1. better data quality;
2. fresher market output;
3. lower uncertainty;
4. stronger independent edge;
5. stable deterministic identity ordering only as a final technical tie-break.

Load order must never affect final ranking.

## 8. Pure Best 10 Rule

After eligibility, normalization, and correlation safety, return the strongest candidates overall.

There is no forced market diversification. If the strongest slate legitimately contains several rushing or passing props, those picks may all appear.

The page must render at most 10 picks. If only 7 picks qualify, it renders 7. It never invents filler to reach 10.

## 9. Correlation and Conflict Safety

Correlation protection exists to prevent one football thesis from occupying several Top-10 positions through near-duplicate bets.

Examples of potentially correlated exposure include:

- team moneyline plus a highly overlapping spread on the same team;
- multiple same-game outcomes whose confidence is driven by the same dominant assumption;
- duplicate representations of the same player/market direction.

The guard must also reject direct contradictions, such as opposing recommendations on the same exact market/identity.

The guard is not a blanket “one pick per game” rule. Distinct picks from the same matchup may coexist when they represent independently strong and sufficiently different edges.

Correlation logic must be deterministic and testable. It should preserve the higher-ranked candidate when two candidates are judged redundant.

## 10. Market Adapter Isolation and Failure Behavior

The six source adapters load independently.

A failure in one market should produce a market-level diagnostic state such as `UNAVAILABLE`, `STALE`, or `ERROR` while allowing healthy markets to continue contributing candidates.

Daily Picks must not crash globally because one market provider, import, or output contract is temporarily unhealthy.

The board may render with partial healthy coverage, but the UI must clearly disclose which source markets are unavailable or stale.

## 11. Page Layout

The Daily Picks page should render as a dedicated NFL command board, not six embedded market pages.

### Top status strip

Show compact status for all six source families, for example:

`Moneyline 🟢 | Spread 🟢 | Game Total 🟢 | Passing 🟢 | Rushing 🟢 | Receiving 🟡`

Each status reflects the adapter’s actual state and freshness.

### Pick cards

Each ranked pick should show, when applicable:

- rank
- market type
- player/team
- matchup
- current line
- pick side
- model probability
- model projection
- confidence / quality
- “Why this pick” explanation
- toughness / risk indicator
- source freshness
- kickoff time

Cards must be compact, readable, and visually consistent with the current Kyre Sports AI design language.

### Empty state

If zero candidates qualify, render a clean message such as:

`No qualified pregame picks are currently available.`

Then show market diagnostics. Do not show raw HTML, old MODEL OFF copy, fake picks, or a blank page.

## 12. Loading and Performance

Daily Picks must not render six heavyweight market UIs behind the scenes.

Each adapter should use the smallest safe read-only data/output layer exposed by its market.

The page shell should render promptly, while independent market data work is bounded and reusable through verified fresh snapshots where safe.

Cached results may be reused only while they satisfy the source market’s freshness contract. Expired data may not silently appear current.

The page should avoid unnecessary recomputation when an equivalent verified snapshot is already available.

## 13. Runtime V5 Route Ownership

Runtime V5 must gain an explicit `NFL / daily-picks` destination mapped to the new Daily Picks owner.

This route must no longer use the generic NFL fallback path.

The route change should be additive and as narrow as possible. Existing NFL market routes must remain unchanged unless an adapter compatibility requirement is proven during implementation.

Runtime V5 generation ownership remains in force:

- latest route generation wins;
- a stale Daily Picks generation cannot mutate active route state;
- late adapter completion may update allowed cache state but cannot render into a page the user has already left.

## 14. Raw HTML Protection

The current fallback can expose matchup `<article ...>` markup as visible text. The new Daily Picks page must never do this.

All HTML-rendered card surfaces must use one controlled render path with explicit HTML permission where required.

Regression coverage must assert that raw card markup is not emitted as user-visible text and that Daily Picks does not call the old NFL foundation fallback renderer.

## 15. Testing Strategy

Implementation follows TDD.

Required regression coverage includes at minimum:

1. `NFL / Daily Picks` resolves to the new Daily Picks module.
2. The old generic NFL V1/V18 fallback is not invoked for Daily Picks.
3. All six approved source adapters are represented.
4. One failing adapter does not prevent healthy adapters from ranking.
5. Only pregame candidates qualify.
6. In-progress/final games are excluded.
7. Exact game identity is required.
8. Exact player identity is required for props.
9. Stale candidates fail closed.
10. Invalid/non-finite ranking fields fail closed.
11. Pure Best 10 imposes no artificial market quota.
12. Results are capped at 10 without filler.
13. Correlated redundant picks collapse deterministically.
14. Directly contradictory picks cannot coexist.
15. Independent same-game picks may coexist when not redundant.
16. Tie-breaking is deterministic and independent of adapter load order.
17. Source projections/probabilities are unchanged by aggregation.
18. Raw HTML cannot leak as visible text.
19. Zero-candidate state is clean and diagnostic.
20. Runtime V5 stale-generation behavior prevents late Daily Picks repaint after navigation away.
21. Existing NFL route regression remains green.

## 16. Scope

### In scope

- new NFL Daily Picks owner/module;
- six read-only source-market adapters;
- common candidate schema;
- eligibility gate;
- cross-market ranking layer;
- correlation/conflict protection;
- Top-10 UI and diagnostics;
- explicit Runtime V5 Daily Picks route;
- targeted tests and proof plan;
- minimal compatibility shims proven necessary by source contracts.

### Out of scope

- changing Moneyline, Spread, Game Total, Passing, Rushing, or Receiving model formulas;
- changing source-market probabilities or projections;
- adding live betting;
- adding markets outside the six approved families;
- forced market diversification quotas;
- redesigning Runtime V5 core architecture;
- changes to CFB, NBA, WNBA, MLB, or unrelated NFL pages;
- background browser automation or a second execution system.

## 17. Implementation Safety / Step 2A

Implementation must maintain exactly one authoritative execution path:

- one active problem;
- one branch;
- one PR;
- one candidate SHA at a time;
- one authoritative Runless proof;
- no duplicate deployments, leases, proof requests, or asynchronous fallback lanes.

If the authoritative path fails, classify the terminal root cause before patching. Do not poll or fan out.

Frozen artifacts may only be changed through the authorized thaw/forward-port lifecycle when required. Prefer additive successor modules where that preserves frozen ownership safely.

## 18. Production Completion Contract

The step is not complete when code merely renders locally.

Required completion chain:

1. RED tests reproduce the missing-route/fallback failure and the agreed ranking/eligibility contracts;
2. implementation turns the targeted suite GREEN;
3. relevant NFL + Runtime V5 regressions pass;
4. exact candidate head is locked;
5. required scope lease is acquired;
6. one Runless exact-head proof reaches `MERGE_AUTHORIZED`;
7. PR merges at the proven head;
8. immutable finalization ledger record is written;
9. closeout readback reaches `GREEN_FROZEN` with failure class `NONE`;
10. scope lease is released and read back;
11. final merged-main route/module/freeze evidence is re-read before claiming completion.

Target terminal state:

`🟢 100% — GREEN + 🧊 FROZEN`

## 19. Success Criteria

The design is successful when a user taps NFL Daily Picks and receives a real, fast, professional Top-10 board sourced from the six existing NFL market engines, containing only fresh pregame qualified candidates, with deterministic ranking and correlation safety, while unrelated markets remain intact.

The route must never again display the NFL V1 “model off” fallback or literal card HTML for Daily Picks.
