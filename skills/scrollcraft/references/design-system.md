# Design decisions

Scroll mechanics are half the page; the other half is whether it looks like someone with taste made
it. Read this before writing CSS.

Contents: [Anti-slop](#the-anti-slop-list) · [Type](#type) · [Space](#space) ·
[Colour](#colour) · [Motion](#motion) · [Media](#media) · [Copy](#copy) ·
[Performance](#performance) · [Accessibility](#accessibility) · [Mobile](#mobile)

## The anti-slop list

These are the specific tells that make a reader think "AI made this" within two seconds. They are
tells because they are what you get by default when nobody made a decision — so the fix is always to
decide something.

- **Everything centred.** Centred hero, centred headings, centred three-column cards, centred CTA.
  Real editorial design uses asymmetry: a headline pinned left against a wide right margin, a stat in
  the gutter, an image bleeding off one edge. Centre things for a reason, not by default.
- **Three equal cards with icons.** The "Fast / Secure / Scalable" row. If you have three things to
  say, they are almost never equally important — size them by weight, or make them a rail, a list,
  or a single well-argued claim.
- **Emoji as icons.** 🚀 ⚡ ✨ in production UI reads as a placeholder nobody replaced. Use a real
  icon set, simple inline SVG, numerals, or nothing.
- **The purple-blue gradient.** Also its cousins: glassmorphism everywhere, `backdrop-filter` on
  every card, a glow behind every heading. One of these as a considered choice is fine; the stack of
  them is the house style of generated pages.
- **Uniform 100vh sections.** Every section exactly one viewport, stacked. Real pages have sections
  of wildly different heights because their content has different weight.
- **One type size for everything.** A 48px heading and 16px body with nothing between, and no weight
  or width contrast. Flatness is what "bland" usually means.
- **The same fade-up on every element.** One transition applied to forty elements. Vary treatment by
  content type, and bind the important ones to scroll instead.
- **Fabricated proof.** Invented logo rows, made-up testimonials with generated headshots, round
  numbers nobody sourced. Beyond dishonest, it is *recognisable* — readers have learned to discount
  a page the moment they suspect it.
- **Generic copy.** "Empower your workflow", "Elevate your brand", "Welcome to the future of…".
  Specifics are always more persuasive than superlatives: a date, a number, a name, a quote.
- **Dead ends.** `href="#"`, buttons that do nothing, a footer with placeholder links. Every
  destination should be real, and if one does not exist yet, say so instead of faking it.

## Type

Two families at most: one for display, one for text — or a single family with genuine weight and
width range. Contrast between them should be obvious (a high-contrast serif against a plain grotesk,
say); two similar sans fonts just look like a mistake.

Build a scale with real jumps. `clamp()` for the display sizes so the hero survives phone-to-desktop:

```css
--step--1: clamp(.83rem, .8rem + .15vw, .9rem);
--step-0:  clamp(1rem, .96rem + .2vw, 1.1rem);     /* body: 16–19px */
--step-1:  clamp(1.3rem, 1.2rem + .5vw, 1.6rem);
--step-2:  clamp(1.8rem, 1.5rem + 1.4vw, 2.6rem);
--step-3:  clamp(2.6rem, 1.9rem + 3.4vw, 4.4rem);
--step-4:  clamp(3.4rem, 1.8rem + 7vw, 8rem);      /* display: one per page */
```

Line height inverts with size: 1.05–1.15 for display, 1.5–1.6 for body. Measure of 60–75 characters
(`max-width: 34ch` for lead paragraphs, `68ch` for body) — full-width text across a 1600px viewport
is unreadable and instantly marks a page as untended. Tighten letter-spacing slightly on large
display type (`-0.02em`) and never on small text. `font-variant-numeric: tabular-nums` on anything
that counts.

## Space

One spacing scale, used consistently:

```css
--s-1: .5rem; --s-2: 1rem; --s-3: 1.5rem; --s-4: 2.5rem;
--s-5: 4rem;  --s-6: 6.5rem; --s-7: 10rem;
```

Section padding belongs at the top of that range — `--s-6` or `--s-7` vertically. Generous space is
the cheapest way to read as premium, and cramped space is what "cheap" usually is. Space
asymmetrically: more above a heading than below it, so the heading binds to its own content.

Use a real grid (`grid-template-columns: repeat(12, 1fr)`) and place things off-centre on it —
content in columns 2–7 with a note in 9–11 reads as designed; everything in 1–12 centred does not.
Keep one consistent page gutter (`clamp(1rem, 4vw, 5rem)`) so edges line up down the whole page.

## Colour

Five values is plenty: ink, paper, one accent, and two neutrals between. Pull them from the brand if
there is one — and pull them from the actual site or logo rather than approximating from memory.

The accent should cover under about 5% of the pixels. It marks the thing that matters; used on
headings and buttons and borders and backgrounds it marks nothing. Dark sections are punctuation, not
the default — two or three inversions in a page, each at a chapter boundary.

Check contrast in both fields if you use field inversion: 4.5:1 for body text, 3:1 for large text,
and remember that a mid-grey that passes on white usually fails on near-black.

## Motion

- **Bound motion** (scroll progress) has no duration — the reader controls it. Its "speed" is the
  scene's height.
- **Discrete motion** (hover, reveal, field change) wants 200–500ms. Under 150ms reads as a jump;
  over 700ms reads as sluggish and blocks the reader.
- **Easing:** `cubic-bezier(.2, .8, .2, 1)` for entrances (fast out, settled landing),
  `cubic-bezier(.4, 0, .2, 1)` for exits. Linear only for continuous loops like a marquee.
- **Two properties maximum per element**, and in practice `transform` and `opacity`.
- **Stagger siblings 40–60ms.** Enough to read as sequence, not enough to wait for.
- **Distance:** 12–24px of travel on a reveal. 100px entrances read as a slideshow.

## Media

Images earn their place by being specific. A real screenshot of the actual product beats a stock
laptop on a desk every time, even when the screenshot is uglier.

Treat media deliberately rather than dropping it in raw: consistent corner radius or none at all
(pick one and hold it), consistent aspect ratios within a set, and a considered decision about
whether images bleed to the edge or sit inside the gutter. Always set `width`/`height` or
`aspect-ratio` so nothing reflows on load — layout shift during scroll is felt as jank even when the
animation is perfect.

## Copy

The page's words do more for "premium" than any animation. Keep theirs wherever it exists; when you
must write, write short, concrete and specific. A headline with a number in it beats an adjective. A
real quote with a real name beats three invented ones.

Never rewrite copy they are attached to without asking — that is a whole revision round spent
undoing a change nobody wanted.

## Performance

The page is judged while it is moving, so jank reads directly as "cheap".

- Animate `transform` and `opacity` only. Reading `offsetTop`/`getBoundingClientRect` inside a scroll
  handler forces synchronous layout; the scaffold engine caches geometry and recomputes on resize for
  exactly this reason.
- One batched rAF pass for all scenes, not a listener per component.
- `will-change: transform` on the handful of elements that actually transform, never broadly — it
  costs memory and can make things worse.
- Lazy-load below-fold media (`loading="lazy"`, `decoding="async"`), eager-load the hero.
- Keep hero video under a couple of MB, muted, `playsinline`, and preferably short and loopable.
- Subset and preload fonts (`<link rel="preload" as="font" crossorigin>`); a font swapping in at
  scene three is very visible.
- Target a steady 60fps while scrubbing on a mid-range phone. If a scene cannot hold that, simplify
  the scene rather than optimising around it.

## Accessibility

- `prefers-reduced-motion: reduce` gets a fully composed, fully legible page with no motion. Not a
  broken one — this is the failure mode to check, because it is invisible unless you look.
- Never hijack the wheel or fake momentum scrolling.
- All content in the DOM, reachable by find-in-page and screen readers regardless of scroll state.
- Keyboard: real focus styles, sensible tab order, and no focusable element that is visually hidden
  by a scene that has not started yet.
- Semantic structure (`<section>`, one `<h1>`, ordered headings) — a scroll page is still a document.
- Alt text that describes the content, and `alt=""` for decoration.

## Mobile

Most readers will be on a phone, so check the phone frames first, not last.

A pinned scrubbing scene often wants to become a stacked reveal below ~768px; a horizontal pin wants
to become a native swipe strip. Decide that per scene while you build it. Watch for the recurring
defects: stage children escaping and creating horizontal scroll, and display type at desktop sizes
overflowing a 390px viewport.

Two specific traps produce phone overflow that looks like nothing is wrong in the source:

- **A 12-column grid with a large gap.** Eleven 2.5rem gaps need 440px before any content does, so
  the grid overflows a 390px viewport on its own. Collapse to `grid-template-columns: 1fr` on
  phones rather than trying to squeeze the columns.
- **A grid stage that becomes a block.** `place-items: center` on the stage sets `justify-items`,
  which resolves to `justify-self: center` on the child — and a *block-level* box with
  `justify-self` shrink-to-fits and centres in current Chromium. A wide child then overflows the
  viewport in both directions. Reset `place-items: normal` in the same rule that switches the stage
  to `display: block`. Tap targets at 44px minimum, and remember `100vh` moves with browser
chrome on iOS — use `100dvh` for stages that must fill the screen exactly.
