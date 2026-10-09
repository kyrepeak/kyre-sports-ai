# CFB Game Total Page 1 Visual Cleanup — Step 1 Target Lock

## Mission
Lock the approved Page-1 presentation hierarchy before any product rendering changes. The current live page is functional but evidence-first. The approved target is summary-first and uses the supplied premium sports-dashboard mockup as a visual/composition reference only.

## Non-negotiable Overview order
1. Matchup Hero
2. Game Context Strip — stadium, location, weather, wind, date/time
3. Overview / Full Analysis tabs
4. Game Prediction + Market Comparison
5. Favorable For + Key Edge + Toughness For
6. Team Snapshot
7. Games on This Day
8. Data Sources + Updated + How We Calculate

## Evidence-wall disposition
The following surfaces may remain available, but they must not dominate Overview:
- GAME TOTAL EVIDENCE • STEPS 1–12
- FINAL MODEL SUMMARY
- TOP-5 SLATE SCANNER

They move to Full Analysis / secondary expandable evidence in later implementation steps. Step 1 does not mutate product runtime.

## Data truth
- The Ohio State/Oregon reference matchup and all values visible in the mockup are illustrative only.
- Never hardcode mockup teams, scores, rankings, lines, weather, records, projections, confidence, or market prices.
- Preserve the real selected-game state and exact-ID data paths.
- Keep America/Phoenix as the Page-1 time policy; mockup ET labels are illustrative.
- Keep sportsbook projection influence at 0.0%.
- Do not change model/projection math, market ownership, ranking, selection, qualification, probability, or API truth.

## Runtime dependencies — read only in Step 1
- Active Page-1 owner: `cfb_game_total_clean_page_v38`
- Public repair: `cfb_game_total_page1_v2_step4_public_repair_v1`
- Router chain: V160 → V181 → V190 → V191

## Prior visual contract
`docs/CFB_GAME_TOTAL_VISUAL_REDESIGN_V1_CONTRACT.md` remains authoritative for the established dark/navy/glass visual language, responsive behavior, accessibility, and visual tokens. This target lock supersedes only the old hierarchy that left the Steps 1–12 evidence wall as a primary page surface.

## Step 2–5 implementation boundaries
- Step 2: hero + top shell convergence.
- Step 3: Overview summary cards and team snapshot convergence.
- Step 4: games-on-this-day/footer polish and evidence relocation.
- Step 5: live mobile/tablet/desktop visual certification and mission closeout.

## Step 1 exit gate
GREEN + FROZEN requires TDD RED evidence, exact-head Runless GREEN, exact-head merge, merged artifact read-back, frozen-registry token `CFB_GAME_TOTAL_PAGE1_VISUAL_CLEANUP_V1_STEP1_TARGET_LOCK_FROZEN`, and terminal authority cleanup.
