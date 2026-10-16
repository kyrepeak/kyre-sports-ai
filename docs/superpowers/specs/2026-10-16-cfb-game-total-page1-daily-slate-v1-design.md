# CFB Game Total — Page 1 Daily Slate V1 Design Specification

## Purpose

**Workstream:** `monster-cfb-game-total-page1-daily-slate-v1`

Restructure College Football -> Game Total into the first page of a future three-page experience. This mission builds only **Page 1: Daily Game Slate**.

Page 1 must answer one question quickly and cleanly on mobile and desktop:

> What college football games are on the selected Phoenix calendar day, when and where are they played, what are the current game conditions, and what does the verified betting market currently show?

The page must show **all available FBS + FCS games for the selected day**. It must not become a model-analysis page.

## Architectural Context

The current Game Total presentation was most recently certified as a two-page flow with a selected-game analysis wrapper and a clean slate wrapper. This new mission supersedes that human-facing page-order presentation by introducing a canonical Page-1 daily slate owner while protecting already-frozen analytics/model systems.

This mission is intentionally the first part of a future three-page architecture:

1. **Page 1 — Daily Slate**: all games, logistics, live state, market snapshot.
2. **Page 2 — Matchup**: future mission; not redesigned here.
3. **Page 3 — Deep Game Total Analysis**: future mission; not redesigned here.

No Page-2 or Page-3 product redesign is allowed in this workstream.

## User-Approved Page 1 Behavior

### Coverage

- Include every discoverable **FBS + FCS** game whose normalized kickoff falls on the selected **America/Phoenix** calendar date.
- `All Games` is the default view.
- Games must not be silently excluded because sportsbook, weather, TV, or injury data is unavailable.
- Missing verified fields remain visible using `—` or `Unavailable`; no guessing or fabrication.

### Phoenix calendar-day ownership

- Every kickoff time shown on Page 1 is normalized to `America/Phoenix`.
- A game belongs to the Phoenix date on which its displayed kickoff occurs.
- If the selected date contains zero games, Page 1 automatically advances to the next Phoenix date with a real FBS/FCS slate.
- The UI must make the resulting selected date explicit after an automatic advance.

### Top-level controls

The top of Page 1 contains:

- `CFB Game Total`
- a subtitle identifying this as the full college-football slate in Phoenix time
- date navigation: previous date / selected date or Today / next date
- team search
- lightweight filter chips:
  - `All Games`
  - `Live`
  - `Upcoming`
  - `Ranked`
  - `FBS`
  - `FCS`
  - `Conference`

Filters alter only the visible slate. They must not mutate game identity, provider routing, market values, or canonical data.

## Slate Organization

Page 1 groups games by operational state and kickoff window.

Display order:

1. **Live Games**
2. **Next Upcoming Window** — automatically expanded
3. remaining future kickoff windows — collapsed by default
4. **Completed Games** — collapsed at the bottom

Recommended kickoff-window labels are Early, Afternoon, Evening, and Late; exact boundaries may be implemented as stable presentation constants provided all games remain ordered chronologically by Phoenix kickoff.

Inside every section, games are ordered strictly by Phoenix kickoff time. Ranked status, betting attractiveness, model score, popularity, or provider quality may not reorder the slate.

When a game reaches `Final`, it leaves its original active/upcoming window and appears in `Completed Games`.

## Compact Game Card Contract

Every game uses one consistent card structure.

### Always-visible card content

When available and verified:

- away team logo, name, record, ranking
- home team logo, name, record, ranking
- Phoenix kickoff time or current live/final status
- score when live or final
- quarter / clock for live games
- television/network
- compact weather summary
- current moneyline
- current spread
- current game total
- explicit `More` control
- explicit `View Game` control

The card itself must not navigate. Only `View Game` may perform downstream navigation.

### Expanded `More` content

`More` expands in place on Page 1 and may show:

- stadium / arena / venue name
- city/location
- temperature
- precipitation probability
- sustained wind
- gusts
- indoor/dome indicator where relevant
- detailed television/broadcast information
- conference / subdivision
- important availability flags, including material quarterback uncertainty and major known absences
- opening moneyline vs current moneyline
- opening spread vs current spread
- opening game total vs current game total
- line movement
- source/market confidence state

`More` must not route away from Page 1.

## Live-State Contract

Page 1 remains useful throughout the day.

Supported visible states include:

- `Scheduled`
- `Starting Soon`
- `Live`
- `Halftime`
- `Final`

For live games, expose score, period/quarter, and game clock when verified.

Live updates may refresh game-state fields but must not overwrite or reinterpret preserved pregame market history.

The data model must keep these concepts distinct:

- opening market
- latest verified pregame market
- live market, if available

A live price must never be silently substituted for the historical pregame current line.

## Multi-Source Data Architecture

This workstream must reuse the existing provider-independent sports-source architecture rather than creating a new page-wide provider owner.

### Governing rule

No single external provider may become the universal source of truth for Page 1.

The unit of source ownership remains the **field/data category**, consistent with the repository's Universal Sports Source Intelligence architecture.

### Required source categories

At minimum, Page 1 requires explicit ownership/fallback policy for:

- schedule / kickoff
- canonical game identity
- team identity / aliases
- subdivision (FBS/FCS)
- team records
- rankings
- venue / city
- television/network
- game status / score / clock
- weather
- availability/injury context
- moneyline
- spread
- game total
- opening/current line movement

### Canonical identity

- KYRE/API 2/MONSTER canonical game and team IDs remain authoritative internally.
- Provider IDs/names are aliases.
- Ambiguous identity must fail closed rather than attach data to the wrong matchup.

### Minimum trustworthy evidence

- Do not fan out blindly to every provider.
- Use the strongest eligible source route per field.
- Stop when the field's minimum trustworthy evidence policy is satisfied.
- Expand to fallback/quorum sources only for failure, staleness, ambiguity, low confidence, or disagreement.

### Betting-market consensus

Page 1 uses multi-source market evidence for moneyline, spread, and game total when available.

The visible market value must be deterministic and provenance-backed. The implementation plan must define a stable rule for selecting/displaying the current consensus/best verified line without pretending that disagreeing books are identical.

When evidence is thin or conflicting, expose a user-facing confidence state such as:

- `Strong consensus`
- `Mixed market`
- `Limited coverage`

If no trustworthy line can be established, show `Unavailable` rather than fabricating a number.

## Mobile UX Contract

Page 1 is mobile-first.

The implementation must not reproduce the previous pattern of squeezing dense desktop analysis into narrow columns.

Rules:

- one readable vertical game card at a time on narrow screens
- scan-first information hierarchy
- optional detail expansion second
- navigation third
- no deep analysis wall
- no tiny multi-column stat matrices
- no hidden tap-anywhere navigation
- expandable regions must not unexpectedly jump/route

Desktop may use wider spacing or controlled multi-column layout only if card readability and chronological ordering remain obvious.

## Explicitly Excluded from Page 1

This workstream must not add or surface deep analytical content such as:

- model win/total probability
- projected final score
- projected game total
- pace analysis
- explosive-play analysis
- red-zone analysis
- matchup-history reasoning
- defense-vs-offense analytical comparisons
- market-aware football reasoning narratives
- toughness/best-pick ranking
- betting recommendation

Those belong to later pages.

## Navigation / Future Page 2 Handoff

Each card exposes a distinct `View Game` action.

This mission must establish a stable handoff containing the canonical selected-game identity and intended next-page route. It may delegate to the existing selected-game downstream surface for compatibility, but **must not redesign or mutate that downstream Page-2/Page-3 content in this workstream**.

The Page-1 implementation must therefore separate:

- Page-1 card expansion state
- selected-game route identity
- downstream page content ownership

so the future Page-2 mission can replace the downstream presentation without rebuilding the Daily Slate.

## Existing Systems to Reuse

Prefer extension/reuse over replacement of:

- the current CFB shared shell and market navigation
- current canonical team/game identity machinery
- Universal Sports Source Intelligence field-level routing, trust/quorum, provider-health, and provenance contracts
- existing CFB schedule/game-total data owners where semantically compatible
- existing Runless exact-head proof path
- Finalization Ledger V2 / current frozen-state process
- Step 2A
- scope-aware lease protection
- parallel-workstream isolation
- anti-loop / failure-ownership protections

Do not create a competing provider-health system, canonical identity system, finalization mechanism, or duplicate route authority.

## Protected Systems / Non-Goals

Unless implementation discovery proves an unavoidable compatibility seam and that seam is explicitly reviewed before mutation, this mission must not modify:

- Game Total model/projection/probability math
- existing deep-analysis calculations
- ranking/selection/betting recommendation logic
- unrelated CFB markets: Moneyline, Over/Under, Top Picks
- NFL, NBA, WNBA, MLB product behavior
- sportsbook projection influence
- legacy frozen analytics solely to make Page 1 easier to build

The old Page-1/Page-2 presentation wrappers may be bypassed or retired from active routing as required, but frozen artifacts themselves should not be casually deleted or rewritten.

## Performance Contract

An all-games FBS+FCS slate can be large, so Page 1 must avoid linear provider fan-out and unnecessary rendering work.

Required behavior:

- source-router early stop after minimum trustworthy evidence
- cache/reuse immutable or freshness-valid source decisions
- no duplicate fetch for the same canonical game+field within one render cycle
- lazy/conditional expansion for detail-only data where practical
- collapsed kickoff windows should not force unnecessary heavyweight presentation work
- no repeated polling of unfinished async/provider operations
- failures must be classified once before fallback/escalation

The implementation plan must define a bounded refresh strategy for live games that does not create request storms.

## Error / Unavailable Behavior

Page 1 fails soft at the field level and fail-closed at identity level.

Examples:

- missing weather -> `Unavailable`
- missing sportsbook line -> `Unavailable`
- missing TV -> `—`
- provider disagreement -> explicit confidence/disagreement state
- ambiguous game/team identity -> do not merge provider data into that matchup
- zero games on selected Phoenix date -> jump to next date with games and visibly update the date

A partial but truthful card is acceptable. A confidently wrong card is not.

## Testing Contract

Implementation must begin with a focused RED regression contract and remain red before product code changes.

Coverage must prove at minimum:

- all FBS + FCS games are eligible for the selected Phoenix date
- Phoenix-date normalization and empty-date forward behavior
- strict chronological ordering
- auto-expanded next window and collapsed remaining windows
- Live / Upcoming / Ranked / FBS / FCS / Conference filters
- completed games move to Completed Games
- compact vs expanded card surfaces
- only `View Game` navigates
- missing fields render `—` / `Unavailable`
- field-level source routing does not establish one page-wide provider master
- betting market evidence preserves opening/current/live distinctions
- ambiguous identity fails closed
- mobile contract does not restore the old cramped multi-column analysis behavior
- unrelated frozen CFB/NFL/etc. route regressions remain green

## Step 2A / One-Authority Execution Contract

Implementation will use exactly one authoritative mutation chain for this Page-1 workstream.

Before product mutation:

1. identify one active problem
2. identify one authoritative branch/PR/proof/deployment path
3. acquire/verify only the required scope lease
4. write the RED contract before product code
5. do not create duplicate branches, PRs, proof requests, deployments, or async runs
6. classify any terminal failure before changing strategy
7. converge through the same authority chain whenever safe

## Acceptance Contract

Page 1 may be declared product-GREEN only when exact-head proof demonstrates all of the following:

- the active CFB Game Total Page 1 is the new Daily Slate owner
- every discoverable FBS + FCS game for the selected Phoenix date is represented or truthfully classified unavailable at the field level
- date selector and Phoenix kickoff ownership agree
- empty selected dates advance to the next game date
- kickoff-window auto-collapse behavior is correct
- Live Games and Completed Games move correctly by status
- compact cards and `More` expansion match the approved interaction design
- `View Game` is the only downstream navigation action
- ML/spread/total use provider-independent field routing and deterministic verified market evidence
- opening/current/live market states remain distinct
- missing data is never fabricated
- mobile presentation remains readable and non-cramped
- no Page-2/Page-3 redesign occurs
- protected model/projection/probability/ranking/selection systems remain unchanged
- scoped regression suites pass

The mission may be declared **GREEN + FROZEN** only after:

1. exact candidate identity
2. authoritative Runless proof
3. proof-before-merge authorization
4. merge
5. merged-main verification
6. Finalization Ledger / freeze transaction
7. unrelated frozen/thaw state preservation
8. scope-lease release
9. canonical read-back proving the expected freeze token/state

No progress percentage or visual completeness may substitute for these proof gates.
