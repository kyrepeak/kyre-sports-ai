# CFB Player Props Page 3 V1 — Player Prop Intelligence Lab

## Intent

Build Page 3 of the three-page College Football Player Props experience as the deep-dive analysis surface for exactly one selected player and one selected prop market.

The user journey is:

1. Page 1 answers **Which game?**
2. Page 2 answers **Which player and prop?**
3. Page 3 answers **What does the evidence say about this exact line?**

Page 3 must feel like a professional player-prop analytics terminal rather than another roster or odds list. It combines the frozen Kyre projection, a user-controlled Line Lab, current multi-book market evidence, recent production, stat-specific opponent context, opportunity evidence, truthful movement, and concise deterministic reasoning.

Hard UX requirements:

- a visible **← Back to Game Props** control that returns to Page 2 for the same game;
- a floating **↑ TOP** control that remains reachable on long mobile/tablet screens;
- one selected player + one selected prop market at a time;
- market switching for the same player without forcing a return to Page 2;
- no sportsbook line may influence the Kyre projection itself.

## Architecture decision

### Selected approach: isolated Page 3 + Runtime V3 selector

Create a new terminal wrapper:

- `cfb_player_props_runtime_v3.py`

Routing contract:

- no canonical `game_id` -> Page 1;
- canonical `game_id`, but no complete canonical `player_id + prop` -> Page 2;
- canonical `game_id + player_id + prop` -> Page 3.

The Universal Runtime CFB Player Props destination moves from Runtime V2 to Runtime V3. Runtime V3 delegates to existing frozen Page 1/Page 2 modules rather than copying them.

This is preferred over:

1. **Extending Page 2 into a Page-2/Page-3 monolith** — rejected because it couples browsing and deep analysis, increases render cost, and risks the already-frozen Page 2.
2. **Creating a disconnected Page-3 route with a second state system** — rejected because Page 2 already owns the canonical game/player/prop handoff and duplicated route identity would reintroduce cross-page bugs.

## Canonical Page-3 identity

Page 3 identity is exactly:

- sport: `cfb`;
- market family: `player-props`;
- slate date;
- official game ID;
- official player ID;
- canonical prop market key.

Provider event/player/market IDs remain provenance only.

Page 3 consumes `cfb_player_props_page2_handoff_v1.SESSION_HANDOFF_KEY` plus canonical query/session state. It must reconstruct and verify the selected game and player against existing Page-2 context/roster owners. A stale or mismatched player/prop cannot silently resolve to another player.

## Navigation contract

### Back to Page 2

**← Back to Game Props** clears only Page-3 selection state:

- `player_id`;
- `prop`;
- Page-3 line-lab/session selection state;
- Page-3 local market tab state.

It preserves:

- `sport=cfb`;
- `market=player-props`;
- slate `date`;
- exact `game_id`.

After rerun, Runtime V3 must render Page 2 for the same game. It must never fall back to Page 1 or another sport unless `game_id` is explicitly cleared by the Page-2 Back action.

### TOP button

Page 3 includes a fixed floating **↑ TOP** action using the same visual/navigation pattern already proven on Page 2. It must not open the keyboard, mutate route state, or obscure primary analysis controls on mobile.

## Page-3 context owner

Create:

- `cfb_player_props_page3_context_v1.py`

Responsibilities:

1. Resolve the exact selected game through existing Page-2 context rules.
2. Resolve the exact verified player from the selected game's current roster.
3. Canonicalize and validate the selected market against the existing supported market set.
4. Rebuild current market observations for that exact game/player rather than trusting stale Page-2 display values.
5. Preserve the original Page-2 handoff as provenance but treat current owners as live data authority.
6. Produce explicit states: `ready`, `market_unavailable`, `player_unavailable`, `invalid`, `unavailable`.

## Frozen model contract

Page 3 must reuse `cfb_player_props_model_v1` unchanged for projection inputs and baseline signal behavior.

Frozen constants remain:

- `MIN_SAMPLE = 4`;
- `MAX_SAMPLE = 8`;
- `DECAY = 0.85`;
- `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0`.

The Page-3 Line Lab may calculate probability at a user-selected line using the already-produced frozen projection mean and uncertainty. It may not feed sportsbook line values back into the projection.

## Line Lab

Create:

- `cfb_player_props_page3_line_lab_v1.py`

The Line Lab is the Page-3 centerpiece.

Inputs:

- frozen projection mean;
- frozen projection uncertainty;
- user-selected line;
- selected canonical market key.

Outputs:

- Over probability;
- Under probability;
- projection-minus-line margin;
- selected side at the chosen line;
- readiness state;
- probability-curve points for presentation.

Probability at a custom line uses the same Normal distribution semantics already used by the frozen model's line grading. The custom line changes only the threshold being evaluated.

### Slider ranges

Use 0.5-step line control with broad market-specific bounds so the user can test materially different lines:

- passing yards: `0.5–500.5`;
- rushing yards: `0.5–250.5`;
- receiving yards: `0.5–250.5`;
- receptions: `0.5–20.5`;
- passing touchdowns: `0.5–6.5`;
- touchdowns: `0.5–4.5`.

Default selection order:

1. current consensus line when available;
2. otherwise the selected Page-2 handoff line;
3. otherwise a safe market-specific midpoint only for the slider UI, clearly labeled as user-test state and never as a sportsbook line.

If the model is not ready, Page 3 still shows history/market evidence but custom model probabilities remain unavailable.

## Current sportsbook board

Reuse the current Page-2 market owner and frozen market normalization rather than creating a new sportsbook pipeline.

For the selected player/market show book-specific rows separately:

- sportsbook;
- line;
- Over price;
- Under price;
- observation freshness;
- provider/source provenance when useful.

Summary values:

- consensus line;
- verified book count;
- best Over;
- best Under;
- latest verified timestamp.

Direct/approved source priority remains governed by the current CFB source rule and existing market owner. One source failure may not erase good rows from another source. Missing/null is never converted to `0`.

## Market movement

Movement is presentation-only and fail-closed.

Show opening -> current only when the existing market owner has explicit trusted opening evidence for the same game/player/market/book. First-seen session values are not opening lines.

A compact timeline may show book-specific changes and consensus direction when supported. If opening evidence is absent, render `Verified opening movement unavailable.`

## Recent production and hit-rate panel

Create:

- `cfb_player_props_page3_history_v1.py`

Reuse verified player gamelog/history ownership. Do not change frozen projection history semantics.

Show:

- last 5 values;
- last 8 values;
- season verified values when available;
- average for each available window;
- hit count/rate versus the **currently selected Line Lab line**;
- sample size beside every hit rate;
- a simple game-by-game chart with the selected line drawn as the comparison threshold.

The chart is descriptive only. Hit rate is not substituted for model probability.

## Opportunity evidence

Page 3 may expose stat-appropriate volume evidence when explicitly available from verified player gamelog/event data:

- QB: attempts/completions when available;
- RB: carries when available;
- WR/TE: receptions and other explicitly available receiving volume fields;
- touchdown markets: verified scoring/opportunity fields only when supplied.

Do not fabricate snap share, route share, target share, red-zone share, or any other unavailable advanced metric. Missing evidence is labeled unavailable rather than estimated.

## Opponent-defense intelligence

Reuse existing Page-2 matchup/team-data owners:

- `cfb_team_data_v2`;
- `cfb_over_under_matchup_engine_v1`;
- `cfb_player_props_page2_matchup_v1` where its presentation-grade mapping remains applicable.

Stat mapping remains market-specific:

- passing yards / passing TDs -> opponent pass-defense context;
- rushing yards -> opponent rush-defense context;
- receiving yards / receptions -> opponent pass-defense context;
- touchdowns -> only supported rushing/receiving defensive context.

Opponent evidence is presentation-only and must not mutate the frozen projection.

## Player-vs-opponent history

Show a prior-meeting section only when exact verified prior-opponent metadata exists for the canonical player and opponent.

If exact prior-opponent evidence cannot be verified from current owners, render:

`No verified prior matchup sample.`

Never infer prior meetings from similar team names or missing opponent metadata.

## Game environment

Show only verified context that can materially affect interpretation:

- kickoff/status;
- venue;
- weather when supplied by an existing verified environment owner;
- selected-player availability;
- opponent/team availability context only when explicitly sourced;
- pace/game-environment indicators already owned by current CFB analytics modules.

No new heuristic adjustment from these fields is applied to the frozen player projection in V1.

## Deterministic reasoning panel

Create a compact **Why the model sees it this way** section from verified evidence only.

Possible evidence statements include:

- projection is above/below the selected line by X;
- recent average is above/below the selected line;
- model uncertainty is relatively wide/narrow as a descriptive value;
- verified opponent matchup context is favorable/neutral/tough;
- selected-player availability is OUT/DOUBTFUL/QUESTIONABLE/AVAILABLE/UNVERIFIED;
- market moved up/down when true opening evidence exists.

Also show compact **Bull Case** and **Bear Case** summaries assembled deterministically from those same facts. These are explanations, not new model inputs.

## Evidence-quality panel

Prefer transparent components over a synthetic confidence score.

Show:

- model readiness + sample count;
- verified book count;
- current source freshness;
- player availability state;
- opponent-data availability;
- movement availability;
- last refresh timestamp.

Do not label confidence `HIGH/MEDIUM/LOW` unless a separately specified and tested confidence model is introduced later.

## Page layout

Recommended mobile-first order:

1. Page-3 hero: player face, team logo, opponent, position, selected prop, availability.
2. Back to Game Props + compact market-switch control.
3. Kyre Projection vs Current Market hero.
4. Line Lab slider with Over/Under probability cards.
5. Probability curve.
6. Sportsbook board + best lines + freshness.
7. Market movement.
8. Recent production chart + L5/L8/season hit rates.
9. Opportunity evidence.
10. Opponent-defense context.
11. Prior matchup history when verified.
12. Game environment.
13. Why / Bull Case / Bear Case.
14. Evidence-quality panel.
15. Floating TOP control remains available throughout long-scroll content.

## Market switching

If the selected player has multiple verified markets, Page 3 offers a compact market selector at the top.

Changing market:

- preserves game ID and player ID;
- updates only canonical `prop` selection and Page-3 local line state;
- reloads history/model/market evidence for that market;
- never changes player identity based on sportsbook provider IDs.

## Responsive behavior

- No keyboard-triggering text/number inputs for primary navigation.
- Slider and market selector must be touch-friendly on phone/tablet.
- Sportsbook rows may collapse to compact cards on narrow screens.
- Probability/history charts must stay readable without horizontal page overflow.
- TOP button must not cover critical slider controls or the Streamlit management drawer.

## Fail-soft / fail-closed behavior

Fail soft:

- one sportsbook outage does not blank all market evidence;
- missing movement does not hide current quotes;
- missing opponent context does not hide player history;
- missing opportunity fields do not hide the Line Lab.

Fail closed:

- unresolved game/player/market identity blocks Page 3 analysis;
- model probability is unavailable below the frozen readiness threshold;
- missing/null source values never become `0`;
- no fabricated player-vs-opponent history;
- no fabricated opening line;
- no sportsbook input enters projection math.

## Performance and refresh

- Reuse current cached roster, history, matchup, and market owners.
- Fetch current market evidence once per render/cache cycle and filter locally.
- Avoid background rendering of Page 1 or Page 2 while Page 3 is active.
- Keep the existing live-market refresh behavior, but preserve slider state across refreshes when the canonical game/player/prop identity has not changed.

## Files expected during implementation

New:

- `cfb_player_props_runtime_v3.py`
- `cfb_player_props_page3_context_v1.py`
- `cfb_player_props_page3_line_lab_v1.py`
- `cfb_player_props_page3_history_v1.py`
- `cfb_player_props_page3_v1.py`
- focused Page-3 tests
- Page-3 integration/runtime tests
- Page-3 Runless proof plan + task ledger

Modify only as required:

- Universal CFB Player Props destination adapter to load Runtime V3.
- Frozen Page-2 code only if a proven compatibility defect prevents the existing Analyze handoff from reaching Runtime V3. Prefer no Page-2 mutation.

## Test requirements

Tests must pin at minimum:

- Runtime V3 routes Page 1/Page 2/Page 3 exclusively and never background-renders another page.
- Page-3 context rejects stale/wrong player/game/market identity.
- Back clears only Page-3 state and returns to Page 2.
- TOP control is present without mutating route state.
- market switching preserves game/player identity.
- custom-line probabilities use frozen projection mean/uncertainty and sportsbook projection influence remains `0.0`.
- model-not-ready state never emits a probability.
- probability curve is monotonic by line.
- book-specific lines remain separate.
- null values remain null/unavailable.
- hit-rate sample sizes are explicit.
- opponent context does not mutate model output.
- movement remains unavailable without verified opening evidence.
- player-vs-opponent history fails closed.
- Page 1 and Page 2 regression suites remain green.
- Universal Runtime V5 / Atomic Navigation regressions remain green.

## Freeze / closeout contract

Final freeze token:

`MONSTER_CFB_PLAYER_PROPS_PAGE3_V1_FROZEN`

GREEN + FROZEN requires:

1. one authoritative branch/PR/proof lane;
2. exact-head verification;
3. authoritative Runless proof;
4. exact-head merge;
5. merged-main verification;
6. immutable finalization-ledger freeze record + manifest read-back;
7. scope-lease release/read-back;
8. fresh final verification evidence before the completion claim.

## Out of scope for Page 3 V1

- changing Kyre projection math;
- feeding sportsbook odds/lines into projection;
- Monte Carlo simulation engine;
- synthetic AI-written explanations that are not traceable to verified evidence;
- new proprietary injury/depth-chart inference;
- fabricated advanced opportunity metrics;
- arbitrary free-text line entry;
- Page 4 or bet-slip execution;
- changing unrelated sport pages.
