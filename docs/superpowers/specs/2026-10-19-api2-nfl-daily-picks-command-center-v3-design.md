# API 2 NFL Daily Picks Command Center V3 — Design

## Intent

Turn the existing frozen NFL Daily Picks surface into an S-tier live analytics command center that helps a user understand the best NFL **Spread, Moneyline, and Game Total** positions and build safer parlays without changing the certified model truth owned by those three NFL engines.

The page must feel like a professional decision desk rather than a static pick list: LIVE NOW / NEXT GAMES / ALL NFL context, model-vs-market intelligence, line movement, best-book visibility, source freshness, risk, and a sticky parlay builder.

## Scope

V3 is strictly limited to:

- Moneyline
- Spread
- Game Total / Over-Under
- Same-game parlays across those markets when the combination is logically valid
- Cross-game parlays across those markets

V3 does **not** add player props, hidden page execution, sportsbook-driven projections, synthetic probabilities, or filler picks.

## Frozen Truth Ownership

The existing NFL engines remain read-only truth sources:

- Moneyline: existing certified Moneyline production outputs
- Spread: existing certified Spread projection / probability outputs
- Game Total: existing certified Game Total projection / probability outputs when the engine exposes a render-independent qualified probability contract

V3 may aggregate, normalize, rank, compare books, explain, and combine certified outputs. It must not rewrite the underlying projection, probability, uncertainty, or certification logic.

Sportsbook observations are settlement and market-context inputs only. Sportsbook data never changes the model projection or model probability.

## Architecture

Use an additive V3 architecture so frozen V1/V2 stays intact:

1. `nfl_daily_picks_command_center_v3.py`
   - presentation and board orchestration
   - consumes existing `DailyPickCandidate` records
   - filters to Spread / Moneyline / Game Total only
   - exposes LIVE NOW / NEXT GAMES / ALL NFL sections
   - exposes risk-profile controls and sticky parlay-slip payloads

2. `nfl_daily_picks_parlay_v3.py`
   - pure parlay intelligence
   - no Streamlit dependency
   - validates leg eligibility
   - blocks contradictions and duplicate exposure
   - applies correlation safeguards
   - computes an explicitly labeled estimated joint probability using only source-owned leg probabilities plus conservative correlation penalties
   - never represents the estimate as a sportsbook probability or independent simulation unless the source engine supplied that contract

3. `nfl_daily_picks_market_v3.py`
   - read-only market observation aggregator
   - accepts verified observations from multiple sportsbook transports already present in the repository
   - normalizes current price, opening line when available, update time, and book identity
   - exposes best-book and line-movement context without feeding sportsbook values back into model truth
   - fails closed when an observation cannot be verified

4. `universal_runtime_v5_loader_nfl_daily_picks_command_v3.py`
   - workstream-unique runtime overlay
   - selects the strongest available upstream Universal Runtime V5 loader at import time
   - overrides only `sport=nfl, market=daily-picks`
   - does not claim a shared numbered loader path owned by parallel work

5. `streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3.py`
   - terminal router overlay
   - preserves the current universal shell and all non-Daily-Picks routes
   - injects only the isolated V3 loader

6. `app.py`
   - smallest possible terminal handoff to the V3 router
   - no other route ownership changes

## Live / Upcoming Data Contract

The page uses the existing authoritative NFL slate/date resolution. It must not require the user to manually hunt for a date.

Game state buckets:

- `LIVE NOW`: kickoff has occurred and the source explicitly marks the game live. V3 may show live market context only when the relevant sportsbook observation is verified as live-eligible. Pregame-only model candidates must not be silently reused as live picks.
- `NEXT GAMES`: next scheduled playable NFL date after the current live/finished state, using the existing universal active-slate behavior.
- `ALL NFL`: the current authoritative slate exposed by the active-date resolver.

If live eligibility cannot be proven, the page keeps the game visible but labels the betting intelligence as unavailable / pregame-only rather than fabricating a live recommendation.

## Multi-Source Sportsbook Contract

V3 prefers a source chain, not one sportsbook:

- verified sportsbook transports already present in API 2
- multiple book observations when available
- best current line / price chosen only from verified, fresh observations
- opening line and movement shown only when timestamped history exists
- source identity and freshness retained in the payload

A blank is preferable to fabricated odds. UI copy should explain `No verified current book` rather than inventing a number.

## Ranking and Risk Modes

The V3 board supports four modes:

- Safe
- Balanced — default
- Aggressive
- Max Edge

Risk mode changes **selection thresholds and portfolio construction**, not source-owned model probability.

Balanced remains the default because it should favor meaningful edge while avoiding unnecessary volatility.

A candidate remains eligible only when its source-owned candidate contract is valid and fresh. V3 ranking may additionally consider verified market value, freshness, uncertainty, and portfolio correlation.

## Parlay Intelligence

### Allowed

- Same-game and cross-game combinations of Moneyline, Spread, and Game Total
- 2–6 legs
- Build-Me-a-Parlay generated from currently eligible legs
- manual add/remove from the sticky slip

### Hard blocks

- duplicate identical leg
- opposing Moneyline sides from the same game
- opposing Spread sides from the same game
- both Over and Under on the same Game Total
- Moneyline + Spread on opposing teams in the same game
- any leg whose underlying source is stale, unqualified, unavailable, or not eligible for the game state

### Correlation safeguards

Same-game combinations are not treated as independent. V3 classifies correlation into `LOW`, `MEDIUM`, `HIGH`, or `BLOCKED`.

Conservative same-game adjustments:

- LOW: no extra penalty
- MEDIUM: subtract 3 percentage points from the naive joint-probability estimate
- HIGH: subtract 7 percentage points
- BLOCKED: combination is not allowed

These adjustments are deliberately conservative heuristics for portfolio construction and must be labeled `estimated parlay probability`, not model-certified joint probability.

Cross-game legs default to LOW correlation unless a future certified correlation source explicitly says otherwise.

## Build-Me-a-Parlay Modes

- Safe: 2–3 legs, strongest probability + quality, low correlation only
- Balanced: 3–4 legs, balanced probability / edge / quality, low or medium correlation
- Aggressive: 4–5 legs, accepts medium/high correlation when not blocked and edge is strong
- Max Edge: up to 6 legs, ranks edge most heavily but never bypasses hard blocks or stale-source rules

No mode may include a candidate that failed source eligibility.

## UI Hierarchy

1. Header: `KYRE SPORTS AI • NFL LIVE COMMAND CENTER`
2. State tabs: `LIVE NOW`, `NEXT GAMES`, `ALL NFL`
3. Summary rail: games tracked, qualified markets, freshest update, verified books
4. Featured intelligence: Best Pick / Strong Edge / Top Value
5. Game cards with Spread + Moneyline + Total in a single readable market cluster
6. Model probability / projection / market / movement / best book / freshness
7. `Why it rates` and `What could go wrong` sections
8. Sticky parlay slip with leg count, correlation grade, estimated combined probability, risk mode, and remove/reset controls
9. `Build Me a Parlay` action using the selected risk mode

On mobile, cards collapse to one column and the parlay slip becomes a compact sticky bottom panel so the page stays usable.

## Performance

- Reuse the current Runtime V5 lazy-loader contract.
- Do not execute the three source page UIs inside Daily Picks.
- Read render-independent snapshots / helpers only.
- Market aggregation is bounded to current authoritative games and known sportsbook observations.
- Cache market reads using the runtime's existing short-lived caching behavior; do not add a second refresh loop.

## Failure States

The page must fail closed and explain the reason:

- source unavailable → `SOURCE CHECK`
- source stale → `REFRESHING`
- no qualified candidate → `CONNECTED • NO QUALIFIED PICK`
- no verified book → retain model intelligence but show `No verified current book`
- live eligibility unverified → show the matchup, disable live recommendation
- parlay conflict → reject the leg with a concise conflict reason

No failure state may silently substitute a different sport, game, sportsbook value, or synthetic probability.

## Isolation / Step 2A

Authoritative workstream: `api2-nfl-daily-picks-command-center-v3`.

Source main SHA: `575a83867da2c7bb9817a0cd9082b98270905da3`.

This workstream owns only its V3 Daily Picks files, unique runtime/router overlays, tests, proof plan, task ledger, and the minimal `app.py` handoff. It must not mutate another live workstream's unique files or create a shared numbered loader collision.

One branch → one PR → one Runless proof path → exact-head verification → one merge → one registry/freeze read-back.

## Acceptance Criteria

- Spread / Moneyline / Game Total only; no player props appear in V3.
- Existing frozen source engines are read-only.
- V3 exposes LIVE NOW / NEXT GAMES / ALL NFL state without manual date hunting.
- Best-book / line-movement payloads use verified multi-source observations and never alter model truth.
- Safe / Balanced / Aggressive / Max Edge modes are deterministic; Balanced is default.
- Same-game and cross-game parlay generation enforce hard conflicts and conservative correlation handling.
- Estimated parlay probability is explicitly labeled as estimated and cannot be confused with a certified source probability.
- V3 owns an isolated runtime overlay; no parallel loader path is overwritten.
- Existing NFL Daily Picks V1/V2 regression tests remain green.
- New V3 contract tests pass through one Runless proof plan.
- Production entrypoint resolves NFL Daily Picks to the V3 owner and leaves unrelated routes unchanged.
- Exact-head proof is green before merge; merged main is read back and recorded as GREEN + FROZEN.