/*
 * OfficeKit standalone deck player. Inlined into dist/slides.html by
 * export-html.mjs; no dependencies.
 *
 * Every slide is stored in its final state (all steps revealed). The JSON in
 * #ok-steps lists, per slide, the elements whose class or style changes with
 * each click step; stepping re-applies those recorded attributes.
 *
 * Two modes:
 *   present  one slide at a time; clicks and keys step through reveals.
 *   browse   every slide stacked and fully revealed in a scrolling page;
 *            clicks never navigate, so text can be selected and commented.
 * Every open starts in browse; `p` / `b` or the mode button switch.
 *
 *   present: → Space PageDown / click     next step
 *            ← PageUp / click left quarter previous step
 *            ↓ ↑                          next / previous slide
 *   browse:  → ←                          next / previous slide (scrolls)
 *   both:    Home End  o overview  f fullscreen  #n in the URL = slide n
 */
(() => {
  const deck = document.getElementById('ok-deck');
  if (!deck) return;
  const W = Number(deck.dataset.width) || 980;
  const H = Number(deck.dataset.height) || 551;
  const slides = Array.from(deck.querySelectorAll(':scope > .ok-slide'));
  if (!slides.length) return;
  let steps = [];
  try {
    steps = JSON.parse(document.getElementById('ok-steps').textContent || '[]');
  } catch {
    steps = [];
  }
  const root = document.documentElement;
  root.classList.add('ok-js');

  const total = (i) => (steps[i] && steps[i].total) || 0;
  const pristine = slides.map((s) => s.querySelector('.ok-canvas').cloneNode(true));
  const nodes = slides.map((s, i) => {
    const map = new Map();
    const els = (steps[i] && steps[i].els) || {};
    for (const id of Object.keys(els)) {
      const el = s.querySelector(`[data-okx="${id}"]`);
      if (el) map.set(el, els[id]);
    }
    return map;
  });

  const setAttr = (el, name, value) => {
    if (value === null || value === undefined) el.removeAttribute(name);
    else el.setAttribute(name, value);
  };

  function applyStep(i, step) {
    for (const [el, rec] of nodes[i]) {
      if (rec.c) setAttr(el, 'class', rec.c[Math.min(step, rec.c.length - 1)]);
      if (rec.s) setAttr(el, 'style', rec.s[Math.min(step, rec.s.length - 1)]);
    }
  }

  // Every open starts in browse; presenting is a deliberate switch.
  let mode = 'browse';

  // ── chrome ──────────────────────────────────────────────────────────
  const icon = (d) =>
    `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const ICONS = {
    prev: icon('<path d="m15 18-6-6 6-6"/>'),
    next: icon('<path d="m9 18 6-6-6-6"/>'),
    overview: icon(
      '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    ),
    full: icon(
      '<path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3"/>',
    ),
    present: icon('<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/><path d="m10 7 5 3-5 3z"/>'),
    browse: icon('<rect x="4" y="3" width="16" height="7" rx="1"/><rect x="4" y="14" width="16" height="7" rx="1"/>'),
  };
  const progress = document.createElement('div');
  progress.className = 'ok-progress';
  const bar = document.createElement('nav');
  bar.className = 'ok-bar';
  bar.setAttribute('aria-label', 'Slide controls');
  bar.innerHTML = [
    `<button type="button" data-act="prev" title="Previous (←)" aria-label="Previous">${ICONS.prev}</button>`,
    '<span class="ok-count" aria-live="polite"></span>',
    `<button type="button" data-act="next" title="Next (→)" aria-label="Next">${ICONS.next}</button>`,
    '<span class="ok-sep" aria-hidden="true"></span>',
    '<button type="button" data-act="mode" class="ok-mode"></button>',
    `<button type="button" data-act="overview" title="Overview (o)" aria-label="Overview">${ICONS.overview}</button>`,
    `<button type="button" data-act="full" title="Fullscreen (f)" aria-label="Fullscreen">${ICONS.full}</button>`,
  ].join('');
  const count = bar.querySelector('.ok-count');
  const modeBtn = bar.querySelector('[data-act="mode"]');
  const overview = document.createElement('div');
  overview.className = 'ok-overview';
  overview.setAttribute('role', 'dialog');
  overview.setAttribute('aria-label', 'Slide overview');
  document.body.append(progress, bar, overview);

  let idleTimer = 0;
  function wake() {
    bar.classList.add('ok-show');
    clearTimeout(idleTimer);
    if (mode === 'present') idleTimer = setTimeout(() => bar.classList.remove('ok-show'), 2200);
  }

  // ── layout ──────────────────────────────────────────────────────────
  function fit() {
    const vw = document.documentElement.clientWidth || window.innerWidth;
    const vh = window.innerHeight;
    if (mode === 'present') {
      const scale = Math.min(vw / W, vh / H);
      const left = (vw - W * scale) / 2;
      const top = (vh - H * scale) / 2;
      for (const s of slides) {
        s.style.width = '';
        s.style.height = '';
        s.querySelector('.ok-canvas').style.transform = `translate(${left}px, ${top}px) scale(${scale})`;
      }
    } else {
      const scale = Math.max(0.2, Math.min((vw - 32) / W, 1.4));
      for (const s of slides) {
        s.style.width = `${W * scale}px`;
        s.style.height = `${H * scale}px`;
        s.querySelector('.ok-canvas').style.transform = `scale(${scale})`;
      }
    }
  }

  // ── state ───────────────────────────────────────────────────────────
  let cur = -1;
  let step = 0;
  const baseTitle = document.title;

  function slideFromHash() {
    const m = /^#\/?(\d+)\b/.exec(window.location.hash);
    if (!m) return null;
    const n = Number(m[1]);
    return n >= 1 && n <= slides.length ? n - 1 : null;
  }

  function setHash(push) {
    const hash = `#${cur + 1}`;
    if (window.location.hash === hash) return;
    try {
      if (push) history.pushState(null, '', hash);
      else history.replaceState(null, '', hash);
    } catch {
      /* some sandboxes refuse history writes; the slide still changes */
    }
  }

  function renderChrome() {
    count.textContent = `${cur + 1} / ${slides.length}`;
    const done = mode === 'browse' || !total(cur) ? 1 : step / total(cur);
    progress.style.width = `${((cur + done) / slides.length) * 100}%`;
    const atStart = cur === 0 && (mode === 'browse' || step === 0);
    const atEnd = cur === slides.length - 1 && (mode === 'browse' || step >= total(cur));
    bar.querySelector('[data-act="prev"]').disabled = atStart;
    bar.querySelector('[data-act="next"]').disabled = atEnd;
    const title = slides[cur].dataset.title;
    document.title = title ? `${title} — ${baseTitle}` : baseTitle;
  }

  // ── present mode ────────────────────────────────────────────────────
  function showActive(dir) {
    slides.forEach((s, i) => {
      const on = i === cur;
      s.classList.toggle('ok-active', on);
      s.toggleAttribute('inert', !on);
      s.setAttribute('aria-hidden', on ? 'false' : 'true');
      if (!on) s.classList.remove('ok-enter-fwd', 'ok-enter-back');
    });
    const active = slides[cur];
    if (dir) {
      active.classList.remove('ok-enter-fwd', 'ok-enter-back');
      void active.offsetWidth;
      active.classList.add(dir > 0 ? 'ok-enter-fwd' : 'ok-enter-back');
    }
  }

  function go(i, s = 0, { push = true, dir = 0 } = {}) {
    i = Math.max(0, Math.min(slides.length - 1, i));
    if (mode === 'browse') {
      scrollToSlide(i, push);
      return;
    }
    s = Math.max(0, Math.min(total(i), s));
    const changed = i !== cur;
    if (changed && cur >= 0) applyStep(cur, total(cur));
    cur = i;
    step = s;
    applyStep(cur, step);
    showActive(changed ? dir : 0);
    renderChrome();
    if (changed) setHash(push);
  }

  function next() {
    if (mode === 'browse') return go(cur + 1);
    if (step < total(cur)) go(cur, step + 1);
    else if (cur < slides.length - 1) go(cur + 1, 0, { dir: 1 });
  }

  function prev() {
    if (mode === 'browse') return go(cur - 1);
    if (step > 0) go(cur, step - 1);
    else if (cur > 0) go(cur - 1, total(cur - 1), { dir: -1 });
  }

  // ── browse mode ─────────────────────────────────────────────────────
  let scrollLock = 0;
  function scrollToSlide(i, push = true) {
    cur = i;
    renderChrome();
    setHash(push);
    scrollLock = Date.now() + 600;
    slides[i].scrollIntoView({ block: 'start', behavior: 'smooth' });
  }

  let scrollQueued = false;
  function trackScroll() {
    if (mode !== 'browse' || scrollQueued || Date.now() < scrollLock) return;
    scrollQueued = true;
    requestAnimationFrame(() => {
      scrollQueued = false;
      const line = window.innerHeight / 3;
      let best = 0;
      for (let i = 0; i < slides.length; i++) {
        if (slides[i].getBoundingClientRect().top <= line) best = i;
        else break;
      }
      if (best !== cur) {
        cur = best;
        renderChrome();
        setHash(false);
      }
    });
  }

  // ── mode switch ─────────────────────────────────────────────────────
  function setMode(next) {
    mode = next;
    root.classList.toggle('ok-browse', mode === 'browse');
    root.classList.toggle('ok-present', mode === 'present');
    const other = mode === 'browse' ? 'present' : 'browse';
    modeBtn.innerHTML = `${ICONS[other]}<span>${other === 'present' ? 'Present' : 'Browse'}</span>`;
    modeBtn.title = other === 'present' ? 'Present one slide at a time (p)' : 'Browse all slides (b)';
    modeBtn.setAttribute('aria-label', modeBtn.title);
    const at = Math.max(cur, 0);
    if (mode === 'browse') {
      slides.forEach((s, i) => {
        applyStep(i, total(i));
        s.classList.remove('ok-active', 'ok-enter-fwd', 'ok-enter-back');
        s.removeAttribute('inert');
        s.removeAttribute('aria-hidden');
      });
      fit();
      cur = at;
      renderChrome();
      scrollLock = Date.now() + 300;
      slides[at].scrollIntoView({ block: 'start' });
      bar.classList.add('ok-show');
    } else {
      fit();
      cur = -1;
      go(at, 0, { push: false });
      window.scrollTo(0, 0);
    }
    wake();
  }

  // ── overview ────────────────────────────────────────────────────────
  let built = false;
  function buildOverview() {
    const grid = document.createElement('div');
    grid.className = 'ok-grid';
    const tileW = Math.min(280, Math.max(180, Math.floor((window.innerWidth - 48) / 4) - 20));
    grid.style.setProperty('--ok-tile-w', `${tileW}px`);
    pristine.forEach((canvas, i) => {
      const tile = document.createElement('button');
      tile.type = 'button';
      tile.className = 'ok-tile';
      tile.dataset.index = String(i);
      const thumb = document.createElement('div');
      thumb.className = 'ok-thumb';
      thumb.style.aspectRatio = `${W} / ${H}`;
      const clone = canvas.cloneNode(true);
      clone.querySelectorAll('[id]').forEach((el) => el.removeAttribute('id'));
      clone.querySelectorAll('[data-okx]').forEach((el) => el.removeAttribute('data-okx'));
      clone.style.transform = '';
      clone.setAttribute('aria-hidden', 'true');
      clone.setAttribute('inert', '');
      thumb.append(clone);
      const label = document.createElement('span');
      label.className = 'ok-label';
      const title = slides[i].dataset.title || '';
      label.innerHTML = '<b></b><span></span>';
      label.firstChild.textContent = String(i + 1);
      label.lastChild.textContent = title;
      tile.setAttribute('aria-label', `Slide ${i + 1}${title ? `: ${title}` : ''}`);
      tile.append(thumb, label);
      grid.append(tile);
    });
    overview.append(grid);
    built = true;
  }

  function sizeThumbs() {
    overview.querySelectorAll('.ok-thumb').forEach((thumb) => {
      thumb.firstElementChild.style.transform = `scale(${thumb.clientWidth / W})`;
    });
  }

  function openOverview() {
    if (!built) buildOverview();
    overview.classList.add('ok-open');
    overview.querySelectorAll('.ok-tile').forEach((t, i) => t.classList.toggle('ok-current', i === cur));
    sizeThumbs();
    const current = overview.querySelector('.ok-tile.ok-current');
    if (current) {
      current.focus({ preventScroll: true });
      current.scrollIntoView({ block: 'center' });
    }
  }

  function closeOverview() {
    overview.classList.remove('ok-open');
  }

  const overviewOpen = () => overview.classList.contains('ok-open');

  overview.addEventListener('click', (e) => {
    const tile = e.target.closest('.ok-tile');
    if (tile) {
      const i = Number(tile.dataset.index);
      closeOverview();
      go(i, 0, { dir: i >= cur ? 1 : -1 });
    } else if (e.target === overview) {
      closeOverview();
    }
  });

  function moveTile(delta) {
    const tiles = Array.from(overview.querySelectorAll('.ok-tile'));
    const at = tiles.indexOf(document.activeElement);
    const cols = Math.max(1, tiles.filter((t) => t.offsetTop === tiles[0].offsetTop).length);
    const by = Math.abs(delta) === 2 ? Math.sign(delta) * cols : delta;
    const target = tiles[Math.max(0, Math.min(tiles.length - 1, (at < 0 ? cur : at) + by))];
    if (target) target.focus();
  }

  // ── fullscreen ──────────────────────────────────────────────────────
  function toggleFull() {
    if (document.fullscreenElement) document.exitFullscreen?.();
    else document.documentElement.requestFullscreen?.().catch(() => {});
  }

  // ── input ───────────────────────────────────────────────────────────
  bar.addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const act = btn.dataset.act;
    if (act === 'prev') prev();
    else if (act === 'next') next();
    else if (act === 'mode') setMode(mode === 'browse' ? 'present' : 'browse');
    else if (act === 'overview') (overviewOpen() ? closeOverview : openOverview)();
    else if (act === 'full') toggleFull();
    btn.blur();
  });

  const INTERACTIVE =
    'a, button, input, textarea, select, summary, label, video, audio, iframe, [contenteditable], [tabindex]';

  deck.addEventListener('click', (e) => {
    if (mode !== 'present') return;
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (e.target.closest(INTERACTIVE)) return;
    const sel = window.getSelection();
    if (sel && String(sel).trim()) return;
    if (e.clientX < window.innerWidth / 4) prev();
    else next();
  });

  document.addEventListener('keydown', (e) => {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
    const t = e.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (overviewOpen()) {
      const moves = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: 2, ArrowUp: -2 };
      if (e.key in moves) moveTile(moves[e.key]);
      else if (e.key === 'Escape' || e.key === 'o') closeOverview();
      else return;
      e.preventDefault();
      return;
    }
    const browse = mode === 'browse';
    switch (e.key) {
      case 'ArrowRight':
        next();
        break;
      case 'ArrowLeft':
        prev();
        break;
      case 'PageDown':
      case ' ':
        if (browse) return; // native scrolling
        next();
        break;
      case 'PageUp':
        if (browse) return;
        prev();
        break;
      case 'ArrowDown':
        if (browse) return;
        if (cur < slides.length - 1) go(cur + 1, 0, { dir: 1 });
        break;
      case 'ArrowUp':
        if (browse) return;
        if (cur > 0) go(cur - 1, 0, { dir: -1 });
        break;
      case 'Home':
        go(0, 0, { dir: -1 });
        break;
      case 'End':
        go(slides.length - 1, 0, { dir: 1 });
        break;
      case 'o':
        openOverview();
        break;
      case 'p':
        if (browse) setMode('present');
        break;
      case 'b':
        if (!browse) setMode('browse');
        break;
      case 'f':
        toggleFull();
        break;
      default:
        return;
    }
    e.preventDefault();
    wake();
  });

  let touchX = null;
  deck.addEventListener(
    'touchstart',
    (e) => {
      touchX = mode === 'present' && e.touches.length === 1 ? e.touches[0].clientX : null;
    },
    { passive: true },
  );
  deck.addEventListener('touchend', (e) => {
    if (touchX === null) return;
    const dx = e.changedTouches[0].clientX - touchX;
    touchX = null;
    if (Math.abs(dx) < 50) return;
    if (dx < 0) next();
    else prev();
  });

  document.addEventListener('mousemove', wake, { passive: true });
  window.addEventListener('scroll', trackScroll, { passive: true });
  window.addEventListener('resize', () => {
    fit();
    if (overviewOpen()) sizeThumbs();
  });
  const onHash = () => {
    const i = slideFromHash();
    if (i === null || i === cur) return;
    closeOverview();
    go(i, 0, { push: false, dir: i > cur ? 1 : -1 });
  };
  window.addEventListener('hashchange', onHash);
  window.addEventListener('popstate', onHash);

  // Print every slide fully revealed, then restore the current step.
  window.addEventListener('beforeprint', () => slides.forEach((_, i) => applyStep(i, total(i))));
  window.addEventListener('afterprint', () => {
    slides.forEach((_, i) => applyStep(i, mode === 'present' && i === cur ? step : total(i)));
  });

  const start = slideFromHash();
  cur = start === null ? 0 : start;
  setMode(mode);
})();
