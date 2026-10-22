# CFB Top Picks Page 2 Analytics Lab V1 — Design Spec

Date: 2026-10-22
Repository: `kyrepeak/kyre-sports-ai`
Workstream: `api2-cfb-top-picks-page2-analytics-lab-v1`
Status: DESIGN — USER REVIEW REQUIRED BEFORE IMPLEMENTATION

## 1. Purpose

Build the deep-analysis Page 2 opened after a user taps a verified CFB Top Pick on Page 1. Page 1 remains the compact decision board. Page 2 becomes the professional research terminal: one adaptive surface that changes its analytics modules according to the selected pick type — Moneyline, Spread, Total, or Player Prop.

The goal is not four disconnected pages. The goal is one consistent Page 2 shell with market-aware modules, verified selected-pick identity, deep research, interactive-but-model-owned line scenarios, exact sportsbook market context, transparent risks, and source/freshness evidence.

## 2. Frozen baseline and constraints

The Page 1 V4 cleanup is frozen under `API2_CFB_TOP_PICKS_PAGE1_CLEANUP_V4_FROZEN`. Page 2 treats it as a baseline and may not alter Page 1 ranking, selection, probability, sportsbook quote, or identity enrichment except through a sanctioned successor/thaw.

Current Page 1 handoff passes display-oriented query parameters. Page 2 V1 strengthens the handoff by carrying the exact Page 1 `candidate_id` plus selected slate date. Page 2 resolves that candidate against Kyre Sports API before building deep analysis.

The legacy Top Picks detail stack contains useful UI/research ideas but cannot be the Page 2 V1 data authority because its identity path requires ESPN event/team IDs. Page 2 V1 replaces that identity/transport layer with NCAA/Kyre canonical identity and approved providers routed only through Kyre Sports API.

## 3. Non-negotiable routing policy

Kyre Sports API is the only application-facing API/data gateway.

Forbidden everywhere in Page 2 request, enrichment, fallback, verification, testing, and production paths:

- SGO
- ESPN
- ESPN BET

Do not call every source for every module. Each module declares one primary source class and at most one or two appropriate fallback/verification sources when data is missing, stale, conflicting, or materially important.

Approved routing by job:

- Player props / odds: FanDuel, DraftKings, BetMGM, Caesars, bet365, Fanatics Sportsbook, The Odds API, OpticOdds, SportsDataIO
- Official player/team stats: NCAA, SportsDataIO, Sportradar, CollegeFootballData
- Game/player history: Sports Reference, CollegeFootballData, NCAA, SportsDataIO
- Live scores/game state/play-by-play: NCAA, SportsDataIO, Sportradar, StatBroadcast, CBS Sports
- Injuries/availability/depth charts: official team/conference sources, RotoWire, SportsDataIO
- Game lines/line movement: direct sportsbooks first, then The Odds API, OpticOdds, SportsDataIO, Action Network, VegasInsider, Covers
- Advanced analytics: CollegeFootballData, SportsDataIO, Sportradar, Sports Reference
- Backup verification: NCAA, CBS Sports, Sports Reference, CollegeFootballData, official team/conference sources

Never average conflicting sportsbook lines. Preserve each sportsbook, market, selection, line, price, and observed timestamp independently.

Never coerce missing/null/unknown data to zero. A statistical zero may display only when an approved source explicitly reports a real zero.

## 4. Identity contract

### 4.1 Candidate-first handoff

Page 1 hands Page 2:

- `top_pick_id` = exact Page 1 `candidate_id`
- `top_pick_kind` = `game-pick` or `player-prop`
- `top_pick_date` = Page 1 selected date/slate anchor

Other display query parameters may remain for backwards compatibility, but Page 2 never trusts them as canonical identity.

### 4.2 Exact resolution

Page 2 first reloads/resolves the Page 1 candidate through Kyre Sports API and requires an exact candidate match.

For a game pick it then owns:

- canonical event/game ID
- away/home canonical team IDs
- selected market
- selected side/selection
- exact sportsbook
- exact line if applicable
- exact price
- Page 1 probability
- kickoff timestamp

For a player prop it additionally requires:

- canonical player ID from verified current-roster enrichment
- current team ID
- opponent ID
- player market
- side
- exact line
- exact sportsbook
- exact price

No fuzzy cross-game player resolution is allowed. Historical player stats preserve the school represented in that historical game/season; current-team identity is never rewritten into history.

### 4.3 Invalid/tampered handoff

If `top_pick_id` cannot be resolved exactly against verified Page 1 inventory, Page 2 returns `IDENTITY_UNAVAILABLE` and renders a safe Back to Top Picks state. It does not infer a pick from URL text.

## 5. Page 2 API contract

New Kyre Sports API endpoint:

`GET /api/v1/cfb/top-picks/page2`

Required request fields:

- `candidate_id`
- `selected_date`

Response schema owner:

`cfb_top_picks_page2_v1`

Top-level response modules:

1. `selection_snapshot`
2. `kyre_verdict`
3. `line_lab`
4. `projection`
5. `drivers`
6. `matchup`
7. `recent_form`
8. `history`
9. `market_board`
10. `line_movement`
11. `availability`
12. `game_environment`
13. `risks`
14. `flip_conditions`
15. `sources`
16. `diagnostics`

Every module has a status:

- `READY`
- `PARTIAL`
- `DATA_UNAVAILABLE`
- `NOT_APPLICABLE`
- `SOURCE_DEGRADED`
- `IDENTITY_UNAVAILABLE`

A module may omit individual values when truly unavailable, but it may not silently render a blank field. UI displays concise unavailable language only where useful rather than flooding the page with warnings.

## 6. Universal Page 2 shell

The page uses one visual system regardless of market so a user always knows where to look.

Order:

1. Back to Top Picks
2. Selected Pick Hero
3. Kyre Verdict
4. Line/Price Lab
5. Model Projection
6. Why It Hits / Key Drivers
7. Matchup Analytics
8. Recent Performance
9. Relevant History
10. Sportsbook Market Board
11. Line Movement
12. Availability + Game Environment
13. Why It Could Lose
14. What Would Change the Pick
15. Sources + Freshness

Page 1 remains intentionally simple; all deep WHY/research content lives here.

## 7. Selected Pick Hero

Always shows:

- rank from Page 1 when available
- team logos / player headshot + team logo
- matchup
- selected market
- selected side/line
- exact sportsbook + price
- Page 1 probability
- kickoff time/date
- verified identity indicator

Player props additionally show position, jersey number, current team, opponent, and canonical player ID when verified.

The hero never recomputes or changes the Page 1 selection.

## 8. Kyre Verdict

Purpose: separate outcome confidence from betting value.

- `OUTCOME_CONFIDENCE`: model likelihood of the selected event/side
- `MARKET_VALUE`: model fair probability/price compared with the exact selected sportsbook quote
- `VERDICT`: concise classification such as `PLAY`, `LEAN`, `PASS AT THIS PRICE`, or `WATCH`

A high-probability favorite may still be `PASS AT THIS PRICE` if the selected market price is worse than model fair value.

Sportsbook odds never become a projection input. They may be converted to implied probability for value comparison only.

## 9. Adaptive market modules

### 9.1 Moneyline

Primary emphasis:

- win probability
- model fair price
- selected sportsbook implied probability
- value/edge
- projected score when a certified score projection exists
- team efficiency matchup
- recent form/home-away context
- key availability
- exact sportsbook board and moneyline movement

Line Lab becomes a `Price Lab`, showing how value changes across supplied moneyline prices. It does not alter win probability.

### 9.2 Spread

Primary emphasis:

- selected spread and cover probability
- model projected margin / fair spread
- margin distribution
- spread Line Lab
- opponent matchup
- recent ATS-relevant performance only when backed by verified sportsbook history
- availability/game-script drivers
- book-by-book spread/price board
- opening/current movement

### 9.3 Total

Primary emphasis:

- selected total and Over/Under probability
- projected total / projected score
- scoring distribution
- pace and offensive/defensive scoring environment
- total Line Lab
- recent scoring/allowing trends
- book-by-book totals board
- opening/current movement
- relevant game environment

### 9.4 Player Prop

Primary emphasis:

- player identity/current-roster verification
- selected prop/line/side/price
- player projection/hit probability
- prop Line Lab
- last 5 / last 10 / season trend when verified
- home/away split when sample is legitimate
- market-appropriate usage: attempts, targets, receptions, routes, snaps, carries, touches, etc.
- opponent allowance/defensive matchup appropriate to the prop
- relevant player-vs-opponent or similar-opponent history when verified
- teammate/QB/starter availability impact when materially relevant
- sportsbook-specific prop board and movement

Do not show generic metrics that do not affect the selected prop.

## 10. Line Lab ownership

The Streamlit UI never invents alternate-line probabilities.

Kyre Sports API/model layer owns scenario generation. Page 2 receives precomputed scenario rows and the UI only switches among them.

Example scenarios:

```json
{"market":"SPREAD","line":2.5,"selected_side_probability":0.646}
{"market":"TOTAL","line":47.5,"over_probability":0.678,"under_probability":0.322}
{"market":"PLAYER_PROP","line":39.5,"over_probability":0.494,"under_probability":0.506}
{"market":"MONEYLINE_PRICE","american_odds":-415,"implied_probability":0.806,"model_probability":0.777,"edge_points":-2.9}
```

Scenario generation uses the same certified model/distribution family that owns the Page 1 probability. If the model cannot legitimately provide alternate-threshold scenarios, Line Lab returns `DATA_UNAVAILABLE` rather than synthesizing a curve.

## 11. Projection module

Game-pick projection may include, only when owned by a certified model:

- projected away/home score
- projected margin
- projected total
- win probabilities
- cover/total probability for selected threshold
- distribution summary / uncertainty band

Player-prop projection may include projected stat, explicitly defined mean/median, selected-line hit probability, and uncertainty/distribution summary.

Never derive fake projected scores just to make the page look complete.

## 12. Why It Hits / Drivers

Render 3–6 evidence cards selected for the current market. Each driver contains:

- title
- concise fact-based explanation
- supporting value(s)
- source group
- observed timestamp/freshness
- polarity (`supports`, `neutral`, `risk`)

Drivers are evidence summaries, not unsupported generated prose.

## 13. Matchup analytics

Use a market-specific comparison table rather than a generic stat dump.

Game picks may compare offensive/defensive efficiency, success rate, explosive-play rate, scoring/red-zone efficiency, turnovers, pace, and home/away splits.

Player props compare player usage/production against opponent defense metrics for that position/market.

Advanced metrics route primarily through CollegeFootballData / SportsDataIO / Sportradar / Sports Reference as appropriate; NCAA owns official/basic stats when available.

## 14. Recent form and history

Recent form and historical matchup are separate modules.

Recent form prioritizes the current season/latest appropriate games.

History may include team vs team prior meetings, player vs opponent, player vs similar defenses, and historical line/market outcomes only when exact historical sportsbook data exists.

History is contextual. It does not automatically change the frozen Page 1 probability unless a future explicitly certified model version says it is a model input.

If verified history is insufficient, render a concise explicit unavailable state and no claim.

## 15. Sportsbook market board

For the selected market only, display independent quotes by sportsbook:

- sportsbook
- market
- selection
- line
- American price
- observed timestamp
- source status

Never average lines/prices.

Identify `BEST_AVAILABLE_PRICE` only by comparing like-for-like selections/lines. Do not call one sportsbook's quote “the market.”

Fallback/aggregation providers are used only when direct approved book data is unavailable or missing for the requested field.

## 16. Line movement

Movement is event + market + sportsbook specific.

Store/render opening line/price when verified, current line/price, intermediate observations when available, timestamps, and direction label.

Do not infer movement from two different sportsbooks.

If opening history is unavailable, show current board only and mark movement unavailable.

## 17. Availability and game environment

Availability focuses on material players/units for the selected pick: starting QB, selected player, major skill-position starters, relevant OL/secondary/front players, suspension/inactive/questionable status, and depth-chart/starter status.

Primary: official team/conference sources. Fallback: RotoWire or SportsDataIO when needed. High-impact availability used in verdict/drivers should be independently verified when practical.

Game environment V1 includes verified venue/home-away context plus pace/game-script inputs from approved CFB sources. Weather is not allowed to influence the verdict until an explicit approved weather-provider contract exists in Kyre Sports API; until then it is omitted rather than guessed.

## 18. Why It Could Lose

Every Page 2 contains 2–5 material evidence-backed risks such as expensive price, turnover volatility, explosive-play vulnerability, matchup weakness, questionable availability, limited role/sample, or market movement against the pick.

No generic filler risks.

## 19. What Would Change the Pick

Return explicit re-evaluation conditions such as a starting QB ruled out, selected player demoted/inactive, exact sportsbook line moving beyond model value threshold, multiple key starters becoming unavailable, or new verified information invalidating assumptions.

This module describes conditions only. It does not monitor in the background.

## 20. Freshness and fallback rules

Every material API field records source/provider, observed/fetched timestamp, freshness status, and identity keys used.

When primary data is missing or stale:

1. identify the missing field
2. call only the next approved source capable of supplying it
3. verify team/game/player/market identity
4. normalize to canonical Kyre IDs
5. populate

One provider outage may degrade only the modules it owns. It must not blank unrelated Page 2 sections.

## 21. UI behavior

- Page 1 tap navigates to Page 2 for the exact candidate.
- Page 2 has a clear Back to Top Picks action that returns to the same slate.
- Loading is staged: hero/selection identity first, then deep analytics.
- No giant raw-data wall.
- Desktop/tablet uses dense professional panels; mobile stacks cleanly.
- No raw HTML/code leakage.
- Source/freshness details live in the final expandable audit area.
- Missing optional fields collapse cleanly; required identity failure stops detail safely.

## 22. Proposed code boundaries

New successor-owned components:

- `sports_api/api/cfb_top_picks_page2_v1.py` — API contract/orchestration
- `sports_api/collectors/cfb_top_picks_page2_identity_v1.py` — candidate-first canonical identity
- `sports_api/collectors/cfb_top_picks_page2_team_analysis_v1.py` — game/team research routing
- `sports_api/collectors/cfb_top_picks_page2_prop_analysis_v1.py` — player-prop research routing
- `sports_api/collectors/cfb_top_picks_page2_market_v1.py` — selected-market multi-book quotes/movement
- `sports_api/collectors/cfb_top_picks_page2_availability_v1.py` — material availability/depth-chart routing
- `cfb_top_picks_page_v16.py` — adaptive Page 2 presentation
- `streamlit_memory_lazy_router_universal_runtime_v5_cfb_top_picks_page2_v1.py` — Page 1/Page 2 handoff runtime
- V1 tests/source policy/proof plan/task ledger

Shared files such as `app.py`, `kyre_sports_api_vercel_v1.py`, or frozen Page 1 routing are mutated only under sanctioned scope lease/thaw and only when required to register the successor.

Existing presentation-only Line Lab patterns may be reused conceptually, but Page 2 owns API-supplied scenarios and does not depend on old ESPN-bound Top Picks detail transport.

## 23. Verification plan

Before GREEN + FROZEN, prove at minimum:

### Identity
- exact candidate ID resolves
- tampered/nonexistent candidate fails closed
- player current-team identity is verified
- transfer-aware history preserves historical school
- no cross-game similarly-named player contamination

### Routing
- application-facing gateway is Kyre Sports API only
- no SGO / ESPN / ESPN BET in new production path
- field-level fallback uses only relevant approved providers
- provider failure degrades only its owned module

### Market integrity
- no sportsbook averaging
- exact book/line/price/timestamp preserved
- movement never mixes sportsbooks
- best-price comparison only compares like-for-like markets

### Null correctness
- missing values never become statistical zero
- explicit true zeros remain zero
- unavailable modules use explicit status
- UI has no unexplained blank cells

### Adaptive UX
- Moneyline renders Price Lab + ML analytics
- Spread renders spread Line Lab + margin analytics
- Total renders total Line Lab + scoring/pace analytics
- Player Prop renders prop Line Lab + market-specific usage/opponent metrics
- Page 1 deep WHY content remains absent
- Back navigation preserves Page 1 slate
- no raw HTML leakage

### Regression / proof
- frozen Page 1 V4 tests remain green
- unrelated NFL/CFB routes remain unchanged
- exact main/candidate SHA proof
- one authoritative Runless proof path
- exact-SHA production deployment verification
- finalization ledger + frozen registry + lease-release readback

## 24. Step 2A / anti-loop execution contract

Implementation uses exactly one active Page 2 problem, one branch, one PR, one scope lease, and one authoritative Runless proof path. It requires exact-head verification before proof/merge, no duplicate proof runs, terminal failure classification before successor proof, frozen-registry thaw only for shared/frozen files actually modified, proof-before-merge, exact authorized-head merge, atomic finalization ledger, registry forward-port/retire thaw, durable `GREEN_FROZEN` readback, and release of only the Page 2 lease.

No Render dependency. Vercel Runless remains the proof/deployment path.

## 25. Out of scope for V1

- bet placement/wagering execution
- background monitoring or automatic pick changes
- changing Page 1 ranking/probability/model ownership
- sportsbook consensus as projection input
- fabricated projected scores or unavailable analytics
- weather-based verdict changes until an explicitly approved weather provider is contracted through Kyre Sports API

## 26. Success definition

Page 2 succeeds when tapping any verified Page 1 Top Pick opens one professional adaptive analytics lab that deeply explains the selected pick without changing its frozen Page 1 identity, uses Kyre Sports API as the sole application gateway, uses the strongest approved source per field with safe fallbacks, preserves sportsbook-specific truth, separates model confidence/value/risk, supports model-owned Line/Price Lab scenarios, contains no avoidable blank fields, and can be proven through the single Step 2A Runless path to `GREEN_FROZEN`.