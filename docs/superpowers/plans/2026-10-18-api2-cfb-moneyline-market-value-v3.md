# API2 CFB Moneyline Market Value V3

## Goal
Upgrade the already-frozen CFB Moneyline Premium V2 presentation into a professional market-value decision page without changing certified model math.

## Scope
- Add Premium V3 presentation owner above frozen V2/model owners.
- Show model verdict, fair moneyline, human confidence, model health.
- Add price-aware BET VERDICT using verified sportsbook moneylines only.
- Prefer existing exact-provider FanDuel side-market infrastructure; fail closed to WAIT FOR PRICE when exact identity/price is unavailable.
- Keep sportsbook projection influence exactly 0.0%.
- Translate model components into human directional football reasons.
- Replace raw audit-style matchup hero with a compact logo/record/rank matchup snapshot.
- Add data freshness and keep deep evidence collapsed.
- Preserve universal CFB tap-only selectors and automatic next-slate behavior.
- Route only CFB / moneyline through Runtime V5 Loader V15; delegate all other routes to V14.

## Safety
- No edits to CFB Moneyline model/final/slate owners.
- No fabricated prices, books, probabilities, or edges.
- Market data is evaluated only after model completion.
- No second prediction engine.
