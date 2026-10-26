# MONSTER WNBA PRA Page 1 Ultra S-Tier V2 Design

## Intent
Make WNBA PRA Page 1 feel like a premium decision-first sports analytics terminal while staying extremely simple. The page should answer, at a glance: what is the best opportunity, what is the line, what does the model project, how strong is the probability/edge, what has the market done, and where can the user open deeper analysis.

## Goals
- Keep the existing black / glacier-blue Kyre Sports visual language.
- Condense the hero into a compact market-status header.
- Replace the three oversized Top 3 cards with one compact ranked leaderboard.
- Make each player card decision-first: pick + line, probability, projection, edge, verified trends, line movement, book/price, then analysis handoff.
- Hide internal model plumbing such as `LINE_BOUND_READY`, `Model State`, and `LINE BOUND` from the consumer UI.
- Hide L5/L10/Season when the snapshot does not contain verified values instead of rendering blank dashes.
- Hide the Final PRA section entirely when no certified pick exists; show a premium compact certified-pick hero only when qualified.
- Preserve search/sort/status controls and existing Page 2 handoff behavior.

## Non-goals
- No provider changes.
- No network calls from the presentation layer.
- No projection, probability, edge, qualification, Monte Carlo, ranking, sportsbook, or market math changes.
- No change to the frozen WNBA PRA S-tier renderer, frozen model artifact, or final-polish V1 display/runtime identity layers.
- No ESPN, ESPN BET, SGO, or Render.

## Architecture
Use a MONSTER-only additive successor `wnba_pra_page1_ultra_stier_v2.py`. It consumes the existing certified Page 1 snapshot and reuses the frozen row-building/ranking/handoff helpers plus the verified image fallback helpers from final-polish V1. The historical compatibility boundary keeps its V1 assignment intact for prior contracts, then explicitly installs the V2 successor before importing the refresh-handoff module so the live render path receives V2 without mutating certified data/model code.

## Presentation contract
1. Compact hero: WNBA PRA, updated time, Verified / Exact Odds / No Averaging / Kyre Sports API.
2. One slate strip: Players, Model Ready, Best Edge, Best Probability, compact market-movement count, current book.
3. One Top 3 leaderboard table with player, matchup, pick, projection, edge, probability, verified trends, line movement, and price.
4. Three-column discovery grid on wide screens; compact responsive stack on smaller screens.
5. Player cards never expose internal model-state strings; verified readiness is a tiny consumer-safe status only.
6. Optional trend fields render only when verified.
7. Final PRA section renders only when at least one certified final pick exists.

## Frozen boundaries
The following remain byte-identical throughout this workstream:
- `wnba_pra_page1_stier_v1.py`
- `wnba_pra_page1_final_polish_v1.py`
- `wnba_pra_page_model_artifact_final_polish_v1.py`
- `runless_v2/wnba_pra_page1_final_polish_runtime_v1.py`

## Control contract
One branch, one PR, one exact-head proof lane. Failure must be classified before correction; no duplicate PR/run/deployment lane. Final GREEN/FROZEN requires exact-head tests, source-policy proof, protected MONSTER merge, production convergence evidence, and frozen-registry/readback evidence.