# NBA PRA Page 2 Insights V1 — Design

## Intent
Add a substantial, professional `INSIGHTS` section to NBA PRA Page 2 so a user can understand *why* the selected PRA pick is attractive, neutral, or risky without leaving the player deep-dive page.

The feature is explanatory only. It does not create a new model, change the Kyre projection, alter probabilities, average sportsbook lines, or introduce a direct provider dependency.

## Placement
`INSIGHTS` appears immediately after `KYRE AI VERDICT` and before `FAST LINE LAB`.

That order keeps the page decision-first: the user sees the pick, then the evidence-backed explanation, then can experiment with alternate thresholds.

## Experience
Insights use a hybrid analyst-report structure. The section may be long when verified evidence exists, but it remains scannable through labeled subsections instead of one wall of text.

Eligible subsections:

1. **Recent Form** — verified recent PRA production, active-line hit rate, sample size, and recent minutes.
2. **Role & Usage** — verified usage %, within-team usage rank, usage sample, and minutes context.
3. **Matchup** — verified opponent PRA/PTS/REB/AST rankings and evidence period.
4. **Player vs Opponent** — exact-opponent verified history, average PRA, hit/miss record at the active line, and latest meeting when available.
5. **Market & Model Edge** — exact sportsbook, current/selected line, Kyre projection, edge, probability, and line-movement context.
6. **Availability & Risk** — verified player availability plus existing Page 2 risk flags.
7. **Game Situation** — home/away identity derived only from the verified scheduled game. No home/away performance claim is made unless such a split is actually supplied.
8. **Kyre Final Insight** — a multi-sentence analyst conclusion assembled only from evidence already present in the sections above.

Sections with no verified evidence are omitted rather than padded with generic filler.

## Data and truth rules
- Kyre Sports API remains the only application-facing gateway.
- Insights consume the already-loaded Page 2 `context`, `model`, `line_result`, and `matchup` objects.
- Insights make **zero external/provider calls**.
- No SGO / SportsGameOdds.
- No ESPN / ESPN BET.
- No sportsbook line averaging.
- No fabricated numbers, trends, injuries, pace claims, role changes, teammate impacts, or home/away performance splits.
- Sportsbook and opponent evidence remain explanatory context only; sportsbook projection influence stays exactly `0.0`.
- When the active Line Lab threshold changes, threshold-dependent insight text may change locally, but the frozen projection does not.

## Architecture
Create `nba_pra_page2_insights_v1.py` as a pure deterministic evidence-composition module. It receives already-normalized Page 2 objects and returns structured insight sections plus the final analyst conclusion. It imports no network client and performs no I/O.

`nba_pra_page2_v1.py` remains the presentation owner. It renders the structured result as an `INSIGHTS` panel using the existing black/glacier-blue Page 2 visual language.

This separation protects frozen Page 2 provider/model ownership and makes the insight logic directly unit-testable.

## Failure behavior
- Missing optional evidence omits that evidence or subsection.
- Missing probability never creates a fake probability statement.
- Missing matchup history never creates a history claim.
- Missing usage never estimates usage.
- `PASS`/insufficient-separation states produce a cautious final insight rather than forcing an Over/Under recommendation.
- Existing Page 2 rendering must continue even if only a small subset of insight evidence is available.

## Acceptance
The feature is complete when:
- Page 2 visibly contains `INSIGHTS` and `KYRE FINAL INSIGHT` in the locked location.
- Rich fixtures produce multiple detailed evidence sections with exact numeric support.
- Sparse fixtures do not invent unavailable facts.
- Line Lab remains provider-free on slider interaction.
- Existing NBA PRA Page 1/Page 2 sync, handoff, S-tier, source-policy, model, and routing regressions remain green.
- Exact-head proof, expected-head merge, production deployment, stable-alias parity, live health, and frozen-state closeout all succeed on the authoritative API 2 path.
