#!/usr/bin/env node
/**
 * Capture a running Slidev preview into one self-contained HTML file: every
 * slide as real DOM (text stays selectable and commentable), the CSS the
 * slides use, images and web fonts inlined as data URIs, and a small
 * dependency-free player (player/player.js) for steps, overview, `#n` links,
 * fullscreen, and print.
 *
 * How it stays generic across decks: it drives Slidev's own navigation
 * (window.__slidev__.nav), steps through every click of every slide, and
 * records only what changes — each element's class and style attribute per
 * step. v-click, v-after, v-clicks, .hide, and code line highlights are all
 * class toggles, so they replay without knowing Slidev internals. Content
 * that is mounted or unmounted by a click (v-if, v-switch) shows in its final
 * state and is reported as a warning.
 *
 * Driven by scripts/presentation/deck.py export --format html; not meant to
 * be run by hand. Prints one JSON document on stdout. Exit 3 when
 * playwright-chromium is missing.
 *
 *   node export-html.mjs --base http://localhost:3030 --out dist/slides.html \
 *        [--no-embed-fonts] [--no-prune] [--settle 900] [--step-settle 250]
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = {};
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
  const key = argv[i];
  if (!key.startsWith('--')) continue;
  const next = argv[i + 1];
  if (next === undefined || next.startsWith('--')) {
    args[key.slice(2)] = true;
  } else {
    args[key.slice(2)] = next;
    i++;
  }
}

let chromium;
try {
  ({ chromium } = await import('playwright-chromium'));
} catch (error) {
  console.log(
    JSON.stringify({
      error: 'playwright-chromium is not installed in the workspace',
      detail: String(error && error.message ? error.message : error),
    }),
  );
  process.exit(3);
}

const base = String(args.base || 'http://localhost:3030').replace(/\/+$/, '');
const out = String(args.out || 'dist/slides.html');
const settle = Number(args.settle || 900);
const stepSettle = Number(args['step-settle'] || 250);
const embedFonts = !args['no-embed-fonts'];
const prune = !args['no-prune'];
const playerCss = readFileSync(path.join(here, 'player', 'player.css'), 'utf8');
const playerJs = readFileSync(path.join(here, 'player', 'player.js'), 'utf8');

const fail = (message) => {
  console.log(JSON.stringify({ error: message }));
  process.exit(1);
};

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1280, height: 720 },
  colorScheme: 'light',
  deviceScaleFactor: 1,
});
const page = await context.newPage();
await page.goto(`${base}/1`, { waitUntil: 'networkidle' });
try {
  await page.waitForFunction(() => window.__slidev__ && window.__slidev__.nav, null, { timeout: 15000 });
  await page.waitForSelector('.slidev-page-1 .slidev-layout', { timeout: 15000 });
} catch {
  await browser.close();
  fail(`no Slidev deck answered at ${base}`);
}

const meta = await page.evaluate(() => {
  const { nav, configs } = window.__slidev__;
  const unref = (v) => (v && typeof v === 'object' && 'value' in v ? v.value : v);
  // Slidev sizes #slide-content itself; match it rather than re-deriving.
  const stage = document.querySelector('#slide-content');
  const width = parseFloat(stage && stage.style.width) || Number(configs.canvasWidth) || 980;
  const ratio = Number(configs.aspectRatio) || 16 / 9;
  return {
    total: unref(nav.total),
    width,
    height: parseFloat(stage && stage.style.height) || Math.round(width / ratio),
    title: configs.title || document.title || 'Slides',
    htmlClass: document.documentElement.className,
    htmlStyle: '',
    bodyClass: document.body.className,
    lang: document.documentElement.lang || 'en',
  };
});

const slides = [];
const warnings = [];

for (let no = 1; no <= meta.total; no++) {
  await page.evaluate((n) => window.__slidev__.nav.go(n, 0), no);
  try {
    await page.waitForSelector(`.slidev-page-${no} .slidev-layout`, { timeout: 10000 });
  } catch {
    warnings.push(`slide ${no}: did not render; skipped`);
    continue;
  }
  await page.waitForTimeout(settle);
  await page.evaluate(() => document.fonts && document.fonts.ready);

  // Tag every element of the stage at step 0 and read the click count.
  const totalClicks = await page.evaluate((n) => {
    const stage = document.querySelector('#slide-content');
    let i = 0;
    for (const el of stage.querySelectorAll('*')) el.setAttribute('data-okx', `${n}-${i++}`);
    const unref = (v) => (v && typeof v === 'object' && 'value' in v ? v.value : v);
    window.__okRecord = {};
    return Number(unref(window.__slidev__.nav.clicksTotal)) || 0;
  }, no);

  const record = () =>
    page.evaluate((n) => {
      const stage = document.querySelector('#slide-content');
      const seen = [];
      for (const el of stage.querySelectorAll('[data-okx]')) {
        if (el.closest('.slidev-page') && !el.closest(`.slidev-page-${n}`)) continue;
        const id = el.getAttribute('data-okx');
        seen.push(id);
        (window.__okRecord[id] ||= []).push([el.getAttribute('class'), el.getAttribute('style')]);
      }
      return seen.length;
    }, no);

  const counts = [await record()];
  for (let k = 1; k <= totalClicks; k++) {
    await page.evaluate(() => window.__slidev__.nav.next());
    await page.waitForTimeout(stepSettle);
    counts.push(await record());
  }

  const captured = await page.evaluate(
    ({ n, steps }) => {
      const stage = document.querySelector('#slide-content');
      const clone = stage.cloneNode(true);
      for (const other of clone.querySelectorAll('.slidev-page')) {
        if (!other.classList.contains(`slidev-page-${n}`)) other.remove();
      }
      // Slidev's drawing layer and any leftover transition wrappers.
      clone.querySelectorAll('.slidev-drawings, [class*="-leave-"]').forEach((el) => el.remove());
      const current = clone.querySelector(`.slidev-page-${n}`);
      if (current) {
        current.style.removeProperty('user-select');
        if (!current.getAttribute('style')) current.removeAttribute('style');
      }
      // Keep the recorded attributes that vary; drop the rest of the tags.
      const els = {};
      let appeared = 0;
      for (const [id, rows] of Object.entries(window.__okRecord)) {
        if (rows.length !== steps + 1) {
          appeared++;
          continue;
        }
        const c = rows.map((r) => r[0]);
        const s = rows.map((r) => r[1]);
        const rec = {};
        if (c.some((v) => v !== c[0])) rec.c = c;
        if (s.some((v) => v !== s[0])) rec.s = s;
        if (rec.c || rec.s) els[id] = rec;
      }
      for (const el of clone.querySelectorAll('[data-okx]')) {
        if (!(el.getAttribute('data-okx') in els)) el.removeAttribute('data-okx');
      }
      // Slidev routes (/3, /3?clicks=1) become in-document anchors.
      for (const a of clone.querySelectorAll('a[href]')) {
        const url = new URL(a.getAttribute('href'), location.href);
        const m = /^\/(\d+)\/?$/.exec(url.pathname);
        if (url.origin === location.origin && m) {
          a.setAttribute('href', `#${m[1]}`);
          a.removeAttribute('target');
        }
      }
      clone.removeAttribute('data-okx');
      clone.style.removeProperty('--slidev-slide-scale');
      const heading = current && current.querySelector('h1, h2, h3');
      const nav = window.__slidev__.nav;
      const unref = (v) => (v && typeof v === 'object' && 'value' in v ? v.value : v);
      const route = (unref(nav.slides) || [])[n - 1];
      const fmTitle = route && route.meta && route.meta.slide && route.meta.slide.title;
      return {
        html: clone.outerHTML,
        els,
        appeared,
        title: String(fmTitle || (heading ? heading.textContent : '') || '').replace(/\s+/g, ' ').trim(),
      };
    },
    { n: no, steps: totalClicks },
  );
  if (captured.appeared || new Set(counts).size > 1) {
    warnings.push(
      `slide ${no}: content is added or removed by clicks (v-if / v-switch); the export shows its final state`,
    );
  }
  slides.push({ no, total: totalClicks, ...captured });
}

if (!slides.length) {
  await browser.close();
  fail('no slide rendered');
}

// ── CSS: keep what the captured slides use, inline assets and fonts ─────────
const assets = await page.evaluate(
  async ({ captured, prune, embedFonts }) => {
    const probe = document.createElement('div');
    probe.setAttribute('aria-hidden', 'true');
    probe.style.cssText = 'position:absolute;left:-100000px;top:0;width:1px;height:1px;overflow:hidden;';
    // Every captured slide, with each varying element carrying the union of
    // its step classes, so rules for hidden steps survive pruning.
    for (const slide of captured) {
      const holder = document.createElement('div');
      holder.innerHTML = slide.html;
      for (const [id, rec] of Object.entries(slide.els)) {
        const el = holder.querySelector(`[data-okx="${id}"]`);
        if (!el || !rec.c) continue;
        const union = new Set();
        rec.c.forEach((v) => (v || '').split(/\s+/).filter(Boolean).forEach((c) => union.add(c)));
        el.setAttribute('class', [...union].join(' '));
      }
      holder.querySelectorAll('[id]').forEach((el) => {
        if (el.id !== 'slide-content' && el.id !== 'slideshow') el.removeAttribute('id');
      });
      probe.append(...holder.childNodes);
    }
    document.body.append(probe);
    // Lay the probe out so every face the slides need starts loading.
    void probe.offsetHeight;
    await new Promise((r) => requestAnimationFrame(() => r()));
    await document.fonts.ready;
    await new Promise((r) => setTimeout(r, 300));

    const DYNAMIC =
      /::?(?:before|after|placeholder|selection|marker|first-letter|first-line|backdrop|file-selector-button|-webkit-[\w-]+|-moz-[\w-]+)|:(?:hover|focus-visible|focus-within|focus|active|visited|link|any-link|target|checked|indeterminate|disabled|enabled|invalid|valid|placeholder-shown|autofill|fullscreen|open|popover-open)\b/g;
    const used = (selectorText) => {
      if (!prune) return true;
      const sel = selectorText.replace(DYNAMIC, '').replace(/\(\s*\)/g, '(*)');
      try {
        for (const el of document.querySelectorAll(sel.trim() || '*')) {
          if (el === document.documentElement || el === document.body || probe.contains(el)) return true;
        }
        return false;
      } catch {
        return true;
      }
    };

    // "U+0000-00FF" in a sheet reads back as "U+0-FF" from the FontFace API.
    const normRange = (range) =>
      String(range || 'u+0-10ffff')
        .toLowerCase()
        .replace(/\s+/g, '')
        .replace(/(^|[+\-,])0+(?=[0-9a-f?])/g, '$1');
    const faceKey = (family, style, weight, range) =>
      `${family.replace(/^["']|["']$/g, '').toLowerCase()}|${style || 'normal'}|${String(weight || '400').trim()}|${normRange(range)}`;
    const loadedFaces = new Set();
    const loadedFamilies = new Set();
    for (const face of document.fonts) {
      if (face.status !== 'loaded') continue;
      loadedFamilies.add(face.family.replace(/^["']|["']$/g, '').toLowerCase());
      loadedFaces.add(faceKey(face.family, face.style, face.weight, face.unicodeRange));
    }

    const external = [];
    const serialize = (rules) => {
      const outText = [];
      for (const rule of rules) {
        const type = rule.constructor.name;
        if (type === 'CSSStyleRule') {
          if (used(rule.selectorText)) outText.push(rule.cssText);
        } else if (type === 'CSSImportRule') {
          let inner = null;
          try {
            inner = rule.styleSheet && rule.styleSheet.cssRules;
          } catch {
            inner = null;
          }
          if (inner) outText.push(serialize(inner));
          else external.push(new URL(rule.href, rule.parentStyleSheet.href || location.href).href);
        } else if (type === 'CSSFontFaceRule') {
          const family = rule.style.getPropertyValue('font-family').replace(/^["']|["']$/g, '').toLowerCase();
          if (!prune || loadedFamilies.has(family)) outText.push(rule.cssText);
        } else if ('cssRules' in rule && type !== 'CSSKeyframesRule') {
          // @media, @supports, @layer {…}, @container: keep when anything inside survives.
          const body = serialize(rule.cssRules);
          if (body.trim()) {
            const head = rule.cssText.slice(0, rule.cssText.indexOf('{'));
            outText.push(`${head}{\n${body}\n}`);
          }
        } else if (type !== 'CSSCharsetRule') {
          outText.push(rule.cssText);
        }
      }
      return outText.join('\n');
    };

    const sheets = [];
    for (const sheet of document.styleSheets) {
      if (sheet.ownerNode && sheet.ownerNode.closest && sheet.ownerNode.closest('#ok-probe')) continue;
      if (sheet.disabled) continue;
      let rules = null;
      try {
        rules = sheet.cssRules;
      } catch {
        rules = null;
      }
      if (rules) {
        sheets.push({ base: sheet.href || location.href, text: serialize(rules) });
      } else if (sheet.href) {
        external.push(sheet.href);
      }
    }
    probe.remove();

    // Data URIs for every same-origin url() in the kept CSS and every asset
    // reference in the captured markup.
    const cache = new Map();
    const toData = async (url) => {
      if (cache.has(url)) return cache.get(url);
      const job = (async () => {
        try {
          const res = await fetch(url);
          if (!res.ok) return null;
          const blob = await res.blob();
          return await new Promise((resolve) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => resolve(null);
            reader.readAsDataURL(blob);
          });
        } catch {
          return null;
        }
      })();
      cache.set(url, job);
      return job;
    };
    const URL_RE = /url\(\s*(['"]?)([^'")]+)\1\s*\)/g;
    const inlineCss = async (text, baseUrl, sameOriginOnly = true) => {
      const found = new Map();
      for (const m of text.matchAll(URL_RE)) {
        const raw = m[2].trim();
        if (/^(data:|#|about:)/i.test(raw)) continue;
        let abs;
        try {
          abs = new URL(raw, baseUrl);
        } catch {
          continue;
        }
        if (sameOriginOnly && abs.origin !== location.origin) continue;
        found.set(raw, abs.href);
      }
      const missing = [];
      for (const [raw, abs] of found) {
        const data = await toData(abs);
        if (data) text = text.split(raw).join(data);
        else missing.push(raw);
      }
      return { text, missing };
    };

    const missing = [];
    const css = [];
    for (const sheet of sheets) {
      const res = await inlineCss(sheet.text, sheet.base);
      missing.push(...res.missing);
      css.push(res.text);
    }

    // Web fonts from cross-origin sheets (Google Fonts and the like): fetch
    // the sheet, keep the faces the slides loaded, merge weights that share
    // one variable file, and inline the files.
    const links = [];
    let fontsEmbedded = 0;
    for (const href of [...new Set(external)]) {
      if (!embedFonts) {
        links.push(href);
        continue;
      }
      let text = null;
      try {
        const res = await fetch(href);
        text = res.ok ? await res.text() : null;
      } catch {
        text = null;
      }
      if (text === null) {
        links.push(href);
        continue;
      }
      const groups = new Map();
      const rest = [];
      for (const block of text.replace(/\/\*[\s\S]*?\*\//g, '').split('}')) {
        if (!block.includes('{')) continue;
        const [head, body] = block.split('{');
        if (!/@font-face/.test(head)) {
          rest.push(`${head}{${body}}`);
          continue;
        }
        const prop = (name) => {
          const m = new RegExp(`${name}\\s*:\\s*([^;]+)`).exec(body);
          return m ? m[1].trim() : '';
        };
        const family = prop('font-family').replace(/^["']|["']$/g, '');
        const style = prop('font-style') || 'normal';
        const range = prop('unicode-range');
        const weight = prop('font-weight') || '400';
        if (prune && !loadedFaces.has(faceKey(family, style, weight, range))) continue;
        const src = prop('src');
        const gkey = `${family}|${style}|${normRange(range)}|${src}`;
        const g = groups.get(gkey) || { family, style, range, src, display: prop('font-display'), weights: [] };
        g.weights.push(...weight.split(/\s+/).map(Number).filter((w) => !Number.isNaN(w)));
        groups.set(gkey, g);
      }
      let faces = '';
      for (const g of groups.values()) {
        const lo = Math.min(...g.weights);
        const hi = Math.max(...g.weights);
        faces += `@font-face{font-family:"${g.family}";font-style:${g.style};font-weight:${lo === hi ? lo : `${lo} ${hi}`};${g.display ? `font-display:${g.display};` : ''}src:${g.src};${g.range ? `unicode-range:${g.range};` : ''}}\n`;
      }
      const res = await inlineCss(faces + rest.join('\n'), href, false);
      missing.push(...res.missing);
      fontsEmbedded += groups.size;
      if (res.text.trim()) css.unshift(res.text);
    }

    // Markup assets: <img src>, <source srcset>, SVG <image href>, inline style url().
    const htmls = [];
    for (const slide of captured) {
      const holder = document.createElement('template');
      holder.innerHTML = slide.html;
      const root = holder.content;
      for (const img of root.querySelectorAll('img[src], video[poster], image[href], use[href]')) {
        const attr = img.tagName.toLowerCase() === 'video' ? 'poster' : img.hasAttribute('src') ? 'src' : 'href';
        const raw = img.getAttribute(attr);
        if (!raw || /^(data:|#)/.test(raw)) continue;
        const abs = new URL(raw, location.href);
        const data = abs.origin === location.origin ? await toData(abs.href) : null;
        if (data) img.setAttribute(attr, data);
        else if (abs.origin === location.origin) missing.push(raw);
      }
      for (const el of root.querySelectorAll('[srcset]')) el.removeAttribute('srcset');
      for (const el of root.querySelectorAll('[style*="url("]')) {
        const res = await inlineCss(el.getAttribute('style'), location.href);
        el.setAttribute('style', res.text);
        missing.push(...res.missing);
      }
      for (const rec of Object.values(slide.els)) {
        if (!rec.s) continue;
        for (let i = 0; i < rec.s.length; i++) {
          if (rec.s[i] && rec.s[i].includes('url(')) rec.s[i] = (await inlineCss(rec.s[i], location.href)).text;
        }
      }
      htmls.push(holder.innerHTML);
    }

    return { css: css.join('\n'), links, htmls, els: captured.map((s) => s.els), missing: [...new Set(missing)], fontsEmbedded };
  },
  { captured: slides, prune, embedFonts },
);

for (const raw of assets.missing) warnings.push(`asset not inlined: ${raw}`);

// ── assemble ────────────────────────────────────────────────────────────────
const esc = (s) =>
  String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const { width: W, height: H } = meta;
const sections = slides
  .map((slide, i) => {
    const label = `Slide ${i + 1} of ${slides.length}${slide.title ? `: ${slide.title}` : ''}`;
    return [
      `<section class="ok-slide" id="${i + 1}" data-title="${esc(slide.title)}" role="group" aria-roledescription="slide" aria-label="${esc(label)}">`,
      `<div class="ok-canvas" style="width:${W}px;height:${H}px"><div class="ok-canvas-anim">`,
      assets.htmls[i],
      '</div></div>',
      '</section>',
    ].join('\n');
  })
  .join('\n');
const stepsJson = JSON.stringify(slides.map((s, i) => ({ total: s.total, els: assets.els[i] }))).replace(
  /</g,
  '\\u003c',
);
const html = `<!doctype html>
<html lang="${esc(meta.lang)}" class="${esc(meta.htmlClass)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="generator" content="OfficeKit deck.py export --format html">
<title>${esc(meta.title)}</title>
${assets.links.map((href) => `<link rel="stylesheet" href="${esc(href)}">`).join('\n')}
<style>
${assets.css.replace(/<\/style/gi, '<\\/style')}
</style>
<style>
${playerCss}
@page { size: ${W}px ${H}px; margin: 0; }
#slide-content { width: ${W}px; height: ${H}px; }
</style>
</head>
<body class="${esc(meta.bodyClass)}">
<main id="ok-deck" data-width="${W}" data-height="${H}" aria-label="${esc(meta.title)}">
${sections}
</main>
<script type="application/json" id="ok-steps">${stepsJson}</script>
<script>
${playerJs.replace(/<\/script/gi, '<\\/script')}
</script>
</body>
</html>
`;

mkdirSync(path.dirname(path.resolve(out)), { recursive: true });
writeFileSync(out, html, 'utf8');

// ── verify: reopen the file offline and walk every slide ────────────────────
const verify = { externalRequests: [], errors: [], blank: [] };
{
  const offline = await browser.newContext({ viewport: { width: W, height: H } });
  await offline.route('**/*', (route) => {
    const u = route.request().url();
    if (u.startsWith('file:') || u.startsWith('data:') || u.startsWith('blob:')) return route.continue();
    verify.externalRequests.push(u);
    return route.abort();
  });
  const check = await offline.newPage();
  check.on('pageerror', (e) => verify.errors.push(String(e && e.message ? e.message : e)));
  await check.goto(pathToFileURL(path.resolve(out)).href);
  await check.waitForTimeout(300);
  // Walk every slide by #n in both modes: browse (the default) scrolls to
  // it, present shows it alone. Either way the counter must follow.
  for (const mode of ['browse', 'present']) {
    const on = await check.evaluate((m) => {
      if (!document.documentElement.classList.contains(`ok-${m}`)) {
        document.dispatchEvent(new KeyboardEvent('keydown', { key: m[0], bubbles: true }));
      }
      return document.documentElement.classList.contains(`ok-${m}`);
    }, mode);
    if (!on) {
      verify.errors.push(`could not switch to ${mode} mode`);
      continue;
    }
    for (let n = 1; n <= slides.length; n++) {
      await check.evaluate((i) => {
        location.hash = `#${i}`;
      }, n);
      await check.waitForTimeout(60);
      const shown = await check.evaluate(
        ({ i, m, count }) => {
          const s = document.getElementById(String(i));
          const box = s && s.querySelector('#slide-content');
          if (!box) return false;
          if (m === 'present' && !s.classList.contains('ok-active')) return false;
          const counter = document.querySelector('.ok-count');
          if (!counter || counter.textContent !== `${i} / ${count}`) return false;
          const r = box.getBoundingClientRect();
          const content = box.textContent.trim().length + box.querySelectorAll('img, svg, canvas').length;
          return r.width > 0 && r.height > 0 && content > 0;
        },
        { i: n, m: mode, count: slides.length },
      );
      if (!shown) verify.blank.push(`${n} (${mode})`);
    }
  }
  await offline.close();
}
await browser.close();
for (const u of verify.externalRequests) warnings.push(`opened offline, the file still requested ${u}`);
for (const e of verify.errors) warnings.push(`player error: ${e}`);
for (const n of verify.blank) warnings.push(`slide ${n}: not shown by the player`);
console.log(
  JSON.stringify({
    out,
    bytes: Buffer.byteLength(html, 'utf8'),
    slides: slides.length,
    steps: slides.reduce((a, s) => a + s.total, 0),
    width: W,
    height: H,
    fontsEmbedded: assets.fontsEmbedded,
    externalStylesheets: assets.links,
    warnings,
  }),
);
