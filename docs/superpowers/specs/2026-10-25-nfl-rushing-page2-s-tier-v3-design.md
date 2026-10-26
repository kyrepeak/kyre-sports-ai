# NFL Rushing Yards Page 2 S-Tier V3 Design

## Intent
Transform the existing NFL Rushing Yards Page 2 command center from a long metric report into a premium mobile-first analyst cockpit. Preserve the verified Kyre Sports API data contract, the frozen rushing-market reliability layer, and all projection math. This is an additive presentation successor, not a model or provider rewrite.

## Goals
- Make the first screen answer: who is the player, what is the verified market, what does Kyre project, what is the edge/probability, and why.
- Add a compact sticky section navigation and a strong visual hierarchy.
- Add Decision Cockpit, Kyre Insights, Market Lab, Recent Performance chart, Hit Rate Matrix, Workload & Role, Opponent Run Defense summary, Trench/Personnel context, Game Environment, Availability & Personnel, Matchup + Comparable History, Advanced Efficiency, Full Game Log, Final Kyre Read, and collapsed Data & Sources.
- Use only fields already delivered through the Kyre Sports API Page 2 detail gateway or deterministic derivatives of those fields.
- When a field is unverified, show a compact truthful semantic state rather than a large empty card or fabricated value.
- Remove visual duplication: advanced-efficiency should focus on player efficiency; workload metrics should live in Workload & Role; sources should collapse into one disclosure row.
- On mobile, never truncate important semantic values such as Pending verification, Market not posted, or Personnel verification pending.

## Non-Goals
- No change to Kyre projection formulas, model weights, sportsbook influence, Page 1 ranking, provider selection, or canonical player identity.
- No direct frontend provider calls.
- No ESPN, ESPN BET, or SGO.
- No fabricated trench grade, injury designation, weather, line movement, spread, total, or matchup history.

## Layout
1. Player + matchup hero with compact tabs/anchor rail.
2. Decision Cockpit: Kyre Lean, verified line, projection, edge, probability, expected load.
3. Kyre Insights: up to three evidence-backed reasons/risks derived from verified detail payload.
4. Market Lab: current line, book-specific over/under, opening line, movement state; no averaging conflicting books.
5. Recent Performance: recent-game vertical bars against current line plus L5/L10/season/away/opponent/comparable hit-rate matrix when sample exists.
6. Workload & Role: season/L3/L5 attempts, rush share, red-zone, goal-line, fourth-quarter, lead/trail and trend.
7. Opponent Run Defense: one visual grade/score plus allowed-yard, YPC, explosive, stuff, success and EPA context.
8. Trench & Personnel: only verified personnel context; if no verified OL/front grade exists, show a compact verification state instead of inventing one.
9. Game Environment: spread, total, game state and weather/venue semantics when verified.
10. Availability & Personnel: player availability and relevant verified personnel context.
11. Matchup + Comparable History: dated exact-opponent rows first, comparable-defense sample second.
12. Advanced Efficiency: player-only explosive rate, stuff rate, success rate and rush EPA/attempt; no repeated workload cards.
13. Full Game Log: compact horizontally scrollable table.
14. Final Kyre Read: lean, confidence/evidence quality, probability, why, risks, bottom line.
15. Collapsed Data & Sources disclosure.

## Visual System
- Preserve black/navy + glacier-blue API2 visual language.
- Stronger section hierarchy; fewer giant empty cards.
- 12–18px card radii, subtle borders, restrained glow only around decision surfaces.
- Responsive two-column metric grids on mobile with values allowed to wrap.
- Floating top control must not cover content; make it smaller and offset from cards.

## Architecture
- Create `nfl_rushing_yards_professional_v3.py` as the presentation successor.
- Keep `nfl_rushing_yards_professional_v2.py` byte-preserved.
- Update only `nfl_rushing_yards_professional_v1.py` compatibility owner to import V3 while retaining the hidden legacy section index.
- Reuse `load_rushing_yards_detail()` and existing Kyre Sports API detail schema.
- Add pure renderer helpers in V3 for performance bars, hit rates, insights, compact semantic states, and source disclosure.

## Acceptance
- V3 renders every named S-tier section without direct provider dependencies.
- Verified market values flow through to Decision Cockpit, Market Lab, hit-rate calculations and Final Kyre Read.
- No verified line means no fake probability/edge/hit rate; semantic pending states remain truthful.
- Recent chart uses verified game rows and the current verified line only.
- Source lineage is collapsed by default.
- Important values wrap instead of ellipsizing on mobile.
- V1 activates V3; V2 remains preserved.
- Existing NFL rushing Page 1 and market-reliability tests remain green.
