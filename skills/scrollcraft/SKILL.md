---
name: scrollcraft
description: >-
  Design and build premium, scroll-driven landing pages for a business, product, service, event or
  personal brand — pages where scrolling drives what happens on screen instead of just moving a
  document. Use this skill whenever someone asks for a landing page, marketing site, hero section,
  product page, launch page, "one-pager" or portfolio, or wants an existing page to feel more
  premium, less generic, less like AI slop, more editorial, more interactive, or "like those sites
  with the scroll animations". Also use it when the ask is a redesign, a restyle, a second version
  of a page they already have, or just "make this look better" about a public-facing page — even if
  they never say the words "scroll", "animation" or "skill". Covers the interview that fixes the
  page's intent, the scroll score that plans it, optional AI asset generation, the build, and a
  screenshot verification pass. Not for app UI, internal dashboards, admin panels, docs sites or
  CRUD screens.
---

# Scrollcraft

## The thesis

A generic page treats scroll as a way to move a document. A scroll-driven page treats scroll as an
**input device**: the reader turns a dial and something on screen responds continuously — a number
climbs, a map fills, a rail of exhibits slides past, a sentence types itself. That feedback loop is
what makes a stranger keep going past the fold, and it is the whole reason this skill exists.

Three properties separate the real thing from decoration:

- **Bound, not triggered.** The visual state is a function of scroll position, so it runs backwards
  when the reader scrolls up. A one-shot fade-in that fires once and is done is a trigger; it has
  its place, but a page made only of triggers feels like a template with a plugin.
- **One idea per scene.** While a scene holds the viewport, it makes exactly one point. Readers
  cannot watch three things change at once, and a scene that tries reads as noise.
- **Earned.** Motion exists because it explains something — growth, scale, before/after, sequence,
  accumulation. Motion that explains nothing is the AI-slop tell, no matter how smooth it is.

Everything below serves those three.

## Phase 0 — Read the room

Before asking anything, spend a few minutes gathering what already exists, because it changes every
later question and the user should not have to describe what you can just read.

- If they named a URL or pointed at a repo/folder, look at it: copy, claims, colour, type, logo,
  real photography, existing links (those links must survive into the new page).
- If there are asset folders, list them. Note what is genuinely usable versus placeholder.
- If there is nothing — a blank slate or a hypothetical business — say so plainly and plan on
  generated or abstract assets rather than pretending you have photography.

Say in one or two lines what you found. Then interview.

## Phase 1 — Interview

Read `references/interview.md` and run it. Do not skip this to start coding: the questions are what
make two runs of this skill produce two different sites instead of one template twice. The
interview is short on purpose — two rounds of at most four questions, with concrete options, using
`AskUserQuestion` where that tool exists and plain numbered questions where it does not.

What you are extracting: the **order the reader meets things**, the **one belief** they should hold
at the end, **which assets are real**, the **signature move** nobody else's site does, and where the
page should feel calm versus intense. Ask about feeling and motive, not features — people answer
"what should they believe by the end?" far better than "what sections do you want?".

**Check first whether a show is wanted at all.** Some briefs are not asking for a page that
performs; they are asking for an embarrassment to stop. "It's from 2011 and looks it", "it's
unreadable on a phone", "the shop is doing fine, the site just isn't" — those want typography,
speed, structure and a layout that works on a phone. There, the honest answer is a calm page and at
most one bound scene, placed where it genuinely explains something, and sometimes none at all. Say
so plainly and build the quiet page; a page that performs when nobody asked costs the client real
money and buys them something they did not want. A skill that cannot decline itself is a salesman,
not a tool — and the cheapest way to lose a client's trust is to answer a question they did not ask.

Scale rather than switch off: the scroll score, the design decisions, the verification pass and the
refusal to fabricate all still apply. What scales down is the number of bound scenes, not the care.

**When there is nobody to ask** — an automated run, a brief handed over without a contact, a client
who has gone quiet — do not stall and do not water the page down into something inoffensive. Answer
the questions yourself from the brief, write each answer into the score as a decision rather than a
fact, and keep building. A page built on four clearly recorded assumptions is worth far more than no
page, and it gives the client something concrete to disagree with, which is how you get the real
answer. Then say plainly in the handover which decisions were yours and which of them would change
the page most if they turn out wrong.

## Phase 2 — Write the scroll score

Before any HTML, write `SCROLL-SCORE.md` in the project. It is short — one block per scene — and it
is where the design actually happens:

```markdown
## Scene 03 — Reach
Claim:      12,400 members in 94 countries, growing.
Mechanic:   pinned scene, globe fills with connection arcs as counter climbs
Bound to:   scroll progress 0→1 over 180vh
Scroll cost: 180vh
Calm/intense: intense — this is the proof beat
Assets:     world.svg (have), arc data (generate)
Exit:       cuts to light on the next scene's first pixel
```

Then check the score as a whole before building:

- **Does the sequence answer the interview's belief?** Read the claims top to bottom with nothing
  else. If a stranger would believe the one sentence by the end, the spine is right.
- **Rhythm.** Mark each scene calm or intense and read the pattern. All-intense is exhausting and
  reads cheap; all-calm is the boring page they came here to escape. Aim for tension and release,
  with the signature move placed where it hits hardest — usually not the very first scene, because
  the reader has not yet agreed to care.
- **Variety.** No mechanic twice in a row, and at most two or three distinct mechanics carrying the
  whole page. A page with nine different tricks looks like a demo reel.
- **Budget.** Sum the scroll costs. 600–1200vh total is a page; beyond that you are asking for a
  commitment strangers do not make.

Show the user the score, or at least its spine, before you build. It is much cheaper to move a
scene in a markdown file than in code, and they will catch a wrong claim instantly.

Mechanic choices and their implementations are catalogued in `references/scroll-patterns.md` —
read it while writing the score, not after.

## Phase 3 — Assets

Read `references/assets.md`. The short version: real assets beat generated ones every time, so use
what they have and generate only to fill gaps the score actually needs. Generated imagery works
best when it is *stylised* rather than pseudo-photographic — an abstract, geometric or diagrammatic
register never hits the uncanny valley and never has six-fingered hands.

Never invent a statistic, testimonial, customer name or logo. If the score calls for a number and
nobody gave you one, either find it in a source you can cite or cut the claim and tell the user why.
Fabricated proof on a real company's page is the one failure mode that actually damages them.

## Phase 4 — Build

Read `references/design-system.md` before writing CSS — it carries the type, spacing, colour and
motion decisions, plus the list of specific tells that make a page read as AI-generated. That list
is the highest-value page in this skill.

Start from `assets/scaffold/`. It gives you a working progress-bound scroll engine
(`scroll.js`, ~130 lines), a token sheet (`styles.css`) and a wired-up `index.html`. Copy it into
the project and edit; do not rewrite the engine per project, and do not reach for a scroll library
unless a scene genuinely needs timeline choreography the primitives cannot express.

Non-negotiables while building, each because it breaks a real reader otherwise:

- **Initialise on load, not only on scroll.** Browsers restore scroll position on reload. If your
  scene state only updates inside a scroll handler, a reader who reloads mid-page sees half the
  content stuck invisible. The scaffold's engine runs one pass on load; keep that.
- **Never hijack the wheel.** No `wheel` preventDefault, no smooth-scroll library that fakes
  momentum. It breaks find-in-page, keyboard scrolling, trackpad muscle memory and screen readers,
  and readers feel it as the page fighting them.
- **`prefers-reduced-motion` gets a composed page**, not a broken one: every element at its final
  state, all content visible, no motion. The engine does this by jumping progress to its end value.
- **Animate `transform` and `opacity` only.** Anything else lands on the layout or paint path and
  the page stutters exactly when the reader is judging whether it feels premium.
- **All content lives in the DOM**, visible to a screen reader and to find-in-page, regardless of
  scroll state.
- **Real copy.** Pull it from their site or their answers. Lorem ipsum and "Empower your workflow"
  both tell the reader nobody was home.

Mobile is not a later pass. A pinned scrubbing scene often wants to become a simple stacked reveal
below ~768px, and it is much easier to decide that while writing the scene than to retrofit it.

## Phase 5 — Verify

This is the part a text-only harness cannot judge by reading its own code, so do not skip it and do
not hand over a page you have not looked at.

```bash
python skills/scrollcraft/scripts/scrollshot.py <url-or-file> --out .scrollcraft/shots
```

It walks the page at even scroll fractions, screenshots each frame at desktop and phone widths,
reloads mid-scroll to catch the restore-position bug, runs a reduced-motion pass, and reports
console errors, horizontal overflow, and any element sitting invisible in the viewport.

Then **look at the frames**. Read `references/verification.md` for what to look for and what the
common failures mean. The script catches mechanical breakage; only your eyes catch a scene that is
technically fine and aesthetically dead.

Fix what you find, re-run, and only then hand over.

## Phase 6 — Hand over and revise

Give the user how to open it, the scroll score as the map, and a short honest note on what you are
unsure about. Then expect feedback, and translate it rather than taking it literally — the user is
describing a feeling and it is your job to find the cause:

| They say | It usually means |
|---|---|
| "it scrolls too fast" | the scene's scroll budget is too small — give it more `vh`, don't slow the easing |
| "bland", "flat", "not premium" | not enough contrast: type is one size, sections are one colour, nothing is bound to scroll — add a scene or raise the stakes on one that exists |
| "too much", "busy", "dizzying" | concurrent motion, or parallax offsets too large — cut to one change per scene |
| "doesn't feel like us" | colour and type drifted off-brand, or the copy got rewritten when it should have been kept |
| "boring at the top" | the first screen is asserting instead of showing — move a proof beat up or give the hero one bound element |

Revise in the score first when the change is structural, then in code. And re-run Phase 5 after
every round, because the fix for one scene routinely breaks the one above it.

## Reference files

- `references/interview.md` — the two interview rounds, how to read the answers, blank-slate variant
- `references/scroll-patterns.md` — the mechanic catalogue, each with when to use it and how to build it
- `references/design-system.md` — type, spacing, colour, motion, performance, and the anti-slop list
- `references/assets.md` — real assets first, generation paths (Kling MCP and HTTP APIs), optimisation
- `references/verification.md` — what to look for in the frames, and what each common failure means
