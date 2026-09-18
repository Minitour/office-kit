<template>
  <div class="slidev-layout end ok-end">
    <slot>END</slot>
  </div>
</template>

<script setup lang="ts">
/**
 * Brand-aware replacement for Slidev's built-in `end` layout.
 *
 * Slidev's own `end.vue` styles itself in a *scoped* block
 * (`.slidev-layout.end[data-v-…] { @apply bg-black tracking-widest … }`),
 * which outranks any plain selector a deck stylesheet can write, so
 * `brand.css` could never recolour the closing slide. A local file under
 * `layouts/` replaces the theme's layout outright. This component carries no
 * brand values: every visual rule lives in `styles/brand.css` under `.ok-end`.
 */
</script>
