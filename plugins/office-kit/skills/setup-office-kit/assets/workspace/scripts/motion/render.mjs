// Frame driver for OfficeKit motion reels. Called by reel.py; not a public CLI.
//
//   node scripts/motion/render.mjs <project-dir> stills [t1,t2,...]
//   node scripts/motion/render.mjs <project-dir> animatic
//   node scripts/motion/render.mjs <project-dir> video [fps]
//   node scripts/motion/render.mjs <project-dir> poster [t]
//   node scripts/motion/render.mjs <project-dir> verify
//
// Add --format=landscape|vertical|square to any mode; the page gets
// ?format=... and re-lays itself out. The page's seek(t) paints one frame per
// call, so every mode is headless Chromium screenshots of the canvas, piped
// to ffmpeg where a movie is wanted.
//
// Outputs (all inside the project):
//   reports/stills/<format>/NN_<t>.png + contact.png   critique input
//   renders/<slug>[-<format>]-animatic.mp4              12 fps timing draft
//   renders/<slug>[-<format>].mp4                       final, with score
//   renders/<slug>[-<format>]-poster.png                one full-res frame
import { spawn, execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, rmSync, existsSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join, resolve, basename } from 'node:path';
import { pathToFileURL } from 'node:url';

const argv = process.argv.slice(2);
const flag = (name, fallback) => {
  const hit = argv.find((a) => a.startsWith(`--${name}=`));
  return hit ? hit.slice(name.length + 3) : fallback;
};
const [projectArg, mode = 'stills', arg] = argv.filter((a) => !a.startsWith('--'));
if (!projectArg) {
  console.error('usage: render.mjs <project-dir> <stills|animatic|video|poster|verify> [arg] [--format=...]');
  process.exit(2);
}
const here = resolve(projectArg);
const format = flag('format', 'landscape');
if (!['landscape', 'vertical', 'square'].includes(format)) {
  console.error(`unknown format ${format}; use landscape, vertical or square`);
  process.exit(2);
}
const outDir = join(here, flag('output-dir', 'renders'));
for (const need of ['index.html', 'timeline.js', 'score.mjs']) {
  if (!existsSync(join(here, need))) {
    console.error(`${join(here, need)} is missing; scaffold with reel.py new first`);
    process.exit(2);
  }
}

let chromium;
try {
  ({ chromium } = await import('playwright-chromium'));
} catch {
  console.error('playwright-chromium is not installed; run `npm install -w projects/<slug>` from the workspace root');
  process.exit(3);
}

const TL = createRequire(join(here, 'package.json'))('./timeline.js');
const VW = format === 'landscape' ? TL.width : TL.height;
const VH = format === 'vertical' ? TL.width : TL.height;
const suffix = format === 'landscape' ? '' : `-${format}`;
const name = basename(here);

// $CHROME points at another Chromium build (for example a cached headless
// shell) when Playwright's own download is unavailable.
const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {});
const page = await browser.newPage({ viewport: { width: VW, height: VH }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => { console.error('page error:', e.message); process.exitCode = 1; });
page.on('console', (m) => { if (m.type() === 'error') console.error('console:', m.text()); });
await page.goto(`${pathToFileURL(join(here, 'index.html')).href}?format=${format}`);
await page.evaluate(() => window.ready);
const canvas = page.locator('canvas');

async function frameAt(t) {
  await page.evaluate((tt) => window.seek(tt), t);
  return canvas.screenshot({ type: 'png' });
}

async function encode(fps, out, preset, crf) {
  const n = Math.round(TL.duration * fps);
  execFileSync('node', [join(here, 'score.mjs')], { stdio: 'inherit' });
  mkdirSync(outDir, { recursive: true });
  // Optional music bed (for example from the strudel-offline skill) sits
  // under the synthesized hits at -6 dB; the limiter keeps the sum below
  // clipping after AAC.
  const bed = join(here, 'media', 'music-bed.wav');
  const audio = existsSync(bed)
    ? ['-i', join(here, 'media', 'score.wav'), '-i', bed, '-filter_complex',
       '[2:a]volume=0.5[b];[1:a][b]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.89[a]',
       '-map', '0:v', '-map', '[a]']
    : ['-i', join(here, 'media', 'score.wav')];
  const ff = spawn('ffmpeg', [
    '-y', '-loglevel', 'error',
    '-f', 'image2pipe', '-framerate', String(fps), '-i', '-',
    ...audio,
    '-c:v', 'libx264', '-preset', preset, '-crf', String(crf), '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart',
    out,
  ], { stdio: ['pipe', 'inherit', 'inherit'] });
  const closed = new Promise((r) => ff.on('close', r));
  for (let i = 0; i < n; i++) {
    const buf = await frameAt(i / fps);
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % fps === 0) process.stdout.write(`\r${i}/${n} frames`);
  }
  ff.stdin.end();
  const code = await closed;
  if (code !== 0) { console.error(`\nffmpeg exited ${code}`); process.exitCode = 1; return; }
  console.log(`\nwrote ${out} (${n} frames)`);
}

if (mode === 'stills') {
  // Default: 20 evenly spaced moments, nudged off exact beats so frames show
  // motion in flight rather than only settled states.
  const times = arg
    ? arg.split(',').map(Number)
    : Array.from({ length: 20 }, (_, i) => +((i + 0.6) * TL.duration / 20).toFixed(2));
  const out = join(here, 'reports', 'stills', format);
  rmSync(out, { recursive: true, force: true });
  mkdirSync(out, { recursive: true });
  for (const [i, t] of times.entries()) {
    writeFileSync(join(out, `${String(i).padStart(2, '0')}_${t.toFixed(2)}.png`), await frameAt(t));
  }
  // Contact sheet: every still in time order, left to right, in one image.
  // Many ffmpeg builds lack drawtext, so the order is printed, not drawn.
  const cols = format === 'vertical' ? 7 : format === 'square' ? 5 : 4;
  const rows = Math.ceil(times.length / cols);
  console.log('order:', times.join(', '));
  execFileSync('ffmpeg', [
    '-y', '-loglevel', 'error', '-pattern_type', 'glob', '-i', join(out, '[0-9]*.png'),
    '-vf', `scale=${format === 'landscape' ? 640 : 400}:-1,tile=${cols}x${rows}:padding=6:color=white`,
    '-frames:v', '1', join(out, 'contact.png'),
  ]);
  console.log(`wrote ${times.length} stills + contact.png to ${out}`);
} else if (mode === 'animatic') {
  await encode(12, join(outDir, `${name}${suffix}-animatic.mp4`), 'ultrafast', 28);
} else if (mode === 'verify') {
  // seek(t) must be a pure function of t. Hidden state carried between frames
  // (a counter, a cached layout, an unbalanced ctx.save) shows up here as a
  // frame that depends on which frame came before it.
  const times = Array.from({ length: 24 }, (_, i) => +((i + 0.37) * TL.duration / 24).toFixed(3));
  const hash = async (t) => createHash('sha1').update(await frameAt(t)).digest('hex');
  const fwd = [];
  for (const t of times) fwd.push(await hash(t));
  const bad = [];
  for (const [i, t] of [...times.entries()].reverse()) if ((await hash(t)) !== fwd[i]) bad.push(t);
  for (const [i, t] of times.entries()) if ((await hash(t)) !== fwd[i]) bad.push(t);
  if (bad.length) { console.error(`${format}: non-deterministic at t =`, [...new Set(bad)].join(', ')); process.exitCode = 1; }
  else console.log(`${format}: deterministic, ${times.length} frames x 3 orders match`);
} else if (mode === 'poster') {
  const t = arg ? Number(arg) : (TL.tagline ?? TL.duration - 1) + 0.8;
  mkdirSync(outDir, { recursive: true });
  const out = join(outDir, `${name}${suffix}-poster.png`);
  writeFileSync(out, await frameAt(t));
  console.log(`wrote ${out} at t=${t}`);
} else if (mode === 'video') {
  await encode(Number(arg || TL.fps), join(outDir, `${name}${suffix}.mp4`), 'slow', 16);
} else {
  console.error(`unknown mode ${mode}`);
  process.exitCode = 2;
}
await browser.close();
