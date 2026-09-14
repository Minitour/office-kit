#!/usr/bin/env node
/**
 * Offline Strudel → WAV. Registers a Node loader stub for @kabelsalat/web
 * (circular with @strudel/core's REPL bundle), then runs lib.mjs.
 *
 * AGPL-3.0-or-later — https://codeberg.org/uzu/strudel
 */
import './hooks/register.mjs';
await import('./lib.mjs');
