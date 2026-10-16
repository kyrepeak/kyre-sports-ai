# NBA Spread — Sharp Money Observations Step 3 V1

## Scope
Add a read-only sharp-money observation adapter that consumes the frozen Step-2 verified public-betting transport. This step does not redesign the page and does not feed sharp-money observations into model, projection, probability, ranking, or pick logic.

## Source ownership
- Schedule/matchup identity remains owned by the existing verified NBA schedule layer.
- Public-bet percentage, money percentage, and absolute tracked bet count remain owned by frozen Step 2.
- Step 3 derives sharp-money evidence only from those verified observations; it does not scrape a second provider copy or create page-wide source authority.

## Fail-closed rules
- Upstream Step-2 unavailable/provider failure: unavailable, never guessed.
- Event must match an eligible UPCOMING/DELAYED schedule matchup by exact away/home tricode pair.
- Absolute bet count must be a positive observed value.
- Away/home bet percentages and money percentages must each be 0–100 and each pair must sum to 100.
- A side is sharp only when verified money percentage minus verified public-bet percentage is positive.
- No arbitrary minimum sharp gap or volume threshold is introduced.
- Missing, contradictory, malformed, completed-game, or unmatched observations are unavailable.

## Decision isolation
- `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0`.
- No model, projection, probability, ranking, pick, or Page-1 visual mutation.

## Verification
- TDD RED proved the behavior contract before implementation.
- Focused Step-3 contract: 8 passed.
- Targeted NBA Spread regression: Step 2 + Step 3 + existing sharp-money selection contract, 21 passed.
- Repository-wide collection was environment-blocked by unrelated missing dependencies in the bare verification image and produced no Step-3 assertion regression.

## Proof contract
Exact-head Runless proof must compile the Step-3 adapter and run the Step-2 public-betting, Step-3 sharp-money, and existing sharp-money selection tests before protected merge. Final certification requires merged-main read-back plus canonical Finalization Ledger V2 freeze and Runless GREEN_FROZEN read-back.
