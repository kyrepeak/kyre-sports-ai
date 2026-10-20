# CFB Player Props Page 2 V1 — Player-First Command Board

## Intent

Build Page 2 of the three-page College Football Player Props experience as a fast, professional, player-first command board for exactly one selected game.

The user journey is:

1. Page 1 automatically loads the next active CFB slate.
2. The user taps one game.
3. Page 2 opens only that exact game.
4. Page 2 immediately shows the important offensive players and the verified prop markets available for them.
5. The user can inspect compact matchup intelligence, sportsbook coverage, recent production, and a Kyre probability preview.
6. The user selects one player/prop for the future Page 3 Line Lab.

Page 2 must be fast enough for browsing and deep enough to make the player/prop selection trustworthy, while leaving the full analytical lab to Page 3.

## Scope

### In scope

- exact selected-game reconstruction from the frozen Page-1 handoff;
- Back button to Page 1;
- selected matchup hero with teams, logos, kickoff, ranks/records when verified;
- verified offensive rosters for both teams;
- QB/RB/WR/TE player-first browsing;
- player photos when verified;
- school/team logos;
- all verified supported CFB player-prop markets for the selected game;
- multi-sportsbook line/price comparison;
- consensus line;
- best Over line and best Under line;
- truthful line movement only when opening/current evidence exists;
- recent player production from verified completed-game history;
- frozen Kyre projection/probability preview using the existing Page-1 model contract;
- compact opponent defensive matchup context;
- verified availability/injury status only when explicitly sourced;
- stable selected-player/prop handoff contract for future Page 3;
- responsive mobile/tablet/desktop layout;
- fail-soft provider behavior and fail-closed identity/model behavior.

### Out of scope

- Page 3 Line Lab implementation;
- editable line slider;
- arbitrary user-entered lines;
- new projection math;
- new probability math;
- changing Page-1 schedule, identity, market, history, or model contracts;
- changing sportsbook data influence on projection;
- fabricated injury status, depth chart, movement, roster, player, game, price, line, ranking, or probability;
- background loading of unrelated games or sports.

## Approved UX direction

Use a **Player-First Command Board**.

Page 2 prioritizes the answer to: **“Which player and prop in this selected game do I want to analyze?”**

It does not start with a long market list or a deep matchup report. Those approaches are rejected because they slow the player-to-prop funnel and duplicate Page 3.

## Route and runtime architecture

### Preserve frozen Page 1

Do not turn `cfb_player_props_page1_v1.py` into a Page-1/Page-2 monolith.

Create a terminal wrapper:

- `cfb_player_props_runtime_v2.py`

The current Universal Runtime destination for `cfb/player-props` will load this wrapper instead of importing Page 1 directly.

Runtime behavior:

- no canonical `game_id` -> delegate unchanged to frozen `cfb_player_props_page1_v1.render_cfb_player_props_page1()`;
- canonical `game_id` present -> render `cfb_player_props_page2_v1.render_cfb_player_props_page2()`.

This preserves Page 1 and gives Page 2 an isolated implementation boundary.

### Canonical Page-2 identity

Page 2 identity is:

- sport: `cfb`;
- market: `player-props`;
- slate date;
- exact official CFB game ID.

Sportsbook event IDs are aliases only and may never select the game.

The Page-1 handoff already supplies exact official game ID, date, away/home official team IDs, names, kickoff, market ID, and generation. Page 2 consumes that contract rather than creating a second navigation identity.

### Exact-game reconstruction

Create:

- `cfb_player_props_page2_context_v1.py`

Responsibilities:

1. Read canonical Page-1 session/query handoff.
2. Require `date` + `game_id`.
3. Load the requested date from the current CFB Schedule V4 owner.
4. Match exactly one game by official game ID.
5. Verify the matched teams are compatible with the handoff when handoff team IDs are available.
6. Reject provider IDs as navigation identity.
7. Never silently substitute a different game if the requested game is unavailable.
8. Produce a normalized immutable Page-2 game context.

If reconstruction fails, Page 2 shows a compact error with **Back to Player Props**. It does not fall through to another matchup.

## Back-navigation contract

The Back button returns to Page 1 by clearing only Page-2/Page-3 selection state:

- `game_id`;
- future `player_id`;
- future `prop`/market selection;
- Page-2 selected position/filter state where appropriate.

It preserves:

- sport = CFB;
- market = Player Props;
- resolved slate date when valid.

Back must not navigate to another sport or another CFB market.

## Page-2 data architecture

Page 2 composes existing frozen data contracts through new Page-2 orchestration modules. It must not fork Page-1 model math or identity rules.

### 1. Roster owner

Create:

- `cfb_player_props_page2_roster_v1.py`

Source:

- ESPN college-football team roster endpoint for the exact official team IDs.

Normalization must reuse:

- `cfb_player_props_identity_v1.CanonicalPlayerIdentity`;
- `player_identity_from_roster_row`;
- existing exact identity rules.

Only QB, RB, WR, and TE are displayed in the primary Page-2 player board.

For each player, preserve when available:

- official ESPN athlete ID;
- official team ID;
- full name;
- position;
- jersey number;
- class/year if explicitly supplied;
- explicit headshot URL from ESPN roster payload;
- team name/abbreviation.

If no verified headshot exists, render a neutral player monogram/avatar. Do not fabricate a face.

Roster fetches are cached by official team ID and bounded TTL. One Page-2 render must not repeatedly fetch the same team roster.

### 2. Availability / injury evidence

Create:

- `cfb_player_props_page2_availability_v1.py`

Availability is optional evidence, not a prerequisite for showing a verified player.

Allowed sources:

- exact ESPN event summary/status fields;
- exact ESPN roster/player status fields when present.

Canonical states:

- `OUT`;
- `DOUBTFUL`;
- `QUESTIONABLE`;
- `AVAILABLE` only when explicitly supported;
- `UNVERIFIED` when no reliable status exists.

Rules:

- absence of an injury report does not mean healthy;
- no heuristic inference from recent stats;
- no status generated from betting lines;
- do not hide a verified player merely because availability is unverified;
- a verified OUT player remains visible but clearly marked and cannot receive a positive “available” label.

### 3. Prop market owner

Reuse frozen Page-1 transport and normalization contracts:

- `cfb_player_props_sportsgameodds_v1.py`;
- `cfb_player_props_fanduel_v1.py`;
- `cfb_player_props_market_v1.py`.

Supported markets remain exactly:

- `passing_yards`;
- `rushing_yards`;
- `receiving_yards`;
- `receiving_receptions`;
- `passing_touchdowns`;
- `touchdowns`.

Page 2 filters all observations to:

- exact official game ID;
- exact canonical player ID;
- verified canonical market key.

A row with unresolved player identity is excluded.

A stale fallback cannot overwrite a fresher verified sportsbook row.

### 4. Page-2 market aggregation

Create:

- `cfb_player_props_page2_market_v1.py`

Group observations by canonical player + market.

For each player/market group calculate presentation-only values:

- consensus line = median of current verified lines, reusing the frozen Page-1 consensus contract;
- book count;
- current sportsbook rows;
- best Over line;
- best Under line;
- best Over price at the chosen best Over line;
- best Under price at the chosen best Under line;
- source freshness/provenance;
- movement state when true evidence exists.

Best-line rules:

- Over: lower verified line is better; price breaks ties;
- Under: higher verified line is better; price breaks ties;
- never compare a missing line as if it were a real quote;
- never label one book “best” without enough comparable verified evidence.

### 5. Line movement

Line movement is display-only and must fail closed.

Create a small normalization layer only if a provider returns both a trusted opening and current observation for the same game/player/market/book.

Display examples:

- `218.5 → 221.5 (+3.0)`;
- `52.5 → 49.5 (-3.0)`.

If verified opening evidence is not present, show `Movement unavailable` or collapse the movement element. Never treat first-seen-in-session as a true opening line.

### 6. Recent player production

Reuse:

- `cfb_player_props_history_v1.py`.

For every player/market shown, load up to the same most recent verified completed-game history window already used by the frozen Page-1 model.

Page 2 preview displays compact values such as:

- last 3 when available;
- season/recent average when it can be computed directly from verified rows;
- current model sample count.

No historical row may be synthesized.

### 7. Kyre signal preview

Reuse without modification:

- `cfb_player_props_model_v1.build_prop_projection`;
- `build_market_consensus`;
- `grade_market_line` / existing Page-1 signal contract.

Frozen model invariants remain:

- minimum 4 verified completed games for model-ready probability;
- maximum 8-game history window;
- 0.85 newest-first decay;
- sportsbook data has `0.0` direct influence on the underlying projection;
- sportsbook consensus supplies threshold/price context only;
- non-finite/zero uncertainty fails closed;
- missing paired prices may still permit model probability but not a valid market edge.

Page 2 may present:

- Kyre projection;
- recommended side;
- probability;
- market edge when valid;
- sample count.

It may not modify the math.

## Opponent defensive matchup intelligence

Create:

- `cfb_player_props_page2_matchup_v1.py`

Reuse existing CFB offense-vs-defense evidence rather than inventing another team-stat system.

The Page-2 matchup layer should consume verified CFB defensive evidence from the existing CFB matchup/stat engines for the exact opponent.

Player-position mapping:

- QB passing props -> opponent pass-defense evidence;
- RB rushing props -> opponent rush-defense evidence;
- WR/TE receiving/receptions -> opponent pass-defense evidence;
- touchdown props -> use only directly supportable rushing/receiving defensive context; do not invent a TD-specific ranking when one is unavailable.

Compact label:

- `FAVORABLE`;
- `NEUTRAL`;
- `TOUGH`;
- `CHECK` when evidence is incomplete.

The label is explanatory/presentation context only in Page 2. It does not alter the frozen Page-1 projection unless a future separately approved model version explicitly changes that contract.

## Page-2 presentation

Create:

- `cfb_player_props_page2_v1.py`

### Section A — Matchup hero

Show:

- `CFB • PLAYER PROPS • PAGE 2`;
- Back to Player Props button;
- away logo/team;
- home logo/team;
- rankings if verified;
- records if verified;
- kickoff in Phoenix-local display time while retaining canonical timestamp;
- game status;
- compact exact-game authority marker in metadata, not as visual clutter.

### Section B — Position filter

Single-select segmented control:

- ALL;
- QB;
- RB;
- WR;
- TE.

Default: ALL.

The filter is local Page-2 presentation state only. It may not change canonical route identity.

### Section C — Player-first board

Desktop/tablet:

- away and home team columns.

Mobile:

- one stacked column with clear team sections.

Each verified player card shows:

- verified headshot or neutral monogram;
- school logo;
- name;
- jersey when verified;
- position;
- availability badge only with truthful state;
- number of verified prop markets;
- compact recent-production strip;
- compact opponent defensive matchup badge.

Players with no props remain visible if they are part of the selected offensive roster, but the card says:

`No verified props posted yet.`

### Section D — Prop rows inside each player card

Each supported verified prop row shows:

- market name;
- consensus line;
- best Over line + sportsbook + price when available;
- best Under line + sportsbook + price when available;
- verified-book count;
- movement only when supported by real opening/current evidence;
- Kyre side/probability/edge preview when model-ready;
- otherwise a truthful model state such as `Need 4 verified games` or `Model unavailable`;
- `Analyze` action that creates the future Page-3 handoff.

Do not render giant sportsbook tables by default. Page 2 is a decision board, not the deep lab.

### Section E — Compact matchup intelligence

Below or adjacent to the player board, show only the information that helps choose a player/prop:

- pass-defense context;
- rush-defense context;
- sourced availability notes;
- concise recent-production summary;
- line-movement summary when verified.

Deep charts, simulations, editable lines, and exhaustive historical splits belong to Page 3.

## Page-3 handoff contract

Create:

- `cfb_player_props_page2_handoff_v1.py`

The Page-2 selected-prop payload must contain:

- route version;
- slate date;
- official game ID;
- away/home official team IDs;
- canonical player ID;
- canonical player name;
- official player team ID;
- canonical market key;
- selected consensus line when available;
- generation;
- selection timestamp/state metadata sufficient to reject stale replacement.

Sportsbook event/player/market IDs may be carried only as provenance aliases, not canonical navigation identity.

A newer selection replaces an older selection atomically. A stale route generation cannot overwrite a newer selection.

Page 2 does not implement the Page-3 Line Lab. It only creates a stable, tested handoff contract for it.

## Error and empty states

### Missing or invalid game

Show:

`Selected game is unavailable. Return to Player Props.`

Provide Back button. Do not substitute another game.

### Roster provider unavailable

Keep the matchup shell visible and say:

`Verified roster temporarily unavailable.`

Do not invent players.

### Verified roster but zero player props

Keep players visible and show:

`No verified props posted yet.`

### Sportsbook provider partial outage

Render remaining verified books. Surface book count/provenance truthfully. Do not blank the whole page if one source fails.

### History unavailable

Show live market information, but no probability if model readiness cannot be proven.

### Defensive evidence unavailable

Use `CHECK` / `Defense data unavailable`; never substitute another opponent or stale unrelated team.

## Performance and loading

- Exact selected game only.
- Fetch each selected team roster at most once per cache TTL.
- Fetch sportsbook slate/game data once per provider per render/cache cycle, then filter locally.
- History fetches are only for verified players with displayed supported prop markets; do not fetch every roster player history preemptively.
- No Page-1 slate background render while Page 2 is active.
- No unrelated sport/market prefetch.
- Inherit Universal Atomic Navigation generation/scope guards.

## Responsive visual standard

Target widths:

- mobile: ~390 px;
- tablet: ~768 px;
- desktop: ~1440 px.

Requirements:

- no horizontal page scroll;
- readable body text on iPhone/iPad;
- touch targets at least comfortably tappable;
- player cards never require keyboard input;
- team columns stack cleanly on mobile;
- sportsbook rows wrap without clipping;
- selected-game header remains visible and visually dominant;
- black/glacier-blue premium analytics language consistent with the rest of Kyre Sports AI.

## Data truth and provenance guardrails

1. Official game ID is the game authority.
2. Official ESPN athlete ID is canonical player authority when available.
3. Fuzzy name similarity never certifies a player.
4. Provider IDs are aliases only.
5. Unverified injury status is never converted into “available.”
6. No fake opening line or line movement.
7. No fake rankings, records, headshots, books, prices, or probabilities.
8. A weaker/staler provider cannot overwrite fresher verified evidence.
9. Sportsbook odds remain external threshold/price context, not projection input.
10. Missing data collapses or shows a truthful unavailable state rather than a misleading blank card.

## Testing requirements

### Routing/context tests

Prove:

- Page 1 remains unchanged when `game_id` is absent;
- Page 2 renders only when a canonical selected game exists;
- exact game reconstruction uses Schedule V4;
- wrong/stale game ID does not select another matchup;
- Back clears Page-2 selection without leaving CFB Player Props.

### Roster/identity tests

Prove:

- exact official team/player IDs survive normalization;
- duplicate/ambiguous names do not resolve incorrectly;
- QB/RB/WR/TE filtering is deterministic;
- missing headshot falls back safely;
- roster provider failure cannot create players.

### Availability tests

Prove:

- explicit OUT/QUESTIONABLE/etc. survives normalization;
- missing status becomes UNVERIFIED, not AVAILABLE;
- availability does not alter player identity.

### Market aggregation tests

Prove:

- selected game only;
- all six supported markets;
- freshest verified observation wins per book/side;
- best Over chooses lower line, price tiebreak;
- best Under chooses higher line, price tiebreak;
- consensus remains frozen Page-1 consensus contract;
- partial provider outage does not erase other verified books;
- opening/current movement is shown only with verified paired evidence.

### Model/history tests

Prove:

- 0–3 verified completed games -> no model probability;
- 4+ uses frozen Page-1 model contract;
- changing sportsbook lines does not change underlying projection;
- history failure fails soft;
- sportsbook projection influence stays 0.0.

### Matchup tests

Prove position-to-defense mapping and fail-closed CHECK behavior when defensive evidence is missing.

### UI/composition tests

Prove:

- one selected matchup hero;
- one Back action;
- ALL/QB/RB/WR/TE filter;
- player cards grouped by selected game teams only;
- truthful zero-prop state;
- prop row contains consensus/best lines/book count;
- Analyze action exists only for verified canonical player+market selection;
- mobile-safe responsive selectors/markers;
- no Page-3 Line Lab implementation leaks into Page 2.

### Integration/regression tests

Run existing frozen Page-1 route/slate/handoff/composition tests plus current Universal Atomic Navigation and runtime certification. Update only assertions that are genuinely superseded by the new terminal wrapper; do not weaken functional checks.

## Control-plane / Step 2A requirements

Before implementation:

1. exactly one active Page-2 problem;
2. exactly one authoritative Page-2 branch/PR/proof path;
3. one scope lease before the first product/test mutation;
4. include every planned write path in the lease;
5. detect/resolve frozen artifact ownership before proof;
6. no duplicate PR, proof, deployment, sandbox, or lease after an authority path exists;
7. classify failures before patching;
8. exact-head verification before Runless proof;
9. expected-head merge only;
10. merged-main provenance verification;
11. Finalization Ledger V2 freeze + read-back;
12. retire any thaw used;
13. release lease;
14. durable Runless `GREEN_FROZEN` read-back before declaring completion.

## Proposed implementation modules

New modules:

- `cfb_player_props_runtime_v2.py`
- `cfb_player_props_page2_context_v1.py`
- `cfb_player_props_page2_roster_v1.py`
- `cfb_player_props_page2_availability_v1.py`
- `cfb_player_props_page2_market_v1.py`
- `cfb_player_props_page2_matchup_v1.py`
- `cfb_player_props_page2_handoff_v1.py`
- `cfb_player_props_page2_v1.py`

Likely existing file modification:

- current Universal Runtime V5 CFB Player Props destination loader, to point at `cfb_player_props_runtime_v2` rather than Page 1 directly.

Frozen Page-1 product/data modules should otherwise remain unchanged unless an implementation-time test proves a tiny compatibility change is unavoidable. Any such discovery upgrades scope and must be called out before mutation.

## Success criteria

Page 2 is successful when a user can tap a real Page-1 CFB game and reliably see **only that game**, browse verified key offensive players, immediately see their available live player props across verified sportsbooks, understand a compact recent-production + opponent-defense + availability context, see Kyre probability/edge only when the frozen readiness gate is satisfied, and create an exact canonical player/prop selection for Page 3—without fabricated data, stale-route bleed, duplicate authority paths, or changes to the frozen projection model.

## Planned freeze identity

Final freeze token:

`MONSTER_CFB_PLAYER_PROPS_PAGE2_V1_FROZEN`
