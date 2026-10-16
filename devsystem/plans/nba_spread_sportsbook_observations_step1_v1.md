# NBA Spread — Sportsbook Observations Step 1 V1

## Scope
Add a read-only sportsbook observation transport for the existing NBA Spread page. This step does not redesign the page and does not feed sportsbook data into model, projection, probability, or ranking logic.

## Source ownership
- Schedule/matchup identity remains owned by the frozen verified NBA schedule layer.
- Sportsbook spread observations are sourced from SportsGameOdds only for this transport.
- SportsGameOdds is not page-wide source authority.
- Downstream consensus remains responsible for requiring multiple independent books.

## Fail-closed rules
- No credential: unavailable, never guessed.
- Provider/network/payload failure: unavailable, never guessed.
- Event must match an eligible verified schedule matchup.
- A book is emitted only when exact away and home full-game spread observations both exist and are mathematical opposites.
- Partial or contradictory book pairs are discarded.

## Proof contract
Focused tests must prove normalization, rejection of invalid pairs, credential fail-closed behavior, NBA/full-game-spread request shape, and non-page-wide authority. Exact-head Runless proof is required before protected merge and GREEN + FROZEN certification.
