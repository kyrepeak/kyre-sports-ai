# NBA PRA Page 2 V1 — Player Intelligence Deep Dive

## Intent

Build Page 2 of the NBA PRA experience as the deep-dive analysis surface for exactly one player and the exact PRA market selected on Page 1.

User journey:

1. Page 1 answers **Which PRA play is strongest?**
2. Page 2 answers **Why should I trust this exact player/line, what makes the matchup favorable or tough, and what could make the play lose?**

Page 2 must feel like a professional analytics terminal, not a second list page. It gives the decision immediately, then organizes deeper evidence into clean sections so the user can stop early or drill down.

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

Routing:

- `sport=nba`, `market=pra`, no valid selected player -> Page 1;
- `sport=nba`, `market=pra`, valid selected player -> Page 2.

The existing Page-1 session key `ks_nba_pra_selected_player` is reused as the canonical player handoff. Page 2 verifies that identity against the current Kyre Sports API snapshot rather than trusting stale display text.

Prefer a new NBA PRA runtime selector/overlay rather than modifying Page 1 rendering internals. Frozen Page 1 files remain unchanged unless a proven handoff defect makes a tiny compatibility patch unavoidable.

## Canonical Page-2 identity and tapped-quote handoff

Page 2 identity is:

- sport: `nba`;
- market family: `pra`;
- slate date;
- canonical player key / official player identity;
- player current team;
- current opponent/game identity.

The Page-1 click handoff additionally preserves the tapped quote snapshot when available:

- sportsbook;
- line;
- Over price;
- Under price;
- observed timestamp.

The quote snapshot is provenance, not permanent market authority. Page 2 immediately re-reads the current quote through Kyre Sports API.

If the live quote still matches the selected snapshot, render normally. If the sportsbook moved the line/price after the tap, Page 2 must visibly label **LINE MOVED SINCE SELECTION**, show the selected snapshot and the current quote separately, and grade the current market using the current verified quote. It must never silently rewrite the selected snapshot.

Provider IDs remain provenance, never route identity.

A stale or ambiguous player selection must fail closed instead of silently opening another player.

## Navigation contract

### Back button

A visible **← Back to PRA Board** control returns to Page 1.

Back clears only Page-2-local selection state:

- selected player deep-dive state;
- selected quote snapshot;
- Page-2 Line Lab custom line;
- Page-2 local tab/accordion state when applicable.

It preserves:

- sport `nba`;
- market `pra`;
- current slate date / page route.

The return must land on Page 1 for NBA PRA, never another sport or NBA market.

### TOP button

A floating **↑ TOP** control remains available throughout the long Page-2 scroll.

Requirements:

- one tap scrolls to top;
- no keyboard popup;
- no player/market route mutation;
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
- selected/current sportsbook quote, PRA line, Over/Under price, and freshness;
- line-moved-since-selection state when applicable.

No generic NBA avatar/logo when verified player/team identity is available.

## 1. Kyre AI Verdict

Display immediately:

- selected side: OVER / UNDER / PASS;
- current line;
- Kyre projection;
- projection edge;
- modeled probability when variance/history is sufficient;
- Kyre Edge Score + tier;
- confidence/readiness state;
- short deterministic explanation using verified evidence only.

Explanation may mention recent form, minutes, opponent ranking, role/availability, and line gap. It must not invent causal evidence.

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

- 0.5 PRA step slider;
- default = current exact selected sportsbook line;
- custom line labeled as a test line, never as a sportsbook quote;
- slider changes threshold only and never feeds back into projection math;
- no free-text numeric input for primary use.

## 3. Current sportsbook board + movement

Show approved sportsbook quotes separately:

- sportsbook;
- line;
- Over price;
- Under price;
- observed timestamp/freshness.

Never average conflicting lines.

Movement appears only when same-book historical observations are genuinely stored. Session-first values are not opening lines.

If unavailable, show `Verified line movement unavailable.`

## 4. Recent form

Show verified form using the same history that powers the model:

- L5 PRA average;
- L10 PRA average;
- season/prior-season sample when current-season sample is not yet meaningful;
- average minutes;
- hit count/rate versus active Line Lab line;
- sample size beside every hit rate.

Game-by-game evidence includes date, opponent, PTS, REB, AST, PRA, MIN, and Over/Under result versus the active test line.

Hit rate is descriptive and never substituted for model probability.

## 5. Opponent ranking against the selected stat

For PRA, show component and combined opponent rankings when legitimate data exists:

- rank vs points;
- rank vs rebounds;
- rank vs assists;
- rank vs PRA / verified positional PRA allowance when supported.

Ranking convention is fixed and explicit:

- **Rank 1 = toughest / stingiest defense against that stat**;
- **Rank 30 = most permissive / easiest defense against that stat**.

The UI should prefer user-readable phrases such as `3rd toughest` or `6th most favorable` rather than an ambiguous raw ordinal alone.

No component rank may be fabricated from unrelated defensive metrics.

## 6. Favorable / Medium / Tough matchup label

The Page-2 selected-stat matchup grade is deterministic:

- ranks **1–10 -> TOUGH**;
- ranks **11–21 -> MEDIUM**;
- ranks **22–30 -> FAVORABLE**.

For the PRA page, the label uses the verified opponent PRA/positional-PRA rank when available. Points, rebounds, and assists ranks are supporting breakdown evidence.

If a verified PRA rank is unavailable, Page 2 must show `MATCHUP GRADE UNAVAILABLE`; it must not synthesize the label by averaging or guessing from unrelated component ranks.

The matchup label is presentation/context in V1. It does not alter the frozen Page-1 Kyre projection.

## 7. Opponent matchup intelligence

Beyond ranking, show verified context when available:

- opponent pace;
- points/rebounds/assists allowed to the player position or closest approved role grouping;
- defensive rebounding environment;
- assist environment;
- relevant paint/perimeter context;
- matchup difficulty badge.

Only fields backed by approved source data render.

## 8. Player vs opponent history

Show prior meetings only when exact player + opponent identity is verified.

Display each prior game's PRA, PTS/REB/AST/MIN, average PRA, hit rate versus active Line Lab line, and sample size.

If no exact verified prior meeting exists, show `No verified prior matchup sample.`

## 9. Role & minutes intelligence

Display verified role/opportunity evidence:

- projected minutes when an approved owner provides it;
- recent minutes;
- starter/bench status when verified;
- recent usage/possessions/touches only when available from approved analytics sources;
- current role-change indicator when explicitly evidenced.

Do not invent touches, usage, starter status, or projected minutes.

## 10. Injury / lineup impact

Show selected-player availability, important teammate availability when approved sources expose it, and deterministic role notes only when verified evidence supports the relationship.

Do not infer teammate-impact adjustments from injury labels alone.

## 11. Projection breakdown

Explain the projection without pretending unsupported internals exist.

If the model exposes component adjustments, display them. Otherwise show traceable evidence:

- base recent-form estimate / sample window;
- minutes context;
- opponent context labeled presentation-only when not a model input;
- role/availability context labeled presentation-only when not a model input;
- final frozen Kyre projection.

Never fabricate numeric component adjustments.

## 12. Risk factors

Use deterministic verified flags such as:

- small history sample;
- wide model variance;
- minutes volatility;
- recent role change;
- questionable/doubtful status;
- return from long absence;
- no recent eligible season;
- weak opponent-history sample;
- stale or thin market coverage.

No generic AI prose detached from evidence.

## 13. Full game log

Expandable table:

- date;
- opponent;
- PTS;
- REB;
- AST;
- PRA;
- MIN;
- outcome vs active Line Lab line.

Default compact view keeps the top half clean.

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
15. Floating TOP throughout.

Use progressive disclosure/expanders for deep evidence so Page 2 stays professional instead of becoming a dense spreadsheet.

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
- model probability unavailable without legitimate variance;
- missing PRA rank cannot generate Favorable/Medium/Tough;
- missing values never become `0`;
- no fabricated prior matchup history;
- no averaged sportsbook line;
- no SGO, ESPN, or ESPN BET anywhere active.

## Performance

- Reuse current Page-1 snapshot/cache owners where practical.
- Load only selected-player/game deep-dive data when avoidable instead of rebuilding all 110 player deep dives.
- Fetch market quotes once per refresh cycle and filter locally.
- Cache opponent/team ranking by game/team/stat key.
- Do not render Page 1 in the background while Page 2 is active.
- Preserve Line Lab state across safe refreshes when canonical player/game identity remains unchanged.

## Expected implementation boundaries

Prefer new modules:

- `nba_pra_runtime_v2.py` or equivalent NBA PRA page selector;
- `nba_pra_page2_context_v1.py`;
- `nba_pra_page2_line_lab_v1.py`;
- `nba_pra_page2_matchup_v1.py`;
- `nba_pra_page2_v1.py`;
- focused Page-2 UI/context/line-lab/matchup/integration tests;
- Page-2 Runless execution/proof/task-ledger artifacts.

Modify existing frozen files only if required by a proven compatibility defect:

- NBA PRA Universal Runtime destination overlay;
- Page-1 handoff code only if the existing player selection cannot safely carry the quote snapshot or trigger Page 2.

Do not modify Page-1 model math.

## Testing requirements

Tests must pin at minimum:

- no selected player -> Page 1 only;
- valid selected player -> Page 2 only;
- Page 1 never background-renders while Page 2 is active;
- stale/wrong player identity fails closed;
- exact tapped quote snapshot is preserved as provenance;
- moved live quote shows selected vs current separately;
- Back returns to NBA PRA Page 1 and preserves sport/market route;
- TOP control is present and route-neutral;
- verified player headshot and team logo render;
- multi-book lines remain separate;
- slider changes threshold only, not projection;
- sportsbook projection influence remains 0.0;
- probability unavailable when sigma/variance unavailable;
- L5/L10/MIN use verified model-history bucket;
- opponent points/rebounds/assists/PRA ranking semantics are explicit;
- ranks 1–10/11–21/22–30 map to Tough/Medium/Favorable only from verified selected-stat rank;
- missing PRA rank -> matchup grade unavailable;
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
