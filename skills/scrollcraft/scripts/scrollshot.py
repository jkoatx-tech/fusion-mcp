#!/usr/bin/env python3
"""Walk a scroll-driven page and report what a text-only read of the source cannot show.

    python scrollshot.py http://localhost:8000 --out .scrollcraft/shots
    python scrollshot.py ./index.html --frames 16 --viewports desktop,phone

Six passes, each aimed at a failure that is invisible in code:

  frame walk         screenshots at even scroll fractions, per viewport, so you can see whether
                     each scene actually changes and whether anything collides mid-progress
  invisible content  elements sitting in the viewport at effectively zero opacity — the most
                     common silent failure in progress-bound scenes
  overflow           a stage child escaping and creating horizontal scroll, or display type too
                     large for a phone
  mid-scroll reload   browsers restore scroll position; state written only in a scroll handler
                     leaves the page half blank for anyone who refreshes
  reduced motion     the composed, still page must be complete, not stuck at its start state
  console/network    thrown exceptions and missing assets

Exits 1 when a pass fails, so it can gate a handover. Needs `pip install playwright`; the browser
is often already provisioned (check PLAYWRIGHT_BROWSERS_PATH before downloading one).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

VIEWPORTS = {
    "desktop": (1440, 900),
    "laptop": (1280, 800),
    "tablet": (834, 1112),
    "phone": (390, 844),
}

# Cumulative opacity rather than the element's own: a scene that fades its whole stage hides its
# children without any of them looking transparent.
AUDIT_JS = r"""
() => {
  const describe = (el) => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    if (el.classList.length) s += '.' + Array.from(el.classList).slice(0, 3).join('.');
    return s;
  };
  const effectiveOpacity = (el) => {
    let o = 1, n = el;
    while (n && n.nodeType === 1) {
      const v = parseFloat(getComputedStyle(n).opacity);
      if (!isNaN(v)) o *= v;
      if (o < 0.001) break;
      n = n.parentElement;
    }
    return o;
  };
  const vh = innerHeight;
  const vw = document.documentElement.clientWidth;
  const invisible = [], overflowing = [];
  const sel = 'h1,h2,h3,h4,h5,p,li,a,button,img,video,figcaption,blockquote,td,th,[data-count],[data-claim]';
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.bottom <= 4 || r.top >= vh - 4) continue;
    if (r.right > vw + 2 || r.left < -2) {
      overflowing.push({ el: describe(el), left: Math.round(r.left), right: Math.round(r.right),
                         overflowX: getComputedStyle(el).overflowX });
    }
  }
  for (const el of document.querySelectorAll(sel)) {
    const media = el.tagName === 'IMG' || el.tagName === 'VIDEO';
    const text = (el.textContent || '').trim();
    if (!text && !media) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    // Tolerate the bottom of the viewport: content just peeking in has legitimately not
    // triggered its reveal yet, and flagging it buries the real failures in noise.
    if (r.bottom <= 4 || r.top >= vh * 0.88) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    if (effectiveOpacity(el) < 0.05) {
      invisible.push({ el: describe(el), text: text.slice(0, 70), top: Math.round(r.top) });
    }
  }
  return {
    invisible: invisible.slice(0, 15),
    overflowing: overflowing.slice(0, 15),
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: vw,
    scrollHeight: document.documentElement.scrollHeight,
  };
}
"""


CHROMIUM_FALLBACKS = (
    "/opt/pw-browsers/chromium",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)


def launch_chromium(pw, explicit: str | None = None):
    """Launch Chromium, falling back to a browser the environment already provides.

    A pinned playwright version often does not match the Chromium build that is already on the
    machine, and `playwright install` is the wrong answer when a working browser is sitting right
    there — so try the bundled one, then the known locations.
    """
    candidates = [explicit] if explicit else []
    candidates.append(None)                      # playwright's own bundled build
    candidates.extend(CHROMIUM_FALLBACKS)
    last = None
    for candidate in candidates:
        if candidate is not None and not pathlib.Path(candidate).exists():
            continue
        try:
            if candidate is None:
                return pw.chromium.launch()
            browser = pw.chromium.launch(executable_path=candidate)
            print(f"using browser at {candidate}")
            return browser
        except Exception as exc:  # noqa: BLE001 - any launch failure is worth trying the next path
            last = exc
    sys.exit("could not launch Chromium.\n"
             f"last error: {last}\n"
             "Install the matching browser (`playwright install chromium`) or pass "
             "--browser /path/to/chrome.")


def settle(page, ms: int = 650) -> None:
    """Let a frame land: two animation frames, then any CSS transition.

    The wait has to outlast a reveal transition (typically 400-600ms). Jumping between
    scroll positions fires the observers late, so a shorter wait screenshots and audits
    elements mid-fade and reports every reveal as invisible content.
    """
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    page.wait_for_timeout(ms)


def resolve_target(target: str) -> str:
    if target.startswith(("http://", "https://", "file://")):
        return target
    path = pathlib.Path(target).resolve()
    if not path.exists():
        sys.exit(f"no such file: {path}")
    print(f"note: loading {path.name} over file:// — if it uses ES modules, fetch() or "
          f"cross-origin media, serve it instead (python -m http.server) and pass the URL")
    return path.as_uri()


def run_viewport(browser, url: str, name: str, size, frames: int, out: pathlib.Path) -> dict:
    width, height = size
    context = browser.new_context(viewport={"width": width, "height": height},
                                  device_scale_factor=1)
    page = context.new_page()
    errors: list[str] = []
    missing: list[str] = []

    def on_console(m):
        # "Failed to load resource" duplicates the response check below, with less detail.
        if m.type == "error" and not m.text.startswith("Failed to load resource"):
            errors.append(f"console.error: {m.text}")

    def on_response(r):
        if r.status >= 400:
            missing.append(f"{r.status} {r.url}")

    page.on("console", on_console)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: missing.append(f"failed {r.url}"))
    page.on("response", on_response)

    page.goto(url, wait_until="load")
    page.wait_for_timeout(600)

    max_scroll = page.evaluate(
        "() => Math.max(document.documentElement.scrollHeight - innerHeight, 0)")
    result = {
        "viewport": name,
        "size": [width, height],
        "max_scroll": max_scroll,
        "page_vh": round(max_scroll / height + 1, 1) if height else 0,
        "frames": [],
        "identical_pairs": [],
        "invisible": [],
        "overflow": None,
        "errors": [],
        "missing_assets": [],
    }

    shots = out / name
    shots.mkdir(parents=True, exist_ok=True)
    previous_hash = None

    for i in range(frames):
        fraction = i / (frames - 1) if frames > 1 else 0
        y = round(max_scroll * fraction)
        page.evaluate("y => window.scrollTo({top: y, behavior: 'instant'})", y)
        settle(page)
        shot = shots / f"{i:02d}-p{round(fraction * 100):03d}.png"
        png = page.screenshot(path=str(shot))
        digest = hashlib.sha1(png).hexdigest()
        audit = page.evaluate(AUDIT_JS)
        result["frames"].append({
            "index": i, "fraction": round(fraction, 3), "scroll_y": y,
            "file": str(shot), "invisible": len(audit["invisible"]),
        })
        if digest == previous_hash:
            result["identical_pairs"].append([i - 1, i])
        previous_hash = digest
        for item in audit["invisible"]:
            result["invisible"].append(dict(item, frame=i))
        if audit["scrollWidth"] > audit["clientWidth"] + 1 and result["overflow"] is None:
            result["overflow"] = {
                "frame": i, "scrollWidth": audit["scrollWidth"],
                "clientWidth": audit["clientWidth"], "offenders": audit["overflowing"],
            }

    # Mid-scroll reload: the restore-position bug.
    reload_report = None
    if max_scroll > 0:
        page.evaluate("y => window.scrollTo({top: y, behavior: 'instant'})",
                      round(max_scroll * 0.5))
        page.wait_for_timeout(200)
        page.reload(wait_until="load")
        page.wait_for_timeout(900)
        audit = page.evaluate(AUDIT_JS)
        shot = shots / "reload-mid.png"
        page.screenshot(path=str(shot))
        reload_report = {
            "file": str(shot),
            "restored_scroll": page.evaluate("() => window.pageYOffset"),
            "invisible": audit["invisible"],
        }
    result["reload"] = reload_report
    result["errors"] = errors[:20]
    result["missing_assets"] = missing[:20]
    context.close()
    return result


def run_reduced_motion(browser, url: str, out: pathlib.Path) -> dict:
    context = browser.new_context(viewport={"width": 1440, "height": 900},
                                  reduced_motion="reduce")
    page = context.new_page()
    page.goto(url, wait_until="load")
    page.wait_for_timeout(900)
    audit = page.evaluate(AUDIT_JS)
    shot = out / "reduced-motion.png"
    page.screenshot(path=str(shot), full_page=True)
    context.close()
    return {"file": str(shot), "invisible": audit["invisible"],
            "scrollHeight": audit["scrollHeight"]}


def report(results: dict) -> bool:
    ok = True
    print("\n" + "=" * 72)
    for vp in results["viewports"]:
        print(f"\n{vp['viewport']}  {vp['size'][0]}x{vp['size'][1]}   "
              f"page length ≈ {vp['page_vh']}vh   {len(vp['frames'])} frames")
        if vp["errors"]:
            ok = False
            print("  FAIL  script errors:")
            for e in vp["errors"][:6]:
                print(f"        {e}")
        hard_misses = [m for m in vp["missing_assets"] if "favicon" not in m]
        if hard_misses:
            ok = False
            print("  FAIL  assets the page asks for and does not get:")
            for m in hard_misses[:6]:
                print(f"        {m}")
        elif vp["missing_assets"]:
            print("  WARN  no favicon (fine locally, worth having before it ships)")
        if vp["overflow"]:
            ok = False
            o = vp["overflow"]
            print(f"  FAIL  horizontal overflow at frame {o['frame']}: "
                  f"scrollWidth {o['scrollWidth']} > {o['clientWidth']}")
            for off in o["offenders"][:6]:
                print(f"        {off['el']}  left={off['left']} right={off['right']}")
        if vp["invisible"]:
            ok = False
            seen = set()
            print("  FAIL  content invisible while in the viewport:")
            for item in vp["invisible"]:
                key = (item["el"], item["text"])
                if key in seen:
                    continue
                seen.add(key)
                print(f"        frame {item['frame']}: {item['el']} — {item['text']!r}")
                if len(seen) >= 6:
                    break
        if vp["identical_pairs"]:
            print("  WARN  consecutive frames are pixel-identical — scroll distance spent on "
                  "nothing:")
            print(f"        {vp['identical_pairs'][:8]}")
        rl = vp.get("reload")
        if rl and rl["invisible"]:
            ok = False
            print(f"  FAIL  mid-scroll reload (restored to y={rl['restored_scroll']}) leaves "
                  f"{len(rl['invisible'])} element(s) invisible — scene state is only written in "
                  f"a scroll handler; run one update pass on load")
        elif rl:
            print(f"  ok    mid-scroll reload clean (restored to y={rl['restored_scroll']})")
        if not (vp["errors"] or hard_misses or vp["overflow"] or vp["invisible"]):
            print("  ok    no errors, no overflow, nothing invisible")

    rm = results.get("reduced_motion")
    if rm:
        if rm["invisible"]:
            ok = False
            print(f"\nreduced motion  FAIL  {len(rm['invisible'])} element(s) invisible — the "
                  f"still page must be complete, not stuck at its start state")
            for item in rm["invisible"][:6]:
                print(f"        {item['el']} — {item['text']!r}")
        else:
            print("\nreduced motion  ok    page composes fully with no motion")

    print("\n" + "=" * 72)
    print(f"frames written to {results['out']}")
    print("Now look at them in order. The script catches breakage; only your eyes catch a scene "
          "that is technically fine and aesthetically dead. See references/verification.md.")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", help="URL, or a path to a local HTML file")
    ap.add_argument("--out", default=".scrollcraft/shots", help="output directory for frames")
    ap.add_argument("--frames", type=int, default=12, help="frames per viewport (default 12)")
    ap.add_argument("--viewports", default="desktop,phone",
                    help="comma-separated: " + ", ".join(VIEWPORTS))
    ap.add_argument("--skip-reduced-motion", action="store_true")
    ap.add_argument("--browser", default=None,
                    help="path to a Chromium/Chrome executable, if the bundled one "
                         "is missing or mismatched")
    ap.add_argument("--json", default=None, help="also write the full report as JSON")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright is not installed: pip install playwright\n"
                 "(the browser may already exist — check $PLAYWRIGHT_BROWSERS_PATH before "
                 "running `playwright install`)")

    names = [n.strip() for n in args.viewports.split(",") if n.strip()]
    unknown = [n for n in names if n not in VIEWPORTS]
    if unknown:
        sys.exit(f"unknown viewport(s) {unknown}; choose from {list(VIEWPORTS)}")

    url = resolve_target(args.target)
    out = pathlib.Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    results = {"target": url, "out": str(out), "viewports": []}
    with sync_playwright() as pw:
        browser = launch_chromium(pw, args.browser)
        for name in names:
            print(f"walking {name} ...")
            results["viewports"].append(
                run_viewport(browser, url, name, VIEWPORTS[name], max(args.frames, 2), out))
        if not args.skip_reduced_motion:
            print("checking reduced motion ...")
            results["reduced_motion"] = run_reduced_motion(browser, url, out)
        browser.close()

    ok = report(results)
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(results, indent=2))
        print(f"report written to {args.json}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
