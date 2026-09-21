# Scroll mechanics

A catalogue of mechanics that are worth building, each with the job it does, the cost it charges in
scroll distance, and how to build it with the scaffold engine. Read it while writing the scroll
score (Phase 2), because "which mechanic" and "what claim" are the same decision.

Contents:

1. [The engine API](#the-engine-api)
2. [Pinned scene with internal progress](#1-pinned-scene-with-internal-progress)
3. [Bound counter](#2-bound-counter)
4. [Horizontal rail](#3-horizontal-rail)
5. [Focus band](#4-focus-band)
6. [Progressive accumulation](#5-progressive-accumulation)
7. [Text as material](#6-text-as-material)
8. [Field inversion](#7-field-inversion)
9. [Depth layering](#8-depth-layering)
10. [Scrubbed sequence](#9-scrubbed-sequence)
11. [Reveal on enter](#10-reveal-on-enter)
12. [Velocity response](#11-velocity-response)
13. [Choosing and combining](#choosing-and-combining)

## The engine API

`assets/scaffold/scroll.js` exposes four primitives and three helpers. Everything below is built
from them.

```js
const { pin, track, reveal, onProgress, clamp, lerp, mapRange } = Scrollcraft;

pin(el, p => { ... });     // el is a tall section; p goes 0→1 over (el.height - viewport)
track(el, p => { ... });   // p goes 0→1 as el crosses the viewport (enter bottom → exit top)
track(el, fn, { startAtRest: true });   // rebase so the element's p at page load counts as 0
reveal(el);                // adds .is-in once, when el is ~25% into view
onProgress(p => { ... });  // whole-document progress, for a page-level indicator
```

All callbacks run in one batched `requestAnimationFrame` pass, once on load, on every scroll, and on
resize. Two habits keep a page of scenes honest:

- **An element already on screen at load is part-way through its crossing**, so a plain `track()`
  hands it p ≈ 0.4 before the reader has touched anything, and its animation starts half-finished.
  `{ startAtRest: true }` rebases that resting value to 0. Every hero needs it.
- **Anything several scenes write to needs a single writer.** A shared readout, a shared CSS
  variable, a shared class: every registered scene runs on every frame, including the ones far
  off screen, so the last one registered silently wins. Either guard the write (`if (p > 0 && p <
  1)`) or keep the scenes' values in one object and let one function apply them. Under `prefers-reduced-motion` each callback is invoked exactly once with its **end** value,
so a scene composes itself into its final state and nothing moves.

## 1. Pinned scene with internal progress

**Job:** hold one idea still while the reader drives it — a map filling, a product rotating, a
before/after wipe, a diagram assembling. This is the workhorse of the genre and the mechanic most
responsible for a page feeling premium.

**Cost:** 150–250vh for one idea. This is the dial that controls perceived speed: if the reader says
it goes too fast, add height here. Slowing the easing does nothing, because progress is bound to
scroll, not to time.

```html
<section class="scene" data-scene="reach" style="--scene-length: 200vh">
  <div class="scene__stage">
    <!-- everything the reader sees, viewport-sized -->
  </div>
</section>
```

```css
.scene { height: var(--scene-length, 200vh); position: relative; }
.scene__stage { position: sticky; top: 0; height: 100vh; overflow: hidden; }
```

```js
pin(document.querySelector('[data-scene="reach"]'), p => {
  arcs.style.setProperty('--fill', p);            // 0 → 1
  counter.textContent = Math.round(lerp(0, 12400, p)).toLocaleString();
});
```

Keep the stage exactly `100vh` and `overflow: hidden`, or a child that animates outward will create
horizontal scroll on phones — the single most common defect this pattern produces.

On phones the stage usually stops being sticky, and then the section is no longer taller than the
viewport, so `pin()` can never advance and the scene sits frozen at its start value — a counter
stuck on 0, a log with no lines. Bind the same callback through `track()` there instead, so the
scene still plays as the section passes:

```js
const phone = matchMedia('(max-width: 767px)').matches;
const bind = phone ? track : pin;
bind(scene, p => { ... });     // same callback, different source of progress
```

## 2. Bound counter

**Job:** make a number feel earned. A counter that animates once on entry is a trigger and reads as
a widget; one bound to scroll makes the reader feel they caused the growth, and it runs backwards.

Use `font-variant-numeric: tabular-nums` so digits stop jittering, and round sensibly — a counter
landing on 12,437 reads as real where one landing on 12,400 reads as marketing. Give the final value
a small held moment by finishing the count at p ≈ 0.85, so the reader sees the result rather than
the digits changing right up to the scene exit:

```js
pin(scene, p => {
  const c = clamp(mapRange(p, 0, 0.85, 0, 1), 0, 1);
  out.textContent = Math.round(lerp(0, 12437, c)).toLocaleString();
});
```

## 3. Horizontal rail

**Job:** a collection with a natural order — exhibits, a timeline, case studies, product variants.
It buys a genuine change of axis, which is why it feels like a different kind of page.

**Cost:** roughly 100vh per card.

```js
pin(rail, p => {
  const travel = track.scrollWidth - window.innerWidth;
  track.style.transform = `translate3d(${-p * travel}px,0,0)`;
});
```

On phones, drop the pin and let the rail be a real `overflow-x: auto; scroll-snap-type: x mandatory`
strip — thumbs already know how to do that, and a hijacked horizontal pin on a small screen fights
the gesture. Give the rail an obvious edge cue (a partially visible next card) so nobody misses that
it continues.

## 4. Focus band

**Job:** one thing at a time from a set, with the reader choosing which. Cards recede — lower
opacity, slight scale down, less saturation — except the one crossing a focal band across the middle
of the viewport.

```js
cards.forEach(card => track(card, p => {
  const focus = 1 - Math.abs(p - 0.5) * 2;        // 1 at centre, 0 at edges
  card.style.setProperty('--focus', clamp(focus, 0, 1).toFixed(3));
}));
```

```css
.card { opacity: calc(0.35 + 0.65 * var(--focus, 0));
        transform: scale(calc(0.96 + 0.04 * var(--focus, 0))); }
```

Keep the receded state legible — around 0.35 opacity, not 0.05. A card the reader cannot read is a
card they will not scroll back for, and text that is invisible at rest is also the thing the
verification pass will flag.

## 5. Progressive accumulation

**Job:** the page proving itself as it goes — sources unlocking, a checklist filling, a counter in
the margin climbing. This is an excellent signature move because it is a *mechanism* rather than an
effect: it makes the page's rigour visible.

Mark each claim with the source it depends on, keep a persistent rail or margin counter, and
increment as each claim passes the focal line. It works because it gives the reader a reason to
continue that is about substance rather than curiosity.

```js
claims.forEach((el, i) => reveal(el, { onEnter: () => unlock(i) }));
```

Only promise it if every claim really has a source. A "0 of 9 sourced" counter on a page with
invented numbers is worse than no counter at all.

## 6. Text as material

**Job:** make a sentence land instead of appear. Word-by-word or line-by-line reveal bound to
progress, so the reader paces the sentence themselves.

```js
pin(scene, p => {
  words.forEach((w, i) => {
    const local = clamp(mapRange(p, i / words.length * 0.8, (i + 1) / words.length * 0.8, 0, 1), 0, 1);
    w.style.opacity = 0.15 + 0.85 * local;
  });
});
```

Reserve it for one sentence per page — the thesis, usually. Two or three of these and the page feels
like it is withholding information from the reader on purpose.

A typewriter variant (revealing characters) suits a single short line and a technical or documentary
register; it gets tedious past about eight words. Either way the full text must be in the DOM, with
only presentation animated, so search and screen readers see the sentence.

## 7. Field inversion

**Job:** punctuation. Flipping from light to dark at a boundary, bound to progress so the transition
happens under the reader's hand, marks a change of chapter more strongly than any heading.

```js
track(boundary, p => {
  document.documentElement.style.setProperty('--field', clamp(mapRange(p, 0.35, 0.65, 0, 1), 0, 1));
});
```

Drive the tokens from `--field` (`--paper`, `--ink` interpolating between the two schemes) so every
element inverts together. Use it two or three times on a page at most: a page that strobes between
schemes at every section reads as indecisive, and check contrast in both states.

## 8. Depth layering

**Job:** a background that is a place rather than a colour. Two or three layers moving at different
rates, with the smallest offsets you can get away with.

```js
track(scene, p => {
  bg.style.transform   = `translate3d(0,${p * -40}px,0)`;
  mid.style.transform  = `translate3d(0,${p * -80}px,0)`;
});
```

Offsets above about 120px over a full scene start reading as sliding panels instead of depth, and
large parallax is the most reliable way to make a page feel cheap. Never parallax body text — text
that drifts relative to its container is genuinely hard to read.

## 9. Scrubbed sequence

**Job:** one hero moment where a real object moves — a product turning, a device assembling, a
camera push. Highest impact per scene and by far the highest cost.

Prefer a video element with `preload="auto"`, `muted`, `playsinline` and paused playback, seeking
`currentTime` from progress:

```js
pin(scene, p => { if (v.readyState >= 2) v.currentTime = p * v.duration; });
```

Frame sequences (`frame-0001.webp` …) scrub more reliably across browsers but cost a lot of bytes;
if you go that way, keep it under ~60 frames, size them to the display size, and decode ahead of the
playhead. Either way: ship a static poster frame as the fallback, because on a slow connection the
scene must still make its point, and check the phone case specifically — a 4K scrub on cellular is a
blank scene for the first ten seconds.

## 10. Reveal on enter

**Job:** the ordinary case. Content arriving as the reader reaches it, so a long page does not
present as a wall.

It is a trigger, not a binding, and that is fine — but it is also the mechanic that, used alone,
produces exactly the generic page this skill exists to avoid. Two rules keep it honest: vary the
treatment by content type (a stat block does not enter like a paragraph), and stagger siblings by
40–60ms rather than animating a group as one slab. Never use it as the only mechanic on a page.

```css
.reveal { opacity: 0; transform: translate3d(0, 16px, 0);
          transition: opacity .5s var(--ease), transform .5s var(--ease); }
.reveal.is-in { opacity: 1; transform: none; }
@media (prefers-reduced-motion: reduce) { .reveal { opacity: 1; transform: none; transition: none; } }
```

## 11. Velocity response

**Job:** a small, cheap sense of physicality — a marquee that speeds up with scroll velocity, or
type that skews a degree under fast scrolling and settles when the reader stops.

```js
let last = 0, vel = 0;
onProgress(() => {
  const y = window.scrollY;
  vel = lerp(vel, (y - last), 0.2); last = y;
  marquee.style.setProperty('--speed', 1 + Math.min(Math.abs(vel) / 40, 2));
});
```

Keep it barely perceptible. Velocity effects are the easiest thing on this list to overdo, and
overdone they read as a glitch rather than a flourish.

## Choosing and combining

- **Two or three mechanics carry a whole page.** Repetition with variation reads as a system; nine
  different tricks read as a demo reel.
- **Never the same mechanic twice in a row.** Alternate axis, field, or register between neighbours.
- **One change per scene.** If two things must move together, they should be the same idea seen two
  ways (a counter and the map it describes), not two ideas.
- **Spend the budget unevenly.** The signature scene deserves 250vh; a transitional beat deserves
  60. Uniform scene lengths are why a page can feel monotonous even when every scene is good.
- **The hero needs exactly one bound element.** Not a full scrubbed scene — the reader has not agreed
  to care yet — but not a static poster either. One thing responding to the first flick of the wheel
  is what tells them the page will reward scrolling.
