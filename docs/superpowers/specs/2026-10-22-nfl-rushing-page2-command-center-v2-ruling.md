# Page 2 Command Center V2 Ruling

The approved decision-first Page 2 design is implemented with a dedicated **Kyre Sports API** detail endpoint at `/api/v1/nfl/rushing-yards/detail`.

This is a field-efficiency refinement of the design, not a user-facing scope change:

- Page 1 remains the frozen lightweight league-wide RB Market Board.
- Page 2 still receives one normalized canonical Kyre Sports result.
- Advanced play-by-play derivations run only after a canonical player/game is opened.
- The frontend does not call any underlying provider.
- The existing slate schema is unchanged.
- Missing advanced/provider-only inputs remain semantic verification states.

This avoids computing deep analytics for every RB1/RB2 card when only one selected player's Page 2 needs them.