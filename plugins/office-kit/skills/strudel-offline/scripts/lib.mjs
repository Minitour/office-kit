#!/usr/bin/env node
/**
 * Offline Strudel → WAV renderer.
 * Pattern eval: @strudel/core + mini + tonal + transpiler
 * Audio: official Dough engine (packages/supradough/dough-export.mjs)
 *
 * AGPL-3.0-or-later — https://codeberg.org/uzu/strudel
 */
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { evaluate, evalScope, Pattern, silence, stack } from '@strudel/core';
import { miniAllStrings } from '@strudel/mini';
import { transpiler } from '@strudel/transpiler';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const DEFAULT_CPS = 0.5;
const WAVEFORMS = new Set([
  'sine',
  'saw',
  'zaw',
  'sawtooth',
  'zawtooth',
  'supersaw',
  'tri',
  'triangle',
  'pulse',
  'square',
  'pulze',
  'dust',
  'crackle',
  'impulse',
  'white',
  'brown',
  'pink',
]);

// REPL drum names → Dough synths (no CDN samples).
const DRUM_SYNTH = {
  bd: { s: 'sine', note: 'c2', decay: 0.28, sustain: 0, release: 0.05, lpf: 280, penv: 28, pdecay: 0.08, gain: 0.9 },
  kick: { s: 'sine', note: 'c2', decay: 0.28, sustain: 0, lpf: 280, penv: 28, pdecay: 0.08, gain: 0.9 },
  sd: { s: 'white', decay: 0.14, sustain: 0, release: 0.04, hpf: 500, lpf: 5000, gain: 0.45 },
  sn: { s: 'white', decay: 0.14, sustain: 0, hpf: 500, lpf: 5000, gain: 0.45 },
  cp: { s: 'white', decay: 0.1, sustain: 0, hpf: 900, gain: 0.4 },
  clap: { s: 'white', decay: 0.1, sustain: 0, hpf: 900, gain: 0.4 },
  hh: { s: 'white', decay: 0.035, sustain: 0, hpf: 8000, gain: 0.22 },
  oh: { s: 'white', decay: 0.18, sustain: 0, hpf: 6500, gain: 0.22 },
  cb: { s: 'triangle', note: 'g5', decay: 0.16, sustain: 0, gain: 0.55 },
  cowbell: { s: 'triangle', note: 'g5', decay: 0.16, sustain: 0, gain: 0.55 },
  rim: { s: 'square', note: 'c5', decay: 0.04, sustain: 0, hpf: 1800, gain: 0.28 },
};

function parseArgs(argv) {
  const args = { seconds: 16, sr: 48000, cps: null, input: null, output: null };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--seconds' || a === '-d') args.seconds = Number(argv[++i]);
    else if (a === '--sr' || a === '-r') args.sr = Number(argv[++i]);
    else if (a === '--cps') args.cps = Number(argv[++i]);
    else if (a === '--help' || a === '-h') args.help = true;
    else rest.push(a);
  }
  args.input = rest[0] ? resolve(rest[0]) : null;
  args.output = rest[1] ? resolve(rest[1]) : null;
  return args;
}

function usage() {
  console.log(`Usage: render.mjs <pattern.js> <out.wav> [--seconds 16] [--sr 48000] [--cps 0.5]`);
}

async function loadDough() {
  const require = createRequire(import.meta.url);
  try {
    const pkg = dirname(require.resolve('supradough/package.json'));
    const mod = await import(resolve(pkg, 'dough.mjs'));
    if (mod.Dough) return mod.Dough;
  } catch {
    // published package may omit source; fall through
  }
  try {
    const mod = await import('supradough');
    if (mod.Dough) return mod.Dough;
  } catch {
    // vite worklet entry is not Node-safe
  }
  const vendor = await import(resolve(SCRIPT_DIR, 'vendor/dough.mjs'));
  return vendor.Dough;
}

function aliasDrums(value) {
  const name = String(value.s ?? '');
  const mapped = DRUM_SYNTH[name];
  if (!mapped) return value;
  if (WAVEFORMS.has(name)) return value;
  return { ...mapped, ...value, s: mapped.s, note: value.note ?? mapped.note };
}

function writeWav16(path, left, right, sampleRate) {
  const n = left.length;
  const dataSize = n * 2 * 2;
  const buf = Buffer.alloc(44 + dataSize);
  buf.write('RIFF', 0);
  buf.writeUInt32LE(36 + dataSize, 4);
  buf.write('WAVE', 8);
  buf.write('fmt ', 12);
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20);
  buf.writeUInt16LE(2, 22);
  buf.writeUInt32LE(sampleRate, 24);
  buf.writeUInt32LE(sampleRate * 4, 28);
  buf.writeUInt16LE(4, 32);
  buf.writeUInt16LE(16, 34);
  buf.write('data', 36);
  buf.writeUInt32LE(dataSize, 40);
  let o = 44;
  for (let i = 0; i < n; i++) {
    const l = Math.max(-1, Math.min(1, left[i]));
    const r = Math.max(-1, Math.min(1, right[i]));
    buf.writeInt16LE((l * 0x7fff) | 0, o);
    buf.writeInt16LE((r * 0x7fff) | 0, o + 2);
    o += 4;
  }
  return writeFile(path, buf);
}

async function setupScope(state) {
  await evalScope(import('@strudel/core'), import('@strudel/mini'), import('@strudel/tonal'));
  miniAllStrings();

  const pPatterns = {};
  let anon = 0;

  Pattern.prototype.p = function p(id) {
    if (typeof id === 'string' && (id.startsWith('_') || id.endsWith('_'))) {
      return silence;
    }
    if (id === '$') id = `$${anon++}`;
    pPatterns[id] = this;
    return this;
  };

  const setCps = (cps) => {
    state.cps = Number(cps) || DEFAULT_CPS;
  };
  const setCpm = (cpm) => setCps(Number(cpm) / 60);

  Object.assign(globalThis, {
    setCps,
    setcps: setCps,
    setCpm,
    setcpm: setCpm,
    hush: () => {
      for (const k of Object.keys(pPatterns)) delete pPatterns[k];
      return silence;
    },
  });

  return pPatterns;
}

function collectPattern(evaluated, pPatterns) {
  const parts = Object.values(pPatterns).filter(Boolean);
  if (parts.length) return stack(...parts);
  if (evaluated && typeof evaluated.queryArc === 'function') return evaluated;
  throw new Error('No pattern returned. Use $: lines or end the file with a pattern expression.');
}

function hapSeconds(hap, cps) {
  const begin = Number(hap.whole?.begin ?? hap.part?.begin ?? 0);
  const duration = Number(hap.duration ?? 0);
  return { begin: begin / cps, duration: duration / cps };
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help || !args.input || !args.output) {
    usage();
    process.exit(args.help ? 0 : 1);
  }
  if (!(args.seconds > 0) || !(args.sr > 0)) {
    console.error('Error: --seconds and --sr must be positive');
    process.exit(1);
  }

  const code = await readFile(args.input, 'utf8');
  const state = { cps: args.cps ?? DEFAULT_CPS };
  const pPatterns = await setupScope(state);

  let evaluated;
  try {
    const result = await evaluate(code, transpiler, {
      wrapAsync: false,
      addReturn: true,
      emitMiniLocations: false,
      emitWidgets: false,
    });
    evaluated = result.pattern;
  } catch (err) {
    console.error(`Eval error: ${err.message}`);
    process.exit(1);
  }

  const cps = args.cps ?? state.cps ?? DEFAULT_CPS;
  const pattern = collectPattern(evaluated, pPatterns);
  const cycles = args.seconds * cps;
  const haps = pattern
    .queryArc(0, cycles)
    .filter((h) => h?.value && (h.value.s != null || h.value.note != null || h.value.n != null));

  const Dough = await loadDough();
  const dough = new Dough(args.sr);
  let skipped = 0;
  for (const hap of haps) {
    const { begin, duration } = hapSeconds(hap, cps);
    const value = aliasDrums({ ...hap.value, _begin: begin, _duration: Math.max(duration, 1 / args.sr) });
    if (!WAVEFORMS.has(String(value.s)) && !DRUM_SYNTH[hap.value.s]) {
      skipped += 1;
    }
    dough.scheduleSpawn(value);
  }

  const frames = Math.ceil(args.seconds * args.sr);
  const left = new Float32Array(frames);
  const right = new Float32Array(frames);
  const t0 = performance.now();
  process.stdout.write(`render ${args.seconds}s @ ${args.sr} Hz, cps=${cps}, haps=${haps.length}\n`);
  while (dough.t < frames) {
    dough.update();
    const i = dough.t - 1;
    if (i >= 0 && i < frames) {
      left[i] = dough.out[0];
      right[i] = dough.out[1];
    }
    if (dough.t % args.sr === 0) process.stdout.write('.');
  }
  const took = (performance.now() - t0) / 1000;
  process.stdout.write('\n');

  await mkdir(dirname(args.output), { recursive: true });
  await writeWav16(args.output, left, right, args.sr);

  console.log(
    JSON.stringify(
      {
        output: args.output,
        seconds: args.seconds,
        sampleRate: args.sr,
        cps,
        haps: haps.length,
        skippedUnknownSounds: skipped,
        renderSeconds: Number(took.toFixed(2)),
        speed: `${(args.seconds / took).toFixed(2)}x`,
      },
      null,
      2,
    ),
  );
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
