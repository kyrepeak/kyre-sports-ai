# CFB Player Props Page 1 V1 — Game-First Prop Hub Design

Date: 2026-10-19
Workstream: `monster-cfb-player-props-page1-v1`
Project: Kyre Sports AI / College Football
Scope: Page 1 of the planned three-page CFB Player Props experience

## User intent

Build a professional three-page College Football Player Props product. This mission implements only Page 1, but Page 1 must establish stable identities and handoffs that Pages 2 and 3 can consume without redesigning the route or data contracts later.

The approved Page 1 experience is game-first:

1. automatically resolve the next active CFB slate;
2. show the real games on that slate;
3. show verified player-prop availability and compact Kyre AI signals for each matchup;
4. let the user tap exactly one game to continue to Page 2 later;
5. keep deep player analysis and Line Lab out of Page 1.

Success means Page 1 is fast, clean, mobile-safe, truthful about data availability, multi-source where sources actually have coverage, and integrated into the current universal CFB navigation without regressing existing Moneyline, Over/Under, Game Total, or Top Picks pages.

## Product architecture

### Route

Add one canonical CFB market route:

- id: `player-props`
- label: `Player Props`
- legacy market: `Player Props`
- canonical page params: `date`, `game_id`

The route must participate in the existing Universal Sports Navigation controller and Universal Atomic Navigation behavior. It must not create a second top-level navigation system.

### Page hierarchy

Page 1 is the **slate / matchup hub**. It owns only:

- next-active-slate resolution;
- game cards;
- compact verified prop coverage;
- compact best-signal preview;
- Page-1 filters/sorting;
- selected-game handoff for future Page 2.

Page 1 does not own:

- complete game roster presentation;
- full player history;
- player-vs-defense history;
- line movement charts;
- adjustable Line Lab;
- full probability curve;
- deep model contributors;
- final Page-3 analysis presentation.

Those are reserved for Pages 2 and 3.

## Data ownership

### 1. Schedule and game identity

Reuse the current CFB schedule truth and universal next-slate resolver rather than adding a second schedule implementation.

Canonical game identity is the existing official CFB event identity. Provider event IDs are aliases only and may never replace the official identity.

Page 1 must:

- resolve the next active CFB game date automatically;
- use Phoenix-local presentation time in the UI while preserving canonical kickoff timestamps;
- render every verified game returned for that selected slate;
- carry the exact selected official game ID into the future Page-2 handoff.

### 2. Player identity

Introduce one reusable player identity contract for CFB props:

- official team ID;
- official athlete/player ID when available;
- canonical player name;
- position;
- team abbreviation/name;
- provider aliases and provider player IDs only as aliases;
- identity verification state and provenance.

A sportsbook row cannot be attached to a player based only on fuzzy display-name similarity when a stronger official/provider identity is available.

### 3. Sportsbook observations

Introduce a normalized CFB player-prop market observation contract. Each observation must include:

- official game ID;
- canonical player identity;
- canonical market key;
- sportsbook/provider;
- line;
- Over price when available;
- Under price when available;
- observed timestamp/freshness;
- provider event/player/market IDs as aliases;
- identity verification state;
- source provenance.

Initial canonical market family:

- passing yards;
- rushing yards;
- receiving yards;
- receptions;
- passing touchdowns;
- anytime touchdown / player touchdown when the provider exposes a compatible market.

The UI shows only markets that are actually available and safely normalized. It must not imply that every book offers every college player prop.

### 4. Multi-source policy

Page 1 is field-driven, not source-loyal.

Preferred source roles:

- existing official CFB schedule/identity owner for game truth;
- official/statistical source such as the existing ESPN-backed CFB identity/stat paths for player/team history where available;
- SportsGameOdds or another currently configured multi-book aggregator for sportsbook observations when it exposes the required CFB player-prop market;
- direct FanDuel transport using the repository's existing CFB provider pattern when that surface exposes verified player props;
- an already-supported secondary odds provider may fill missing observations only when identity and freshness gates pass.

No fallback may overwrite a fresher verified primary quote merely because it is present. Each field keeps provenance.

A provider that lacks a market is an unavailable source, not a reason to fabricate a row.

### 5. Model preview

Page 1 may show a compact Kyre AI projection/probability only when the player/market passes readiness gates.

The reusable model contract must be independent of sportsbook direction. Sportsbook data supplies the threshold/price context; it does not dictate the Kyre projection.

Minimum readiness for a displayed probability:

- verified player identity;
- verified game/opponent identity;
- sufficient official recent/season sample for the requested statistic;
- no unresolved structural parsing failure;
- finite model projection and dispersion/uncertainty;
- live/acceptable sportsbook line freshness for the probability shown against that line.

When readiness fails, Page 1 may still display a verified sportsbook market, but must label the Kyre signal as unavailable/pending rather than inventing a projection.

## Page 1 visual design

### Header

Keep the universal Kyre Sports header/nav stable.

The Page 1 hero beneath it should show:

- `CFB • PLAYER PROPS` eyebrow;
- `College Football Player Props` title;
- selected slate date;
- `Next active slate` status;
- count of games with verified prop coverage;
- compact source/freshness status.

No duplicate site header.

### Filter strip

Keep controls tap-only/mobile-safe where practical. Page 1 can include compact filters for:

- All Games;
- games with live props;
- QB / RB / WR-TE preview signal;
- market family where useful;
- sorting by kickoff or strongest verified edge.

The default state is the full next active slate, ordered by kickoff.

### Matchup cards

Each game card should be decision-first and compact:

- away/home team logos;
- school/team names and abbreviations;
- rankings when verified;
- kickoff time;
- game status;
- verified sportsbook coverage count;
- available prop-market badges;
- one compact `Top Kyre Signal` preview only when model-ready;
- player name + market + live line + Over/Under side + model probability + edge when verified;
- `No verified player props posted yet` when the game is real but props are absent;
- one clear `View Game Props` action that stores the exact game handoff for Page 2.

Do not render a long player list on Page 1. Page 2 owns the full player pool for the selected matchup.

### Empty and degraded states

- Real game + no verified player props: keep the game card, show truthful no-props state.
- Provider temporarily unavailable: keep schedule truth and show degraded source state; never delete real games from the slate just because an odds provider is down.
- Schedule unavailable: fail closed with a clear retry/status message; do not synthesize games.
- Model unavailable: sportsbook observations may remain visible, but probability/edge must collapse or show `Model unavailable`.

## Page-2 handoff contract

Page 1 writes one canonical selected-game payload for the future Page 2:

- route version;
- selected slate date;
- official game ID;
- canonical away team ID/name;
- canonical home team ID/name;
- kickoff timestamp;
- selected CFB market route (`player-props`);
- generation/version token for stale-navigation protection.

Provider-specific IDs must not be the navigation key.

The handoff must be restorable from supported query/session route state so refresh/back navigation does not silently open the wrong game.

## Performance and navigation

Page 1 must inherit Universal Atomic Navigation V1:

- only the selected CFB Player Props route renders;
- previous sports/markets cannot remain visible behind it;
- non-selected sports/pages do not prefetch in the background;
- stale async/provider results cannot commit after route generation changes;
- no blanket Streamlit cache clearing;
- schedule, identity, and provider calls use deliberate TTL/cache boundaries;
- one user route action should cause at most one necessary rerun.

The page should render schedule/card shells before expensive optional model enrichment where architecture permits, without exposing stale prior-page content.

## Scope and isolation

This mission may add new CFB Player Props Page-1 modules and tests and minimally extend the current canonical CFB route registry/dispatch path.

It must not:

- redesign existing CFB Moneyline, Over/Under, Game Total, or Top Picks pages;
- modify NFL Daily Picks V4-owned files;
- reopen the frozen Universal Atomic Navigation V1 lane;
- modify unrelated NBA/MLB/WNBA/NFL page behavior;
- change existing frozen CFB projection engines;
- fabricate sportsbook quotes, player identities, game identities, injuries, rankings, probabilities, logos, or movement;
- implement Pages 2 or 3 beyond the stable selected-game handoff contract.

## Testing and proof

Implementation must be TDD-first.

Required focused contracts:

1. `player-props` is a valid CFB canonical route with `date` and `game_id` params.
2. Existing four CFB markets remain byte/behavior compatible except for the additive nav option.
3. Next-active-slate selection reuses current CFB schedule truth.
4. Page 1 renders every verified game in the selected slate even when prop coverage is missing.
5. Prop observations require verified game + player + market identity and finite live line data.
6. Multi-source merge preserves provenance and does not overwrite fresher verified observations with weaker fallback rows.
7. Probability/edge is absent unless model readiness gates pass.
8. Sportsbook line acts as threshold/context and has 0.0 direct influence on the underlying Kyre projection.
9. Tapping one card emits the exact official game handoff and no other game.
10. Atomic Navigation route isolation remains GREEN; no old-page/background renderer executes for the selected route.
11. Mobile/tap-only selector and universal nav regressions remain GREEN.
12. Existing CFB schedule/market and Universal Runtime certification remain GREEN.

Final certification must follow the current Step-2A / Runless chain:

`exact candidate -> exact-head verification -> immutable receipt -> App 5204253 runless-final-gate -> expected-head merge -> merged-main verification -> Finalization Ledger V2 freeze/read-back -> scope-lease release -> durable GREEN_FROZEN`.

## Freeze token

`MONSTER_CFB_PLAYER_PROPS_PAGE1_V1_FROZEN`
