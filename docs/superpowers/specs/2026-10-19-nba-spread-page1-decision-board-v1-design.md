# NBA Spread Page 1 — Professional Decision Board V1 Design Specification

## Purpose

**Workstream:** `api2-nba-spread-page1-decision-board-v1`

Turn the current NBA Spread Page 1 into a launch-ready premium decision board for the 2026 NBA opener.

The page must answer, in roughly ten seconds:

> What NBA games are next, what is the verified spread market, what does Kyre's sportsbook-independent fair-spread model say, what is the cover probability/edge at the verified line, what injuries matter, and which matchup should I open for deeper Page-2 analysis?

This is the user-approved **Approach A — Professional Decision Board**.

Page 1 remains a scanner. Page 2 remains the deep-analysis owner.

## Current State

The current frozen Page-1 presentation is `nba_spread_page_v7.py`, routed through Universal Runtime V5 loader V22.

V7 already fixed the first presentation problem:

- only the next active NBA slate is shown;
- giant unavailable panels were removed;
- full injury walls were collapsed;
- compact game cards expose Market, Kyre Fair Spread, Cover Probability, Injury Status, and Model Status;
- Sources & Diagnostics is collapsed;
- Page 2 and the frozen Step-10 decision pipeline remain untouched.

The remaining launch problem is that important fields can still appear pending even when real market lines visibly exist. The current market bridge relies on the SportsGameOdds transport, which can return independent FanDuel, DraftKings, BetMGM, and Caesars observations but requires a working production credential path. The current Step-9 fair-spread model is already correctly separated: fair spread is sportsbook-independent, while cover probability uses the sportsbook only as a threshold.

## Product Goals

1. Make each game card feel like a premium sports decision card, not a system-status card.
2. Get real verified sportsbook spread observations onto Page 1 whenever an authorized market transport can supply them.
3. Keep Kyre Fair Spread independent of sportsbook availability.
4. Display cover probability and market edge only against a verified market threshold.
5. Add exact team logos.
6. Split injury status by team.
7. Add compact line movement only when verified history exists.
8. Add an exact-game `View Analysis →` handoff to existing Page 2.
9. Show public betting only when verified; hide pending public-betting status from the consumer surface.
10. Preserve sportsbook projection influence at 0.0% and preserve frozen model/probability/ranking ownership.

## Non-Goals

This mission does **not**:

- redesign Page 2;
- rewrite the Step-9 projected-margin/fair-spread formula;
- weaken Step-10 decision thresholds just to produce picks;
- invent injury point values;
- use sportsbook lines as fair-spread projection inputs;
- scrape numbers from screenshots;
- add brittle hidden FanDuel browser scraping as a production dependency;
- fabricate prices, spreads, splits, probabilities, injuries, logos, or line movement;
- modify unrelated NFL/CFB/MLB/WNBA routes.

## Page Hierarchy

Consumer order:

1. Universal KYRE SPORTS navigation
2. `NBA Spread`
3. human-readable next-slate header such as `NEXT NBA SLATE • TUE OCT 20`
4. one thin freshness / verification row
5. `Best Opportunities` only when at least one frozen Step-10 decision is a verified `PLAY`
6. compact matchup decision cards
7. collapsed `Sources & Diagnostics`

The previous tall Most Bet / Sharp Money / Market Spread unavailable panels, repeated preview cards, and full injury walls must not return.

## Date / Slate Contract

Reuse the current V7 next-active-slate behavior.

- Phoenix calendar time owns user-facing dates and tip times.
- Show the earliest upcoming verified NBA date in the rolling schedule.
- Use human-readable date labels on the consumer surface.
- Keep ISO dates for internal identity/diagnostics only.
- Games remain visible even when market/model fields are unavailable.

## Compact Matchup Decision Card

Each game card must contain, when verified:

- exact away/home logo + tricode/team name;
- Phoenix tip time and readable date;
- venue;
- **Market** — current line, coverage/book context, price only when explicitly supplied and validated;
- **Kyre Fair Spread** — sportsbook-independent Step-9 output;
- **Cover Probability** — probability at the verified current line;
- **Edge** — deterministic point difference between the displayed verified market line and Kyre Fair Spread;
- **Injury Status** — separated by team;
- **Decision** — frozen Step-10 PLAY/PASS/grade state translated into human-readable copy;
- optional verified line movement;
- explicit `View Analysis →`.

Illustrative shape only:

```text
☘ BOS @ DET 🔵                              12:00 PM MST
Boston Celtics at Detroit Pistons             TUE • OCT 20

MARKET             KYRE FAIR       COVER       EDGE
BOS -1.5 (-110)    BOS -3.0        57.8%       +1.5 pts
3 books verified

INJURIES
BOS: 1 OUT                       DET: 2 OUT • 2 Q

🟢 KYRE LEAN • BOS -1.5 • B+
Opened -2.0 → Current -1.5                    View Analysis →
```

Production values must be verified or omitted/gated.

## Market Intelligence Architecture

### Evidence ownership

No page-wide provider becomes universal truth.

For spread fields, the evidence unit is an **independent bookmaker observation attached to an exact canonical matchup**.

The existing SportsGameOdds transport may remain an aggregator transport, but FanDuel, DraftKings, BetMGM, Caesars, etc. must be treated as separate sportsbook observations when computing coverage/consensus.

Other categories remain independently owned:

- schedule/game identity: NBA Official + ESPN NBA;
- performance history: NBA Official + ESPN NBA source consensus;
- injuries/availability: existing verified injury route;
- public betting: existing verified public-betting route;
- market: verified sportsbook observations.

### Launch-critical production transport requirement

This workstream includes fixing/validating the **production market transport path**, not merely redesigning pending-state copy.

Before GREEN + FROZEN, implementation must determine why the deployed Page 1 does not receive tomorrow's spread observations while real sportsbook markets exist.

Required diagnostic sequence:

1. verify whether the production server can resolve an authorized market credential/source;
2. if the SportsGameOdds secret exists, verify the server-side credential discovery path and request contract;
3. verify the provider actually returns Oct. 20 NBA events and expected bookmaker rows;
4. verify canonical matchup normalization attaches BOS@DET, PHI@NYK, and OKC@SAS to the correct observations;
5. if the existing transport is unavailable, inspect the repository for another **already-supported, authorized** verified market transport before adding anything new;
6. do not claim launch-ready market functionality while the authorized transport remains broken or unconfigured.

If a required external credential truly does not exist and no authorized fallback transport exists, that is an explicit launch blocker, not a UI condition to hide.

The UI must still fail gracefully, but `GREEN + FROZEN` for this mission requires truthful resolution of the production market-data path or a clearly demonstrated external credential blocker that the implementation cannot create itself.

### Per-game market normalization

Normalize each verified row to:

- canonical game identity;
- away/home tricode;
- sportsbook name;
- away/home spread;
- retrieval/observation timestamp;
- American price when explicitly supplied and parseable;
- provider provenance.

Reject:

- one-sided pairs;
- non-opposite away/home spreads beyond tolerance;
- ambiguous identity;
- wrong date/game attachment;
- non-finite values;
- stale rows beyond the adopted freshness window;
- conflicting duplicate rows that cannot be deterministically reconciled.

### Consensus / limited coverage

A `Consensus` label requires at least two independent verified sportsbooks for the exact same game.

Use a deterministic rule, such as median spread, so provider ordering cannot change the result.

If only one verified sportsbook exists:

- show that exact sportsbook and line as `1 book verified`;
- do not call it consensus;
- preserve whatever quorum the frozen Step-9/Step-10 decision contract requires.

This mission must not weaken a frozen safety quorum to manufacture a recommendation.

### FanDuel visibility

If the verified transport supplies FanDuel, Page 1 may show FanDuel explicitly. The screenshot/manual observation is visual evidence only and never becomes a production data source.

## Fair Spread / Market Separation

The Step-9 model already supports the correct separation and sportsbook projection influence remains `0.0%`.

Page 1 must distinguish four states:

1. **Fair model ready + market ready** — show fair spread, market, cover probability, edge; Step-10 evaluates normally.
2. **Fair model ready + market unavailable** — still show Kyre Fair Spread; market/cover/edge remain gated.
3. **Fair model unavailable + market ready** — show market, but fair spread/cover/edge/pick remain gated with a human-readable model reason.
4. **Both unavailable** — keep the game card visible and compact; diagnostics remain collapsed.

The Page-1 renderer must not interpret `cover_verification=UNAVAILABLE` as evidence that the entire fair model is unavailable.

## Opening-Night / Cold-Start Contract

Opening night is launch-critical.

Before any model change, implementation must inspect whether the current two-source performance-history layer has enough verified pregame history for BOS, DET, PHI, NYK, OKC, and SAS.

If enough verified history exists, use the existing model unchanged.

If the frozen Step-9 model genuinely lacks sufficient history:

- do not silently lower `MIN_TEAM_GAMES`;
- do not silently blend unverified prior-season data;
- do not invent priors in this mission;
- show `Fair model waiting for verified history` (or equivalent) on the consumer card;
- retain the technical reason in diagnostics;
- treat a cold-start model redesign as a separate explicitly approved model mission.

## Injury Presentation

Replace combined counts like `3 out • 2 questionable` with team-separated summaries:

- `BOS: 1 OUT`
- `DET: 2 OUT • 2 Q`

At most one or two material verified player names per side may appear on Page 1. Full injury detail belongs on Page 2. No uncalibrated injury point deductions are introduced here.

## Team Logos

Use exact team identity only.

- Prefer already-verified schedule/team metadata or an existing canonical logo resolver.
- Never use fuzzy fallback that could attach the wrong logo.
- If exact identity cannot resolve, use a tricode/monogram fallback.

## Line Movement

Line movement is conditional.

Show `Opened X → Current Y` only when both endpoints are verified for the exact same game/market.

Acceptable evidence:

- provider-supplied opening/current line with trustworthy timestamps; or
- internally retained time-ordered verified snapshots, where the earliest snapshot is labeled `First seen`, not falsely called sportsbook `Open`.

If only the current line is known, omit movement.

## Public Betting Splits

Public betting remains secondary.

- show split status/cues only when verified;
- if unavailable, hide the consumer pending box entirely;
- keep the diagnostic in `Sources & Diagnostics`;
- public betting does not alter Kyre Fair Spread in this mission.

## Thin Freshness Strip

Replace the three large V7 status boxes with one low-height row, for example:

`● Market: 3 books verified   ● Injuries: verified   ● Updated: 2:48 PM MST`

Rules:

- book count means independent verified sportsbooks;
- public-betting status appears only when verified;
- stale data is explicitly labeled `STALE`;
- no technical error codes appear on the consumer surface.

## Best Opportunities

Preserve the V7 safety rule: only frozen verified Step-10 `PLAY` decisions may appear.

Each opportunity may show matchup, verified market, fair spread, cover probability, edge, and frozen grade/strength.

If there are no verified plays, omit the section completely.

No Page-1-only recommendation/ranking formula may be created.

## Exact Page-2 Handoff

Every card exposes `View Analysis →`.

The handoff must bind stable selected-game identity, including canonical game key/event ID when available, date, away/home teams, sport, and market route.

Required opener checks:

- BOS@DET opens BOS@DET;
- PHI@NYK opens PHI@NYK;
- OKC@SAS opens OKC@SAS;
- no stale prior-game identity;
- no cross-sport bleed;
- no keyboard popup;
- Page 2 itself is not redesigned here.

## Mobile UX Contract

- small aligned team logos;
- matchup and time readable without zooming;
- metrics collapse responsively to 2×2/short rows on narrow screens;
- no tiny debug text;
- no giant empty/status cards;
- explicit large tap target for `View Analysis`;
- no hidden navigation that can route the wrong game.

## Performance Contract

The redesign must not make Page 1 slower.

- schedule once per freshness-valid render;
- sportsbook payload once per slate refresh, partitioned in memory by game;
- injury payload once per slate refresh;
- public-betting payload once per slate refresh;
- performance/model work reuses existing caches;
- no provider fetch per game card;
- no duplicate sportsbook request for Market, Cover Probability, Edge, and status strip;
- measured cold/warm render checks are required.

## Error / Safety Contract

Fail soft at field level and fail closed at identity/decision level.

Examples:

- market unavailable -> game visible; market/cover/edge gated;
- one book -> limited coverage, not fake consensus;
- stale market -> visible stale state;
- fair model unavailable -> market may still display, but model/pick remains gated;
- injuries unavailable -> no inferred health state;
- ambiguous game identity -> reject provider attachment;
- no verified PLAY -> no Best Opportunities section;
- no public betting -> no consumer pending split card.

## Existing Systems to Reuse

Prefer reuse/extension of:

- `nba_spread_page_v7.py`;
- `nba_spread_page_v6.py`;
- `nba_spread_live_data_repair_v1.py`;
- `nba_spread_sportsbook_observations_v1.py`;
- `nba_spread_market_lines_v1.py`;
- `nba_spread_page_v4.py` / `nba_spread_fair_spread_probability_v1.py` Step-9 ownership;
- `nba_spread_page_v5.py` Step-10 decision ownership;
- existing injury and public-betting routes;
- Universal Runtime V5 route delegation;
- existing exact-game navigation/session contracts;
- Runless exact-head proof, frozen-artifact registry, Finalization Ledger V2, Step 2A, scope-aware lease, anti-loop, and failure ownership.

## Protected Boundaries

Do not change without an explicitly reviewed compatibility seam:

- Step-9 projected-margin/fair-spread formula;
- Step-9 probability formula;
- Step-10 decision thresholds;
- Page-2 analytical ownership;
- unrelated sports routes;
- universal navigation semantics;
- sportsbook projection influence (`0.0%`);
- uncalibrated injury adjustment (`0.0` points);
- canonical schedule identity rules.

## Testing Contract

Implementation begins RED-first.

At minimum prove:

1. exact per-game market attachment;
2. deterministic two-book consensus;
3. one-book limited coverage is not called consensus;
4. missing market does not suppress a verified fair spread;
5. cover probability remains unavailable without a verified market threshold;
6. market may display while fair model is unavailable;
7. edge uses only the exact displayed verified market + fair spread;
8. team injuries remain separated;
9. ambiguous/wrong-game observations fail closed;
10. stale market is gated;
11. prices render only when supplied/validated;
12. line movement renders only from verified time-ordered evidence;
13. public-betting pending state is absent from consumer UI;
14. Best Opportunities uses only frozen Step-10 verified PLAY decisions;
15. opener `View Analysis` actions preserve exact game identity;
16. NBA Spread only is overridden by the new runtime route;
17. Page-2 regressions remain green;
18. universal navigation/runtime certification remains green;
19. sportsbook projection influence stays 0.0%;
20. a live opener probe confirms truthful market/model/injury states.

Historical test failures must be baseline-checked before being classified as regressions.

## GREEN + FROZEN Completion Contract

Call this mission complete only after:

- one authoritative branch/PR/proof chain;
- production market transport root cause is classified and repaired when repair is possible with authorized existing credentials/sources;
- exact candidate SHA proof passes;
- focused + NBA behavioral + Page-2 + universal navigation/runtime tests pass, with any baseline-only debt proven unchanged;
- opener live-data probe confirms exact games and truthful data states;
- proof-before-merge succeeds;
- exact-head merge succeeds;
- merged-main verification runs on the actual merge SHA;
- any frozen-artifact thaw is exact-path/exact-blob and forward-ported;
- Finalization Ledger V2 binds candidate, merged SHA, proof digest, and artifacts;
- Runless closeout returns `GREEN_FROZEN / NONE`;
- workstream leases read back zero;
- only then may the work be labeled `🟢 100% GREEN + ❄️ FROZEN`.
