# NBA PRA Page 2 V1 — Player Intelligence Deep Dive

## Intent

Build Page 2 of the NBA PRA experience as the deep-dive analysis surface for exactly one player and the exact PRA market selected on Page 1.

User journey:

1. Page 1 answers **Which PRA play is strongest?**
2. Page 2 answers **Why should I trust this exact player/line, what makes the matchup favorable or tough, and what could make the play lose?**

Page 2 must feel like a professional analytics terminal, not a second list page. It should give the decision immediately, then organize deeper evidence into clean sections so the user can stop early or drill down.

Selected design: **Hybrid S-tier (Option C)**.

## Non-negotiable source contract

- **Kyre Sports API is the only application-facing API/data gateway.**
- Never use SportsGameOdds / SGO.
- Never use ESPN or ESPN BET in request, fallback, enrichment, verification, or production paths.
- Do not call every source at once. Route by data type.
- Preserve sportsbook, line, price, and timestamp separately. Never average conflicting sportsbook lines.
- Never fabricate missing values. If an approved source cannot provide a field, move only to the next approved source for that field type.
- Page 2 may reuse Page 1 model outputs but sportsbook lines remain at **0.0% influence** on Kyre projection math.

Approved routing priority by data type:

- player props / odds: FanDuel primary, then DraftKings, BetMGM, Caesars, bet365, Fanatics Sportsbook, The Odds API, OpticOdds as appropriate;
- official player/team stats: NBA Stats, then configured Sportradar/SportsDataIO;
- game/player history: NBA Stats, Basketball-Reference, Stathead, Sportradar as available; CBS Sports may be used only as approved backup verification/fill when the stronger source is degraded or rate-limited;
- injuries/availability/lineups: NBA Official Injury Report primary, RotoWire secondary;
- advanced matchup analytics: NBA Stats, PBP Stats, Sportradar when configured;
- backup verification: CBS Sports, Basketball-Reference, SportsDataIO, Sportradar.

## Architecture decision

### Selected approach: isolated Page 2 + NBA PRA runtime selector

Create a Page-2 runtime layer that delegates to the existing frozen Page 1 when no player is selected and renders Page 2 when a canonical Page-2 selection is present.

Preferred routing:

- `sport=nba`, `market=pra`, no valid selected player -> Page 1;
- `sport=nba`, `market=pra`, valid selected player + exact selected PRA quote identity -> Page 2.

The existing Page-1 session key `ks_nba_pra_selected_player` is reused as the starting handoff. Page 2 must verify that selected identity against the current Page-1/Kyre Sports API snapshot rather than trusting stale display text.

Prefer a new NBA PRA runtime selector/overlay rather than modifying Page 1 rendering internals. Frozen Page 1 files should remain unchanged unless a proven handoff defect makes a tiny compatibility patch unavoidable.

## Canonical Page-2 identity

Page 2 identity is:

- sport: `nba`;
- market family: `pra`;
- slate date;
- official/canonical player identity;
- player current team;
- current opponent/game identity;
- selected sportsbook quote identity when available: sportsbook + line + over price + under price + observed timestamp.

Provider IDs remain provenance, never the primary route identity.

A stale or ambiguous player selection must fail closed instead of silently opening another player.

## Navigation contract

### Back button

A visible **← Back to PRA Board** control returns to Page 1.

Back clears only Page-2-local selection state, including:

- selected player deep-dive state;
- Page-2 Line Lab custom line;
- Page-2 local tab/accordion state when applicable.

It preserves:

- sport `nba`;
- market `pra`;
- current slate date / page route.

The return must land on Page 1 for NBA PRA, not another sport or another NBA market.

### TOP button

A floating **↑ TOP** control remains available throughout the long Page-2 scroll.

Requirements:

- one tap scrolls to top;
- must not open the keyboard;
- must not mutate player/market route state;
- must not cover the Streamlit management drawer or Line Lab controls on phone/tablet;
- same behavior across iPhone/iPad/desktop widths.

## Page-2 hero / identity card

The top of Page 2 shows:

- player headshot / picture ID;
- team logo ID;
- player name;
- current team and position;
- opponent and opponent logo;
- game date/time in Phoenix time;
- verified injury/availability state;
- selected sportsbook + current PRA line + over/under price + freshness.

No generic NBA avatar/logo when a verified player/team identity is available.

## 1. Kyre AI Verdict

The first analytics section must answer the bet question immediately.

Display:

- selected side: OVER / UNDER / PASS;
- current line;
- Kyre projection;
- projection edge;
- modeled probability when variance/history is sufficient;
- Kyre Edge Score + tier;
- confidence/readiness state;
- short deterministic explanation using verified evidence only.

The explanation may mention recent form, minutes, opponent ranking, role/availability, and line gap. It must not invent causal evidence.

## 2. Line Lab

Line Lab is the primary interactive Page-2 feature.

Inputs:

- frozen Kyre projection mean;
- frozen model uncertainty / sigma when available;
- user-selected test line.

Outputs update live:

- Over probability;
- Under probability;
- projection-minus-line edge;
- selected side;
- Kyre Edge Score/tier for the test threshold;
- readiness state.

Rules:

- slider uses 0.5 PRA steps;
- default is the exact selected sportsbook line;
- custom line is explicitly labeled as a test line, not a sportsbook quote;
- changing the slider never feeds the line back into projection math;
- no free-text numeric input for primary use, avoiding mobile keyboard popups.

## 3. Current sportsbook board + movement

Show each approved sportsbook quote separately:

- sportsbook;
- line;
- Over price;
- Under price;
- observed timestamp/freshness.

Never create a consensus by averaging conflicting lines.

Movement may be shown only when true same-book historical line observations exist. Session-first values are not labeled as opening lines.

If movement history is unavailable, show `Verified line movement unavailable.`

## 4. Recent form

Show verified form using the same history that powers the model:

- L5 PRA average;
- L10 PRA average;
- season/prior-season sample when current-season sample is not yet meaningful;
- average minutes;
- hit count and hit rate versus the currently selected Line Lab line;
- sample size beside every hit rate.

Include a game-by-game visual/table with:

- date;
- opponent;
- points;
- rebounds;
- assists;
- PRA;
- minutes;
- Over/Under result versus the currently selected Line Lab line.

Hit rate is descriptive and is never substituted for model probability.

## 5. Opponent ranking against the selected stat

Page 2 must show opponent ranking for the exact selected stat family.

For PRA, show both the combined PRA context and component ranks when legitimate data exists:

- opponent rank vs points;
- opponent rank vs rebounds;
- opponent rank vs assists;
- opponent rank vs PRA / aggregated positional allowance if a verified owner supports it.

Example presentation:

- Points defense vs position: `16th`;
- Rebounds defense vs position: `1st`;
- Assists defense vs position: `24th`;
- PRA matchup: `8th toughest`.

Ranking semantics must be explicit: whether `1st` means stingiest/toughest or most allowed/easiest. The UI should phrase rankings in user-readable terms such as `3rd toughest` or `25th toughest` to avoid ambiguity.

## 6. Favorable / Medium / Tough matchup label

Create a deterministic stat-specific matchup grade:

- **FAVORABLE** — opponent is meaningfully permissive for the selected stat/profile;
- **MEDIUM** — middle-of-league matchup;
- **TOUGH** — opponent is meaningfully restrictive.

The grade must be derived from the same verified opponent-ranking evidence shown on screen.

Do not produce a matchup grade when the ranking evidence is unavailable or stale beyond the accepted contract. Show `MATCHUP GRADE UNAVAILABLE` instead.

The matchup grade is presentation/context in V1. It does not silently mutate the frozen Page-1 Kyre projection unless a separately approved future model version explicitly introduces that feature.

## 7. Opponent matchup intelligence

Beyond rank, show verified context when available:

- opponent pace;
- points/rebounds/assists allowed to the player position or closest approved role grouping;
- defensive rebounding environment;
- assist environment;
- relevant paint/perimeter context;
- matchup difficulty badge.

Only fields backed by approved source data are rendered.

## 8. Player vs opponent history

Show prior meetings only when exact player + opponent identity can be verified.

Display:

- each prior game PRA;
- PTS / REB / AST / MIN;
- average PRA;
- hit rate versus the currently selected Line Lab line;
- sample size.

If no exact verified prior meeting exists, show `No verified prior matchup sample.`

## 9. Role & minutes intelligence

Display verified role/opportunity evidence:

- projected minutes when an approved source/model owner provides it;
- recent minutes;
- starter/bench status when verified;
- recent usage/possessions/touches only when available from approved analytics sources;
- current role-change indicator when explicitly evidenced.

Do not invent touches, usage, starter status, or projected minutes.

## 10. Injury / lineup impact

Show:

- selected player's verified availability;
- important teammate availability when approved sources expose it;
- deterministic role notes only when evidence supports the relationship.

Example allowed language: `Primary ball-handler OUT; verified recent on/off role evidence shows increased assist opportunity.`

Do not infer teammate-impact adjustments from injury labels alone.

## 11. Projection breakdown

Expose a transparent explanation of the current Kyre projection without pretending unsupported model internals exist.

If the model exposes component adjustments, show them directly.

If not, show a traceable evidence summary instead:

- base recent-form estimate;
- sample window;
- minutes context;
- opponent context as presentation-only if not in model;
- role/availability context as presentation-only if not in model;
- final frozen Kyre projection.

Never fabricate numeric component adjustments.

## 12. Risk factors

Compact risk panel using deterministic verified flags such as:

- small history sample;
- wide model variance;
- minutes volatility;
- recent role change;
- questionable/doubtful status;
- return from long absence;
- no recent eligible season;
- weak opponent-history sample;
- stale or thin market coverage.

No generic AI prose detached from actual evidence.

## 13. Full game log

Expandable detailed table at the bottom:

- date;
- opponent;
- PTS;
- REB;
- AST;
- PRA;
- MIN;
- outcome vs the active Line Lab line.

Default compact view should not make the top half feel crowded.

## Mobile-first layout order

1. Back to PRA Board + page title.
2. Player hero: picture, team logo, opponent, status, current quote.
3. Kyre AI Verdict.
4. Line Lab.
5. Sportsbook quote board / verified movement.
6. Recent Form.
7. Opponent Ranking + Favorable/Medium/Tough badge.
8. Opponent Matchup Intelligence.
9. Player vs Opponent History.
10. Role & Minutes.
11. Injury / Lineup Impact.
12. Projection Breakdown / Why.
13. Risk Factors.
14. Full Game Log.
15. Floating TOP remains available throughout.

Use progressive disclosure/expanders for deep evidence so Page 2 stays professional rather than becoming a dense spreadsheet.

## Fail-soft / fail-closed behavior

Fail soft:

- one sportsbook failure does not erase other verified quotes;
- missing opponent ranking does not hide recent form;
- missing prior-matchup history does not hide Line Lab;
- missing movement does not hide current quotes;
- one secondary provider failure does not trigger shotgun calls to all providers.

Fail closed:

- unresolved player identity blocks Page 2;
- wrong/stale selected player cannot silently resolve to another player;
- model probability remains unavailable without legitimate variance;
- missing ranking cannot generate Favorable/Medium/Tough;
- missing values never become `0`;
- no fabricated prior matchup history;
- no averaged sportsbook line;
- no SGO, ESPN, or ESPN BET anywhere active.

## Performance

- Reuse the current Page-1 snapshot/cache owners where practical.
- Page 2 should load only the selected player/game deep-dive data, not all 110 players again when avoidable.
- Market quotes should be fetched once per refresh cycle and filtered locally.
- Opponent/team ranking data should be cached by game/team/stat key.
- Do not render Page 1 in the background while Page 2 is active.
- Preserve Line Lab state across safe refreshes when canonical player/game identity remains unchanged.

## Expected implementation boundaries

New modules should be preferred:

- `nba_pra_runtime_v2.py` or equivalent NBA PRA page selector;
- `nba_pra_page2_context_v1.py`;
- `nba_pra_page2_line_lab_v1.py`;
- `nba_pra_page2_matchup_v1.py`;
- `nba_pra_page2_v1.py`;
- focused Page-2 UI/context/line-lab/matchup/integration tests;
- Page-2 Runless execution/proof/task-ledger artifacts.

Modify existing frozen files only if required by a proven compatibility defect:

- NBA PRA Universal Runtime destination overlay;
- Page-1 handoff code only if the existing session selection cannot trigger the new runtime selector safely.

Do not modify Page-1 model math.

## Testing requirements

Tests must pin at minimum:

- no selected player -> Page 1 only;
- valid selected player -> Page 2 only;
- Page 1 never background-renders while Page 2 is active;
- stale/wrong player identity fails closed;
- Back returns to NBA PRA Page 1 and preserves sport/market route;
- TOP control is present and route-neutral;
- player headshot and team logo are rendered from verified identity;
- exact selected quote identity is preserved;
- multi-book lines remain separate;
- slider changes threshold only, not projection;
- sportsbook projection influence remains 0.0;
- probability unavailable when sigma/variance is unavailable;
- L5/L10/MIN use the verified model-history bucket;
- opponent points/rebounds/assists/PRA ranking semantics are explicit;
- Favorable/Medium/Tough derives only from verified ranking evidence;
- missing ranking -> matchup grade unavailable;
- opponent context does not silently mutate frozen projection;
- player-vs-opponent history fails closed;
- injury/role fields are not fabricated;
- null source values remain null/unavailable;
- no active SGO/SportsGameOdds/ESPN/ESPN BET references;
- Page-1 regression suite remains green;
- Universal Runtime V5 navigation/isolation regressions remain green.

## Freeze / closeout contract

Final freeze token:

`API2_NBA_PRA_PAGE2_V1_FROZEN`

GREEN + FROZEN requires:

1. one authoritative branch;
2. one authoritative PR;
3. one Runless proof path;
4. exact-head regression + forbidden-provider verification;
5. Runless final gate on exact candidate;
6. expected-head merge;
7. production deployment/read-back on exact merge SHA;
8. finalization-ledger freeze record + manifest + bridge read-back;
9. scope-lease release/read-back;
10. fresh verification evidence before any 100% completion claim.

## Out of scope for Page 2 V1

- changing Page-1 projection math;
- feeding sportsbook lines into projection;
- new bet-slip/wager execution;
- new Page 3;
- arbitrary free-text model prompts;
- fabricated advanced metrics;
- changing unrelated NBA/NFL/CFB/WNBA pages;
- SGO or ESPN-family integration of any kind.
