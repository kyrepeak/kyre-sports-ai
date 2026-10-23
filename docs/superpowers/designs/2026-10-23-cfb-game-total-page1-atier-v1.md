# CFB Game Total Page 1 A-Tier V1 Design

## Intent
Keep Page 1 fast, simple, professional, and analytical. It is a decision board, not a full research terminal. Page 2 remains the deep-analysis owner.

## User-visible hierarchy
1. Game identity + kickoff + verified market state.
2. Market total.
3. Over and Under prices.
4. Safe no-vig probabilities derived only from the selected verified quote.
5. One concise Market Read (Over lean / Under lean / Balanced / semantic empty state).
6. Source freshness/integrity line.
7. Same-tab Open Analysis handoff to Page 2.

## What is removed from Page 1
- Away spread
- Home spread
- Moneyline
- Expanded per-book rows
- Record-unavailable clutter

Those inputs may still exist behind Kyre Sports API and/or Page 2, but they are not primary Game Total Page 1 presentation.

## Data and routing constraints
- KYRE SPORTS API is the only application-facing gateway.
- Frontend does not import or call any external provider.
- No SGO, ESPN, or ESPN BET may appear in the Page 1 request path.
- Existing `/api/v1/cfb/game-total/page1` payload remains the source for schedule + sportsbook-specific quotes.
- Do not average conflicting lines.
- Do not convert null to zero.
- Missing market data uses semantic copy, not blank/N/A/null.
- No legacy Game Total projection model is pulled into Page 1 because its historical model-input ancestry contains an ESPN-era dependency marker. Deep model analysis remains Page 2 until an approved no-ESPN projection path is available through Kyre Sports API.

## Safe analytics
American prices may be transformed into implied probabilities and normalized to no-vig probabilities only when both Over and Under prices are valid. This is deterministic math from verified quote inputs; it is not a Kyre model projection and must be labeled as market probability/read.

Market Read rules:
- Both no-vig sides available and difference < 2 percentage points: BALANCED MARKET.
- Over exceeds Under by >= 2 points: OVER MARKET LEAN.
- Under exceeds Over by >= 2 points: UNDER MARKET LEAN.
- Quote/price missing: semantic market state, never guessed.

## Approaches considered
1. **Recommended: Market-first A-tier board.** Uses existing Kyre Sports API payload + safe no-vig derivation. Fastest and fully compliant with no-ESPN rule.
2. Pull legacy Page 2 model projection onto Page 1. Rejected because the older model-input ancestry is not clean under the new absolute no-ESPN rule.
3. Add a brand-new approved no-ESPN projection service in this same step. Rejected as too broad for a Page 1 cleanup and would mix data-platform/model work with presentation work.

## Non-goals
- No Page 2 redesign.
- No projection/model/probability/ranking mutation.
- No provider expansion in this step.
- No historical opener/current-line model changes.

## Success
Page 1 scans quickly on mobile/tablet, contains no irrelevant spread/moneyline boxes, shows meaningful semantic states, preserves sportsbook-specific lines, and keeps deep analysis one tap away.
