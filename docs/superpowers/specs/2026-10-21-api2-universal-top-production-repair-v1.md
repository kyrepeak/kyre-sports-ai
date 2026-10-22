# API2 Universal TOP Production Repair V1

## Problem

Live mobile production evidence from `vault.streamlit.app` shows the universal `↑ TOP` control is absent even though Universal Page Experience V1 is present in the repository and its static tests pass.

## Root-cause finding

The existing TOP control is client-JavaScript-owned and visibility depends on runtime scroll-owner detection. The frozen tests only inspect generated JavaScript text; they do not prove that a real Streamlit/mobile browser renders a usable TOP control. The production screenshot is therefore a valid successor regression.

## Required behavior

- Every active KYRE SPORTS AI route renders exactly one fixed `↑ TOP` control through ordinary Streamlit HTML/Markdown, so the control remains visible and usable even if the JavaScript enhancement does not execute or detects the wrong scroll owner.
- The native control must require no keyboard, Streamlit rerun, or route change.
- Its default no-JavaScript action must return the browser document to the top.
- Existing JavaScript may enhance the same control with smooth scrolling, but JavaScript must not own visibility.
- Do not change sports models, projections, Kyre Sports API routing, sportsbook data, navigation destinations, or loader semantics in this repair.
- Preserve one universal implementation rather than adding sport-specific TOP buttons.

## Verification

A regression test must fail against the prior implementation because no native fixed TOP fallback exists, then pass only after the universal runtime emits the fixed no-JavaScript control. The existing Universal Page Experience regression suite must remain green.