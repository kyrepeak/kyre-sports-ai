# NBA Spread Page 1 — S-Tier Analytics V2 Design

## Goal
Turn NBA Spread Page 1 into a decision-first analytics surface while preserving the frozen sportsbook-independent Step-9/Step-10 model and leaving Page 2 ownership unchanged.

## User-facing hierarchy
Page 1 answers, in seconds: what is the model verdict, what is the cover probability, where is the line value, what does the market consensus say, and is there enough verified evidence to open Page 2.

The card hierarchy is: matchup identity -> Kyre AI verdict / cover probability -> line value -> market consensus vs Kyre fair line -> sportsbook quote strip -> best available lines/prices -> line movement -> injury/status chips -> one View Full Analysis CTA.

## Market data contract
Primary market source: SportsGameOdds multi-book full-game spreads. Request major books including FanDuel, DraftKings, BetMGM, Caesars, Pinnacle, ESPN BET, Fanatics and Bet365, and request provider open/close fields.

Secondary market source: Odds-API.io. It is gap-fill only: a verified primary row for the same exact game+book cannot be overwritten by the fallback.

Credentialless final market fallback: ESPN public scoreboard sportsbook row, under the already frozen exact-side verification rules.

Per-book rows retain source provenance and freshness. Consensus uses verified fresh paired spreads only. Best-line selection favors the bettor-improving point spread first, then price. Open-to-current movement is labeled OPEN_TO_CURRENT only when actual opening spread evidence exists.

## Integrity boundaries
- `sportsbook_projection_influence = 0.0`
- no model/projection/probability/ranking formula changes
- no Step-9/Step-10 ownership changes
- no Page 2 redesign in this workstream
- no fabricated odds, probabilities, injuries or line movement
- unavailable optional market detail collapses or presents a truthful pending/unavailable state; it is never rendered as an unexplained blank

## Runtime approach
Use additive successors only: sportsbook observations V3, multi-source live repair V3, decision-board data V2, Page V9, runtime loader V25 and a new terminal NBA-spread-only runtime overlay. All non-NBA-spread routes delegate to the frozen prior runtime.

## Verification
TDD contract covers successor existence, major-book/open-line request policy, gap-fill precedence, market consensus/best-line/movement shaping, S-tier HTML hierarchy, model-boundary constants and runtime activation. Frozen Page 1/2 handoff, model/decision, injury/provider-resilience and universal navigation regressions must remain green. Final authority is exact-head `runless-final-gate` from GitHub App 5204253, followed by merged-main verification and freeze read-back.