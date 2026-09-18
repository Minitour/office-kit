<template>
  <footer v-if="$nav.currentPage > 1" class="brand-footer">
    <div v-if="hasLogo" class="brand-logo" aria-hidden="true" />
  </footer>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

/**
 * Brand footer — every slide except the cover.
 *
 * Nothing here is brand-specific: the mark comes from --ok-logo, which
 * style.css resolves against the shared brand directory. This component never
 * holds a logo path or a company name, so it needs no regeneration when the
 * brand changes.
 *
 * The mark is painted as a CSS background rather than an <img src>. An unset
 * or unresolvable value renders nothing instead of a 404 and a broken-image
 * icon, and the probe below drops the element entirely when the deck opts out
 * with `--ok-logo: none`, so the footer reserves no empty space.
 */
const hasLogo = ref(false)

onMounted(() => {
  const token = getComputedStyle(document.documentElement)
    .getPropertyValue('--ok-logo')
    .trim()

  hasLogo.value = token !== '' && token !== 'none'
})
</script>

<style scoped>
.brand-footer {
  /* absolute, not fixed: the layer mounts inside the slide box, and in
   * export `fixed` resolves against the printed page, which clipped the
   * left third of the mark on every default-layout slide. */
  position: absolute;
  bottom: 1rem;
  left: 1.5rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  opacity: 0.5;
  pointer-events: none;
  z-index: 100;
}

.brand-logo {
  height: 24px;
  width: 96px;
  background-image: var(--ok-logo, none);
  background-repeat: no-repeat;
  background-position: left center;
  background-size: contain;
}
</style>
