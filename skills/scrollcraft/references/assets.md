# Assets

## Real first

Anything the user actually owns beats anything you can generate, even when it is lower quality. A
slightly badly lit photo of a real event, a real screenshot with real names in it, a real product
shot — these carry proof. Generated imagery carries none, and readers now spot it quickly.

So: inventory what exists, use all of it, and generate only for the gaps the scroll score genuinely
needs. Ask before generating; some people will be unhappy to find synthetic imagery on their company's
page, and every generation costs the user money.

### Curating what exists

- Crop with intent. A tight crop of one face out of a group shot is usually stronger than the group.
- Treat a mixed set so it reads as a set — a consistent duotone, grade, grain or border can unify
  photos taken by five different people on five different phones.
- Screenshots: crop out browser chrome, keep them legible at the size they will actually render, and
  redact anything private. A screenshot rendered at 30% of its native size proves nothing because
  nobody can read it.
- Convert to WebP or AVIF, and export at roughly 2× the largest rendered size — not at 4000px.

## Generating

Prefer a **stylised register**: geometric, low-poly, isometric, diagrammatic, duotone, line art.
It never lands in the uncanny valley, it is easy to keep on-brand by constraining the palette, and it
reads as illustration rather than as a failed photograph. Pseudo-photographic people are where
generated assets go visibly wrong — hands, text, logos, crowds and faces at any distance.

Keep prompts specific about medium, palette, subject and framing, and repeat the same style clause
across every asset in a set so they look related:

> Minimal low-poly geometric illustration, flat vector, three-colour palette (#0B0E14 ink, #F5F3EE
> paper, #2F6BFF accent), abstract human figures without facial detail, one figure teaching two
> others at a table, isometric view, generous negative space, no text, no logos.

### Paths, in order of preference

1. **An image/video MCP connector, if this session has one.** Kling is the common case: call
   `who_am_i` first (it reports the models and argument shapes to use), then `text_to_image` and, for
   motion, `image_to_video` on a still you already like. Every job is billed, so do not submit trial
   runs — decide the prompt, then generate once. If a parameter is unclear, ask rather than guessing.
2. **An HTTP image API with a key already in the environment** (`KIE_API_KEY`, `REPLICATE_API_TOKEN`,
   `FAL_KEY`, `OPENAI_API_KEY` …). Check what exists before assuming; never ask the user to paste a
   key into the chat, and never commit one.
3. **Generate nothing.** CSS, SVG and canvas can carry a great deal: gradient fields, animated grids,
   data-driven diagrams, typographic composition, a real SVG world map with plotted arcs. For an
   abstract or technical brand this is often the better-looking option anyway, and it is infinitely
   editable, tiny, and sharp at every resolution.

If no path is available, say so plainly and design around it rather than shipping grey placeholder
rectangles.

### Video

Generate a still you are happy with first, then animate it — text-to-video in one shot gives you far
less control over composition and brand. Keep clips short (3–6s), loopable, muted, and encode to both
MP4/H.264 and WebM. Always ship a poster frame: on a slow connection the poster is what the reader
sees, so the scene has to work as a still image.

For a scrubbed scene (see `scroll-patterns.md` §9), keep the clip small and simple — scrubbing decodes
constantly, and a heavy clip that plays smoothly can still scrub badly.

## Organising and checking

Keep a flat, named asset folder and record provenance, because six months later nobody remembers
which images were generated:

```
assets/
  img/   hero-poster.webp, founder.webp, cohort-01.webp
  video/ reach.mp4, reach.webm, reach-poster.webp
  svg/   world.svg, logo.svg
  ASSETS.md    # per file: source (real / generated + model + prompt), licence, who approved it
```

Before handing over, confirm every asset is actually referenced, no file is unreasonably large for
what it shows, every image has real alt text, dimensions are set so nothing reflows, and nothing
synthetic is presented as documentary evidence. Say out loud, in the handover, which assets were
generated — the user needs to know that before the page goes public.
