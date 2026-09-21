# Verification

A scroll page cannot be verified by reading its source. Progress-bound scenes fail in ways that look
perfectly correct in code — a scene whose spacer is shorter than its stage, a transform that lands
one pixel outside the viewport, a reveal that never fires because its observer root is wrong. So
look at the page before handing it over.

## Running it

```bash
python skills/scrollcraft/scripts/scrollshot.py http://localhost:8000 --out .scrollcraft/shots
# a local file works too:
python skills/scrollcraft/scripts/scrollshot.py ./index.html --out .scrollcraft/shots
```

Useful flags: `--frames N` (default 12), `--viewports desktop,phone`, `--skip-reload`,
`--skip-reduced-motion`, `--json report.json`.

It needs Playwright (`pip install playwright`; the browser is usually already provisioned — check
`PLAYWRIGHT_BROWSERS_PATH` before downloading anything). Serve the page over HTTP if it loads modules
or media; `python -m http.server` is enough.

What it does, and why each check exists:

| Pass | Catches |
|---|---|
| Frame walk at even scroll fractions, per viewport | scenes that never change, dead space, overlap, clipped type |
| Invisible-element audit at every frame | content stuck at opacity 0 — the most common silent failure |
| Horizontal overflow check | stage children escaping, oversized display type on phones |
| Dead-link check | `href="#"`, empty and `javascript:void(0)` destinations |
| Mid-scroll reload | state that only updates in a scroll handler, so a reload leaves the page blank |
| Reduced-motion pass | a composed page, or an empty one |
| Console and network errors | missing assets, thrown exceptions mid-scene |

The script reports mechanical breakage. It cannot tell you the page is boring.

## Then actually look at the frames

Read them in order, as a reader would, and ask:

- **Does every frame change?** Two consecutive identical frames mean scroll distance is being spent on
  nothing. Either the scene is too long or its mechanic is not bound to progress.
- **Does each frame make one point?** If you cannot say what a frame is about, the scene is doing two
  things at once.
- **Is anything clipped or colliding?** Descenders cut off, a heading over a busy part of an image,
  a counter overlapping a caption at some intermediate progress value. Intermediate states are where
  collisions hide, which is why frames beat endpoints.
- **Do the phone frames hold up?** Display type that fits at 1440px routinely overflows at 390px.
- **Is the rhythm there?** Flip through quickly: you should see contrast in density and field, not
  twelve versions of the same grey page.
- **Is the first frame at rest?** Anything bound to scroll must sit at its start value before the
  reader scrolls. A hero whose animation is already half-played on load reads as a glitch, and the
  frame walk shows it immediately.
- **Does the first frame earn the second?** If nothing in the first screen suggests scrolling will
  reward you, that is the highest-value fix on the page.

## Common failures and what they mean

| Symptom | Cause | Fix |
|---|---|---|
| Content invisible after reload | scene state set only inside a scroll handler | run one update pass on load (the scaffold engine does) |
| A scene never advances | spacer height ≤ stage height, so progress is always 0 | give the section real `--scene-length` above 100vh |
| Scene jumps at its start | progress computed from the wrong reference point | measure against the section's own top, not the document's |
| Horizontal scrollbar on phone | a stage child transforms outward | `overflow: hidden` on the stage; check transform extremes, not just the ends |
| Janky scrub | animating layout properties, or reading geometry per frame | transform/opacity only; cache geometry, recompute on resize |
| Reduced-motion page empty | reveals rely on a class the observer never adds | final state must be the reduced-motion default in CSS |
| Counter reads wrong at the end | progress never quite reaches 1 | clamp, and finish the count before p = 1 |
| A shared readout shows the wrong scene | every scene writes on every frame; the last registered wins | guard the write with an active test, or give the target one writer |
| A scene is frozen at its start value on phones | the stage stopped being sticky, so `pin()` has no length | bind the same callback through `track()` below the breakpoint |
| Video scene blank on first pass | scrubbing before `readyState >= 2` | guard on readiness, and ship a poster |
| Links reported as dead | a placeholder survived, or a script-only control was built as a link | wire the real destination; a control that only runs script is a `<button>` |

## Before handing over

Walk the page once yourself, at a normal scrolling speed, then again fast, then reload halfway, then
at phone width. Click every link and confirm it goes where the interview said it should. Re-run the
script after every revision round — fixing a scene very often breaks its neighbour, because scenes
share the scroll axis and moving one moves them all.
