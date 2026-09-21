# Scrollcraft

A Claude skill for designing and building premium, scroll-driven landing pages — pages where
scrolling drives what happens on screen instead of just moving a document.

It covers the whole arc: an interview that fixes the page's intent, a scroll score that plans the
scenes before any code, an asset pass, the build on top of a working scroll engine, and a
screenshot verification pass that catches the failures a text-only read of the source cannot see.

## Install

Copy the folder to wherever the skills for your setup live:

```bash
cp -r skills/scrollcraft ~/.claude/skills/          # personal, available everywhere
cp -r skills/scrollcraft <project>/.claude/skills/  # one project
```

Then ask for a landing page — the description triggers on landing pages, hero sections, marketing
sites, redesigns and "make this feel more premium". Or invoke it by name.

## What is in here

```
SKILL.md                     the workflow: read the room → interview → score → assets → build → verify
references/interview.md      the two interview rounds and how to read the answers
references/scroll-patterns.md eleven mechanics, when each one is the right tool, how to build it
references/design-system.md  type, space, colour, motion, performance, a11y, and the anti-slop list
references/assets.md         real assets first; generation paths and how to keep a set coherent
references/verification.md   what to look for in the frames and what each failure means
assets/scaffold/             a working starting point: scroll engine, token sheet, wired-up page
scripts/scrollshot.py        the verification pass
```

## The verification script

```bash
pip install playwright                 # the browser is often already provisioned
python scripts/scrollshot.py http://localhost:8000 --out .scrollcraft/shots
```

Walks the page at even scroll fractions on desktop and phone, screenshots each frame, and reports
console errors, missing assets, horizontal overflow, content stuck invisible in the viewport, the
mid-scroll reload bug, and whether the reduced-motion page composes fully. Exits non-zero when a
pass fails, so it can gate a handover.

It finds a Chromium automatically (`--browser` overrides), which matters when the installed
Playwright version does not match the browser build already on the machine.

## Eine fertige Seite zum Ansehen

`examples/halbwert/` (im selben Repository, nicht in diesem Ordner, damit eine Kopie der Skill
schlank bleibt) ist eine vollständige Seite, mit dieser Skill gebaut: sechs Szenen, ein
ausgeführter Scroll-Score, und der Regressionsfall für die Engine. Das Studio darin ist erfunden
und weist das selbst aus.

## The scaffold

`assets/scaffold/` is a working page, not a snippet: `scroll.js` is a ~130-line progress-bound
engine (`pin`, `track`, `reveal`, `onProgress`) that batches every scene into one rAF pass, runs one
update on load so a mid-page reload is not blank, and composes the page into its final state under
`prefers-reduced-motion`. `styles.css` carries the type, space and colour tokens; `index.html` wires
up a hero, a pinned counter, a horizontal rail, a field inversion and staggered reveals.

Serve it and look at it:

```bash
cd assets/scaffold && python -m http.server 8000
```
