# CFB Player Props Page 3 Professional V1 — Design

Date: 2026-10-20
Workstream: `monster-cfb-player-props-page3-professional-v1`
Parent freeze: `MONSTER_CFB_PLAYER_PROPS_PAGE3_V1_FROZEN`
Source main: `88cc62f815456890a8ba007be7cd6d927c6a15a2`
Scope lease: `SCOPE-LEASE-5B3FE9DA17B4BF0A67A81C90`

## Intent

Upgrade the existing CFB Player Props Page 3 from a functional intelligence screen into a professional, premium analytics page while preserving the already-frozen Page-3 projection contract and exact player/game/market identity.

The page must make the primary answer understandable immediately, then expose deeper evidence underneath it. It must add verified recent-player history, direct player-vs-opponent history, team matchup context, opponent-vs-position context when trustworthy data exists, and sportsbook-specific market comparison without allowing sportsbook information to mutate Kyre projection math.

## Non-negotiable contracts

1. Preserve frozen Page-3 owners and model math. Do not modify:
   - `cfb_player_props_page3_analysis_v1.py`
   - `cfb_player_props_page3_context_v1.py`
   - `cfb_player_props_page3_history_v1.py`
   - frozen projection behavior
2. Sportsbook projection influence remains exactly `0.0`.
3. Exact game, player, team, opponent, and market identity remain fail-closed.
4. Missing/null values remain missing/null and must never be converted to zero.
5. Sportsbook-specific lines remain separate observations; do not collapse the market into a fabricated single sportsbook line.
6. One failed provider must not blank a card when an approved fallback can provide the same semantic field.
7. Use only 2–4 relevant sources per data field. Never query every approved provider for every field.
8. Prefer direct/official sources over aggregators when they provide the same field.
9. Cross-check important data with at least two independent sources when possible.
10. When trustworthy sources disagree, prefer the newest timestamp after identity/semantic validation.
11. No universal-runtime route mutation in this workstream.
12. Existing Page-3 Back, market switching, slider identity cleanup, and TOP behavior remain intact.

## Source-routing contract

Page 3 will add a local field-source policy layer that is compatible with the existing universal provider registry/field-router contract but expresses the explicit CFB priority order requested for this page.

### Player props / sportsbook lines

Priority:
1. Direct sportsbook observations already available to the product, including FanDuel and any other configured direct books.
2. Approved odds aggregation transports such as Odds-API.io / The Odds API or SportsDataIO when configured and semantically equivalent.
3. Never synthesize a line when no verified observation exists.

The UI stores and displays each sportsbook separately. Consensus is allowed only as an explicitly labeled derived market statistic.

### Game lines / line movement

Priority:
1. Direct sportsbook observations.
2. Odds aggregation transport.
3. Action Network / VegasInsider-style confirmation/history when a compatible verified adapter exists.

Opening-line movement is shown only when the opening value is independently verified; first-seen session values are not mislabeled as true opening lines.

### Player stats

Priority:
1. NCAA Official / SportsDataIO when configured.
2. CollegeFootballData / Sports Reference-style verified historical adapters when available.
3. Existing exact-identity ESPN history may remain a fallback where the repository already owns that transport.

### Game scores / status / live state

Priority:
1. SportsDataIO / NCAA Official when configured.
2. ESPN / CBS / StatBroadcast-style confirmation where an approved adapter exists.

### Game / player history

Priority:
1. Sports Reference-style / CollegeFootballData-style verified historical owners when available.
2. NCAA Official.
3. Existing exact-identity history owner as fallback.

### Injuries / depth charts / availability

Priority:
1. Official team sources.
2. RotoWire when configured.
3. SportsDataIO when configured.
4. Existing verified availability owner as fallback.

### Provider-availability rule

A provider listed in policy is not automatically claimed as active. It may be used only when a configured/reachable adapter actually returns semantically valid data. Evidence labels must reflect sources actually consulted, not the whole approved pool.

## Architecture

### 1. Frozen owners remain read-only

`cfb_player_props_page3_analysis_v1.py`, `cfb_player_props_page3_context_v1.py`, and `cfb_player_props_page3_history_v1.py` remain unchanged. They continue to produce the authoritative Page-3 packet and frozen projection/probability behavior.

### 2. New field-source policy

Create `cfb_player_props_page3_source_policy_v1.py`.

Responsibilities:
- map each Page-3 field family to a ranked 2–4 source list;
- filter unavailable/unconfigured providers rather than pretending they are live;
- preserve exact semantic-field matching;
- choose the newest trustworthy observation when equivalent providers disagree;
- return explicit provenance metadata;
- never coerce missing values to zero;
- never allow sportsbook data to enter projection math.

This layer may reuse the existing universal provider registry and field-router as read-only policy dependencies.

### 3. New professional analytics composer

Create `cfb_player_props_page3_professional_v1.py`.

Responsibilities:
- consume the frozen Page-3 analysis packet;
- build presentation-only intelligence without changing projection math;
- derive recent-form windows and comparison summaries;
- separate direct player-vs-opponent history from team-vs-team history;
- expose opponent-vs-position evidence only when identity and sample validity are satisfied;
- build compact decision-card and evidence-card view models;
- carry provenance/source timestamps into every supplemental section.

### 4. Existing Page-3 UI upgraded in place

Modify `cfb_player_props_page3_v1.py` only for presentation and calls to the new helper modules.

The route and runtime identity remain unchanged, avoiding universal-runtime overlap with concurrent workstreams.

## Page hierarchy

### A. Premium Player Hero

Show:
- player headshot;
- team logo;
- player name and position;
- school/team;
- opponent;
- kickoff time;
- selected prop;
- selected/current market line when available;
- availability badge;
- live-market freshness badge.

Use the existing black / glacier-blue Kyre Sports AI visual language with tighter spacing, stronger typography, and mobile-safe sizing.

### B. Decision Bar

Directly below the hero, show the primary analytical answer:
- Kyre projection;
- selected line / market consensus;
- projection margin;
- model Over probability;
- model Under probability;
- confidence/evidence state;
- deterministic model lean when model-ready.

The lean must be derived from the frozen projection/line result only. Sportsbook pricing cannot change the model projection.

### C. Line Lab Centerpiece

Retain the interactive slider and make it the primary interactive visual.

Requirements:
- large thumb-friendly mobile slider;
- selected line visibly emphasized;
- model projection marker;
- current market/consensus marker when available;
- Over and Under probabilities update immediately;
- existing identity-keyed session-state reset behavior remains intact;
- no keyboard entry required.

### D. Recent QB / Player Form

For the selected player and selected market, display:
- Last 3 games;
- Last 5 games;
- each game result;
- comparison to selected line;
- average;
- hit count and hit rate;
- game/opponent/date labels where verified.

For quarterback passing markets, include available passing detail such as attempts, completions, passing TDs, interceptions, completion rate, and yards per attempt only when verified. Do not show zero placeholders for absent stats.

### E. Direct Player vs Opponent History

If the exact player has previously faced the exact opponent team ID, show the verified prior matchups separately:
- date/season;
- selected-market production;
- relevant supporting stats;
- selected-line hit/miss comparison;
- direct-H2H sample average and hit rate.

If no direct sample exists, display `No verified prior player-vs-opponent matchup`.

### F. Team vs Team History

If the schools/teams played previously but the selected player was not the same participant, show it under a separate label: `Team Matchup History`.

Never present team history as player H2H.

### G. Opponent vs Position / Role

When verified data exists, summarize how the upcoming opponent has performed recently against comparable players/positions for the selected market. The card must show sample size and source provenance. If no trustworthy sample exists, omit directional claims and show unavailable state.

### H. Sportsbook Market Board

Show sportsbook-specific rows separately:
- sportsbook;
- Over line and price;
- Under line and price;
- timestamp;
- best verified Over;
- best verified Under.

Never imply that consensus equals a single book's offered line.

### I. Market Movement

Show verified opening-to-current movement only when a trusted opening observation exists. Keep sportsbook identity attached to movement.

### J. Why the Model Sees It This Way

Render 3–5 compact evidence drivers, for example:
- projection margin;
- recent form;
- matchup context;
- opportunity/volume;
- availability;
- verified movement context.

Clearly distinguish supportive and risk evidence. These are explanations of existing evidence, not hidden changes to projection math.

### K. Data Quality / Sources

At the bottom of the page show:
- model sample size;
- sportsbook count;
- latest market timestamp;
- availability verification state;
- history sample size;
- source/provenance badges for supplemental fields;
- explicit unavailable states instead of blank cards.

## History semantics

The new composer will expose at least:
- `last3`
- `last5`
- `direct_opponent`
- `team_matchup`
- `opponent_vs_role`

Every history block must carry:
- sample size;
- average when calculable;
- hits / hit rate when a selected comparison line exists;
- source list actually used;
- newest source timestamp when known.

No block may claim a hit rate from missing production values.

## Error handling

- Provider failure is isolated to its semantic field.
- The page remains usable when optional supplemental evidence is unavailable.
- Required exact player/game/market identity still fails closed.
- Missing supplemental data renders an explicit unavailable caption, not `0`, fake rows, or empty unexplained cards.
- Provider exceptions are swallowed only at the adapter boundary and converted into provenance-aware unavailable results.
- A fallback may replace a missing field only if it represents the same semantic metric.

## Testing

### Source policy tests

Create `tests/test_cfb_player_props_page3_source_policy_v1.py` covering:
- 2–4 source cap per field;
- direct/official preference order;
- unavailable provider removal;
- fallback selection;
- newest-timestamp conflict resolution;
- null is not coerced to zero;
- sportsbook observations remain book-specific;
- only actually consulted providers are reported active.

### Professional composer tests

Create `tests/test_cfb_player_props_page3_professional_v1.py` covering:
- Last-3 and Last-5 summaries;
- exact direct-opponent identity filtering;
- team-vs-team history separation;
- opponent-vs-role unavailable semantics;
- hit-rate calculation against selected line;
- no fake zero values;
- sportsbook projection influence remains 0.0;
- no mutation of frozen projection packet.

### UI contract tests

The professional test suite will also inspect the Page-3 source for:
- premium hero and decision bar;
- Line Lab slider retained;
- recent-form and direct-H2H sections;
- sportsbook-specific board;
- data quality/source section;
- Back and TOP controls retained;
- no keyboard input path introduced.

Existing Page-3 regressions and Universal Runtime V5 certification remain required at final proof.

## Approaches considered

### A. Modify the frozen analysis/history owners

Rejected. It would require thawing already-finalized Page-3 core artifacts and increases regression risk unnecessarily.

### B. Add professional/source-policy helpers around frozen owners

Chosen. It preserves the frozen projection/history core, keeps the change isolated to Page 3, supports the requested richer history and source routing, and avoids universal-runtime overlap.

### C. Create an entirely new Page-3 runtime route

Rejected for this refinement. It adds route churn and would overlap shared universal-runtime surfaces while another lane is active.

## Finalization contract

Implementation will use exactly one successor branch/PR/Runless proof authority. Final completion requires:
1. exact-head focused verification;
2. existing Page-3 regression verification;
3. Universal Runtime V5 certification;
4. exact-head `runless-final-gate` success from App 5204253;
5. merge against the expected current main;
6. merged-main verification;
7. successor freeze record/read-back;
8. successor scope lease release;
9. final canonical GREEN + FROZEN read-back.

No duplicate PR, proof, deployment, lease, or finalization lane is permitted.