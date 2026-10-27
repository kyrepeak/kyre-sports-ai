# MONSTER NBA PRA Page 2 S-Tier V4 Design

## Intent
Turn NBA PRA Page 2 into a compact, decision-first player betting terminal that feels premium on mobile while preserving all verified Page 2 data/model behavior.

## Hard isolation
- Authority: MONSTER ONLY.
- Source baseline: protected `main` at `75aef81d6141c3baf16cbf8a19ef760b4640d51d`.
- Do not import, inspect, mutate, or use API 2 branches, PRs, runs, leases, state, GREEN/FROZEN claims, or proof artifacts as MONSTER evidence.
- Kyre Sports API remains the only application-facing data gateway.
- No SGO, ESPN, or ESPN BET.
- No provider I/O or projection math is added to the presentation successor.
- No fabricated line, odds, role, injury, usage, matchup, or history data.

## Chosen approach
Create a new presentation successor `nba_pra_page2_command_center_v4.py`. It consumes the same normalized context/model/result/matchup mappings and the same verified-history completeness owner already used by live Page 2. Activate V4 only in `nba_pra_page2_sync_v1.py`.

## Page hierarchy
1. Player Command Center
2. Compact Kyre Decision strip
3. L10 PRA trend vs active threshold
4. Projection distribution / model range visual
5. Market Intelligence
6. Recent Form + PRA composition
7. Matchup Intelligence
8. Role & Availability
9. Model Drivers
10. Why It Works / What Could Break It
11. Compact Kyre Read / Final Insight
12. Full Game Log

Deep evidence after the primary decision surface may be collapsible, but verified content must remain accessible.

## Player Command Center
- Larger player portrait when verified.
- Team identity and opponent identity are visually balanced.
- Compact matchup line.
- Human-readable status (`ACTIVE` when an official report was checked and there is no designation; otherwise the verified status text).
- Evidence coverage meter.
- Recent minutes and PRA matchup rank where verified.
- Team watermark may use only an already-verified logo URL.
- Decision is visually integrated with the command center without duplicating a second large decision card.

## Decision strip
Display only verified/frozen model values already supplied to the renderer: side + active line, projection, probability, edge, Kyre score. Missing values render as semantic dashes, never invented replacements.

## L10 trend
Use up to ten verified games. Render PRA values as an inline SVG/polyline/dots with a horizontal active-line threshold. Over/under styling is display-only. No new data source or model calculation.

## Projection distribution
Visualize the existing projection and sigma as the model center and ±1 sigma range, plus active threshold. No distribution is invented when projection or sigma is missing.

## Market Intelligence
- Show all verified independent sportsbook quotes supplied in context.
- Surface best verified Over/Under price where comparable.
- Surface line spread/consensus only when the verified quotes support it.
- Never average conflicting books into a projection.
- Preserve semantic no-movement state when same-book history is unavailable.

## Role & Availability
- Prefer verified usage %, usage rank, and source/period.
- Show recent verified minutes as opportunity context.
- Keep official player availability and teammate availability evidence.
- Never translate an unverified status into ACTIVE.

## Model Drivers
Display directional, evidence-backed labels derived only from supplied verified fields: recent form, minutes, matchup, role/usage, availability. Missing evidence becomes `NOT VERIFIED`, not a guessed direction.

## Insights
Replace repeated long-form evidence with a compact `KYRE READ`: primary edge, primary caution, and a concise evidence-backed bottom line. Detailed evidence cards remain accessible in a collapsible section and remain unchanged in meaning.

## Full Game Log
Desktop may use a table. Mobile must use stacked cards to avoid horizontal clipping. Each verified game shows date, opponent, minutes, PRA and threshold result when those values exist.

## Non-goals
- No changes to projection formulas, probabilities, grades, provider routing, player-context API, history collection, or matchup API.
- No direct sportsbook/provider calls from the UI.
- No changes to NBA PRA Page 1.
- No changes to WNBA/NFL/CFB pages.
