# CFB Game Total Visual Redesign — V1 Contract

Status: STEP 1 TARGET LOCK
Base main SHA: `d38e5b098029f8c17ed308bdf4e841729e84fea8`
Production route owner chain:
- `app.py`
- `streamlit_memory_lazy_router_v169.py`
- `cfb_game_total_clean_page_v24.py`

## Scope lock

This contract governs **presentation only** for the College Football Game Total page.

Frozen / out of scope:
- projection math
- confidence math
- probability/model logic
- team-stat calculations
- market-line ownership
- event identity / exact ESPN ID protections
- data routing / normalization
- sportsbook projection influence (must remain exactly 0.0%)
- Steps 1–12 analytical ownership and completed cleanup behavior
- certified data, runtime, verifier, and production contracts unless a later visual step provides direct contradictory evidence

No provider/source hunting is authorized by this visual redesign while DATA remains GREEN.

## Target visual language

The approved target is the premium neon sports-dashboard concept shown for Purdue vs UCLA:
- deep navy / near-black background
- cyan/teal primary glow
- electric blue secondary glow
- purple edge accent
- Purdue warm gold/orange accent
- UCLA cool blue accent
- rounded glass cards
- subtle stadium/field texture only as low-contrast decoration
- clear large-number hierarchy
- compact icon-led labels
- small progress bars / sparklines used only as visual summaries of already-owned values
- polished tablet-first composition with desktop/mobile fallbacks

The redesign must feel more fun and premium without becoming noisy.

## Global visual tokens

### Geometry
- page section radius: 20–24 px
- metric-card radius: 14–18 px
- pill radius: 999 px
- major section gap: 18–22 px
- card gap: 12–16 px
- card inner padding: 18–24 px
- touch targets: minimum 44 px

### Borders / glow
- base border: 1 px low-opacity cyan/blue
- active/featured border: 1–2 px brighter cyan/green
- section glow: restrained outer glow, never enough to reduce text contrast
- Purdue card: gold/orange edge accent
- UCLA card: blue edge accent
- purple reserved for shell/outer-frame contrast and selected-state emphasis

### Typography hierarchy
1. section title
2. hero metric number
3. card label
4. supporting explanation
5. provenance / microcopy

Hero numbers must dominate. Provenance must never compete visually with the decision metrics.

## Page structure lock

The Game Total screen keeps this vertical order:

1. Matchup hero / game context
2. Optional section-tab navigation
3. **GAME TOTAL ANALYSIS**
4. **TEAM EVIDENCE**
5. Existing **GAME TOTAL EVIDENCE • STEPS 1–12**

Steps 1–12 remain below these summary surfaces and are not redesigned under this Step 1 contract.

## GAME TOTAL ANALYSIS target

Use a premium bento layout.

Required visible values/tiles when data exists:
- Projected Total
- Market Total
- Over / Under Lean
- Confidence
- Data Check Progress
- 5M Certified
- 0.0% sportsbook projection influence
- existing provenance/live-data strip

Visual behavior:
- Projected Total is a primary hero card with the largest number.
- Market Total is a secondary comparison card.
- Over / Under Lean is a primary decision card with directional momentum treatment.
- Confidence uses a circular or semicircular gauge sourced from the existing confidence value.
- Data Check uses a segmented progress strip sourced from the existing check count.
- Certification and sportsbook-influence cards remain clearly visible but visually secondary.
- Existing feed/event provenance remains present at the bottom of the section.

No visual element may manufacture, infer, or alter a value.

## TEAM EVIDENCE target

Use two balanced side-by-side team cards when width allows; stack them on narrow screens.

Each team card preserves:
- team logo
- team name
- record / conference where available
- PPG
- Allowed PPG
- Point Diff
- Recent Form

Visual upgrades allowed:
- micro bar charts derived only from the displayed metric
- sparkline/trend decorations derived only from already-owned trend/form data
- recent-form W/L chips
- small rank/supporting labels when already supplied by the current data contract
- central VS divider
- a matchup-edge badge only when an existing, explicit underlying field already owns that conclusion

Purdue uses warm gold/orange accenting.
UCLA uses cool blue accenting.

No fabricated rating, rank, edge, or trend may be introduced.

## Responsive lock

Tablet is the visual reference size.

Desktop:
- preserve wide bento layout and side-by-side Team Evidence cards.

Tablet:
- primary target; no clipped cards, no horizontal overflow for core sections.

Mobile:
- stack bento cards and team cards vertically.
- hero numbers remain readable.
- no card requires pinch zoom.
- Steps 1–12 retain their existing collapsible behavior.

## Accessibility / readability lock

- text contrast must remain readable against glass backgrounds
- status is never communicated by color alone
- numeric meaning remains available as text
- hover-only behavior is prohibited for essential information
- decorative glow must not obscure borders or labels

## Step 1 acceptance contract

Step 1 is GREEN when:
1. this contract exists on a branch created from certified main SHA `d38e5b098029f8c17ed308bdf4e841729e84fea8`;
2. production render owner is documented as `cfb_game_total_clean_page_v24.py` through Router V169;
3. target geometry, spacing, glow, typography, Game Total structure, Team Evidence structure, and responsive rules are frozen here;
4. frozen analytics/data/model behavior is explicitly excluded from the visual redesign;
5. targeted diff proof shows Step 1 changed only this contract file.

After these five criteria pass:
**STEP 1 = GREEN → FREEZE.**
