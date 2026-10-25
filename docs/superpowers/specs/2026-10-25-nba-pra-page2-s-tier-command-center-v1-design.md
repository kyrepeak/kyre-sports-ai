# NBA PRA Page 2 S-Tier Command Center V1 Design

## Intent
Transform the live NBA PRA Page 2 from a long stack of similarly weighted cards into an elite visual sports-analytics command center. A user should understand the pick in seconds, then be able to inspect the evidence deeply without leaving the page.

## Approved direction
Use the visual analytics command-center approach shown in the approved mockup. Preserve the existing dark navy / glacier-blue Kyre Sports AI brand and the current player-level information, but make hierarchy, visual analytics, and evidence density the focus.

## Goals
- Make the first viewport communicate player, matchup, decision, sportsbook line, Kyre projection, probability, edge, score/tier, and evidence coverage.
- Replace repeated static cards with visual evidence: projection distribution, recent PRA chart, verified PRA composition, matchup rank bars, and compact market intelligence.
- Keep the existing detailed Insights analyst report, but use it as the written explanation layer while the rest of the page becomes the visual evidence layer.
- Preserve the Line Lab behavior: frozen projection, local threshold re-evaluation, zero external provider fetches per slider move.
- Preserve Kyre Sports API as the only application-facing data gateway. No SGO, ESPN, or ESPN BET.
- Fail closed. Unsupported evidence must be omitted or summarized in a compact Data Gaps area; it must never be fabricated.
- Keep mobile/tablet rendering first-class.

## Non-goals
- No changes to projection math, sigma, probability formulas, score/tier math, provider routing, sportsbook influence, or Page 1 handoff math.
- No new external provider calls.
- No synthetic projected PTS/REB/AST components. The current model exposes only total PRA projection, so the component visualization is labeled VERIFIED PRA COMPOSITION and is derived only from verified game history.
- No averaging of conflicting sportsbook lines.

## Architecture
Keep the frozen Page 2 V1/core/Insights files byte-identical. Add a new pure presentation module, `nba_pra_page2_command_center_v1.py`, which consumes the same verified `context`, `model`, `line_result`, and `matchup` mappings already loaded by Page 2. Update only `nba_pra_page2_sync_v1.py` to route Page 2 HTML/CSS rendering through the successor presentation module while continuing to use the frozen model/default-line helpers.

The successor module performs no I/O and no provider access. It may derive display-only SVG geometry, evidence coverage, verified recent-stat averages, rank-bar positions, and market presentation from data already present in the mappings.

## Page hierarchy
1. Player Command Center hero
2. Projection Distribution
3. Kyre Insights + Kyre Final Insight
4. Recent Performance chart
5. Verified PRA Composition
6. Matchup Intelligence rank bars
7. Market Intelligence
8. Role / Availability / Data Gaps (only verified evidence receives full visual weight)
9. Risk & Evidence Quality
10. Full Game Log

The native Streamlit PRA Line Lab slider remains functional and continues to drive local threshold re-evaluation; the HTML redesign removes the redundant legacy FAST LINE LAB card and redundant standalone KYRE AI VERDICT panel because those metrics are promoted into the hero.

## Visual truth rules
- Projection distribution uses only `model.projection` and `model.sigma`; if sigma is absent, render a truthful unavailable state rather than a curve.
- Recent Performance uses only verified game rows with PTS/REB/AST, showing a horizontal active-line marker.
- Verified PRA Composition uses average verified PTS/REB/AST from the same displayed history sample; it is never labeled as a model component projection.
- Matchup bars use the verified 1-to-30 opponent ranks already supplied by matchup context.
- Market Intelligence preserves every sportsbook quote independently with its own line, prices, and timestamp. No conflicting lines are averaged.
- Evidence Coverage is a display-only completeness indicator, not model confidence.
- Unverified usage, injuries, history, or other missing fields appear in a compact Data Gaps treatment rather than full-size empty cards.

## Safety / control constraints
- API 2 only; MONSTER state is never evidence or authority.
- Step 2A: one authoritative branch/PR/proof path.
- Anti-Loop: no duplicate PRs, runs, proofs, deployments, leases, or repeated polling.
- Step 2B: lock acceptance criteria and source/proof mapping before implementation.
- Step 2C: classify failures and repair root causes autonomously.
- Step 2D: sportsbook/provider/data truth remains unchanged.
- Step 2E: regression protection must prove frozen projection/provider behavior and the frozen prior Page 2 artifacts remain unchanged.
- Step 2F: exact-head protected-main proof, merge, live-main identity, freeze registry write/readback, durable GREEN_FROZEN closeout.

## Acceptance criteria
- The new live Page 2 uses the command-center hierarchy above.
- It contains a truthful projection-distribution visualization when sigma is verified.
- It contains a game-by-game PRA chart using verified game history.
- It contains verified PRA component composition without inventing component projections.
- It contains visual opponent rank bars and compact market intelligence.
- Insights remain present and data-backed.
- Legacy duplicate KYRE AI VERDICT and FAST LINE LAB HTML cards are removed from the new presentation layer.
- Missing evidence is compact and explicit rather than occupying large empty cards.
- The native Line Lab still changes only threshold evaluation and does not fetch externally.
- Frozen `nba_pra_page2_v1.py`, `nba_pra_page2_core_v2.py`, and `nba_pra_page2_insights_v1.py` remain byte-identical to the current frozen baseline.
- Focused tests, existing NBA PRA Page 2 regressions, source guards, compile checks, protected-main Runless proof, and final freeze readback all pass before GREEN + FROZEN.