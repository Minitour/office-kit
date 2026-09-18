#!/usr/bin/env node
/**
 * Render every slide of a running Slidev preview at the canvas size and
 * report what a static pass cannot see: content that extends past the layout
 * box, images that failed to load, and (with --dark) what the deck does under
 * prefers-color-scheme: dark. One PNG per slide lands in --out.
 *
 * Driven by scripts/presentation/deck.py audit; not meant to be run by hand.
 * Prints one JSON document on stdout. Exit 3 when playwright-chromium is
 * missing (the workspace installs it with each deck; export needs it too).
 *
 *   node render-audit.mjs --base http://localhost:3030 --count 18 \
 *        --width 980 --height 551 --out reports/render [--dark] [--settle 1200]
 */
import { mkdirSync } from 'node:fs';
import path from 'node:path';

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
const count = Number(args.count || 0);
const width = Number(args.width || 980);
const height = Number(args.height || Math.round((width * 9) / 16));
const settle = Number(args.settle || 1200);
const scheme = args.dark ? 'dark' : 'light';
const out = String(args.out || 'reports/render');
mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width, height },
  colorScheme: scheme,
  deviceScaleFactor: 1,
});
const page = await context.newPage();
const slides = [];

for (let no = 1; no <= count; no++) {
  await page.goto(`${base}/${no}`, { waitUntil: 'networkidle' });
  // The scaffold's slide transition can leave the previous slide on screen;
  // wait for this page's own element rather than screenshotting on arrival.
  try {
    await page.waitForSelector(`.slidev-page-${no} .slidev-layout`, { timeout: 10000 });
  } catch {
    // Reported below as not found.
  }
  await page.waitForTimeout(settle);
  const info = await page.evaluate((pageNo) => {
    const layout = document.querySelector(`.slidev-page-${pageNo} .slidev-layout`);
    if (!layout) return { found: false };
    const box = layout.getBoundingClientRect();
    const clipped = (el) => {
      for (let node = el.parentElement; node && node !== layout; node = node.parentElement) {
        const style = getComputedStyle(node);
        if (/hidden|clip|scroll|auto/.test(style.overflowY) || /hidden|clip|scroll|auto/.test(style.overflowX)) {
          return true;
        }
      }
      return false;
    };
    const describe = (el) => {
      const cls = typeof el.className === 'string' ? el.className.trim().split(/\s+/).filter(Boolean).slice(0, 2) : [];
      return el.tagName.toLowerCase() + (cls.length ? '.' + cls.join('.') : '');
    };
    let worst = null;
    for (const el of layout.querySelectorAll('*')) {
      const b = el.getBoundingClientRect();
      if (b.width === 0 && b.height === 0) continue;
      if (clipped(el)) continue;
      const over = Math.max(b.bottom - box.bottom, b.right - box.right);
      if (over > 2 && (!worst || over > worst.by)) worst = { by: over, element: describe(el) };
    }
    const scrollOver = Math.max(
      layout.scrollHeight - layout.clientHeight,
      layout.scrollWidth - layout.clientWidth,
    );
    if (scrollOver > 2 && (!worst || scrollOver > worst.by)) {
      worst = { by: scrollOver, element: 'slidev-layout (scrollable)' };
    }
    const brokenImages = [...layout.querySelectorAll('img')]
      .filter((img) => img.complete && img.naturalWidth === 0)
      .map((img) => img.getAttribute('src'));
    return {
      found: true,
      overflow: Boolean(worst),
      by: worst ? Math.round(worst.by) : 0,
      element: worst ? worst.element : null,
      brokenImages,
      dark: document.documentElement.classList.contains('dark'),
    };
  }, no);
  const file = path.join(out, `slide-${String(no).padStart(2, '0')}.png`);
  await page.screenshot({ path: file });
  slides.push({ no, ...info, screenshot: file });
}

await browser.close();
console.log(JSON.stringify({ scheme, width, height, slides }));
