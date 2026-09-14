# Strudel offline — reference

Source of truth: [uzu/strudel](https://codeberg.org/uzu/strudel) (AGPL-3.0).

## How the official stack splits

| Layer | Package | Offline? |
| --- | --- | --- |
| Pattern language | `@strudel/core`, `@strudel/mini`, `@strudel/tonal` | Yes — pure JS |
| `$:` / mini-string rewrite | `@strudel/transpiler` | Yes |
| REPL tempo + `.p()` | Injected by the REPL, **not** core | We reimplement in `render.mjs` |
| Browser sound | `@strudel/webaudio` + `superdough` | No — needs AudioContext / worklets |
| Headless sound | `supradough` `Dough` | Yes — sample loop, no browser |
| Official WAV POC | `packages/supradough/dough-export.mjs` | Yes — this skill follows that design |
| Default `bd` / 909 / piano | CDN / `samples()` / soundfonts | No, unless cached locally |

`Dough.scheduleSpawn` expects `_begin` and `_duration` in **seconds**. Haps from `queryArc` are in **cycles**. Convert with `seconds = cycles / cps`.

Official live path (worklet): `_duration = hap.duration / cps`.  
Official export POC instead does `.slow(1/cps)` so cycle units become seconds. This renderer uses the live conversion, not `.slow`.

## What `setcpm` / `$: ` actually are

Published `@strudel/core` 1.2.6 also imports `@kabelsalat/web` from its REPL bundle. That import is circular in Node (`SalatRepl` is not exported yet). `render.mjs` registers `hooks/resolve.mjs` to stub `@kabelsalat/web` before loading Strudel.

`setcpm` is **not** exported by `@strudel/core`. The REPL injects:

```js
setcpm = (cpm) => scheduler.setCps(cpm / 60)
```

`$: pat` is a JS label. The transpiler turns it into `pat.p('$')`. The REPL’s `.p(id)` stores the pattern in a map and stacks them. `_$: ` mutes (leading/trailing `_`).

`render.mjs` copies that behavior so REPL-style files evaluate without a browser.

## Dough waveforms

`sine`, `saw` / `sawtooth`, `zaw` / `zawtooth`, `supersaw`, `tri` / `triangle`, `pulse` / `square`, `pulze`, `dust` / `crackle`, `impulse`, `white`, `brown`, `pink`.

Unknown `s` values log `sound not loaded` and stay silent. The renderer remaps `bd`, `sd`, `hh`, `oh`, `cp`, `cb`, `cowbell`, `rim` to these synths.

## Effects Dough understands (subset)

Gain, pan, ADSR, LPF/HPF, resonance, delay send, shape/distort, FM (`fmi`/`fmh`/`fmenv`), vibrato, chorus, coarse/crush, pitch env (`penv`).

`.room()` exists in the REPL (convolution/reverb) and is **weak or missing** in Dough — do not rely on it for the mix.

## Samples (not wired yet)

Dough can `loadSample(name, channels, sampleRate)` from decoded PCM. `doughsamples('github:...')` fetches the network. A later step is: download a CC bank once, write a local `strudel.json`, decode WAVs with a Node decoder, `loadSample` before spawn.

Until then, stay synth-only.

## Three-skill pipeline

- **`music-composition`** (sjy051) — decide key/progression/mood. Start at
  `references/00-navigation.md`. For explainers:
  `references/genres/media-and-commercial-music.md` and
  `assets/progressions-catalog.md`.
- **`strudel`** (bfollington/terma) — how to write the pattern. REPL-oriented
  (`strudel.cc` URLs, CDN banks). Use it for syntax and
  `assets/patterns/ambient-pad.js`, then strip anything Dough cannot play.
- **This renderer** — `queryArc` + Dough → WAV. That is the video deliverable.

## Cheerful beds (for create-video)

Default to **major I–IV–V–I** (C–F–G–C). That is tonic → subdominant →
dominant → tonic: tension releases home, all major triads.

**I–V–vi–IV** (C–G–Am–F) is the pop-warm variant; keep **I** as home, not vi.

Do **not** default to A minor descending **i–VII–VI–v** (Am–G–F–Em). Parallel
minor plus a falling bass is why earlier beds sounded gloomy.

Pads: long attack/release, no `bd`/`hh`. Brighter pad LPF (~1400) than a
sad cue (~600).

## Other renderers

- [rendel](https://github.com/wyote4094/rendel) — fuller CLI; default Dirt/909 samples still need network unless you add a bank.
- `node-web-audio-api` + superdough — closer to strudel.cc, heavier, not official.

This skill stays on the official Dough-in-Node path.

## License

Strudel, Dough, and this renderer are **AGPL-3.0-or-later**. Using the script in a closed-source product requires complying with AGPL.
