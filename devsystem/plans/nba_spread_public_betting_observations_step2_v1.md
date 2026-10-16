# NBA Spread — Public Betting Observations Step 2 V1

## Scope
Add a read-only public betting observation transport for the existing NBA Spread page. This step does not redesign the page and does not feed public betting data into model, projection, probability, ranking, or pick logic.

## Source ownership
- Schedule/matchup identity remains owned by the frozen verified NBA schedule layer.
- Public bet percentage, money percentage, and absolute tracked bet count are sourced from Action Network only for this transport.
- Action Network is not page-wide source authority.
- SportsGameOdds Step 1 remains frozen and unchanged.

## Fail-closed rules
- Provider/network/HTML failure: unavailable, never guessed.
- Event must match an eligible verified upcoming/delayed schedule matchup by exact away/home tricode pair.
- Absolute bet count must be a positive observed value; percentages are never substituted for volume.
- Away/home bet percentages must each be 0–100 and sum to 100.
- Away/home money percentages must each be 0–100 and sum to 100.
- Missing, contradictory, malformed, completed-game, or unmatched observations are discarded.

## Decision isolation
- `SPORTSBOOK_PROJECTION_INFLUENCE = 0.0`.
- No model, projection, probability, ranking, or Page-1 visual mutation.

## Proof contract
TDD must prove exact schedule filtering, positive absolute volume, percentage-pair validation, provider failure fail-closed behavior, non-page-wide authority, and zero decision-layer influence. Exact-head Runless proof is required before protected merge and GREEN + FROZEN certification.
