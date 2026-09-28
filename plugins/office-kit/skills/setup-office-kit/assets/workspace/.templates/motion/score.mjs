// Synthesizes the soundtrack from the same timeline the picture reads, so
// every pop, click and whoosh lands on the frame that causes it. Seeded
// noise, no samples: the render is identical every run.
import { mkdirSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const T = createRequire(import.meta.url)('./timeline.js');
const SR = 44100;
const N = Math.round(T.duration * SR);
const L = new Float32Array(N), R = new Float32Array(N);

let seed = 0x5ca1ab1e;
const rnd = () => {
  seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
  let x = Math.imul(seed ^ (seed >>> 15), 1 | seed);
  x = (x + Math.imul(x ^ (x >>> 7), 61 | x)) ^ x;
  return ((x ^ (x >>> 14)) >>> 0) / 4294967296 * 2 - 1;
};

function add(t0, dur, fn, gain = 1, pan = 0) {
  const s0 = Math.round(t0 * SR), n = Math.round(dur * SR);
  const gl = gain * Math.min(1, 1 - pan), gr = gain * Math.min(1, 1 + pan);
  for (let i = 0; i < n; i++) {
    const k = s0 + i;
    if (k < 0 || k >= N) continue;
    const v = fn(i / SR);
    L[k] += v * gl; R[k] += v * gr;
  }
}

const B = T.beat;

// ---- instruments ----

function kick(t0, g = 1) {
  let ph = 0;
  add(t0, 0.45, (x) => {
    const f = 45 + 95 * Math.exp(-x * 28);
    ph += 2 * Math.PI * f / SR;
    return Math.sin(ph) * Math.exp(-x * 7) * 0.9;
  }, g);
}
function clap(t0, g = 1) {
  let lp = 0;
  add(t0, 0.2, (x) => {
    const n = rnd();
    lp += 0.35 * (n - lp);
    const env = Math.exp(-x * 22) * (x < 0.012 ? 0.6 : 1);
    return (n - lp) * env * 0.5;
  }, g);
}
function hat(t0, g = 1, pan = 0) {
  let lp = 0;
  add(t0, 0.05, (x) => {
    const n = rnd();
    lp += 0.6 * (n - lp);
    return (n - lp) * Math.exp(-x * 90) * 0.35;
  }, g, pan);
}
function pop(t0, f0 = 950, g = 1, pan = 0) {
  let ph = 0;
  add(t0, 0.12, (x) => {
    ph += 2 * Math.PI * (f0 * (0.55 + 0.45 * Math.exp(-x * 40))) / SR;
    return Math.sin(ph) * Math.exp(-x * 38) * 0.5;
  }, g, pan);
}
function tick(t0, g = 1) {
  add(t0, 0.012, (x) => rnd() * Math.exp(-x * 500) * 0.25, g, 0.2);
}
function click(t0, g = 1) {
  add(t0, 0.03, (x) => (rnd() * 0.5 + Math.sin(2 * Math.PI * 2400 * x)) * Math.exp(-x * 220) * 0.4, g);
}
function whoosh(tHit, g = 1) {
  let lp = 0;
  const pre = 0.42, post = 0.18;
  add(tHit - pre, pre + post, (x) => {
    const u = x / pre;
    const env = u < 1 ? Math.pow(u, 2.2) : Math.exp(-(x - pre) * 18);
    const cut = 0.04 + 0.4 * Math.min(1, u);
    lp += cut * (rnd() - lp);
    return lp * env * 0.9;
  }, g);
}
function chime(t0, g = 1) {
  const fs = [1046.5, 1318.5, 1568, 2093];
  add(t0, 2.4, (x) => fs.reduce((s, f, i) => s + Math.sin(2 * Math.PI * f * x) * Math.exp(-x * (1.6 + i * 0.7)) / (i + 1.5), 0) * 0.5, g);
}

const midi = (m) => 440 * Math.pow(2, (m - 69) / 12);
function padChord(t0, dur, notes, g = 1) {
  add(t0, dur, (x) => {
    const att = Math.min(1, x / 0.25), rel = Math.min(1, (dur - x) / 0.35);
    let v = 0;
    notes.forEach((m, i) => {
      const f = midi(m);
      // Two detuned triangles per note: soft, wide, never buzzy.
      for (const d of [-0.12, 0.12]) {
        const p = ((f * (1 + d / 100) * x) % 1);
        v += (4 * Math.abs(p - 0.5) - 1) * (i % 2 ? 0.8 : 1);
      }
    });
    return v * att * rel * 0.045;
  }, g);
}
function bassNote(t0, dur, m, g = 1) {
  const f = midi(m);
  add(t0, dur, (x) => {
    const env = Math.min(1, x / 0.01) * Math.exp(-x * 5);
    return (Math.sin(2 * Math.PI * f * x) + 0.3 * Math.sin(4 * Math.PI * f * x)) * env * 0.35;
  }, g);
}

// ---- arrangement ----
// Replace freely. Keep every hit keyed to a T.* event so picture and sound
// stay locked; change key, tempo feel and instruments per reel so each film
// has its own voice.

// Am F C G, one chord per bar (4 beats), resolving to C on the lockup.
const prog = [
  { root: 45, pad: [57, 60, 64, 69] },
  { root: 41, pad: [57, 60, 65, 69] },
  { root: 48, pad: [55, 60, 64, 67] },
  { root: 43, pad: [55, 59, 62, 67] },
];
const bars = Math.floor(T.lockup / (4 * B));
for (let bar = 0; bar < bars; bar++) {
  const c = prog[bar % 4];
  const t0 = bar * 4 * B;
  padChord(t0, 4 * B + 0.05, c.pad);
  for (let e = 0; e < 8; e++) {
    if (bar === 0 && e < 4) continue; // bass enters once the mark is built
    bassNote(t0 + e * B / 2, B / 2, c.root + (e % 4 === 3 ? 12 : 0), e % 2 ? 0.55 : 1);
  }
}
const tailStart = bars * 4 * B;
if (T.lockup > tailStart) padChord(tailStart, T.lockup - tailStart + 0.05, prog[bars % 4].pad);

const beats = Math.round(T.lockup / B);
for (let i = 0; i < beats; i++) {
  const t = i * B;
  if (i >= 2) kick(t, i % 4 === 0 ? 1 : 0.8);
  if (i >= 4 && i % 2 === 1) clap(t, 0.8);
  if (i >= 8) hat(t + B / 2, 0.8, (i % 4) / 4 - 0.4);
}

// Lockup: one big downbeat, the resolved chord, and the chime.
kick(T.lockup, 1.3);
clap(T.lockup, 0.7);
padChord(T.lockup, T.duration - T.lockup, [48, 55, 60, 64, 67, 72], 1.4);
bassNote(T.lockup, 1.6, 36, 1.3);
chime(T.lockup + 0.02, 0.9);

// ---- sound design, locked to the picture ----
T.pops.forEach((t, i) => pop(t, 700 + i * 140, 1, [-0.4, 0.4, -0.2, 0.2][i % 4]));
T.whooshes.forEach((t) => whoosh(t, 0.9));
T.words.forEach((t) => pop(t, 420, 0.8));

// ---- master ----
let peak = 0;
for (let i = 0; i < N; i++) {
  const fadeOut = Math.min(1, (N - i) / (0.8 * SR));
  L[i] = Math.tanh(L[i] * 1.2) * fadeOut;
  R[i] = Math.tanh(R[i] * 1.2) * fadeOut;
  peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
}
const norm = 0.79 / (peak || 1); // headroom for AAC overshoot

const buf = Buffer.alloc(44 + N * 4);
buf.write('RIFF', 0); buf.writeUInt32LE(36 + N * 4, 4); buf.write('WAVE', 8);
buf.write('fmt ', 12); buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(2, 22);
buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(SR * 4, 28); buf.writeUInt16LE(4, 32); buf.writeUInt16LE(16, 34);
buf.write('data', 36); buf.writeUInt32LE(N * 4, 40);
for (let i = 0; i < N; i++) {
  buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, L[i] * norm)) * 32767), 44 + i * 4);
  buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, R[i] * norm)) * 32767), 46 + i * 4);
}
mkdirSync(join(here, 'media'), { recursive: true });
writeFileSync(join(here, 'media', 'score.wav'), buf);
console.log(`media/score.wav: ${T.duration}s, peak normalized from ${peak.toFixed(2)}`);
