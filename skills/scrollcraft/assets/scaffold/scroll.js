/* Scrollcraft — progress-bound scroll engine.
 *
 * Four primitives, one batched rAF pass, geometry cached and recomputed on resize.
 *
 *   pin(el, p => {})    p: 0 → 1 across (el.height - viewport). el is a tall section
 *                       containing a sticky, viewport-sized stage.
 *   track(el, p => {})  p: 0 → 1 as el crosses the viewport (0 = top edge entering from
 *                       below, 0.5 = centred, 1 = bottom edge leaving at the top).
 *   reveal(el, opts)    adds a class once when el enters view. A trigger, not a binding.
 *   onProgress(fn)      whole-document progress, for page-level indicators.
 *
 * Two things here matter more than they look:
 *
 * 1. update() runs once on load. Browsers restore scroll position on reload, so a page whose
 *    state is only written inside a scroll handler shows half its content invisible to anyone
 *    who refreshes mid-page.
 * 2. Under prefers-reduced-motion every callback is invoked exactly once with its composed
 *    value (pin → 1, the finished state; track → 0.5, the in-view state) and no listeners are
 *    attached. The page ends up complete and still, rather than stuck at its start state.
 */
window.Scrollcraft = (function () {
  'use strict';

  var scenes = [];
  var pageFns = [];
  var vh = 0;
  var ticking = false;
  var needsMeasure = true;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)');

  function clamp(v, lo, hi) {
    if (lo === undefined) lo = 0;
    if (hi === undefined) hi = 1;
    return v < lo ? lo : v > hi ? hi : v;
  }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function mapRange(v, inMin, inMax, outMin, outMax) {
    if (inMax === inMin) return outMin;
    return outMin + ((v - inMin) * (outMax - outMin)) / (inMax - inMin);
  }

  function measure() {
    vh = window.innerHeight;
    var y = window.pageYOffset;
    for (var i = 0; i < scenes.length; i++) {
      var s = scenes[i];
      var r = s.el.getBoundingClientRect();
      s.top = r.top + y;
      s.height = r.height;
      if (s.mode === 'pin' && s.height <= vh + 1 && !s.warned) {
        s.warned = true;
        console.warn('[scrollcraft] pinned section is not taller than the viewport, so its ' +
          'progress can never advance. Give it a --scene-length above 100vh:', s.el);
      }
    }
    needsMeasure = false;
  }

  function progressOf(s, y) {
    if (s.mode === 'pin') {
      return clamp((y - s.top) / Math.max(s.height - vh, 1));
    }
    return clamp((y + vh - s.top) / Math.max(s.height + vh, 1));
  }

  function docProgress(y) {
    var max = document.documentElement.scrollHeight - vh;
    return clamp(max > 0 ? y / max : 0);
  }

  function update() {
    ticking = false;
    if (needsMeasure) measure();
    var y = window.pageYOffset;
    for (var i = 0; i < scenes.length; i++) scenes[i].fn(progressOf(scenes[i], y));
    var p = docProgress(y);
    for (var j = 0; j < pageFns.length; j++) pageFns[j](p);
  }

  function request() {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }

  function invalidate() { needsMeasure = true; request(); }

  function add(mode, el, fn, opts) {
    if (!el || typeof fn !== 'function') return;
    opts = opts || {};
    if (reduced.matches) {
      var composed = opts.reducedProgress;
      if (composed === undefined) composed = mode === 'pin' ? 1 : 0.5;
      fn(composed);
      return;
    }
    scenes.push({ el: el, fn: fn, mode: mode });
    invalidate();
  }

  function reveal(el, opts) {
    if (!el) return;
    opts = opts || {};
    var cls = opts.className || 'is-in';
    var fire = function () {
      el.classList.add(cls);
      if (opts.onEnter) opts.onEnter(el);
    };
    if (reduced.matches || !('IntersectionObserver' in window)) { fire(); return; }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        fire();
        if (opts.once !== false) io.unobserve(entry.target);
      });
    }, { threshold: opts.threshold === undefined ? 0.25 : opts.threshold,
         rootMargin: opts.rootMargin || '0px 0px -6% 0px' });
    io.observe(el);
  }

  /* Stagger a set of siblings so they read as a sequence rather than one slab. */
  function revealAll(els, opts) {
    opts = opts || {};
    var step = opts.step === undefined ? 50 : opts.step;
    Array.prototype.forEach.call(els, function (el, i) {
      el.style.transitionDelay = (i * step) + 'ms';
      reveal(el, opts);
    });
  }

  if (!reduced.matches) {
    window.addEventListener('scroll', request, { passive: true });
    window.addEventListener('resize', invalidate);
    window.addEventListener('orientationchange', invalidate);
    window.addEventListener('load', invalidate);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(invalidate);
    /* Late-loading media changes section heights, which changes every scene below it. */
    if ('ResizeObserver' in window) {
      new ResizeObserver(invalidate).observe(document.documentElement);
    }
    request();
  }

  return {
    pin: function (el, fn, opts) { add('pin', el, fn, opts); },
    track: function (el, fn, opts) { add('track', el, fn, opts); },
    reveal: reveal,
    revealAll: revealAll,
    onProgress: function (fn) {
      if (reduced.matches) { fn(1); return; }
      pageFns.push(fn); request();
    },
    refresh: invalidate,
    clamp: clamp,
    lerp: lerp,
    mapRange: mapRange,
    reducedMotion: reduced.matches
  };
})();
