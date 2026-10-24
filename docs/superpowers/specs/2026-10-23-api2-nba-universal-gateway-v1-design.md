# API2 NBA Universal Gateway V1 — Design

## Intent
Make Kyre Sports API the only application-facing NBA data gateway so PRA is the first migrated market and every future NBA page can reuse the same NBA domain boundary instead of adding page-specific transports.

## Goals
- Register a first-class NBA domain in `kyre_sports_api_vercel_v1.py`.
- Move all currently application-facing NBA PRA routes off the Runless proof-service host and onto `https://kyre-sports-api.vercel.app`.
- Preserve the existing NBA PRA market, schedule, player-context, injury, and matchup contracts.
- Add an NBA domain status/capabilities route that declares the future market-router contract.
- Harden FanDuel PRA normalization so common Points + Rebounds + Assists market-name variants resolve to one canonical PRA market.
- Keep sportsbook observations at zero projection influence and never average sportsbook lines into a model projection.
- Keep Runless as proof/control plane only, never product transport.

## Non-goals
- Do not build UI pages for every future NBA market in this step.
- Do not invent sportsbook observations or fill missing numeric values with fabricated data.
- Do not delete historical Runless NBA modules in this step; compatibility code may remain, but application clients must no longer target it.
- Do not mutate NFL, CFB, WNBA, MLB, projections, rankings, or unrelated Streamlit routing.

## Global constraints
- Kyre Sports API is the ONLY application-facing NBA API/data gateway.
- Do NOT use SGO / SportsGameOdds.
- Do NOT use ESPN.
- Do NOT use ESPN BET.
- Frontend NBA code never calls an underlying provider directly.
- Field-first routing: use the strongest approved source for each field and use fallbacks only for missing, stale, conflicting, historical, or unhealthy primary data.
- No fabricated numbers. Legitimate absence becomes a semantic unavailable state.
- Runless owns testing/proof/freeze only.

## Architecture

```text
NBA frontend/pages
      |
      v
https://kyre-sports-api.vercel.app
      |
      v
/api/v1/nba/*
  |-- /status
  |-- /pra/market
  |-- /pra/schedule
  |-- /pra/player-context
  |-- /pra/injuries
  `-- /pra/matchup
      |
      v
NBA domain routing / normalization / provider health
      |
      v
approved official / sportsbook / history sources
```

Future NBA pages add market routers behind `/api/v1/nba/*`; they do not create a new application host.

## Existing route migration
The working NBA PRA business logic currently lives under the Runless package and the five application clients default to `https://kyre-runless-proof.vercel.app`. This step copies product-serving route implementations into `sports_api/api/`, registers them in the Kyre Sports API Vercel entrypoint, and changes the five application clients to default to the Kyre Sports API production host.

## NBA domain manifest
`GET /api/v1/nba/status` returns a stable manifest declaring:
- `application_gateway = KYRE_SPORTS_API`
- `runless_product_transport = false`
- `provider_direct_frontend = false`
- currently live PRA capabilities
- future market IDs that plug into the same domain (`points`, `rebounds`, `assists`, `threes`, `moneyline`, `spread`, `totals`, `player-combos`)
- banned provider policy (`SGO`, `ESPN`, `ESPN BET`)

The future market list is a capability contract, not a claim those endpoints already exist.

## FanDuel PRA normalization
The parser treats the following suffixes as the same canonical market, case-insensitively and with flexible whitespace:
- `Pts + Reb + Ast`
- `Pts + Rebs + Asts`
- `Points + Rebounds + Assists`

Alternative-line markets remain excluded from the standard PRA observation set. A zero-row result stays semantic `UNAVAILABLE`; it never becomes a fabricated line.

## Proof contract
Before merge, exact-head Runless proof must run compile + focused tests against the real `kyre_sports_api_vercel_v1:app` TestClient. After merge, the exact production deployment must be READY and production `/api/v1/nba/status` must return the Kyre gateway manifest. Production PRA status/market must be served from the Kyre Sports API host. Final Runless closeout must reach `GREEN_FROZEN`, then the scope lease is released.

## Approaches considered
1. **Patch PRA only.** Rejected because every future NBA page would recreate routing, provider health, and host ownership.
2. **Universal NBA domain in Kyre Sports API with PRA as first proof market.** Selected because it fixes current ownership once and creates the extension point for future NBA pages.
3. **Keep Runless as NBA transport and rename it logically.** Rejected because proof infrastructure must not be the application-serving data plane.
